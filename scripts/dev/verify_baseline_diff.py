"""
Verify baseline diff between baseline_v1.1.3.json and current screening engine under Python 3.14.
Checks all 60 queries: tiers, record IDs, raw scores (to 4 decimal places), phonetic codes, and reason codes.
"""
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import metaphone
from modules.screening.tiering import screen_query_all_lists
from modules.watchman.client import WatchmanClient
from scripts.dev.build_baseline import QUERIES

def get_phonetic_tuple(name: str):
    if not name or name == "—":
        return []
    codes = []
    for word in name.split():
        clean = "".join(c for c in word if c.isalnum())
        if clean:
            p, s = metaphone.doublemetaphone(clean)
            codes.append(f"{p}/{s}")
    return codes

def main():
    baseline_file = PROJECT_ROOT / "reviews" / "baseline_v1.1.3.json"
    with open(baseline_file, "r", encoding="utf-8") as f:
        baseline_data = json.load(f)

    print(f"Comparing current engine against {baseline_file.name} under Python {sys.version}...")
    client = WatchmanClient(engine="python")

    diffs = []
    total_checks = 0

    for idx, (q, q_type, group) in enumerate(QUERIES, 1):
        q_key = f"{q}::{q_type}"
        base_q = baseline_data.get(q_key)
        if not base_q:
            diffs.append(f"Missing query in baseline: {q_key}")
            continue

        res = screen_query_all_lists(q, client=client, query_type=q_type)
        phonetics = get_phonetic_tuple(q)

        # Check phonetic codes
        if phonetics != base_q.get("phonetic_codes", []):
            diffs.append(f"[{q}] Phonetic codes diff: base={base_q.get('phonetic_codes')} curr={phonetics}")

        for l_name in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]:
            total_checks += 1
            hit = res.get(l_name, {}).get("best_hit", {})
            base_hit = base_q["lists"].get(l_name, {})

            curr_tier = hit.get("tier")
            base_tier = base_hit.get("tier")
            if curr_tier != base_tier:
                diffs.append(f"[{q}][{l_name}] Tier diff: base={base_tier} curr={curr_tier}")

            curr_score = round(float(hit.get("score", 0.0)), 4)
            base_score = round(float(base_hit.get("score", 0.0)), 4)
            if curr_score != base_score:
                diffs.append(f"[{q}][{l_name}] Score diff: base={base_score} curr={curr_score}")

            curr_reason = hit.get("reason")
            base_reason = base_hit.get("reason")
            if curr_reason != base_reason:
                diffs.append(f"[{q}][{l_name}] Reason diff: base={base_reason} curr={curr_reason}")

            curr_id = str(hit.get("source_id", "") or "")
            base_id = str(base_hit.get("source_id", "") or "")
            if curr_id != base_id:
                diffs.append(f"[{q}][{l_name}] Record ID diff: base={base_id} curr={curr_id}")

    print(f"Completed {len(QUERIES)} queries ({total_checks} list evaluations).")
    print(f"Total differences found: {len(diffs)}")
    if diffs:
        for d in diffs:
            print("  DIFF:", d)
        sys.exit(1)
    else:
        print("PERFECT MATCH: Baseline diff is ZERO across all tiers, record IDs, raw scores (to 4 decimal places), phonetic codes, and reason codes!")
        sys.exit(0)

if __name__ == "__main__":
    main()
