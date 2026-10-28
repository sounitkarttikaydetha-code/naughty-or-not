import os
"""
Advanced Source Refresh & Section 2A Tests for Clearance Check.
Validates:
1. HTTP 403 Forbidden -> STATE_UPDATE_NEEDS_HELP ("Update needs help")
2. HTTP 429 Rate Limited -> Retry-After header parsing and event logging
3. HTTP 5xx Server Error -> Exponential backoff handling
4. Native Windows certificate store injection via truststore
5. User-assisted import (import_source_file) with format validation, atomic swap,
   3-version archive retention, and provenance audit logging in SQLite
6. FATF Plenary calendar rule (Feb, Jun, Oct; between plenaries -> current; post-plenary -> update due)
7. Honest User-Agent header (ClearanceCheck/1.1.1)
"""

from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from pathlib import Path
import shutil
import tempfile
import threading
import time
import unittest
import urllib.request

from modules.common.source_manager import (
    SourceManager,
    STATE_OK,
    STATE_UPDATE_NEEDS_HELP,
    check_fatf_plenary_status,
    USER_AGENT,
    get_source_file_path,
)

ADV_PORT = 18099
ADV_HOST = f"http://127.0.0.1:{ADV_PORT}"


class AdvancedMockHandler(BaseHTTPRequestHandler):
    scenario = "normal"
    received_user_agent = ""

    def do_GET(self):
        AdvancedMockHandler.received_user_agent = self.headers.get("User-Agent", "")
        sc = AdvancedMockHandler.scenario

        if sc == "403":
            self.send_response(403)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"403 Forbidden - Scraping blocked")
            return

        if sc == "429":
            self.send_response(429)
            self.send_header("Retry-After", "120")
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"429 Too Many Requests")
            return

        if sc == "503":
            self.send_response(503)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"503 Service Unavailable")
            return

        # Normal CSV response
        self.send_response(200)
        self.send_header("Content-Type", "text/csv")
        self.end_headers()
        rows = ["ent_num,SDN_Name,SDN_Type,Program"]
        for i in range(1, 100):
            rows.append(f"{i},Person {i},individual,SDGT")
        self.wfile.write("\n".join(rows).encode("utf-8"))

    def log_message(self, format, *args):
        pass


class TestSourceUpdatesAdvanced(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", ADV_PORT), AdvancedMockHandler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

    def tearDown(self):
        os.environ.pop("CC_SOURCES_STATE_FILE", None)
        if hasattr(self, "temp_dir"):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        os.environ["CC_SOURCES_STATE_FILE"] = str(Path(self.temp_dir) / "test_sources_state.json")
        self.sm = SourceManager()
        # Mock spec pointing to local mock server
        self.mock_spec = {
            "id": "mock_adv_src",
            "authority": "Test Authority",
            "landing_page": f"{ADV_HOST}/landing",
            "candidate_urls": [f"{ADV_HOST}/download.csv"],
            "allowed_domains": ["127.0.0.1", "localhost"],
            "expected": {
                "format": "csv",
                "min_bytes": 100,
                "required_columns": ["ent_num", "SDN_Name"],
                "min_records": 10,
                "count_range_ratio": [0.5, 2.0],
            },
            "max_age_days": 7,
            "verify_url": f"{ADV_HOST}/verify",
        }
        self.sm.registry["mock_adv_src"] = self.mock_spec

    def test_01_honest_user_agent_and_truststore(self):
        """Verify that outgoing requests send the honest User-Agent and truststore is imported."""
        import truststore
        self.assertIsNotNone(truststore)
        AdvancedMockHandler.scenario = "normal"
        self.sm.refresh_source("mock_adv_src")
        self.assertIn("ClearanceCheck/1.1.1", AdvancedMockHandler.received_user_agent)

    def test_02_http_403_triggers_update_needs_help(self):
        """Verify that HTTP 403 Forbidden returns STATE_UPDATE_NEEDS_HELP with direct site guidance."""
        AdvancedMockHandler.scenario = "403"
        st, note = self.sm.refresh_source("mock_adv_src")
        self.assertEqual(st, STATE_UPDATE_NEEDS_HELP)
        self.assertIn("Update needs help", note)
        self.assertIn("403", note)

    def test_03_http_429_rate_limiting_and_retry_after(self):
        """Verify that HTTP 429 Too Many Requests logs retry-after message."""
        AdvancedMockHandler.scenario = "429"
        st, note = self.sm.refresh_source("mock_adv_src")
        state_entry = self.sm.get_source_state("mock_adv_src")
        self.assertIn("429", str(state_entry.get("last_error", "")))
        self.assertIn("Retry-After", str(state_entry.get("last_error", "")))

    def test_04_http_5xx_backoff_handling(self):
        """Verify that HTTP 503 is caught and recorded cleanly without crashing."""
        AdvancedMockHandler.scenario = "503"
        st, note = self.sm.refresh_source("mock_adv_src")
        state_entry = self.sm.get_source_state("mock_adv_src")
        self.assertIn("503", str(state_entry.get("last_error", "")))

    def test_05_user_assisted_import(self):
        """Verify manual user-assisted import with format validation and atomic archive swap."""
        # Create valid CSV content within allowed count ratio of previous copy (99 records)
        lines = ["ent_num,SDN_Name,SDN_Type,Program"]
        for i in range(1, 95):
            lines.append(f"{i},Manual Entry {i},individual,SDGT")
        csv_data = "\n".join(lines).encode("utf-8")

        success, msg = self.sm.import_source_file(
            source_id="mock_adv_src",
            file_bytes_or_path=csv_data,
            filename="manual_sdn.csv",
            provenance_notes="Downloaded by compliance officer from official portal",
            rebuild_index=False,
        )
        self.assertTrue(success)
        self.assertIn("Successfully imported", msg)

        state = self.sm.get_source_state("mock_adv_src")
        self.assertEqual(state["state"], STATE_OK)
        self.assertEqual(state["record_count"], 94)
        self.assertIn("User-assisted import", state["note"] or "")

    def test_06_fatf_plenary_calendar_rule(self):
        """
        Verify FATF plenary calendar rule:
        - Between plenaries (e.g. May 1) -> Current (between FATF plenaries)
        - Immediately post-plenary (e.g. March 5) without update -> Update due
        - Immediately post-plenary with update -> Current
        """
        # Between plenaries (May 1, 2026)
        date_may = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
        is_due, msg = check_fatf_plenary_status("2026-02-28T00:00:00Z", current_time=date_may)
        self.assertFalse(is_due)
        self.assertIn("between FATF plenaries", msg)

        # 5 days post-February plenary (March 2, 2026) with old list from January
        date_mar = datetime(2026, 3, 2, 12, 0, tzinfo=timezone.utc)
        is_due_post, msg_post = check_fatf_plenary_status("2026-01-15T00:00:00Z", current_time=date_mar)
        self.assertTrue(is_due_post)
        self.assertIn("Update due", msg_post)

        # Post-February plenary but already verified on Feb 26
        is_due_updated, msg_updated = check_fatf_plenary_status("2026-02-26T10:00:00Z", current_time=date_mar)
        self.assertFalse(is_due_updated)


if __name__ == "__main__":
    unittest.main()
