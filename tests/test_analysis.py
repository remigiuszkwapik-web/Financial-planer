"""Tests for the deterministic monthly analysis and the date parser."""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.analysis import category_totals, monthly_report  # noqa: E402
from backend.dates import parse_label  # noqa: E402


# ---- date parsing -----------------------------------------------------------

def test_parse_day_month():
    assert parse_label("5. Juli", today=date(2026, 7, 10)) == "2026-07-05"


def test_parse_future_rolls_back_a_year():
    # "20. Dezember" seen in July belongs to the previous December.
    assert parse_label("20. Dezember", today=date(2026, 7, 10)) == "2025-12-20"


def test_parse_keywords():
    t = date(2026, 7, 10)
    assert parse_label("Vorgemerkte Umsätze", today=t) == "2026-07-10"
    assert parse_label("Gestern", today=t) == "2026-07-09"


def test_parse_numeric():
    assert parse_label("01.07.2026") == "2026-07-01"


def test_parse_fallback_today():
    t = date(2026, 7, 10)
    assert parse_label(None, today=t) == "2026-07-10"
    assert parse_label("kein datum", today=t) == "2026-07-10"


# ---- monthly report ---------------------------------------------------------

SAMPLE = [
    {"amount_cents": -1380, "occurred_on": "2026-07-05", "category_name": "Essen", "category_id": 1},
    {"amount_cents": -850,  "occurred_on": "2026-07-20", "category_name": "Essen", "category_id": 1},
    {"amount_cents": -4000, "occurred_on": "2026-07-02", "category_name": "Reise", "category_id": 2},
    {"amount_cents": 200000, "occurred_on": "2026-07-01", "category_name": None, "category_id": None},
    {"amount_cents": -2000, "occurred_on": "2026-06-15", "category_name": "Essen", "category_id": 1},
]


def test_month_grouping_and_totals():
    rep = monthly_report(SAMPLE)
    months = {m["month"]: m for m in rep["months"]}
    assert months["2026-07"]["expense_cents"] == 1380 + 850 + 4000
    assert months["2026-07"]["income_cents"] == 200000
    assert months["2026-07"]["net_cents"] == 200000 - (1380 + 850 + 4000)
    assert months["2026-06"]["expense_cents"] == 2000


def test_months_sorted_newest_first():
    rep = monthly_report(SAMPLE)
    assert [m["month"] for m in rep["months"]] == ["2026-07", "2026-06"]


def test_top_category_and_extremes():
    rep = monthly_report(SAMPLE)
    jul = next(m for m in rep["months"] if m["month"] == "2026-07")
    assert jul["top_category"] == "Reise"  # 4000 is the biggest single expense
    assert rep["best_month"] == "2026-07"  # positive net from the income
    assert rep["worst_expense_month"] == "2026-07"


def test_category_totals_expenses_only():
    totals = {t["name"]: t for t in category_totals(SAMPLE)}
    assert totals["Essen"]["total_cents"] == -(1380 + 850 + 2000)
    assert totals["Essen"]["count"] == 3
    assert "Reise" in totals


def test_empty_report():
    rep = monthly_report([])
    assert rep["months"] == []
    assert rep["best_month"] is None
    assert rep["worst_expense_month"] is None
