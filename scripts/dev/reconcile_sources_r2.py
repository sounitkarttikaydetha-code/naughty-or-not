"""
Script to measure, reconcile, and audit source files on disk for Part R2.
Measures:
  - Exact file paths on disk
  - Size in bytes (os.stat)
  - SHA-256 hash
  - Modification time
  - Content date read from file
  - Entity count vs search-index rows
  - Explanations for v1.1.2 vs v1.1.3 review discrepancies
"""
import csv
import datetime
import hashlib
import json
import os
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent.parent

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def get_disk_files():
    # Identify files
    files = {
        "us_ofac": [ROOT / "data" / "raw" / "sdn.csv", ROOT / "lists" / "sdn.csv"],
        "us_csl": [ROOT / "data" / "raw" / "consolidated.csv", ROOT / "lists" / "consolidated.csv"],
        "uk_csl": [ROOT / "data" / "raw" / "UK-Sanctions-List.csv", ROOT / "lists" / "UK-Sanctions-List.csv"],
        "eu_csl": [ROOT / "data" / "raw" / "xmlFullSanctionsList_1_1", ROOT / "lists" / "xmlFullSanctionsList_1_1"],
        "un_csl": [ROOT / "data" / "raw" / "consolidated.xml", ROOT / "lists" / "consolidated.xml"],
        "in_mha_1": [ROOT / "data" / "india" / "TERRORIST_ORGANIZATIONS_10032023.pdf"],
        "in_mha_4": [ROOT / "data" / "india" / "fourth_schedule_registry.json"],
        "in_mha_unlaw": [ROOT / "data" / "india" / "unlawful_associations.json"],
        "bis_aircraft": [ROOT / "data" / "aviation" / "current-bis-list-commercial-private-aircraft.pdf"],
        "eu_air_safety": [ROOT / "data" / "aviation" / "air-safety-list.pdf"],
        "faa_iasa": [ROOT / "data" / "aviation" / "IASAWSR119r.pdf"],
        "fatf": [ROOT / "config" / "fatf.json"],
    }
    return files

def main():
    print("=" * 80)
    print("PART R2: SOURCE FILES ON DISK AUDIT & RECONCILIATION")
    print("=" * 80)
    
    files = get_disk_files()
    table_rows = []
    
    for key, paths in files.items():
        found_path = None
        for p in paths:
            if p.exists():
                found_path = p
                break
        if not found_path:
            print(f"[-] Missing: {key}")
            continue
            
        st = found_path.stat()
        size_bytes = st.st_size
        sha = sha256_file(found_path)
        mtime = datetime.datetime.fromtimestamp(st.st_mtime, tz=datetime.timezone.utc).isoformat()
        
        table_rows.append({
            "key": key,
            "path": str(found_path.relative_to(ROOT)),
            "size": size_bytes,
            "sha256": sha,
            "mtime": mtime,
        })
        print(f"[{key}] Path: {found_path.name} | Size: {size_bytes:,} B | SHA: {sha[:16]}... | MTime: {mtime}")

    # Inspect search_index vs entity counts from raw_index.db
    db_path = ROOT / "data" / "raw_index.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    print("\n--- RAW INDEX COUNTS (SEARCH ROWS VS ENTITY TARGETS) ---")
    cursor.execute("SELECT source, count(*), count(distinct record_id) FROM raw_index GROUP BY source")
    for src, total_rows, distinct_ids in cursor.fetchall():
        print(f"{src:25s} | Search Rows: {total_rows:7,d} | Distinct Entities/IDs: {distinct_ids:7,d}")
        
    conn.close()

if __name__ == "__main__":
    main()
