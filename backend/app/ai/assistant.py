from __future__ import annotations

import json
import re
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.providers import client_from_settings
from app.config import get_settings
from app.models import Category, Expense
from app.seed import get_setting
from app.services.analytics import (
    category_breakdown,
    category_total_cents,
    merchant_total_cents,
    month_expenses,
    monthly_summary,
    monthly_trend,
)
from app.services.dates import month_bounds, parse_month_key, previous_month, resolve_expense_date, today_in_tz
from app.services.expenses import active_expenses
from app.services.money import cents_to_dollars, format_dollars

INTENT_PROMPT = """Extract a query intent against a personal expense database.
Return ONLY JSON:
{
  "intent": "monthly_total" | "category_spend" | "merchant_spend" | "top_category" | "top_merchant" | "largest_expenses" | "month_compare" | "over_amount" | "unknown",
  "month": "YYYY-MM" or null,
  "year": number or null,
  "category": string or null,
  "merchant": string or null,
  "min_amount": number or null,
  "limit": number or null
}
Use DATE_TODAY as today. Do not compute totals. Only extract intent.
Categories: Food & Dining, Groceries, Transportation, Shopping, Entertainment, Housing, Utilities, Subscriptions, Education, Health, Travel, Personal Care, Gifts, Bills, Insurance, Pets, Other.
"""


def answer_question(db: Session, question: str, timezone: str | None = None) -> dict:
    tz = timezone or get_setting(db, "timezone", "America/Chicago")
    today = today_in_tz(tz)
    intent = extract_intent(question, today)
    result = execute_intent(db, intent, today)
    explanation = explain(intent, result, question)
    return {
        "question": question,
        "intent": intent.get("intent", "unknown"),
        "explanation": explanation,
        "result": result,
        "used_llm": bool(intent.get("from_llm")),
    }


def extract_intent(question: str, today: date) -> dict:
    settings = get_settings()
    client = client_from_settings(settings, settings.ai_provider)
    if client is not None and settings.ai_provider not in {"fallback", "", "none"}:
        try:
            raw = client.complete_json(
                INTENT_PROMPT.replace("DATE_TODAY", today.isoformat()),
                f"Today is {today.isoformat()}. Question: {question}",
            )
            data = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(data, dict) and data.get("intent"):
                data["from_llm"] = True
                return data
        except Exception:
            pass
    return heuristic_intent(question, today)


def heuristic_intent(question: str, today: date) -> dict:
    q = question.lower()
    intent = "unknown"
    category = _match_category(q)
    merchant = _match_merchant(q)
    limit = 5 if "five" in q or "5 " in q or "largest" in q else None
    min_amount = None
    m = re.search(r"over \$?(\d+(?:\.\d+)?)", q)
    if m:
        min_amount = float(m.group(1))
        intent = "over_amount"

    if any(w in q for w in ["compare", "than", "vs", "versus", "more did i spend"]):
        intent = "month_compare"
    elif "top category" in q or "biggest category" in q or "largest category" in q:
        intent = "top_category"
    elif "merchant" in q and any(w in q for w in ["most", "top", "biggest"]):
        intent = "top_merchant"
    elif "largest" in q or "biggest expense" in q:
        intent = "largest_expenses"
    elif merchant:
        intent = "merchant_spend"
    elif category or "eating out" in q or "food" in q:
        intent = "category_spend"
        if "eating out" in q or ("food" in q and "grocer" not in q):
            category = category or "Food & Dining"
    elif "how much" in q or "spend" in q or "spent" in q:
        intent = "monthly_total"

    month = None
    year = None
    for name, num in [
        ("january", 1), ("february", 2), ("march", 3), ("april", 4), ("may", 5), ("june", 6),
        ("july", 7), ("august", 8), ("september", 9), ("october", 10), ("november", 11), ("december", 12),
    ]:
        if name in q:
            month = f"{today.year:04d}-{num:02d}"
            break
    if "this month" in q:
        month = f"{today.year:04d}-{today.month:02d}"
    if "last month" in q:
        y, mth = previous_month(today.year, today.month)
        month = f"{y:04d}-{mth:02d}"
    if "this year" in q or "in " + str(today.year) in q:
        year = today.year
    m = re.search(r"\b(20\d{2})\b", q)
    if m:
        year = int(m.group(1))

    return {
        "intent": intent,
        "month": month,
        "year": year,
        "category": category,
        "merchant": merchant,
        "min_amount": min_amount,
        "limit": limit or 5,
        "from_llm": False,
    }


def _match_category(q: str) -> str | None:
    mapping = {
        "food": "Food & Dining",
        "dining": "Food & Dining",
        "restaurant": "Food & Dining",
        "coffee": "Food & Dining",
        "grocer": "Groceries",
        "uber": None,
        "transport": "Transportation",
        "gas": "Transportation",
        "shopping": "Shopping",
        "amazon": None,
        "rent": "Housing",
        "hous": "Housing",
        "utilit": "Utilities",
        "subscription": "Subscriptions",
        "netflix": None,
        "health": "Health",
        "travel": "Travel",
        "education": "Education",
        "pet": "Pets",
        "insurance": "Insurance",
        "gift": "Gifts",
        "entertainment": "Entertainment",
    }
    for key, cat in mapping.items():
        if key in q and cat:
            return cat
    return None


def _match_merchant(q: str) -> str | None:
    for name in ["starbucks", "chipotle", "uber", "amazon", "netflix", "spotify", "trader joe", "lyft", "target", "walmart", "costco"]:
        if name in q:
            return name
    m = re.search(r"\bat\s+([a-z0-9&'.]+)", q)
    if m:
        return m.group(1)
    return None


def execute_intent(db: Session, intent: dict, today: date) -> dict:
    kind = intent.get("intent") or "unknown"
    month_key = intent.get("month") or f"{today.year:04d}-{today.month:02d}"
    year, month = parse_month_key(month_key)

    if kind == "monthly_total":
        if intent.get("year") and not intent.get("month"):
            y = int(intent["year"])
            start, _ = month_bounds(y, 1)
            _, end = month_bounds(y, 12)
            stmt = select(func.coalesce(func.sum(Expense.amount_cents), 0), func.count()).where(
                Expense.deleted_at.is_(None), Expense.date >= start, Expense.date <= end
            )
            total, count = db.execute(stmt).one()
            return {"total_cents": int(total), "count": int(count), "year": y, "scope": "year"}
        summary = monthly_summary(db, year, month)
        return {"total_cents": summary["total_cents"], "count": summary["count"], "label": summary["label"]}

    if kind == "category_spend":
        name = intent.get("category") or "Food & Dining"
        cents = category_total_cents(db, year, month, name)
        return {"category": name, "cents": cents, "label": date(year, month, 1).strftime("%B %Y")}

    if kind == "merchant_spend":
        merchant = intent.get("merchant") or ""
        start = date(intent["year"], 1, 1) if intent.get("year") and not intent.get("month") else date(year, month, 1)
        if intent.get("year") and not intent.get("month"):
            end = date(intent["year"], 12, 31)
        else:
            _, end = month_bounds(year, month)
        total, count = merchant_total_cents(db, merchant, start, end)
        return {"merchant": merchant, "cents": total, "count": count}

    if kind == "top_category":
        rows = category_breakdown(db, year, month)
        top = rows[0] if rows else None
        return {"top": top, "label": date(year, month, 1).strftime("%B %Y")}

    if kind == "top_merchant":
        summary = monthly_summary(db, year, month)
        return {"top": summary.get("top_merchant"), "label": summary["label"]}

    if kind == "largest_expenses":
        limit = int(intent.get("limit") or 5)
        expenses = month_expenses(db, year, month)
        expenses.sort(key=lambda e: e.amount_cents, reverse=True)
        return {
            "items": [
                {
                    "amount_cents": e.amount_cents,
                    "merchant": e.merchant,
                    "description": e.description,
                    "date": e.date.isoformat(),
                    "category": e.category.name if e.category else "Other",
                }
                for e in expenses[:limit]
            ]
        }

    if kind == "month_compare":
        py, pm = previous_month(year, month)
        current = monthly_summary(db, year, month)
        previous = monthly_summary(db, py, pm)
        return {
            "current": current,
            "previous": previous,
            "delta_cents": current["total_cents"] - previous["total_cents"],
        }

    if kind == "over_amount":
        min_cents = int(round(float(intent.get("min_amount") or 100) * 100))
        expenses = [e for e in month_expenses(db, year, month) if e.amount_cents >= min_cents]
        return {
            "min_cents": min_cents,
            "count": len(expenses),
            "total_cents": sum(e.amount_cents for e in expenses),
            "items": [
                {
                    "amount_cents": e.amount_cents,
                    "merchant": e.merchant,
                    "date": e.date.isoformat(),
                }
                for e in expenses[:20]
            ],
        }

    summary = monthly_summary(db, today.year, today.month)
    return {"fallback_summary": summary, "note": "Could not parse a specific intent."}


def explain(intent: dict, result: dict, question: str) -> str:
    kind = intent.get("intent")
    if kind == "monthly_total" and "total_cents" in result:
        scope = result.get("label") or result.get("year") or "that period"
        return f"You spent {format_dollars(result['total_cents'])} across {result.get('count', 0)} expenses in {scope}."
    if kind == "category_spend":
        return f"{result.get('category')}: {format_dollars(result.get('cents', 0))} in {result.get('label')}."
    if kind == "merchant_spend":
        return (
            f"You spent {format_dollars(result.get('cents', 0))} at {result.get('merchant')} "
            f"across {result.get('count', 0)} purchases."
        )
    if kind == "top_category":
        top = result.get("top")
        if not top:
            return "No expenses in that month."
        return f"The largest category in {result.get('label')} was {top['category']} at {top['amount']}."
    if kind == "top_merchant":
        top = result.get("top")
        if not top:
            return "No merchant totals for that month."
        return f"You spent the most at {top['name']} ({format_dollars(top['cents'])})."
    if kind == "largest_expenses":
        items = result.get("items") or []
        if not items:
            return "No expenses found."
        lines = [
            f"{format_dollars(i['amount_cents'])} — {i.get('merchant') or i.get('description') or 'Expense'} ({i['date']})"
            for i in items
        ]
        return "Largest expenses:\n" + "\n".join(lines)
    if kind == "month_compare":
        cur = result["current"]
        prev = result["previous"]
        delta = result["delta_cents"]
        direction = "more" if delta > 0 else "less"
        return (
            f"{cur['label']}: {format_dollars(cur['total_cents'])}. "
            f"{prev['label']}: {format_dollars(prev['total_cents'])}. "
            f"{format_dollars(abs(delta))} {direction} in {cur['label']}."
        )
    if kind == "over_amount":
        return (
            f"{result['count']} purchases over {format_dollars(result['min_cents'])}, "
            f"totaling {format_dollars(result['total_cents'])}."
        )
    if result.get("fallback_summary"):
        s = result["fallback_summary"]
        return f"This month you spent {format_dollars(s['total_cents'])} across {s['count']} expenses."
    return "I could not match that question to your expense data."
