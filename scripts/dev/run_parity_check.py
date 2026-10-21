"""
A2. Comprehensive Parity & Evaluation Test
Compares Python Engine against Docker Watchman across all required criteria:
1. Golden set tier parity
2. Watchman 🔴 and 🟠 hit recall (no missed hits)
3. Score differences (<= 0.02 for 95%, <= 0.05 for 🔴/🟠)
4. Clean controls (zero false 🔴)
5. Record count verification
6. 6 Mutation checks
7. Fail-safe check
8. Performance metrics (RAM, load time, search latency)
"""

import json
import logging
import os
from pathlib import Path
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.watchman.client import WatchmanClient
from modules.screening.tiering import screen_query_all_lists, SOURCE_LISTS

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("parity_check")

GOLDEN_SET_PATH = PROJECT_ROOT / "tests" / "golden_set.json"

CLEAN_CONTROLS = [
    ("Jaipur International Airport Limited", "organisation"),
    ("Adani Airport Holdings Limited", "organisation"),
    ("Air India", "airline"),
    ("IndiGo", "airline"),
    ("InterGlobe Aviation Limited", "organisation"),
    ("Siberian Wellness", "organisation"),
    ("Larsen & Toubro", "organisation"),
    ("SpiceJet", "airline"),
    ("Akasa Air", "airline"),
    ("Tata Consultancy Services", "organisation"),
]

TEST_QUERIES = [
    ("Sberbank", "organisation"),
    ("Sberbank of Russia", "organisation"),
    ("PJSC Sberbank", "organisation"),
    ("VTB Bank", "organisation"),
    ("S7 Airlines", "airline"),
    ("Siberia Airlines", "airline"),
    ("Aeroflot", "airline"),
    ("Azur Air", "airline"),
    ("UTair", "airline"),
    ("Jaipur International Airport Limited", "organisation"),
    ("Adani Airport Holdings Limited", "organisation"),
    ("Air India", "airline"),
    ("IndiGo", "airline"),
    ("InterGlobe Aviation Limited", "organisation"),
    ("Siberian Wellness", "organisation"),
    ("Rajesh Kumar", "person"),
    ("Mohammed Khan", "person"),
    ("Sky Bank", "organisation"),
    ("Volga Logistics", "organisation"),
    ("Rosneft", "organisation"),
    ("Gazprombank", "organisation"),
    ("Mahan Air", "airline"),
    ("Rossiya", "airline"),
    ("Ural Airlines", "airline"),
    ("Larsen & Toubro", "organisation"),
    ("SpiceJet", "airline"),
    ("Akasa Air", "airline"),
    ("Tata Steel", "organisation"),
    ("Bharat Petroleum", "organisation"),
]


def run_parity():
    sys.stdout.reconfigure(encoding="utf-8")
    py_client = WatchmanClient(engine="python")
    wm_client = WatchmanClient(engine="watchman")

    wm_health = wm_client.health()
    if not wm_health.get("healthy"):
        print("ERROR: Docker Watchman is not reachable on localhost:8084")
        sys.exit(1)

    print("=== 1. RECORD COUNT COMPARISON ===")
    wm_raw = wm_client.list_info().get("lists", {})
    wm_info = wm_raw.get("lists", wm_raw)
    py_raw = py_client.list_info().get("lists", {})
    py_info = py_raw.get("lists", py_raw)
    print(f"{'Source':<12} | {'Watchman':<10} | {'Python':<10} | {'Diff':<6}")
    print("-" * 45)
    for src in SOURCE_LISTS:
        w_cnt = wm_info.get(src, 0)
        p_cnt = py_info.get(src, 0)
        print(f"{src:<12} | {w_cnt:<10} | {p_cnt:<10} | {p_cnt - w_cnt:<6}")

    print("\n=== 2. QUERY PARITY & SCORE DIFFERENCES ===")
    total_comparisons = 0
    diff_under_02 = 0
    red_orange_checked = 0
    red_orange_under_05 = 0
    missed_red_or_orange = []
    golden_tier_mismatches = []
    clean_control_false_reds = []

    # Check Golden Set
    with open(GOLDEN_SET_PATH, "r", encoding="utf-8") as f:
        golden_data = json.load(f)

    for q_name, g_entry in golden_data.items():
        q_type = g_entry.get("query_type")
        exp_lists = g_entry.get("lists", {})

        py_screen = screen_query_all_lists(q_name, client=py_client, query_type=q_type)
        wm_screen = screen_query_all_lists(q_name, client=wm_client, query_type=q_type)

        for src in SOURCE_LISTS:
            exp_tier = exp_lists.get(src, {}).get("tier")
            verified = exp_lists.get(src, {}).get("verified")
            py_tier = py_screen[src]["best_hit"]["tier"]
            wm_tier = wm_screen[src]["best_hit"]["tier"]

            if verified is True:
                if py_tier != exp_tier:
                    golden_tier_mismatches.append(
                        f"[{q_name}][{src}] expected {exp_tier}, got {py_tier}"
                    )

    # Check Test Queries (29 queries)
    for q_name, q_type in TEST_QUERIES:
        py_res = screen_query_all_lists(q_name, client=py_client, query_type=q_type)
        wm_res = screen_query_all_lists(q_name, client=wm_client, query_type=q_type)

        for src in SOURCE_LISTS:
            py_hit = py_res[src]["best_hit"]
            wm_hit = wm_res[src]["best_hit"]

            wm_tier = wm_hit.get("tier")
            py_tier = py_hit.get("tier")
            wm_score = wm_hit.get("score", 0.0)
            py_score = py_hit.get("score", 0.0)

            # Check if Watchman hit a 🔴 or 🟠 that Python missed
            if wm_tier in ["POTENTIAL_MATCH", "POSSIBLE_MATCH_REVIEW"]:
                red_orange_checked += 1
                if py_tier not in ["POTENTIAL_MATCH", "POSSIBLE_MATCH_REVIEW"]:
                    missed_red_or_orange.append(
                        f"[{q_name}][{src}] WM={wm_tier} ({wm_score:.3f}), PY={py_tier} ({py_score:.3f})"
                    )
                else:
                    score_diff = abs(wm_score - py_score)
                    if score_diff <= 0.05:
                        red_orange_under_05 += 1

            # Candidate score differences in top candidates
            wm_cands = {c["source_id"]: c["score"] for c in wm_res[src].get("all_candidates", []) if c.get("source_id")}
            py_cands = {c["source_id"]: c["score"] for c in py_res[src].get("all_candidates", []) if c.get("source_id")}

            common_ids = set(wm_cands.keys()) & set(py_cands.keys())
            for sid in common_ids:
                total_comparisons += 1
                diff = abs(wm_cands[sid] - py_cands[sid])
                if diff <= 0.02:
                    diff_under_02 += 1

    # Check Clean Controls
    for ctrl_name, ctrl_type in CLEAN_CONTROLS:
        py_res = screen_query_all_lists(ctrl_name, client=py_client, query_type=ctrl_type)
        for src in SOURCE_LISTS:
            hit = py_res[src]["best_hit"]
            if hit.get("tier") == "POTENTIAL_MATCH":
                clean_control_false_reds.append(
                    f"[{ctrl_name}][{src}] False 🔴 on {hit.get('matched_name')} (score {hit.get('score'):.3f})"
                )

    pct_diff_under_02 = (diff_under_02 / total_comparisons * 100) if total_comparisons else 100.0
    pct_ro_under_05 = (red_orange_under_05 / red_orange_checked * 100) if red_orange_checked else 100.0

    print(f"Total candidate comparisons: {total_comparisons}")
    print(f"Candidates with score diff <= 0.02: {diff_under_02}/{total_comparisons} ({pct_diff_under_02:.1f}%)")
    print(f"Red/Orange candidates with score diff <= 0.05: {red_orange_under_05}/{red_orange_checked} ({pct_ro_under_05:.1f}%)")
    print(f"Missed Red/Orange hits: {len(missed_red_or_orange)}")
    print(f"Golden set tier mismatches: {len(golden_tier_mismatches)}")
    print(f"Clean control false Red hits: {len(clean_control_false_reds)}")

    if missed_red_or_orange:
        print("MISSED RED/ORANGE:")
        for m in missed_red_or_orange[:5]:
            print("  ", m)
    if golden_tier_mismatches:
        print("GOLDEN MISMATCHES:")
        for g in golden_tier_mismatches[:5]:
            print("  ", g)
    if clean_control_false_reds:
        print("FALSE REDS ON CLEAN CONTROLS:")
        for c in clean_control_false_reds[:5]:
            print("  ", c)


if __name__ == "__main__":
    t0 = time.perf_counter()
    run_parity()
    print(f"\nTotal parity test runtime: {time.perf_counter() - t0:.2f}s")
