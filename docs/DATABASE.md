# Database

Engine: SQLite, WAL mode, foreign keys on.

Default location (Mac): `~/Library/Application Support/Daybook/expenses.db`

Override: `EXPENSE_DATA_DIR`.

## Tables

### expenses

| Column | Type | Notes |
| --- | --- | --- |
| id | INTEGER PK | |
| amount_cents | INTEGER | never float |
| currency | TEXT | default USD |
| date | DATE | canonical calendar date |
| merchant | TEXT | nullable |
| description | TEXT | nullable |
| category_id | FK | |
| subcategory | TEXT | optional |
| payment_method | TEXT | optional |
| notes | TEXT | |
| source | TEXT | AI_TEXT, MANUAL, RECEIPT, IMPORT |
| category_uncertain | BOOL | |
| is_recurring | BOOL | |
| created_at / updated_at | DATETIME | |
| deleted_at | DATETIME | soft delete |

Indexes: `date`, `category_id`, `merchant`, `deleted_at`.

### categories

id, name, icon, parent_category_id, is_custom, created_at.

Seeded: Food & Dining, Groceries, Transportation, Shopping, Entertainment, Housing, Utilities, Subscriptions, Education, Health, Travel, Personal Care, Gifts, Bills, Insurance, Pets, Other.

### merchant_rules

merchant_pattern (normalized lowercase), preferred_category, preferred_subcategory.

Written when you correct a categorized expense that has a merchant.

### user_settings

key/value: currency, timezone, week_start, theme, ai_provider, auto_save_ai.

### budgets

category_id, month (YYYY-MM), amount_cents.

### recurring_expenses

Reserved for confirmed recurring items. Detection currently derives from expense history.

## Backup

`POST /api/backup` copies the SQLite file into `backups/` under the data directory.
CSV export is `GET /api/export.csv`.
