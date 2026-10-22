"""
Measure recall on 200 non-clean sample names from the 5 lists for T8-6A.
"""

import json
import random
import sys
from pathlib import Path
sys.path.insert(0, ".")
from modules.screening.tiering import screen_query_all_lists
from modules.watchman.client import WatchmanClient, get_python_engine

def run_recall_eval():
    client = WatchmanClient(engine="python")
    engine = get_python_engine()
    
    # Collect sample names from the 5 lists
    random.seed(42)
    sample_records = []
    for src in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]:
        recs = engine.records_by_source.get(src, [])
        for r in recs:
            if len(r.prepared_name.split()) >= 1 and len(r.prepared_name) >= 4:
                sample_records.append((src, r.source_id, r.prepared_name, r.entity_type))
    
    selected_sample = random.sample(sample_records, 200)

    # 1. Evaluate with PHONETIC_ENABLED = True
    elevated_count = 0
    orange_or_red_count = 0
    info_or_better_count = 0

    for src, sid, name, etype in selected_sample:
        # Run search
        q_type = etype if etype in ["individual", "person", "organisation", "aircraft", "vessel"] else None
        res = screen_query_all_lists(name, client=client, query_type=q_type)
        hit = res.get(src, {}).get("best_hit", {})
        tier = hit.get("tier", "NO_MATCH")
        reason = hit.get("reason", "")
        
        if tier in ["POTENTIAL_MATCH", "POSSIBLE_MATCH_REVIEW"]:
            orange_or_red_count += 1
            if "phonetic" in reason:
                elevated_count += 1
        if tier in ["POTENTIAL_MATCH", "POSSIBLE_MATCH_REVIEW", "BELOW_THRESHOLD"]:
            info_or_better_count += 1

    print("200-sample recall evaluation (seed 42):")
    print(f"  Recall at ORANGE or better: {orange_or_red_count}/200 ({orange_or_red_count/200*100:.1f}%) [Target >= 98.0%]")
    print(f"  Recall at INFO or better: {info_or_better_count}/200 ({info_or_better_count/200*100:.1f}%) [Target 100.0%]")
    print(f"  Phonetic elevations: {elevated_count}")

if __name__ == "__main__":
    run_recall_eval()
