from datetime import date

from app.recommendations.rules import (
    check_threshold_proximity,
    check_rising_trend,
    check_bill_mismatch,
    generate_suggestions,
)
from app.tariff_engine.loader import load_tariff_for_date

TARIFF = load_tariff_for_date(date(2026, 6, 1))


def test_threshold_proximity_fires_when_close():
    result = check_threshold_proximity(190, "general_purpose", TARIFF)
    assert result is not None
    assert result.priority == "high"


def test_threshold_proximity_does_not_fire_when_far():
    result = check_threshold_proximity(400, "general_purpose", TARIFF)
    assert result is None


def test_threshold_proximity_does_not_fire_below_threshold():
    result = check_threshold_proximity(100, "general_purpose", TARIFF)
    assert result is None


def test_rising_trend_fires_on_consistent_increase():
    result = check_rising_trend([100, 150, 200])
    assert result is not None
    assert result.priority == "medium"


def test_rising_trend_does_not_fire_on_mixed_pattern():
    result = check_rising_trend([200, 150, 180])
    assert result is None


def test_rising_trend_needs_three_months():
    result = check_rising_trend([100, 150])
    assert result is None


def test_bill_mismatch_fires_on_large_gap():
    result = check_bill_mismatch(mismatch=500, calculated_amount=2000)
    assert result is not None


def test_bill_mismatch_does_not_fire_on_small_gap():
    result = check_bill_mismatch(mismatch=50, calculated_amount=2000)
    assert result is None


def test_generate_suggestions_combines_rules():
    suggestions = generate_suggestions(
        kwh=190,
        category="general_purpose",
        tariff=TARIFF,
        recent_kwh=[100, 150, 190],
        mismatch=500,
        calculated_amount=2000,
    )
    assert len(suggestions) == 3