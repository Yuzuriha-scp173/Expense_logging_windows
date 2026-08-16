from __future__ import annotations

import json
import re
from datetime import date
from typing import Protocol

import httpx

from app.config import Settings
from app.schemas import ParsedExpense
from app.services.dates import resolve_expense_date

SYSTEM_PROMPT = """You extract personal expenses from a short message.
Return ONLY valid JSON: {"expenses": [ ... ]}
Each expense object:
{
  "amount": number,
  "currency": "USD",
  "category": one of [Food & Dining, Groceries, Transportation, Shopping, Entertainment, Housing, Utilities, Subscriptions, Education, Health, Travel, Personal Care, Gifts, Bills, Insurance, Pets, Other],
  "subcategory": string or null,
  "merchant": string or null,
  "description": string or null,
  "date": "YYYY-MM-DD" or a phrase like today/yesterday,
  "payment_method": null unless clearly stated,
  "notes": null unless clearly stated,
  "category_uncertain": boolean
}
Rules:
- Do not invent merchant, subcategory, or payment method.
- If date is missing, use DATE_TODAY.
- Multiple amounts in one message become multiple expenses.
- If category is unclear, use Other and category_uncertain true.
- Amounts are positive numbers. Strip $ and commas.
"""


class LLMClient(Protocol):
    def complete_json(self, system: str, user: str) -> str: ...


class OpenAIClient:
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def complete_json(self, system: str, user: str) -> str:
        with httpx.Client(timeout=30) as client:
            response = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]


class AnthropicClient:
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def complete_json(self, system: str, user: str) -> str:
        with httpx.Client(timeout=30) as client:
            response = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 1024,
                    "temperature": 0,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                },
            )
            response.raise_for_status()
            blocks = response.json()["content"]
            return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")


class OllamaClient:
    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    def complete_json(self, system: str, user: str) -> str:
        with httpx.Client(timeout=60) as client:
            response = client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "stream": False,
                    "format": "json",
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
            response.raise_for_status()
            return response.json()["message"]["content"]


def client_from_settings(settings: Settings, provider: str | None = None) -> LLMClient | None:
    kind = (provider or settings.ai_provider or "fallback").lower()
    if kind == "openai" and settings.openai_api_key:
        return OpenAIClient(settings.openai_api_key, settings.openai_model)
    if kind == "anthropic" and settings.anthropic_api_key:
        return AnthropicClient(settings.anthropic_api_key, settings.anthropic_model)
    if kind == "ollama":
        return OllamaClient(settings.ollama_base_url, settings.ollama_model)
    return None


class LLMParser:
    def __init__(self, client: LLMClient) -> None:
        self.client = client

    def parse(self, text: str, today: date, default_currency: str = "USD") -> list[ParsedExpense]:
        system = SYSTEM_PROMPT.replace("DATE_TODAY", today.isoformat())
        user = f"Today is {today.isoformat()}. Default currency is {default_currency}.\nMessage: {text}"
        raw = self.client.complete_json(system, user)
        data = _extract_json(raw)
        items = data.get("expenses", data if isinstance(data, list) else [data])
        parsed: list[ParsedExpense] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            item = dict(item)
            raw_date = item.get("date")
            if isinstance(raw_date, str) and not re.match(r"^\d{4}-\d{2}-\d{2}$", raw_date):
                item["date"] = resolve_expense_date(raw_date, today).isoformat()
            elif not raw_date:
                item["date"] = today.isoformat()
            item.setdefault("currency", default_currency)
            try:
                parsed.append(ParsedExpense.model_validate(item))
            except Exception:
                continue
        return parsed


def _extract_json(raw: str) -> dict | list:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw).strip()
        raw = re.sub(r"```$", "", raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}|\[.*\]", raw, re.S)
        if match:
            return json.loads(match.group(0))
        raise
