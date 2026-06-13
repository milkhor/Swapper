from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, Filter
from config import PRIVATE_CHANNEL_ID
from states import ExchangeStates
from services import simpleswap
from services.address_validation import validate_wallet_address
from services.amount_limits import format_limit_amount, get_pair_limits
from services.currencies import get_currency
from services.order_details import format_payment_details
from services.limiter import limiter
from database.db import get_user_lang, save_swap, is_user_blocked
from handlers.aml import check_aml
from services.i18n import t
from keyboards.inline import (
    back_to_menu, cancel_keyboard, confirm_keyboard, exchange_cancel_keyboard,
    amount_mode_keyboard, main_menu,
    crypto_from_keyboard, crypto_to_keyboard, payment_details_keyboard
)

import logging

logger = logging.getLogger(__name__)
router = Router()


class IsNotFiat(Filter):
    async def __call__(self, update: CallbackQuery | Message, state: FSMContext) -> bool:
        data = await state.get_data()
        return not data.get("is_fiat", False)


# ---------------------------------------------------------------------------
# /cancel
# ---------------------------------------------------------------------------

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current = await state.get_state()
    if current is None:
        await message.answer("No active action. Type /start")
        return
    await state.clear()
    await message.answer("❌ Cancelled.\n\nType /start to begin again.")


@router.callback_query(F.data == "action_cancel")
async def callback_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    try:
        await callback.message.edit_text("❌ Cancelled.\n\nType /start to begin again.")
    except TelegramBadRequest:
        pass


# ---------------------------------------------------------------------------
# swap_back — step-by-step Back navigation within the swap flow
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "swap_back")
async def swap_back_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    current = await state.get_state()
    data = await state.get_data()

    try:
        if current == ExchangeStates.waiting_currency_to:
            await state.set_state(ExchangeStates.waiting_currency_from)
            await callback.message.edit_text(
                "🔄 <b>New swap</b>\n\nChoose the currency you want to <b>send</b>:",
                reply_markup=await crypto_from_keyboard()
            )

        elif current == ExchangeStates.waiting_amount_mode:
            await state.set_state(ExchangeStates.waiting_currency_to)
            label_from = data.get("label_from", data.get("currency_from", "?").upper())
            await callback.message.edit_text(
                f"✅ Sending: <b>{label_from}</b>\n\n"
                f"Choose the currency you want to <b>receive</b>:",
                reply_markup=await crypto_to_keyboard(
                    exclude_ticker=data.get("currency_from"),
                    exclude_network=data.get("network_from"),
                )
            )

        elif current == ExchangeStates.waiting_amount:
            await state.set_state(ExchangeStates.waiting_amount_mode)
            label_from = data.get("label_from", "?")
            label_to = data.get("label_to", "?")
            await callback.message.edit_text(
                f"✅ Pair: <b>{label_from} → {label_to}</b>\n\n"
                f"How would you like to specify the amount?",
                reply_markup=amount_mode_keyboard()
            )

        elif current == ExchangeStates.waiting_address:
            await state.set_state(ExchangeStates.waiting_amount)
            mode = data.get("amount_mode", "send")
            if mode == "receive":
                amount_label = data.get("label_to", "?")
                ticker = data.get("currency_to", "?").upper()
                prompt_prefix = f"Enter the amount of <b>{amount_label}</b> you want to <b>receive</b>:"
            else:
                amount_label = data.get("label_from", "?")
                ticker = data.get("currency_from", "?").upper()
                prompt_prefix = f"Enter the amount of <b>{amount_label}</b> you want to <b>send</b>:"

            min_amount = data.get("min_amount", 0)
            min_label = "Current minimum" if data.get("min_amount_source") == "api" else "Configured minimum"
            await callback.message.edit_text(
                f"{prompt_prefix}\n"
                f"<i>{min_label}: {format_limit_amount(min_amount)} {ticker}</i>\n\n"
                f"<i>Type /cancel to abort</i>",
                reply_markup=exchange_cancel_keyboard()
            )

        elif current == ExchangeStates.confirm:
            await state.set_state(ExchangeStates.waiting_address)
            mode = data.get("amount_mode", "send")
            amount = data.get("amount", "?")
            amount_to = data.get("amount_to", "?")
            label_from = data.get("label_from", "?")
            label_to = data.get("label_to", "?")
            if mode == "receive":
                send_str = f"≈{amount} {label_from}"
                receive_str = f"{amount_to} {label_to}"
            else:
                send_str = f"{amount} {label_from}"
                receive_str = f"≈{amount_to} {label_to}"
            await callback.message.edit_text(
                f"💱 <b>Quote:</b>\n\n"
                f"You send: <b>{send_str}</b>\n"
                f"You receive: <b>{receive_str}</b>\n\n"
                f"Enter destination wallet address for <b>{label_to}</b>:\n\n"
                f"<i>Type /cancel to abort</i>",
                reply_markup=exchange_cancel_keyboard()
            )

        else:
            await state.clear()
            lang = await get_user_lang(callback.from_user.id)
            await callback.message.edit_text(t(lang, "welcome"), reply_markup=main_menu(lang))

    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


# ---------------------------------------------------------------------------
# Step 1 — Start swap
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "action_swap")
async def start_swap(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    allowed, reason = limiter.check(callback.from_user.id)
    if not allowed:
        await callback.message.edit_text(reason, reply_markup=back_to_menu())
        return

    if await is_user_blocked(callback.from_user.id):
        return await callback.answer("You are blocked.", show_alert=True)

    if not await check_aml(callback, state):
        return

    await state.set_state(ExchangeStates.waiting_currency_from)
    await state.update_data(is_fiat=False)
    try:
        await callback.message.edit_text(
            "🔄 <b>New swap</b>\n\nChoose the currency you want to <b>send</b>:",
            reply_markup=await crypto_from_keyboard()
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


# ---------------------------------------------------------------------------
# Step 2 — Choose FROM
# ---------------------------------------------------------------------------

@router.callback_query(ExchangeStates.waiting_currency_from, F.data.startswith("from_"))
async def choose_from(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.split("_")
    ticker = parts[1]
    network = parts[2]

    currency = await get_currency(ticker, network)
    if not currency:
        await callback.answer("Unknown currency", show_alert=True)
        return

    await state.update_data(
        currency_from=ticker,
        network_from=network,
        label_from=currency["label"]
    )
    await state.set_state(ExchangeStates.waiting_currency_to)

    try:
        await callback.message.edit_text(
            f"✅ Sending: <b>{currency['label']}</b>\n\n"
            f"Choose the currency you want to <b>receive</b>:",
            reply_markup=await crypto_to_keyboard(exclude_ticker=ticker, exclude_network=network)
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


# ---------------------------------------------------------------------------
# Step 3 — Choose TO
# ---------------------------------------------------------------------------

@router.callback_query(ExchangeStates.waiting_currency_to, F.data.startswith("to_"), IsNotFiat())
async def choose_to(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.split("_")
    ticker = parts[1]
    network = parts[2]

    currency = await get_currency(ticker, network)
    if not currency:
        await callback.answer("Unknown currency", show_alert=True)
        return

    await state.update_data(
        currency_to=ticker,
        network_to=network,
        label_to=currency["label"]
    )

    data = await state.get_data()
    await state.set_state(ExchangeStates.waiting_amount_mode)

    try:
        await callback.message.edit_text(
            f"✅ Pair: <b>{data['label_from']} → {currency['label']}</b>\n\n"
            f"How would you like to specify the amount?",
            reply_markup=amount_mode_keyboard()
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


# ---------------------------------------------------------------------------
# Step 3.5 — Choose amount mode (Send or Receive)
# ---------------------------------------------------------------------------

@router.callback_query(ExchangeStates.waiting_amount_mode, F.data.in_({"mode_send", "mode_receive"}), IsNotFiat())
async def choose_amount_mode(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    mode = "send" if callback.data == "mode_send" else "receive"
    await state.update_data(amount_mode=mode)
    data = await state.get_data()

    limits = await get_pair_limits(
        data["currency_from"],
        data["network_from"],
        data["currency_to"],
        data["network_to"],
        reverse=(mode == "receive"),
    )
    await state.update_data(
        min_amount=limits["min"],
        max_amount=limits["max"],
        min_amount_source=limits["source"],
    )
    await state.set_state(ExchangeStates.waiting_amount)

    min_amount = format_limit_amount(limits["min"])
    min_label = "Current minimum" if limits["source"] == "api" else "Configured minimum"

    if mode == "receive":
        amount_label = data["label_to"]
        ticker = data["currency_to"].upper()
        prompt = (
            f"Enter the amount of <b>{amount_label}</b> you want to <b>receive</b>:\n"
            f"<i>{min_label}: {min_amount} {ticker}</i>\n\n"
            f"<i>Type /cancel to abort</i>"
        )
    else:
        amount_label = data["label_from"]
        ticker = data["currency_from"].upper()
        prompt = (
            f"Enter the amount of <b>{amount_label}</b> you want to <b>send</b>:\n"
            f"<i>{min_label}: {min_amount} {ticker}</i>\n\n"
            f"<i>Type /cancel to abort</i>"
        )

    await callback.message.edit_text(prompt, reply_markup=exchange_cancel_keyboard())


# ---------------------------------------------------------------------------
# Step 4 — Enter amount
# ---------------------------------------------------------------------------

@router.message(ExchangeStates.waiting_amount, IsNotFiat())
async def enter_amount(message: Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("currency_from"):
        return

    try:
        amount_str = message.text.replace(",", ".")
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer(
            "⚠️ Enter a valid positive number.\n<i>Type /cancel to abort</i>",
            reply_markup=exchange_cancel_keyboard()
        )
        return

    mode = data.get("amount_mode", "send")

    # Use limits already fetched and cached in choose_amount_mode step
    min_amount = data.get("min_amount") or 0.0
    max_amount = data.get("max_amount")
    min_label = "Current minimum" if data.get("min_amount_source") == "api" else "Configured minimum"

    if mode == "receive":
        ticker = data["currency_to"].upper()
    else:
        ticker = data["currency_from"].upper()

    if min_amount and amount < min_amount:
        await message.answer(
            f"⚠️ Amount too small.\n\n"
            f"{min_label}: <b>{format_limit_amount(min_amount)} {ticker}</b>\n\n"
            f"Please enter a higher amount.\n<i>Type /cancel to abort</i>",
            reply_markup=exchange_cancel_keyboard()
        )
        return

    if max_amount is not None and amount > max_amount:
        await message.answer(
            f"⚠️ Amount too large.\n\n"
            f"Maximum: <b>{format_limit_amount(max_amount)} {ticker}</b>\n\n"
            f"Please enter a lower amount.\n<i>Type /cancel to abort</i>",
            reply_markup=exchange_cancel_keyboard()
        )
        return

    msg = await message.answer("⏳ Fetching quote...")

    estimated_resp = await simpleswap.get_estimated(
        ticker_from=data["currency_from"],
        network_from=data["network_from"],
        ticker_to=data["currency_to"],
        network_to=data["network_to"],
        amount=str(amount),
        reverse=(mode == "receive"),
    )

    if not estimated_resp:
        await msg.edit_text(
            f"❌ <b>Could not get a quote.</b>\n\n"
            f"This pair may be temporarily unavailable or the amount is outside the supported range. "
            f"Please try a different amount or check back later.\n"
            f"<i>Type /cancel to abort</i>",
            reply_markup=exchange_cancel_keyboard()
        )
        return

    if mode == "receive":
        amount_to_send = estimated_resp.get("estimatedAmountFrom")
        amount_to_receive = amount
        if amount_to_send is None:
            await msg.edit_text(
                f"❌ <b>Could not calculate the required send amount.</b>\n\n"
                f"Please try again or choose a different pair.\n"
                f"<i>Type /cancel to abort</i>",
                reply_markup=exchange_cancel_keyboard()
            )
            return
        await state.update_data(
            amount=amount_to_send,
            amount_to=amount_to_receive,
            rate_id=estimated_resp.get("rateId"),
        )
        send_str = f"≈{amount_to_send} {data['label_from']}"
        receive_str = f"{amount_to_receive} {data['label_to']}"
    else:
        await state.update_data(
            amount=amount,
            amount_to=estimated_resp["estimatedAmountTo"],
            rate_id=estimated_resp.get("rateId"),
        )
        send_str = f"{amount} {data['label_from']}"
        receive_str = f"≈{estimated_resp['estimatedAmountTo']} {data['label_to']}"

    await state.set_state(ExchangeStates.waiting_address)

    await msg.edit_text(
        f"💱 <b>Quote:</b>\n\n"
        f"You send: <b>{send_str}</b>\n"
        f"You receive: <b>{receive_str}</b>\n\n"
        f"Enter destination wallet address for <b>{data['label_to']}</b>:\n\n"
        f"<i>Type /cancel to abort</i>",
        reply_markup=exchange_cancel_keyboard()
    )


# ---------------------------------------------------------------------------
# Step 5 — Enter address
# ---------------------------------------------------------------------------

@router.message(ExchangeStates.waiting_address, IsNotFiat())
async def enter_address(message: Message, state: FSMContext):
    address = message.text.strip()
    data = await state.get_data()
    currency_to = data.get("currency_to", "")

    is_valid, error = await validate_wallet_address(
        address=address,
        ticker=currency_to,
        network=data.get("network_to", ""),
        label=data.get("label_to", currency_to.upper()),
    )
    if not is_valid:
        await message.answer(
            f"{error}\n\n<i>Type /cancel to abort</i>",
            reply_markup=exchange_cancel_keyboard()
        )
        return

    await state.update_data(address_to=address)
    await state.set_state(ExchangeStates.confirm)

    mode = data.get("amount_mode", "send")
    amount = data.get("amount")
    amount_to = data.get("amount_to")
    if mode == "receive":
        send_str = f"≈{amount} {data['label_from']}"
        receive_str = f"{amount_to} {data['label_to']}"
    else:
        send_str = f"{amount} {data['label_from']}"
        receive_str = f"≈{amount_to} {data['label_to']}"

    await message.answer(
        f"📋 <b>Confirm swap:</b>\n\n"
        f"You send: <b>{send_str}</b>\n"
        f"You receive: <b>{receive_str}</b>\n"
        f"Address: <code>{address}</code>\n\n"
        f"Everything correct?",
        reply_markup=confirm_keyboard()
    )


# ---------------------------------------------------------------------------
# Step 6 — Confirm
# ---------------------------------------------------------------------------

@router.callback_query(ExchangeStates.confirm, F.data == "confirm_yes", IsNotFiat())
async def confirm_exchange(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()

    await callback.message.edit_text("⏳ Creating exchange...")

    is_receive_mode = data.get("amount_mode") == "receive"

    # Refresh estimate right before creating the exchange to avoid using an expired rateId
    try:
        fresh_est = await simpleswap.get_estimated(
            ticker_from=data["currency_from"],
            network_from=data["network_from"],
            ticker_to=data["currency_to"],
            network_to=data["network_to"],
            amount=str(data["amount"]),
            reverse=is_receive_mode,
        )
    except Exception as e:
        logger.warning(f"Could not refresh estimate before create: {e}")
        fresh_est = None

    rate_id_to_use = None
    if fresh_est and fresh_est.get("rateId"):
        rate_id_to_use = fresh_est.get("rateId")
    else:
        rate_id_to_use = data.get("rate_id")

    result = await simpleswap.create_exchange(
        ticker_from=data["currency_from"],
        network_from=data["network_from"],
        ticker_to=data["currency_to"],
        network_to=data["network_to"],
        amount=str(data["amount"]),
        address_to=data["address_to"],
        fixed=is_receive_mode,
        rate_id=rate_id_to_use
    )

    if not result:
        await callback.message.edit_text(
            "❌ Failed to create exchange. Please try again later.",
            reply_markup=back_to_menu()
        )
        await state.clear()
        return

    exchange_id = result.get("id") or result.get("exchangeId")
    address_from = result.get("addressFrom") or result.get("address_from")
    payment_url = result.get("redirectUrl") or result.get("paymentUrl") or result.get("redirect_url")
    status = result.get("status") or "waiting"

    await save_swap(
        user_id=callback.from_user.id,
        exchange_id=exchange_id,
        currency_from=f"{data['currency_from']}_{data['network_from']}",
        currency_to=f"{data['currency_to']}_{data['network_to']}",
        amount_from=data["amount"],
        amount_to=data["amount_to"],
        address_to=data["address_to"],
        address_from=address_from,
        payment_url=payment_url,
        status=status,
    )

    if PRIVATE_CHANNEL_ID:
        try:
            channel_id = int(PRIVATE_CHANNEL_ID)
            text = (
                f"🆕 <b>New Exchange Created</b>\n\n"
                f"🆔 <code>{exchange_id}</code>\n"
                f"👤 User: <code>{callback.from_user.id}</code>\n"
                f"🔄 {data['label_from']} → {data['label_to']}\n"
                f"💰 Amount: <b>{data['amount']} {data['currency_from'].upper()}</b>\n"
                f"📊 Status: <b>waiting</b>"
            )
            logger.info(f"DEBUG CHANNEL: PRIVATE_CHANNEL_ID='{PRIVATE_CHANNEL_ID}' type={type(PRIVATE_CHANNEL_ID)}")
            await callback.bot.send_message(chat_id=channel_id, text=text, parse_mode="HTML")
            logger.info(f"Successfully sent log to channel {channel_id}")
        except Exception as e:
            logger.error(f"Channel post error: {e}")

    limiter.record(callback.from_user.id)
    await state.clear()

    swap_details = {
        "exchange_id": exchange_id,
        "status": status,
        "currency_from": f"{data['currency_from']}_{data['network_from']}",
        "currency_to": f"{data['currency_to']}_{data['network_to']}",
        "amount_from": data["amount"],
        "amount_to": data["amount_to"],
        "address_to": data["address_to"],
        "address_from": address_from,
        "payment_url": payment_url,
    }

    await callback.message.edit_text(
        format_payment_details(swap_details),
        reply_markup=payment_details_keyboard(exchange_id, payment_url)
    )


@router.callback_query(ExchangeStates.confirm, F.data == "confirm_no", IsNotFiat())
async def cancel_exchange(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "❌ Exchange cancelled.",
        reply_markup=back_to_menu()
    )
