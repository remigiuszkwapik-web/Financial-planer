"""Deterministic money parsing and formatting.

Money is stored everywhere as integer cents so that all arithmetic is exact.
No floating point is used for storage or summation. This module is the single
place that knows how to turn text into cents and back — no AI, just rules.
"""

from __future__ import annotations

import re

# A monetary token: optional currency, groups of digits with . or , separators.
# Examples matched: "12,34", "1.234,56", "1,234.56", "12.34", "€ 9,99", "1234"
_MONEY_RE = re.compile(
    r"""
    (?P<cur>[€$£]|EUR|USD|GBP)?      # optional leading currency
    \s*
    (?P<num>\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)
    \s*
    (?P<cur2>[€$£]|EUR|USD|GBP)?     # optional trailing currency
    """,
    re.VERBOSE | re.IGNORECASE,
)


def parse_amount_to_cents(text: str) -> int | None:
    """Parse a single number string into integer cents.

    Handles both German (1.234,56) and English (1,234.56) grouping by treating
    the *last* separator as the decimal point. Returns None if nothing parses.
    """
    if text is None:
        return None
    raw = text.strip()
    if not raw:
        return None

    # Keep only digits and separators.
    cleaned = re.sub(r"[^\d.,]", "", raw)
    if not cleaned or not re.search(r"\d", cleaned):
        return None

    last_dot = cleaned.rfind(".")
    last_comma = cleaned.rfind(",")
    dec_pos = max(last_dot, last_comma)

    if dec_pos == -1:
        # No separator at all -> whole units.
        return int(cleaned) * 100

    dec_sep = cleaned[dec_pos]
    int_part = cleaned[:dec_pos]
    frac_part = cleaned[dec_pos + 1:]

    # If the "decimal" part is exactly 3 digits and the separator also appears
    # earlier, it's a thousands separator, not a decimal point (e.g. "1.234").
    if len(frac_part) == 3 and dec_sep in int_part:
        int_part = (int_part + frac_part).replace(".", "").replace(",", "")
        frac_part = ""
    elif len(frac_part) == 3 and cleaned.count(dec_sep) == 1 and not re.search(r"[.,]", int_part):
        # e.g. "1.234" with nothing else -> ambiguous; treat as thousands.
        int_part = int_part + frac_part
        frac_part = ""

    int_digits = re.sub(r"[^\d]", "", int_part) or "0"
    frac_digits = re.sub(r"[^\d]", "", frac_part)

    if len(frac_digits) == 1:
        frac_digits += "0"
    elif len(frac_digits) == 0:
        frac_digits = "00"
    elif len(frac_digits) > 2:
        frac_digits = frac_digits[:2]

    return int(int_digits) * 100 + int(frac_digits)


def find_amounts_in_text(text: str) -> list[int]:
    """Return all monetary amounts (in cents) found in a block of text."""
    results: list[int] = []
    for m in _MONEY_RE.finditer(text):
        has_currency = bool(m.group("cur") or m.group("cur2"))
        cents = parse_amount_to_cents(m.group("num"))
        if cents is None:
            continue
        # Bare integers with no currency and no decimals are noisy (dates, ids).
        num = m.group("num")
        looks_like_money = has_currency or ("," in num) or ("." in num)
        if looks_like_money:
            results.append(cents)
    return results


def format_cents(cents: int) -> str:
    """Format integer cents as a German-style decimal string, e.g. 1234 -> '12,34'."""
    sign = "-" if cents < 0 else ""
    cents = abs(int(cents))
    return f"{sign}{cents // 100},{cents % 100:02d}"
