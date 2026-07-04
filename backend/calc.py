"""Deterministic calculations. NO AI, NO floating point.

Given the raw transactions from the database, this computes the totals per
category and the grand total, all in integer cents. This is the module that
'does the money' — plain, testable arithmetic.
"""

from __future__ import annotations


def summarize(transactions: list[dict]) -> dict:
    """Sum transactions per category.

    Returns:
        {
          "categories": [{"name": str, "total_cents": int, "count": int}, ...],
          "unsorted":  {"total_cents": int, "count": int},
          "grand_total_cents": int,
        }
    Sorted-out (categorized) transactions and unsorted ones are reported
    separately; grand_total covers everything.
    """
    per_cat: dict[str, dict] = {}
    unsorted_total = 0
    unsorted_count = 0
    grand_total = 0

    for tx in transactions:
        amount = int(tx["amount_cents"])
        grand_total += amount
        name = tx.get("category_name")
        if name is None:
            unsorted_total += amount
            unsorted_count += 1
        else:
            bucket = per_cat.setdefault(
                name, {"name": name, "total_cents": 0, "count": 0}
            )
            bucket["total_cents"] += amount
            bucket["count"] += 1

    categories = sorted(
        per_cat.values(), key=lambda b: b["total_cents"], reverse=True
    )
    return {
        "categories": categories,
        "unsorted": {"total_cents": unsorted_total, "count": unsorted_count},
        "grand_total_cents": grand_total,
    }
