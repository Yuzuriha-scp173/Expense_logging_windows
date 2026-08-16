from __future__ import annotations

import calendar
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def today_in_tz(tz_name: str) -> date:
    tz = ZoneInfo(tz_name)
    return datetime.now(tz).date()


def month_bounds(year: int, month: int) -> tuple[date, date]:
    last = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    total = year * 12 + (month - 1) + delta
    return total // 12, (total % 12) + 1


def previous_month(year: int, month: int) -> tuple[int, int]:
    return shift_month(year, month, -1)


def parse_month_key(value: str) -> tuple[int, int]:
    year_s, month_s = value.split("-")
    year, month = int(year_s), int(month_s)
    if month < 1 or month > 12:
        raise ValueError(f"Invalid month: {value}")
    return year, month


def last_weekday(today: date, weekday: int) -> date:
    days = (today.weekday() - weekday) % 7
    if days == 0:
        days = 7
    return today - timedelta(days=days)


def clamp_past_date(parsed: date, today: date) -> date:
    if parsed > today:
        try:
            return parsed.replace(year=parsed.year - 1)
        except ValueError:
            return parsed.replace(year=parsed.year - 1, day=28)
    return parsed


def parse_natural_date(text: str, today: date) -> date | None:
    """Parse a date expression from expense text. Returns None if none found."""
    t = text.lower().strip()

    if re.search(r"\byesterday\b", t) or re.search(r"\blast night\b", t):
        return today - timedelta(days=1)
    if re.search(r"\btoday\b", t) or re.search(r"\bthis morning\b", t):
        return today
    if re.search(r"\bthis afternoon\b", t) or re.search(r"\btonight\b", t):
        return today
    if re.search(r"\bthis evening\b", t):
        return today

    m = re.search(r"\blast\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", t)
    if m:
        return last_weekday(today, WEEKDAYS[m.group(1)])

    m = re.search(
        r"\b(january|february|march|april|may|june|july|august|september|october|november|december|"
        r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s*(\d{4}))?\b",
        t,
    )
    if m:
        month = MONTHS[m.group(1)]
        day = int(m.group(2))
        year = int(m.group(3)) if m.group(3) else today.year
        try:
            parsed = date(year, month, day)
        except ValueError:
            return None
        if not m.group(3):
            parsed = clamp_past_date(parsed, today)
        return parsed

    m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", t)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        year_raw = m.group(3)
        if year_raw:
            year = int(year_raw)
            if year < 100:
                year += 2000
        else:
            year = today.year
        # US-style M/D
        month, day = a, b
        if month > 12 and day <= 12:
            month, day = day, month
        try:
            parsed = date(year, month, day)
        except ValueError:
            return None
        if not year_raw:
            parsed = clamp_past_date(parsed, today)
        return parsed

    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", t)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    return None


def resolve_expense_date(text: str, today: date) -> date:
    found = parse_natural_date(text, today)
    return found if found else today
