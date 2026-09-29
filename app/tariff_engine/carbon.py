"""Converts electricity consumption (kWh) into estimated CO2 emissions."""
from __future__ import annotations

from pathlib import Path

import yaml

EMISSION_FACTOR_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "emission_factors" / "lk_2022.yaml"
)


def load_emission_factor(path: Path = EMISSION_FACTOR_PATH) -> float:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["value_kg_co2_per_kwh"]


def calculate_carbon_kg(kwh: float, emission_factor: float | None = None) -> float:
    """Estimated kg of CO2 for a given electricity consumption."""
    if kwh < 0:
        raise ValueError("kwh cannot be negative")
    factor = emission_factor if emission_factor is not None else load_emission_factor()
    return round(kwh * factor, 2)