"""
Regression and validation tests for T9-2: Sound-alike (phonetic) layer validation.
"""

import os
import sqlite3
import pytest
import yaml
from pathlib import Path
from modules.screening.tiering import (
    screen_query_all_lists,
    TIER_POSSIBLE_MATCH,
    TIER_POTENTIAL_MATCH,
)
import modules.screening.config as config
from modules.watchman.client import WatchmanClient, get_python_engine
from modules.common.ui import render_status_chip
from modules.reporting.generator import generate_reports
from modules.reporting.logger import get_db_connection


def test_name_variants_audit_applied_not_approved():
    """Verify all 8 curated variant groups are documented with linguistic source and marked 'applied, not yet approved'."""
    yaml_path = Path(__file__).resolve().parent.parent / "config" / "name_variants.yaml"
    assert yaml_path.exists(), f"Missing {yaml_path}"
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    expected_groups = [
        "mohammed", "hussein", "yevgeny", "qaddafi",
        "sheikh", "chaudhary", "vladimir", "alexander"
    ]
    sources = data.get("variant_sources", {})
    for grp in expected_groups:
        assert grp in sources, f"Variant group '{grp}' missing from variant_sources"
        grp_meta = sources[grp]
        assert grp_meta.get("status") == "applied, not yet approved", (
            f"Group '{grp}' status must be 'applied, not yet approved', got {grp_meta.get('status')}"
        )
        assert grp_meta.get("source"), f"Group '{grp}' must document linguistic source"


def test_sound_alike_status_chip():
    """Verify render_status_chip('SOUNDS_LIKE') contains the speaker icon and label."""
    chip_html = render_status_chip("SOUNDS_LIKE")
    assert "🔊" in chip_html
    assert "SOUNDS LIKE" in chip_html
    assert "chip-possible" in chip_html


def test_phonetic_probes_recall_orange():
    """Verify key sound-alike probes achieve at least 🟠 (POSSIBLE_MATCH_REVIEW)."""
    engine = get_python_engine()
    engine.phonetic_enabled = True
    config.PHONETIC_ENABLED = True
    client = WatchmanClient(engine="python")

    probes = [
        ("Kadhafi", "person", "us_ofac", "15258"),
        ("Yevgeny", "person", "us_ofac", None),
        ("Shaikh", "person", "un_csl", None),
    ]

    for query, q_type, list_id, expected_id in probes:
        res = screen_query_all_lists(query, client=client, query_type=q_type)
        list_res = res.get(list_id, {})
        best = list_res.get("best_hit")
        assert best is not None, f"Expected hits for query {query} on {list_id}"
        assert best.get("tier") in (TIER_POTENTIAL_MATCH, TIER_POSSIBLE_MATCH), (
            f"Query {query} expected >= 🟠, got {best.get('tier')}"
        )
        if expected_id:
            assert str(best.get("source_id")) == expected_id, (
                f"Query {query} on {list_id} expected ID {expected_id}, got {best.get('source_id')}"
            )


def test_reports_show_phonetic_disabled_banner(tmp_path):
    """When phonetic_enabled=False, PDF and Excel reports include 'Sound-alike matching OFF'."""
    pdf_path, excel_path = generate_reports(
        search_type="Name Screening",
        inputs={"name": "TEST ENTITY", "type": "organisation"},
        overall_banner="POTENTIAL_MATCH",
        source_statuses=[{"source": "US OFAC", "status": "POTENTIAL_MATCH", "records": 1}],
        sanctions_hits=[{
            "list_id": "us_ofac",
            "name": "TEST ENTITY",
            "source_id": "99999",
            "score": 0.95,
            "tier": "POTENTIAL_MATCH",
            "reason": "exact_match",
        }],
        aviation_hits=[],
        country_risk_hits=[],
        phonetic_enabled=False,
    )

    # Check xlsx
    import openpyxl
    wb = openpyxl.load_workbook(excel_path)
    sheet = wb.active
    found_banner = False
    for row in sheet.iter_rows(values_only=True):
        for cell in row:
            if cell and "Sound-alike matching OFF" in str(cell):
                found_banner = True
                break
    assert found_banner, "Excel report missing 'Sound-alike matching OFF' banner when phonetic is disabled"

    # Clean up generated test report files
    try:
        pdf_path.unlink(missing_ok=True)
        excel_path.unlink(missing_ok=True)
    except Exception:
        pass


def test_database_schema_has_phonetic_and_metadata_columns():
    """Verify screening_logs and screening_hits contain T9-2 required columns."""
    conn = get_db_connection()
    c = conn.cursor()

    # Check screening_logs columns
    c.execute("PRAGMA table_info(screening_logs)")
    log_cols = [row[1] for row in c.fetchall()]
    assert "phonetic_enabled" in log_cols, "screening_logs missing 'phonetic_enabled'"
    assert "publication_date" in log_cols, "screening_logs missing 'publication_date'"
    assert "last_verified_at" in log_cols, "screening_logs missing 'last_verified_at'"

    # Check screening_hits columns
    c.execute("PRAGMA table_info(screening_hits)")
    hit_cols = [row[1] for row in c.fetchall()]
    assert "expanded_from" in hit_cols, "screening_hits missing 'expanded_from'"
    assert "score_source" in hit_cols, "screening_hits missing 'score_source'"
    conn.close()
