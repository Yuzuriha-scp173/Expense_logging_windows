# Architecture

This repository is the **Windows version** of Daybook.

Daybook is a local desktop app: Electron wraps a React UI that talks to a FastAPI process on localhost. SQLite is the source of truth. On Windows, `install.bat` places a Desktop shortcut that launches Electron in standalone mode from whatever folder you cloned.

```text
Electron window
    → React (Vite) UI
        → HTTP /api/*
            → FastAPI
                → SQLite (user data dir)
                → ExpenseParser (OpenAI | Anthropic | Ollama | fallback)
```

## Why this split

- Python is a good fit for Decimal money math, date parsing, and optional LLM HTTP calls.
- React is a good fit for a calm dashboard.
- Electron is the practical path to a Mac `.app` now and a Windows `.exe` later.

## Process model

**Development (`npm run dev`)**

- Uvicorn serves the API on port 8765.
- Vite serves the UI on 5173 and proxies `/api`.
- Electron loads the Vite URL. It does not spawn Python in dev.

**Packaged app**

- Electron starts Uvicorn on an ephemeral localhost port.
- `EXPENSE_DATA_DIR` is the OS userData folder.
- `DAYBOOK_UI` points at the built frontend so FastAPI can serve it.

## Money

Amounts are stored as **integer cents**. Python converts with `Decimal` and `ROUND_HALF_UP`. Charts and the LLM never add money. Monthly totals are `SUM(amount_cents)` in SQL/Python.

## AI flow

**Capture**

```text
typed sentence → ExpenseParser.parse → Pydantic schema → confirm card → INSERT
```

Malformed model JSON is rejected. Merchant rules applied after parse override generic classification.

**Questions**

```text
question → intent JSON → database query → deterministic totals → short explanation
```

The model does not receive a dump of transactions to “add up.”

## Desktop packaging notes

Mac: `npm run build:mac` (electron-builder dmg/zip).

Windows: `npm run build:win` (NSIS). Python 3 plus `backend/.venv` still required unless you freeze the API with PyInstaller into `daybook-api.exe` and drop it into `backend/`.
