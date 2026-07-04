"""Monthly analysis — deterministic, no AI.

Given the raw transactions from the database, this groups them by calendar
month and computes income, expenses, net, and the per-category expense
breakdown. It also surfaces the best month (highest net) and the month with the
strongest spending. Pure integer-cent arithmetic.
"""

from __future__ import annotations

from collections import defaultdict


def _month_key(occurred_on: str | None, created_at: str | None) -> str:
    src = occurred_on or created_at or ""
    return src[:7]  # 'YYYY-MM'


def monthly_report(transactions: list[dict]) -> dict:
    """Build the month-by-month report.

    Returns:
        {
          "months": [                       # newest first
            {
              "month": "2026-07",
              "income_cents": int,
              "expense_cents": int,          # positive magnitude
              "net_cents": int,              # income - expense
              "categories": [{"name": str, "expense_cents": int}, ...],
              "top_category": str | None,
            }, ...
          ],
          "best_month": "2026-07" | None,        # highest net
          "worst_expense_month": "2026-06" | None,  # highest spending
        }
    """
    by_month: dict[str, dict] = {}
    cat_by_month: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for tx in transactions:
        key = _month_key(tx.get("occurred_on"), tx.get("created_at"))
        if not key:
            continue
        bucket = by_month.setdefault(
            key, {"month": key, "income_cents": 0, "expense_cents": 0}
        )
        amount = int(tx["amount_cents"])
        if amount >= 0:
            bucket["income_cents"] += amount
        else:
            bucket["expense_cents"] += -amount
            name = tx.get("category_name") or "Unsortiert"
            cat_by_month[key][name] += -amount

    months = []
    for key, bucket in by_month.items():
        cats = sorted(
            ({"name": n, "expense_cents": c} for n, c in cat_by_month[key].items()),
            key=lambda x: x["expense_cents"], reverse=True,
        )
        bucket["categories"] = cats
        bucket["top_category"] = cats[0]["name"] if cats else None
        bucket["net_cents"] = bucket["income_cents"] - bucket["expense_cents"]
        months.append(bucket)

    months.sort(key=lambda b: b["month"], reverse=True)

    best_month = max(months, key=lambda b: b["net_cents"])["month"] if months else None
    worst = max(months, key=lambda b: b["expense_cents"]) if months else None
    worst_expense_month = worst["month"] if worst and worst["expense_cents"] > 0 else None

    return {
        "months": months,
        "best_month": best_month,
        "worst_expense_month": worst_expense_month,
    }


def category_totals(transactions: list[dict]) -> list[dict]:
    """Per-category expense totals across all time (for the sorting board)."""
    totals: dict[str, dict] = {}
    for tx in transactions:
        if tx.get("category_id") is None:
            continue
        name = tx.get("category_name")
        if name is None:
            continue
        b = totals.setdefault(name, {"name": name, "total_cents": 0, "count": 0})
        b["total_cents"] += int(tx["amount_cents"])
        b["count"] += 1
    return list(totals.values())
