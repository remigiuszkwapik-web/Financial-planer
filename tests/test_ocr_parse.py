"""Tests for parsing a banking-app statement into individual transactions.

The sample text mirrors an ING Girokonto screenshot: many rows, signed amounts,
date group headers, and noise (balance, nav bar) that must be ignored.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.ocr import parse_transactions  # noqa: E402

SAMPLE = """\
16:07  LTE
Meine Konten   Girokonto
Girokonto
DE27 5001 0517 5435 5345 83   1.697,14 EUR
Geld senden   Vorschau   Karten   Wero
Vorgemerkte Umsätze   EUR
CASUALFOOD 2120 2   Frankfurt am   -13,80
6213 DB HH-Airport   Hamburg   -2,20
Warner Bros. Studios   London   +16,95
5. Juli   EUR
Tetiana Lomakina   -400,00
2. Juli   EUR
VISA WARNER BROS. STUDIOS   +16,96
VISA WARNER BROS. STUDIOS   +0,34
VISA DONER TIME   -8,50
VISA BUDNIKOWSKY FIL. 288   -3,79
1. Juli   EUR
VISA KAUFLAND HAMBURG BRAMF   -27,19
VISA SUMUP *HAUS5 SERVICE   -8,30
Konten   Aufträge   Investieren   Produkte   Service
"""


def test_row_count():
    rows = parse_transactions(SAMPLE)
    assert len(rows) == 10  # exactly the 10 transactions, no balance/nav noise


def test_balance_not_parsed_as_transaction():
    amounts = [r["amount_cents"] for r in parse_transactions(SAMPLE)]
    assert 169714 not in amounts  # the unsigned balance must be ignored


def test_signs_and_values():
    rows = parse_transactions(SAMPLE)
    by_amount = [r["amount_cents"] for r in rows]
    assert -1380 in by_amount   # CASUALFOOD
    assert -220 in by_amount    # DB HH-Airport
    assert 1695 in by_amount    # Warner Bros (income, positive)
    assert -40000 in by_amount  # Tetiana Lomakina
    assert -2719 in by_amount   # KAUFLAND


def test_payee_prefix_stripped():
    rows = parse_transactions(SAMPLE)
    payees = [(r["payee"] or "") for r in rows]
    # "VISA " prefix removed, merchant kept.
    assert any(p.startswith("DONER TIME") for p in payees)
    assert not any(p.startswith("VISA") for p in payees)


def test_date_labels_flow_down():
    rows = parse_transactions(SAMPLE)
    tetiana = next(r for r in rows if (r["payee"] or "").startswith("Tetiana"))
    assert tetiana["date_label"] == "5. Juli"
