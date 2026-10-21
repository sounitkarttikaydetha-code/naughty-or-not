"""
Test script to verify Top-25 Candidate Overlap:
- Jaccard and set overlap for each query x list
- Average overlap >= 90%
- No candidate scoring >= 0.60 in Watchman is missing from Python's top 25
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.watchman.client import WatchmanClient
from modules.screening.tiering import screen_query_all_lists, SOURCE_LISTS
from scripts.dev.run_parity_check import TEST_QUERIES


def run_overlap_check():
    sys.stdout.reconfigure(encoding="utf-8")
    py_client = WatchmanClient(engine="python")
    wm_client = WatchmanClient(engine="watchman")

    jaccard_scores = []
    set_overlaps = []
    missing_high_scoring = []

    print(f"{'Query':<25} | {'List':<8} | {'WM Top25':<8} | {'PY Top25':<8} | {'Overlap':<8} | {'Jaccard':<8}")
    print("-" * 75)

    for q_name, q_type in TEST_QUERIES:
        py_res = screen_query_all_lists(q_name, client=py_client, query_type=q_type)
        wm_res = screen_query_all_lists(q_name, client=wm_client, query_type=q_type)

        for src in SOURCE_LISTS:
            wm_all = wm_res[src].get("all_candidates", [])
            py_all = py_res[src].get("all_candidates", [])

            wm_top25 = wm_all[:25]
            py_top25 = py_all[:25]

            wm_ids = [c["source_id"] for c in wm_top25 if c.get("source_id")]
            py_ids = [c["source_id"] for c in py_top25 if c.get("source_id")]

            wm_set = set(wm_ids)
            py_set = set(py_ids)

            intersection = wm_set & py_set
            union = wm_set | py_set

            # Set overlap relative to Watchman's count
            overlap = len(intersection) / len(wm_set) if wm_set else 1.0
            jaccard = len(intersection) / len(union) if union else 1.0

            jaccard_scores.append(jaccard)
            set_overlaps.append(overlap)

            # Check if any candidate scoring >= 0.60 in Watchman is missing from Python's top 25
            py_top25_set = set(py_ids)
            py_min_score = py_top25[-1].get("score", 0.0) if len(py_top25) >= 25 else 0.0
            for c in wm_top25:
                score = c.get("score", 0.0)
                if score >= 0.60:
                    sid = c.get("source_id")
                    if sid and sid not in py_top25_set:
                        # Exclude boundary ties where Python's 25th candidate has the exact same score
                        if abs(score - py_min_score) < 1e-4:
                            continue
                        missing_high_scoring.append(
                            f"[{q_name}][{src}] ID {sid} ({c.get('matched_name')}) scored {c.get('score'):.3f} in WM but not in PY top 25"
                        )

            print(f"{q_name:<25} | {src:<8} | {len(wm_ids):<8} | {len(py_ids):<8} | {overlap*100:6.1f}% | {jaccard*100:6.1f}%")

    avg_overlap = sum(set_overlaps) / len(set_overlaps) if set_overlaps else 0.0
    avg_jaccard = sum(jaccard_scores) / len(jaccard_scores) if jaccard_scores else 0.0

    print("\n=== SUMMARY ===")
    print(f"Total query x list pairs evaluated: {len(set_overlaps)}")
    print(f"Average Set Overlap: {avg_overlap*100:.1f}% (target >= 90%)")
    print(f"Average Jaccard Overlap: {avg_jaccard*100:.1f}%")
    print(f"Missing >= 0.60 candidates: {len(missing_high_scoring)} (target 0)")
    if missing_high_scoring:
        print("Missing candidates scoring >= 0.60:")
        for m in missing_high_scoring[:10]:
            print("  ", m)


if __name__ == "__main__":
    run_overlap_check()
