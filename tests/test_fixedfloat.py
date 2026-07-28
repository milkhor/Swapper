"""
Tests for the FixedFloat client. Network is mocked at the _post boundary so
these run offline and don't need real API keys.
"""
import hashlib
import hmac

import pytest

import services.fixedfloat as ff


@pytest.fixture
def mock_ff(monkeypatch):
    """Capture the last (path, payload) and return a canned FF `data` object."""
    calls = []

    async def fake_post(path, payload, retries=3):
        calls.append((path, payload))
        return fake_post.response, fake_post.error

    fake_post.response = None
    fake_post.error = None
    monkeypatch.setattr(ff, "_post", fake_post)
    # Seed the code cache (provider-style (coin, network) keys) so these tests
    # exercise a single endpoint instead of also fetching /ccies.
    monkeypatch.setattr(ff, "_ccy_index", {
        ("btc", "btc"): "BTC",
        ("eth", "eth"): "ETH",
        ("usdt", "trc"): "USDTTRC",
        ("usdt", "eth"): "USDT",
    })
    return fake_post, calls


# ── Pure helpers ────────────────────────────────────────────────────────────

def test_ff_code_mapping_and_fallback():
    assert ff._ff_code("usdt", "trx") == "USDTTRC"   # per FF docs, not USDTTRC20
    assert ff._ff_code("btc", "btc") == "BTC"
    # Unknown pair falls back to bare uppercase ticker.
    assert ff._ff_code("doge", "doge") == "DOGE"


def test_status_mapping_covers_all_ff_states():
    assert ff._map_status("NEW") == "waiting"
    assert ff._map_status("PENDING") == "confirming"
    assert ff._map_status("EXCHANGE") == "exchanging"
    assert ff._map_status("WITHDRAW") == "sending"
    assert ff._map_status("DONE") == "finished"
    assert ff._map_status("EXPIRED") == "expired"
    assert ff._map_status("EMERGENCY") == "failed"
    assert ff._map_status(None) == "waiting"


def test_signature_is_hmac_sha256_of_body(monkeypatch):
    monkeypatch.setattr(ff, "FIXEDFLOAT_API_SECRET", "s3cret")
    body = '{"a":1}'
    expected = hmac.new(b"s3cret", body.encode(), hashlib.sha256).hexdigest()
    assert ff._sign(body) == expected


# ── get_estimated ───────────────────────────────────────────────────────────

async def test_get_estimated_forward(mock_ff):
    fake_post, calls = mock_ff
    fake_post.response = {"from": {"amount": "0.01"}, "to": {"amount": "615.5"}}
    res = await ff.get_estimated("btc", "btc", "usdt", "trx", "0.01")
    assert res["estimatedAmountTo"] == 615.5
    path, payload = calls[0]
    assert path == "/price"
    assert payload["direction"] == "from"
    assert payload["fromCcy"] == "BTC" and payload["toCcy"] == "USDTTRC"


async def test_get_estimated_reverse_returns_send_amount(mock_ff):
    fake_post, calls = mock_ff
    fake_post.response = {"from": {"amount": "0.0099"}, "to": {"amount": "600"}}
    res = await ff.get_estimated("btc", "btc", "usdt", "trx", "600", reverse=True)
    assert res["estimatedAmountTo"] == 600.0
    assert res["estimatedAmountFrom"] == 0.0099
    assert calls[0][1]["direction"] == "to"
    assert calls[0][1]["type"] == "fixed"  # reverse forces fixed


async def test_get_estimated_none_on_api_failure(mock_ff):
    fake_post, _ = mock_ff
    fake_post.response = None
    assert await ff.get_estimated("btc", "btc", "eth", "eth", "1") is None


# ── create_exchange ─────────────────────────────────────────────────────────

async def test_create_exchange_extracts_token_and_address(mock_ff):
    fake_post, calls = mock_ff
    fake_post.response = {
        "id": "ABC123",
        "token": "tok_secret",
        "status": "NEW",
        "from": {"address": "1DepositAddr", "amount": "0.01"},
        "to": {"address": "0xUser", "amount": "615.5"},
    }
    res = await ff.create_exchange("btc", "btc", "usdt", "trx", "0.01", "0xUser")
    assert res["id"] == "ABC123"
    assert res["token"] == "tok_secret"          # must be stored for later /order
    assert res["addressFrom"] == "1DepositAddr"
    assert res["amountTo"] == "615.5"
    assert res["status"] == "waiting"            # mapped from NEW
    assert calls[0][0] == "/create"
    assert calls[0][1]["toAddress"] == "0xUser"


# ── get_exchange ────────────────────────────────────────────────────────────

async def test_get_exchange_requires_token(mock_ff):
    fake_post, calls = mock_ff
    fake_post.response = {"status": "DONE"}
    # No token -> must not hit the API and returns None.
    assert await ff.get_exchange("ABC123", None) is None
    assert calls == []


async def test_get_exchange_maps_status(mock_ff):
    fake_post, calls = mock_ff
    fake_post.response = {
        "status": "WITHDRAW",
        "from": {"address": "1Dep", "amount": "0.01", "code": "BTC"},
        "to": {"address": "0xUser", "amount": "615.5", "code": "USDTTRC20"},
    }
    res = await ff.get_exchange("ABC123", "tok_secret")
    assert res["status"] == "sending"
    assert res["addressFrom"] == "1Dep"
    assert calls[0] == ("/order", {"id": "ABC123", "token": "tok_secret"})


# ── create_exchange type selection ──────────────────────────────────────────

async def test_create_type_is_float_by_default_and_fixed_when_requested(mock_ff):
    fake_post, calls = mock_ff
    fake_post.response = {"id": "1", "token": "t", "status": "NEW",
                          "from": {"address": "a", "amount": "1"},
                          "to": {"address": "b", "amount": "2"}}
    await ff.create_exchange("btc", "btc", "eth", "eth", "1", "b")
    assert calls[-1][1]["type"] == "float"
    await ff.create_exchange("btc", "btc", "eth", "eth", "1", "b", fixed=True)
    assert calls[-1][1]["type"] == "fixed"


# ── get_exchange_ranges ─────────────────────────────────────────────────────

async def test_ranges_returns_none_without_api_call(mock_ff):
    # FF has no min/max endpoint; caller falls back to local minimums.
    fake_post, calls = mock_ff
    assert await ff.get_exchange_ranges("btc", "btc", "eth", "eth") is None
    assert calls == []  # must not hit the network


# ── _post HTTP boundary (httpx mocked) ──────────────────────────────────────

class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeClient:
    """Async-context-manager stand-in for httpx.AsyncClient."""
    last = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, content=None, headers=None, timeout=None):
        _FakeClient.last = {"url": url, "content": content, "headers": headers}
        return _FakeResp(_FakeClient.response)


async def test_post_signs_body_and_returns_data(monkeypatch):
    monkeypatch.setattr(ff, "FIXEDFLOAT_API_KEY", "key123")
    monkeypatch.setattr(ff, "FIXEDFLOAT_API_SECRET", "secret123")
    monkeypatch.setattr(ff.httpx, "AsyncClient", _FakeClient)
    _FakeClient.response = {"code": 0, "msg": "OK", "data": {"hello": "world"}}

    data, err = await ff._post("/price", {"amount": 1})
    assert err is None
    assert data == {"hello": "world"}
    sent = _FakeClient.last
    assert sent["headers"]["X-API-KEY"] == "key123"
    # Signature must be HMAC-SHA256 of the exact bytes sent.
    expected = hmac.new(b"secret123", sent["content"].encode(), hashlib.sha256).hexdigest()
    assert sent["headers"]["X-API-SIGN"] == expected


async def test_post_returns_none_on_error_code(monkeypatch):
    monkeypatch.setattr(ff.httpx, "AsyncClient", _FakeClient)
    _FakeClient.response = {"code": 301, "msg": "Invalid pair", "data": None}
    data, err = await ff._post("/create", {})
    assert data is None
    assert "Invalid pair" in err


# ── error surfacing ─────────────────────────────────────────────────────────

async def test_get_estimated_returns_provider_reason(mock_ff):
    """The user must see *why* a quote failed, not a generic message."""
    fake_post, _ = mock_ff
    fake_post.response = None
    fake_post.error = "Amount is less than minimum"
    res = await ff.get_estimated("btc", "btc", "usdt", "trx", "0.5", reverse=True)
    assert res == {"error": "Amount is less than minimum"}
