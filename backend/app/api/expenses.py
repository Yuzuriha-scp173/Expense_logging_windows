from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.ai.parser import parsing_service
from app.database import get_db
from app.models import Category, Expense
from app.schemas import ExpenseCreate, ExpenseOut, ExpenseUpdate, ParseRequest, ParseResponse, ParsedExpense
from app.seed import get_setting
from app.services.dates import month_bounds, parse_month_key, today_in_tz
from app.services.expenses import (
    active_expenses,
    create_expense,
    find_duplicates,
    soft_delete,
    to_out,
    update_expense,
)
from app.services.money import dollars_to_cents

router = APIRouter(prefix="/api/expenses", tags=["expenses"])


@router.post("/parse", response_model=ParseResponse)
def parse_expenses(payload: ParseRequest, db: Session = Depends(get_db)) -> ParseResponse:
    tz = payload.timezone or get_setting(db, "timezone", "America/Chicago")
    today = today_in_tz(tz)
    expenses, parser, warnings = parsing_service.parse(payload.text, today, db)
    duplicates = []
    for item in expenses:
        found = find_duplicates(db, _parsed_to_create(item))
        if found:
            duplicates.append(
                {"merchant": item.merchant, "amount": str(item.amount), "date": item.date.isoformat()}
            )
    used = "llm" if parser == "llm" else "fallback"
    return ParseResponse(expenses=expenses, parser=used, warnings=warnings, duplicates=duplicates)  # type: ignore[arg-type]


@router.post("", response_model=ExpenseOut)
def add_expense(
    payload: ExpenseCreate,
    force: bool = Query(False),
    db: Session = Depends(get_db),
) -> ExpenseOut:
    expense, duplicates = create_expense(db, payload, force=force)
    if duplicates and not force:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "This expense may already exist.",
                "duplicates": [to_out(d).model_dump(mode="json") for d in duplicates],
            },
        )
    return to_out(expense)


@router.post("/bulk", response_model=list[ExpenseOut])
def add_many(
    payload: list[ExpenseCreate], force: bool = Query(False), db: Session = Depends(get_db)
) -> list[ExpenseOut]:
    saved: list[ExpenseOut] = []
    conflicts = []
    for item in payload:
        expense, duplicates = create_expense(db, item, force=force)
        if duplicates and not force:
            conflicts.append(to_out(duplicates[0]).model_dump(mode="json"))
            continue
        saved.append(to_out(expense))
    if conflicts and not saved:
        raise HTTPException(
            status_code=409,
            detail={"message": "These expenses may already exist.", "duplicates": conflicts},
        )
    return saved


@router.get("", response_model=list[ExpenseOut])
def list_expenses(
    month: str | None = None,
    start: date | None = None,
    end: date | None = None,
    category: str | None = None,
    merchant: str | None = None,
    search: str | None = None,
    min_amount: Decimal | None = None,
    max_amount: Decimal | None = None,
    sort: str = "newest",
    db: Session = Depends(get_db),
) -> list[ExpenseOut]:
    stmt = active_expenses()
    if month:
        year, m = parse_month_key(month)
        ms, me = month_bounds(year, m)
        stmt = stmt.where(Expense.date >= ms, Expense.date <= me)
    if start:
        stmt = stmt.where(Expense.date >= start)
    if end:
        stmt = stmt.where(Expense.date <= end)
    if category:
        stmt = stmt.where(Expense.category.has(Category.name == category))
    if merchant:
        stmt = stmt.where(Expense.merchant.ilike(f"%{merchant}%"))
    if search:
        term = f"%{search}%"
        stmt = stmt.where(
            or_(
                Expense.merchant.ilike(term),
                Expense.description.ilike(term),
                Expense.notes.ilike(term),
                Expense.subcategory.ilike(term),
            )
        )
    if min_amount is not None:
        stmt = stmt.where(Expense.amount_cents >= dollars_to_cents(min_amount))
    if max_amount is not None:
        stmt = stmt.where(Expense.amount_cents <= dollars_to_cents(max_amount))
    if sort == "oldest":
        stmt = stmt.order_by(Expense.date.asc(), Expense.id.asc())
    elif sort == "highest":
        stmt = stmt.order_by(Expense.amount_cents.desc())
    elif sort == "lowest":
        stmt = stmt.order_by(Expense.amount_cents.asc())
    else:
        stmt = stmt.order_by(Expense.date.desc(), Expense.id.desc())
    rows = list(db.scalars(stmt).unique().all())
    return [to_out(e) for e in rows]


@router.get("/{expense_id}", response_model=ExpenseOut)
def get_expense(expense_id: int, db: Session = Depends(get_db)) -> ExpenseOut:
    expense = db.get(Expense, expense_id)
    if expense is None or expense.deleted_at is not None:
        raise HTTPException(404, "Expense not found")
    return to_out(expense)


@router.put("/{expense_id}", response_model=ExpenseOut)
def edit_expense(expense_id: int, payload: ExpenseUpdate, db: Session = Depends(get_db)) -> ExpenseOut:
    expense = db.get(Expense, expense_id)
    if expense is None or expense.deleted_at is not None:
        raise HTTPException(404, "Expense not found")
    update_expense(db, expense, payload)
    return to_out(expense)


@router.delete("/{expense_id}")
def remove_expense(expense_id: int, db: Session = Depends(get_db)) -> dict:
    expense = db.get(Expense, expense_id)
    if expense is None or expense.deleted_at is not None:
        raise HTTPException(404, "Expense not found")
    soft_delete(db, expense)
    return {"ok": True}


def _parsed_to_create(item: ParsedExpense) -> ExpenseCreate:
    return ExpenseCreate(
        amount=item.amount,
        currency=item.currency,
        date=item.date,
        merchant=item.merchant,
        description=item.description,
        category=item.category,
        subcategory=item.subcategory,
        payment_method=item.payment_method,
        notes=item.notes,
        source="AI_TEXT",
        category_uncertain=item.category_uncertain,
    )
