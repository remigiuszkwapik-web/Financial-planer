"""Screenshot extraction — the ONLY 'reading from image' step.

A single screenshot of a banking app usually lists MANY transactions. This
module reads the text and parses every transaction row into its own record:
{amount_cents (signed), payee, date_label}. It does no categorization and no
math.

Discriminator that makes this robust: in a banking statement every transaction
amount carries an explicit sign ("-13,80", "+16,95"), while noise like the
account balance ("1.697,14 EUR") does not. So we only accept signed amounts.

If Tesseract is not installed, extraction returns an empty list and the user
adds rows by hand. To swap in another engine later, keep the same return shape.
"""

from __future__ import annotations

import io
import re

from .amount import parse_amount_to_cents

# A transaction amount: explicit sign, then a German-formatted number.
_SIGNED_AMOUNT = re.compile(r"([+\-−])\s?(\d{1,3}(?:[.\s]\d{3})*,\d{2})")

# Date group headers in the statement ("5. Juli", "Vorgemerkte Umsätze", ...).
_MONTHS = (
    "januar|februar|märz|maerz|april|mai|juni|juli|august|september|"
    "oktober|november|dezember|jan|feb|mär|mar|apr|jun|jul|aug|sep|okt|nov|dez"
)
_DATE_HEADER = re.compile(
    rf"(vorgemerkt\w*|heute|gestern|\b\d{{1,2}}\.\s*(?:{_MONTHS})\b"
    rf"|\b\d{{1,2}}\.\d{{1,2}}\.\d{{2,4}}\b)",
    re.IGNORECASE,
)

# Lines that are never transactions (nav bar, headers, balance labels).
_SKIP_LINE = re.compile(
    r"^(eur|umsätze|umsatze|meine konten|girokonto|geld senden|vorschau|"
    r"karten|wero|konten|aufträge|auftrage|investieren|produkte|service|"
    r"\d{1,2}:\d{2}|lte|de\d{2}\b)",
    re.IGNORECASE,
)


def _ocr_text(image_bytes: bytes) -> str:
    """Run OCR, or return '' if the OCR stack is unavailable."""
    try:
        import pytesseract
        from PIL import Image
    except Exception:
        return ""
    for lang in ("deu+eng", None):
        try:
            img = Image.open(io.BytesIO(image_bytes))
            return pytesseract.image_to_string(img, lang=lang) if lang \
                else pytesseract.image_to_string(img)
        except Exception:
            continue
    return ""


def _clean_payee(text: str) -> str:
    """Tidy the left-hand text of a row into a payee label."""
    s = re.sub(r"\s{2,}", " ", text).strip(" \t·|-–—")
    # Drop a leading transaction-type prefix that carries no info on its own.
    s = re.sub(r"^(visa|master(card)?|paypal|lastschrift|dauerauftrag)\s+",
               "", s, flags=re.IGNORECASE).strip()
    return s[:80]


def parse_transactions(text: str) -> list[dict]:
    """Parse OCR text into a list of transaction rows.

    Returns records shaped like:
        {"amount_cents": int (signed), "payee": str|None, "date_label": str|None}
    """
    rows: list[dict] = []
    current_date: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        header = _DATE_HEADER.search(line)
        # A pure date header (no amount on it) just updates the running date.
        if header and not _SIGNED_AMOUNT.search(line):
            current_date = header.group(0).strip()
            continue

        if _SKIP_LINE.match(line):
            continue

        matches = list(_SIGNED_AMOUNT.finditer(line))
        if not matches:
            continue

        m = matches[-1]  # rightmost = the transaction amount column
        cents = parse_amount_to_cents(m.group(2))
        if cents is None:
            continue
        sign = -1 if m.group(1) in "-−" else 1

        payee = _clean_payee(line[: m.start()])
        rows.append({
            "amount_cents": sign * cents,
            "payee": payee or None,
            "date_label": current_date,
        })

    return rows


def extract(image_bytes: bytes) -> dict:
    """Return {'transactions': [ ... ], 'raw_text': str} for one screenshot."""
    text = _ocr_text(image_bytes)
    return {"transactions": parse_transactions(text), "raw_text": text}


def ocr_available() -> bool:
    try:
        import pytesseract
        from PIL import Image  # noqa: F401

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False
