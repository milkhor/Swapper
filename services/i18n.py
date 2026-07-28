TEXTS = {
    "ru": {
        "welcome": (
            "👋 Привет! Я бот для обмена криптовалют через FixedFloat.\n\n"
            "⚡ Быстро, без регистрации, без KYC.\n\n"
            "Выбери действие:"
        ),
        "how_it_works": (
            "📖 <b>Как это работает:</b>\n\n"
            "1. Выбираешь валюту и сумму\n"
            "2. Получаешь курс обмена\n"
            "3. Подтверждаешь — я создаю обмен\n"
            "4. Отправляешь крипту на адрес\n"
            "5. Получаешь обмененные монеты 🎉\n\n"
            "<i>Powered by FixedFloat</i>"
        ),
        "btn_swap": "🔄 Обменять",
        "btn_buy_card": "💳 Купить картой",
        "btn_how": "ℹ️ Как это работает?",
        "btn_back": "🔙 Назад",
        "btn_cancel": "❌ Отмена",
        "btn_confirm": "✅ Подтвердить",
        "btn_language": "🌐 Язык / Language",
        "choose_from": "🔄 <b>Новый обмен</b>\n\nВыбери валюту, которую хочешь <b>отдать</b>:",
        "choose_to": "✅ Отдаёшь: <b>{from_label}</b>\n\nТеперь выбери валюту, которую хочешь <b>получить</b>:",
        "enter_amount": "✅ Получаешь: <b>{to_label}</b>\n\nВведи сумму в <b>{from_label}</b>:\n<i>Минимум: {min} {ticker}</i>\n\n<i>/cancel для отмены</i>",
        "fetching_quote": "⏳ Получаю котировку...",
        "quote": "💱 <b>Котировка:</b>\n\nОтдаёшь: <b>{amount} {from_label}</b>\nПолучаешь: <b>≈{amount_to} {to_label}</b>\n\nВведи адрес кошелька для получения <b>{to_label}</b>:\n\n<i>/cancel для отмены</i>",
        "amount_too_small": "⚠️ Сумма слишком маленькая.\n\nМинимум для <b>{from_label}</b>: <b>{min} {ticker}</b>\n\n<i>/cancel для отмены</i>",
        "quote_failed": "❌ <b>Не удалось получить котировку.</b>",
        "confirm": "📋 <b>Подтверди обмен:</b>\n\nОтдаёшь: <b>{amount} {from_label}</b>\nПолучаешь: <b>≈{amount_to} {to_label}</b>\nАдрес: <code>{address}</code>\n\nВсё верно?",
        "creating": "⏳ Создаю обмен...",
        "created": "✅ <b>Обмен создан!</b>\n\nID: <code>{id}</code>\nОтправь <b>{amount} {from_label}</b> на адрес:\n<code>{address_from}</code>",
        "create_failed": "❌ Не удалось создать обмен.",
        "cancelled": "❌ Отменено.",
        "no_active": "Нет активного действия.",
        "invalid_amount": "⚠️ Введи корректную сумму",
        "address_short": "⚠️ Адрес слишком короткий для <b>{label}</b>.",
        "choose_language": "🌐 Выбери язык:",
        "language_set": "✅ Язык изменён на Русский",
        "fiat_choose": "💳 <b>Купить крипту картой</b>\n\nВыбери валюту оплаты:",
        "fiat_enter_amount": "Введите сумму:",
        "fiat_created": "✅ <b>Заказ создан!</b>\n\nОплати здесь:\n{url}",
        "fiat_created_no_url": "✅ <b>Заказ создан!</b>",
    },

    "en": {
        "welcome": (
            "👋 Hello! I'm a crypto exchange bot powered by FixedFloat.\n\n"
            "⚡ Fast, no registration, no KYC.\n\n"
            "Choose an action:"
        ),
        "how_it_works": (
            "📖 <b>How it works:</b>\n\n"
            "1. Choose assets and amount\n"
            "2. Get exchange rate\n"
            "3. Confirm — I'll create an exchange\n"
            "4. Send crypto to the provided address\n"
            "5. Receive your coins 🎉\n\n"
            "<i>Powered by FixedFloat</i>"
        ),
        "btn_swap": "🔄 Swap",
        "btn_buy_card": "💳 Buy with card",
        "btn_how": "ℹ️ How it works?",
        "btn_back": "🔙 Back",
        "btn_cancel": "❌ Cancel",
        "btn_confirm": "✅ Confirm",
        "btn_language": "🌐 Language",
        "choose_from": "🔄 <b>New swap</b>\n\nChoose the currency you want to <b>send</b>:",
        "choose_to": "✅ Sending: <b>{from_label}</b>\n\nNow choose the currency you want to <b>receive</b>:",
        "enter_amount": "✅ Receiving: <b>{to_label}</b>\n\nEnter the amount in <b>{from_label}</b>:\n<i>Minimum: {min} {ticker}</i>\n\n<i>/cancel to abort</i>",
        "fetching_quote": "⏳ Fetching quote...",
        "quote": "💱 <b>Quote:</b>\n\nYou send: <b>{amount} {from_label}</b>\nYou receive: <b>≈{amount_to} {to_label}</b>\n\nEnter your wallet address for receiving <b>{to_label}</b>:\n\n<i>/cancel to abort</i>",
        "amount_too_small": "⚠️ Amount too small.\n\nMinimum for <b>{from_label}</b>: <b>{min} {ticker}</b>\n\n<i>/cancel to abort</i>",
        "quote_failed": "❌ <b>Could not get a quote.</b>",
        "confirm": "📋 <b>Confirm swap:</b>\n\nYou send: <b>{amount} {from_label}</b>\nYou receive: <b>≈{amount_to} {to_label}</b>\nAddress: <code>{address}</code>\n\nIs everything correct?",
        "creating": "⏳ Creating exchange...",
        "created": "✅ <b>Exchange created!</b>\n\nID: <code>{id}</code>\nSend <b>{amount} {from_label}</b> to address:\n<code>{address_from}</code>",
        "create_failed": "❌ Failed to create exchange.",
        "cancelled": "❌ Cancelled.",
        "no_active": "No active action.",
        "invalid_amount": "⚠️ Enter a valid amount",
        "address_short": "⚠️ Address too short for <b>{label}</b>.",
        "choose_language": "🌐 Choose language:",
        "language_set": "✅ Language set to English",
        "fiat_choose": "💳 <b>Buy crypto with card</b>\n\nChoose payment currency:",
        "fiat_enter_amount": "Enter amount:",
        "fiat_created": "✅ <b>Order created!</b>\n\nPay here:\n{url}",
        "fiat_created_no_url": "✅ <b>Order created!</b>",
    },

    "de": {
        "welcome": (
            "👋 Hallo! Ich bin ein Krypto-Tauschbot, unterstützt von FixedFloat.\n\n"
            "⚡ Schnell, ohne Registrierung, ohne KYC.\n\n"
            "Wähle eine Aktion:"
        ),
        "how_it_works": (
            "📖 <b>So funktioniert es:</b>\n\n"
            "1. Wähle Währungen und Betrag\n"
            "2. Erhalte den Wechselkurs\n"
            "3. Bestätige — ich erstelle den Tausch\n"
            "4. Sende Krypto an die Adresse\n"
            "5. Erhalte deine Münzen 🎉\n\n"
            "<i>Powered by FixedFloat</i>"
        ),
        "btn_swap": "🔄 Tauschen",
        "btn_buy_card": "💳 Mit Karte kaufen",
        "btn_how": "ℹ️ Wie funktioniert es?",
        "btn_back": "🔙 Zurück",
        "btn_cancel": "❌ Abbrechen",
        "btn_confirm": "✅ Bestätigen",
        "btn_language": "🌐 Sprache",
        "choose_from": "🔄 <b>Neuer Tausch</b>\n\nWähle die Währung, die du <b>senden</b> möchtest:",
        "choose_to": "✅ Du sendest: <b>{from_label}</b>\n\nWähle nun die Währung, die du <b>erhalten</b> möchtest:",
        "enter_amount": "✅ Du erhältst: <b>{to_label}</b>\n\nGib den Betrag in <b>{from_label}</b> ein:\n<i>Minimum: {min} {ticker}</i>\n\n<i>/cancel zum Abbrechen</i>",
        "fetching_quote": "⏳ Kurs wird geladen...",
        "quote": "💱 <b>Angebot:</b>\n\nDu sendest: <b>{amount} {from_label}</b>\nDu erhältst: <b>≈{amount_to} {to_label}</b>\n\nGib deine Zieladresse für <b>{to_label}</b> ein:\n\n<i>/cancel zum Abbrechen</i>",
        "amount_too_small": "⚠️ Betrag zu klein.\n\nMinimum für <b>{from_label}</b>: <b>{min} {ticker}</b>\n\n<i>/cancel zum Abbrechen</i>",
        "quote_failed": "❌ <b>Kurs konnte nicht geladen werden.</b>",
        "confirm": "📋 <b>Tausch bestätigen:</b>\n\nDu sendest: <b>{amount} {from_label}</b>\nDu erhältst: <b>≈{amount_to} {to_label}</b>\nAdresse: <code>{address}</code>\n\nIst alles korrekt?",
        "creating": "⏳ Erstelle Tausch...",
        "created": "✅ <b>Tausch erstellt!</b>\n\nID: <code>{id}</code>\nSende <b>{amount} {from_label}</b> an die Adresse:\n<code>{address_from}</code>",
        "create_failed": "❌ Fehler beim Erstellen des Tauschs.",
        "cancelled": "❌ Abgebrochen.",
        "no_active": "Keine aktive Aktion.",
        "invalid_amount": "⚠️ Ungültiger Betrag",
        "address_short": "⚠️ Adresse zu kurz für <b>{label}</b>.",
        "choose_language": "🌐 Sprache wählen:",
        "language_set": "✅ Sprache auf Deutsch eingestellt",
        "fiat_choose": "💳 <b>Krypto mit Karte kaufen</b>\n\nZahlungswährung wählen:",
        "fiat_enter_amount": "Betrag eingeben:",
        "fiat_created": "✅ <b>Bestellung erstellt!</b>\n\nHier bezahlen:\n{url}",
        "fiat_created_no_url": "✅ <b>Bestellung erstellt!</b>",
    },

    "fr": {
        "welcome": (
            "👋 Bonjour! Je suis un bot d'échange crypto via FixedFloat.\n\n"
            "⚡ Rapide, sans inscription, sans KYC.\n\n"
            "Choisissez une action :"
        ),
        "how_it_works": (
            "📖 <b>Comment ça marche :</b>\n\n"
            "1. Choisissez les devises et le montant\n"
            "2. Obtenez le taux de change\n"
            "3. Confirmez — je crée l'échange\n"
            "4. Envoyez la crypto à l'adresse indiquée\n"
            "5. Recevez vos pièces 🎉\n\n"
            "<i>Propulsé par FixedFloat</i>"
        ),
        "btn_swap": "🔄 Échanger",
        "btn_buy_card": "💳 Acheter par carte",
        "btn_how": "ℹ️ Comment ça marche ?",
        "btn_back": "🔙 Retour",
        "btn_cancel": "❌ Annuler",
        "btn_confirm": "✅ Confirmer",
        "btn_language": "🌐 Langue",
        "choose_from": "🔄 <b>Nouvel échange</b>\n\nChoisissez la devise que vous voulez <b>envoyer</b> :",
        "choose_to": "✅ Vous envoyez : <b>{from_label}</b>\n\nChoisissez la devise que vous voulez <b>recevoir</b> :",
        "enter_amount": "✅ Vous recevez : <b>{to_label}</b>\n\nEntrez le montant en <b>{from_label}</b> :\n<i>Minimum : {min} {ticker}</i>\n\n<i>/cancel pour annuler</i>",
        "fetching_quote": "⏳ Récupération du taux...",
        "quote": "💱 <b>Devis :</b>\n\nVous envoyez : <b>{amount} {from_label}</b>\nVous recevez : <b>≈{amount_to} {to_label}</b>\n\nEntrez l'adresse du portefeuille pour <b>{to_label}</b> :\n\n<i>/cancel pour annuler</i>",
        "amount_too_small": "⚠️ Montant trop faible.\n\nMinimum pour <b>{from_label}</b> : <b>{min} {ticker}</b>\n\n<i>/cancel pour annuler</i>",
        "quote_failed": "❌ <b>Impossible d'obtenir un devis.</b>",
        "confirm": "📋 <b>Confirmer l'échange :</b>\n\nVous envoyez : <b>{amount} {from_label}</b>\nVous recevez : <b>≈{amount_to} {to_label}</b>\nAdresse : <code>{address}</code>\n\nTout est correct ?",
        "creating": "⏳ Création de l'échange...",
        "created": "✅ <b>Échange créé !</b>\n\nID : <code>{id}</code>\nEnvoyez <b>{amount} {from_label}</b> à l'adresse :\n<code>{address_from}</code>",
        "create_failed": "❌ Échec de la création de l'échange.",
        "cancelled": "❌ Annulé.",
        "no_active": "Aucune action active.",
        "invalid_amount": "⚠️ Entrez un montant valide",
        "address_short": "⚠️ Adresse trop courte pour <b>{label}</b>.",
        "choose_language": "🌐 Choisissez la langue :",
        "language_set": "✅ Langue réglée sur Français",
        "fiat_choose": "💳 <b>Acheter crypto par carte</b>\n\nChoisissez la devise de paiement :",
        "fiat_enter_amount": "Entrez le montant :",
        "fiat_created": "✅ <b>Commande créée !</b>\n\nPayez ici :\n{url}",
        "fiat_created_no_url": "✅ <b>Commande créée !</b>",
    },

    "fa": {
        "welcome": (
            "👋 سلام! من ربات تبدیل ارز دیجیتال با FixedFloat هستم.\n\n"
            "⚡ سریع، بدون ثبت‌نام، بدون KYC.\n\n"
            "یک گزینه انتخاب کنید:"
        ),
        "how_it_works": (
            "📖 <b>نحوه کار:</b>\n\n"
            "1. ارز و مقدار را انتخاب کنید\n"
            "2. نرخ تبدیل را دریافت کنید\n"
            "3. تأیید کنید تا سفارش ایجاد شود\n"
            "4. ارز را به آدرس داده شده ارسال کنید\n"
            "5. کوین‌های خود را دریافت کنید 🎉\n\n"
            "<i>Powered by FixedFloat</i>"
        ),
        "btn_swap": "🔄 تبدیل",
        "btn_buy_card": "💳 خرید با کارت",
        "btn_how": "ℹ️ چگونه کار می‌کند؟",
        "btn_back": "🔙 بازگشت",
        "btn_cancel": "❌ لغو",
        "btn_confirm": "✅ تأیید",
        "btn_language": "🌐 زبان",
        "choose_from": "🔄 <b>تبادل جدید</b>\n\nارزی که قصد <b>ارسال</b> آن را دارید انتخاب کنید:",
        "choose_to": "✅ ارسال می‌کنید: <b>{from_label}</b>\n\nحالا ارزی که قصد <b>دریافت</b> آن را دارید انتخاب کنید:",
        "enter_amount": "✅ دریافت می‌کنید: <b>{to_label}</b>\n\nمقدار را به <b>{from_label}</b> وارد کنید:\n<i>حداقل: {min} {ticker}</i>\n\n<i>/cancel برای لغو</i>",
        "fetching_quote": "⏳ در حال دریافت نرخ...",
        "quote": "💱 <b>نرخ تبدیل:</b>\n\nارسال: <b>{amount} {from_label}</b>\nدریافت: <b>≈{amount_to} {to_label}</b>\n\nآدرس کیف پول برای دریافت <b>{to_label}</b> را وارد کنید:\n\n<i>/cancel برای لغو</i>",
        "amount_too_small": "⚠️ مقدار خیلی کم است.\n\nحداقل برای <b>{from_label}</b>: <b>{min} {ticker}</b>\n\n<i>/cancel برای لغو</i>",
        "quote_failed": "❌ <b>دریافت نرخ ممکن نشد.</b>",
        "confirm": "📋 <b>تأیید تبدیل:</b>\n\nارسال: <b>{amount} {from_label}</b>\nدریافت: <b>≈{amount_to} {to_label}</b>\nآدرس: <code>{address}</code>\n\nآیا همه موارد صحیح است؟",
        "creating": "⏳ در حال ایجاد سفارش...",
        "created": "✅ <b>سفارش ایجاد شد!</b>\n\nشناسه: <code>{id}</code>\nمقدار <b>{amount} {from_label}</b> را به این آدرس ارسال کنید:\n<code>{address_from}</code>",
        "create_failed": "❌ خطا در ایجاد سفارش.",
        "cancelled": "❌ لغو شد.",
        "no_active": "عملیاتی فعال نیست.",
        "invalid_amount": "⚠️ مقدار نامعتبر است",
        "address_short": "⚠️ آدرس برای <b>{label}</b> خیلی کوتاه است.",
        "choose_language": "🌐 زبان را انتخاب کنید:",
        "language_set": "✅ زبان فارسی فعال شد",
        "fiat_choose": "💳 <b>خرید کریپتو با کارت</b>\n\nارز پرداخت را انتخاب کنید:",
        "fiat_enter_amount": "مبلغ را وارد کنید:",
        "fiat_created": "✅ <b>سفارش ایجاد شد!</b>\n\nاز اینجا پرداخت کنید:\n{url}",
        "fiat_created_no_url": "✅ <b>سفارش ایجاد شد!</b>",
    },

    "ar": {
        "welcome": (
            "👋 أهلاً! أنا بوت تبادل العملات الرقمية عبر FixedFloat.\n\n"
            "⚡ سريع، بدون تسجيل، بدون KYC.\n\n"
            "اختر إجراءً:"
        ),
        "how_it_works": (
            "📖 <b>كيف يعمل:</b>\n\n"
            "1. اختر العملات والمبلغ\n"
            "2. احصل على سعر الصرف\n"
            "3. أكّد العملية — سأقوم بإنشاء الطلب\n"
            "4. أرسل العملات إلى العنوان المزود\n"
            "5. استلم عملاتك 🎉\n\n"
            "<i>مدعوم بواسطة FixedFloat</i>"
        ),
        "btn_swap": "🔄 تبديل",
        "btn_buy_card": "💳 شراء بالبطاقة",
        "btn_how": "ℹ️ كيف يعمل؟",
        "btn_back": "🔙 رجوع",
        "btn_cancel": "❌ إلغاء",
        "btn_confirm": "✅ تأكيد",
        "btn_language": "🌐 اللغة",
        "choose_from": "🔄 <b>تبديل جديد</b>\n\nاختر العملة التي تريد <b>إرسالها</b>:",
        "choose_to": "✅ ستُرسل: <b>{from_label}</b>\n\nالآن اختر العملة التي تريد <b>استلامها</b>:",
        "enter_amount": "✅ ستستلم: <b>{to_label}</b>\n\nأدخل المبلغ بـ <b>{from_label}</b>:\n<i>الحد الأدنى: {min} {ticker}</i>\n\n<i>/cancel للإلغاء</i>",
        "fetching_quote": "⏳ جاري جلب السعر...",
        "quote": "💱 <b>السعر المقدر:</b>\n\nستُرسل: <b>{amount} {from_label}</b>\nستستلم: <b>≈{amount_to} {to_label}</b>\n\nأدخل عنوان محفظتك لاستلام <b>{to_label}</b>:\n\n<i>/cancel للإلغاء</i>",
        "amount_too_small": "⚠️ المبلغ صغير جداً.\n\nالحد الأدنى لـ <b>{from_label}</b> هو: <b>{min} {ticker}</b>\n\n<i>/cancel للإلغاء</i>",
        "quote_failed": "❌ <b>تعذر الحصول على السعر.</b>",
        "confirm": "📋 <b>تأكيد التبديل:</b>\n\nستُرسل: <b>{amount} {from_label}</b>\nستستلم: <b>≈{amount_to} {to_label}</b>\nالعنوان: <code>{address}</code>\n\nهل كل شيء صحيح؟",
        "creating": "⏳ جاري إنشاء الطلب...",
        "created": "✅ <b>تم إنشاء الطلب!</b>\n\nالمعرف: <code>{id}</code>\nأرسل <b>{amount} {from_label}</b> إلى العنوان:\n<code>{address_from}</code>",
        "create_failed": "❌ فشل في إنشاء التبديل.",
        "cancelled": "❌ تم الإلغاء.",
        "no_active": "لا يوجد إجراء نشط.",
        "invalid_amount": "⚠️ أدخل مبلغاً صالحاً",
        "address_short": "⚠️ العنوان قصير جداً لـ <b>{label}</b>.",
        "choose_language": "🌐 اختر اللغة:",
        "language_set": "✅ تم ضبط اللغة إلى العربية",
        "fiat_choose": "💳 <b>شراء كريبتو بالبطاقة</b>\n\nاختر عملة الدفع:",
        "fiat_enter_amount": "أدخل المبلغ:",
        "fiat_created": "✅ <b>تم إنشاء الطلب!</b>\n\nادفع هنا:\n{url}",
        "fiat_created_no_url": "✅ <b>تم إنشاء الطلب!</b>",
    }
}

DEFAULT_LANG = "en"


def t(lang: str, key: str, **kwargs) -> str:
    text = TEXTS.get(lang, TEXTS[DEFAULT_LANG]).get(key)
    if text is None:
        text = TEXTS[DEFAULT_LANG].get(key, key)
    if kwargs:
        text = text.format(**kwargs)
    return text