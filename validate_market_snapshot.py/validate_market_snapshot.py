import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent
REQUIRED = {"SPX": "^GSPC", "NDX": "^NDX", "DJI": "^DJI", "TA125": "^TA125.TA", "TA35": "TA35.TA"}
with open(ROOT / "data.json", encoding="utf-8") as handle:
    data = json.load(handle)
missing = []
for key in REQUIRED:
    quote = data.get("quotes", {}).get(key)
    if not isinstance(quote, dict):
        missing.append(f"{key}: missing quote")
        continue
    px = quote.get("px")
    if not isinstance(px, (int, float)) or px <= 0:
        missing.append(f"{key}: missing/invalid price")
    if not isinstance(quote.get("ch"), (int, float)):
        missing.append(f"{key}: missing/invalid change")
if missing:
    raise SystemExit("Required index quotes missing or invalid: " + "; ".join(missing))
print("All required index quotes validated: " + ", ".join(REQUIRED))
