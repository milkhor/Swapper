from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu(lang: str = "en") -> InlineKeyboardMarkup:
    from services.i18n import t
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_swap"),     callback_data="action_swap")],
        [InlineKeyboardButton(text=t(lang, "btn_buy_card"), callback_data="action_fiat")],
        [InlineKeyboardButton(text="📜 My History",         callback_data="action_history")],
        [InlineKeyboardButton(text=t(lang, "btn_how"),      callback_data="action_how")],
        [InlineKeyboardButton(text="📊 Prices", callback_data="action_prices")],
        [InlineKeyboardButton(text=t(lang, "btn_language"), callback_data="action_language")],
    ])


def back_to_menu(lang: str = "en") -> InlineKeyboardMarkup:
    from services.i18n import t
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="action_back")]
    ])


def cancel_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    from services.i18n import t
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="action_back")]
    ])


def confirm_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    from services.i18n import t
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t(lang, "btn_confirm"), callback_data="confirm_yes"),
            InlineKeyboardButton(text=t(lang, "btn_cancel"),  callback_data="confirm_no"),
        ]
    ])


def fiat_confirm_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    from services.i18n import t
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t(lang, "btn_confirm"), callback_data="fiat_confirm_yes"),
            InlineKeyboardButton(text=t(lang, "btn_cancel"),  callback_data="fiat_confirm_no"),
        ]
    ])


def swap_mode_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    from services.i18n import t
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Send Amount", callback_data="mode_send")],
        [InlineKeyboardButton(text="💰 Receive Amount", callback_data="mode_receive")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="action_back")]
    ])


def admin_back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Back to Admin", callback_data="admin_main")]
    ])


async def crypto_from_keyboard(lang: str = "en",
                                exclude_ticker: str = None,
                                exclude_network: str = None) -> InlineKeyboardMarkup:
    from database.db import get_currencies
    from services.i18n import t
    currencies = await get_currencies(crypto_only=True, active_only=True)
    buttons = []
    row = []
    for c in currencies:
        if c["ticker"] == exclude_ticker and c["network"] == exclude_network:
            continue
        row.append(InlineKeyboardButton(
            text=c["label"],
            callback_data=f"from_{c['ticker']}_{c['network']}"
        ))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="action_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def crypto_to_keyboard(lang: str = "en",
                              exclude_ticker: str = None,
                              exclude_network: str = None) -> InlineKeyboardMarkup:
    from database.db import get_currencies
    from services.i18n import t
    currencies = await get_currencies(crypto_only=True, active_only=True)
    buttons = []
    row = []
    for c in currencies:
        if c["ticker"] == exclude_ticker and c["network"] == exclude_network:
            continue
        row.append(InlineKeyboardButton(
            text=c["label"],
            callback_data=f"to_{c['ticker']}_{c['network']}"
        ))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="action_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def fiat_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    from database.db import get_currencies
    from services.i18n import t
    currencies = await get_currencies(fiat_only=True, active_only=True)
    buttons = []
    for c in currencies:
        buttons.append([InlineKeyboardButton(
            text=c["label"],
            callback_data=f"fiat_{c['ticker']}_{c['network']}"
        )])
    buttons.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="action_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Русский",  callback_data="lang_ru"),
            InlineKeyboardButton(text="🇬🇧 English",  callback_data="lang_en"),
        ],
        [
            InlineKeyboardButton(text="🇩🇪 Deutsch",  callback_data="lang_de"),
            InlineKeyboardButton(text="🇫🇷 Français", callback_data="lang_fr"),
        ],
        [
            InlineKeyboardButton(text="🇮🇷 فارسی",    callback_data="lang_fa"),
            InlineKeyboardButton(text="🇸🇦 العربية",  callback_data="lang_ar"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Back",       callback_data="action_back"),
        ],
    ])
