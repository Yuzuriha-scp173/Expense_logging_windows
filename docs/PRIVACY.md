# Privacy

Expense data is personal financial history. Daybook is local-first.

## Where data lives

SQLite on disk in the OS application-support folder. Nothing is uploaded unless you enable a cloud AI provider.

## What leaves the machine

If `AI_PROVIDER` is `openai` or `anthropic`, **only the sentence you just typed** (plus today’s date and currency) is sent, to extract a structured expense or a query intent.

The app does not send:

- your full expense history
- dashboard totals for the model to “recalculate”
- API keys to the frontend (keys stay in backend environment variables)

Ollama and the built-in parser stay on-device.

## Totals

Monthly totals, category shares, and assistant answers that include dollar amounts are computed in Python/SQLite.

## Auth

Single-user local app. No accounts in V1. If you later host this on a public server, add real authentication and per-user rows before exposing it.

## Backup

Use Settings → Copy database backup, or copy `expenses.db` yourself. Treat backups like any other financial file.
