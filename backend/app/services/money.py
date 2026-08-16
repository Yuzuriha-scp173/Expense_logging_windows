from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

CENTS = Decimal("0.01")
ZERO = Decimal("0.00")


def to_decimal(value: Decimal | int | str | float) -> Decimal:
    """Convert to Decimal without using binary float for money strings/ints."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "").replace("$", "")
        return Decimal(cleaned)
    # Floats are unsafe; still accept by going through string quantization.
    return Decimal(str(value))


def dollars_to_cents(amount: Decimal | int | str | float) -> int:
    quantized = to_decimal(amount).quantize(CENTS, rounding=ROUND_HALF_UP)
    return int(quantized * 100)


def cents_to_dollars(cents: int) -> Decimal:
    return (Decimal(cents) / Decimal(100)).quantize(CENTS, rounding=ROUND_HALF_UP)


def format_dollars(cents: int, currency: str = "USD") -> str:
    amount = cents_to_dollars(cents)
    sign = "-" if amount < 0 else ""
    body = f"{abs(amount):,.2f}"
    if currency == "USD":
        return f"{sign}${body}"
    return f"{sign}{body} {currency}"


def percent_change(current_cents: int, previous_cents: int) -> Decimal | None:
    if previous_cents == 0:
        return None
    current = Decimal(current_cents)
    previous = Decimal(previous_cents)
    change = ((current - previous) / previous) * Decimal(100)
    return change.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
