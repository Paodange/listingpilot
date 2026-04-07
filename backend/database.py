"""
Simple SQLite database for user management.
For MVP only – migrate to PostgreSQL when scaling.
"""

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "listingpilot.db"


def _ensure_dir():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_db():
    _ensure_dir()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create tables if they don't exist."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                email                TEXT UNIQUE NOT NULL,
                password             TEXT NOT NULL,
                plan                 TEXT NOT NULL DEFAULT 'free',
                ls_customer_id       TEXT DEFAULT '',
                ls_subscription_id   TEXT DEFAULT '',
                pp_subscription_id   TEXT DEFAULT '',
                created_at           REAL NOT NULL,
                updated_at           REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usage_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                date        TEXT NOT NULL,
                count       INTEGER NOT NULL DEFAULT 0,
                UNIQUE(user_id, date),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        # Migrate: add pp_subscription_id if missing (safe to run on existing DB)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "pp_subscription_id" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN pp_subscription_id TEXT DEFAULT ''")


# ----- User CRUD -----

def create_user(email: str, hashed_password: str) -> dict | None:
    now = time.time()
    with get_db() as conn:
        try:
            conn.execute(
                "INSERT INTO users (email, password, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (email, hashed_password, now, now),
            )
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            return dict(row)
        except sqlite3.IntegrityError:
            return None


def get_user_by_email(email: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def update_user_plan(
    email: str,
    plan: str,
    ls_customer_id: str | None = None,
    ls_subscription_id: str | None = None,
    pp_subscription_id: str | None = None,
):
    now = time.time()
    fields = ["plan=?", "updated_at=?"]
    values: list = [plan, now]
    if ls_customer_id is not None:
        fields.insert(1, "ls_customer_id=?")
        values.insert(1, ls_customer_id)
    if ls_subscription_id is not None:
        fields.insert(2, "ls_subscription_id=?")
        values.insert(2, ls_subscription_id)
    if pp_subscription_id is not None:
        fields.insert(3, "pp_subscription_id=?")
        values.insert(3, pp_subscription_id)
    values.append(email)
    with get_db() as conn:
        conn.execute(
            f"UPDATE users SET {', '.join(fields)} WHERE email=?",
            values,
        )


# ----- Usage tracking -----

def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def get_daily_usage(user_id: int) -> int:
    today = _today()
    with get_db() as conn:
        row = conn.execute(
            "SELECT count FROM usage_log WHERE user_id=? AND date=?",
            (user_id, today),
        ).fetchone()
        return row["count"] if row else 0


def increment_usage(user_id: int) -> int:
    today = _today()
    with get_db() as conn:
        row = conn.execute(
            "SELECT count FROM usage_log WHERE user_id=? AND date=?",
            (user_id, today),
        ).fetchone()
        if row:
            new_count = row["count"] + 1
            conn.execute(
                "UPDATE usage_log SET count=? WHERE user_id=? AND date=?",
                (new_count, user_id, today),
            )
        else:
            new_count = 1
            conn.execute(
                "INSERT INTO usage_log (user_id, date, count) VALUES (?, ?, ?)",
                (user_id, today, new_count),
            )
        return new_count


# Initialize on import
init_db()
