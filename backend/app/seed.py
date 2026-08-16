from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Category, UserSetting

DEFAULT_CATEGORIES: list[tuple[str, str]] = [
    ("Food & Dining", "utensils"),
    ("Groceries", "shopping-basket"),
    ("Transportation", "car"),
    ("Shopping", "bag"),
    ("Entertainment", "clapperboard"),
    ("Housing", "home"),
    ("Utilities", "plug"),
    ("Subscriptions", "repeat"),
    ("Education", "graduation-cap"),
    ("Health", "heart-pulse"),
    ("Travel", "plane"),
    ("Personal Care", "sparkles"),
    ("Gifts", "gift"),
    ("Bills", "file-text"),
    ("Insurance", "shield"),
    ("Pets", "paw-print"),
    ("Other", "circle"),
]

DEFAULT_SETTINGS: dict[str, str] = {
    "default_currency": "USD",
    "timezone": "America/Chicago",
    "week_start": "sunday",
    "theme": "system",
    "ai_provider": "fallback",
    "auto_save_ai": "false",
}

SUBCATEGORIES: dict[str, list[str]] = {
    "Food & Dining": ["Restaurants", "Coffee", "Fast Food", "Delivery"],
    "Transportation": ["Gas", "Rideshare", "Parking", "Public Transit", "Car Maintenance"],
    "Shopping": ["Clothing", "Electronics", "Household", "Online Shopping"],
    "Subscriptions": ["Streaming", "Software", "Memberships"],
}


def seed_defaults(db: Session) -> None:
    existing = {row.name for row in db.query(Category).all()}
    for name, icon in DEFAULT_CATEGORIES:
        if name not in existing:
            db.add(Category(name=name, icon=icon, is_custom=False))
    existing_keys = {row.key for row in db.query(UserSetting).all()}
    for key, value in DEFAULT_SETTINGS.items():
        if key not in existing_keys:
            db.add(UserSetting(key=key, value=value))
    db.commit()


def get_setting(db: Session, key: str, default: str = "") -> str:
    row = db.get(UserSetting, key)
    if row is None:
        return default
    return row.value


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.get(UserSetting, key)
    if row is None:
        db.add(UserSetting(key=key, value=value))
    else:
        row.value = value
