"""Build tariff_lambda.zip. Run from the project root:  python scripts/build_lambda.py
Converts config/tariffs/lk_*.yaml to JSON and bundles it with handler.py and calculator.py.
Uses zipfile so the paths inside the zip use forward slashes (Compress-Archive on Windows does not)."""
import json
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tariff_lambda.zip"

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    z.write(ROOT / "lambda_tariff" / "handler.py", "handler.py")
    z.write(ROOT / "app" / "tariff_engine" / "calculator.py", "calculator.py")
    for path in sorted((ROOT / "config" / "tariffs").glob("lk_*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        z.writestr(f"tariffs/{path.stem}.json", json.dumps(data))
        print("bundled", path.name)

print(f"wrote {OUT.name} ({OUT.stat().st_size} bytes)")