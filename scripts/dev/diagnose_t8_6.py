import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from modules.watchman.client import WatchmanClient
from modules.screening.tiering import screen_query_all_lists
from modules.engine.engine import PythonEngine

client = WatchmanClient(engine="python")
engine = client._engine if hasattr(client, "_engine") and client._engine else PythonEngine()

print("=" * 80)
print("T8-6 DIAGNOSIS: SHORT NAMES AND NON-LATIN INPUT")
print("=" * 80)

# Check indexing and IDF/DF rules in engine
total_recs = sum(len(recs) for recs in engine.records_by_source.values())
print("Engine stats: total records across all sources =", total_recs)

# Check IDF/DF rules
short_queries = ["VTB", "S7", "IRGC", "ZTE", "Bank", "Air", "International", "Commercial Bank Company Limited"]

for q in short_queries:
    print(f"\n--- Query: '{q}' (Organisation) ---")
    norm_text = q.lower().strip()
    norm_tokens = norm_text.split()
    print(f"Tokens: {norm_tokens}")
    for src in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]:
        t_idx = engine.token_index_by_source.get(src, {})
        part_size = len(engine.records_by_source.get(src, []))
        for t in norm_tokens:
            hits = t_idx.get(t, [])
            df = len(hits) / part_size if part_size else 0.0
            print(f"  [{src}] Token '{t}': hit count = {len(hits)} / {part_size}, DF = {df:.4f} ({df*100:.2f}%)")
    
    # Screen across lists
    res = screen_query_all_lists(q, client=client, query_type="organisation")
    for src in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]:
        bh = res[src]["best_hit"]
        reds = len(res[src]["red_hits"])
        oranges = len(res[src]["orange_hits"])
        print(f"  [{src}] {bh['tier_icon']} {bh['tier']} (Score: {bh['score']:.4f}, Reason: {bh.get('reason')}, Primary: '{bh['primary_name']}', Matched: '{bh['matched_name']}', ID: {bh.get('source_id')}) | Reds: {reds}, Oranges: {oranges}")

print("=" * 80)
