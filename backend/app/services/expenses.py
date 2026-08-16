from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import Category, Expense
from app.schemas import ExpenseCreate, ExpenseOut, ExpenseUpdate
from app.seed import get_setting
from app.services.merchant_rules import apply_merchant_rule, remember_correction
from app.services.money import cents_to_dollars, dollars_to_cents


def get_category_by_name(db: Session, name: str) -> Category | None:
    return db.scalar(select(Category).where(Category.name == name))


def require_category(db: Session, name: str) -> Category:
    category = get_category_by_name(db, name)
    if category is None:
        other = get_category_by_name(db, "Other")
        if other is None:
            raise ValueError("Categories are not seeded")
        return other
    return category


def active_expenses() -> Select[tuple[Expense]]:
    return select(Expense).where(Expense.deleted_at.is_(None)).options(joinedload(Expense.category))


def to_out(expense: Expense, possible_duplicate: bool = False) -> ExpenseOut:
    created = expense.created_at.isoformat() if expense.created_at else None
    updated = expense.updated_at.isoformat() if expense.updated_at else None
    return ExpenseOut(
        id=expense.id,
        amount=cents_to_dollars(expense.amount_cents),
        amount_cents=expense.amount_cents,
        currency=expense.currency,
        date=expense.date,
        merchant=expense.merchant,
        description=expense.description,
        category=expense.category.name if expense.category else "Other",
        category_id=expense.category_id,
        subcategory=expense.subcategory,
        payment_method=expense.payment_method,
        notes=expense.notes,
        source=expense.source,
        category_uncertain=expense.category_uncertain,
        is_recurring=expense.is_recurring,
        created_at=created,
        updated_at=updated,
        possible_duplicate=possible_duplicate,
    )


def find_duplicates(db: Session, payload: ExpenseCreate, exclude_id: int | None = None) -> list[Expense]:
    stmt = active_expenses().where(
        Expense.amount_cents == dollars_to_cents(payload.amount),
        Expense.date == payload.date,
        Expense.currency == payload.currency,
    )
    if payload.merchant:
        stmt = stmt.where(Expense.merchant == payload.merchant)
    else:
        stmt = stmt.where(Expense.merchant.is_(None))
    if payload.description:
        stmt = stmt.where(Expense.description == payload.description)
    else:
        stmt = stmt.where(or_(Expense.description.is_(None), Expense.description == ""))
    if exclude_id is not None:
        stmt = stmt.where(Expense.id != exclude_id)
    return list(db.scalars(stmt).unique().all())


def create_expense(db: Session, payload: ExpenseCreate, force: bool = False) -> tuple[Expense, list[Expense]]:
    duplicates = find_duplicates(db, payload)
    if duplicates and not force:
        return duplicates[0], duplicates

    applied = apply_merchant_rule(db, payload.merchant, payload.category, payload.subcategory)
    category = require_category(db, applied.category)
    currency = payload.currency or get_setting(db, "default_currency", "USD")
    expense = Expense(
        amount_cents=dollars_to_cents(payload.amount),
        currency=currency,
        date=payload.date,
        merchant=payload.merchant,
        description=payload.description,
        category_id=category.id,
        subcategory=applied.subcategory,
        payment_method=payload.payment_method,
        notes=payload.notes,
        source=payload.source,
        category_uncertain=payload.category_uncertain and applied.category == payload.category,
    )
    db.add(expense)
    db.flush()
    if payload.learn_merchant_rule and payload.merchant:
        remember_correction(db, payload.merchant, category.name, expense.subcategory)
    db.refresh(expense)
    return expense, []


def update_expense(db: Session, expense: Expense, payload: ExpenseUpdate) -> Expense:
    if payload.amount is not None:
        expense.amount_cents = dollars_to_cents(payload.amount)
    if payload.currency is not None:
        expense.currency = payload.currency
    if payload.date is not None:
        expense.date = payload.date
    if payload.merchant is not None:
        expense.merchant = payload.merchant or None
    if payload.description is not None:
        expense.description = payload.description or None
    if payload.subcategory is not None:
        expense.subcategory = payload.subcategory or None
    if payload.payment_method is not None:
        expense.payment_method = payload.payment_method or None
    if payload.notes is not None:
        expense.notes = payload.notes or None
    if payload.is_recurring is not None:
        expense.is_recurring = payload.is_recurring
    if payload.category is not None:
        category = require_category(db, payload.category)
        expense.category_id = category.id
        expense.category_uncertain = False
        if payload.learn_merchant_rule and expense.merchant:
            remember_correction(db, expense.merchant, category.name, expense.subcategory)
    expense.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.flush()
    db.refresh(expense)
    return expense


def soft_delete(db: Session, expense: Expense) -> None:
    expense.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.flush()
