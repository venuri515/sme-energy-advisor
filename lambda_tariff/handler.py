"""AWS Lambda handler for the SME Energy Advisor.
Two jobs, chosen by the event:
  {"category", "kwh", "bill_date", ["submitted_amount"]}  -> recalculate one bill (standard library only)
  {"business": "sunrise-bakery"}                          -> read recent bills from DynamoDB and forecast next month
The DynamoDB part needs the execution role to allow dynamodb:Query on the table, and TABLE_NAME set."""
import json
import os
import time
from datetime import date

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from baseline import forecast_next_month  # copied from app/forecasting by scripts/build_lambda.py
from calculator import calculate_bill      # copied from app/tariff_engine by scripts/build_lambda.py
from pathlib import Path

_START = time.time()
_calls = 0
_table = None

# Runs once per cold start. Warm invocations reuse these.
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


def _get_table():
    global _table
    if _table is None:  # config comes from an environment variable, not from the code
        _table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
    return _table


def _num(value):
    return float(value) if value is not None else None


def _business_summary(slug: str, limit: int = 6) -> dict:
    resp = _get_table().query(
        KeyConditionExpression=Key("pk").eq(f"BIZ#{slug}") & Key("sk").begins_with("BILL#"),
        ScanIndexForward=False,  # newest first
        Limit=limit,
    )
    items = list(reversed(resp["Items"]))  # oldest first, which is what the forecast wants
    if not items:
        return _reply(404, {"error": f"no bills found for {slug}"})
    bills = []
    for it in items:
        calc, charged = _num(it.get("calculated_amount")), _num(it.get("submitted_amount"))
        bills.append({
            "month": it["sk"].split("#", 1)[1], "kwh": _num(it["kwh"]), "our_calc_lkr": calc,
            "charged_lkr": charged,
            "difference_lkr": round(charged - calc, 2) if calc is not None and charged is not None else None,
            "source": it.get("source"),
        })
    out = {
        "business": slug,
        "bills": bills,
        "possible_overcharges": [b["month"] for b in bills if (b["difference_lkr"] or 0) > 1],
    }
    if len(bills) >= 2:
        f = forecast_next_month([b["kwh"] for b in bills])
        out["forecast_next_month_kwh"] = f.predicted_kwh
        out["forecast_method"] = f.method
    return _reply(200, out)


def lambda_handler(event, context):
    global _calls
    _calls += 1
    try:
        data = event if ("kwh" in event or "business" in event) else json.loads(event.get("body") or "{}")
        if "business" in data:
            return _business_summary(str(data["business"]))
        category, kwh = data["category"], float(data["kwh"])
        tariff = _tariff_for(date.fromisoformat(data["bill_date"]))
        result = calculate_bill(category, kwh, tariff)
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        return _reply(403 if "AccessDenied" in code else 500, {"error": code, "detail": exc.response["Error"]["Message"]})
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