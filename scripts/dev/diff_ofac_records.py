"""
Compare OFAC sdn.csv between the 5,744,136 B version and the 5,750,799 B version.
Extract added and removed record IDs and reconcile the counts.
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

def load_ofac_ids(csv_path: Path):
    ids = set()
    rows = []
    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        for r in reader:
            if r and r[0].strip().isdigit():
                ids.add(r[0].strip())
                rows.append(r[0].strip())
    return ids, len(rows)

def main():
    p1 = ROOT / "dist" / "ClearanceCheck" / "_internal" / "data" / "raw" / "us_ofac_sdn.csv"
    p2 = ROOT / "data" / "raw" / "us_ofac_sdn.csv"
    p3 = ROOT / "lists" / "raw" / "us_ofac_sdn.csv"
    
    print(f"File 1: {p1} ({p1.stat().st_size:,} bytes)")
    print(f"File 2: {p2} ({p2.stat().st_size:,} bytes)")
    print(f"File 3: {p3} ({p3.stat().st_size:,} bytes)")
    
    ids1, count1 = load_ofac_ids(p1)
    ids2, count2 = load_ofac_ids(p2)
    ids3, count3 = load_ofac_ids(p3)
    
    print(f"\nFile 1 (5,744,136 B): Total rows = {count1}, Unique IDs = {len(ids1)}")
    print(f"File 2 (5,750,799 B): Total rows = {count2}, Unique IDs = {len(ids2)}")
    print(f"File 3 (5,833,851 B): Total rows = {count3}, Unique IDs = {len(ids3)}")
    
    diff_add_1_2 = ids2 - ids1
    diff_rem_1_2 = ids1 - ids2
    print(f"\nBetween File 1 and File 2:")
    print(f"  Added IDs count: {len(diff_add_1_2)}")
    print(f"  Removed IDs count: {len(diff_rem_1_2)}")
    print(f"  Net change: {len(ids2) - len(ids1)}")
    
    diff_add_2_3 = ids3 - ids2
    diff_rem_2_3 = ids2 - ids3
    print(f"\nBetween File 2 and File 3 (Latest 10 Nov):")
    print(f"  Added IDs count: {len(diff_add_2_3)}")
    print(f"  Removed IDs count: {len(diff_rem_2_3)}")
    print(f"  Net change: {len(ids3) - len(ids2)}")
    if diff_add_2_3:
        print(f"  Sample added IDs in File 3: {sorted(list(diff_add_2_3))[:10]}")

if __name__ == "__main__":
    main()
