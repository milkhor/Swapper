"""
FixedFloat (ff.io) API v2 client.

Exposes the same coroutine interface the bot already uses for the crypto swap
flow (get_estimated / create_exchange / get_exchange / get_exchange_ranges),
so the handlers only need minimal changes.

Auth: every request is a POST signed with HMAC-SHA256 of the *exact* request
body, sent as headers X-API-KEY and X-API-SIGN.

NOTE ON CURRENCY CODES: FixedFloat identifies a coin+network with a single code
(e.g. USDT on Tron is "USDTTRC20"). The bot stores ticker+network separately,
so FF_CCY below maps our (ticker, network) pairs to FF codes. These must match
what FixedFloat actually returns from /ccies — run `python -m scripts.ff_ccies`
(or services.fixedfloat.list_currencies) with real keys to verify/adjust them.
"""
import hashlib
import hmac
import json
import logging
import time

import httpx

from config import FIXEDFLOAT_API_KEY, FIXEDFLOAT_API_SECRET

logger = logging.getLogger(__name__)

BASE_URL = "https://ff.io/api/v2"

# (ticker, network) as stored in the `currencies` table  ->  FixedFloat code.
FF_CCY = {
    ("btc",  "btc"):   "BTC",
    ("eth",  "eth"):   "ETH",
    ("usdt", "trx"):   "USDTTRC",
    ("usdt", "eth"):   "USDTETH",
    ("sol",  "sol"):   "SOL",
    ("bnb",  "bsc"):   "BNBBSC",
    ("trx",  "trx"):   "TRX",
    ("xmr",  "xmr"):   "XMR",
    ("usdc", "matic"): "USDCMATIC",
    ("usdt", "matic"): "USDTMATIC",
}

# FixedFloat order status -> internal bot status used across the app.
_STATUS_MAP = {
    "NEW":       "waiting",
    "PENDING":   "confirming",
    "EXCHANGE":  "exchanging",
    "WITHDRAW":  "sending",
    "DONE":      "finished",
    "EXPIRED":   "expired",
    "EMERGENCY": "failed",
}


def _ff_code(ticker: str, network: str) -> str:
    key = (ticker.lower(), (network or "").lower())
    if key in FF_CCY:
        return FF_CCY[key]
    # Fallback: bare uppercase ticker (works for most base coins).
    logger.warning(f"[FF] No FF_CCY mapping for {key}; falling back to '{ticker.upper()}'")
    return ticker.upper()


def _map_status(ff_status: str | None) -> str:
    if not ff_status:
        return "waiting"
    return _STATUS_MAP.get(ff_status.upper(), ff_status.lower())


def _sign(body: str) -> str:
    return hmac.new(
        FIXEDFLOAT_API_SECRET.encode(),
        body.encode(),
        hashlib.sha256,
    ).hexdigest()


async def _post(path: str, payload: dict, retries: int = 3) -> tuple[dict | None, str | None]:
    """
    POST to FixedFloat. Returns (data, error):
      success -> (data, None)
      failure -> (None, reason from the provider or transport)

    The reason is returned rather than stored globally so concurrent requests
    from different users can never see each other's error.
    """
    body = json.dumps(payload)
    headers = {
        "X-API-KEY": FIXEDFLOAT_API_KEY,
        "X-API-SIGN": _sign(body),
        "Content-Type": "application/json; charset=UTF-8",
    }
    url = f"{BASE_URL}{path}"
    for attempt in range(retries):
        try:
            start = time.monotonic()
            async with httpx.AsyncClient() as client:
                # Send the exact signed bytes (content=), not json=.
                resp = await client.post(url, content=body, headers=headers, timeout=15)
            elapsed = round((time.monotonic() - start) * 1000)
            data = resp.json()
            code = data.get("code")
            if code != 0:
                msg = data.get("msg") or f"error code {code}"
                logger.error(f"[FF] {path} → code={code} msg={msg} ({elapsed}ms) payload={payload}")
                return None, str(msg)
            logger.info(f"[FF] POST {path} → OK ({elapsed}ms)")
            return data.get("data"), None
        except httpx.TimeoutException:
            logger.warning(f"[FF] Timeout attempt {attempt + 1} — {path}")
            if attempt == retries - 1:
                logger.error(f"[FF] All {retries} attempts timed out: {path}")
                return None, "the exchange provider did not respond"
        except Exception as e:
            logger.error(f"[FF] Request error {path}: {e}")
            return None, "could not reach the exchange provider"
    return None, "could not reach the exchange provider"


# ── Currencies (for verifying FF codes) ─────────────────────────────────────────

async def list_currencies() -> list:
    data, _ = await _post("/ccies", {})
    if isinstance(data, dict):
        return data.get("ccies") or data.get("data") or []
    if isinstance(data, list):
        return data
    return []


# ── Estimate / price ────────────────────────────────────────────────────────────

async def get_estimated(
    ticker_from: str,
    network_from: str,
    ticker_to: str,
    network_to: str,
    amount: str,
    fixed: bool = False,
    reverse: bool = False,
) -> dict | None:
    """
    reverse=False: `amount` is what the user sends  → returns estimatedAmountTo.
    reverse=True:  `amount` is what the user wants to receive → also returns
                   estimatedAmountFrom (how much they must send).

    On failure returns {"error": "<reason from the provider>"} so the caller can
    tell the user *why* (e.g. amount below the minimum) instead of a generic
    "could not get a quote".
    """
    payload = {
        "type": "fixed" if (fixed or reverse) else "float",
        "fromCcy": _ff_code(ticker_from, network_from),
        "toCcy": _ff_code(ticker_to, network_to),
        "direction": "to" if reverse else "from",
        "amount": float(amount),
    }
    data, error = await _post("/price", payload)
    if not data:
        return {"error": error} if error else None
    try:
        d_from = data.get("from", {})
        d_to = data.get("to", {})
        amount_from = d_from.get("amount")
        amount_to = d_to.get("amount")
        if reverse:
            if amount_from is None:
                return None
            return {
                "estimatedAmountTo": float(amount),
                "estimatedAmountFrom": float(amount_from),
                "rateId": None,  # FF locks the rate at /create, no separate rateId
            }
        if amount_to is None:
            return None
        return {
            "estimatedAmountTo": float(amount_to),
            "rateId": None,
        }
    except (TypeError, ValueError) as e:
        logger.error(f"[FF] get_estimated parse error: {e} | data={data}")
        return None


# ── Create order ─────────────────────────────────────────────────────────────────

async def create_exchange(
    ticker_from: str,
    network_from: str,
    ticker_to: str,
    network_to: str,
    amount: str,
    address_to: str,
    fixed: bool = False,
    rate_id: str | None = None,  # unused for FF; kept for interface compatibility
) -> dict | None:
    payload = {
        "type": "fixed" if fixed else "float",
        "fromCcy": _ff_code(ticker_from, network_from),
        "toCcy": _ff_code(ticker_to, network_to),
        "direction": "from",
        "amount": float(amount),
        "toAddress": address_to.strip(),
    }
    data, _ = await _post("/create", payload)
    if not data:
        return None
    d_from = data.get("from", {})
    d_to = data.get("to", {})
    return {
        "id": data.get("id"),
        "token": data.get("token"),           # REQUIRED to query the order later
        "status": _map_status(data.get("status")),
        "addressFrom": d_from.get("address"),
        "amountFrom": d_from.get("amount"),
        "amountTo": d_to.get("amount"),
        "addressTo": d_to.get("address"),
    }


# ── Order status ─────────────────────────────────────────────────────────────────

async def get_exchange(order_id: str, token: str | None = None) -> dict | None:
    """
    Fetch order status. FixedFloat REQUIRES the per-order token returned by
    /create, so `token` must be supplied (stored in swaps.order_token).
    """
    if not token:
        logger.warning(f"[FF] get_exchange called without token for order {order_id}")
        return None
    data, _ = await _post("/order", {"id": order_id, "token": token})
    if not data:
        return None
    d_from = data.get("from", {})
    d_to = data.get("to", {})
    return {
        "status": _map_status(data.get("status")),
        "addressFrom": d_from.get("address"),
        "amountFrom": d_from.get("amount"),
        "tickerFrom": d_from.get("code"),
        "amountTo": d_to.get("amount"),
        "tickerTo": d_to.get("code"),
        "addressTo": d_to.get("address"),
        "raw": data,
    }


# ── Ranges (min / max) ───────────────────────────────────────────────────────────

async def get_exchange_ranges(
    ticker_from: str,
    network_from: str,
    ticker_to: str,
    network_to: str,
    fixed: bool = False,
    reverse: bool = False,
) -> dict | None:
    """
    FixedFloat has no standalone min/max endpoint (limits require a concrete
    positive amount via /price), so we return None and let the caller fall back
    to the local per-currency minimums. The real FixedFloat limits are still
    enforced at quote/create time: an out-of-range amount makes get_estimated /
    create_exchange return None, and the user sees a "try another amount" error.
    """
    return None


# ── Address validation ───────────────────────────────────────────────────────────

async def get_address_validation_pattern(ticker: str, network: str) -> str | None:
    """FixedFloat has no address-pattern endpoint; rely on local regex patterns."""
    return None
