"""Tiny persistence layer (SQLite). Swap DATABASE path for PostgreSQL/RDS in the cloud."""
from __future__ import annotations

import json
import sqlite3
import threading
import time

from .config import settings

DB_PATH = settings.DATA_DIR / "trademind.db"
_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


_db = _conn()
_db.executescript("""
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, email TEXT, name TEXT, picture TEXT, provider TEXT,
    created_at REAL, last_login REAL);
CREATE TABLE IF NOT EXISTS accounts (
    user_id TEXT PRIMARY KEY, state_json TEXT, updated_at REAL);
""")
_db.commit()


def upsert_user(uid: str, email: str, name: str, picture: str, provider: str) -> dict:
    now = time.time()
    with _lock:
        _db.execute("""INSERT INTO users (id, email, name, picture, provider, created_at, last_login)
                       VALUES (?,?,?,?,?,?,?)
                       ON CONFLICT(id) DO UPDATE SET email=excluded.email, name=excluded.name,
                       picture=excluded.picture, last_login=excluded.last_login""",
                    (uid, email, name, picture, provider, now, now))
        _db.commit()
    return {"id": uid, "email": email, "name": name, "picture": picture, "provider": provider}


def get_user(uid: str) -> dict | None:
    row = _db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    return dict(row) if row else None


def load_account(uid: str) -> dict | None:
    row = _db.execute("SELECT state_json FROM accounts WHERE user_id=?", (uid,)).fetchone()
    return json.loads(row["state_json"]) if row else None


def save_account(uid: str, state: dict) -> None:
    with _lock:
        _db.execute("""INSERT INTO accounts (user_id, state_json, updated_at) VALUES (?,?,?)
                       ON CONFLICT(user_id) DO UPDATE SET state_json=excluded.state_json,
                       updated_at=excluded.updated_at""", (uid, json.dumps(state), time.time()))
        _db.commit()
