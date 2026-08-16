from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category, Expense
from app.services.dates import month_bounds, previous_month, shift_month
from app.services.money import cents_to_dollars, percent_change
from app.services.expenses import active_expenses


def _month_filter(year: int, month: int):
    start, end = month_bounds(year, month)
    return Expense.date >= start, Expense.date <= end, start, end


def month_expenses(db: Session, year: int, month: int) -> list[Expense]:
    start, end = month_bounds(year, month)
    stmt = (
        active_expenses()
        .where(Expense.date >= start, Expense.date <= end)
        .order_by(Expense.date.desc(), Expense.id.desc())
    )
    return list(db.scalars(stmt).unique().all())


def sum_cents(expenses: list[Expense]) -> int:
    return sum(e.amount_cents for e in expenses)


def monthly_summary(db: Session, year: int, month: int) -> dict:
    expenses = month_expenses(db, year, month)
    total = sum_cents(expenses)
    count = len(expenses)
    start, end = month_bounds(year, month)
    days_in_month = (end - start).days + 1
    today = date.today()
    if year == today.year and month == today.month:
        days_elapsed = max(today.day, 1)
    elif date(year, month, 1) > today:
        days_elapsed = 0
    else:
        days_elapsed = days_in_month

    largest = max(expenses, key=lambda e: e.amount_cents) if expenses else None
    by_category: dict[str, int] = defaultdict(int)
    by_merchant: dict[str, int] = defaultdict(int)
    for e in expenses:
        name = e.category.name if e.category else "Other"
        by_category[name] += e.amount_cents
        merchant = e.merchant or "Unknown"
        by_merchant[merchant] += e.amount_cents

    top_category = max(by_category.items(), key=lambda kv: kv[1]) if by_category else None
    top_merchant = max(by_merchant.items(), key=lambda kv: kv[1]) if by_merchant else None

    prev_y, prev_m = previous_month(year, month)
    prev_total = sum_cents(month_expenses(db, prev_y, prev_m))
    change = percent_change(total, prev_total)

    return {
        "year": year,
        "month": month,
        "label": date(year, month, 1).strftime("%B %Y"),
        "total_cents": total,
        "total": str(cents_to_dollars(total)),
        "count": count,
        "average_cents": (total // count) if count else 0,
        "average": str(cents_to_dollars(total // count if count else 0)),
        "average_daily_cents": (total // days_elapsed) if days_elapsed else 0,
        "average_daily": str(cents_to_dollars(total // days_elapsed if days_elapsed else 0)),
        "days_elapsed": days_elapsed,
        "largest": _expense_brief(largest) if largest else None,
        "top_category": {"name": top_category[0], "cents": top_category[1]} if top_category else None,
        "top_merchant": {"name": top_merchant[0], "cents": top_merchant[1]} if top_merchant else None,
        "vs_last_month_cents": total - prev_total,
        "vs_last_month_percent": str(change) if change is not None else None,
        "previous_month_total_cents": prev_total,
        "previous_month_label": date(prev_y, prev_m, 1).strftime("%B %Y"),
    }


def category_breakdown(db: Session, year: int, month: int) -> list[dict]:
    expenses = month_expenses(db, year, month)
    total = sum_cents(expenses)
    buckets: dict[str, int] = defaultdict(int)
    for e in expenses:
        buckets[e.category.name if e.category else "Other"] += e.amount_cents
    rows = []
    for name, cents in sorted(buckets.items(), key=lambda kv: kv[1], reverse=True):
        pct = (Decimal(cents) / Decimal(total) * 100) if total else Decimal(0)
        rows.append(
            {
                "category": name,
                "cents": cents,
                "amount": str(cents_to_dollars(cents)),
                "percent": float(pct.quantize(Decimal("0.1"))),
            }
        )
    return rows


def daily_spending(db: Session, year: int, month: int) -> list[dict]:
    start, end = month_bounds(year, month)
    expenses = month_expenses(db, year, month)
    by_day: dict[str, int] = defaultdict(int)
    for e in expenses:
        by_day[e.date.isoformat()] += e.amount_cents
    rows = []
    cumulative = 0
    cursor = start
    while cursor <= end:
        key = cursor.isoformat()
        cents = by_day.get(key, 0)
        cumulative += cents
        rows.append(
            {
                "date": key,
                "cents": cents,
                "amount": str(cents_to_dollars(cents)),
                "cumulative_cents": cumulative,
                "cumulative": str(cents_to_dollars(cumulative)),
            }
        )
        cursor = cursor.fromordinal(cursor.toordinal() + 1)
    return rows


def monthly_trend(db: Session, year: int, month: int, months: int = 6) -> list[dict]:
    start_year, start_month = shift_month(year, month, -(months - 1))
    rows = []
    y, m = start_year, start_month
    for _ in range(months):
        total = sum_cents(month_expenses(db, y, m))
        rows.append(
            {
                "year": y,
                "month": m,
                "key": f"{y:04d}-{m:02d}",
                "label": date(y, m, 1).strftime("%b %Y"),
                "cents": total,
                "amount": str(cents_to_dollars(total)),
            }
        )
        y, m = shift_month(y, m, 1)
    return rows


def category_month_compare(db: Session, year: int, month: int) -> list[dict]:
    current = {row["category"]: row["cents"] for row in category_breakdown(db, year, month)}
    py, pm = previous_month(year, month)
    previous = {row["category"]: row["cents"] for row in category_breakdown(db, py, pm)}
    names = sorted(set(current) | set(previous), key=lambda n: current.get(n, 0), reverse=True)
    rows = []
    for name in names:
        cur = current.get(name, 0)
        prev = previous.get(name, 0)
        change = percent_change(cur, prev)
        rows.append(
            {
                "category": name,
                "current_cents": cur,
                "previous_cents": prev,
                "delta_cents": cur - prev,
                "percent": str(change) if change is not None else None,
            }
        )
    return rows


def _expense_brief(expense: Expense) -> dict:
    return {
        "id": expense.id,
        "amount_cents": expense.amount_cents,
        "amount": str(cents_to_dollars(expense.amount_cents)),
        "merchant": expense.merchant,
        "description": expense.description,
        "category": expense.category.name if expense.category else "Other",
        "date": expense.date.isoformat(),
    }


def dashboard_payload(db: Session, year: int, month: int) -> dict:
    expenses = month_expenses(db, year, month)
    recent = expenses[:8]
    return {
        "summary": monthly_summary(db, year, month),
        "categories": category_breakdown(db, year, month),
        "daily": daily_spending(db, year, month),
        "trend": monthly_trend(db, year, month),
        "category_compare": category_month_compare(db, year, month),
        "recent": [
            {
                "id": e.id,
                "date": e.date.isoformat(),
                "merchant": e.merchant,
                "description": e.description,
                "category": e.category.name if e.category else "Other",
                "amount_cents": e.amount_cents,
                "amount": str(cents_to_dollars(e.amount_cents)),
                "subcategory": e.subcategory,
            }
            for e in recent
        ],
        "empty": len(expenses) == 0,
    }


def history_payload(db: Session, year: int, month: int, months: int = 12) -> dict:
    start_year, start_month = shift_month(year, month, -(months - 1))
    chronological: list[dict] = []
    y, m = start_year, start_month
    for _ in range(months):
        summary = monthly_summary(db, y, m)
        chronological.append(
            {
                "key": f"{y:04d}-{m:02d}",
                "label": date(y, m, 1).strftime("%B %Y"),
                "short_label": date(y, m, 1).strftime("%b"),
                "year": y,
                "month": m,
                "total_cents": summary["total_cents"],
                "count": summary["count"],
                "average_cents": summary["average_cents"],
                "top_category": summary["top_category"],
                "top_merchant": summary["top_merchant"],
                "largest": summary["largest"],
                "vs_last_month_cents": summary["vs_last_month_cents"],
                "vs_last_month_percent": summary["vs_last_month_percent"],
                "categories": category_breakdown(db, y, m),
            }
        )
        y, m = shift_month(y, m, 1)

    total = sum(item["total_cents"] for item in chronological)
    count = sum(item["count"] for item in chronological)
    spent = [item for item in chronological if item["total_cents"] > 0]
    peak = max(spent, key=lambda item: item["total_cents"]) if spent else None
    start_label = chronological[0]["label"] if chronological else ""
    end_label = chronological[-1]["label"] if chronological else ""
    return {
        "chart": chronological,
        "months": list(reversed(chronological)),
        "range_total_cents": total,
        "range_count": count,
        "peak": peak,
        "months_count": months,
        "start_label": start_label,
        "end_label": end_label,
    }


def category_total_cents(db: Session, year: int, month: int, category_name: str) -> int:
    start, end = month_bounds(year, month)
    stmt = (
        select(func.coalesce(func.sum(Expense.amount_cents), 0))
        .join(Category)
        .where(
            Expense.deleted_at.is_(None),
            Expense.date >= start,
            Expense.date <= end,
            Category.name == category_name,
        )
    )
    return int(db.scalar(stmt) or 0)


def merchant_total_cents(
    db: Session,
    merchant: str,
    start: date | None = None,
    end: date | None = None,
) -> tuple[int, int]:
    stmt = select(func.coalesce(func.sum(Expense.amount_cents), 0), func.count()).where(
        Expense.deleted_at.is_(None),
        Expense.merchant.ilike(f"%{merchant}%"),
    )
    if start:
        stmt = stmt.where(Expense.date >= start)
    if end:
        stmt = stmt.where(Expense.date <= end)
    total, count = db.execute(stmt).one()
    return int(total or 0), int(count or 0)
