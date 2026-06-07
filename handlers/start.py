from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from keyboards.inline import main_menu, back_to_menu
from database.db import get_user_lang, ensure_user_registered, get_user_rank, get_user_swaps
from services.i18n import t
from services.order_details import is_payment_active
from services.prices import get_prices, format_prices

router = Router()

async def _active_orders_notice(user_id: int) -> str:
    """Return a notice string if user has active (waiting) orders, else empty string."""
    try:
        swaps = await get_user_swaps(user_id)
        active = [s for s in swaps if is_payment_active(s.get("status"))]
        if active:
            count = len(active)
            label = "order" if count == 1 else "orders"
            return f"\n\n⚠️ You have <b>{count} active {label}</b> awaiting payment. Tap 📜 My History to view payment details."
    except Exception:
        pass
    return ""


@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    await ensure_user_registered(user_id)

    lang = await get_user_lang(user_id)
    emoji, rank_name, swap_count = await get_user_rank(user_id)
    notice = await _active_orders_notice(user_id)

    welcome_text = f"{t(lang, 'welcome')}\n\n{emoji} <b>Rank:</b> {rank_name} ({swap_count} swaps){notice}"

    await message.answer(
        text=welcome_text,
        reply_markup=main_menu(lang)
    )

@router.callback_query(F.data == "action_prices")
async def callback_prices(callback: CallbackQuery):
    prices = await get_prices()
    if not prices:
        return await callback.answer("Error fetching prices.", show_alert=True)
    
    await callback.message.edit_text(
        text=format_prices(prices),
        reply_markup=back_to_menu(await get_user_lang(callback.from_user.id))
    )


@router.callback_query(F.data == "action_how")
async def callback_how(callback: CallbackQuery):
    await callback.answer()
    lang = await get_user_lang(callback.from_user.id)
    await callback.message.edit_text(
        text=t(lang, "how_it_works"),
        reply_markup=back_to_menu(lang)
    )


@router.callback_query(F.data == "action_back")
async def callback_back(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)
    notice = await _active_orders_notice(user_id)
    await callback.message.edit_text(
        text=f"{t(lang, 'welcome')}{notice}",
        reply_markup=main_menu(lang)
    )


@router.callback_query(F.data == "action_menu")
async def callback_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)
    notice = await _active_orders_notice(user_id)
    await callback.message.answer(
        text=f"{t(lang, 'welcome')}{notice}",
        reply_markup=main_menu(lang)
    )


@router.callback_query(F.data == "action_language")
async def callback_language(callback: CallbackQuery):
    await callback.answer()
    from handlers.language import language_keyboard
    lang = await get_user_lang(callback.from_user.id)
    await callback.message.edit_text(
        text=t(lang, "choose_language"),
        reply_markup=language_keyboard()
    )
