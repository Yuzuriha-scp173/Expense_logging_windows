from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.ai.assistant import answer_question
from app.database import get_db
from app.models import Budget, Category, MerchantRule
from app.schemas import (
    AssistantQuery,
    BudgetIn,
    BudgetOut,
    CategoryCreate,
    CategoryOut,
    SettingsOut,
    SettingsUpdate,
)
from app.seed import DEFAULT_SETTINGS, SUBCATEGORIES, get_setting, set_setting
from app.services.analytics import category_total_cents, dashboard_payload
from app.services.backup import backup_database, expenses_to_csv
from app.services.dates import parse_month_key, today_in_tz
from app.services.insights import build_insights, monthly_narrative
from app.services.merchant_rules import delete_rule, list_rules
from app.services.money import cents_to_dollars, dollars_to_cents
from app.services.recurring import detect_recurring
from app.config import get_settings

summary_router = APIRouter(prefix="/api/summary", tags=["summary"])
settings_router = APIRouter(prefix="/api/settings", tags=["settings"])
categories_router = APIRouter(prefix="/api/categories", tags=["categories"])
assistant_router = APIRouter(prefix="/api/assistant", tags=["assistant"])
misc_router = APIRouter(prefix="/api", tags=["misc"])


@summary_router.get("/dashboard")
def dashboard(month: str | None = None, timezone: str | None = None, db: Session = Depends(get_db)) -> dict:
    tz = timezone or get_setting(db, "timezone", "America/Chicago")
    today = today_in_tz(tz)
    if month:
        year, m = parse_month_key(month)
    else:
        year, m = today.year, today.month
    payload = dashboard_payload(db, year, m)
    payload["month"] = f"{year:04d}-{m:02d}"
    return payload


@summary_router.get("/monthly")
def monthly(month: str, db: Session = Depends(get_db)) -> dict:
    year, m = parse_month_key(month)
    return dashboard_payload(db, year, m)["summary"]


@summary_router.get("/categories")
def categories(month: str, db: Session = Depends(get_db)) -> list:
    from app.services.analytics import category_breakdown

    year, m = parse_month_key(month)
    return category_breakdown(db, year, m)


@summary_router.get("/trends")
def trends(month: str, db: Session = Depends(get_db)) -> list:
    from app.services.analytics import monthly_trend

    year, m = parse_month_key(month)
    return monthly_trend(db, year, m)


@summary_router.get("/insights")
def insights(month: str, db: Session = Depends(get_db)) -> dict:
    year, m = parse_month_key(month)
    return {"insights": build_insights(db, year, m), "narrative": monthly_narrative(db, year, m)}


@summary_router.get("/history")
def history(month: str | None = None, timezone: str | None = None, db: Session = Depends(get_db)) -> dict:
    from app.services.analytics import history_payload

    tz = timezone or get_setting(db, "timezone", "America/Chicago")
    today = today_in_tz(tz)
    if month:
        year, m = parse_month_key(month)
    else:
        year, m = today.year, today.month
    return history_payload(db, year, m, months=12)


@settings_router.get("", response_model=SettingsOut)
def read_settings(db: Session = Depends(get_db)) -> SettingsOut:
    env = get_settings()
    provider = get_setting(db, "ai_provider", env.ai_provider)
    return SettingsOut(
        default_currency=get_setting(db, "default_currency", "USD"),
        timezone=get_setting(db, "timezone", "America/Chicago"),
        week_start=get_setting(db, "week_start", "sunday"),
        theme=get_setting(db, "theme", "system"),
        ai_provider=provider,
        auto_save_ai=get_setting(db, "auto_save_ai", "false") == "true",
        openai_model=env.openai_model,
        anthropic_model=env.anthropic_model,
        ollama_model=env.ollama_model,
        has_openai_key=bool(env.openai_api_key),
        has_anthropic_key=bool(env.anthropic_api_key),
    )


@settings_router.put("", response_model=SettingsOut)
def write_settings(payload: SettingsUpdate, db: Session = Depends(get_db)) -> SettingsOut:
    mapping = payload.model_dump(exclude_none=True)
    for key, value in mapping.items():
        if isinstance(value, bool):
            set_setting(db, key, "true" if value else "false")
        else:
            set_setting(db, key, str(value))
    db.commit()
    return read_settings(db)


@categories_router.get("", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)) -> list[CategoryOut]:
    rows = db.query(Category).order_by(Category.id.asc()).all()
    return [
        CategoryOut(id=c.id, name=c.name, icon=c.icon, is_custom=c.is_custom, parent_category_id=c.parent_category_id)
        for c in rows
    ]


@categories_router.get("/subcategories")
def subcategories() -> dict[str, list[str]]:
    return SUBCATEGORIES


@categories_router.post("", response_model=CategoryOut)
def add_category(payload: CategoryCreate, db: Session = Depends(get_db)) -> CategoryOut:
    existing = db.query(Category).filter(Category.name == payload.name).first()
    if existing:
        raise HTTPException(400, "Category already exists")
    cat = Category(name=payload.name.strip(), icon=payload.icon, is_custom=True)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return CategoryOut(id=cat.id, name=cat.name, icon=cat.icon, is_custom=cat.is_custom, parent_category_id=None)


@assistant_router.post("/query")
def assistant(payload: AssistantQuery, db: Session = Depends(get_db)) -> dict:
    tz = payload.timezone or get_setting(db, "timezone", "America/Chicago")
    return answer_question(db, payload.question, tz)


@misc_router.get("/health")
def health() -> dict:
    return {"ok": True, "name": "Daybook"}


@misc_router.get("/export.csv")
def export_csv(db: Session = Depends(get_db)) -> PlainTextResponse:
    body = expenses_to_csv(db)
    return PlainTextResponse(body, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=daybook.csv"})


@misc_router.post("/backup")
def backup() -> dict:
    path = backup_database()
    return {"path": str(path)}


@misc_router.get("/rules")
def rules(db: Session = Depends(get_db)) -> list[dict]:
    return [
        {
            "id": r.id,
            "merchant_pattern": r.merchant_pattern,
            "preferred_category": r.preferred_category,
            "preferred_subcategory": r.preferred_subcategory,
        }
        for r in list_rules(db)
    ]


@misc_router.delete("/rules/{rule_id}")
def remove_rule(rule_id: int, db: Session = Depends(get_db)) -> dict:
    if not delete_rule(db, rule_id):
        raise HTTPException(404, "Rule not found")
    db.commit()
    return {"ok": True}


@misc_router.get("/subscriptions")
def subscriptions(db: Session = Depends(get_db)) -> list[dict]:
    return detect_recurring(db)


@misc_router.get("/budgets", response_model=list[BudgetOut])
def budgets(month: str, db: Session = Depends(get_db)) -> list[BudgetOut]:
    year, m = parse_month_key(month)
    rows = db.query(Budget).filter(Budget.month == month).all()
    out = []
    for b in rows:
        cat = db.get(Category, b.category_id)
        name = cat.name if cat else "Other"
        spent = category_total_cents(db, year, m, name)
        remaining = b.amount_cents - spent
        percent = (spent / b.amount_cents * 100) if b.amount_cents else 0
        out.append(
            BudgetOut(
                id=b.id,
                category=name,
                month=month,
                amount_cents=b.amount_cents,
                spent_cents=spent,
                remaining_cents=remaining,
                percent=round(percent, 1),
            )
        )
    return out


@misc_router.post("/budgets", response_model=BudgetOut)
def upsert_budget(payload: BudgetIn, db: Session = Depends(get_db)) -> BudgetOut:
    cat = db.query(Category).filter(Category.name == payload.category).first()
    if not cat:
        raise HTTPException(400, "Unknown category")
    existing = db.query(Budget).filter(Budget.category_id == cat.id, Budget.month == payload.month).first()
    cents = dollars_to_cents(payload.amount)
    if existing:
        existing.amount_cents = cents
        db.commit()
        return budgets(payload.month, db)[0] if False else _budget_out(db, existing)
    row = Budget(category_id=cat.id, month=payload.month, amount_cents=cents)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _budget_out(db, row)


def _budget_out(db: Session, b: Budget) -> BudgetOut:
    cat = db.get(Category, b.category_id)
    name = cat.name if cat else "Other"
    year, m = parse_month_key(b.month)
    spent = category_total_cents(db, year, m, name)
    remaining = b.amount_cents - spent
    percent = (spent / b.amount_cents * 100) if b.amount_cents else 0
    return BudgetOut(
        id=b.id,
        category=name,
        month=b.month,
        amount_cents=b.amount_cents,
        spent_cents=spent,
        remaining_cents=remaining,
        percent=round(percent, 1),
    )
