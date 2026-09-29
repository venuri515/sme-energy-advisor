"""Bill calculation for volume-differentiated (VDMC) tariff categories."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BillResult:
    category: str
    kwh: float
    band_used: str          # "low" or "high"
    energy_charge_rate: float
    energy_cost: float
    fixed_charge: float
    total: float


def calculate_bill(category: str, kwh: float, tariff: dict) -> BillResult:
    if kwh < 0:
        raise ValueError("kwh cannot be negative")

    try:
        cat = tariff["categories"][category]
    except KeyError:
        raise ValueError(f"Unknown tariff category: {category!r}")

    threshold = cat["threshold_kwh"]
    band_name = "low" if kwh <= threshold else "high"
    band = cat["bands"][band_name]

    energy_cost = kwh * band["energy_charge"]
    fixed_charge = band["fixed_charge"]
    total = energy_cost + fixed_charge

    return BillResult(
        category=category,
        kwh=kwh,
        band_used=band_name,
        energy_charge_rate=band["energy_charge"],
        energy_cost=energy_cost,
        fixed_charge=fixed_charge,
        total=total,
    )