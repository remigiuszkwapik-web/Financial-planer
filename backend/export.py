"""Export the ledger to Excel (.xlsx) or Markdown (.md).

Both formats are generated from the same deterministic data, so they always
agree with each other and with the app. Exports are output, never the source.
"""

from __future__ import annotations

import io

from .amount import format_cents
from .analysis import monthly_report


def _sorted_expense_totals(transactions: list[dict]) -> list[dict]:
    totals: dict[str, dict] = {}
    for tx in transactions:
        if tx.get("category_id") is None or int(tx["amount_cents"]) >= 0:
            continue
        name = tx.get("category_name") or "Unsortiert"
        b = totals.setdefault(name, {"name": name, "total_cents": 0, "count": 0})
        b["total_cents"] += -int(tx["amount_cents"])
        b["count"] += 1
    return sorted(totals.values(), key=lambda x: x["total_cents"], reverse=True)


def to_markdown(transactions: list[dict], balance_cents: int = 0) -> str:
    report = monthly_report(transactions)
    lines: list[str] = ["# Finanzübersicht", ""]
    lines.append(f"**Kontostand:** {format_cents(balance_cents)} €\n")

    lines.append("## Ausgaben pro Kategorie\n")
    lines.append("| Kategorie | Anzahl | Ausgaben |")
    lines.append("| --- | ---: | ---: |")
    for c in _sorted_expense_totals(transactions):
        lines.append(f"| {c['name']} | {c['count']} | {format_cents(c['total_cents'])} |")

    lines.append("\n## Monatsübersicht\n")
    lines.append("| Monat | Einnahmen | Ausgaben | Netto | Größter Posten |")
    lines.append("| --- | ---: | ---: | ---: | --- |")
    for m in report["months"]:
        lines.append(
            f"| {m['month']} | {format_cents(m['income_cents'])} "
            f"| {format_cents(m['expense_cents'])} | {format_cents(m['net_cents'])} "
            f"| {m['top_category'] or '—'} |"
        )
    if report["best_month"]:
        lines.append(f"\n- **Bester Monat (Netto):** {report['best_month']}")
    if report["worst_expense_month"]:
        lines.append(f"- **Höchste Ausgaben:** {report['worst_expense_month']}")

    return "\n".join(lines) + "\n"


def to_xlsx(transactions: list[dict], balance_cents: int = 0) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    report = monthly_report(transactions)
    wb = Workbook()

    ws = wb.active
    ws.title = "Übersicht"
    ws.append(["Kontostand (€)", balance_cents / 100])
    ws["A1"].font = Font(bold=True)
    ws.append([])
    ws.append(["Kategorie", "Anzahl", "Ausgaben (€)"])
    for c in ws[3]:
        c.font = Font(bold=True)
    for c in _sorted_expense_totals(transactions):
        ws.append([c["name"], c["count"], c["total_cents"] / 100])

    wm = wb.create_sheet("Monate")
    wm.append(["Monat", "Einnahmen (€)", "Ausgaben (€)", "Netto (€)", "Größter Posten"])
    for c in wm[1]:
        c.font = Font(bold=True)
    for m in report["months"]:
        wm.append([
            m["month"], m["income_cents"] / 100, m["expense_cents"] / 100,
            m["net_cents"] / 100, m["top_category"] or "",
        ])

    wt = wb.create_sheet("Buchungen")
    wt.append(["Datum", "Kategorie", "Empfänger", "Betrag (€)"])
    for c in wt[1]:
        c.font = Font(bold=True)
    for tx in transactions:
        wt.append([
            (tx.get("occurred_on") or (tx.get("created_at") or "")[:10]),
            tx.get("category_name") or ("Einnahme" if int(tx["amount_cents"]) > 0 else ""),
            tx.get("payee") or "",
            tx["amount_cents"] / 100,
        ])

    for sheet in (ws, wm, wt):
        for col in sheet.columns:
            width = max((len(str(c.value)) if c.value is not None else 0) for c in col)
            sheet.column_dimensions[col[0].column_letter].width = max(12, width + 2)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
