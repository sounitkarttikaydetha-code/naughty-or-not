#!/usr/bin/env python3
"""
Build Review Tables Script
Generates markdown review tables by querying the live screening engine.
All numbers and tier reason codes in review tables originate strictly from this script.
Outputs tables to reviews/_generated_tables.md.
"""

import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.screening.tiering import screen_query_all_lists
from modules.india.client import IndiaClient
from modules.watchman.client import WatchmanClient

AGREED_QUERIES = [
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
]

EXPANDED_AIRLINE_QUERIES = [
    ("Siberia Airlines", "airline"),
    ("S7", "airline"),
    ("Aeroflot Russian Airlines", "airline"),
]

SOURCE_ORDER = ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl", "in_mha"]


def format_hit_cell(res_data: dict) -> str:
    hit = res_data.get("best_hit", {}) if isinstance(res_data, dict) else {}
    tier = hit.get("tier")
    score = hit.get("score", 0.0)
    reason = hit.get("reason", "none")
    below_count = hit.get("below_threshold_count") or len(res_data.get("info_hits", [])) if isinstance(res_data, dict) else 0
    if tier == "POTENTIAL_MATCH":
        icon = "🔴"
    elif tier == "POSSIBLE_MATCH_REVIEW":
        icon = "🟠"
    elif tier == "NO_MATCH":
        icon = "✅"
    else:
        icon = "⚪"
    info_suffix = f" +{below_count}ℹ️" if below_count > 0 else ""
    return f"{icon} {score:.4f} ({reason}){info_suffix}"


def main():
    watchman = WatchmanClient()
    india = IndiaClient()

    reviews_dir = PROJECT_ROOT / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    out_file = reviews_dir / "_generated_tables.md"

    lines = []
    lines.append("### 2. Full Per-List Tier Table: 19 Agreed Queries × 6 Lists")
    lines.append("")
    lines.append("| Query | us_ofac | us_csl | uk_csl | eu_csl | un_csl | in_mha |")
    lines.append("|---|---|---|---|---|---|---|")

    print("Screening 19 agreed queries...")
    for q, qtype in AGREED_QUERIES:
        w_res = screen_query_all_lists(q, client=watchman, query_type=qtype)
        mha_search_type = "INDIVIDUAL" if qtype == "person" else "ORGANIZATION"
        in_res = india.screen(q, search_type=mha_search_type)

        cells = []
        for src in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]:
            res_data = w_res.get(src, {})
            cells.append(format_hit_cell(res_data))

        # Format India MHA hit
        mha_tier = in_res.get("tier", "NO_MATCH")
        mha_score = in_res.get("matches", [{}])[0].get("score", 0.0) if in_res.get("matches") else 0.0
        mha_icon = "🔴" if mha_tier == "POTENTIAL_MATCH" else ("🟠" if mha_tier == "POSSIBLE_MATCH_REVIEW" else ("✅" if mha_tier == "NO_MATCH" else "⚪"))
        mha_reason = "mha_core" if mha_tier == "POTENTIAL_MATCH" else "none"
        cells.append(f"{mha_icon} {mha_score:.4f} ({mha_reason})")

        row_str = f"| {q} | " + " | ".join(cells) + " |"
        lines.append(row_str)

    lines.append("")
    lines.append("### 2b. Expanded Airline Queries Table")
    lines.append("")
    lines.append("| Query | List | Tier | Best Hit / Listed Name | Score | Reason | Matched Name | Expanded From |")
    lines.append("|---|---|---|---|---|---|---|---|")

    print("Screening expanded airline queries...")
    for q, qtype in EXPANDED_AIRLINE_QUERIES:
        w_res = screen_query_all_lists(q, client=watchman, query_type=qtype)
        for src in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]:
            hit = w_res.get(src, {}).get("best_hit", {})
            tier_icon = hit.get("tier_icon", "✅")
            tier_str = hit.get("tier", "NO_MATCH")
            p_name = hit.get("primary_name", "—")
            score_val = hit.get("score", 0.0)
            reason_str = hit.get("reason", "none")
            m_name = hit.get("matched_name", "—")
            exp_from = hit.get("expanded_from") or "—"
            lines.append(f"| {q} | {src} | {tier_icon} {tier_str} | {p_name} | {score_val:.4f} | {reason_str} | {m_name} | {exp_from} |")

    content = "\n".join(lines) + "\n"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Tables successfully written to {out_file}")


if __name__ == "__main__":
    main()
