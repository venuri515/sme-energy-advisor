"""Rule-based savings suggestions, using only data already computed elsewhere."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Suggestion:
    title: str
    detail: str
    priority: str  # "high" | "medium" | "low"


def check_threshold_proximity(kwh: float, category: str, tariff: dict) -> Suggestion | None:
    """Flag if consumption is just above the VDMC threshold, where a small cut saves a lot."""
    cat = tariff["categories"].get(category)
    if cat is None:
        return None

    threshold = cat["threshold_kwh"]
    margin = kwh - threshold

    # "just above" = within 10% of the threshold, or within 10 kWh, whichever is larger
    band_width = max(threshold * 0.10, 10)

    if 0 < margin <= band_width:
        low_band = cat["bands"]["low"]
        high_band = cat["bands"]["high"]
        current_total = kwh * high_band["energy_charge"] + high_band["fixed_charge"]
        at_threshold_total = threshold * low_band["energy_charge"] + low_band["fixed_charge"]
        potential_saving = round(current_total - at_threshold_total, 2)

        return Suggestion(
            title="Close to the next tariff band",
            detail=(
                f"Usage was {kwh:.0f} kWh, just {margin:.0f} kWh above the "
                f"{threshold:.0f} kWh threshold. Cutting {margin:.0f} kWh could save "
                f"about LKR {potential_saving:,.0f} this month, since the whole bill "
                f"drops to the lower rate."
            ),
            priority="high",
        )
    return None


def check_rising_trend(recent_kwh: list[float]) -> Suggestion | None:
    """Flag if the last 3 months show a consistent upward trend."""
    if len(recent_kwh) < 3:
        return None

    last_three = recent_kwh[-3:]
    if last_three[0] < last_three[1] < last_three[2]:
        increase_pct = (last_three[2] - last_three[0]) / last_three[0] * 100
        return Suggestion(
            title="Consumption has been rising",
            detail=(
                f"Usage has increased for 3 months in a row "
                f"({last_three[0]:.0f} -> {last_three[1]:.0f} -> {last_three[2]:.0f} kWh), "
                f"up {increase_pct:.0f}% overall. Worth checking what changed."
            ),
            priority="medium",
        )
    return None


def check_bill_mismatch(mismatch: float | None, calculated_amount: float) -> Suggestion | None:
    """Flag if the calculated bill differs a lot from what was actually submitted/charged."""
    if mismatch is None or calculated_amount == 0:
        return None

    mismatch_pct = abs(mismatch) / calculated_amount * 100
    if mismatch_pct > 10:
        direction = "higher" if mismatch > 0 else "lower"
        return Suggestion(
            title="Bill doesn't match our calculation",
            detail=(
                f"Our calculated amount is {mismatch_pct:.0f}% {direction} than the "
                f"submitted bill. Worth checking the meter reading or bill for errors."
            ),
            priority="medium",
        )
    return None


def generate_suggestions(
    kwh: float,
    category: str,
    tariff: dict,
    recent_kwh: list[float] | None = None,
    mismatch: float | None = None,
    calculated_amount: float = 0,
) -> list[Suggestion]:
    """Run all rules and return whichever suggestions actually fired."""
    suggestions = []

    threshold_suggestion = check_threshold_proximity(kwh, category, tariff)
    if threshold_suggestion:
        suggestions.append(threshold_suggestion)

    if recent_kwh:
        trend_suggestion = check_rising_trend(recent_kwh)
        if trend_suggestion:
            suggestions.append(trend_suggestion)

    mismatch_suggestion = check_bill_mismatch(mismatch, calculated_amount)
    if mismatch_suggestion:
        suggestions.append(mismatch_suggestion)

    return suggestions