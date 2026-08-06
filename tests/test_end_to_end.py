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


# ── Admin-added currencies ──────────────────────────────────────────────────

async def test_admin_added_crypto_currency_works_without_code_changes(fake_ff, fresh_db):
    """
    A currency added from the admin panel must be usable immediately: the code
    comes from the provider's list, so no redeploy is needed for anything
    FixedFloat already supports.
    """
    # XMR is NOT in the static FF_CCY-only path we rely on for unknown pairs.
    cur_id = await fresh_db.add_currency(
        ticker="xmr", network="xmr", label="XMR", min_amount=0.1, is_fiat=False
    )
    assert cur_id

    listed = await fresh_db.get_currencies(crypto_only=True, active_only=True)
    assert any(c["ticker"] == "xmr" and c["network"] == "xmr" for c in listed)

    # Resolves through the live provider list and quotes successfully.
    assert await ff.resolve_code("xmr", "xmr") == "XMR"
    quote = await ff.get_estimated("btc", "btc", "xmr", "xmr", "0.01")
    assert quote and "error" not in quote


async def test_admin_added_currency_unknown_to_provider_is_reported(fake_ff, fresh_db):
    """An unsupported currency must fail loudly at quote time, not silently."""
    await fresh_db.add_currency(
        ticker="fake", network="fake", label="FAKE", min_amount=1.0, is_fiat=False
    )
    quote = await ff.get_estimated("btc", "btc", "fake", "fake", "0.01")
    assert quote == {"error": "toCcy is incorrect"}


async def test_admin_toggle_and_min_edit_apply(fresh_db):
    """Disabling a currency hides it; editing its minimum takes effect."""
    cur_id = await fresh_db.add_currency("ltc", "ltc", "LTC", 0.05, False)

    await fresh_db.update_currency_min(cur_id, 0.25)
    rows = await fresh_db.get_all_currencies_admin()
    assert next(c["min_amount"] for c in rows if c["id"] == cur_id) == 0.25

    await fresh_db.toggle_currency(cur_id)  # disable
    active = await fresh_db.get_currencies(crypto_only=True, active_only=True)
    assert all(c["id"] != cur_id for c in active)


# ── Provider split: crypto -> FixedFloat, fiat -> SimpleSwap ────────────────

async def test_orders_are_routed_back_to_their_own_provider(fresh_db, monkeypatch):
    from services import providers

    calls = []

    async def fake_ff_get(order_id, token):
        calls.append(("fixedfloat", order_id, token))
        return {"status": "finished"}

    async def fake_ss_get(public_id):
        calls.append(("simpleswap", public_id))
        return {"status": "finished"}

    monkeypatch.setattr(providers.fixedfloat, "get_exchange", fake_ff_get)
    monkeypatch.setattr(providers.simpleswap, "get_exchange", fake_ss_get)

    crypto = {"exchange_id": "FF1", "order_token": "tok", "provider": "fixedfloat"}
    fiat = {"exchange_id": "SS1", "order_token": None, "provider": "simpleswap"}

    assert (await providers.fetch_order_status(crypto))["status"] == "finished"
    assert (await providers.fetch_order_status(fiat))["status"] == "finished"
    assert calls == [("fixedfloat", "FF1", "tok"), ("simpleswap", "SS1")]


async def test_legacy_orders_are_not_sent_to_any_provider(monkeypatch):
    """Pre-migration rows have neither provider nor token — never poll them."""
    from services import providers

    async def boom(*a, **k):
        raise AssertionError("legacy order must not reach a provider")

    monkeypatch.setattr(providers.fixedfloat, "get_exchange", boom)
    monkeypatch.setattr(providers.simpleswap, "get_exchange", boom)

    legacy = {"exchange_id": "OLD1", "order_token": None, "provider": None}
    assert await providers.fetch_order_status(legacy) is None


async def test_provider_is_persisted_per_order(fresh_db):
    await fresh_db.save_swap(
        user_id=1, exchange_id="FF9", order_token="t", provider="fixedfloat",
        currency_from="btc_btc", currency_to="usdt_trx",
        amount_from=1.0, amount_to=2.0, address_to="x",
    )
    await fresh_db.save_swap(
        user_id=1, exchange_id="SS9", provider="simpleswap",
        currency_from="usd_usd", currency_to="btc_btc",
        amount_from=100.0, amount_to=0.001, address_to="y",
    )
    assert (await fresh_db.get_swap_by_exchange_id("FF9"))["provider"] == "fixedfloat"
    assert (await fresh_db.get_swap_by_exchange_id("SS9"))["provider"] == "simpleswap"


# ── Affiliate commission (afftax) ───────────────────────────────────────────

def _set_commission(monkeypatch, afftax, refcode="MYCODE"):
    monkeypatch.setattr(ff, "FIXEDFLOAT_AFFTAX", afftax)
    monkeypatch.setattr(ff, "FIXEDFLOAT_REFCODE", refcode)


async def test_no_commission_configured_by_default(fake_ff, monkeypatch):
    """Unset means we send nothing extra — FixedFloat's plain rate."""
    _set_commission(monkeypatch, "", "")
    await ff.get_estimated("btc", "btc", "usdt", "trx", "0.01")
    await ff.create_exchange("btc", "btc", "usdt", "trx", "0.01", "TWallet")
    for path, payload in fake_ff.requests:
        assert "afftax" not in payload and "refcode" not in payload


async def test_commission_applied_identically_to_quote_and_create(fake_ff, monkeypatch):
    """
    The quote and the created order must carry the same commission, otherwise
    the user is shown one rate and given a worse one.
    """
    _set_commission(monkeypatch, "0.5")
    await ff.get_estimated("btc", "btc", "usdt", "trx", "0.01")
    await ff.create_exchange("btc", "btc", "usdt", "trx", "0.01", "TWallet")

    price = next(p for path, p in fake_ff.requests if path == "/price")
    create = next(p for path, p in fake_ff.requests if path == "/create")
    assert price["afftax"] == 0.5 and price["refcode"] == "MYCODE"
    assert create["afftax"] == price["afftax"]
    assert create["refcode"] == price["refcode"]


async def test_commission_accepts_comma_decimal(monkeypatch):
    _set_commission(monkeypatch, "0,75")
    assert ff.affiliate_params()["afftax"] == 0.75


async def test_malformed_commission_is_ignored_not_fatal(fake_ff, monkeypatch):
    """A bad config value costs margin, it must never break exchanges."""
    _set_commission(monkeypatch, "half a percent")
    assert ff.affiliate_params() == {}
    quote = await ff.get_estimated("btc", "btc", "usdt", "trx", "0.01")
    assert quote and "error" not in quote


async def test_commission_requires_a_refcode(monkeypatch):
    """FixedFloat needs both — sending afftax alone would be rejected."""
    _set_commission(monkeypatch, "0.5", refcode="")
    assert ff.affiliate_params() == {}


async def test_zero_or_negative_commission_is_not_sent(monkeypatch):
    _set_commission(monkeypatch, "0")
    assert ff.affiliate_params() == {}
    _set_commission(monkeypatch, "-1")
    assert ff.affiliate_params() == {}
