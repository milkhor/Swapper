from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from html import escape

from services.fixedfloat import get_exchange
from database.db import (
    get_user_swaps,
    update_swap_payment_details,
    get_swap_by_exchange_id,
)
from keyboards.inline import active_orders_keyboard, back_to_menu, payment_details_keyboard
from services.order_details import (
    extract_payment_details,
    format_history_payment_line,
    format_payment_details,
    is_payment_active,
)

import logging

logger = logging.getLogger(__name__)
router = Router()

STATUS_EMOJI = {
    "created":    "⏳",
    "waiting":    "⏳",
    "confirming": "🔄",
    "exchanging": "💱",
    "sending":    "📤",
    "finished":   "✅",
    "failed":     "❌",
    "refunded":   "↩️",
    "expired":    "⌛",
}


@router.message(F.text.regexp(r"^/status_(.+)$"))
async def cmd_status(message: Message):
    exchange_id = message.text.split("_", 1)[1].strip()

    await message.answer("⏳ Checking status...")

    # FixedFloat needs the per-order token, which we only have for our own stored
    # orders — so look the order up locally first.
    swap = await get_swap_by_exchange_id(exchange_id)

    result = await get_exchange(exchange_id, swap.get("order_token") if swap else None)

    if not result and not swap:
        await message.answer("❌ Exchange not found. Check the ID and try again.")
        return

    if result:
        status = result.get("status", "unknown")
        address_from, payment_url = extract_payment_details(result)

        await update_swap_payment_details(
            exchange_id,
            address_from=address_from,
            payment_url=payment_url,
            status=status,
        )
        swap = await get_swap_by_exchange_id(exchange_id)

    if not swap:
        status = result.get("status", "unknown")
        address_from, payment_url = extract_payment_details(result)
        ticker_from = result.get("tickerFrom") or result.get("currency_from", "—")
        ticker_to = result.get("tickerTo") or result.get("currency_to", "—")
        network_from = result.get("networkFrom") or result.get("network_from")
        network_to = result.get("networkTo") or result.get("network_to")
        currency_from = f"{ticker_from}_{network_from}" if network_from else ticker_from
        currency_to = f"{ticker_to}_{network_to}" if network_to else ticker_to
        swap = {
            "exchange_id": exchange_id,
            "status": status,
            "currency_from": currency_from,
            "currency_to": currency_to,
            "amount_from": result.get("amountFrom") or result.get("amount_from", "—"),
            "amount_to": result.get("amountTo") or result.get("amount_to", "—"),
            "address_to": result.get("addressTo") or result.get("address_to"),
            "address_from": address_from,
            "payment_url": payment_url,
        }

    keyboard = (
        payment_details_keyboard(exchange_id, swap.get("payment_url"))
        if swap.get("user_id") == message.from_user.id and is_payment_active(swap.get("status"))
        else back_to_menu()
    )

    await message.answer(
        format_payment_details(swap),
        reply_markup=keyboard
    )
    
@router.message(Command("myorder"))
async def cmd_myorder(message: Message):
    args = message.text.split()
    
    if len(args) < 2:
        return await message.answer("Usage: /myorder ID_HERE")
    
    exchange_id = args[1]
    swap = await get_swap_by_exchange_id(exchange_id)
    
    if not swap:
        return await message.answer("Order not found.")
    if swap.get("user_id") != message.from_user.id:
        return await message.answer("Order not found.")
    
    keyboard = (
        payment_details_keyboard(exchange_id, swap.get("payment_url"))
        if is_payment_active(swap.get("status"))
        else back_to_menu()
    )
    await message.answer(format_payment_details(swap), reply_markup=keyboard)


@router.message(Command("history"))
async def cmd_history(message: Message):
    swaps = await get_user_swaps(message.from_user.id)

    if not swaps:
        await message.answer(
            "📭 You have no exchanges yet.\n\nPress /start to begin."
        )
        return

    text = "📋 <b>Your recent exchanges:</b>\n\n"

    for swap in swaps:
        status = swap.get("status", "unknown")
        emoji = STATUS_EMOJI.get(status, "❓")
        payment_line = format_history_payment_line(swap)
        destination = ""
        if payment_line and swap.get("address_to"):
            destination = f"   Destination: <code>{escape(str(swap['address_to']))}</code>\n"
        text += (
            f"{emoji} <code>{swap['exchange_id']}</code>\n"
            f"   {swap['amount_from']} {swap['currency_from'].upper()} → "
            f"{swap['currency_to'].upper()}\n"
            f"   {payment_line}"
            f"{destination}"
            f"   /status_{swap['exchange_id']}\n\n"
        )

    await message.answer(text, reply_markup=active_orders_keyboard(swaps))
