import sys
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from modules.watchman.client import WatchmanClient
from modules.screening.tiering import screen_query_all_lists

client = WatchmanClient(engine="python")

queries_to_inspect = [
    ("Mohammed Khan", "person", ["us_ofac"]),
    ("Rajesh Kumar", "person", ["uk_csl"]),
    ("Sky Bank", "organisation", ["us_ofac"]),
    ("Siberian Wellness", "organisation", ["us_ofac"]),
    ("Volga Logistics", "organisation", ["us_ofac"]),
    ("Azur Air", "airline", ["uk_csl", "eu_csl"]),
    ("UTair", "airline", ["uk_csl"]),
]

print("=" * 80)
print("T8-4 DIAGNOSIS: 7 QUERIES THAT CHANGED SINCE EARLIER ROUNDS")
print("=" * 80)

for query, q_type, target_lists in queries_to_inspect:
    print(f"\nQUERY: '{query}' (Type: {q_type})")
    res = screen_query_all_lists(query, client=client, query_type=q_type)
    for src in target_lists:
        bh = res.get(src, {}).get("best_hit", {})
        print(f"  Source List: {src}")
        print(f"    Tier: {bh.get('tier_icon')} {bh.get('tier')}")
        print(f"    Record ID: {bh.get('source_id')}")
        print(f"    Primary Name: {bh.get('primary_name')}")
        print(f"    Matched Name/Alias: {bh.get('matched_name')}")
        print(f"    Entity Type: {bh.get('entity_type')}")
        print(f"    Raw Score: {bh.get('score'):.6f}")
        print(f"    Reason Code: {bh.get('reason')}")
        print(f"    Expanded From: {bh.get('expanded_from')}")
        print(f"    Score Source: {bh.get('score_source')}")
        print(f"    Total candidates: {len(res.get(src, {}).get('all_candidates', []))}")
        # Show top 3 candidates for context
        for idx, cand in enumerate(res.get(src, {}).get("all_candidates", [])[:3]):
            print(f"      Candidate {idx+1}: {cand.get('matched_name')} (ID: {cand.get('source_id')}, Tier: {cand.get('tier_icon')} {cand.get('tier')}, Score: {cand.get('score'):.4f}, Reason: {cand.get('reason')})")

print("=" * 80)
