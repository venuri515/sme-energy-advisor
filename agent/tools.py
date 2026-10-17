"""Agent tools: thin wrappers around the existing tariff, carbon, forecast and savings code."""
from datetime import date

from strands import tool

from app.forecasting.baseline import forecast_next_month
from app.recommendations.rules import generate_suggestions
from app.tariff_engine.calculator import calculate_bill
from app.tariff_engine.carbon import calculate_carbon_kg
from app.tariff_engine.loader import load_tariff_for_date


@tool
def check_bill(category: str, kwh: float, bill_date: str, submitted_amount: float | None = None) -> dict:
    """Recalculate a Sri Lankan electricity bill from the official tariff and compare it
    with the amount the customer was actually charged.

    Args:
        category: Tariff category: general_purpose, industrial or hotel.
        kwh: Units consumed in the month.
        bill_date: Billing month start, as YYYY-MM-DD.
        submitted_amount: Amount on the customer's bill in LKR, if they gave one.
    """
    tariff = load_tariff_for_date(date.fromisoformat(bill_date))
    result = calculate_bill(category, kwh, tariff)
    out = {
        "calculated_amount_lkr": result.total,
        "tariff_band": result.band_used,
        "tariff_effective_from": tariff["effective_from"],
    }
    if submitted_amount is not None:
        out["mismatch_lkr"] = round(result.total - submitted_amount, 2)
    return out


@tool
def carbon_footprint(kwh: float) -> dict:
    """Estimate CO2 emissions in kg for the given electricity use in kWh."""
    return {"carbon_kg": calculate_carbon_kg(kwh)}


@tool
def forecast_usage(recent_kwh: list[float]) -> dict:
    """Forecast next month's kWh from a list of previous months, oldest first (at least 2)."""
    result = forecast_next_month(recent_kwh)
    return {"predicted_kwh": result.predicted_kwh, "method": result.method}


@tool
def savings_tips(category: str, kwh: float, bill_date: str, recent_kwh: list[float] | None = None) -> dict:
    """Give savings suggestions, such as being just over a tariff band threshold."""
    tariff = load_tariff_for_date(date.fromisoformat(bill_date))
    tips = generate_suggestions(kwh=kwh, category=category, tariff=tariff, recent_kwh=recent_kwh)
    return {"suggestions": [{"title": t.title, "detail": t.detail} for t in tips]}