from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.analytics import category_breakdown, category_month_compare, monthly_summary, month_expenses
from app.services.money import cents_to_dollars, format_dollars


def build_insights(db: Session, year: int, month: int) -> list[dict]:
    summary = monthly_summary(db, year, month)
    insights: list[dict] = []
    if summary["count"] == 0:
        return [
            {
                "id": "empty",
                "text": f"No expenses yet in {summary['label']}. Add your first expense.",
            }
        ]

    compare = category_month_compare(db, year, month)
    for row in compare:
        if row["previous_cents"] == 0 or row["delta_cents"] == 0:
            continue
        direction = "increased" if row["delta_cents"] > 0 else "decreased"
        pct = row["percent"]
        delta = format_dollars(abs(row["delta_cents"]))
        insights.append(
            {
                "id": f"cat-{row['category']}",
                "text": f"{row['category']} {direction} {pct}% compared with last month ({delta}).",
            }
        )

    categories = category_breakdown(db, year, month)
    total = summary["total_cents"]
    for row in categories:
        if total and row["percent"] >= 8:
            insights.append(
                {
                    "id": f"share-{row['category']}",
                    "text": f"{row['category']} represents {row['percent']}% of total spending.",
                }
            )

    expenses = month_expenses(db, year, month)
    under_10 = [e for e in expenses if e.amount_cents < 1000]
    if under_10:
        insights.append(
            {
                "id": "small",
                "text": f"You made {len(under_10)} purchase{'s' if len(under_10) != 1 else ''} under $10.",
            }
        )

    if summary["top_merchant"] and summary["top_merchant"]["name"] != "Unknown":
        insights.append(
            {
                "id": "merchant",
                "text": (
                    f"Top merchant was {summary['top_merchant']['name']} at "
                    f"{format_dollars(summary['top_merchant']['cents'])}."
                ),
            }
        )

    return insights[:8]


def monthly_narrative(db: Session, year: int, month: int) -> dict:
    summary = monthly_summary(db, year, month)
    insights = build_insights(db, year, month)
    lines = [
        f"{summary['label']} Summary",
        "",
        f"You spent {format_dollars(summary['total_cents'])} this month.",
    ]
    if summary["top_category"]:
        lines.append(
            f"Your largest category was {summary['top_category']['name']} at "
            f"{format_dollars(summary['top_category']['cents'])}."
        )
    if summary["largest"]:
        who = summary["largest"]["merchant"] or summary["largest"]["description"] or "an expense"
        lines.append(
            f"Your largest individual expense was {format_dollars(summary['largest']['amount_cents'])} ({who})."
        )
    lines.append(f"You logged {summary['count']} transaction{'s' if summary['count'] != 1 else ''}.")
    extra = [i["text"] for i in insights if not i["id"].startswith("share-")][:3]
    body = "\n".join(lines + ([""] + extra if extra else []))
    return {"label": summary["label"], "text": body, "summary": summary, "insights": insights}
