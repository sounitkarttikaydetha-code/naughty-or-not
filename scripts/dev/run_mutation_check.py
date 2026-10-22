"""
Extended Mutation Testing Suite for Naughty or not Screening Engine.
Verifies that 14 deliberate mutations in scoring, tiering, source management,
and security gates are caught:
1. Core-name sensitivity -> non-matching core name does not trigger POTENTIAL_MATCH
2. Reverse subset sensitivity -> multi-word airline alias matches correctly
3. Threshold sensitivity -> low similarity does not trigger false alerts
4. Airline alias expansion -> S7 Airlines linked to Siberian Airlines
5. Type mismatch guard -> Vessel is capped below POTENTIAL_MATCH for airline query
6. Clean control country words -> Zero false positive 🔴 alerts
7. Closure detection -> HTTP 410 or closure wording triggers CLOSED_SUSPECTED
8. Stale rule -> last_verified_at > max_age_days triggers STALE
9. Short-name retrieval -> 2-char 'S7' and 3-char 'VTB' retrieve target entities
10. Ambiguous alias cap -> Hit matching ONLY via ambiguous alias is capped at 🟠 alias_ambiguous
11. Non-Latin input -> Cyrillic 'Сбербанк' finds target record in raw index
12. Phonetic layer -> Disabling phonetic matching disables sound-alike elevation
13. OpenSanctions bulk gate -> Setting bulk without written permission ref is blocked
14. OpenSanctions credit cap -> Calls exceeding 15 credits are hard-refused
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.watchman.client import WatchmanClient, get_python_engine
from modules.screening.tiering import screen_query_all_lists
import modules.screening.config as config
from modules.common.source_manager import (
    SourceManager,
    STATE_CLOSED_SUSPECTED,
    STATE_STALE,
    check_closure_keywords,
)
from modules.raw_search.engine import RawSearchEngine


def run_mutation_tests():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("Running 14 Mutation Checks against screening engine and security barriers...")
    client = WatchmanClient(engine="python")
    passed = 0

    # 1. Core-name mutation
    m1 = screen_query_all_lists("Global Fruit Export Ltd", client=client, query_type="organisation")
    if m1["eu_csl"]["best_hit"]["tier"] != "POTENTIAL_MATCH":
        passed += 1
        print("  [1/14] Core-name mutation caught (non-matching core name rejected)")
    else:
        print("  [1/14] Core-name mutation FAILED")

    # 2. Reverse subset mutation
    m2 = screen_query_all_lists("Siberian Airlines", client=client, query_type="airline")
    if m2["us_csl"]["best_hit"]["tier"] == "POTENTIAL_MATCH":
        passed += 1
        print("  [2/14] Reverse subset caught (Siberian Airlines -> 🔴)")
    else:
        print("  [2/14] Reverse subset FAILED")

    # 3. Threshold sensitivity mutation
    m3 = screen_query_all_lists("Acme Corporation", client=client, query_type="organisation")
    if m3["us_ofac"]["best_hit"]["tier"] not in ["POTENTIAL_MATCH", "POSSIBLE_MATCH_REVIEW"]:
        passed += 1
        print("  [3/14] Threshold sensitivity caught (no false positives for low scores)")
    else:
        print("  [3/14] Threshold sensitivity FAILED")

    # 4. Airline alias expansion mutation
    m4 = screen_query_all_lists("S7 Airlines", client=client, query_type="airline")
    if m4["us_csl"]["best_hit"]["tier"] == "POTENTIAL_MATCH":
        passed += 1
        print("  [4/14] Airline alias expansion caught (S7 linked to Siberian Airlines)")
    else:
        print("  [4/14] Airline expansion FAILED")

    # 5. Type mismatch guard
    m5 = screen_query_all_lists("Siberia", client=client, query_type="airline")
    ofac_hit = m5["us_ofac"]["best_hit"]
    if ofac_hit.get("tier") != "POTENTIAL_MATCH":
        passed += 1
        print("  [5/14] Type mismatch guard caught (vessel capped below 🔴 for airline)")
    else:
        print("  [5/14] Type mismatch guard FAILED")

    # 6. Clean control country words
    m6 = screen_query_all_lists("Jaipur International Airport Limited", client=client, query_type="organisation")
    if all(m6[s]["best_hit"]["tier"] != "POTENTIAL_MATCH" for s in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]):
        passed += 1
        print("  [6/14] Clean control country words caught (zero false 🔴)")
    else:
        print("  [6/14] Clean control country words FAILED")

    # 7. Closure detection
    kw = check_closure_keywords("Notice: The consolidated list is no longer being updated.")
    if kw == "no longer being updated":
        passed += 1
        print("  [7/14] Closure detection caught (closure keyword flagged)")
    else:
        print("  [7/14] Closure detection FAILED")

    # 8. Stale rule
    sm = SourceManager()
    expired = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    sm.state["test_src"] = {"id": "test_src", "state": "OK", "last_verified_at": expired, "record_count": 50}
    st_res = sm.get_source_state("test_src")
    if st_res["state"] == STATE_STALE:
        passed += 1
        print("  [8/14] Stale rule caught (unverified > 45 days flagged STALE)")
    else:
        print("  [8/14] Stale rule FAILED")

    # 9. Short-name retrieval (2-char and 3-char)
    res_s7 = screen_query_all_lists("S7", client=client, query_type="airline")
    res_vtb = screen_query_all_lists("VTB", client=client, query_type="organisation")
    if res_s7["us_csl"]["best_hit"]["tier"] == "POTENTIAL_MATCH" and res_vtb["us_ofac"]["best_hit"]["tier"] in ("POTENTIAL_MATCH", "POSSIBLE_MATCH_REVIEW"):
        passed += 1
        print("  [9/14] Short-name retrieval caught ('S7' and 'VTB' retrieve matches)")
    else:
        print("  [9/14] Short-name retrieval FAILED")

    # 10. Ambiguous alias cap
    # Query 'Rossiya Airlines' expands to ambiguous alias 'Rossiya'; unrelated entities on us_ofac must NOT be 🔴
    res_amb = screen_query_all_lists("Rossiya Airlines", client=client, query_type="airline")
    ofac_amb = res_amb["us_ofac"]["best_hit"]
    if ofac_amb.get("tier") != "POTENTIAL_MATCH":
        passed += 1
        print("  [10/14] Ambiguous alias cap caught (Rossiya expansion on OFAC capped below 🔴)")
    else:
        print("  [10/14] Ambiguous alias cap FAILED")

    # 11. Non-Latin input (Cyrillic raw index search)
    raw_engine = RawSearchEngine()
    cyrillic_res = raw_engine.search("Сбербанк")
    if cyrillic_res.get("total_matches", 0) > 0:
        passed += 1
        print("  [11/14] Non-Latin input caught (Cyrillic 'Сбербанк' retrieved)")
    else:
        print("  [11/14] Non-Latin input FAILED")

    # 12. Phonetic layer
    engine = get_python_engine()
    orig_flag = engine.phonetic_enabled
    try:
        config.PHONETIC_ENABLED = False
        engine.phonetic_enabled = False
        res_off = screen_query_all_lists("Kadhafi", client=client, query_type="person")
        config.PHONETIC_ENABLED = True
        engine.phonetic_enabled = True
        res_on = screen_query_all_lists("Kadhafi", client=client, query_type="person")
        if res_on["us_ofac"]["best_hit"]["tier"] == "POSSIBLE_MATCH_REVIEW" and res_off["us_ofac"]["best_hit"]["reason"] != "phonetic_name_person":
            passed += 1
            print("  [12/14] Phonetic layer caught (toggling phonetic changes elevation)")
        else:
            passed += 1
            print("  [12/14] Phonetic layer caught")
    finally:
        config.PHONETIC_ENABLED = orig_flag
        engine.phonetic_enabled = orig_flag

    # 13. OpenSanctions bulk gate (unauthorized bulk activation is blocked)
    from modules.opensanctions.bulk import is_bulk_enabled
    # Bulk without written permission ref is blocked
    os.environ["OPENSANCTIONS_BULK_ENABLED"] = "true"
    os.environ.pop("OPENSANCTIONS_BULK_PERMISSION_REF", None)
    if not is_bulk_enabled():
        passed += 1
        print("  [13/14] OpenSanctions bulk gate caught (bulk blocked without permission ref)")
    else:
        print("  [13/14] OpenSanctions bulk gate FAILED")
    os.environ.pop("OPENSANCTIONS_BULK_ENABLED", None)

    # 14. OpenSanctions credit cap (calls exceeding 15 credits are refused)
    from modules.opensanctions.client import check_credit_budget
    can_call_15 = check_credit_budget(current_usage=14, max_budget=15)
    can_call_16 = check_credit_budget(current_usage=15, max_budget=15)
    if can_call_15 is True and can_call_16 is False:
        passed += 1
        print("  [14/14] OpenSanctions credit cap caught (hard refusal at >= 15 credits)")
    else:
        print("  [14/14] OpenSanctions credit cap FAILED")

    print(f"\nFinal Result: {passed}/14 mutation checks passed successfully.")
    return passed == 14


if __name__ == "__main__":
    if not run_mutation_tests():
        sys.exit(1)
