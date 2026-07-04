"""SQLite storage — the single source of truth.

Exports (Excel / Markdown) and analyses are always derived from this; they are
never the source. All amounts are stored as signed integer cents
(negative = expense, positive = income).
"""

from __future__ import annotations

import sqlite3
from datetime import date
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
                amount_cents INTEGER NOT NULL,          -- signed
                payee        TEXT,
                kind         TEXT NOT NULL DEFAULT 'expense',  -- 'expense'|'income'
                category_id  INTEGER REFERENCES categories(id) ON DELETE SET NULL,
                occurred_on  TEXT,                      -- ISO date for monthly grouping
                image_path   TEXT,
                created_at   TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
            """
        )


# ---- settings ---------------------------------------------------------------

def get_setting(key: str) -> str | None:
    with _connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None


def set_setting(key: str, value: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def get_start_balance_cents() -> int:
    v = get_setting("start_balance_cents")
    return int(v) if v is not None else 0


def set_start_balance_cents(cents: int) -> None:
    set_setting("start_balance_cents", str(int(cents)))


# ---- categories -------------------------------------------------------------

def list_categories() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM categories ORDER BY position, id").fetchall()
        return [dict(r) for r in rows]


def add_category(name: str) -> dict:
    name = name.strip()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO categories (name, position) VALUES (?, "
            "(SELECT COALESCE(MAX(position), 0) + 1 FROM categories))",
            (name,),
        )
        row = conn.execute("SELECT * FROM categories WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)


def delete_category(category_id: int) -> None:
    # Expenses fall back to unsorted (ON DELETE SET NULL) so nothing is lost.
    with _connect() as conn:
        conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))


# ---- transactions -----------------------------------------------------------

def add_transaction(amount_cents: int, payee: str | None, *,
                    kind: str | None = None,
                    occurred_on: str | None = None,
                    category_id: int | None = None,
                    image_path: str | None = None) -> dict:
    if kind is None:
        kind = "income" if amount_cents > 0 else "expense"
    if occurred_on is None:
        occurred_on = date.today().isoformat()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO transactions (amount_cents, payee, kind, category_id, occurred_on, image_path) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (int(amount_cents), payee, kind, category_id, occurred_on, image_path),
        )
        row = conn.execute("SELECT * FROM transactions WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)


def update_transaction(tx_id: int, *, amount_cents: int | None = None,
                       payee: str | None = None) -> dict | None:
    sets, params = [], []
    if amount_cents is not None:
        sets.append("amount_cents = ?")
        params.append(int(amount_cents))
        # Keep kind consistent with the sign.
        sets.append("kind = ?")
        params.append("income" if amount_cents > 0 else "expense")
    if payee is not None:
        sets.append("payee = ?")
        params.append(payee)
    if not sets:
        return get_transaction(tx_id)
    params.append(tx_id)
    with _connect() as conn:
        conn.execute(f"UPDATE transactions SET {', '.join(sets)} WHERE id = ?", params)
        row = conn.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone()
        return dict(row) if row else None


def set_category(tx_id: int, category_id: int | None) -> dict | None:
    with _connect() as conn:
        conn.execute("UPDATE transactions SET category_id = ? WHERE id = ?", (category_id, tx_id))
        row = conn.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone()
        return dict(row) if row else None


def get_transaction(tx_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone()
        return dict(row) if row else None


def delete_transaction(tx_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))


def list_unsorted_expenses() -> list[dict]:
    """The cards to sort: expenses not yet assigned to a category."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM transactions "
            "WHERE kind = 'expense' AND category_id IS NULL "
            "ORDER BY created_at DESC, id DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def list_by_category(category_id: int) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM transactions WHERE category_id = ? ORDER BY occurred_on DESC, id DESC",
            (category_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def list_all_transactions() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT t.*, c.name AS category_name "
            "FROM transactions t LEFT JOIN categories c ON t.category_id = c.id "
            "ORDER BY t.occurred_on, t.id"
        ).fetchall()
        return [dict(r) for r in rows]


def sum_all_cents() -> int:
    with _connect() as conn:
        row = conn.execute("SELECT COALESCE(SUM(amount_cents), 0) AS s FROM transactions").fetchone()
        return int(row["s"])


def balance_cents() -> int:
    return get_start_balance_cents() + sum_all_cents()
