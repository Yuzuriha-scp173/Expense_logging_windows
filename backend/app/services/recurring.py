from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import Expense
from app.services.expenses import active_expenses
from app.services.money import cents_to_dollars


def detect_recurring(db: Session) -> list[dict]:
    expenses = list(db.scalars(active_expenses()).unique().all())
    groups: dict[tuple[str, int], list[Expense]] = defaultdict(list)
    for e in expenses:
        if not e.merchant:
            continue
        # Bucket similar amounts within $1
        bucket = round(e.amount_cents / 100)
        groups[(e.merchant.strip().lower(), bucket)].append(e)

    results = []
    for (merchant, _bucket), items in groups.items():
        if len(items) < 2:
            continue
        items.sort(key=lambda x: x.date)
        gaps = [(items[i].date - items[i - 1].date).days for i in range(1, len(items))]
        if not gaps:
            continue
        avg_gap = sum(gaps) / len(gaps)
        interval = None
        if 25 <= avg_gap <= 35:
            interval = "monthly"
        elif 6 <= avg_gap <= 8:
            interval = "weekly"
        elif 13 <= avg_gap <= 16:
            interval = "biweekly"
        elif 85 <= avg_gap <= 95:
            interval = "quarterly"
        elif 350 <= avg_gap <= 380:
            interval = "yearly"
        if interval is None:
            continue
        typical = round(sum(i.amount_cents for i in items) / len(items))
        monthly = typical
        if interval == "weekly":
            monthly = typical * 4
        elif interval == "biweekly":
            monthly = typical * 2
        elif interval == "quarterly":
            monthly = typical // 3
        elif interval == "yearly":
            monthly = typical // 12
        results.append(
            {
                "merchant": items[-1].merchant,
                "typical_cents": typical,
                "typical": str(cents_to_dollars(typical)),
                "interval": interval,
                "count": len(items),
                "last_seen": items[-1].date.isoformat(),
                "monthly_cents": monthly,
                "annual_cents": monthly * 12,
                "monthly": str(cents_to_dollars(monthly)),
                "annual": str(cents_to_dollars(monthly * 12)),
                "category": items[-1].category.name if items[-1].category else "Other",
                "likely": True,
            }
        )
    results.sort(key=lambda r: r["monthly_cents"], reverse=True)
    return results
