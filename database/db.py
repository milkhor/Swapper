import aiosqlite
import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def _resolve_db_path() -> str:
    """
    Where the SQLite file lives, in priority order:
      1. DB_PATH                      — explicit override
      2. $RAILWAY_VOLUME_MOUNT_PATH   — set automatically when a Railway volume
                                        is attached, so persistence works with
                                        no manual configuration
      3. ./swaps.db                   — local dev (ephemeral on Railway!)
    """
    explicit = os.getenv("DB_PATH")
    if explicit:
        return explicit
    volume = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
    if volume:
        return os.path.join(volume, "swaps.db")
    return "swaps.db"


DB_PATH = _resolve_db_path()


# ── Init ───────────────────────────────────────────────────────────────────────

async def init_db():
    # DB_PATH may point into a mounted volume (e.g. /data/swaps.db); make sure the
    # directory exists so the first boot doesn't fail on "unable to open database".
    parent = os.path.dirname(DB_PATH)
    if parent:
        try:
            os.makedirs(parent, exist_ok=True)
        except OSError as e:
            logger.error(f"Could not create DB directory {parent}: {e}")

    logger.info(f"Using database at {os.path.abspath(DB_PATH)}")
    if not os.getenv("DB_PATH") and not os.getenv("RAILWAY_VOLUME_MOUNT_PATH"):
        logger.warning(
            "No DB_PATH or Railway volume configured — the database is EPHEMERAL "
            "and will be wiped on every redeploy. Attach a volume to retain "
            "transaction records (required for the 1-year retention policy)."
        )

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS swaps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                language_code TEXT,
                exchange_id TEXT,
                order_token TEXT,
                currency_from TEXT,
                currency_to TEXT,
                amount_from REAL,
                amount_to REAL,
                address_to TEXT,
                address_from TEXT,
                payment_url TEXT,
                status TEXT DEFAULT 'created',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                lang TEXT DEFAULT 'en',
                aml_accepted INTEGER DEFAULT 0,
                aml_accepted_at TIMESTAMP,
                swap_count INTEGER DEFAULT 0,
                rank TEXT DEFAULT 'standard',
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS currencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                network TEXT NOT NULL,
                label TEXT NOT NULL,
                min_amount REAL NOT NULL DEFAULT 0.0,
                is_fiat INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS blocked_users (
                user_id INTEGER PRIMARY KEY,
                blocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reason TEXT DEFAULT ''
            )
        """)
        # Audit log of administrative access to / export of customer records
        # (FixedFloat compliance requirement #4).
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admin_access_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                target TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

        # Migrate: add columns if they don't exist yet
        migrations = [
            ("aml_accepted", "INTEGER DEFAULT 0"),
            ("aml_accepted_at", "TIMESTAMP"),
            ("registered_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("swap_count", "INTEGER DEFAULT 0"),
            ("rank", "TEXT DEFAULT 'standard'")
        ]
        
        for col_name, col_type in migrations:
            try:
                await db.execute(f"ALTER TABLE user_settings ADD COLUMN {col_name} {col_type}")
                await db.commit()
            except Exception:
                pass  # column already exists

        swap_migrations = [
            ("address_from", "TEXT"),
            ("payment_url", "TEXT"),
            ("username", "TEXT"),
            ("language_code", "TEXT"),
            ("order_token", "TEXT"),
        ]
        for col_name, col_type in swap_migrations:
            try:
                await db.execute(f"ALTER TABLE swaps ADD COLUMN {col_name} {col_type}")
                await db.commit()
                if col_name == "order_token":
                    # First run after the FixedFloat migration: orders created with
                    # the previous provider have no token, so the new checker can
                    # never resolve them. Close them out instead of polling forever.
                    # (Records are kept — only the status label changes.)
                    cur = await db.execute("""
                        UPDATE swaps SET status = 'expired'
                        WHERE order_token IS NULL
                          AND status NOT IN ('finished', 'failed', 'refunded', 'expired')
                    """)
                    await db.commit()
                    if cur.rowcount:
                        logger.info(
                            f"Marked {cur.rowcount} pre-FixedFloat order(s) as expired "
                            f"(no order token — not trackable with the new provider)"
                        )
            except Exception:
                pass  # column already exists

        # Index for fast lookup of the Telegram user record by provider order ID.
        try:
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_swaps_exchange_id ON swaps(exchange_id)"
            )
            await db.commit()
        except Exception:
            pass

        cursor = await db.execute("SELECT COUNT(*) FROM currencies")
        count = (await cursor.fetchone())[0]
        if count == 0:
            await _seed_currencies(db)

    logger.info("Database initialized")
    
async def update_user_rank(user_id: int, rank: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)", (user_id,))
        await db.execute("UPDATE user_settings SET rank = ? WHERE user_id = ?", (rank, user_id))
        await db.commit()
        return True
    
async def update_user_swaps_count(user_id: int, count: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)", (user_id,))
        await db.execute("UPDATE user_settings SET swap_count = ? WHERE user_id = ?", (count, user_id))
        await db.commit()
        return True


async def _seed_currencies(db):
    defaults = [
        # CRYPTO
        ("btc",  "btc",  "BTC",          0.0001, 0, 1, 1),
        ("eth",  "eth",  "ETH",           0.005,  0, 1, 2),
        ("usdt", "trx",  "USDT (TRC20)",  1.0,    0, 1, 3),
        ("usdt", "eth",  "USDT (ERC20)", 10.0,    0, 1, 4),
        ("sol",  "sol",  "SOL",           0.1,    0, 1, 5),
        ("bnb",  "bsc",  "BNB",           0.01,   0, 1, 6),
        ("trx",  "trx",  "TRX",          50.0,    0, 1, 7),
        ("xmr",  "xmr",  "XMR",           0.1,    0, 1, 5),
        ("usdc", "matic", "USDC (Polygon)", 10.0,  0, 1, 6), 
        ("usdt", "matic", "USDT (Polygon)", 10.0,  0, 1, 7),
        
        # FIAT
        ("usd",  "usd",  "💵 USD",       20.0,    1, 1, 8),
        ("eur",  "eur",  "💶 EUR",       20.0,    1, 1, 9),
    ]
    await db.executemany("""
        INSERT INTO currencies
            (ticker, network, label, min_amount, is_fiat, is_active, sort_order)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, defaults)
    await db.commit()
    logger.info("Default currencies seeded")


# ── Language ───────────────────────────────────────────────────────────────────

async def get_user_lang(user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT lang FROM user_settings WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else "en"


async def set_user_lang(user_id: int, lang: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO user_settings (user_id, lang)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET lang = excluded.lang
        """, (user_id, lang))
        await db.commit()


# ── AML ────────────────────────────────────────────────────────────────────────

async def has_accepted_aml(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT aml_accepted FROM user_settings WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return bool(row[0]) if row else False


async def accept_aml(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.now().isoformat()
        await db.execute("""
            INSERT INTO user_settings (user_id, aml_accepted, aml_accepted_at)
            VALUES (?, 1, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                aml_accepted = 1,
                aml_accepted_at = excluded.aml_accepted_at
        """, (user_id, now))
        await db.commit()


async def ensure_user_registered(user_id: int):
    """Create user_settings row if not exists (called on /start)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO user_settings (user_id, registered_at)
            VALUES (?, ?)
        """, (user_id, datetime.now().isoformat()))
        await db.commit()


# ── Ranks ──────────────────────────────────────────────────────────────────────

def get_rank(swap_count: int) -> tuple[str, str]:
    """Return (rank_emoji, rank_name) based on swap count."""
    if swap_count == 0:
        return "🆕", "Newcomer"
    elif swap_count < 3:
        return "🥉", "Bronze"
    elif swap_count < 10:
        return "🥈", "Silver"
    elif swap_count < 25:
        return "🥇", "Gold"
    elif swap_count < 50:
        return "💎", "Diamond"
    else:
        return "👑", "VIP"


async def get_user_rank(user_id: int) -> tuple[str, str, int]:
    """Return (emoji, name, swap_count)."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Проверяем ручной ранг из настроек
        cursor = await db.execute("SELECT rank, swap_count FROM user_settings WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        
        if row and row[0] and row[0] != 'standard':
            # Если установлен ручной ранг (VIP/Whale)
            rank_name = row[0].capitalize()
            rank_emoji = "👑" if rank_name == "Vip" else "🐋"
            return rank_emoji, rank_name, row[1]
            
        # Иначе считаем по количеству обменов
        cursor = await db.execute(
            "SELECT COUNT(*) FROM swaps WHERE user_id = ? AND status = 'finished'",
            (user_id,)
        )
        count = (await cursor.fetchone())[0]
    emoji, name = get_rank(count)
    return emoji, name, count


# ── Swaps ──────────────────────────────────────────────────────────────────────

async def save_swap(user_id: int, exchange_id: str, currency_from: str,
                    currency_to: str, amount_from: float, amount_to: float,
                    address_to: str, address_from: str | None = None,
                    payment_url: str | None = None,
                    status: str = "waiting",
                    username: str | None = None,
                    language_code: str | None = None,
                    order_token: str | None = None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO swaps
                (user_id, username, language_code, exchange_id, order_token,
                 currency_from, currency_to,
                 amount_from, amount_to, address_to, address_from,
                 payment_url, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, username, language_code, exchange_id, order_token,
              currency_from, currency_to,
              amount_from, amount_to, address_to, address_from,
              payment_url, status))
        await db.commit()
        return cursor.lastrowid


async def get_user_swaps(user_id: int, limit: int = 5) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM swaps WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def update_swap_status(exchange_id: str, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE swaps SET status = ? WHERE exchange_id = ?",
            (status, exchange_id)
        )
        await db.commit()


async def update_swap_payment_details(exchange_id: str,
                                      address_from: str | None = None,
                                      payment_url: str | None = None,
                                      status: str | None = None):
    updates = []
    params = []
    if address_from:
        updates.append("address_from = ?")
        params.append(address_from)
    if payment_url:
        updates.append("payment_url = ?")
        params.append(payment_url)
    if status:
        updates.append("status = ?")
        params.append(status)
    if not updates:
        return

    params.append(exchange_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE swaps SET {', '.join(updates)} WHERE exchange_id = ?",
            params
        )
        await db.commit()


async def get_active_swaps() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT * FROM swaps
            WHERE status NOT IN ('finished', 'failed', 'refunded', 'expired')
            AND exchange_id IS NOT NULL
            ORDER BY created_at DESC
        """)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_all_swaps(limit: int = 10) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM swaps ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_swaps_by_period(days: int | None = None,
                               date_from: str | None = None,
                               date_to: str | None = None,
                               limit: int = 500) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if days is not None:
            since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            cursor = await db.execute("""
                SELECT * FROM swaps
                WHERE DATE(created_at) >= ?
                ORDER BY created_at DESC LIMIT ?
            """, (since, limit))
        elif date_from and date_to:
            cursor = await db.execute("""
                SELECT * FROM swaps
                WHERE DATE(created_at) BETWEEN ? AND ?
                ORDER BY created_at DESC LIMIT ?
            """, (date_from, date_to, limit))
        else:
            cursor = await db.execute(
                "SELECT * FROM swaps ORDER BY created_at DESC LIMIT ?", (limit,)
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_swap_by_exchange_id(exchange_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM swaps WHERE exchange_id = ?", (exchange_id.strip(),)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


# ── Admin access audit ───────────────────────────────────────────────────────

async def log_admin_access(admin_id: int, action: str, target: str | None = None):
    """Record administrative access to / export of customer records."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO admin_access_log (admin_id, action, target) VALUES (?, ?, ?)",
            (admin_id, action, target)
        )
        await db.commit()


async def get_admin_access_log(limit: int = 30) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM admin_access_log ORDER BY id DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


# ── Stats ──────────────────────────────────────────────────────────────────────

async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM swaps")
        total = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(*) FROM swaps WHERE status = 'finished'"
        )
        finished = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(*) FROM swaps WHERE status IN "
            "('waiting','confirming','exchanging','sending')"
        )
        pending = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(*) FROM swaps WHERE status IN ('failed','expired')"
        )
        failed = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(DISTINCT user_id) FROM swaps"
        )
        users = (await cursor.fetchone())[0]

        # Registrations
        cursor = await db.execute("SELECT COUNT(*) FROM user_settings")
        registrations_total = (await cursor.fetchone())[0]

        today     = datetime.now().strftime("%Y-%m-%d")
        week_ago  = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        cursor = await db.execute(
            "SELECT COUNT(*) FROM swaps WHERE DATE(created_at) = ?", (today,)
        )
        today_count = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(*) FROM swaps WHERE DATE(created_at) >= ?", (week_ago,)
        )
        week_count = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(*) FROM swaps WHERE DATE(created_at) >= ?", (month_ago,)
        )
        month_count = (await cursor.fetchone())[0]

        # Registrations by period
        cursor = await db.execute(
            "SELECT COUNT(*) FROM user_settings WHERE DATE(registered_at) = ?", (today,)
        )
        reg_today = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(*) FROM user_settings WHERE DATE(registered_at) >= ?", (week_ago,)
        )
        reg_week = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(*) FROM user_settings WHERE DATE(registered_at) >= ?", (month_ago,)
        )
        reg_month = (await cursor.fetchone())[0]

        return {
            "total":               total,
            "finished":            finished,
            "pending":             pending,
            "failed":              failed,
            "users":               users,
            "registrations_total": registrations_total,
            "reg_today":           reg_today,
            "reg_week":            reg_week,
            "reg_month":           reg_month,
            "today":               today_count,
            "week":                week_count,
            "month":               month_count,
        }


async def get_top_pairs(limit: int = 5) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT currency_from, currency_to,
                   COUNT(*) as count, SUM(amount_from) as volume
            FROM swaps WHERE status = 'finished'
            GROUP BY currency_from, currency_to
            ORDER BY count DESC LIMIT ?
        """, (limit,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_average_amount() -> float:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT AVG(amount_from) FROM swaps WHERE status = 'finished'"
        )
        result = (await cursor.fetchone())[0]
        return round(result, 6) if result else 0.0


async def get_volume_by_period(days: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        cursor = await db.execute("""
            SELECT COUNT(*) as count, COUNT(DISTINCT user_id) as users
            FROM swaps
            WHERE DATE(created_at) >= ? AND status = 'finished'
        """, (since,))
        row = await cursor.fetchone()
        return {"count": row[0], "users": row[1]}


# ── User management ────────────────────────────────────────────────────────────

async def get_all_users() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Берем всех из user_settings и джойним статистику из swaps
        query = """
            SELECT 
                u.user_id, 
                u.swap_count, 
                u.rank,
                u.registered_at,
                (SELECT SUM(amount_from) FROM swaps WHERE user_id = u.user_id AND status = 'finished') as total_volume,
                (SELECT MAX(created_at) FROM swaps WHERE user_id = u.user_id) as last_swap,
                CASE WHEN b.user_id IS NOT NULL THEN 1 ELSE 0 END AS is_blocked
            FROM user_settings u
            LEFT JOIN blocked_users b ON u.user_id = b.user_id
            ORDER BY u.registered_at DESC
        """
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_user_swap_history(user_id: int, limit: int = 20) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT * FROM swaps WHERE user_id = ?
            ORDER BY created_at DESC LIMIT ?
        """, (user_id, limit))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def is_user_blocked(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM blocked_users WHERE user_id = ?", (user_id,)
        )
        return (await cursor.fetchone()) is not None


async def block_user(user_id: int, reason: str = "") -> bool:
    if await is_user_blocked(user_id):
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO blocked_users (user_id, reason) VALUES (?, ?)",
            (user_id, reason)
        )
        await db.commit()
    return True


async def unblock_user(user_id: int) -> bool:
    if not await is_user_blocked(user_id):
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM blocked_users WHERE user_id = ?", (user_id,)
        )
        await db.commit()
    return True


# ── Logs ───────────────────────────────────────────────────────────────────────

async def get_recent_logs(n: int = 20) -> list[str]:
    log_path = os.path.join("logs", "bot.log")
    if not os.path.exists(log_path):
        return ["Log file not found."]
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return [l.strip() for l in lines[-n:] if l.strip()]
    except Exception as e:
        return [f"Error reading logs: {e}"]


# ── Currency management ────────────────────────────────────────────────────────

async def get_currencies(fiat_only=False, crypto_only=False, active_only=True) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM currencies WHERE 1=1"
        if active_only:
            query += " AND is_active = 1"
        if fiat_only:
            query += " AND is_fiat = 1"
        if crypto_only:
            query += " AND is_fiat = 0"
        query += " ORDER BY sort_order ASC"
        cursor = await db.execute(query)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_all_currencies_admin() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM currencies ORDER BY is_fiat ASC, sort_order ASC"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def add_currency(ticker: str, network: str, label: str,
                       min_amount: float, is_fiat: bool) -> int:
    ticker  = ticker.lower().replace("$", "").replace(" ", "").strip()
    network = network.lower().replace("$", "").replace(" ", "").strip()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT MAX(sort_order) FROM currencies")
        max_order = (await cursor.fetchone())[0] or 0
        cursor = await db.execute("""
            INSERT INTO currencies
                (ticker, network, label, min_amount, is_fiat, is_active, sort_order)
            VALUES (?, ?, ?, ?, ?, 1, ?)
        """, (ticker, network, label, min_amount, int(is_fiat), max_order + 1))
        await db.commit()
        return cursor.lastrowid


async def toggle_currency(currency_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT is_active FROM currencies WHERE id = ?", (currency_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return False
        new_state = 0 if row[0] else 1
        await db.execute(
            "UPDATE currencies SET is_active = ? WHERE id = ?",
            (new_state, currency_id)
        )
        await db.commit()
        return bool(new_state)


async def update_currency_min(currency_id: int, min_amount: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE currencies SET min_amount = ? WHERE id = ?",
            (min_amount, currency_id)
        )
        await db.commit()


async def delete_currency(currency_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM currencies WHERE id = ?", (currency_id,))
        await db.commit()
