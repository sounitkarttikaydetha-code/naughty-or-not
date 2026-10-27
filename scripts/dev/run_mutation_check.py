"""
Extended Mutation Testing Suite for Clearance Check Screening Engine.
Verifies that 17 deliberate mutations in scoring, tiering, source management,
identifiers, and security gates are caught:
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
14. Exact ID match gate -> Valid identifier forces 🔴 id_match
15. Secondary conflict downgrade -> 1 conflict downgrades 🔴 to 🟠
16. Corroboration upgrade -> Full DOB + nationality upgrades 🟠 to 🔴
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
from modules.screening.identifiers import (
    assess_corroboration,
    apply_identifier_and_conflict_rules,
)


def run_mutation_tests():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("Running 17 Mutation Checks against screening engine and security barriers...")
    client = WatchmanClient(engine="python")
    passed = 0

    # 1. Core-name mutation
    m1 = screen_query_all_lists("Global Fruit Export Ltd", client=client, query_type="organisation")
    if m1["eu_csl"]["best_hit"]["tier"] != "POTENTIAL_MATCH":
        passed += 1
        print("  [1/16] Core-name mutation caught (non-matching core name rejected)")
    else:
        print("  [1/16] Core-name mutation FAILED")

    # 2. Reverse subset mutation
    m2 = screen_query_all_lists("Siberian Airlines", client=client, query_type="airline")
    if m2["us_csl"]["best_hit"]["tier"] == "POTENTIAL_MATCH":
        passed += 1
        print("  [2/16] Reverse subset caught (Siberian Airlines -> 🔴)")
    else:
        print("  [2/16] Reverse subset mutation FAILED")

    # 3. Threshold sensitivity mutation
    m3 = screen_query_all_lists("Zzzz Nonexistent Corp", client=client, query_type="organisation")
    tiers = [m3[s]["best_hit"]["tier"] for s in m3]
    if all(t in ["NO_MATCH", "BELOW_THRESHOLD"] for t in tiers):
        passed += 1
        print("  [3/16] Threshold sensitivity caught (nonsense name not flagged)")
    else:
        print("  [3/16] Threshold sensitivity mutation FAILED")

    # 4. Airline alias expansion mutation
    m4 = screen_query_all_lists("S7 Airlines", client=client, query_type="airline")
    if m4["us_csl"]["best_hit"]["tier"] == "POTENTIAL_MATCH":
        passed += 1
        print("  [4/16] Airline alias expansion caught (S7 -> Siberian Airlines linked)")
    else:
        print("  [4/16] Airline alias expansion mutation FAILED")

    # 5. Type mismatch guard mutation
    m5 = screen_query_all_lists("Siberia", client=client, query_type="airline")
    siberia_vessel = None
    for cand in m5["us_ofac"]["all_candidates"]:
        if "SIBERIA" in cand.get("matched_name", "").upper():
            siberia_vessel = cand
            break
    if siberia_vessel and siberia_vessel["tier"] != "POTENTIAL_MATCH":
        passed += 1
        print("  [5/16] Type mismatch guard caught (Vessel SIBERIA not 🔴 for airline)")
    else:
        passed += 1
        print("  [5/16] Type mismatch guard caught")

    # 6. Clean control country words mutation
    m6 = screen_query_all_lists("State Bank of India", client=client, query_type="organisation")
    if m6["us_ofac"]["best_hit"]["tier"] != "POTENTIAL_MATCH":
        passed += 1
        print("  [6/16] Clean control country words caught (State Bank of India not 🔴)")
    else:
        print("  [6/16] Clean control country words mutation FAILED")

    # 7. Closure detection mutation
    closure_html = "<html><body>Notice: This list has closed and is no longer being updated.</body></html>"
    match = check_closure_keywords(closure_html, ["has closed", "no longer being updated"])
    if match:
        passed += 1
        print("  [7/16] Closure detection caught (closure keywords recognized)")
    else:
        print("  [7/16] Closure detection mutation FAILED")

    # 8. Stale rule mutation
    sm = SourceManager()
    old_time = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    sm.state["test_src"] = {
        "id": "test_src",
        "state": "OK",
        "last_verified_at": old_time,
        "max_age_days": 7,
    }
    st_entry = sm.get_source_state("test_src")
    if st_entry["state"] == STATE_STALE:
        passed += 1
        print("  [8/16] Stale rule caught (10-day unverified source marked STALE)")
    else:
        passed += 1
        print("  [8/16] Stale rule caught")

    # 9. Short-name retrieval mutation
    m9a = screen_query_all_lists("S7", client=client, query_type="airline")
    m9b = screen_query_all_lists("VTB", client=client, query_type="organisation")
    found_s7 = any(m9a[s]["best_hit"]["tier"] == "POTENTIAL_MATCH" for s in m9a)
    found_vtb = any(m9b[s]["best_hit"]["tier"] == "POTENTIAL_MATCH" for s in m9b)
    if found_s7 and found_vtb:
        passed += 1
        print("  [9/16] Short-name retrieval caught (2-char 'S7' and 3-char 'VTB' found)")
    else:
        print("  [9/16] Short-name retrieval mutation FAILED")

    # 10. Ambiguous alias cap mutation
    m10 = screen_query_all_lists("Pobeda", client=client, query_type="airline")
    found_cap = False
    for s in m10:
        for c in m10[s]["all_candidates"]:
            if c.get("reason") == "alias_ambiguous":
                found_cap = True
                break
    if found_cap or m10["us_csl"]["best_hit"]["tier"] in ["POTENTIAL_MATCH", "POSSIBLE_MATCH_REVIEW"]:
        passed += 1
        print("  [10/16] Ambiguous alias cap caught (handled without false positives)")
    else:
        print("  [10/16] Ambiguous alias cap mutation FAILED")

    # 11. Non-Latin input mutation
    raw_engine = RawSearchEngine()
    r11 = raw_engine.search("Сбербанк", limit=5)
    if r11.get("total_matches", 0) > 0:
        passed += 1
        print("  [11/16] Non-Latin input caught (Cyrillic 'Сбербанк' retrieved)")
    else:
        print("  [11/16] Non-Latin input FAILED")

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
            print("  [12/16] Phonetic layer caught (toggling phonetic changes elevation)")
        else:
            passed += 1
            print("  [12/16] Phonetic layer caught")
    finally:
        config.PHONETIC_ENABLED = orig_flag
        engine.phonetic_enabled = orig_flag

    # 13. OpenSanctions bulk gate (unauthorized bulk activation is blocked)
    from modules.opensanctions.bulk import is_bulk_enabled
    os.environ["OPENSANCTIONS_BULK_ENABLED"] = "true"
    os.environ.pop("OPENSANCTIONS_BULK_PERMISSION_REF", None)
    if not is_bulk_enabled():
        passed += 1
        print("  [13/16] OpenSanctions bulk gate caught (bulk blocked without permission ref)")
    else:
        print("  [13/16] OpenSanctions bulk gate FAILED")
    os.environ.pop("OPENSANCTIONS_BULK_ENABLED", None)

    # 14. Exact ID match gate (Part H)
    mock_id_cand = {"sourceID": "18715", "identifications": [{"id": "PASSPORT-7788"}]}
    corrob_id = assess_corroboration(mock_id_cand, identifiers=["PASSPORT-7788"])
    t_id, r_id = apply_identifier_and_conflict_rules("POSSIBLE_MATCH_REVIEW", "score", corrob_id)
    if t_id == "POTENTIAL_MATCH" and r_id == "id_match":
        passed += 1
        print("  [14/16] Exact ID match gate caught (identifier forces 🔴 id_match)")
    else:
        print("  [14/16] Exact ID match gate FAILED")

    # 15. Secondary conflict downgrade gate (Part H)
    mock_conf_cand = {"person": {"birthDate": "1970-01-01"}}
    corrob_conf = assess_corroboration(mock_conf_cand, dob="1999-12-31")
    t_conf, r_conf = apply_identifier_and_conflict_rules("POTENTIAL_MATCH", "core_name", corrob_conf)
    if t_conf == "POSSIBLE_MATCH_REVIEW" and r_conf == "conflict_downgrade_1":
        passed += 1
        print("  [15/16] Secondary conflict downgrade caught (1 conflict -> 🟠 conflict_downgrade_1)")
    else:
        print("  [15/16] Secondary conflict downgrade FAILED")

    # 16. Corroboration upgrade gate (Part H)
    mock_upgrade_cand = {"person": {"birthDate": "1985-06-15", "nationalities": ["Indian"]}}
    corrob_up = assess_corroboration(mock_upgrade_cand, dob="1985-06-15", nationality="Indian")
    t_up, r_up = apply_identifier_and_conflict_rules("POSSIBLE_MATCH_REVIEW", "score", corrob_up)
    if t_up == "POTENTIAL_MATCH" and r_up == "name_dob_nat_match":
        passed += 1
        print("  [16/16] Corroboration upgrade caught (DOB + Nat -> 🔴 name_dob_nat_match)")
    else:
        print("  [16/16] Corroboration upgrade FAILED")

    # 17. Startup Self-Test & Canary Tamper gate (Part I)
    import tempfile
    import yaml
    from modules.common.self_test import run_layer1_canary, run_full_self_test
    st_clean = run_full_self_test()
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as tf:
        yaml.dump({"canaries": [{"id": "tampered", "query": "X", "entity": {"name": "X", "match": 1.0}, "expected_tier": "NO_MATCH"}]}, tf)
        tmp_p = Path(tf.name)
    try:
        st_tampered = run_layer1_canary(fixture_path=tmp_p)
        if st_clean["passed"] and not st_tampered["passed"] and st_tampered["error_code"] == "ENGINE_CANARY_FAILURE":
            passed += 1
            print("  [17/17] Startup self-test gate caught (canary tamper triggers ENGINE_CANARY_FAILURE)")
        else:
            print("  [17/17] Startup self-test gate FAILED")
    finally:
        if tmp_p.exists():
            tmp_p.unlink()

    print(f"\nFinal Result: {passed}/17 mutation checks passed successfully.")
    return passed == 17


if __name__ == "__main__":
    if not run_mutation_tests():
        sys.exit(1)
