# Implementation Plan — Daybook

A local-first personal expense journal for Windows. Not an accounting system.

## Goal

Type what you spent in natural language. The app extracts amount, merchant, category, and date; saves it; and shows where money went this month.

## Stack

- **Desktop shell:** Electron + Desktop shortcut; NSIS / portable `.exe` via `npm run build:win`
- **Backend:** FastAPI + SQLite (local user-data directory)
- **Frontend:** React + TypeScript + Vite
- **Money:** integer cents in SQLite; `Decimal` in Python; no float arithmetic
- **AI:** `ExpenseParser` interface — OpenAI / Anthropic / Ollama / deterministic fallback
- **Product name:** Daybook

## Design

Calm stationery ledger, not a crypto dashboard.

- Paper `#F4F1EB` · Ink `#241F1C` · Sage `#4A6B5C` · Spend `#9A4A32` · Line `#DDD6CC` · Surface `#FFFcf7`
- Display: Source Serif 4 (monthly total, like a receipt)
- UI: Outfit · Amounts: IBM Plex Mono
- Signature: oversized month total as a receipt line, with a quiet one-line “What did you spent?” composer

## Steps

1. Project scaffold, env, gitignore
2. SQLite schema, seed categories, money/date helpers
3. Expense CRUD, soft-delete, duplicate detection, merchant rules
4. Monthly analytics (totals, categories, daily, trends)
5. Fallback parser + LLM parser abstraction
6. Assistant: intent → DB query → deterministic math → explanation
7. React desktop UI (dashboard, expenses, insights, settings)
8. Electron shell that starts FastAPI and loads the UI
9. Tests + docs + run/verify

## Verification

- `pytest` in `backend/`
- `npm run build` in `frontend/`
- `npm run dev` launches desktop window
- Parse `"Spent $23.50 on dinner at Chipotle"` → $23.50 / Food & Dining / Chipotle / today

## Risks

- No AI API key: fallback parser must still work
- Python 3.14 package wheels
- Packaging a Python sidecar into a signed Mac app (dev uses system/venv Python)

## V1 vs later

**V1:** parse, save/edit/delete, categories, month nav, totals, charts, search, merchant learning, insights, assistant, CSV export, dark mode, settings.

**Shipped light, not blocking:** budgets, recurring/subscriptions.

**V2:** receipt photos, CSV bank import, automated backups.
