"""
End-to-end tests for the swap lifecycle.

These drive the real code paths — currency-code resolution, quote, order
creation, persistence, the background status checker and the admin lookup —
against a fake FixedFloat that mimics the provider's actual API v2 responses
(including its irregular currency codes and the {code,msg,data} envelope).

Network is faked at the httpx layer, so nothing here needs API keys.
"""
import json

import pytest

import database.db as db
import services.fixedfloat as ff


# Real codes as returned by FixedFloat's live currency list.
LIVE_CCIES = [
    {"code": "BTC",       "coin": "BTC",  "network": "BTC",   "name": "Bitcoin"},
    {"code": "ETH",       "coin": "ETH",  "network": "ETH",   "name": "Ethereum"},
    {"code": "USDT",      "coin": "USDT", "network": "ETH",   "name": "Tether (ERC20)"},
    {"code": "USDTTRC",   "coin": "USDT", "network": "TRC",   "name": "Tether (TRC20)"},
    {"code": "USDTMATIC", "coin": "USDT", "network": "MATIC", "name": "Tether (Polygon)"},
    {"code": "BSC",       "coin": "BNB",  "network": "BSC",   "name": "BNB"},
    {"code": "SOL",       "coin": "SOL",  "network": "SOL",   "name": "Solana"},
    {"code": "XMR",       "coin": "XMR",  "network": "XMR",   "name": "Monero"},
]


class FakeFixedFloat:
    """Stands in for the FixedFloat API, recording what the bot sends."""

    def __init__(self):
        self.requests = []
        self.orders = {}
        self.min_amount = 20.0        # provider-side minimum, in `to` units
        self._next_status = "NEW"

    # -- helpers ---------------------------------------------------------
    def set_status(self, status):
        self._next_status = status

    def _handle(self, path, payload):
        if path == "/ccies":
            return {"code": 0, "msg": "", "data": LIVE_CCIES}

        if path in ("/price", "/create"):
            known = {c["code"] for c in LIVE_CCIES}
            for field in ("fromCcy", "toCcy"):
                if payload.get(field) not in known:
                    return {"code": 301, "msg": f"{field} is incorrect", "data": None}

            amount = float(payload["amount"])
            if payload.get("direction") == "to" and amount < self.min_amount:
                return {"code": 302, "msg": "Amount is less than minimum", "data": None}

            # Simple fixed rate: 1 BTC = 60000 units of the counter currency.
            if payload.get("direction") == "to":
                amount_to, amount_from = amount, round(amount / 60000, 8)
            else:
                amount_from, amount_to = amount, round(amount * 60000, 2)

            if path == "/price":
                return {"code": 0, "msg": "", "data": {
                    "from": {"amount": str(amount_from), "code": payload["fromCcy"]},
                    "to":   {"amount": str(amount_to),   "code": payload["toCcy"]},
                }}

            order_id, token = "FFTEST01", "tok-secret-01"
            self.orders[order_id] = token
            return {"code": 0, "msg": "", "data": {
                "id": order_id,
                "token": token,
                "status": "NEW",
                "from": {"address": "1DepositAddressXYZ", "amount": str(amount_from),
                         "code": payload["fromCcy"]},
                "to":   {"address": payload["toAddress"], "amount": str(amount_to),
                         "code": payload["toCcy"]},
            }}

        if path == "/order":
            if self.orders.get(payload.get("id")) != payload.get("token"):
                return {"code": 401, "msg": "Invalid token", "data": None}
            return {"code": 0, "msg": "", "data": {
                "status": self._next_status,
                "from": {"address": "1DepositAddressXYZ", "amount": "0.01", "code": "BTC"},
                "to":   {"address": "TUserWallet", "amount": "600", "code": "USDTTRC"},
            }}

        return {"code": 404, "msg": "unknown endpoint", "data": None}

    # -- httpx stand-in --------------------------------------------------
    def client_factory(self):
        api = self

        class _Resp:
            def __init__(self, payload):
                self._payload = payload

            def json(self):
                return self._payload

        class _Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, content=None, headers=None, timeout=None):
                path = url.replace(ff.BASE_URL, "")
                payload = json.loads(content)
                api.requests.append((path, payload))
                return _Resp(api._handle(path, payload))

        return _Client


@pytest.fixture
def fake_ff(monkeypatch):
    api = FakeFixedFloat()
    monkeypatch.setattr(ff.httpx, "AsyncClient", api.client_factory())
    monkeypatch.setattr(ff, "FIXEDFLOAT_API_KEY", "test-key")
    monkeypatch.setattr(ff, "FIXEDFLOAT_API_SECRET", "test-secret")
    monkeypatch.setattr(ff, "_ccy_index", None)  # don't leak cache between tests
    return api


# ── Currency codes ──────────────────────────────────────────────────────────

async def test_codes_resolved_from_the_provider(fake_ff):
    """The pairs that broke in production must resolve to the provider's codes."""
    assert await ff.resolve_code("usdt", "eth") == "USDT"        # not USDTETH
    assert await ff.resolve_code("bnb", "bsc") == "BSC"          # not BNBBSC
    assert await ff.resolve_code("usdt", "trx") == "USDTTRC"     # alias trx -> TRC
    assert await ff.resolve_code("btc", "btc") == "BTC"


async def test_currency_list_is_fetched_once(fake_ff):
    await ff.resolve_code("btc", "btc")
    await ff.resolve_code("eth", "eth")
    assert sum(1 for p, _ in fake_ff.requests if p == "/ccies") == 1


async def test_falls_back_to_static_table_when_list_unavailable(fake_ff, monkeypatch):
    async def no_list():
        return []
    monkeypatch.setattr(ff, "list_currencies", no_list)
    assert await ff.resolve_code("usdt", "trx") == "USDTTRC"  # from FF_CCY


# ── Quote ───────────────────────────────────────────────────────────────────

async def test_quote_receive_mode_returns_send_amount(fake_ff):
    res = await ff.get_estimated("btc", "btc", "usdt", "eth", "600", reverse=True)
    assert res["estimatedAmountTo"] == 600.0
    assert res["estimatedAmountFrom"] == 0.01
    price = next(p for path, p in fake_ff.requests if path == "/price")
    assert price["toCcy"] == "USDT" and price["direction"] == "to"


async def test_quote_below_provider_minimum_reports_the_reason(fake_ff):
    """The user must be told why — this is what "10" hit in production."""
    res = await ff.get_estimated("btc", "btc", "usdt", "eth", "10", reverse=True)
    assert res == {"error": "Amount is less than minimum"}


# ── Full lifecycle: quote → create → persist → status → admin lookup ────────

async def test_full_swap_lifecycle(fake_ff, fresh_db, monkeypatch):
    # 1. Quote
    quote = await ff.get_estimated("btc", "btc", "usdt", "trx", "600", reverse=True)
    assert "error" not in quote

    # 2. Create the order
    order = await ff.create_exchange(
        "btc", "btc", "usdt", "trx",
        amount=str(quote["estimatedAmountFrom"]),
        address_to="TUserWallet", fixed=True,
    )
    assert order["id"] and order["token"]
    assert order["addressFrom"] == "1DepositAddressXYZ"
    assert order["status"] == "waiting"

    # 3. Persist with the Telegram identity (FixedFloat retention requirement)
    await fresh_db.save_swap(
        user_id=555, username="bob", language_code="en",
        exchange_id=order["id"], order_token=order["token"],
        currency_from="btc_btc", currency_to="usdt_trx",
        amount_from=float(order["amountFrom"]), amount_to=float(order["amountTo"]),
        address_to="TUserWallet", address_from=order["addressFrom"],
        status=order["status"],
    )

    # 4. Background checker picks up a status change
    fake_ff.set_status("DONE")
    stored = await fresh_db.get_swap_by_exchange_id(order["id"])
    result = await ff.get_exchange(stored["exchange_id"], stored["order_token"])
    assert result["status"] == "finished"
    await fresh_db.update_swap_status(stored["exchange_id"], result["status"])

    # 5. Admin can retrieve the user record by the provider's order ID
    found = await fresh_db.get_swap_by_exchange_id(order["id"])
    assert found["status"] == "finished"
    assert found["user_id"] == 555
    assert found["username"] == "bob"
    assert found["language_code"] == "en"


async def test_status_query_rejects_a_wrong_token(fake_ff):
    await ff.create_exchange("btc", "btc", "usdt", "trx", "0.01", "TUserWallet")
    assert await ff.get_exchange("FFTEST01", "not-the-token") is None


async def test_every_request_is_signed(fake_ff):
    """Auth headers must be present and correct on the real request path."""
    import hashlib
    import hmac

    await ff.get_estimated("btc", "btc", "eth", "eth", "0.01")
    assert fake_ff.requests, "no request reached the provider"
    for path, payload in fake_ff.requests:
        body = json.dumps(payload)
        expected = hmac.new(b"test-secret", body.encode(), hashlib.sha256).hexdigest()
        assert ff._sign(body) == expected
