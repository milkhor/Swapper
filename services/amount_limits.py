from services import fixedfloat
from services.currencies import get_min_amount


async def get_pair_limits(
    ticker_from: str,
    network_from: str,
    ticker_to: str,
    network_to: str,
    reverse: bool = False,
) -> dict:
    ranges = await fixedfloat.get_exchange_ranges(
        ticker_from=ticker_from,
        network_from=network_from,
        ticker_to=ticker_to,
        network_to=network_to,
        reverse=reverse,
    )
    if ranges and ranges.get("min") is not None:
        min_amount = ranges["min"]
        source = "api"
    else:
        try:
            local_min = await get_min_amount(ticker_from, network_from)
        except Exception:
            local_min = 0.0
        min_amount = local_min
        source = "local"

    return {
        "min": min_amount,
        "max": ranges.get("max") if ranges else None,
        "source": source,
    }


def format_limit_amount(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.12f}".rstrip("0").rstrip(".")
