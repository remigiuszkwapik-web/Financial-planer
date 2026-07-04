"""Turn the date labels read off a banking screenshot into real ISO dates.

Deterministic, no AI. Handles German group headers like "5. Juli",
"Vorgemerkte Umsätze", "Heute", "Gestern" and "01.07.2026".
"""

from __future__ import annotations

import re
from datetime import date, timedelta

_MONTHS = {
    "januar": 1, "jan": 1, "februar": 2, "feb": 2, "märz": 3, "maerz": 3,
    "mär": 3, "mar": 3, "april": 4, "apr": 4, "mai": 5, "juni": 6, "jun": 6,
    "juli": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sep": 9,
    "sept": 9, "oktober": 10, "okt": 10, "november": 11, "nov": 11,
    "dezember": 12, "dez": 12,
}

_DAY_MONTH = re.compile(r"(\d{1,2})\.\s*([a-zäöü]+)", re.IGNORECASE)
_NUMERIC = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})")


def parse_label(label: str | None, today: date | None = None) -> str:
    """Return an ISO date string. Falls back to *today* when nothing parses."""
    today = today or date.today()
    if not label:
        return today.isoformat()
    s = label.strip().lower()

    if "vorgemerkt" in s or "heute" in s:
        return today.isoformat()
    if "gestern" in s:
        return (today - timedelta(days=1)).isoformat()

    m = _NUMERIC.search(s)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if year < 100:
            year += 2000
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return today.isoformat()

    m = _DAY_MONTH.search(s)
    if m:
        day = int(m.group(1))
        month = _MONTHS.get(m.group(2))
        if month:
            try:
                d = date(today.year, month, day)
            except ValueError:
                return today.isoformat()
            # A parsed date far in the future almost certainly belongs to last year.
            if d > today + timedelta(days=7):
                try:
                    d = date(today.year - 1, month, day)
                except ValueError:
                    pass
            return d.isoformat()

    return today.isoformat()
