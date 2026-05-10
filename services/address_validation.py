import re

from services import simpleswap


EVM_NETWORKS = {
    "eth", "bsc", "matic", "polygon", "base", "arb", "arbitrum",
    "op", "optimism", "avax", "cchain", "ftm", "fantom", "cro",
    "cronos", "xdai", "gnosis", "linea", "zksync", "blast",
}

NETWORK_PATTERNS = {
    "btc": r"(bc1[0-9a-z]{25,80}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})",
    "trx": r"T[1-9A-HJ-NP-Za-km-z]{33}",
    "sol": r"[1-9A-HJ-NP-Za-km-z]{32,44}",
    "xmr": r"[48][0-9AB][1-9A-HJ-NP-Za-km-z]{93}([1-9A-HJ-NP-Za-km-z]{11})?",
}

NETWORK_NAMES = {
    "eth": "ERC20",
    "trx": "TRC20",
    "bsc": "BEP20",
    "matic": "Polygon",
    "btc": "Bitcoin",
    "sol": "Solana",
    "xmr": "Monero",
}


def _clean_api_pattern(pattern: str) -> str:
    pattern = pattern.strip()
    if len(pattern) > 2 and pattern.startswith("/"):
        last_slash = pattern.rfind("/")
        if last_slash > 0:
            pattern = pattern[1:last_slash]
    return pattern


def _fallback_pattern(network: str) -> str | None:
    network = network.lower()
    if network in EVM_NETWORKS:
        return r"0x[0-9A-Fa-f]{40}"
    return NETWORK_PATTERNS.get(network)


def _network_name(network: str) -> str:
    network = (network or "").lower()
    return NETWORK_NAMES.get(network, network.upper() if network else "selected")


def _invalid_message(label: str, network: str) -> str:
    network_name = _network_name(network)
    return (
        f"⚠️ Invalid wallet address for <b>{label}</b>.\n\n"
        f"This order uses the <b>{network_name}</b> network. "
        f"Enter only an address from this network. Wrong-network addresses "
        f"are not accepted."
    )


async def validate_wallet_address(
    address: str,
    ticker: str,
    network: str,
    label: str | None = None,
) -> tuple[bool, str | None]:
    address = address.strip()
    label = label or f"{ticker.upper()} ({_network_name(network)})"
    if not address:
        return False, _invalid_message(label, network)

    fallback = _fallback_pattern(network)
    if fallback:
        try:
            if re.fullmatch(fallback, address):
                return True, None
        except re.error:
            pass
        return False, _invalid_message(label, network)

    api_pattern = await simpleswap.get_address_validation_pattern(ticker, network)
    if api_pattern:
        try:
            if re.fullmatch(_clean_api_pattern(api_pattern), address):
                return True, None
        except re.error:
            pass
        return False, _invalid_message(label, network)

    return (
        False,
        f"⚠️ Could not validate the address format for <b>{label}</b>. "
        f"Please try again later or choose a supported network.",
    )
