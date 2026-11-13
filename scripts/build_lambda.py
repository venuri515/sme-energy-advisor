"""Build tariff_lambda.zip and the lambda_build/ folder. Run from the project root:  python scripts/build_lambda.py
Converts config/tariffs/lk_*.yaml to JSON and bundles it with handler.py and calculator.py.
Uses zipfile so the paths inside the zip use forward slashes (Compress-Archive on Windows does not)."""
import json
import shutil
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tariff_lambda.zip"

files = {
    "handler.py": (ROOT / "lambda_tariff" / "handler.py").read_text(encoding="utf-8"),
    "ingest.py": (ROOT / "lambda_tariff" / "ingest.py").read_text(encoding="utf-8"),
    "calculator.py": (ROOT / "app" / "tariff_engine" / "calculator.py").read_text(encoding="utf-8"),
    "baseline.py": (ROOT / "app" / "forecasting" / "baseline.py").read_text(encoding="utf-8"),
}
for path in sorted((ROOT / "config" / "tariffs").glob("lk_*.yaml")):
    files[f"tariffs/{path.stem}.json"] = json.dumps(yaml.safe_load(path.read_text(encoding="utf-8")))
    print("bundled", path.name)

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for name, text in files.items():
        z.writestr(name, text)

# the same files as a plain folder, for AWS SAM (CodeUri: lambda_build/)
BUILD = ROOT / "lambda_build"
shutil.rmtree(BUILD, ignore_errors=True)
for name, text in files.items():
    target = BUILD / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")

print(f"wrote {OUT.name} ({OUT.stat().st_size} bytes) and {BUILD.name}/")