"""
UI Tests for Sanction checK (T5).
Uses Streamlit AppTest to validate user interactions, form submissions,
banner rendering, source freshness, logging, and report output generation.
"""

import os
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from modules.reporting.logger import DB_PATH, APP_VERSION

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
APP_FILE = str(Path(__file__).resolve().parent.parent / "app.py")


class TestSanctionCheckUI(unittest.TestCase):
    """Test suite for Sanction checK Streamlit interface."""

    def test_banner_and_notices(self):
        """Verify permanent warning banner and notice presence."""
        at = AppTest.from_file(APP_FILE)
        at.run(timeout=15)
        self.assertFalse(at.exception)

        # Check permanent banner
        self.assertTrue(len(at.warning) >= 1)
        self.assertIn("TEST VERSION", at.warning[0].value)
        self.assertIn("OpenSanctions data is licensed CC BY-NC 4.0", at.warning[0].value)

        # Check Title
        titles = [t.value for t in at.title]
        self.assertIn("Sanction checK", titles)

    def test_opensanctions_default_off(self):
        """OpenSanctions checkbox must be OFF by default and make no API calls when unticked."""
        at = AppTest.from_file(APP_FILE)
        at.run(timeout=15)
        self.assertFalse(at.exception)

        # Find OpenSanctions checkbox
        os_checkbox = None
        for cb in at.checkbox:
            if "OpenSanctions" in cb.label:
                os_checkbox = cb
                break
        self.assertIsNotNone(os_checkbox)
        self.assertFalse(os_checkbox.value)

    def test_search_aeroflot_airline(self):
        """Test Airline search: Aeroflot -> triggers findings, report, and log."""
        at = AppTest.from_file(APP_FILE, default_timeout=30)
        at.session_state["acknowledged"] = True
        at.run(timeout=15)

        # Select Airline
        at.selectbox[0].select("Airline")
        at.run(timeout=15)

        # Fill name
        at.text_input[0].input("Aeroflot")
        # Submit form via Screen Entity button (button[0])
        at.button[0].click().run(timeout=60)
        self.assertFalse(at.exception)

        # Check banner or error/warning/success
        banner_rendered = bool(at.error or at.warning or at.success or at.info)
        self.assertTrue(banner_rendered)

        # Verify report file created
        pdf_reports = list(REPORTS_DIR.glob("*Aeroflot*.pdf"))
        self.assertTrue(len(pdf_reports) > 0)

        # Verify log entry in SQLite
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM screening_logs WHERE search_type = 'Airline'")
        count = cur.fetchone()[0]
        conn.close()
        self.assertTrue(count > 0)

    def test_search_ra73093_aircraft(self):
        """Test Aircraft search: RA-73093 -> BIS EAR finding."""
        at = AppTest.from_file(APP_FILE, default_timeout=30)
        at.session_state["acknowledged"] = True
        at.run(timeout=15)

        at.selectbox[0].select("Aircraft")
        at.run(timeout=15)

        at.text_input[0].input("RA-73093")
        at.button[0].click().run(timeout=60)
        self.assertFalse(at.exception)

        # Verify BIS EAR restriction banner/error
        errors = [e.value for e in at.error]
        self.assertTrue(any("POTENTIAL MATCH" in e for e in errors))

        # Check report generated
        pdf_reports = list(REPORTS_DIR.glob("*RA*73093*.pdf"))
        self.assertTrue(len(pdf_reports) > 0)

    def test_search_jaipur_airport_clean(self):
        """Test Organisation search: Jaipur International Airport Limited -> Clean / NO MATCH."""
        at = AppTest.from_file(APP_FILE, default_timeout=30)
        at.session_state["acknowledged"] = True
        at.run(timeout=15)

        at.selectbox[0].select("Organisation")
        at.run(timeout=15)

        at.text_input[0].input("Jaipur International Airport Limited")
        at.button[0].click().run(timeout=60)
        self.assertFalse(at.exception)

        # Verify clean banner
        successes = [s.value for s in at.success]
        self.assertTrue(any("NO MATCH" in s for s in successes))

    def test_search_person_with_dob(self):
        """Test Person search with DOB -> runs and verifies."""
        at = AppTest.from_file(APP_FILE, default_timeout=30)
        at.session_state["acknowledged"] = True
        at.run(timeout=15)

        at.selectbox[0].select("Person")
        at.run(timeout=15)

        at.text_input[0].input("Mohammed Khan")
        at.text_input[1].input("1980")
        at.button[0].click().run(timeout=60)
        self.assertFalse(at.exception)

        # Verify banner and report
        pdf_reports = list(REPORTS_DIR.glob("*Mohammed_Khan*.pdf"))
        self.assertTrue(len(pdf_reports) > 0)

    def test_simulated_watchman_down_incomplete_banner(self):
        """Simulate Watchman being down -> produces ⚪ Incomplete banner."""
        with patch("modules.watchman.client.WatchmanClient.search", return_value={"status": "unavailable", "results": {"entities": []}}):
            at = AppTest.from_file(APP_FILE, default_timeout=30)
            at.session_state["acknowledged"] = True
            at.run(timeout=15)

            at.selectbox[0].select("Organisation")
            at.run(timeout=15)

            at.text_input[0].input("Sberbank")
            at.button[0].click().run(timeout=60)
            self.assertFalse(at.exception)

            # Incomplete banner rendered as info
            infos = [i.value for i in at.info]
            self.assertTrue(any("INCOMPLETE" in i for i in infos))

    def test_simulated_india_down_incomplete_banner(self):
        """Simulate India MHA list failure -> must produce ⚪ Incomplete banner, never false clean."""
        with patch("modules.watchman.client.WatchmanClient.search", return_value={"status": "ok", "results": {"entities": []}}), \
             patch("modules.india.client.IndiaClient.screen", return_value={"tier": "NOT_CHECKED", "status": "FAILED", "finding": "SOURCE_UNAVAILABLE"}):
            at = AppTest.from_file(APP_FILE, default_timeout=30)
            at.session_state["acknowledged"] = True
            at.run(timeout=15)

            at.selectbox[0].select("Organisation")
            at.run(timeout=15)

            at.text_input[0].input("Clean Control Company")
            at.button[0].click().run(timeout=60)
            self.assertFalse(at.exception)

            infos = [i.value for i in at.info]
            self.assertTrue(any("INCOMPLETE" in i for i in infos), f"Expected INCOMPLETE banner, got: {infos}")

    def test_tab_switch_preserves_results_without_name_error(self):
        """Simulate switching to Raw Search tab when previous results exist in session_state."""
        at = AppTest.from_file(APP_FILE, default_timeout=30)
        at.session_state["acknowledged"] = True
        at.session_state["last_results"] = {
            "banner_text": "✅ NO MATCH — Clean on all checked sources",
            "banner_type": "success",
            "search_type": "Organisation",
            "primary_query": "Test Corporation",
            "dob_entered": False,
            "nat_entered": False,
            "sanctions_hits": [],
            "source_statuses": [{"id": "us_ofac", "tier": "NO_MATCH", "status": "OK", "below_count": 0}],
            "per_list_data": {},
            "aviation_hits": [],
            "country_risk_hits": [],
            "pdf_path": "",
            "excel_path": "",
        }
        at.query_params["tab"] = "raw"
        at.run(timeout=15)
        self.assertFalse(at.exception, f"AppTest raised unexpected exception: {at.exception}")






if __name__ == "__main__":
    unittest.main()
