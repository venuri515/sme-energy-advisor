"""Loads tariff config files and picks the one that applies to a given billing date."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config" / "tariffs"


def _parse_effective_date(path: Path) -> date:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return date.fromisoformat(data["effective_from"])


def load_tariff_for_date(billing_date: date, config_dir: Path = CONFIG_DIR) -> dict:
    """Return the tariff config whose effective_from is the latest one on or before billing_date."""
    candidates = []
    for path in config_dir.glob("lk_*.yaml"):
        effective = _parse_effective_date(path)
        if effective <= billing_date:
            candidates.append((effective, path))

    if not candidates:
        raise ValueError(f"No tariff file found effective on or before {billing_date}")

    candidates.sort(key=lambda pair: pair[0])
    _, chosen_path = candidates[-1]

    with open(chosen_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)