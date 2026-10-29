"""DynamoDB data tool for the SME Energy Advisor. Run from the project root (agent environment):
    python scripts/dynamo_demo.py seed                 # realistic SYNTHETIC businesses and bills (labelled source=synthetic)
    python scripts/dynamo_demo.py recent sunrise-bakery   # newest bills for one business (one Query)
    python scripts/dynamo_demo.py import data/samples/my_bills.csv   # real bills later (business,category,month,kwh,charged_lkr)
    python scripts/dynamo_demo.py purge-synthetic      # delete every synthetic item (a Scan, on purpose)
Uses the admin profile "default" unless DYNAMO_PROFILE says otherwise."""
import csv
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import boto3
from boto3.dynamodb.conditions import Attr, Key

from app.tariff_engine.calculator import calculate_bill
from app.tariff_engine.loader import load_tariff_for_date

TABLE = "sme-advisor"
REGION = "ap-southeast-2"
MONTHS = ["2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]

# slug: (name, category, kWh per month, what the pattern is meant to show)
SYNTHETIC = {
    "sunrise-bakery":      ("Sunrise Bakery", "general_purpose", [150, 165, 172, 181, 190], "creeping over the 180 kWh band"),
    "colombo-print-shop":  ("Colombo Print Shop", "general_purpose", [140, 150, 135, 145, 138], "steady, safely under the band"),
    "galle-fashion-store": ("Galle Fashion Store", "general_purpose", [205, 198, 175, 182, 170], "flipping either side of 180 kWh"),
    "kandy-textiles":      ("Kandy Textile Works", "industrial", [260, 280, 310, 295, 330], "hovering around the 300 kWh band"),
    "galle-auto-repair":   ("Galle Auto Repair", "industrial", [220, 235, 228, 240, 252], "steady growth, under the band"),
    "lakeview-guesthouse": ("Lakeview Guesthouse", "hotel", [310, 360, 405, 380, 340], "seasonal, above 300 kWh"),
}
# Simulated "what the utility charged" when it differs from the tariff. Everything else is charged exactly our calculation.
QUIRKS = {("sunrise-bakery", "2026-10"): 9000, ("lakeview-guesthouse", "2026-08"): 1.12}  # amount, or multiplier


def get_table():
    profile = os.environ.get("DYNAMO_PROFILE", "default") or None
    return boto3.Session(profile_name=profile, region_name=REGION).resource("dynamodb").Table(TABLE)


def slugify(name):
    return "-".join(name.lower().split())


def put_bill(batch, slug, category, month, kwh, charged, source, day="15"):
    """Write one bill. charged may be None (decided after we calculate). Returns (our calc or None, charged)."""
    item = {"pk": f"BIZ#{slug}", "sk": f"BILL#{month}", "kwh": Decimal(str(kwh)), "source": source}
    calc = None
    try:
        tariff = load_tariff_for_date(date.fromisoformat(f"{month}-{day}"))
        calc = calculate_bill(category, kwh, tariff).total
        item["calculated_amount"] = Decimal(str(calc))
        item["tariff_effective_from"] = tariff["effective_from"]
    except ValueError as exc:
        print(f"  note: {month} not calculated ({exc})")
    if charged is None and calc is not None:
        charged = round(calc)
    if charged is not None:
        item["submitted_amount"] = Decimal(str(round(charged)))
    batch.put_item(Item=item)
    return calc, charged


def header():
    print(f"{'business':22} {'month':8} {'kWh':>6} {'charged':>9} {'our calc':>9} {'difference':>10}")


def row(name, month, kwh, charged, calc):
    calc_text = f"{calc:,.0f}" if calc is not None else "n/a"
    diff_text = f"{charged - calc:+,.0f}" if calc is not None and charged is not None else "n/a"
    charged_text = f"{charged:,.0f}" if charged is not None else "n/a"
    print(f"{name[:22]:22} {month:8} {kwh:>6.0f} {charged_text:>9} {calc_text:>9} {diff_text:>10}")


def seed(table):
    header()
    with table.batch_writer() as batch:
        for slug, (name, category, usage, _story) in SYNTHETIC.items():
            batch.put_item(Item={"pk": f"BIZ#{slug}", "sk": "PROFILE", "name": name, "category": category, "source": "synthetic"})
            for month, kwh in zip(MONTHS, usage):
                tariff = load_tariff_for_date(date.fromisoformat(f"{month}-15"))
                calc = calculate_bill(category, kwh, tariff).total
                quirk = QUIRKS.get((slug, month))
                charged = round(calc * quirk) if isinstance(quirk, float) else (quirk if quirk else round(calc))
                put_bill(batch, slug, category, month, kwh, charged, "synthetic")
                row(name, month, kwh, charged, calc)
    print(f"wrote {len(SYNTHETIC)} synthetic businesses and {len(SYNTHETIC) * len(MONTHS)} bills (source=synthetic)")


def import_csv(table, path):
    rows = list(csv.DictReader(open(path, newline="", encoding="utf-8-sig")))
    seen = set()
    header()
    with table.batch_writer() as batch:
        for r in rows:
            name, category, month = r["business"].strip(), r["category"].strip(), r["month"].strip()
            kwh, charged = float(r["kwh"]), float(r["charged_lkr"])
            slug = slugify(name)
            if slug not in seen:
                batch.put_item(Item={"pk": f"BIZ#{slug}", "sk": "PROFILE", "name": name, "category": category, "source": "real"})
                seen.add(slug)
            calc, _ = put_bill(batch, slug, category, month, kwh, charged, "real")
            row(name, month, kwh, charged, calc)
    print(f"imported {len(rows)} real bills for {len(seen)} business(es)")


def recent(table, slug, limit=3):
    resp = table.query(
        KeyConditionExpression=Key("pk").eq(f"BIZ#{slug}") & Key("sk").begins_with("BILL#"),
        ScanIndexForward=False,  # newest first, because the sort key is the month
        Limit=limit,
        ReturnConsumedCapacity="TOTAL",
    )
    for item in resp["Items"]:
        calc, charged = item.get("calculated_amount"), item.get("submitted_amount")
        print(item["sk"], f"{item['kwh']} kWh", f"our calc LKR {calc}" if calc is not None else "our calc n/a",
              f"| charged LKR {charged}" if charged is not None else "", f"| {item.get('source', '?')}")
    print("items returned:", resp["Count"], "| read capacity used:", resp["ConsumedCapacity"]["CapacityUnits"])


def purge_synthetic(table):
    """A Scan reads EVERY item and filters afterwards. Fine for a tiny table, costly for a big one."""
    kwargs = {"FilterExpression": Attr("source").eq("synthetic"), "ProjectionExpression": "pk, sk",
              "ReturnConsumedCapacity": "TOTAL"}
    deleted, capacity = 0, 0.0
    while True:
        resp = table.scan(**kwargs)
        capacity += resp["ConsumedCapacity"]["CapacityUnits"]
        with table.batch_writer() as batch:
            for it in resp["Items"]:
                batch.delete_item(Key={"pk": it["pk"], "sk": it["sk"]})
                deleted += 1
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    print(f"deleted {deleted} synthetic items | scan read capacity used: {capacity}")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "seed":
        seed(get_table())
    elif command == "import" and len(sys.argv) > 2:
        import_csv(get_table(), sys.argv[2])
    elif command == "recent" and len(sys.argv) > 2:
        recent(get_table(), sys.argv[2])
    elif command == "purge-synthetic":
        purge_synthetic(get_table())
    else:
        print(__doc__)