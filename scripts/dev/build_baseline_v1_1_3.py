"""
Build Baseline v1.1.3 Outputs for Regression Tracking.
Captures tier, record IDs, raw scores, reasons, matched names, and phonetic codes across all 60 target queries
for the v1.1.3 baseline.
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
    print("=" * 60)
    print("BUILDING BASELINE v1.1.3")
    print(f"Total queries to evaluate: {len(QUERIES)}")
    print("=" * 60)

    client = WatchmanClient(engine="python")
    baseline = {}

    for idx, (q, q_type, group) in enumerate(QUERIES, 1):
        print(f"[{idx:02d}/{len(QUERIES):02d}] Screening '{q}' ({q_type}) [{group}]...")
        res = screen_query_all_lists(q, client=client, query_type=q_type)
        q_entry = {
            "query": q,
            "query_type": q_type,
            "group": group,
            "phonetic_codes": get_phonetic_tuple(q),
            "lists": {},
        }
        for l_name in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]:
            hit = res.get(l_name, {}).get("best_hit", {})
            matched = hit.get("matched_name", "—")
            q_entry["lists"][l_name] = {
                "tier": hit.get("tier", "NO_MATCH"),
                "tier_icon": hit.get("tier_icon", "✅"),
                "score": hit.get("score", 0.0),
                "reason": hit.get("reason", "none"),
                "primary_name": hit.get("primary_name", "—"),
                "matched_name": matched,
                "source_id": hit.get("source_id", "—"),
                "expanded_from": hit.get("expanded_from", ""),
                "below_threshold_count": hit.get("below_threshold_count", 0),
                "matched_phonetic_codes": get_phonetic_tuple(matched),
            }
        key = f"{q}::{q_type}"
        baseline[key] = q_entry

    out_dir = PROJECT_ROOT / "reviews"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "baseline_v1.1.3.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"BASELINE WRITTEN: {out_path} ({len(baseline)} entries)")
    print("=" * 60)


if __name__ == "__main__":
    main()
