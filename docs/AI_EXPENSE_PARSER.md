# AI expense parser

Interface: `ExpenseParser.parse(text, today, currency) -> list[ParsedExpense]`.

Implementations:

1. **FallbackParser** — regex amounts, date phrases, merchant dictionary. Always available.
2. **LLMParser** — OpenAI, Anthropic, or Ollama. Returns JSON, validated by Pydantic. Discarded if invalid.

`ParsingService` tries the configured provider, then falls back. Merchant rules then overwrite category/subcategory.

## What the model is allowed to see

Only the current typed sentence, today’s date, and the default currency. Not the expense table.

## Schema

```json
{
  "amount": 18.50,
  "currency": "USD",
  "category": "Food & Dining",
  "subcategory": "Restaurant",
  "merchant": "Chipotle",
  "description": "Lunch",
  "date": "2026-08-15",
  "payment_method": null,
  "notes": null
}
```

Missing date → today. Missing merchant → null (not invented). Unclear category → Other + `category_uncertain`.

## Dates

Canonical storage is `YYYY-MM-DD`. Phrases understood without an LLM: today, yesterday, last night, this morning, last Friday, August 10, 8/10.

## Multiple expenses

“Today I spent $6 on coffee, $18 on lunch, and $35 on groceries.” becomes three records, shown together before save.

## Questions

`POST /api/assistant/query` extracts an intent, runs SQL/Python aggregates, then explains the structured result. Arithmetic is never delegated to the model.

## Config

`backend/.env` (never the frontend):

```
AI_PROVIDER=fallback
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2
```
