from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from html import escape

from keyboards.inline import active_orders_keyboard, back_to_menu, payment_details_keyboard
from database.db import (
    get_swap_by_exchange_id,
    get_user_swaps,
    update_swap_payment_details,
)
from services.order_details import (
    extract_payment_details,
    format_history_payment_line,
    format_payment_details,
    is_payment_active,
)
from services.simpleswap import get_exchange

router = Router()

STATUS_EMOJI = {
    "created": "⏳",
    "waiting": "⏳",
    "confirming": "🔄",
    "exchanging": "💱",
    "sending": "📤",
    "finished": "✅",
    "failed": "❌",
    "refunded": "↩️",
    "expired": "⌛",
}

@router.callback_query(F.data == "action_history")
async def show_history(callback: CallbackQuery):
    await callback.answer()
    
    # Получаем последние 5-10 обменов пользователя
    swaps = await get_user_swaps(callback.from_user.id)
    
    if not swaps:
        await callback.message.edit_text(
            "📭 You haven't made any swaps yet.",
            reply_markup=back_to_menu()
        )
        return

    text = "📜 <b>Your Swap History:</b>\n\n"
    for s in swaps:
        status_icon = STATUS_EMOJI.get(s.get("status"), "❓")
        payment_line = format_history_payment_line(s)
        destination = ""
        if payment_line and s.get("address_to"):
            destination = f"👛 Destination wallet:\n<code>{escape(str(s['address_to']))}</code>\n"
        
        text += (
            f"{status_icon} <code>{s['exchange_id']}</code>\n"
            f"🔄 {s['currency_from'].upper()} ➡️ {s['currency_to'].upper()}\n"
            f"💰 {s['amount_from']} → {s['amount_to']}\n"
            f"📅 Status: <b>{s['status']}</b>\n"
            f"{payment_line}"
            f"{destination}"
            f"---------------------------\n"
        )

    await callback.message.edit_text(text, reply_markup=active_orders_keyboard(swaps))


@router.callback_query(F.data.startswith("view_payment_"))
async def view_payment_details(callback: CallbackQuery):
    await callback.answer()
    exchange_id = callback.data.removeprefix("view_payment_")
    swap = await get_swap_by_exchange_id(exchange_id)

    if not swap or swap.get("user_id") != callback.from_user.id:
        await callback.answer("Order not found.", show_alert=True)
        return

    if is_payment_active(swap.get("status")):
        result = await get_exchange(exchange_id)
        if result:
            status = result.get("status") or swap.get("status")
            address_from, payment_url = extract_payment_details(result)
            await update_swap_payment_details(
                exchange_id,
                address_from=address_from,
                payment_url=payment_url,
                status=status,
            )
            if address_from:
                swap["address_from"] = address_from
            if payment_url:
                swap["payment_url"] = payment_url
            if status:
                swap["status"] = status

    keyboard = (
        payment_details_keyboard(exchange_id, swap.get("payment_url"))
        if is_payment_active(swap.get("status"))
        else back_to_menu()
    )

    try:
        await callback.message.edit_text(
            format_payment_details(swap),
            reply_markup=keyboard
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
