from datetime import date

from app.tariff_engine.calculator import calculate_bill
from app.tariff_engine.loader import load_tariff_for_date

TARIFF = load_tariff_for_date(date(2026, 6, 1))  # any date on/after 2026-05-11


def test_general_purpose_below_threshold():
    result = calculate_bill("general_purpose", 150, TARIFF)
    assert result.band_used == "low"
    assert result.energy_cost == 150 * 27.00
    assert result.total == 150 * 27.00 + 500.00


def test_general_purpose_above_threshold():
    result = calculate_bill("general_purpose", 200, TARIFF)
    assert result.band_used == "high"
    assert result.total == 200 * 36.00 + 1600.00


def test_general_purpose_exactly_at_threshold():
    # threshold itself (180) should use the LOW band, since max_kwh: 180 is inclusive
    result = calculate_bill("general_purpose", 180, TARIFF)
    assert result.band_used == "low"


def test_industrial_below_threshold():
    result = calculate_bill("industrial", 250, TARIFF)
    assert result.total == 250 * 9.00 + 300.00


def test_hotel_above_threshold():
    result = calculate_bill("hotel", 350, TARIFF)
    assert result.total == 350 * 18.00 + 800.00


def test_unknown_category_raises():
    try:
        calculate_bill("bakery", 100, TARIFF)
        assert False, "should have raised"
    except ValueError:
        pass