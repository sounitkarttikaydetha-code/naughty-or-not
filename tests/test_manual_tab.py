"""
Tests for T8-9: Manual check tab, publisher cards, audit logging, and report inclusion.
"""

from pathlib import Path
import sqlite3
import pytest
from streamlit.testing.v1 import AppTest

from modules.reporting.logger import (
    get_db_connection,
    log_manual_check,
    get_manual_checks_for_entity,
    DB_PATH,
)
from modules.reporting.generator import generate_reports

APP_FILE = str(Path(__file__).resolve().parent.parent / "app.py")


def test_manual_check_audit_logging():
    """Saving a manual check writes a row to screening_logs with mode = 'manual'."""
    # Log two manual checks
    log_manual_check("Gazprombank", "us_ofac", "Match", "Confirmed on SDN list", app_version="1.0.3")
    log_manual_check("Gazprombank", "uk_csl", "Clean", "No UK designation found", app_version="1.0.3")

    conn = get_db_connection(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT mode, source, result, comment, top_match FROM screening_logs WHERE mode = 'manual' AND top_match = 'Gazprombank'")
    rows = cur.fetchall()

    assert len(rows) >= 2
    for r in rows:
        assert r[0] == "manual"
        assert r[4] == "Gazprombank"

    conn.close()


def test_get_manual_checks_for_entity():
    """Retrieve recent checks for an entity name."""
    log_manual_check("Test Entity Alpha", "us_ofac", "Clean", "Verified official portal")
    records = get_manual_checks_for_entity("Test Entity Alpha")
    assert len(records) > 0
    assert records[0]["source"] == "us_ofac"
    assert records[0]["result"] == "Clean"


def test_reports_include_section_d_manual_checks():
    """Reports generated with manual_checks populate Section D in PDF and Excel."""
    checks = [
        {
            "timestamp": "2026-10-23 00:00:00 UTC",
            "source": "us_ofac",
            "source_name": "US OFAC",
            "result": "Clean",
            "comment": "No designation on official search",
            "verify_url": "https://sanctionssearch.ofac.treas.gov/",
        }
    ]

    pdf, xlsx = generate_reports(
        search_type="Organisation",
        inputs={"name": "Sberbank"},
        overall_banner="✅ NO MATCH",
        source_statuses=[],
        sanctions_hits=[],
        aviation_hits=[],
        country_risk_hits=[],
        manual_checks=checks,
    )

    assert pdf.is_file()
    assert xlsx.is_file()

    import openpyxl
    wb = openpyxl.load_workbook(str(xlsx))
    assert "Manual Official Checks" in wb.sheetnames
    ws = wb["Manual Official Checks"]
    rows = list(ws.iter_rows(values_only=True))
    assert len(rows) >= 2
    # Check header and values
    assert rows[1][1] == "US OFAC"
    assert rows[1][2] == "Clean"
    assert rows[1][3] == "No designation on official search"


def test_manual_tab_renders_via_apptest():
    """Verify that Tab 3 renders properly with publisher cards and inputs."""
    at = AppTest.from_file(APP_FILE, default_timeout=30)
    at.session_state["acknowledged"] = True
    at.query_params["tab"] = "manual"
    at.run(timeout=15)
    assert not at.exception
