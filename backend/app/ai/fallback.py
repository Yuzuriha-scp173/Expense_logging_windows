from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from app.schemas import ParsedExpense
from app.services.dates import resolve_expense_date
from app.services.money import to_decimal

MERCHANT_MAP: dict[str, tuple[str, str | None]] = {
    "starbucks": ("Food & Dining", "Coffee"),
    "dunkin": ("Food & Dining", "Coffee"),
    "chipotle": ("Food & Dining", "Fast Food"),
    "mcdonald": ("Food & Dining", "Fast Food"),
    "mcdonald's": ("Food & Dining", "Fast Food"),
    "wendy": ("Food & Dining", "Fast Food"),
    "taco bell": ("Food & Dining", "Fast Food"),
    "panera": ("Food & Dining", "Restaurants"),
    "sweetgreen": ("Food & Dining", "Restaurants"),
    "doordash": ("Food & Dining", "Delivery"),
    "uber eats": ("Food & Dining", "Delivery"),
    "grubhub": ("Food & Dining", "Delivery"),
    "trader joe": ("Groceries", None),
    "trader joe's": ("Groceries", None),
    "whole foods": ("Groceries", None),
    "safeway": ("Groceries", None),
    "kroger": ("Groceries", None),
    "costco": ("Groceries", None),
    "aldi": ("Groceries", None),
    "walmart": ("Shopping", None),
    "target": ("Shopping", None),
    "amazon": ("Shopping", "Online Shopping"),
    "uber": ("Transportation", "Rideshare"),
    "lyft": ("Transportation", "Rideshare"),
    "shell": ("Transportation", "Gas"),
    "chevron": ("Transportation", "Gas"),
    "exxon": ("Transportation", "Gas"),
    "bp": ("Transportation", "Gas"),
    "netflix": ("Subscriptions", "Streaming"),
    "spotify": ("Subscriptions", "Streaming"),
    "hulu": ("Subscriptions", "Streaming"),
    "disney": ("Subscriptions", "Streaming"),
    "chatgpt": ("Subscriptions", "Software"),
    "openai": ("Subscriptions", "Software"),
    "apple": ("Subscriptions", "Software"),
    "google": ("Subscriptions", "Software"),
    "gym": ("Health", None),
    "planet fitness": ("Health", None),
}

KEYWORD_CATEGORY: list[tuple[re.Pattern[str], str, str | None]] = [
    (re.compile(r"\b(coffee|latte|espresso|cappuccino|cafe)\b", re.I), "Food & Dining", "Coffee"),
    (re.compile(r"\b(lunch|dinner|breakfast|brunch|restaurant|pizza|sushi|taco|burger)\b", re.I), "Food & Dining", "Restaurants"),
    (re.compile(r"\b(grocer(?:y|ies)|supermarket)\b", re.I), "Groceries", None),
    (re.compile(r"\b(uber|lyft|rideshare|taxi|cab)\b", re.I), "Transportation", "Rideshare"),
    (re.compile(r"\b(gas|fuel|petrol)\b", re.I), "Transportation", "Gas"),
    (re.compile(r"\b(parking|metro|transit|bus|train|subway)\b", re.I), "Transportation", "Public Transit"),
    (re.compile(r"\b(rent|mortgage|landlord)\b", re.I), "Housing", None),
    (re.compile(r"\b(electric|water bill|internet|wifi|utility|utilities|phone bill)\b", re.I), "Utilities", None),
    (re.compile(r"\b(netflix|spotify|hulu|subscription|membership)\b", re.I), "Subscriptions", "Streaming"),
    (re.compile(r"\b(school supplies|tuition|textbook|course)\b", re.I), "Education", None),
    (re.compile(r"\b(pharmacy|doctor|dentist|medicine|gym)\b", re.I), "Health", None),
    (re.compile(r"\b(hotel|flight|airbnb|airline)\b", re.I), "Travel", None),
    (re.compile(r"\b(amazon|clothes|clothing|shoes|electronics)\b", re.I), "Shopping", None),
    (re.compile(r"\b(movie|concert|game|tickets)\b", re.I), "Entertainment", None),
    (re.compile(r"\b(haircut|salon|barber)\b", re.I), "Personal Care", None),
    (re.compile(r"\b(gift|present)\b", re.I), "Gifts", None),
    (re.compile(r"\b(insurance)\b", re.I), "Insurance", None),
    (re.compile(r"\b(vet|pet|dog food|cat food)\b", re.I), "Pets", None),
]

STOP_MERCHANTS = {
    "i", "a", "the", "on", "for", "at", "to", "and", "my", "was", "cost", "paid", "spent",
    "dollars", "bucks", "usd", "today", "yesterday", "morning", "night", "this", "last",
    "subscription", "bill",
}

AMOUNT_RE = re.compile(
    r"(?:(?P<sym>\$)|(?P<cur>usd\s*))?"
    r"(?P<num>\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)"
    r"(?:\s*(?P<unit>dollars|bucks|usd))?",
    re.I,
)

AT_MERCHANT_RE = re.compile(r"\b(?:at|from)\s+([A-Za-z][A-Za-z0-9&.'\s]{1,40})", re.I)


class FallbackParser:
    """Regex + dictionary parser. Works with no LLM."""

    def parse(self, text: str, today: date, default_currency: str = "USD") -> list[ParsedExpense]:
        chunks = _split_expense_chunks(text)
        expenses: list[ParsedExpense] = []
        for chunk in chunks:
            parsed = _parse_one(chunk, text, today, default_currency)
            if parsed:
                expenses.append(parsed)
        return expenses


def _split_expense_chunks(text: str) -> list[str]:
    matches = list(AMOUNT_RE.finditer(text))
    if len(matches) <= 1:
        return [text.strip()] if text.strip() else []
    # Multiple amounts — split around each amount using nearby conjunctions
    parts: list[str] = []
    for i, match in enumerate(matches):
        start = match.start()
        # include a little left context for merchant-first phrases like "Uber $22"
        left = text.rfind(",", 0, start)
        and_at = text.lower().rfind(" and ", 0, start)
        cut = max(left, and_at)
        if i == 0:
            chunk_start = 0
        else:
            chunk_start = cut + 1 if cut != -1 else match.start()
        if i + 1 < len(matches):
            next_start = matches[i + 1].start()
            comma = text.find(",", match.end(), next_start)
            and_pos = text.lower().find(" and ", match.end(), next_start)
            candidates = [p for p in (comma, and_pos) if p != -1]
            chunk_end = min(candidates) if candidates else next_start
        else:
            chunk_end = len(text)
        chunk = text[chunk_start:chunk_end].strip(" ,.;")
        if chunk:
            parts.append(chunk)
    return parts or [text]


def _parse_one(chunk: str, full_text: str, today: date, default_currency: str) -> ParsedExpense | None:
    match = AMOUNT_RE.search(chunk)
    if not match:
        return None
    raw = match.group("num").replace(",", "")
    try:
        amount = to_decimal(raw)
    except (InvalidOperation, ValueError):
        return None
    if amount <= 0:
        return None

    expense_date = resolve_expense_date(chunk, today)
    if expense_date == today:
        expense_date = resolve_expense_date(full_text, today)

    merchant = _extract_merchant(chunk)
    category, subcategory, uncertain = _classify(chunk, merchant)
    description = _extract_description(chunk, merchant, amount)

    return ParsedExpense(
        amount=amount,
        currency=default_currency,
        category=category,
        subcategory=subcategory,
        merchant=merchant,
        description=description,
        date=expense_date,
        payment_method=None,
        notes=None,
        category_uncertain=uncertain,
    )


def _extract_merchant(chunk: str) -> str | None:
    at = AT_MERCHANT_RE.search(chunk)
    if at:
        name = _clean_merchant(at.group(1))
        if name:
            return name
    lowered = chunk.lower()
    for key in sorted(MERCHANT_MAP, key=len, reverse=True):
        if key in lowered:
            return _title_merchant(key)
    return None


def _clean_merchant(raw: str) -> str | None:
    cleaned = re.split(r"\b(for|on|this|today|yesterday|last|with)\b", raw, maxsplit=1, flags=re.I)[0]
    cleaned = re.sub(r"[^A-Za-z0-9&.'\s]", "", cleaned).strip(" .,'")
    if not cleaned or cleaned.lower() in STOP_MERCHANTS:
        return None
    if len(cleaned) < 2:
        return None
    return cleaned.title() if cleaned.islower() or cleaned.istitle() else cleaned


def _title_merchant(key: str) -> str:
    specials = {
        "trader joe": "Trader Joe's",
        "trader joe's": "Trader Joe's",
        "mcdonald": "McDonald's",
        "mcdonald's": "McDonald's",
        "uber eats": "Uber Eats",
        "whole foods": "Whole Foods",
        "taco bell": "Taco Bell",
        "planet fitness": "Planet Fitness",
        "chatgpt": "ChatGPT",
    }
    if key in specials:
        return specials[key]
    return key.title()


def _classify(chunk: str, merchant: str | None) -> tuple[str, str | None, bool]:
    if merchant:
        key = merchant.lower().replace("’", "'")
        for pattern, pair in sorted(MERCHANT_MAP.items(), key=lambda item: len(item[0]), reverse=True):
            if pattern == key or pattern in key:
                return pair[0], pair[1], False
    for pattern, category, sub in KEYWORD_CATEGORY:
        if pattern.search(chunk):
            return category, sub, False
    return "Other", None, True


def _extract_description(chunk: str, merchant: str | None, amount: Decimal) -> str | None:
    text = AMOUNT_RE.sub(" ", chunk)
    text = re.sub(r"\b(spent|paid|was|cost|i|my|a|the|on|for|at|from|dollars|bucks|usd)\b", " ", text, flags=re.I)
    text = re.sub(
        r"\b(today|yesterday|this morning|last night|this afternoon|tonight)\b",
        " ",
        text,
        flags=re.I,
    )
    if merchant:
        text = re.sub(re.escape(merchant), " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" ,.-")
    text = re.sub(r"^and\s+", "", text, flags=re.I)
    if not text or text.lower() in STOP_MERCHANTS:
        if merchant:
            return None
        return None
    # Keep it short
    words = text.split()
    if len(words) > 8:
        words = words[:8]
    desc = " ".join(words).strip()
    return desc[:80] if desc else None
