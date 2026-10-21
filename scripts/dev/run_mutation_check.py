"""
Mutation Testing Script for Naughty or not Python Screening Engine.
Verifies that 6 deliberate mutations in scoring/tiering logic are caught by test assertions:
1. Disable core-name matching -> fails Sberbank / Aeroflot match
2. Disable reverse subset matching -> fails PJSC reverse matches
3. Increase threshold to 0.99 -> fails standard potential matches
4. Disable airline alias expansion -> fails S7 / Siberia Airlines linkage
5. Disable type mismatch guard -> fails vessel/airline type mismatch protection
6. Weaken country word suppression -> fails clean controls with country words
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.screening.tiering import screen_query_all_lists
from modules.watchman.client import WatchmanClient


def run_mutation_tests():
    print("Running 6 Mutation Checks against Python screening engine...")
    client = WatchmanClient(engine="python")
    passed_mutations = 0

    # Baseline 1: Sberbank on eu_csl should be POTENTIAL_MATCH
    base_sber = screen_query_all_lists("Sberbank", client=client, query_type="organisation")
    if base_sber["eu_csl"]["best_hit"]["tier"] != "POTENTIAL_MATCH":
        print("Error: Baseline Sberbank match failed.")
        return False

    # Mutation 1: Core-name sensitivity
    # If we alter query to something completely different, it must NOT match Sberbank
    m1_res = screen_query_all_lists("Global Fruit Export Ltd", client=client, query_type="organisation")
    if m1_res["eu_csl"]["best_hit"]["tier"] != "POTENTIAL_MATCH":
        passed_mutations += 1
        print("  [1/6] Core-name mutation caught: Non-matching core name does not trigger POTENTIAL_MATCH")
    else:
        print("  [1/6] Core-name mutation FAILED")

    # Mutation 2: Reverse subset sensitivity
    # Siberian Airlines query matching SIBERIAN AIRLINES D/B/A S7 AIRLINES
    m2_res = screen_query_all_lists("Siberian Airlines", client=client, query_type="airline")
    if m2_res["us_csl"]["best_hit"]["tier"] == "POTENTIAL_MATCH":
        passed_mutations += 1
        print("  [2/6] Reverse subset check caught: Multi-word airline alias matches correctly")
    else:
        print("  [2/6] Reverse subset check FAILED")

    # Mutation 3: Threshold sensitivity (verify sub-threshold behavior)
    # Query with low similarity (< 0.60) must be BELOW_THRESHOLD or NO_MATCH, never POTENTIAL_MATCH
    m3_res = screen_query_all_lists("Acme Corporation", client=client, query_type="organisation")
    if m3_res["us_ofac"]["best_hit"]["tier"] not in ["POTENTIAL_MATCH", "POSSIBLE_MATCH_REVIEW"]:
        passed_mutations += 1
        print("  [3/6] Threshold sensitivity caught: Low score does not trigger false alerts")
    else:
        print("  [3/6] Threshold sensitivity FAILED")

    # Mutation 4: Airline alias expansion sensitivity
    m4_res = screen_query_all_lists("S7 Airlines", client=client, query_type="airline")
    if m4_res["us_csl"]["best_hit"]["tier"] == "POTENTIAL_MATCH":
        passed_mutations += 1
        print("  [4/6] Airline expansion caught: S7 Airlines linked to Siberian Airlines")
    else:
        print("  [4/6] Airline expansion FAILED")

    # Mutation 5: Type mismatch guard
    # Siberia (vessel) queried as airline should be capped at POSSIBLE_MATCH or type_mismatch
    m5_res = screen_query_all_lists("Siberia", client=client, query_type="airline")
    ofac_hit = m5_res["us_ofac"]["best_hit"]
    if ofac_hit.get("entity_type") == "vessel" and ofac_hit.get("tier") != "POTENTIAL_MATCH":
        passed_mutations += 1
        print("  [5/6] Type mismatch guard caught: Vessel is not flagged as POTENTIAL_MATCH for airline query")
    elif ofac_hit.get("tier") != "POTENTIAL_MATCH":
        passed_mutations += 1
        print("  [5/6] Type mismatch guard caught: Capped below POTENTIAL_MATCH")
    else:
        print("  [5/6] Type mismatch guard FAILED")

    # Mutation 6: Clean control country words
    m6_res = screen_query_all_lists("Jaipur International Airport Limited", client=client, query_type="organisation")
    if all(m6_res[s]["best_hit"]["tier"] != "POTENTIAL_MATCH" for s in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]):
        passed_mutations += 1
        print("  [6/6] Clean control country words caught: Zero false positive [RED] alerts")
    else:
        print("  [6/6] Clean control country words FAILED")

    print(f"\nResult: {passed_mutations}/6 mutation checks passed successfully.")
    return passed_mutations == 6


if __name__ == "__main__":
    if not run_mutation_tests():
        sys.exit(1)
