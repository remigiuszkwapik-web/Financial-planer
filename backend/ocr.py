"""Screenshot extraction module — the ONLY 'reading from image' step.

This is intentionally a small, swappable module. It reads the text off a
screenshot and picks a best-guess amount and payee. It does no categorization
and no math. If Tesseract is not installed, it degrades gracefully to empty
values so the user can type them by hand.

To swap in a different engine later (e.g. a fully-local vision model), just
provide another `extract()` with the same return shape.
"""

from __future__ import annotations

import io
import re

from .amount import find_amounts_in_text, parse_amount_to_cents

# Words that hint a line is the recipient/merchant rather than noise.
_NOISE_LINE = re.compile(
    r"^(uhr|datum|date|time|iban|bic|ref|referenz|beleg|betrag|amount|total|"
    r"summe|mwst|ust|\d{1,2}[:.]\d{2}|\d{1,2}[./]\d{1,2}[./]\d{2,4})",
    re.IGNORECASE,
)


def _ocr_text(image_bytes: bytes) -> str:
    """Run OCR, or return '' if the OCR stack is unavailable."""
    try:
        import pytesseract
        from PIL import Image
    except Exception:
        return ""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        return pytesseract.image_to_string(img, lang="deu+eng")
    except Exception:
        # Fall back to English-only if the German data pack is missing.
        try:
            import pytesseract
            from PIL import Image

            img = Image.open(io.BytesIO(image_bytes))
            return pytesseract.image_to_string(img)
        except Exception:
            return ""


def _guess_amount(text: str) -> int | None:
    amounts = find_amounts_in_text(text)
    if not amounts:
        return None
    # Heuristic: the largest monetary value on the screenshot is usually the
    # total. The user can always correct it on the card.
    return max(amounts)


def _guess_payee(text: str) -> str | None:
    for line in text.splitlines():
        s = line.strip()
        if len(s) < 3:
            continue
        if _NOISE_LINE.match(s):
            continue
        # Skip lines that are mostly digits/punctuation (amounts, dates, ids).
        letters = sum(c.isalpha() for c in s)
        if letters < 3 or letters < len(s) * 0.4:
            continue
        return s[:80]
    return None


def extract(image_bytes: bytes) -> dict:
    """Return {'amount_cents': int|None, 'payee': str|None, 'raw_text': str}."""
    text = _ocr_text(image_bytes)
    return {
        "amount_cents": _guess_amount(text),
        "payee": _guess_payee(text),
        "raw_text": text,
    }


def ocr_available() -> bool:
    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401

        import pytesseract as _pt

        _pt.get_tesseract_version()
        return True
    except Exception:
        return False
