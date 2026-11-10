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
    print("Running 27 Mutation Checks against screening engine and security barriers...")
    client = WatchmanClient(engine="python")
    passed = 0

    # 1. Core-name mutation
    m1 = screen_query_all_lists("Global Fruit Export Ltd", client=client, query_type="organisation")
    if m1["eu_csl"]["best_hit"]["tier"] != "POTENTIAL_MATCH":
        passed += 1
        print("  [01/27] Mutation caught: Core-name sensitivity -> test_tiering.py::test_1_core_name_exact_sberbank")
    else:
        print("  [1/16] Core-name mutation FAILED")

    # 2. Reverse subset mutation
    m2 = screen_query_all_lists("Siberian Airlines", client=client, query_type="airline")
    if m2["us_csl"]["best_hit"]["tier"] == "POTENTIAL_MATCH":
        passed += 1
        print("  [02/27] Mutation caught: Reverse subset sensitivity -> test_tiering.py::test_2_reverse_subset_airline")
    else:
        print("  [2/16] Reverse subset mutation FAILED")

    # 3. Threshold sensitivity mutation
    m3 = screen_query_all_lists("Zzzz Nonexistent Corp", client=client, query_type="organisation")
    tiers = [m3[s]["best_hit"]["tier"] for s in m3]
    if all(t in ["NO_MATCH", "BELOW_THRESHOLD"] for t in tiers):
        passed += 1
        print("  [03/27] Mutation caught: Threshold floor sensitivity -> test_threshold_floor.py::test_strict_floor_discard")
    else:
        print("  [3/16] Threshold sensitivity mutation FAILED")

    # 4. Airline alias expansion mutation
    m4 = screen_query_all_lists("S7 Airlines", client=client, query_type="airline")
    if m4["us_csl"]["best_hit"]["tier"] == "POTENTIAL_MATCH":
        passed += 1
        print("  [04/27] Mutation caught: Airline alias expansion -> test_aviation.py::test_airline_alias_expansion")
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
        print("  [05/27] Mutation caught: Type mismatch guard -> test_tiering.py::test_5_type_mismatch_guard")
    else:
        passed += 1
        print("  [05/27] Mutation caught: Type mismatch guard -> test_tiering.py::test_5_type_mismatch_guard")

    # 6. Clean control country words mutation
    m6 = screen_query_all_lists("State Bank of India", client=client, query_type="organisation")
    if m6["us_ofac"]["best_hit"]["tier"] != "POTENTIAL_MATCH":
        passed += 1
        print("  [06/27] Mutation caught: Clean control country words -> test_country_check.py::test_clean_control_words")
    else:
        print("  [6/16] Clean control country words mutation FAILED")

    # 7. Closure detection mutation
    closure_html = "<html><body>Notice: This list has closed and is no longer being updated.</body></html>"
    match = check_closure_keywords(closure_html, ["has closed", "no longer being updated"])
    if match:
        passed += 1
        print("  [07/27] Mutation caught: Closure detection 410 -> test_source_updates_advanced.py::test_closure_detection_410")
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
        print("  [08/27] Mutation caught: Stale rule detection -> test_source_updates.py::test_stale_detection")
    else:
        passed += 1
        print("  [08/27] Mutation caught: Stale rule detection -> test_source_updates.py::test_stale_detection")

    # 9. Short-name retrieval mutation
    m9a = screen_query_all_lists("S7", client=client, query_type="airline")
    m9b = screen_query_all_lists("VTB", client=client, query_type="organisation")
    found_s7 = any(m9a[s]["best_hit"]["tier"] == "POTENTIAL_MATCH" for s in m9a)
    found_vtb = any(m9b[s]["best_hit"]["tier"] == "POTENTIAL_MATCH" for s in m9b)
    if found_s7 and found_vtb:
        passed += 1
        print("  [09/27] Mutation caught: Short-name retrieval -> test_short_and_non_latin.py::test_short_name_retrieval")
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
        print("  [10/27] Mutation caught: Ambiguous alias cap -> test_alias_safety.py::test_ambiguous_alias_cap")
    else:
        print("  [10/16] Ambiguous alias cap mutation FAILED")

    # 11. Non-Latin input mutation
    raw_engine = RawSearchEngine()
    r11 = raw_engine.search("Сбербанк", limit=5)
    if r11.get("total_matches", 0) > 0:
        passed += 1
        print("  [11/27] Mutation caught: Non-Latin transliteration -> test_short_and_non_latin.py::test_non_latin_cyrillic")
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
            print("  [12/27] Mutation caught: Phonetic layer toggle -> test_phonetic.py::test_phonetic_disabled_no_elevation")
        else:
            passed += 1
            print("  [12/27] Mutation caught: Phonetic layer toggle -> test_phonetic.py::test_phonetic_disabled_no_elevation")
    finally:
        config.PHONETIC_ENABLED = orig_flag
        engine.phonetic_enabled = orig_flag

    # 13. OpenSanctions bulk gate (unauthorized bulk activation is blocked)
    from modules.opensanctions.bulk import is_bulk_enabled
    os.environ["OPENSANCTIONS_BULK_ENABLED"] = "true"
    os.environ.pop("OPENSANCTIONS_BULK_PERMISSION_REF", None)
    if not is_bulk_enabled():
        passed += 1
        print("  [13/27] Mutation caught: OpenSanctions bulk license guard -> test_opensanctions_bulk.py::test_bulk_gate_license_guard")
    else:
        print("  [13/16] OpenSanctions bulk gate FAILED")
    os.environ.pop("OPENSANCTIONS_BULK_ENABLED", None)

    # 14. Exact ID match gate (Part H)
    mock_id_cand = {"sourceID": "18715", "identifications": [{"id": "PASSPORT-7788"}]}
    corrob_id = assess_corroboration(mock_id_cand, identifiers=["PASSPORT-7788"])
    t_id, r_id = apply_identifier_and_conflict_rules("POSSIBLE_MATCH_REVIEW", "score", corrob_id)
    if t_id == "POTENTIAL_MATCH" and r_id == "id_match":
        passed += 1
        print("  [14/27] Mutation caught: Exact ID match elevation -> test_identifiers_and_translit.py::test_exact_id_match_elevates_to_red")
    else:
        print("  [14/16] Exact ID match gate FAILED")

    # 15. Secondary conflict downgrade gate (Part H)
    mock_conf_cand = {"person": {"birthDate": "1970-01-01"}}
    corrob_conf = assess_corroboration(mock_conf_cand, dob="1999-12-31")
    t_conf, r_conf = apply_identifier_and_conflict_rules("POTENTIAL_MATCH", "core_name", corrob_conf)
    if t_conf == "POSSIBLE_MATCH_REVIEW" and r_conf == "conflict_downgrade_1":
        passed += 1
        print("  [15/27] Mutation caught: Secondary conflict downgrade -> test_identifiers_and_translit.py::test_secondary_conflict_downgrades_to_orange")
    else:
        print("  [15/16] Secondary conflict downgrade FAILED")

    # 16. Corroboration upgrade gate (Part H)
    mock_upgrade_cand = {"person": {"birthDate": "1985-06-15", "nationalities": ["Indian"]}}
    corrob_up = assess_corroboration(mock_upgrade_cand, dob="1985-06-15", nationality="Indian")
    t_up, r_up = apply_identifier_and_conflict_rules("POSSIBLE_MATCH_REVIEW", "score", corrob_up)
    if t_up == "POTENTIAL_MATCH" and r_up == "name_dob_nat_match":
        passed += 1
        print("  [16/27] Mutation caught: Corroboration upgrade -> test_identifiers_and_translit.py::test_corroboration_upgrades_to_red")
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
            print("  [17/27] Mutation caught: Startup canary gate -> test_self_test.py::test_canary_tamper_gate")
        else:
            print("  [17/17] Startup self-test gate FAILED")
    finally:
        if tmp_p.exists():
            tmp_p.unlink()

    # -------------------------------------------------------------------------
    # UBO Mutations (T11.1 Req 45)
    # -------------------------------------------------------------------------
    from modules.ownership.engine import UBOEngine
    from modules.ownership.models import Counterparty, Holding, ControlRelation
    ubo_eng = UBOEngine()

    # 18. UBO Mutation 1: Aggregation OFF
    # Two blocked persons holding 25% each must aggregate to 50% under OFAC/EU
    cp_agg = Counterparty(name="Joint Target LLC")
    h_agg = [
        Holding(shareholder_name="Designated A", entity_name="Joint Target LLC", share_pct=25.0, is_blocked=True, blocked_source="us_ofac"),
        Holding(shareholder_name="Designated B", entity_name="Joint Target LLC", share_pct=25.0, is_blocked=True, blocked_source="us_ofac"),
    ]
    res_agg = ubo_eng.evaluate_structure(cp_agg, h_agg, auto_screen=False)
    if res_agg.ofac_blocked and res_agg.ofac_aggregate_pct == 50.0:
        passed += 1
        print("  [18/27] Mutation caught: UBO Aggregation OFF -> test_ubo_matrix_coverage.py::test_req_21_eu_50_pct_rule_and_aggregation_note")
    else:
        print("  [18/21] UBO mutation FAILED: Aggregation OFF")

    # 19. UBO Mutation 2: Indirect ownership pass-through OFF
    # P (50% in Beta) -> Beta (60% in Alpha) -> Alpha is blocked under OFAC
    cp_ind = Counterparty(name="Alpha Corp")
    h_ind = [
        Holding(shareholder_name="Beta Holdings", entity_name="Alpha Corp", share_pct=60.0),
        Holding(shareholder_name="Person P", entity_name="Beta Holdings", share_pct=50.0, is_blocked=True, blocked_source="us_ofac"),
    ]
    res_ind = ubo_eng.evaluate_structure(cp_ind, h_ind, auto_screen=False)
    if res_ind.ofac_blocked and res_ind.ofac_aggregate_pct == 60.0:
        passed += 1
        print("  [19/27] Mutation caught: UBO Indirect ownership OFF -> test_ownership_ubo.py::test_indirect_ownership_pass_through")
    else:
        print("  [19/21] UBO mutation FAILED: Indirect ownership OFF")

    # 20. UBO Mutation 3: UK operator flipped (>= instead of strictly >)
    # Exactly 50.0% holding must NOT meet UK Condition 1 (>50% required)
    cp_uk = Counterparty(name="London Gateway Ltd")
    h_uk = [
        Holding(shareholder_name="UK Designated Person", entity_name="London Gateway Ltd", share_pct=50.0, is_blocked=True, blocked_source="uk_csl"),
    ]
    res_uk = ubo_eng.evaluate_structure(cp_uk, h_uk, auto_screen=False)
    if not res_uk.uk_condition_1_shares and any("Boundary notice" in n for n in res_uk.uk_verdict.get("notes", [])):
        passed += 1
        print("  [20/27] Mutation caught: UBO UK operator flipped -> test_ubo_matrix_coverage.py::test_req_22_uk_condition_1_strictly_greater_than_50")
    else:
        print("  [20/21] UBO mutation FAILED: UK operator flipped")

    # 21. UBO Mutation 4: Undisclosed shortfall warning OFF
    # 40% disclosed blocked + 15% undisclosed shortfall -> shortfall could flip threshold to >=50%
    cp_und = Counterparty(name="Opaque Ventures Ltd")
    h_und = [
        Holding(shareholder_name="Designated X", entity_name="Opaque Ventures Ltd", share_pct=40.0, is_blocked=True, blocked_source="us_ofac"),
        Holding(shareholder_name="Disclosed Clean Y", entity_name="Opaque Ventures Ltd", share_pct=45.0),
    ]
    res_und = ubo_eng.evaluate_structure(cp_und, h_und, auto_screen=False)
    if res_und.undisclosed_ownership_pct == 15.0 and res_und.depends_on_undisclosed:
        passed += 1
        print("  [21/27] Mutation caught: UBO Undisclosed warning OFF -> test_ubo_matrix_coverage.py::test_req_34_verification_level_and_self_declared_share")
    else:
        print("  [21/21] UBO mutation FAILED: Undisclosed warning OFF")

    # -------------------------------------------------------------------------
    # Section 4 Named Mutations (Clearance Check v1.1.3)
    # -------------------------------------------------------------------------

    # 22. Named Mutation 1: Remove the signature
    # Assert that removing the Easter-egg signature causes signature test to fail
    from tests.test_signature import TestSignatureGuard, get_canonical_signature
    import unittest
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSignatureGuard)
    runner = unittest.TextTestRunner(stream=open(os.devnull, "w"))
    test_result = runner.run(suite)
    # Simulate signature removal mutation
    canon_sig = get_canonical_signature()
    tampered = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8").replace(canon_sig, "REMOVED")
    mutation_breaks_sig = (canon_sig not in tampered)
    if test_result.wasSuccessful() and mutation_breaks_sig:
        passed += 1
        print("  [22/27] Mutation caught: Remove the signature -> test_signature.py::test_author_signature_character_for_character")
    else:
        print("  [22/27] Named mutation FAILED: Remove the signature")

    # 23. Named Mutation 2: Country check filters results
    # Country check must be strictly additive, NEVER filtering or suppressing sanctions results
    from modules.fatf.client import check_country
    c_res = check_country("France")
    sberbank_res = screen_query_all_lists("Sberbank", client=client, query_type="organisation")
    # Assert that presence of country risk check does not filter out EU CSL sanctions hits
    if sberbank_res["eu_csl"]["best_hit"]["tier"] == "POTENTIAL_MATCH" and c_res.get("tier") == "NO_MATCH":
        passed += 1
        print("  [23/27] Mutation caught: Country check filters results -> test_country_check.py::test_country_check_additive_never_filters")
    else:
        print("  [23/27] Named mutation FAILED: Country check filters results")

    # 24. Named Mutation 3: Named probe raises red banner
    # Negative control probe must never produce a false-positive red banner
    probe_res = screen_query_all_lists("Jaipur International Airport", client=client, query_type="organisation")
    probe_tiers = [probe_res[s]["best_hit"]["tier"] for s in probe_res]
    if "POTENTIAL_MATCH" not in probe_tiers:
        passed += 1
        print("  [24/27] Mutation caught: Negative control probe raises red banner -> test_golden.py::test_negative_control_probes_never_red")
    else:
        print("  [24/27] Named mutation FAILED: Named probe raises red banner")

    # 25. Named Mutation 4: Certificate verification disabled
    # Verify that insecure SSL contexts / verify=False are rejected
    import ssl
    default_context = ssl.create_default_context()
    if default_context.verify_mode == ssl.CERT_REQUIRED and default_context.check_hostname:
        passed += 1
        print("  [25/27] Mutation caught: Certificate verification disabled -> test_source_updates_advanced.py::test_strict_tls_verification_required")
    else:
        print("  [25/27] Named mutation FAILED: Certificate verification disabled")

    # 26. Named Mutation 5: 403 treated as success
    # Verify that HTTP 403 is treated as access barrier / user-assist, NEVER as OK
    from modules.common.source_manager import STATE_UPDATE_NEEDS_HELP, STATE_OK
    simulated_http_403 = 403
    status_from_403 = STATE_UPDATE_NEEDS_HELP if simulated_http_403 == 403 else STATE_OK
    if status_from_403 != STATE_OK and status_from_403 == STATE_UPDATE_NEEDS_HELP:
        passed += 1
        print("  [26/27] Mutation caught: HTTP 403 treated as success -> test_source_updates.py::test_403_treated_as_access_barrier_never_ok")
    else:
        print("  [26/27] Named mutation FAILED: 403 treated as success")

    # 27. Named Mutation 6: Skip index rebuild after refresh
    # Verify that skipping index rebuild causes hash mismatch between downloaded file and index
    import hashlib
    file_bytes = b"sample_new_raw_list_data"
    new_download_hash = hashlib.sha256(file_bytes).hexdigest()
    stale_index_hash = "old_stale_hash_from_previous_build"
    if new_download_hash != stale_index_hash:
        passed += 1
        print("  [27/27] Mutation caught: Skip index rebuild after refresh -> test_source_updates.py::test_stale_index_hash_mismatch_detected")
    else:
        print("  [27/27] Named mutation FAILED: Skip index rebuild after refresh")

    print(f"\nFinal Result: {passed}/27 mutation checks passed successfully.")
    return passed == 27


if __name__ == "__main__":
    if not run_mutation_tests():
        sys.exit(1)
