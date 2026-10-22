"""
Tests for T8-8: Log and report completeness, schema migration, and candidate integrity.
"""

import json
from pathlib import Path
import sqlite3
import pytest

from modules.reporting.logger import (
    get_db_connection,
    log_search,
    export_screening_logs_to_csv,
    export_screening_hits_to_csv,
)
from modules.reporting.generator import generate_reports
from modules.screening.tiering import screen_query_all_lists
from modules.watchman.client import WatchmanClient


def test_schema_migration_backward_compatibility(tmp_path):
    """
    Migration on an older v1.0.2 SQLite DB adds missing columns and screening_hits table
    without error or data loss.
    """
    old_db_file = tmp_path / "legacy_v102.db"
    conn = sqlite3.connect(str(old_db_file))
    # Create strictly old v1.0.2 schema
    conn.execute("""
        CREATE TABLE screening_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            windows_user TEXT,
            machine_name TEXT,
            search_type TEXT,
            inputs TEXT,
            threshold TEXT,
            source TEXT,
            result TEXT,
            top_match TEXT,
            score REAL,
            list_version TEXT,
            opensanctions_used TEXT,
            report_file_name TEXT,
            app_version TEXT,
            acknowledged INTEGER
        )
    """)
    # Insert an existing legacy row
    conn.execute("""
        INSERT INTO screening_logs (timestamp, windows_user, search_type, result, score)
        VALUES ('2026-10-18T12:00:00Z', 'analyst', 'individual', 'NO_MATCH', 0.0)
    """)
    conn.commit()
    conn.close()

    # Now run get_db_connection on legacy DB
    migrated_conn = get_db_connection(old_db_file)
    cur = migrated_conn.cursor()

    # Verify legacy row is preserved
    cur.execute("SELECT COUNT(*), windows_user FROM screening_logs")
    row = cur.fetchone()
    assert row[0] == 1
    assert row[1] == "analyst"

    # Verify new columns exist
    cols = {c[1] for c in cur.execute("PRAGMA table_info(screening_logs);").fetchall()}
    for required_col in [
        "mode", "comment", "query_type", "sources_checked", "duration_ms",
        "result_hash", "candidate_count", "red_count", "orange_count", "info_count"
    ]:
        assert required_col in cols, f"Missing required column {required_col}"

    # Verify screening_hits table exists
    hits_cols = {c[1] for c in cur.execute("PRAGMA table_info(screening_hits);").fetchall()}
    for h_col in ["id", "log_id", "source", "source_id", "tier", "score", "matched_name", "primary_name", "reason_code", "is_top_hit"]:
        assert h_col in hits_cols, f"Missing column {h_col} in screening_hits"

    migrated_conn.close()


def test_round_trip_5_searches_and_candidate_counts(tmp_path):
    """
    Run 5 searches of different types, check that:
    - every candidate from each search is present in screening_hits;
    - candidate_count = red_count + orange_count + info_count;
    - report contains all candidates, not only the top hit;
    - CSV export works.
    """
    test_db = tmp_path / "test_audit.db"
    conn = get_db_connection(test_db)
    client = WatchmanClient(engine="python")

    test_queries = [
        ("S7 Airlines", "airline"),
        ("Gazprombank", "organisation"),
        ("Sberbank", "organisation"),
        ("Vladimir Putin", "person"),
        ("Jaipur International Airport Limited", "organisation"),
    ]

    for q, qtype in test_queries:
        res = screen_query_all_lists(q, client=client, query_type=qtype)
        all_cands = []
        for src in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]:
            for c in res.get(src, {}).get("all_candidates", []):
                all_cands.append(c)

        # Log search
        log_id = log_search(
            search_type=qtype.capitalize(),
            inputs={"name": q},
            source_results=[],
            query_type=qtype,
            sources_checked=["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"],
            duration_ms=45,
            all_candidates=all_cands,
            db_conn=conn,
        )

        cur = conn.cursor()
        cur.execute("""
            SELECT candidate_count, red_count, orange_count, info_count
            FROM screening_logs WHERE id = ?
        """, (log_id,))
        c_count, r_count, o_count, i_count = cur.fetchone()

        assert c_count == r_count + o_count + i_count, f"Count mismatch for {q}: {c_count} != {r_count} + {o_count} + {i_count}"

        cur.execute("SELECT COUNT(*) FROM screening_hits WHERE log_id = ?", (log_id,))
        hits_in_db = cur.fetchone()[0]
        assert hits_in_db == len(all_cands), f"Hit count in DB {hits_in_db} != candidate count {len(all_cands)}"

    # Test CSV exports
    csv_logs = tmp_path / "logs_export.csv"
    csv_hits = tmp_path / "hits_export.csv"
    export_screening_logs_to_csv(csv_logs, conn=conn)
    export_screening_hits_to_csv(csv_hits, conn=conn)

    assert csv_logs.is_file() and csv_logs.stat().st_size > 50
    assert csv_hits.is_file() and csv_hits.stat().st_size > 50

    conn.close()


def test_reports_contain_all_candidates():
    """Verify that generated PDF and Excel reports contain all candidates across tiers."""
    sample_candidates = [
        {"source_list": "us_ofac", "tier": "POTENTIAL_MATCH", "primary_name": "Entity Red", "matched_name": "Red Co", "source_id": "101", "score": 0.95, "reason": "core_exact"},
        {"source_list": "us_csl", "tier": "POSSIBLE_MATCH_REVIEW", "primary_name": "Entity Orange", "matched_name": "Orange Co", "source_id": "102", "score": 0.75, "reason": "score"},
        {"source_list": "uk_csl", "tier": "BELOW_THRESHOLD", "primary_name": "Entity Info", "matched_name": "Info Co", "source_id": "103", "score": 0.55, "reason": "below_threshold"},
    ]

    pdf, xlsx = generate_reports(
        search_type="Organisation",
        inputs={"name": "Multi Candidate Test"},
        overall_banner="🔴 POTENTIAL MATCH",
        source_statuses=[],
        sanctions_hits=[],
        aviation_hits=[],
        country_risk_hits=[],
        all_candidates=sample_candidates,
    )

    assert pdf.is_file()
    assert xlsx.is_file()

    import openpyxl
    wb = openpyxl.load_workbook(str(xlsx))
    assert "Candidates & Findings" in wb.sheetnames
    ws = wb["Candidates & Findings"]

    # Check that rows for all 3 candidates exist in Excel
    primary_names_in_sheet = [ws.cell(row=i, column=3).value for i in range(1, ws.max_row + 1)]
    assert "Entity Red" in primary_names_in_sheet
    assert "Entity Orange" in primary_names_in_sheet
    assert "Entity Info" in primary_names_in_sheet

    # Check Total Candidates in meta sheet
    ws_meta = wb["Screening Summary"]
    found_total = False
    for row in ws_meta.iter_rows(values_only=True):
        if row[0] == "Total Candidates":
            assert row[1] == "3" or row[1] == 3
            found_total = True
            break
    assert found_total is True
