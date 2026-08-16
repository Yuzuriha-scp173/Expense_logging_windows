from __future__ import annotations

from datetime import date
from typing import Protocol

from sqlalchemy.orm import Session

from app.ai.fallback import FallbackParser
from app.ai.providers import LLMParser, client_from_settings
from app.config import get_settings
from app.schemas import ParsedExpense
from app.seed import get_setting
from app.services.merchant_rules import apply_merchant_rule


class ExpenseParser(Protocol):
    def parse(self, text: str, today: date, default_currency: str = "USD") -> list[ParsedExpense]: ...


class ParsingService:
    def __init__(self) -> None:
        self.fallback = FallbackParser()

    def parse(
        self,
        text: str,
        today: date,
        db: Session,
        prefer_provider: str | None = None,
    ) -> tuple[list[ParsedExpense], str, list[str]]:
        settings = get_settings()
        currency = get_setting(db, "default_currency", "USD")
        provider = prefer_provider or get_setting(db, "ai_provider", settings.ai_provider)
        warnings: list[str] = []
        used = "fallback"
        expenses: list[ParsedExpense] = []

        client = client_from_settings(settings, provider)
        if client is not None and provider not in {"fallback", "", "none"}:
            try:
                expenses = LLMParser(client).parse(text, today, currency)
                used = "llm"
            except Exception as exc:  # noqa: BLE001 — degrade to fallback
                warnings.append(
                    "AI parsing is temporarily unavailable. You can still enter the expense manually."
                )
                warnings.append(str(exc)[:200])
                expenses = []

        if not expenses:
            expenses = self.fallback.parse(text, today, currency)
            if used == "llm":
                warnings.append("Fell back to the built-in parser.")
            used = "fallback" if used != "llm" or not expenses else used
            if not expenses and used != "llm":
                used = "fallback"

        if not expenses:
            # If LLM returned nothing and fallback nothing
            expenses = self.fallback.parse(text, today, currency)
            used = "fallback"

        applied: list[ParsedExpense] = []
        for item in expenses:
            rule = apply_merchant_rule(db, item.merchant, item.category, item.subcategory)
            data = item.model_dump()
            data["category"] = rule.category
            data["subcategory"] = rule.subcategory
            if rule.category != item.category:
                data["category_uncertain"] = False
            applied.append(ParsedExpense.model_validate(data))
        return applied, used if applied and used == "llm" else "fallback" if not client else used, warnings


parsing_service = ParsingService()
