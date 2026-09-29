"""
~/nexora/server/store.py — Base de dados SQLite e persistência do NEXORA 3.0.
Usa padrão WAL e conexões thread-local isoladas.
"""

import json
import os
import sqlite3
import threading
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "nexora.db"

_local = threading.local()
_ensured_schemas = set()
_ensure_lock = threading.Lock()


def get_connection() -> sqlite3.Connection:
    """Retorna uma conexão isolada por thread."""
    if not hasattr(_local, "con") or _local.con is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(DB_PATH), timeout=30.0, check_same_thread=False)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode = WAL;")
        con.execute("PRAGMA synchronous = NORMAL;")
        _local.con = con
    return _local.con


def ensure(schema_sql: str, name: str) -> None:
    """Aplica o schema DDL se ainda não aplicado no processo."""
    with _ensure_lock:
        if name in _ensured_schemas:
            return
        con = get_connection()
        con.executescript(schema_sql)
        _ensured_schemas.add(name)


def query(sql: str, args: tuple = ()) -> list[dict]:
    con = get_connection()
    cur = con.execute(sql, args)
    return [dict(row) for row in cur.fetchall()]


def one(sql: str, args: tuple = ()) -> dict | None:
    con = get_connection()
    cur = con.execute(sql, args)
    row = cur.fetchone()
    return dict(row) if row else None


def execute(sql: str, args: tuple = ()) -> tuple[int, int]:
    con = get_connection()
    cur = con.execute(sql, args)
    con.commit()
    return (cur.lastrowid or 0, cur.rowcount or 0)


# Core Schemas
_CORE_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at REAL NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT
);

CREATE TABLE IF NOT EXISTS avatars (
    owner TEXT PRIMARY KEY,
    choice TEXT NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent TEXT NOT NULL,
    session_name TEXT NOT NULL,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    files TEXT,
    at REAL NOT NULL,
    ms INTEGER DEFAULT 0
);
"""

ensure(_CORE_SCHEMA, "core")


def settings() -> dict:
    rows = query("SELECT key, value FROM settings")
    current = {r["key"]: r["value"] for r in rows}
    defaults = {
        "display_name": "",
        "operator_name": "Fabiano",
        "timezone": "America/Sao_Paulo",
        "voice_engine": "local"
    }
    defaults.update(current)
    return defaults


def save_settings(changes: dict) -> None:
    now = time.time()
    for k, v in changes.items():
        execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (str(k), str(v), now)
        )


def audit(actor: str, action: str, detail_dict: dict | None = None) -> None:
    now = time.time()
    detail_str = json.dumps(detail_dict or {}, ensure_ascii=False)
    execute(
        "INSERT INTO audit (at, actor, action, detail) VALUES (?, ?, ?, ?)",
        (now, actor, action, detail_str)
    )


def recent_audit(limit: int = 50) -> list[dict]:
    return query("SELECT * FROM audit ORDER BY at DESC LIMIT ?", (limit,))
