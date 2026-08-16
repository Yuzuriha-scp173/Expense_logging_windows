from decimal import Decimal

from app.services.money import cents_to_dollars, dollars_to_cents, format_dollars, percent_change, to_decimal


def test_dollars_to_cents_avoids_float_error():
    assert dollars_to_cents(Decimal("18.50")) == 1850
    assert dollars_to_cents("18.50") == 1850
    assert dollars_to_cents("1,500.00") == 150000
    assert dollars_to_cents("0.10") == 10
    assert dollars_to_cents("0.1") == 10


def test_round_half_up():
    assert dollars_to_cents("1.005") == 101
    assert dollars_to_cents("1.004") == 100


def test_cents_to_dollars():
    assert cents_to_dollars(1850) == Decimal("18.50")
    assert cents_to_dollars(0) == Decimal("0.00")


def test_format():
    assert format_dollars(218457) == "$2,184.57"
    assert format_dollars(0) == "$0.00"


def test_percent_change():
    assert percent_change(52000, 42000) == Decimal("23.8")
    assert percent_change(100, 0) is None


def test_to_decimal_from_float_uses_str():
    assert to_decimal(18.5) == Decimal("18.5")
