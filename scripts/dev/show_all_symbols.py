import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

with open("reviews/symbol_inventory.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for item in data["findings"]:
    if item["classification"] == "decorative" and ("modules" in item["file"] or "app.py" in item["file"]):
        print(f"{item['file']}:{item['line']} | {repr(item['symbol'])} | {item['context']}")
