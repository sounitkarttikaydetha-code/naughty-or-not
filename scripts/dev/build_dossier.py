"""
Build Dossier Script for Naughty or not v1.0.2 Architecture Dossier.
Measures real performance, counts data records across all sources,
benchmarks matching timings, and extracts database / test inventory.
"""

import csv
import ctypes
from ctypes import wintypes
import json
import os
import platform
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

# Force UTF-8 on Windows stdout/stderr
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Windows Memory API
k32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


psapi.GetProcessMemoryInfo.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
    wintypes.DWORD,
]
psapi.GetProcessMemoryInfo.restype = wintypes.BOOL


def get_ram_usage_mb() -> float:
    try:
        pmc = PROCESS_MEMORY_COUNTERS()
        pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        if psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
            return pmc.WorkingSetSize / (1024 * 1024)
    except Exception:
        pass
    return 0.0


def main():
    print("=" * 60)
    print("NAUGHTY OR NOT v1.0.2 DOSSIER DATA GENERATOR")
    print("=" * 60)

    # 1. Tech stack and environment
    print("\n--- 1. ENVIRONMENT & PLATFORM ---")
    print(f"OS: {platform.system()} {platform.release()} ({platform.version()})")
    print(f"Python: {platform.python_version()} ({platform.python_implementation()})")
    print(f"Architecture: {platform.machine()}")
    print(f"Initial Process RSS: {get_ram_usage_mb():.2f} MB")

    # 2. Config & Thresholds
    print("\n--- 2. CONFIGURATION & SCORING THRESHOLDS ---")
    from modules.screening.config import (
        CANDIDATE_MIN_MATCH,
        DISPLAY_MIN_MATCH,
        DISPLAY_LIMIT,
        POSSIBLE_MATCH_THRESHOLD,
        POTENTIAL_MATCH_THRESHOLD,
        MIN_DISTINCTIVE_WORD_LEN,
        WEAK_WORDS,
        ALIAS_SPLIT_DELIMITERS,
        COMPANY_TYPE_WORDS,
        NAME_VARIANTS,
        COUNTRY_WORDS,
        KNOWN_CITIES,
        FUZZY_WORD_MIN_LEN,
        FUZZY_WORD_MIN_SIMILARITY,
    )
    from modules.engine.scoring import (
        LENGTH_DIFFERENCE_CUTOFF_FACTOR,
        LENGTH_DIFFERENCE_PENALTY_WEIGHT,
        DIFFERENT_LETTER_PENALTY_WEIGHT,
        UNMATCHED_INDEX_TOKEN_WEIGHT,
        NAME_ONLY_PENALTY_MULTIPLIER,
    )

    print(f"Candidate Min Match: {CANDIDATE_MIN_MATCH}")
    print(f"Display Min Match: {DISPLAY_MIN_MATCH}")
    print(f"Display Limit: {DISPLAY_LIMIT}")
    print(f"Possible Match Threshold (Orange): {POSSIBLE_MATCH_THRESHOLD}")
    print(f"Potential Match Threshold (Red): {POTENTIAL_MATCH_THRESHOLD}")
    print(f"Min Distinctive Word Length: {MIN_DISTINCTIVE_WORD_LEN}")
    print(f"Fuzzy Word Min Length: {FUZZY_WORD_MIN_LEN}")
    print(f"Fuzzy Word Min Similarity: {FUZZY_WORD_MIN_SIMILARITY}")
    print(f"Name Only Penalty Multiplier: {NAME_ONLY_PENALTY_MULTIPLIER}")
    print(f"Length Difference Cutoff Factor: {LENGTH_DIFFERENCE_CUTOFF_FACTOR}")
    print(f"Length Difference Penalty Weight: {LENGTH_DIFFERENCE_PENALTY_WEIGHT}")
    print(f"Different Letter Penalty Weight: {DIFFERENT_LETTER_PENALTY_WEIGHT}")
    print(f"Unmatched Index Token Weight: {UNMATCHED_INDEX_TOKEN_WEIGHT}")
    print(f"Count of Weak Words: {len(WEAK_WORDS)} (e.g., {WEAK_WORDS[:5]})")
    print(f"Count of Company Type Words: {len(COMPANY_TYPE_WORDS)} (e.g., {COMPANY_TYPE_WORDS[:5]})")
    print(f"Count of Country Words: {len(COUNTRY_WORDS)} (e.g., {COUNTRY_WORDS[:5]})")
    print(f"Count of Known Cities: {len(KNOWN_CITIES)} (e.g., {list(KNOWN_CITIES)[:5]})")
    print(f"Count of Name Variants: {len(NAME_VARIANTS)} (e.g., {list(NAME_VARIANTS.items())[:3]})")
    print(f"Alias Split Delimiters: {ALIAS_SPLIT_DELIMITERS}")

    # Airline aliases
    alias_csv = PROJECT_ROOT / "data" / "aviation" / "airline_aliases.csv"
    alias_rows = 0
    if alias_csv.is_file():
        with open(alias_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            alias_rows = sum(1 for _ in reader)
    print(f"Count of Airline Alias Expansion Rows: {alias_rows}")

    # 3. Source Records Count & Parsing
    print("\n--- 3. DATA SOURCES & RECORD COUNTS ---")
    # Python Engine (5 Sanctions Lists)
    t0 = time.perf_counter()
    from modules.engine.engine import PythonEngine
    engine = PythonEngine(data_dir=PROJECT_ROOT / "data" / "raw")
    t_engine_load = time.perf_counter() - t0
    info = engine.listinfo()
    sanctions_counts = info.get("lists", {})
    print(f"Python Engine Load Time: {t_engine_load:.3f} s")
    print(f"Post-Engine Load RSS: {get_ram_usage_mb():.2f} MB")
    for k, v in sanctions_counts.items():
        print(f"  - {k}: {v:,} records (hash: {info.get('listHashes', {}).get(k, '')[:12]}...)")

    # Aviation Sources
    from modules.aviation.parser import parse_bis_aircraft, parse_eu_air_safety_list, parse_faa_iasa
    bis_data = parse_bis_aircraft(PROJECT_ROOT / "data" / "aviation" / "bis_aircraft.pdf")
    eu_asl = parse_eu_air_safety_list(PROJECT_ROOT / "data" / "aviation" / "eu_air_safety_list.pdf")
    faa_data = parse_faa_iasa(PROJECT_ROOT / "data" / "aviation" / "faa_iasa.pdf")
    print(f"  - bis_aircraft: {len(bis_data.get('active', []))} active aircraft, {len(bis_data.get('removals', []))} removals")
    print(f"  - eu_air_safety_list: {len(eu_asl.get('annex_a', []))} Annex A carriers, {len(eu_asl.get('annex_b', []))} Annex B carriers, {len(eu_asl.get('banned_states', []))} banned states")
    print(f"  - faa_iasa: {len(faa_data.get('countries', []))} Category 2 jurisdictions")

    # India Sources
    from modules.india.parser import parse_first_schedule, parse_fourth_schedule, parse_unlawful_associations
    mha_1 = parse_first_schedule(PROJECT_ROOT / "data" / "india" / "first_schedule.pdf")
    mha_4 = parse_fourth_schedule(PROJECT_ROOT / "data" / "india" / "individuals_all.json")
    mha_u = parse_unlawful_associations(PROJECT_ROOT / "data" / "india" / "unlawful_associations_all.json")
    print(f"  - in_mha_first_schedule: {len(mha_1.get('entities', []))} organisations")
    print(f"  - in_mha_fourth_schedule: {len(mha_4.get('entities', []))} individuals")
    print(f"  - in_mha_unlawful_assoc: {len(mha_u.get('entities', []))} associations")

    # FATF
    with open(PROJECT_ROOT / "config" / "fatf_lists.json", "r", encoding="utf-8") as f:
        fatf_json = json.load(f)
    print(f"  - fatf_jurisdictions: {len(fatf_json.get('black_list', []))} high-risk (black), {len(fatf_json.get('grey_list', []))} monitored (grey)")

    # 4. Raw Index FTS5
    print("\n--- 4. RAW TEXT SEARCH INDEX (SQLITE FTS5) ---")
    raw_db_path = PROJECT_ROOT / "data" / "raw_index.db"
    if not raw_db_path.is_file():
        from modules.common.paths import get_index_db_path
        raw_db_path = get_index_db_path()

    if raw_db_path.is_file():
        db_size_mb = raw_db_path.stat().st_size / (1024 * 1024)
        con = sqlite3.connect(str(raw_db_path))
        cur = con.cursor()
        total_indexed = cur.execute("SELECT COUNT(*) FROM raw_index;").fetchone()[0]
        source_breakdown = cur.execute("SELECT source, status, record_count, list_date FROM source_meta;").fetchall()
        print(f"Raw Index Database: {raw_db_path}")
        print(f"Database Size: {db_size_mb:.2f} MB")
        print(f"Total FTS5 Indexed Records: {total_indexed:,}")
        for s, st, rc, ld in source_breakdown:
            print(f"    * {s}: {rc:,} records ({st}, date: {ld})")
        con.close()
    else:
        print(f"Raw index database not found at {raw_db_path}")

    # 5. Search & Screening Performance Benchmarks
    print("\n--- 5. PERFORMANCE BENCHMARKS (TIMINGS) ---")
    from modules.screening.tiering import screen_query_all_lists
    from modules.watchman.client import WatchmanClient

    client = WatchmanClient(engine="python")

    # Warm search 1: Aeroflot (Airline)
    t0 = time.perf_counter()
    res_aero = screen_query_all_lists("Aeroflot", client=client, query_type="airline")
    t_aero = time.perf_counter() - t0
    print(f"Screening 'Aeroflot' (Airline, with airline alias expansion): {t_aero * 1000:.2f} ms")
    for src in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]:
        bh = res_aero[src]["best_hit"]
        print(f"    * {src}: [{bh['tier_icon']}] {bh['tier']} (score: {bh['score']:.4f}, reason: {bh['reason']})")

    # Warm search 2: Jaipur International Airport Limited (Clean Organisation)
    t0 = time.perf_counter()
    res_clean = screen_query_all_lists("Jaipur International Airport Limited", client=client, query_type="organisation")
    t_clean = time.perf_counter() - t0
    print(f"Screening 'Jaipur International Airport Limited' (Clean Organisation): {t_clean * 1000:.2f} ms")
    for src in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]:
        bh = res_clean[src]["best_hit"]
        print(f"    * {src}: [{bh['tier_icon']}] {bh['tier']} (score: {bh['score']:.4f}, info_hits: {bh.get('below_threshold_count', 0)})")

    # Warm search 3: Raw Search FTS5
    if raw_db_path.is_file():
        from modules.raw_search.engine import RawSearchEngine
        raw_engine = RawSearchEngine(db_path=raw_db_path)
        t0 = time.perf_counter()
        raw_res = raw_engine.search("RUS2426", limit=25)
        t_raw = time.perf_counter() - t0
        print(f"Raw Search 'RUS2426' (FTS5 trigram): {t_raw * 1000:.2f} ms ({len(raw_res.get('results', []))} results)")

    # Benchmark Report Generation
    from modules.reporting.generator import generate_reports
    t0 = time.perf_counter()
    source_statuses = [{"source": s, "status": "OK"} for s in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]]
    sanctions_hits = res_aero["us_csl"]["red_hits"]
    pdf_path, xlsx_path = generate_reports(
        search_type="airline",
        inputs={"name": "Aeroflot"},
        overall_banner="Potential Match",
        source_statuses=source_statuses,
        sanctions_hits=sanctions_hits,
        aviation_hits=[],
        country_risk_hits=[],
        opensanctions_used=False,
    )
    t_rep = time.perf_counter() - t0
    print(f"Report Generation (PDF + Excel): {t_rep * 1000:.2f} ms")
    print(f"  PDF Size: {pdf_path.stat().st_size / 1024:.1f} KB ({pdf_path.name})")
    print(f"  Excel Size: {xlsx_path.stat().st_size / 1024:.1f} KB ({xlsx_path.name})")

    # Benchmark Manual Check Save
    from modules.reporting.logger import log_manual_check
    t0 = time.perf_counter()
    log_manual_check(
        name="Aeroflot",
        source="eu_air_safety_list",
        result="MATCH",
        comment="Verified Annex A entry for evaluation",
        user="ComplianceOfficer",
    )
    t_mc = time.perf_counter() - t0
    print(f"Manual Check SQLite Save: {t_mc * 1000:.2f} ms")

    # 6. Audit Database Schema & Row
    print("\n--- 6. AUDIT DATABASE (SCREENING.DB) ---")
    from modules.reporting.logger import DB_PATH, get_db_connection
    print(f"Database Location: {DB_PATH}")
    conn = get_db_connection()
    cur = conn.cursor()
    cols = cur.execute("PRAGMA table_info(screening_logs);").fetchall()
    print("Columns in screening_logs:")
    for col in cols:
        print(f"    - {col[1]} ({col[2]})")
    total_logs = cur.execute("SELECT COUNT(*) FROM screening_logs;").fetchone()[0]
    total_ack = cur.execute("SELECT COUNT(*) FROM acknowledgement_logs;").fetchone()[0]
    modes_count = cur.execute("SELECT mode, COUNT(*) FROM screening_logs GROUP BY mode;").fetchall()
    print(f"Total Logged Screening Rows: {total_logs} (Breakdown by mode: {dict(modes_count)})")
    print(f"Total Acknowledgement Rows: {total_ack}")
    latest_row = cur.execute("SELECT * FROM screening_logs ORDER BY id DESC LIMIT 1;").fetchone()
    if latest_row:
        print(f"Sample Log Row (ID {latest_row[0]}): timestamp={latest_row[1]}, mode={latest_row[4]}, type={latest_row[5]}, result={latest_row[9]}, score={latest_row[11]}")
    conn.close()

    # 7. Test Inventory & Golden Set
    print("\n--- 7. TEST INVENTORY & GOLDEN REGRESSION SET ---")
    golden_path = PROJECT_ROOT / "tests" / "golden_set.json"
    if golden_path.is_file():
        with open(golden_path, "r", encoding="utf-8") as f:
            golden_data = json.load(f)
        total_queries = len(golden_data)
        total_list_entries = 0
        verified_locks = 0
        tiers_count = {}
        for q_name, q_val in golden_data.items():
            lists = q_val.get("lists", {})
            total_list_entries += len(lists)
            for l_name, l_info in lists.items():
                t = l_info.get("tier")
                tiers_count[t] = tiers_count.get(t, 0) + 1
                if l_info.get("verified"):
                    verified_locks += 1
        print(f"Total Golden Set Queries: {total_queries}")
        print(f"  - Total List Expectations: {total_list_entries}")
        print(f"  - Verified Locks (verified: true): {verified_locks}")
        print(f"Expected Tier Distribution across all query-lists: {tiers_count}")

    # Pytest count
    try:
        proc = subprocess.run(
            [str(PROJECT_ROOT / ".venv" / "Scripts" / "pytest.exe"), "--collect-only", "-q"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        test_lines = [l for l in proc.stdout.splitlines() if "::" in l]
        print(f"Total Pytest Test Cases Collected: {len(test_lines)}")
    except Exception as e:
        print(f"Pytest collection error: {e}")

    # 8. Distribution Files Sizes
    print("\n--- 8. DISTRIBUTION ARTIFACT SIZES ---")
    dist_dir = PROJECT_ROOT / "dist"
    installer_dir = dist_dir / "installer"
    if installer_dir.is_dir():
        for f in sorted(installer_dir.iterdir()):
            print(f"  - {f.name}: {f.stat().st_size / (1024 * 1024):.2f} MB")

    data_raw_dir = PROJECT_ROOT / "data" / "raw"
    if data_raw_dir.is_dir():
        raw_size = sum(f.stat().st_size for f in data_raw_dir.iterdir() if f.is_file())
        print(f"  - Seed Sanctions Directory (data/raw): {raw_size / (1024 * 1024):.2f} MB ({len(list(data_raw_dir.iterdir()))} files)")

    print(f"Peak Process RSS: {get_ram_usage_mb():.2f} MB")
    print("\n" + "=" * 60)
    print("DOSSIER DATA GENERATION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
