# Daybook (Windows version)

Windows build of Daybook, a local-first personal expense journal. Type what you spent. Daybook files it. You can see where the money went this month.

This is the **Windows version**. The macOS repo is [Expense_logging](https://github.com/Yuzuriha-scp173/Expense_logging).

This is not accounting software. It is ChatGPT-style capture plus a quiet monthly dashboard.

## First-time setup (any folder)

You can clone or unzip this project **anywhere** on the PC.

You need:

- [Node.js](https://nodejs.org/)
- [Python 3](https://www.python.org/downloads/) — check **Add python.exe to PATH** when installing

From GitHub:

```bat
git clone https://github.com/Yuzuriha-scp173/Expense_logging_windows.git
cd Expense_logging_windows
install.bat
```

Or unzip the downloaded folder, open it, and double-click **install.bat**.

That installs dependencies, builds the app, and puts a **Daybook** shortcut on your Desktop. Double-click it to start. The shortcut remembers this project folder, even if it is not on the Desktop.

If you later move the project folder, run `install.bat` again from the new location.

### Manual commands (same result)

```bat
python -m venv backend\.venv
backend\.venv\Scripts\pip install -r backend\requirements.txt
cd frontend && npm install && cd ..
npm install
npm run install:desktop
```

## Build a Windows .exe installer

On a Windows PC, after the setup above:

```bat
npm run build:win
```

This writes installer and portable EXEs into the `release` folder, for example:

- `Daybook Setup 1.0.0.exe` — NSIS installer (desktop shortcut included)
- `Daybook 1.0.0.exe` — portable EXE

The Python backend still needs Python 3 on the machine (or a future bundled `daybook-api.exe`). The Desktop shortcut from `install.bat` is the supported one-click path today.

## Start from a terminal (development)

From the project folder:

```bat
npm run dev
```

SQLite lives at `%APPDATA%\Daybook\expenses.db`.

UI only (no desktop window): `npm run dev:web` then open `http://127.0.0.1:5173`.

## Try it

In the top field:

```text
Spent $23.50 on dinner at Chipotle
```

Confirm the card, save. Monthly totals and charts update immediately.

Multiple expenses in one line also work:

```text
Today I spent $6 on coffee, $18 on lunch, and $35 on groceries.
```

The built-in parser works with no API key. Optional cloud/local models: copy `.env.example` to `backend/.env` and set `AI_PROVIDER` to `openai`, `anthropic`, or `ollama`.

## Tests

```bat
cd backend
.venv\Scripts\python -m pytest -q
```

## Privacy

Expense text is parsed locally by default. Cloud AI, if enabled, receives only the sentence you typed — never your full history. Totals always come from SQLite, never from the model. Details: `docs/PRIVACY.md`.
