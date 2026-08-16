from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import MerchantRule


@dataclass
class AppliedRule:
    category: str
    subcategory: str | None


def normalize_merchant(name: str) -> str:
    return " ".join(name.strip().lower().split())


def apply_merchant_rule(
    db: Session,
    merchant: str | None,
    category: str,
    subcategory: str | None,
) -> AppliedRule:
    if not merchant:
        return AppliedRule(category=category, subcategory=subcategory)
    pattern = normalize_merchant(merchant)
    rule = db.scalar(select(MerchantRule).where(MerchantRule.merchant_pattern == pattern))
    if rule is None:
        return AppliedRule(category=category, subcategory=subcategory)
    return AppliedRule(category=rule.preferred_category, subcategory=rule.preferred_subcategory or subcategory)


def remember_correction(
    db: Session,
    merchant: str,
    category: str,
    subcategory: str | None,
) -> MerchantRule:
    pattern = normalize_merchant(merchant)
    rule = db.scalar(select(MerchantRule).where(MerchantRule.merchant_pattern == pattern))
    if rule is None:
        rule = MerchantRule(
            merchant_pattern=pattern,
            preferred_category=category,
            preferred_subcategory=subcategory,
        )
        db.add(rule)
    else:
        rule.preferred_category = category
        rule.preferred_subcategory = subcategory
    db.flush()
    return rule


def list_rules(db: Session) -> list[MerchantRule]:
    return list(db.scalars(select(MerchantRule).order_by(MerchantRule.merchant_pattern)).all())


def delete_rule(db: Session, rule_id: int) -> bool:
    rule = db.get(MerchantRule, rule_id)
    if rule is None:
        return False
    db.delete(rule)
    return True


def rule_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(MerchantRule)) or 0
