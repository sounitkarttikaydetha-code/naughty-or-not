"""
Diff current screening results against reviews/baseline_v1.0.2.json.
Reports any changes in tier, source_id, raw score (> 0.0001), or reason code.
"""

import json
from pathlib import Path
import sys

# Force UTF-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.screening.tiering import screen_query_all_lists
from modules.watchman.client import WatchmanClient

def run_diff(allowed_changes=None):
    if allowed_changes is None:
        allowed_changes = {}

    baseline_path = PROJECT_ROOT / "reviews" / "baseline_v1.0.2.json"
    if not baseline_path.is_file():
        print(f"Error: Baseline file not found at {baseline_path}")
        return False, []

    with open(baseline_path, "r", encoding="utf-8") as f:
        baseline = json.load(f)

    client = WatchmanClient(engine="python")
    differences = []

    print(f"Comparing current engine against {baseline_path.name} ({len(baseline)} queries)...")

    for key, base_entry in baseline.items():
        q = base_entry["query"]
        q_type = base_entry["query_type"]
        res = screen_query_all_lists(q, client=client, query_type=q_type)

        for l_name, base_hit in base_entry["lists"].items():
            curr_hit = res.get(l_name, {}).get("best_hit", {})
            diffs_for_hit = []

            # Check tier
            c_tier = curr_hit.get("tier", "NO_MATCH")
            b_tier = base_hit.get("tier", "NO_MATCH")
            if c_tier != b_tier:
                diffs_for_hit.append(f"tier: {b_tier} -> {c_tier}")

            # Check reason
            c_reason = curr_hit.get("reason", "none")
            b_reason = base_hit.get("reason", "none")
            if c_reason != b_reason:
                diffs_for_hit.append(f"reason: {b_reason} -> {c_reason}")

            # Check score
            c_score = curr_hit.get("score", 0.0)
            b_score = base_hit.get("score", 0.0)
            if abs(c_score - b_score) > 0.0001:
                diffs_for_hit.append(f"score: {b_score:.4f} -> {c_score:.4f}")

            # Check matched source_id
            c_id = curr_hit.get("source_id", "—")
            b_id = base_hit.get("source_id", "—")
            if c_id != b_id:
                diffs_for_hit.append(f"source_id: {b_id} -> {c_id}")

            if diffs_for_hit:
                change_key = f"{key}::{l_name}"
                diff_summary = {
                    "key": key,
                    "query": q,
                    "query_type": q_type,
                    "list": l_name,
                    "diffs": diffs_for_hit,
                    "is_allowed": change_key in allowed_changes,
                    "allowed_explanation": allowed_changes.get(change_key, ""),
                }
                differences.append(diff_summary)

    unexplained = [d for d in differences if not d["is_allowed"]]
    print(f"Total differences found: {len(differences)} (Unexplained: {len(unexplained)})")

    for d in differences:
        tag = "[EXPECTED]" if d["is_allowed"] else "[UNEXPLAINED]"
        print(f"  {tag} {d['query']} ({d['query_type']}) on {d['list']}: {', '.join(d['diffs'])}")
        if d["is_allowed"]:
            print(f"       Note: {d['allowed_explanation']}")

    return len(unexplained) == 0, differences

if __name__ == "__main__":
    success, diffs = run_diff()
    if not success:
        sys.exit(1)
    print("Baseline diff PASSED with zero unexplained changes.")
