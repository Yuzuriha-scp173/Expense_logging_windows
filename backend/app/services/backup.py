from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import shutil

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Expense
from app.services.expenses import active_expenses
from app.services.money import cents_to_dollars


CSV_FIELDS = ["Date", "Merchant", "Description", "Category", "Subcategory", "Amount", "Currency", "Payment Method", "Notes", "Source"]


def expenses_to_csv(db: Session) -> str:
    rows = [",".join(CSV_FIELDS)]
    expenses = list(db.scalars(active_expenses().order_by(Expense.date.asc(), Expense.id.asc())).unique().all())
    for e in expenses:
        values = [
            e.date.isoformat(),
            e.merchant or "",
            e.description or "",
            e.category.name if e.category else "",
            e.subcategory or "",
            str(cents_to_dollars(e.amount_cents)),
            e.currency,
            e.payment_method or "",
            (e.notes or "").replace("\n", " "),
            e.source,
        ]
        rows.append(",".join(_csv_cell(v) for v in values))
    return "\n".join(rows) + "\n"


def _csv_cell(value: str) -> str:
    if any(ch in value for ch in [",", '"', "\n"]):
        return '"' + value.replace('"', '""') + '"'
    return value


def backup_database(destination: Path | None = None) -> Path:
    settings = get_settings()
    src = settings.db_path
    if destination is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        destination = settings.expense_data_dir / "backups" / f"expenses-{stamp}.db"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, destination)
    return destination
