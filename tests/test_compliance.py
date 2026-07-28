"""
Tests for the FixedFloat data-retention / compliance layer:
Telegram user info stored per order, retrievable by provider order ID,
plus the admin access audit log.
"""
import aiosqlite
import pytest

import database.db as db


async def _make_swap(fresh_db, **overrides):
    kwargs = dict(
        user_id=12345,
        username="alice",
        language_code="ru",
        exchange_id="FF_ORDER_1",
        currency_from="btc_btc",
        currency_to="usdt_trx",
        amount_from=0.01,
        amount_to=600.0,
        address_to="Taddr123",
        status="waiting",
    )
    kwargs.update(overrides)
    return await fresh_db.save_swap(**kwargs)


# ── Schema ──────────────────────────────────────────────────────────────────

async def test_swaps_table_has_compliance_columns(fresh_db):
    async with aiosqlite.connect(fresh_db.DB_PATH) as c:
        cur = await c.execute("PRAGMA table_info(swaps)")
        cols = {r[1] for r in await cur.fetchall()}
    assert {"username", "language_code", "exchange_id", "user_id", "created_at"} <= cols


async def test_exchange_id_index_exists(fresh_db):
    async with aiosqlite.connect(fresh_db.DB_PATH) as c:
        cur = await c.execute("PRAGMA index_list(swaps)")
        idx = [r[1] for r in await cur.fetchall()]
    assert any("exchange_id" in name for name in idx)


async def test_admin_access_log_table_exists(fresh_db):
    async with aiosqlite.connect(fresh_db.DB_PATH) as c:
        cur = await c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='admin_access_log'"
        )
        assert await cur.fetchone() is not None


# ── Data collection & association ───────────────────────────────────────────

async def test_save_swap_persists_telegram_identity(fresh_db):
    await _make_swap(fresh_db)
    rec = await fresh_db.get_swap_by_exchange_id("FF_ORDER_1")
    assert rec is not None
    assert rec["user_id"] == 12345
    assert rec["username"] == "alice"
    assert rec["language_code"] == "ru"
    assert rec["id"]  # internal transaction id present
    assert rec["created_at"]  # timestamp recorded


async def test_lookup_by_order_id_strips_whitespace(fresh_db):
    await _make_swap(fresh_db, exchange_id="FF_ORDER_2")
    rec = await fresh_db.get_swap_by_exchange_id("   FF_ORDER_2  ")
    assert rec is not None and rec["exchange_id"] == "FF_ORDER_2"


async def test_lookup_unknown_order_returns_none(fresh_db):
    assert await fresh_db.get_swap_by_exchange_id("does-not-exist") is None


async def test_order_token_persisted_for_status_queries(fresh_db):
    # FixedFloat needs the per-order token to query status later.
    await _make_swap(fresh_db, exchange_id="FF_TOK", order_token="tok_abc")
    rec = await fresh_db.get_swap_by_exchange_id("FF_TOK")
    assert rec["order_token"] == "tok_abc"


async def test_username_may_be_missing(fresh_db):
    # Telegram username is optional; language_code too.
    await _make_swap(fresh_db, exchange_id="FF_ORDER_3", username=None, language_code=None)
    rec = await fresh_db.get_swap_by_exchange_id("FF_ORDER_3")
    assert rec["username"] is None
    assert rec["language_code"] is None
    assert rec["user_id"] == 12345  # user id still linked


# ── Retention ───────────────────────────────────────────────────────────────

async def test_records_survive_reinit(fresh_db):
    """init_db must never drop existing transaction records (>=1yr retention)."""
    await _make_swap(fresh_db, exchange_id="FF_KEEP")
    await fresh_db.init_db()  # simulate a restart
    rec = await fresh_db.get_swap_by_exchange_id("FF_KEEP")
    assert rec is not None


# ── Admin access audit ──────────────────────────────────────────────────────

async def test_admin_access_log_roundtrip(fresh_db):
    await fresh_db.log_admin_access(999, "order_lookup", "FF_ORDER_1")
    logs = await fresh_db.get_admin_access_log()
    assert logs and logs[0]["admin_id"] == 999
    assert logs[0]["action"] == "order_lookup"
    assert logs[0]["target"] == "FF_ORDER_1"


async def test_admin_access_log_orders_newest_first(fresh_db):
    await fresh_db.log_admin_access(1, "export_csv", "a")
    await fresh_db.log_admin_access(2, "order_lookup", "b")
    logs = await fresh_db.get_admin_access_log()
    assert [l["action"] for l in logs[:2]] == ["order_lookup", "export_csv"]


async def test_access_log_respects_limit(fresh_db):
    for i in range(5):
        await fresh_db.log_admin_access(1, "order_lookup", str(i))
    assert len(await fresh_db.get_admin_access_log(limit=3)) == 3


# ── Migration from legacy schema ────────────────────────────────────────────

async def test_migration_adds_columns_to_legacy_db(tmp_path, monkeypatch):
    """A pre-existing DB without the new columns must migrate without data loss."""
    path = str(tmp_path / "legacy.db")
    # Build a legacy swaps table (no username / language_code).
    async with aiosqlite.connect(path) as c:
        await c.execute("""
            CREATE TABLE swaps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                exchange_id TEXT,
                currency_from TEXT,
                currency_to TEXT,
                amount_from REAL,
                amount_to REAL,
                address_to TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await c.execute(
            "INSERT INTO swaps (user_id, exchange_id, status) VALUES (?, ?, ?)",
            (777, "OLD_ORDER", "finished"),
        )
        await c.commit()

    monkeypatch.setattr(db, "DB_PATH", path)
    await db.init_db()  # runs migration

    async with aiosqlite.connect(path) as c:
        cur = await c.execute("PRAGMA table_info(swaps)")
        cols = {r[1] for r in await cur.fetchall()}
    assert "username" in cols and "language_code" in cols

    # Legacy row preserved and still retrievable by order id.
    rec = await db.get_swap_by_exchange_id("OLD_ORDER")
    assert rec is not None and rec["user_id"] == 777
    assert rec["username"] is None  # backfilled as NULL


async def test_pre_migration_active_orders_are_closed_out(tmp_path, monkeypatch):
    """Legacy orders have no FF token, so they must not be polled forever."""
    path = str(tmp_path / "legacy2.db")
    async with aiosqlite.connect(path) as c:
        await c.execute("""
            CREATE TABLE swaps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                exchange_id TEXT,
                currency_from TEXT,
                currency_to TEXT,
                amount_from REAL,
                amount_to REAL,
                address_to TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await c.executemany(
            "INSERT INTO swaps (user_id, exchange_id, status) VALUES (?, ?, ?)",
            [(1, "OLD_WAITING", "waiting"), (1, "OLD_DONE", "finished")],
        )
        await c.commit()

    monkeypatch.setattr(db, "DB_PATH", path)
    await db.init_db()

    # Stale active order closed out; finished order untouched; records retained.
    assert (await db.get_swap_by_exchange_id("OLD_WAITING"))["status"] == "expired"
    assert (await db.get_swap_by_exchange_id("OLD_DONE"))["status"] == "finished"

    # Idempotent: a later order that legitimately has a token stays active.
    await db.save_swap(
        user_id=1, exchange_id="NEW_ONE", order_token="tok",
        currency_from="btc_btc", currency_to="eth_eth",
        amount_from=1.0, amount_to=2.0, address_to="x", status="waiting",
    )
    await db.init_db()
    assert (await db.get_swap_by_exchange_id("NEW_ONE"))["status"] == "waiting"
