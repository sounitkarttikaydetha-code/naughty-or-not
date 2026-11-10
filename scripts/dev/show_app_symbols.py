import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

with open("reviews/symbol_inventory.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for item in data["findings"]:
    if item["file"] == "app.py" and item["classification"] == "decorative":
        print(f"{item['line']}: {repr(item['symbol'])} | {item['context']}")
