from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from keyboards.inline import main_menu, back_to_menu
from database.db import get_user_lang, ensure_user_registered, get_user_rank, get_user_swaps
from services.i18n import t
from services.order_details import is_payment_active
from services.prices import get_prices, format_prices

router = Router()

PRIVACY_TEXT = {
    "en": (
        "🔒 <b>Privacy Policy — Telegram Bot &amp; Exchange Transactions</b>\n\n"
        "When you use our Telegram bot to create, pay for, or complete an exchange "
        "transaction, we may collect and process certain information associated with "
        "your Telegram account, including your Telegram user ID, username (if available), "
        "and language settings.\n\n"
        "We may associate this information with transaction-related information, including "
        "an internal transaction identifier, the exchange provider's order or exchange "
        "identifier, transaction status, and relevant timestamps.\n\n"
        "We process this information to provide and operate the exchange service, maintain "
        "transaction records, prevent misuse, investigate technical or security incidents, "
        "comply with contractual and legal obligations, and respond to valid requests "
        "relating to specific transactions.\n\n"
        "Transaction-related user information may be retained for at least one year where "
        "required for the operation of our exchange services or by our service providers. "
        "Information may be retained for a longer period where necessary to comply with "
        "applicable legal obligations, resolve disputes, or protect our legitimate interests.\n\n"
        "We may share relevant information with service providers involved in processing or "
        "facilitating an exchange (including the exchange provider FixedFloat), and with "
        "competent authorities or other parties where disclosure is required or permitted by "
        "applicable law. We do not disclose user information in response to arbitrary or "
        "unauthorized requests.\n\n"
        "Access to stored transaction-related user information is restricted to authorized "
        "personnel and is subject to appropriate technical and organizational security measures.\n\n"
        "You may contact us using the contact details provided in this Privacy Policy to "
        "exercise any privacy rights available to you under applicable law."
    ),
    "ru": (
        "🔒 <b>Политика конфиденциальности — Telegram-бот и обменные операции</b>\n\n"
        "Когда вы используете нашего Telegram-бота для создания, оплаты или завершения "
        "обменной операции, мы можем собирать и обрабатывать определённую информацию, "
        "связанную с вашим аккаунтом Telegram, включая ваш Telegram user ID, имя "
        "пользователя (username, если доступно) и языковые настройки.\n\n"
        "Мы можем связывать эту информацию с данными о транзакции, включая внутренний "
        "идентификатор транзакции, идентификатор заказа/обмена провайдера, статус "
        "транзакции и соответствующие отметки времени.\n\n"
        "Мы обрабатываем эту информацию, чтобы предоставлять и обеспечивать работу обменного "
        "сервиса, вести учёт транзакций, предотвращать злоупотребления, расследовать "
        "технические инциденты и инциденты безопасности, соблюдать договорные и юридические "
        "обязательства и отвечать на обоснованные запросы, касающиеся конкретных транзакций.\n\n"
        "Информация о пользователе, связанная с транзакцией, может храниться не менее одного "
        "года, если это требуется для работы наших обменных сервисов или нашими поставщиками "
        "услуг. Информация может храниться дольше, если это необходимо для соблюдения "
        "применимых юридических обязательств, разрешения споров или защиты наших законных "
        "интересов.\n\n"
        "Мы можем передавать соответствующую информацию поставщикам услуг, участвующим в "
        "проведении обмена (включая обменного провайдера FixedFloat), а также компетентным "
        "органам или иным лицам, если раскрытие требуется или разрешено применимым "
        "законодательством. Мы не раскрываем информацию о пользователях в ответ на "
        "произвольные или несанкционированные запросы.\n\n"
        "Доступ к хранимой информации о пользователях, связанной с транзакциями, ограничен "
        "уполномоченным персоналом и защищён соответствующими техническими и "
        "организационными мерами безопасности.\n\n"
        "Вы можете связаться с нами по контактным данным, указанным в настоящей Политике, "
        "чтобы реализовать любые права на конфиденциальность, доступные вам согласно "
        "применимому законодательству."
    ),
}


def _privacy_text(lang: str) -> str:
    return PRIVACY_TEXT.get(lang, PRIVACY_TEXT["en"])

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


@router.callback_query(F.data == "action_privacy")
async def callback_privacy(callback: CallbackQuery):
    await callback.answer()
    lang = await get_user_lang(callback.from_user.id)
    await callback.message.edit_text(
        text=_privacy_text(lang),
        reply_markup=back_to_menu(lang),
        disable_web_page_preview=True,
    )


@router.message(Command("privacy"))
async def cmd_privacy(message: Message):
    lang = await get_user_lang(message.from_user.id)
    await message.answer(
        text=_privacy_text(lang),
        reply_markup=back_to_menu(lang),
        disable_web_page_preview=True,
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
