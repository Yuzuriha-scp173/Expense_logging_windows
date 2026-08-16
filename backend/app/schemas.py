from __future__ import annotations

from datetime import date as Date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.money import to_decimal

Source = Literal["AI_TEXT", "MANUAL", "RECEIPT", "IMPORT"]
ParserKind = Literal["llm", "fallback"]


class ParsedExpense(BaseModel):
    amount: Decimal = Field(..., gt=0)
    currency: str = "USD"
    category: str = "Other"
    subcategory: str | None = None
    merchant: str | None = None
    description: str | None = None
    date: Date
    payment_method: str | None = None
    notes: str | None = None
    category_uncertain: bool = False

    @field_validator("amount", mode="before")
    @classmethod
    def _amount(cls, value: object) -> Decimal:
        return to_decimal(value)  # type: ignore[arg-type]

    @field_validator("merchant", "description", "subcategory", "payment_method", "notes")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if stripped == "" or stripped.lower() in {"unknown", "n/a", "none", "null"}:
            return None
        return stripped

    @field_validator("category")
    @classmethod
    def _category(cls, value: str | None) -> str:
        if not value or value.strip().lower() in {"unknown", "n/a", "none", "null", ""}:
            return "Other"
        return value.strip()

    @field_validator("currency")
    @classmethod
    def _currency(cls, value: str) -> str:
        return value.strip().upper() or "USD"


class ExpenseCreate(BaseModel):
    amount: Decimal = Field(..., gt=0)
    currency: str = "USD"
    date: Date
    merchant: str | None = None
    description: str | None = None
    category: str
    subcategory: str | None = None
    payment_method: str | None = None
    notes: str | None = None
    source: Source = "MANUAL"
    category_uncertain: bool = False
    learn_merchant_rule: bool = True

    @field_validator("amount", mode="before")
    @classmethod
    def _amount(cls, value: object) -> Decimal:
        return to_decimal(value)  # type: ignore[arg-type]


class ExpenseUpdate(BaseModel):
    amount: Decimal | None = None
    currency: str | None = None
    date: Date | None = None
    merchant: str | None = None
    description: str | None = None
    category: str | None = None
    subcategory: str | None = None
    payment_method: str | None = None
    notes: str | None = None
    is_recurring: bool | None = None
    learn_merchant_rule: bool = True

    @field_validator("amount", mode="before")
    @classmethod
    def _amount(cls, value: object) -> object:
        if value is None:
            return value
        return to_decimal(value)  # type: ignore[arg-type]


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount: Decimal
    amount_cents: int
    currency: str
    date: Date
    merchant: str | None
    description: str | None
    category: str
    category_id: int
    subcategory: str | None
    payment_method: str | None
    notes: str | None
    source: str
    category_uncertain: bool
    is_recurring: bool
    created_at: str | None = None
    updated_at: str | None = None
    possible_duplicate: bool = False


class ParseRequest(BaseModel):
    text: str = Field(..., min_length=1)
    timezone: str | None = None


class ParseResponse(BaseModel):
    expenses: list[ParsedExpense]
    parser: ParserKind
    warnings: list[str] = []
    duplicates: list[dict] = []


class ExpenseListQuery(BaseModel):
    month: str | None = None
    start: Date | None = None
    end: Date | None = None
    category: str | None = None
    merchant: str | None = None
    search: str | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    sort: Literal["newest", "oldest", "highest", "lowest"] = "newest"


class CategoryOut(BaseModel):
    id: int
    name: str
    icon: str
    is_custom: bool
    parent_category_id: int | None = None


class CategoryCreate(BaseModel):
    name: str
    icon: str = "circle"


class SettingsOut(BaseModel):
    default_currency: str
    timezone: str
    week_start: str
    theme: str
    ai_provider: str
    auto_save_ai: bool
    openai_model: str
    anthropic_model: str
    ollama_model: str
    has_openai_key: bool
    has_anthropic_key: bool


class SettingsUpdate(BaseModel):
    default_currency: str | None = None
    timezone: str | None = None
    week_start: str | None = None
    theme: str | None = None
    ai_provider: str | None = None
    auto_save_ai: bool | None = None


class AssistantQuery(BaseModel):
    question: str = Field(..., min_length=1)
    timezone: str | None = None


class AssistantAnswer(BaseModel):
    question: str
    intent: str
    explanation: str
    result: dict
    used_llm: bool = False


class BudgetIn(BaseModel):
    category: str
    month: str
    amount: Decimal = Field(..., gt=0)

    @field_validator("amount", mode="before")
    @classmethod
    def _amount(cls, value: object) -> Decimal:
        return to_decimal(value)  # type: ignore[arg-type]


class BudgetOut(BaseModel):
    id: int
    category: str
    month: str
    amount_cents: int
    spent_cents: int
    remaining_cents: int
    percent: float
