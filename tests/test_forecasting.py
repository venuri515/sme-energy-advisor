import pytest

from app.forecasting.baseline import forecast_next_month


def test_forecast_flat_data():
    result = forecast_next_month([100, 100, 100, 100])
    assert result.predicted_kwh == pytest.approx(100, abs=0.5)


def test_forecast_rising_trend():
    result = forecast_next_month([100, 150, 200])
    # trend is +50/month, so next should be ~250
    assert result.predicted_kwh == pytest.approx(250, abs=1)


def test_forecast_falling_trend():
    result = forecast_next_month([300, 200, 100])
    assert result.predicted_kwh == pytest.approx(0, abs=1)


def test_forecast_never_negative():
    result = forecast_next_month([100, 50, 0])
    assert result.predicted_kwh >= 0


def test_forecast_needs_at_least_two_points():
    with pytest.raises(ValueError):
        forecast_next_month([100])


def test_forecast_reports_method_and_count():
    result = forecast_next_month([100, 110, 120, 130])
    assert result.method == "linear_trend"
    assert result.based_on_months == 4