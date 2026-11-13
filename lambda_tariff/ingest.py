"""S3-triggered Lambda: reads an uploaded CSV of bills, calculates each one, writes the rows to DynamoDB,
and writes a small report to results/. Columns: business,category,month,kwh,charged_lkr[,source]
Triggered only by uploads/*.csv, so writing the report under results/ cannot start another run."""
import csv
import io
import json
import os
import re
import urllib.parse
from datetime import date
from decimal import Decimal
from pathlib import Path

import boto3

from calculator import calculate_bill  # copied from app/tariff_engine by scripts/build_lambda.py

TABLE = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"]) if os.environ.get("TABLE_NAME") else None
S3 = boto3.client("s3")

TARIFFS = sorted(
    (json.loads(p.read_text(encoding="utf-8")) for p in (Path(__file__).parent / "tariffs").glob("lk_*.json")),
    key=lambda t: t["effective_from"],
)
CATEGORIES = {"general_purpose", "industrial", "hotel"}
SOURCES = {"real", "synthetic", "uploaded"}
REQUIRED = {"business", "category", "month", "kwh", "charged_lkr"}
MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
MAX_BYTES = 1_000_000
MAX_ROWS = 1000


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _tariff_for(day: date):
    usable = [t for t in TARIFFS if date.fromisoformat(t["effective_from"]) <= day]
    return usable[-1] if usable else None


def _parse_row(row: dict):
    """Returns (clean values, None) or (None, reason)."""
    name = (row.get("business") or "").strip()
    category = (row.get("category") or "").strip()
    month = (row.get("month") or "").strip()
    if not _slug(name):
        return None, "business name is empty"
    if category not in CATEGORIES:
        return None, f"category must be one of {sorted(CATEGORIES)}, got '{category}'"
    if not MONTH.match(month):
        return None, f"month must look like 2026-06, got '{month}'"
    try:
        kwh, charged = float(row["kwh"]), float(row["charged_lkr"])
    except (TypeError, ValueError):
        return None, "kwh and charged_lkr must be numbers"
    if kwh < 0 or charged < 0:
        return None, "kwh and charged_lkr cannot be negative"
    source = (row.get("source") or "").strip().lower()
    return {"name": name, "slug": _slug(name), "category": category, "month": month, "kwh": kwh,
            "charged": charged, "source": source if source in SOURCES else "uploaded"}, None


def _process(bucket: str, key: str, size: int) -> dict:
    report = {"file": key, "rows_read": 0, "rows_written": 0, "rows_rejected": [], "not_calculated": [], "error": None}
    if size > MAX_BYTES:
        report["error"] = f"file is {size} bytes; the limit is {MAX_BYTES}"
    else:
        try:
            text = S3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(text))
            missing = REQUIRED - set(reader.fieldnames or [])
            if missing:
                report["error"] = f"missing columns: {sorted(missing)}"
            else:
                profiles = set()
                with TABLE.batch_writer() as batch:
                    for number, row in enumerate(reader, start=2):  # row 1 is the header
                        if number - 1 > MAX_ROWS:
                            report["error"] = f"stopped after {MAX_ROWS} rows"
                            break
                        report["rows_read"] += 1
                        clean, problem = _parse_row(row)
                        if problem:
                            report["rows_rejected"].append({"row": number, "error": problem})
                            continue
                        if clean["slug"] not in profiles:
                            batch.put_item(Item={"pk": f"BIZ#{clean['slug']}", "sk": "PROFILE", "name": clean["name"],
                                                 "category": clean["category"], "source": clean["source"]})
                            profiles.add(clean["slug"])
                        item = {"pk": f"BIZ#{clean['slug']}", "sk": f"BILL#{clean['month']}",
                                "kwh": Decimal(str(clean["kwh"])), "submitted_amount": Decimal(str(round(clean["charged"]))),
                                "source": clean["source"]}
                        tariff = _tariff_for(date.fromisoformat(clean["month"] + "-15"))
                        if tariff is None:
                            report["not_calculated"].append({"row": number, "reason": "no tariff in force for that month"})
                        else:
                            item["calculated_amount"] = Decimal(str(calculate_bill(clean["category"], clean["kwh"], tariff).total))
                            item["tariff_effective_from"] = tariff["effective_from"]
                        batch.put_item(Item=item)  # same key again just replaces the item, so re-uploading is safe
                        report["rows_written"] += 1
        except (UnicodeDecodeError, csv.Error) as exc:
            report["error"] = f"could not read the file as CSV text: {exc}"

    S3.put_object(Bucket=bucket, Key="results/" + key.split("/", 1)[-1] + ".json",
                  Body=json.dumps(report, indent=2).encode(), ContentType="application/json")
    print(json.dumps({"event": "INGEST_DONE", "file": key, "written": report["rows_written"],
                      "rejected": len(report["rows_rejected"]), "error": report["error"]}))
    return report


def lambda_handler(event, context):
    reports = []
    for record in event["Records"]:
        obj = record["s3"]["object"]
        reports.append(_process(record["s3"]["bucket"]["name"], urllib.parse.unquote_plus(obj["key"]), obj.get("size", 0)))
    return reports