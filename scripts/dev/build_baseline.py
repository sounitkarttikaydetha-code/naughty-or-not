"""
Build Baseline v1.0.2 Outputs for Regression Tracking.
Captures tier, record IDs, raw scores, reasons, and matched names across all target queries.
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

# All queries to lock into baseline
QUERIES = [
    # Golden Set (21)
    ("Sberbank", "organisation", "golden_set"),
    ("Sberbank of Russia", "organisation", "golden_set"),
    ("VTB Bank", "organisation", "golden_set"),
    ("S7 Airlines", "airline", "golden_set"),
    ("Siberia Airlines", "airline", "golden_set"),
    ("Aeroflot", "airline", "golden_set"),
    ("Azur Air", "airline", "golden_set"),
    ("UTair", "airline", "golden_set"),
    ("Jaipur International Airport Limited", "organisation", "golden_set"),
    ("Adani Airport Holdings Limited", "organisation", "golden_set"),
    ("Air India", "organisation", "golden_set"),
    ("IndiGo", "airline", "golden_set"),
    ("InterGlobe Aviation Limited", "airline", "golden_set"),
    ("Siberian Wellness", "organisation", "golden_set"),
    ("Rajesh Kumar", "person", "golden_set"),
    ("Mohammed Khan", "person", "golden_set"),
    ("Sky Bank", "organisation", "golden_set"),
    ("Volga Logistics", "organisation", "golden_set"),
    ("S7", "airline", "golden_set"),
    ("Aeroflot Russian Airlines", "airline", "golden_set"),
    ("Siberian Airlines", "organisation", "golden_set"),

    # 19 Agreed Queries delta
    ("PJSC Sberbank", "organisation", "19_agreed"),

    # 29 Independent Check delta
    ("Larsen & Toubro", "organisation", "29_independent"),
    ("SpiceJet", "airline", "29_independent"),
    ("Akasa Air", "airline", "29_independent"),
    ("Tata Steel", "organisation", "29_independent"),
    ("Bharat Petroleum", "organisation", "29_independent"),
    ("Rosneft", "organisation", "29_independent"),
    ("Gazprombank", "organisation", "29_independent"),
    ("Mahan Air", "airline", "29_independent"),

    # T8-5 Probes
    ("Ural", "airline", "t8_5_probes"),
    ("Rossiya", "airline", "t8_5_probes"),
    ("Pobeda", "airline", "t8_5_probes"),
    ("Homa", "airline", "t8_5_probes"),
    ("Nord Wind", "airline", "t8_5_probes"),
    ("Ural Airlines", "airline", "t8_5_probes"),

    # T8-6 Probes
    ("VTB", "organisation", "t8_6_probes"),
    ("S7", "organisation", "t8_6_probes"),
    ("IRGC", "organisation", "t8_6_probes"),
    ("ZTE", "organisation", "t8_6_probes"),
    ("Bank", "organisation", "t8_6_probes"),
    ("Air", "organisation", "t8_6_probes"),
    ("International", "organisation", "t8_6_probes"),
    ("Сбербанк", "organisation", "t8_6_probes"),
    ("طيران ماهان", "airline", "t8_6_probes"),

    # T8-6A Probes
    ("Qaddafi", "person", "t8_6a_probes"),
    ("Kadhafi", "person", "t8_6a_probes"),
    ("Gadhafi", "person", "t8_6a_probes"),
    ("Hussein", "person", "t8_6a_probes"),
    ("Husayn", "person", "t8_6a_probes"),
    ("Yevgeny", "person", "t8_6a_probes"),
    ("Evgeniy", "person", "t8_6a_probes"),
    ("Sheikh", "person", "t8_6a_probes"),
    ("Shaikh", "person", "t8_6a_probes"),
    ("Chaudhary", "person", "t8_6a_probes"),
    ("Choudhary", "person", "t8_6a_probes"),
    ("Wladimir", "person", "t8_6a_probes"),
    ("Vladimir", "person", "t8_6a_probes"),
    ("Vladimir Putin", "person", "t8_6a_probes"),
    ("Kim Jong Un", "person", "t8_6a_probes"),
]

def main():
    print("=" * 60)
    print("BUILDING BASELINE v1.0.2")
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
            "lists": {},
        }
        for l_name in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]:
            hit = res.get(l_name, {}).get("best_hit", {})
            q_entry["lists"][l_name] = {
                "tier": hit.get("tier", "NO_MATCH"),
                "tier_icon": hit.get("tier_icon", "✅"),
                "score": hit.get("score", 0.0),
                "reason": hit.get("reason", "none"),
                "primary_name": hit.get("primary_name", "—"),
                "matched_name": hit.get("matched_name", "—"),
                "source_id": hit.get("source_id", "—"),
                "expanded_from": hit.get("expanded_from", ""),
                "below_threshold_count": hit.get("below_threshold_count", 0),
            }
        # Key by (query, query_type)
        key = f"{q}::{q_type}"
        baseline[key] = q_entry

    out_dir = PROJECT_ROOT / "reviews"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "baseline_v1.0.2.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"BASELINE WRITTEN: {out_path} ({len(baseline)} entries)")
    print("=" * 60)

if __name__ == "__main__":
    main()
