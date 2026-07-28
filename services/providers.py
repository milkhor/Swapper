"""
Routing between exchange providers.

The bot uses two:
  * FixedFloat  — crypto → crypto swaps
  * SimpleSwap  — fiat → crypto ("buy with card"), which FixedFloat doesn't offer

Orders record which provider created them, so status lookups go back to the
right API. Everything that needs an order's status should call
`fetch_order_status()` rather than a provider module directly.
"""
import logging

from services import fixedfloat, simpleswap

logger = logging.getLogger(__name__)

FIXEDFLOAT = "fixedfloat"
SIMPLESWAP = "simpleswap"


def provider_of(swap: dict) -> str | None:
    """
    Which provider owns this order.

    Rows created before the provider column existed are inferred: a FixedFloat
    order always has a token, so a row without one is a pre-migration order that
    no longer resolves anywhere — those return None and are left alone.
    """
    provider = (swap.get("provider") or "").strip().lower()
    if provider:
        return provider
    return FIXEDFLOAT if swap.get("order_token") else None


async def fetch_order_status(swap: dict) -> dict | None:
    """Fetch live order state from whichever provider created the order."""
    exchange_id = swap.get("exchange_id")
    if not exchange_id:
        return None

    provider = provider_of(swap)
    if provider is None:
        return None  # legacy order, not trackable

    if provider == FIXEDFLOAT:
        token = swap.get("order_token")
        if not token:
            logger.warning(f"[providers] FixedFloat order {exchange_id} has no token")
            return None
        return await fixedfloat.get_exchange(exchange_id, token)

    if provider == SIMPLESWAP:
        return await simpleswap.get_exchange(exchange_id)

    logger.warning(f"[providers] Unknown provider '{provider}' for order {exchange_id}")
    return None
