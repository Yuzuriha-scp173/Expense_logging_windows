from datetime import date

from app.services.dates import month_bounds, parse_natural_date, previous_month, resolve_expense_date, shift_month


def test_yesterday_and_today():
    today = date(2026, 8, 15)
    assert parse_natural_date("yesterday I spent 40 dollars on gas", today) == date(2026, 8, 14)
    assert parse_natural_date("Coffee $6.25 this morning", today) == date(2026, 8, 15)
    assert parse_natural_date("last night pizza", today) == date(2026, 8, 14)
    assert resolve_expense_date("Spent $25 on dinner", today) == today


def test_last_friday():
    today = date(2026, 8, 15)  # Saturday
    assert parse_natural_date("last Friday", today) == date(2026, 8, 14)


def test_named_and_numeric_dates():
    today = date(2026, 8, 15)
    assert parse_natural_date("Paid rent $1,500 on August 1.", today) == date(2026, 8, 1)
    assert parse_natural_date("spent 20 on 8/10", today) == date(2026, 8, 10)


def test_month_boundaries_and_year_wrap():
    start, end = month_bounds(2026, 8)
    assert start == date(2026, 8, 1)
    assert end == date(2026, 8, 31)
    assert previous_month(2026, 1) == (2025, 12)
    assert shift_month(2025, 12, 1) == (2026, 1)
