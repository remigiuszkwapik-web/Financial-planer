"""SQLite storage — the single source of truth.

Exports (Excel / Markdown) are always derived from this; they are never the
source. Amounts are stored as integer cents.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "finance.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL UNIQUE,
                position   INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                amount_cents INTEGER NOT NULL,
                payee        TEXT,
                raw_text     TEXT,
                image_path   TEXT,
                category_id  INTEGER REFERENCES categories(id) ON DELETE SET NULL,
                created_at   TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )


# ---- categories -------------------------------------------------------------

def list_categories() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM categories ORDER BY position, id"
        ).fetchall()
        return [dict(r) for r in rows]


def add_category(name: str) -> dict:
    name = name.strip()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO categories (name, position) VALUES (?, "
            "(SELECT COALESCE(MAX(position), 0) + 1 FROM categories))",
            (name,),
        )
        row = conn.execute(
            "SELECT * FROM categories WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return dict(row)


def delete_category(category_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))


# ---- transactions -----------------------------------------------------------

def add_transaction(amount_cents: int, payee: str | None,
                    raw_text: str | None, image_path: str | None) -> dict:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO transactions (amount_cents, payee, raw_text, image_path) "
            "VALUES (?, ?, ?, ?)",
            (int(amount_cents), payee, raw_text, image_path),
        )
        row = conn.execute(
            "SELECT * FROM transactions WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return dict(row)


def update_transaction(tx_id: int, *, amount_cents: int | None = None,
                       payee: str | None = None,
                       category_id: int | None = None,
                       set_category: bool = False) -> dict | None:
    sets, params = [], []
    if amount_cents is not None:
        sets.append("amount_cents = ?")
        params.append(int(amount_cents))
    if payee is not None:
        sets.append("payee = ?")
        params.append(payee)
    if set_category:
        sets.append("category_id = ?")
        params.append(category_id)
    if not sets:
        return get_transaction(tx_id)
    params.append(tx_id)
    with _connect() as conn:
        conn.execute(
            f"UPDATE transactions SET {', '.join(sets)} WHERE id = ?", params
        )
        row = conn.execute(
            "SELECT * FROM transactions WHERE id = ?", (tx_id,)
        ).fetchone()
        return dict(row) if row else None


def get_transaction(tx_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM transactions WHERE id = ?", (tx_id,)
        ).fetchone()
        return dict(row) if row else None


def delete_transaction(tx_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))


def list_unsorted() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM transactions WHERE category_id IS NULL "
            "ORDER BY created_at DESC, id DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def list_all_transactions() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT t.*, c.name AS category_name "
            "FROM transactions t LEFT JOIN categories c ON t.category_id = c.id "
            "ORDER BY t.created_at, t.id"
        ).fetchall()
        return [dict(r) for r in rows]
