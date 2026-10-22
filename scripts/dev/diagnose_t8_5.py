import sys
import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from modules.watchman.client import WatchmanClient
from modules.screening.tiering import screen_query_all_lists, AIRLINE_ALIASES_CSV

client = WatchmanClient(engine="python")

print("=" * 80)
print("T8-5 DIAGNOSIS: ALIAS EXPANSION SAFETY")
print("=" * 80)

# 1. Read airline_aliases.csv
carrier_rows = []
with open(AIRLINE_ALIASES_CSV, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for r in reader:
        carrier_rows.append(r)

print(f"Loaded {len(carrier_rows)} airline groups from {AIRLINE_ALIASES_CSV}")

hits_from_expansion = []

for row in carrier_rows:
    canonical = row.get("canonical airline", "").strip()
    aliases = [a.strip() for a in row.get("aliases", "").split(";") if a.strip()]
    
    # Screen canonical name
    res = screen_query_all_lists(canonical, client=client, query_type="airline")
    for src, l_res in res.items():
        all_cands = l_res.get("all_candidates", [])
        for cand in all_cands:
            if cand.get("expanded_from"):
                hits_from_expansion.append({
                    "queried_carrier": canonical,
                    "src": src,
                    "alias_used": cand.get("expanded_from"),
                    "source_id": cand.get("source_id"),
                    "primary_name": cand.get("primary_name"),
                    "matched_name": cand.get("matched_name"),
                    "entity_type": cand.get("entity_type"),
                    "tier": cand.get("tier"),
                    "score": cand.get("score"),
                    "reason": cand.get("reason"),
                })

print(f"\nTotal hits derived via expanded_from: {len(hits_from_expansion)}")
for idx, hit in enumerate(hits_from_expansion, 1):
    print(f"[{idx}] Carrier '{hit['queried_carrier']}' on {hit['src']}:")
    print(f"    Alias Used (expanded_from): '{hit['alias_used']}'")
    print(f"    Matched Record: ID {hit['source_id']} - '{hit['matched_name']}' (Primary: '{hit['primary_name']}')")
    print(f"    Entity Type: {hit['entity_type']} | Score: {hit['score']:.4f} | Tier: {hit['tier']} | Reason: {hit['reason']}")

print("=" * 80)
