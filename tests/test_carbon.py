import pytest

from app.tariff_engine.carbon import calculate_carbon_kg, load_emission_factor


def test_calculate_carbon_with_explicit_factor():
    assert calculate_carbon_kg(100, emission_factor=0.4173) == 41.73


def test_calculate_carbon_loads_default_factor():
    result = calculate_carbon_kg(1000)
    assert result == pytest.approx(1000 * 0.4173, rel=1e-3)


def test_negative_kwh_raises():
    with pytest.raises(ValueError):
        calculate_carbon_kg(-5)


def test_load_emission_factor_returns_expected_value():
    assert load_emission_factor() == 0.4173