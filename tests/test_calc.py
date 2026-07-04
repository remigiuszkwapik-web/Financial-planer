"""Tests for the deterministic money logic — no AI, exact integer arithmetic."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.amount import (  # noqa: E402
    find_amounts_in_text,
    format_cents,
    parse_amount_to_cents,
)
from backend.calc import summarize  # noqa: E402


# ---- parsing ----------------------------------------------------------------

def test_parse_german():
    assert parse_amount_to_cents("12,34") == 1234
    assert parse_amount_to_cents("1.234,56") == 123456
    assert parse_amount_to_cents("0,99") == 99


def test_parse_english():
    assert parse_amount_to_cents("12.34") == 1234
    assert parse_amount_to_cents("1,234.56") == 123456


def test_parse_whole_numbers():
    assert parse_amount_to_cents("42") == 4200
    assert parse_amount_to_cents("1.234") == 123400  # thousands, not decimal


def test_parse_single_decimal_digit():
    assert parse_amount_to_cents("5,5") == 550


def test_parse_junk():
    assert parse_amount_to_cents("") is None
    assert parse_amount_to_cents("abc") is None


def test_format_roundtrip():
    assert format_cents(1234) == "12,34"
    assert format_cents(99) == "0,99"
    assert format_cents(-500) == "-5,00"


def test_find_amounts_prefers_money_like():
    text = "Beleg 12345\nBetrag 19,99 €\nTrinkgeld 2,00"
    found = find_amounts_in_text(text)
    assert 1999 in found
    assert 200 in found
    assert 1234500 not in found  # bare integer id ignored


# ---- summation --------------------------------------------------------------

def test_summarize_groups_and_totals():
    txs = [
        {"amount_cents": 1000, "category_name": "Essen"},
        {"amount_cents": 500, "category_name": "Essen"},
        {"amount_cents": 2500, "category_name": "Miete"},
        {"amount_cents": 300, "category_name": None},
    ]
    s = summarize(txs)
    cats = {c["name"]: c for c in s["categories"]}
    assert cats["Essen"]["total_cents"] == 1500
    assert cats["Essen"]["count"] == 2
    assert cats["Miete"]["total_cents"] == 2500
    assert s["unsorted"]["total_cents"] == 300
    assert s["grand_total_cents"] == 4300


def test_summarize_sorted_by_total_desc():
    txs = [
        {"amount_cents": 100, "category_name": "A"},
        {"amount_cents": 900, "category_name": "B"},
    ]
    s = summarize(txs)
    assert [c["name"] for c in s["categories"]] == ["B", "A"]


def test_summarize_empty():
    s = summarize([])
    assert s["grand_total_cents"] == 0
    assert s["categories"] == []
