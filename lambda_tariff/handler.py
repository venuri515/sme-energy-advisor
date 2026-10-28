"""AWS Lambda handler: recalculates a Sri Lankan SME electricity bill.
Standard library only, so the deployment package stays tiny."""
import json
import time
from datetime import date
from pathlib import Path

from calculator import calculate_bill  # copied from app/tariff_engine by scripts/build_lambda.py

_START = time.time()
_calls = 0

# Runs once per cold start. Warm invocations reuse these (that is the point of the lesson).
TARIFFS = sorted(
    (json.loads(p.read_text(encoding="utf-8")) for p in (Path(__file__).parent / "tariffs").glob("lk_*.json")),
    key=lambda t: t["effective_from"],
)


def _tariff_for(day: date) -> dict:
    usable = [t for t in TARIFFS if date.fromisoformat(t["effective_from"]) <= day]
    if not usable:
        raise ValueError(f"No tariff in force on {day}")
    return usable[-1]


def _reply(status: int, body: dict) -> dict:
    return {"statusCode": status, "headers": {"content-type": "application/json"}, "body": json.dumps(body)}


def lambda_handler(event, context):
    global _calls
    _calls += 1
    try:
        data = event if "kwh" in event else json.loads(event.get("body") or "{}")
        category, kwh = data["category"], float(data["kwh"])
        bill_date = date.fromisoformat(data["bill_date"])
        tariff = _tariff_for(bill_date)
        result = calculate_bill(category, kwh, tariff)
    except (KeyError, ValueError, TypeError) as exc:
        return _reply(400, {"error": str(exc)})

    out = {
        "calculated_amount_lkr": result.total,
        "tariff_band": result.band_used,
        "tariff_effective_from": tariff["effective_from"],
        "invocation_number_on_this_container": _calls,
        "container_age_seconds": round(time.time() - _START, 1),
    }
    submitted = data.get("submitted_amount")
    if submitted is not None:
        out["difference_lkr"] = round(float(submitted) - result.total, 2)
    return _reply(200, out)