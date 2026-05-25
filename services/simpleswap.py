import httpx
from config import SIMPLESWAP_API_KEY
import logging
import time


logger = logging.getLogger(__name__)

BASE_URL = "https://api.simpleswap.io"

NETWORKS = {
    "btc": "btc",
    "eth": "eth",
    "usdt": "eth",
    "sol": "sol",
    "bnb": "bsc",
    "trx": "trx",
}


async def _request_with_retry(method: str, url: str, retries: int = 3, **kwargs) -> dict | None:
    for attempt in range(retries):
        try:
            start = time.monotonic()
            async with httpx.AsyncClient() as client:
                resp = await client.request(method, url, timeout=10, **kwargs)
                elapsed = round((time.monotonic() - start) * 1000)
                resp.raise_for_status()
                data = resp.json()
                logger.info(f"[API] {method} {url} → {resp.status_code} ({elapsed}ms)")
                return data
        except httpx.TimeoutException:
            logger.warning(f"[API] Timeout attempt {attempt + 1} — {url}")
            if attempt == retries - 1:
                logger.error(f"[API] All {retries} attempts failed: {url}")
                return None
        except httpx.HTTPStatusError as e:
            logger.error(
                f"[API] HTTP {e.response.status_code} — {url} "
                f"| body: {e.response.text[:200]}"
            )
            return None
        except Exception as e:
            logger.error(f"[API] Request error: {e}")
            return None
    return None


def _get_network_for_ticker(ticker: str, pairs: list) -> str | None:
    key = ticker.lower()
    if key in NETWORKS:
        return NETWORKS[key]
    for p in pairs:
        if not isinstance(p, dict):
            continue
        if p.get("ticker", "").lower() == key:
            if p.get("network"):
                return p["network"]
            networks = p.get("networks")
            if isinstance(networks, list) and networks:
                return networks[0]
    return None


async def get_pairs(fixed: bool = False) -> list:
    data = await _request_with_retry(
        "GET",
        f"{BASE_URL}/v3/currencies",
        params={"api_key": SIMPLESWAP_API_KEY, "fixed": fixed},
    )
    if not data:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("result") or data.get("data") or []
    return []


async def get_estimated(
    ticker_from: str,
    network_from: str,
    ticker_to: str,
    network_to: str,
    amount: str,
    fixed: bool = False
) -> dict | None:
    try:
        t_from = ticker_from.lower()
        n_from = network_from.lower() if network_from else ""
        t_to = ticker_to.lower()
        n_to = network_to.lower() if network_to else ""

        params = {
            "tickerFrom": t_from,
            "networkFrom": n_from,
            "tickerTo": t_to,
            "networkTo": n_to,
            "amount": amount,
            "fixed": str(fixed).lower(),
        }

        logger.info(f"DEBUG SENDING PARAMS: {params}")

        data = await _request_with_retry(
            "GET",
            f"{BASE_URL}/v3/estimates",
            params=params,
            headers={"x-api-key": SIMPLESWAP_API_KEY},
        )

        if not data or "result" not in data:
            logger.error(f"!!! QUOTE ERROR FULL RESPONSE: {data}")
            return None

        result = data["result"]
        logger.info(f"!!! QUOTE SUCCESS FULL RESULT: {result}")

        estimated = result.get("estimatedAmount") or result.get("amountTo") or result.get("estimatedAmountTo")

        if estimated is None:
            return None

        return {
            "estimatedAmountTo": float(estimated),
            "rateId": result.get("rateId"),
        }

    except Exception as e:
        logger.error(f"get_estimated error: {e}")
        return None


async def get_estimated_reverse(
    ticker_from: str,
    network_from: str,
    ticker_to: str,
    network_to: str,
    amount: str,
) -> dict | None:
    try:
        t_from = ticker_from.lower()
        n_from = network_from.lower() if network_from else ""
        t_to = ticker_to.lower()
        n_to = network_to.lower() if network_to else ""

        params = {
            "tickerFrom": t_to,
            "networkFrom": n_to,
            "tickerTo": t_from,
            "networkTo": n_from,
            "amount": amount,
            "fixed": "true",
        }

        logger.info(f"DEBUG REVERSE PARAMS: {params}")

        data = await _request_with_retry(
            "GET",
            f"{BASE_URL}/v3/estimates",
            params=params,
            headers={"x-api-key": SIMPLESWAP_API_KEY},
        )

        if not data or "result" not in data:
            logger.error(f"!!! REVERSE QUOTE ERROR: {data}")
            return None

        result = data["result"]
        logger.info(f"!!! REVERSE QUOTE SUCCESS: {result}")

        estimated = result.get("estimatedAmount") or result.get("amountTo") or result.get("estimatedAmountTo")

        if estimated is None:
            return None

        return {
            "estimatedAmountFrom": float(estimated),
            "rateId": result.get("rateId"),
        }

    except Exception as e:
        logger.error(f"get_estimated_reverse error: {e}")
        return None


async def create_exchange(
    ticker_from: str,
    network_from: str,
    ticker_to: str,
    network_to: str,
    amount: str,
    address_to: str,
    fixed: bool = False,
    rate_id: str | None = None,
) -> dict | None:
    try:
        t_from = ticker_from.lower()
        n_from = network_from.lower() if network_from else ""
        t_to = ticker_to.lower()
        n_to = network_to.lower() if network_to else ""

        payload = {
            "tickerFrom": t_from,
            "networkFrom": n_from,
            "tickerTo": t_to,
            "networkTo": n_to,
            "amount": amount,
            "addressTo": address_to.strip(),
            "fixed": fixed,
        }
        if rate_id:
            payload["rateId"] = rate_id

        logger.info(f"DEBUG CREATE PAYLOAD: {payload}")

        data = await _request_with_retry(
            "POST",
            f"{BASE_URL}/v3/exchanges",
            json=payload,
            headers={"x-api-key": SIMPLESWAP_API_KEY},
        )

        if not data or (isinstance(data, dict) and "result" not in data):
            logger.error(f"!!! CREATE ERROR FULL RESPONSE: {data}")
            return None

        if isinstance(data, dict) and "result" in data:
            return data["result"]
            
        return data
        
    except Exception as e:
        logger.error(f"create_exchange error: {e}")
        return None


async def get_exchange(public_id: str) -> dict | None:
    data = await _request_with_retry(
        "GET",
        f"{BASE_URL}/v3/exchanges/{public_id}",
        headers={"x-api-key": SIMPLESWAP_API_KEY},
    )

    if not data:
        return None

    if isinstance(data, dict) and isinstance(data.get("result"), dict):
        return data["result"]

    return data
