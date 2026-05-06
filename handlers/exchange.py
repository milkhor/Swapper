from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, Filter
import re
from config import PRIVATE_CHANNEL_ID
from states import ExchangeStates
from services import simpleswap
# Функции теперь async, поэтому вызываем их с await ниже
from services.currencies import get_currency, get_min_amount, currency_key
from services.limiter import limiter
from database.db import save_swap, is_user_blocked
from handlers.aml import check_aml
from keyboards.inline import (
    back_to_menu, cancel_keyboard, confirm_keyboard,
    crypto_from_keyboard, crypto_to_keyboard
)

import logging

logger = logging.getLogger(__name__)
router = Router()

ADDRESS_MIN_LENGTH = {
    "btc": 25, "eth": 42, "usdt": 42,
    "sol": 32, "bnb": 42, "trx": 34,
}


# ---------------------------------------------------------------------------
# Кастомный фильтр: пропускает только если is_fiat == False
# ---------------------------------------------------------------------------

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
        await callback.message.edit_text(
            "❌ Cancelled.\n\nType /start to begin again."
        )
    except TelegramBadRequest:
        pass


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

    # 2. Проверка AML
    if not await check_aml(callback, state):
        return  # Бот сам покажет текст AML и прервет выполнение

    await state.set_state(ExchangeStates.waiting_currency_from)
    await state.update_data(is_fiat=False)
    try:
        # ИСПРАВЛЕНО: добавлен await для клавиатуры
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
    
    # ИСПРАВЛЕНО: добавлен await
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
    
    # ИСПРАВЛЕНО: добавлен await для клавиатуры
    await callback.message.edit_text(
        f"✅ Sending: <b>{currency['label']}</b>\n\n"
        f"Choose the currency you want to <b>receive</b>:",
        reply_markup=await crypto_to_keyboard(exclude_ticker=ticker, exclude_network=network)
    )


# ---------------------------------------------------------------------------
# Step 3 — Choose TO
# ---------------------------------------------------------------------------

@router.callback_query(ExchangeStates.waiting_currency_to, F.data.startswith("to_"), IsNotFiat())
async def choose_to(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.split("_")
    ticker = parts[1]
    network = parts[2]
    
    # ИСПРАВЛЕНО: добавлен await
    currency = await get_currency(ticker, network)
    if not currency:
        await callback.answer("Unknown currency", show_alert=True)
        return

    await state.update_data(
        currency_to=ticker,
        network_to=network,
        label_to=currency["label"]
    )
    await state.set_state(ExchangeStates.waiting_amount)
    data = await state.get_data()
    
    # ИСПРАВЛЕНО: добавлен await
    min_amount = await get_min_amount(data["currency_from"], data["network_from"])

    await callback.message.edit_text(
        f"✅ Receiving: <b>{currency['label']}</b>\n\n"
        f"Enter the amount in <b>{data['label_from']}</b>:\n"
        f"<i>Minimum: {min_amount} {data['currency_from'].upper()}</i>\n\n"
        f"<i>Type /cancel to abort</i>",
        reply_markup=cancel_keyboard()
    )


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
            "⚠️ Enter a valid amount.\n<i>Type /cancel to abort</i>",
            reply_markup=cancel_keyboard()
        )
        return

    # ИСПРАВЛЕНО: добавлен await
    min_amount = await get_min_amount(data["currency_from"], data["network_from"])
    
    if amount < min_amount:
        await message.answer(
            f"⚠️ Amount too small.\n\n"
            f"Minimum for <b>{data['label_from']}</b>: "
            f"<b>{min_amount} {data['currency_from'].upper()}</b>\n\n"
            f"Please enter a higher amount.\n<i>Type /cancel to abort</i>",
            reply_markup=cancel_keyboard()
        )
        return

    await state.update_data(amount=amount)
    msg = await message.answer("⏳ Fetching quote...")

    estimated_resp = await simpleswap.get_estimated(
        ticker_from=data["currency_from"],
        network_from=data["network_from"],
        ticker_to=data["currency_to"],
        network_to=data["network_to"],
        amount=str(amount)
    )

    if not estimated_resp:
        await msg.edit_text(
            f"❌ <b>Could not get a quote.</b>\n\n"
            f"Possible reasons:\n"
            f"• Amount is too small (min: {min_amount} {data['currency_from'].upper()})\n"
            f"• Pair temporarily unavailable\n"
            f"• API issue\n\n"
            f"Try a different amount.\n<i>Type /cancel to abort</i>",
            reply_markup=cancel_keyboard()
        )
        return

    await state.update_data(amount_to=estimated_resp["estimatedAmountTo"])
    await state.set_state(ExchangeStates.waiting_address)

    await msg.edit_text(
        f"💱 <b>Quote:</b>\n\n"
        f"You send: <b>{amount} {data['label_from']}</b>\n"
        f"You receive: <b>≈{estimated_resp['estimatedAmountTo']} {data['label_to']}</b>\n\n"
        f"Enter destination wallet address for <b>{data['label_to']}</b>:\n\n"
        f"<i>Type /cancel to abort</i>",
        reply_markup=cancel_keyboard()
    )


# ---------------------------------------------------------------------------
# Step 5 — Enter address
# ---------------------------------------------------------------------------

@router.message(ExchangeStates.waiting_address, IsNotFiat())
async def enter_address(message: Message, state: FSMContext):
    address = message.text.strip()
    data = await state.get_data()
    currency_to = data.get("currency_to", "")
    min_len = ADDRESS_MIN_LENGTH.get(currency_to, 10)

    if len(address) < min_len:
        await message.answer(
            f"⚠️ Address too short for <b>{data.get('label_to', currency_to)}</b>.\n"
            f"Minimum {min_len} characters, you entered {len(address)}.\n\n"
            f"<i>Type /cancel to abort</i>",
            reply_markup=cancel_keyboard()
        )
        return

    await state.update_data(address_to=address)
    await state.set_state(ExchangeStates.confirm)

    await message.answer(
        f"📋 <b>Confirm swap:</b>\n\n"
        f"You send: <b>{data['amount']} {data['label_from']}</b>\n"
        f"You receive: <b>≈{data['amount_to']} {data['label_to']}</b>\n"
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

    result = await simpleswap.create_exchange(
        ticker_from=data["currency_from"],
        network_from=data["network_from"],
        ticker_to=data["currency_to"],
        network_to=data["network_to"],
        amount=str(data["amount"]),
        address_to=data["address_to"]
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

    await save_swap(
        user_id=callback.from_user.id,
        exchange_id=exchange_id,
        currency_from=f"{data['currency_from']}_{data['network_from']}",
        currency_to=f"{data['currency_to']}_{data['network_to']}",
        amount_from=data["amount"],
        amount_to=data["amount_to"],
        address_to=data["address_to"]
    )

    # Находим этот блок в Step 6
    if PRIVATE_CHANNEL_ID:
        try:
            # Превращаем в число, если вдруг это строка
            channel_id = int(PRIVATE_CHANNEL_ID) 
            
            text = (
                f"🆕 <b>New Exchange Created</b>\n\n"
                f"🆔 <code>{exchange_id}</code>\n"
                f"👤 User: <code>{callback.from_user.id}</code>\n"
                f"🔄 {data['label_from']} → {data['label_to']}\n"
                f"💰 Amount: <b>{data['amount']} {data['currency_from'].upper()}</b>\n"
                f"📊 Status: <b>waiting</b>"
            )
            
            # Используем напрямую bot из callback
            logger.info(f"DEBUG CHANNEL: PRIVATE_CHANNEL_ID='{PRIVATE_CHANNEL_ID}' type={type(PRIVATE_CHANNEL_ID)}")
            await callback.bot.send_message(chat_id=channel_id, text=text, parse_mode="HTML")
            logger.info(f"Successfully sent log to channel {channel_id}")
            
        except Exception as e:
            logger.error(f"Channel post error: {e}")

    limiter.record(callback.from_user.id)
    await state.clear()

    await callback.message.edit_text(
        f"✅ <b>Exchange created!</b>\n\n"
        f"ID: <code>{exchange_id}</code>\n"
        f"Send <b>{data['amount']} {data['label_from']}</b> to:\n"
        f"<code>{address_from}</code>\n\n"
        f"Check status: /status_{exchange_id}",
        reply_markup=back_to_menu()
    )


@router.callback_query(ExchangeStates.confirm, F.data == "confirm_no", IsNotFiat())
async def cancel_exchange(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "❌ Exchange cancelled.",
        reply_markup=back_to_menu()
    )