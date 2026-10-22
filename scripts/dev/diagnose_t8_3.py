import time
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.dev.build_dossier import get_ram_usage_mb

print("=" * 60)
print("STEP A: DIAGNOSIS OF PERFORMANCE (T8-3)")
print("=" * 60)

rss_start = get_ram_usage_mb()
print(f"1. Initial Python Process RSS (idle interpreter before loading engine): {rss_start:.2f} MB")

from modules.watchman.client import WatchmanClient, get_python_engine
client = WatchmanClient(engine="python")

t0 = time.perf_counter()
eng = get_python_engine()
t_engine_load = time.perf_counter() - t0
rss_after_engine = get_ram_usage_mb()
print(f"2. Engine Load Time: {t_engine_load:.3f} s (happens lazily on FIRST SEARCH, not at app launch!)")
print(f"   Post-Engine-Load Process RSS: {rss_after_engine:.2f} MB")
print(f"   Memory increase: {rss_after_engine - rss_start:.2f} MB for in-memory EntityRecords, token inverted indices, and raw dicts.")
print(f"   Reconciliation: 23.72 MB in dossier was Python interpreter idle RSS before index load. Real working set is ~{rss_after_engine:.1f} MB.")

from modules.screening.tiering import screen_query_all_lists
t0 = time.perf_counter()
res_first = screen_query_all_lists("Jaipur International Airport Limited", client=client, query_type="organisation")
t_first_search = time.perf_counter() - t0
print(f"3. First search after engine loaded (Clean Org): {t_first_search:.3f} s")

print("\n4. Breakdown of Aeroflot Airline Search:")
from modules.screening.tiering import get_airline_alias_row, _screen_direct_all_lists
expansion_row = get_airline_alias_row("Aeroflot")
aliases = expansion_row.get("aliases", []) if expansion_row else []
print(f"   - Expansion row matched: canonical={expansion_row.get('canonical airline')}")
print(f"   - Raw aliases evaluated: {len(aliases)} aliases: {aliases}")
print(f"   - Sub-queries evaluated: {len(aliases)} aliases * 5 lists = {len(aliases) * 5} list searches")

t_direct_start = time.perf_counter()
res_direct = _screen_direct_all_lists("Aeroflot", client=client, query_type="airline")
t_direct = time.perf_counter() - t_direct_start
print(f"   - Time for direct query 'Aeroflot' across 5 lists: {t_direct:.3f} s")

total_alias_time = 0.0
for a in aliases:
    if a.strip().lower() == "aeroflot":
        continue
    t0 = time.perf_counter()
    _screen_direct_all_lists(a, client=client, query_type="airline")
    dt = time.perf_counter() - t0
    total_alias_time += dt
    print(f"     * Sub-query '{a}' across 5 lists: {dt:.3f} s")

t_full_start = time.perf_counter()
res_full = screen_query_all_lists("Aeroflot", client=client, query_type="airline")
t_full = time.perf_counter() - t_full_start
print(f"   - Total un-optimized Aeroflot airline search time: {t_full:.3f} s")
print("=" * 60)
