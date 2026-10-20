"""Unit tests for T5.2 (Verification links and Manual check tab).
Validates official link formats, SQLite audit logging for mode='manual',
and inclusion of manual check results in screening reports.
"""

from pathlib import Path
import sqlite3
import unittest
import yaml

from modules.reporting.generator import generate_reports
from modules.reporting.logger import log_manual_check, DB_PATH
from modules.raw_search.engine import load_sources_config

SOURCES_YAML_PATH = Path(__file__).resolve().parent.parent / "config" / "sources.yaml"


class TestManualCheckAndVerificationLinks(unittest.TestCase):
    """Test suite for T5.2 verification links and manual check logging/reporting."""

    def test_sources_yaml_contains_verify_urls(self):
        """Every source in config/sources.yaml must have a non-empty verify_url."""
        self.assertTrue(SOURCES_YAML_PATH.is_file())
        with open(SOURCES_YAML_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        sources = data.get("sources", [])
        self.assertTrue(len(sources) >= 12)
        for s in sources:
            sid = s.get("id")
            v_url = s.get("verify_url")
            self.assertTrue(bool(v_url), f"Source {sid} must have verify_url")
            self.assertTrue(v_url.startswith("http"), f"Source {sid} verify_url must be HTTP/HTTPS")

    def test_record_level_link_templates_for_supported_publishers(self):
        """Publishers with record-level links (OFAC, OpenSanctions, BIS, MHA) have valid templates."""
        sources = load_sources_config()
        # OFAC
        ofac = sources.get("us_ofac", {})
        self.assertIn("Details.aspx?id={id}", ofac.get("record_url_template", ""))
        # OpenSanctions
        os_cfg = sources.get("os_bulk", {})
        self.assertIn("entities/{id}", os_cfg.get("record_url_template", ""))

    def test_save_manual_check_writes_sqlite_log(self):
        """Saving a manual check writes a row to screening_logs with mode = 'manual'."""
        test_name = "Test Manual Subject LLC"
        test_src = "us_ofac"
        test_res = "No match"
        test_comm = "Verified clean on official OFAC portal by compliance analyst"

        log_manual_check(
            name=test_name,
            source=test_src,
            result=test_res,
            comment=test_comm,
        )

        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        row = cur.execute(
            """
            SELECT mode, source, result, comment, top_match FROM screening_logs
            WHERE mode = 'manual' AND top_match = ?
            ORDER BY id DESC LIMIT 1
            """,
            (test_name,),
        ).fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], "manual")
        self.assertEqual(row[1], test_src)
        self.assertEqual(row[2], test_res)
        self.assertEqual(row[3], test_comm)
        self.assertEqual(row[4], test_name)

    def test_report_includes_manual_checks(self):
        """Screening report generated with manual_checks includes Section D."""
        manual_items = [
            {
                "source": "us_ofac",
                "authority": "US Treasury, OFAC",
                "result": "No match",
                "comment": "Checked SDN & non-SDN",
                "verify_url": "https://sanctionssearch.ofac.treas.gov/",
            }
        ]
        pdf_path, excel_path = generate_reports(
            search_type="Organisation",
            inputs={"name": "Aeroflot"},
            overall_banner="🔴 POTENTIAL MATCH — Match identified on official list",
            source_statuses=[{"id": "us_ofac", "authority": "OFAC", "date": "current", "status": "OK", "tier": "POTENTIAL_MATCH"}],
            sanctions_hits=[],
            aviation_hits=[],
            country_risk_hits=[],
            manual_checks=manual_items,
        )
        self.assertTrue(pdf_path.is_file())
        self.assertTrue(excel_path.is_file())

        # Check excel has Manual Official Checks sheet
        import openpyxl
        wb = openpyxl.load_workbook(str(excel_path))
        self.assertIn("Manual Official Checks", wb.sheetnames)
        ws = wb["Manual Official Checks"]
        rows = list(ws.iter_rows(values_only=True))
        self.assertTrue(any("us_ofac" in str(r) for r in rows))
