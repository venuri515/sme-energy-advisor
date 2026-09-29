"""Simple linear-trend forecast: fits a straight line through recent kWh values
and projects one step ahead. This is the baseline forecast, to be compared
against Prophet/XGBoost later if time allows.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ForecastResult:
    predicted_kwh: float
    method: str
    based_on_months: int


def forecast_next_month(recent_kwh: list[float]) -> ForecastResult:
    """Fit a straight line (least-squares) through recent_kwh and project one point ahead.

    recent_kwh must be in chronological order (oldest first).
    """
    n = len(recent_kwh)
    if n < 2:
        raise ValueError("Need at least 2 months of data to forecast")

    x = list(range(n))
    x_mean = sum(x) / n
    y_mean = sum(recent_kwh) / n

    numerator = sum((x[i] - x_mean) * (recent_kwh[i] - y_mean) for i in range(n))
    denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

    slope = numerator / denominator if denominator != 0 else 0
    intercept = y_mean - slope * x_mean

    next_x = n  # the next point in the sequence
    predicted = intercept + slope * next_x

    return ForecastResult(
        predicted_kwh=max(0, round(predicted, 1)),  # consumption can't be negative
        method="linear_trend",
        based_on_months=n,
    )