"""
Audit script: check normalisation diff between Python 3.12 and Python 3.14 across all loaded lists.
Extracts every primary_name and alias in raw_index.db (113,094 records),
applies normalize_name() (case-folding, NFKD accent-folding, company word stripping, punctuation stripping),
and compares results.
"""
import json
import sqlite3
import sys
import unicodedata
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from modules.common.alias_splitter import normalize_name

def extract_names_and_normalize(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT source, record_id, primary_name, all_names FROM raw_index")
    
    results = {}
    total_names = 0
    for source, record_id, primary_name, all_names in cursor.fetchall():
        key = f"{source}:{record_id}"
        items = []
        if primary_name:
            items.append(primary_name)
        if all_names:
            items.extend(all_names.split(" | "))
        
        # Deduplicate raw items per record
        unique_items = sorted(set(filter(None, items)))
        total_names += len(unique_items)
        
        # Compute normalized forms
        norm_map = {}
        for item in unique_items:
            norm_tokens = normalize_name(item)
            norm_map[item] = " ".join(norm_tokens)
        results[key] = norm_map
        
    conn.close()
    return results, total_names

if __name__ == "__main__":
    db_path = ROOT / "data" / "raw_index.db"
    out_file = ROOT / "reviews" / f"normalisation_py{sys.version_info.major}{sys.version_info.minor}.json"
    print(f"Running on Python {sys.version}...")
    results, total_names = extract_names_and_normalize(db_path)
    print(f"Processed {len(results)} records, {total_names} unique raw name instances.")
    
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False)
    print(f"Saved to {out_file}")
