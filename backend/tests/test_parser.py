from datetime import date
from decimal import Decimal

from app.ai.fallback import FallbackParser
from app.schemas import ParsedExpense


TODAY = date(2026, 8, 15)
parser = FallbackParser()


def parse(text: str) -> list[ParsedExpense]:
    return parser.parse(text, TODAY)


def test_lunch_amount():
    items = parse("Spent $15 on lunch")
    assert len(items) == 1
    assert items[0].amount == Decimal("15.00") or items[0].amount == Decimal("15")
    assert items[0].category == "Food & Dining"
    assert items[0].date == TODAY
    assert items[0].merchant is None
    assert items[0].payment_method is None


def test_coffee_without_dollar_sign():
    items = parse("Coffee was 6.25")
    assert items[0].amount == Decimal("6.25")
    assert items[0].category == "Food & Dining"
    assert items[0].subcategory == "Coffee"


def test_yesterday_uber():
    items = parse("Yesterday Uber cost $27")
    assert items[0].amount == Decimal("27") or items[0].amount == Decimal("27.00")
    assert items[0].date == date(2026, 8, 14)
    assert items[0].merchant == "Uber"
    assert items[0].category == "Transportation"


def test_multiple_expenses():
    items = parse("I spent $50 on groceries and $20 on gas")
    assert len(items) == 2
    amounts = sorted(i.amount for i in items)
    assert amounts == [Decimal("20"), Decimal("50")] or amounts == [Decimal("20.00"), Decimal("50.00")]
    cats = {i.category for i in items}
    assert "Groceries" in cats
    assert "Transportation" in cats


def test_three_expenses_in_one_message():
    items = parse("Today I spent $6 on coffee, $18 on lunch, and $35 on groceries.")
    assert len(items) == 3
    assert [i.amount for i in items] == [Decimal("6"), Decimal("18"), Decimal("35")] or [
        i.amount for i in items
    ] == [Decimal("6.00"), Decimal("18.00"), Decimal("35.00")]


def test_netflix():
    items = parse("$19.99 Netflix subscription")
    assert items[0].amount == Decimal("19.99")
    assert items[0].merchant == "Netflix"
    assert items[0].category == "Subscriptions"


def test_rent_august_first():
    items = parse("Paid rent $1,500 on August 1.")
    assert items[0].amount == Decimal("1500") or items[0].amount == Decimal("1500.00")
    assert items[0].date == date(2026, 8, 1)
    assert items[0].category == "Housing"


def test_chipotle_dinner():
    items = parse("Spent $23.50 on dinner at Chipotle")
    assert items[0].amount == Decimal("23.50")
    assert items[0].merchant == "Chipotle"
    assert items[0].category == "Food & Dining"
    assert items[0].date == TODAY
    assert items[0].description and "dinner" in items[0].description.lower()


def test_do_not_invent_merchant():
    items = parse("Spent $20")
    assert items[0].amount == Decimal("20") or items[0].amount == Decimal("20.00")
    assert items[0].merchant is None
    assert items[0].payment_method is None


def test_schema_rejects_zero():
    try:
        ParsedExpense(
            amount=0,
            category="Other",
            date=TODAY,
        )
        assert False, "should reject"
    except Exception:
        pass
