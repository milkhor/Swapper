from html import escape


TERMINAL_STATUSES = {"finished", "failed", "refunded", "expired"}

NETWORK_NAMES = {
    "eth": "ERC20",
    "trx": "TRC20",
    "bsc": "BEP20",
    "matic": "Polygon",
    "btc": "Bitcoin",
    "sol": "Solana",
    "xmr": "Monero",
}


def is_payment_active(status: str | None) -> bool:
    return (status or "").lower() not in TERMINAL_STATUSES


def extract_payment_details(result: dict | None) -> tuple[str | None, str | None]:
    if not result:
        return None, None
    address_from = (
        result.get("addressFrom")
        or result.get("address_from")
        or result.get("depositAddress")
        or result.get("deposit_address")
    )
    payment_url = (
        result.get("redirectUrl")
        or result.get("paymentUrl")
        or result.get("redirect_url")
        or result.get("payment_url")
    )
    return address_from, payment_url


def _split_currency(value: str | None) -> tuple[str, str | None]:
    if not value:
        return "?", None
    parts = value.rsplit("_", 1)
    if len(parts) == 2:
        return parts[0].upper(), parts[1].lower()
    return value.upper(), None


def _network_name(network: str | None) -> str:
    if not network:
        return "selected"
    return NETWORK_NAMES.get(network.lower(), network.upper())


def _currency_label(ticker: str, network: str | None) -> str:
    if not network or network.lower() == ticker.lower():
        return ticker
    return f"{ticker} ({_network_name(network)})"


def _amount(value) -> str:
    return escape(str(value if value is not None else "—"))


def format_payment_details(swap: dict) -> str:
    exchange_id = escape(str(swap.get("exchange_id") or "—"))
    status = escape(str(swap.get("status") or "unknown"))
    from_ticker, from_network = _split_currency(swap.get("currency_from"))
    to_ticker, to_network = _split_currency(swap.get("currency_to"))
    from_label = _currency_label(from_ticker, from_network)
    to_label = _currency_label(to_ticker, to_network)
    address_from = swap.get("address_from")
    payment_url = swap.get("payment_url")
    address_to = swap.get("address_to")

    lines = [
        "📋 <b>Order payment details</b>",
        "",
        f"ID: <code>{exchange_id}</code>",
        f"Status: <b>{status}</b>",
        f"You send: <b>{_amount(swap.get('amount_from'))} {escape(from_label)}</b>",
        f"You receive: <b>≈{_amount(swap.get('amount_to'))} {escape(to_label)}</b>",
    ]

    if payment_url:
        safe_url = escape(str(payment_url), quote=True)
        lines.extend([
            "",
            f"Payment link: <a href=\"{safe_url}\">open payment page</a>",
        ])
    elif address_from:
        lines.extend([
            "",
            f"Send only <b>{escape(from_label)}</b> to this address:",
            f"<code>{escape(str(address_from))}</code>",
        ])
    else:
        lines.extend([
            "",
            "Payment details are not available locally yet.",
        ])

    if address_to:
        lines.extend([
            "",
            "Destination wallet:",
            f"<code>{escape(str(address_to))}</code>",
        ])

    return "\n".join(lines)


def format_history_payment_line(swap: dict) -> str:
    if not is_payment_active(swap.get("status")):
        return ""

    if swap.get("payment_url"):
        return "💳 Payment: use the \"Continue payment\" button below\n"
    if swap.get("address_from"):
        return f"🏦 Deposit address:\n<code>{escape(str(swap['address_from']))}</code>\n"
    return "🔎 Payment details: use the button below\n"
