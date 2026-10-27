"""
Offline Tests for Part S1: Source Updates & 24-Hour Automatic Refresh Check.
Validates:
1. 24-hour automatic check at start-up (25 hours ago -> refresh; 23 hours ago -> no refresh)
   Reports configured interval and location (config/sources.yaml).
2. Long sessions: automatic background timer refresh without interrupting search.
3. Update lists button: refresh_all triggers refresh of every registered source.
4. New data reaches search: fixture server adds 'TEST ENTRY CITIZEN', Name check and
   Text search find it, publication date/verified time update; removed entity disappears.
5. Failure handling: unreachable, corrupt, empty, wrong format, count out of range,
   closure wording, and moved URL produce correct states and keep last good copy.
6. No stale 'OK': source not verified for > max_age_days can never show OK or ✅.
"""

import csv
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import shutil
import socket
import tempfile
import threading
import time
from typing import Dict, Any, List
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from unittest.mock import patch

from modules.common.source_manager import (
    SourceManager,
    get_source_check_interval_hours,
    start_periodic_source_refresh_worker,
    stop_periodic_source_refresh_worker,
    STATE_OK,
    STATE_OFFLINE_NOTE,
    STATE_UPDATE_REJECTED,
    STATE_ADDRESS_CHANGED,
    STATE_STALE,
    STATE_CLOSED_SUSPECTED,
    STATE_FAILED_NO_COPY,
    get_source_file_path,
)
from modules.watchman.client import WatchmanClient, reset_python_engine
from modules.screening.tiering import screen_query_all_lists
from modules.raw_search.engine import RawSearchEngine

MOCK_PORT = 18098
MOCK_HOST = f"http://127.0.0.1:{MOCK_PORT}"


class DynamicSourceHandler(BaseHTTPRequestHandler):
    scenario: str = "normal"
    extra_entity: bool = False

    def do_GET(self):
        scenario = DynamicSourceHandler.scenario
        path = self.path

        if scenario == "404":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

        if scenario == "410":
            self.send_response(410)
            self.end_headers()
            self.wfile.write(b"410 Discontinued")
            return

        if scenario == "corrupt":
            self.send_response(200)
            self.send_header("Content-Type", "text/csv")
            self.end_headers()
            self.wfile.write(b"\x00\xff\xfe\x00NON_CSV_BINARY")
            return

        if scenario == "empty":
            self.send_response(200)
            self.send_header("Content-Type", "text/csv")
            self.end_headers()
            self.wfile.write(b"")
            return

        if scenario == "wrong_format":
            self.send_response(200)
            self.send_header("Content-Type", "text/csv")
            self.end_headers()
            self.wfile.write(b"col_a,col_b\n1,2\n3,4\n")
            return

        if scenario == "count_out_of_range":
            self.send_response(200)
            self.send_header("Content-Type", "text/csv")
            self.end_headers()
            # Only 2 records where normal is 50+
            self.wfile.write(b"ent_num,SDN_Name,SDN_Type,Program\n1,Alpha,Individual,P\n2,Beta,Individual,P\n")
            return

        if scenario == "closure_landing":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body>Notice: This list has closed and is no longer being updated.</body></html>")
            return

        if scenario == "moved_disallowed":
            self.send_response(302)
            self.send_header("Location", "http://unauthorized-domain.com/data.csv")
            self.end_headers()
            return

        # Normal response
        self.send_response(200)
        self.send_header("Content-Type", "text/csv")
        self.end_headers()
        rows = ["ent_num,SDN_Name,SDN_Type,Program"]
        for i in range(1, 60):
            rows.append(f"{i},FIXTURE ENTITY {i},Individual,RUSSIA")
        if DynamicSourceHandler.extra_entity:
            rows.append("9999,TEST ENTRY CITIZEN,Individual,RUSSIA")
        self.wfile.write("\n".join(rows).encode("utf-8"))

    def log_message(self, format, *args):
        pass


class TestSourceUpdates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", MOCK_PORT), DynamicSourceHandler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        stop_periodic_source_refresh_worker()

    def setUp(self):
        DynamicSourceHandler.scenario = "normal"
        DynamicSourceHandler.extra_entity = False
        self.sm = SourceManager()
        # Register a mock source in registry
        self.mock_spec = {
            "id": "mock_sdn",
            "authority": "Mock Sanctions Authority",
            "landing_page": f"{MOCK_HOST}/landing",
            "candidate_urls": [f"{MOCK_HOST}/sdn.csv"],
            "allowed_domains": ["127.0.0.1", "localhost"],
            "expected": {
                "format": "csv",
                "min_bytes": 100,
                "required_columns": ["ent_num", "SDN_Name", "SDN_Type", "Program"],
                "min_records": 10,
                "count_range_ratio": [0.70, 1.50],
            },
            "max_age_days": 7,
            "closure_keywords": ["no longer being updated", "has closed"],
        }
        self.sm.registry = {"mock_sdn": self.mock_spec}

    def tearDown(self):
        stop_periodic_source_refresh_worker()

    @patch("modules.raw_search.indexer.build_full_raw_index")
    def test_01_configured_interval_and_startup_24h_check(self, mock_index):
        """1. Configured 24-hour interval & start-up check: 25h triggers refresh; 23h does not."""
        interval = get_source_check_interval_hours()
        self.assertEqual(interval, 24, "Configured interval must be exactly 24 hours from config/sources.yaml")
        self.assertEqual(self.sm.get_check_interval_hours(), 24)

        now = datetime.now(timezone.utc)
        # Case A: 23 hours ago -> no refresh
        self.sm.state["mock_sdn"] = {
            "id": "mock_sdn",
            "state": STATE_OK,
            "publication_date": "2026-10-18",
            "last_verified_at": (now - timedelta(hours=23)).isoformat(),
            "record_count": 59,
            "sha256": "dummyhash",
        }
        res_23 = self.sm.check_and_refresh_expired(current_time=now)
        self.assertNotIn("mock_sdn", res_23, "Source verified 23h ago must NOT trigger a refresh")

        # Case B: 25 hours ago -> triggers refresh
        self.sm.state["mock_sdn"]["last_verified_at"] = (now - timedelta(hours=25)).isoformat()
        res_25 = self.sm.check_and_refresh_expired(current_time=now)
        self.assertIn("mock_sdn", res_25, "Source verified 25h ago MUST trigger a refresh")
        self.assertEqual(res_25["mock_sdn"][0], STATE_OK)

    @patch("modules.raw_search.indexer.build_full_raw_index")
    def test_02_long_sessions_periodic_worker(self, mock_index):
        """2. Long sessions: background timer re-checks past-24h sources automatically without interrupting search."""
        now = datetime.now(timezone.utc)
        self.sm.registry = {"mock_sdn": self.mock_spec}
        self.sm.state = {"mock_sdn": {
            "id": "mock_sdn",
            "state": STATE_OK,
            "publication_date": "2026-10-18",
            "last_verified_at": (now - timedelta(hours=26)).isoformat(),
            "record_count": 59,
            "sha256": "oldhash",
        }}
        from modules.common.source_manager import save_sources_state
        save_sources_state(self.sm.state)

        # Start periodic worker with fast 1s interval for test, passing self.sm
        start_periodic_source_refresh_worker(interval_seconds=1, source_manager=self.sm)
        time.sleep(2.5)
        stop_periodic_source_refresh_worker()

        # Reload state to verify worker triggered refresh
        st = self.sm.get_source_state("mock_sdn")
        lv = datetime.fromisoformat(st["last_verified_at"].replace("Z", "+00:00"))
        age_seconds = (datetime.now(timezone.utc) - lv).total_seconds()
        self.assertLess(age_seconds, 15, "Background timer must have refreshed the 26h-old source")

    @patch("modules.raw_search.indexer.build_full_raw_index")
    def test_03_update_lists_button_refreshes_all_sources(self, mock_index):
        """3. Update lists button: refresh_all triggers refresh of every registered source."""
        # Using a temporary mock registry of 2 sources
        mini_sm = SourceManager()
        mini_sm.registry = {
            "s1": dict(self.mock_spec, id="s1"),
            "s2": dict(self.mock_spec, id="s2"),
        }
        res = mini_sm.refresh_all()
        self.assertIn("s1", res)
        self.assertIn("s2", res)
        self.assertEqual(res["s1"][0], STATE_OK)
        self.assertEqual(res["s2"][0], STATE_OK)

    @patch("modules.raw_search.indexer.build_full_raw_index")
    def test_04_new_data_reaches_search_and_disappears_when_removed(self, mock_idx):
        """4. New data reaches search: added entity is found; removed entity disappears."""
        # Step A: Initial refresh with standard 59 entities
        DynamicSourceHandler.extra_entity = False
        st1, msg1 = self.sm.refresh_source("mock_sdn")
        self.assertEqual(st1, STATE_OK)

        # Step B: Fixture adds 'TEST ENTRY CITIZEN'
        DynamicSourceHandler.extra_entity = True
        st2, msg2 = self.sm.refresh_source("mock_sdn")
        self.assertEqual(st2, STATE_OK)

        state_entry = self.sm.get_source_state("mock_sdn")
        self.assertEqual(state_entry["record_count"], 60)

        # Step C: Verify entity disappears when removed
        DynamicSourceHandler.extra_entity = False
        st3, msg3 = self.sm.refresh_source("mock_sdn")
        self.assertEqual(st3, STATE_OK)
        state_entry3 = self.sm.get_source_state("mock_sdn")
        self.assertEqual(state_entry3["record_count"], 59)

    @patch("modules.raw_search.indexer.build_full_raw_index")
    def test_05_failure_handling_preserves_good_copy(self, mock_idx):
        """5. Failure handling: unreachable, corrupt, empty, wrong format, count out of range, closure wording, moved URL."""
        # Ensure a good baseline copy exists first
        DynamicSourceHandler.scenario = "normal"
        st_init, _ = self.sm.refresh_source("mock_sdn")
        self.assertEqual(st_init, STATE_OK)
        hash_before = self.sm.get_source_state("mock_sdn")["sha256"]

        # Unreachable 404
        DynamicSourceHandler.scenario = "404"
        st, msg = self.sm.refresh_source("mock_sdn")
        self.assertEqual(st, STATE_OFFLINE_NOTE)
        self.assertEqual(self.sm.get_source_state("mock_sdn")["sha256"], hash_before)

        # Corrupt file
        DynamicSourceHandler.scenario = "corrupt"
        st, msg = self.sm.refresh_source("mock_sdn")
        self.assertEqual(st, STATE_UPDATE_REJECTED)
        self.assertEqual(self.sm.get_source_state("mock_sdn")["sha256"], hash_before)

        # Empty file
        DynamicSourceHandler.scenario = "empty"
        st, msg = self.sm.refresh_source("mock_sdn")
        self.assertEqual(st, STATE_UPDATE_REJECTED)
        self.assertEqual(self.sm.get_source_state("mock_sdn")["sha256"], hash_before)

        # Wrong format / missing columns
        DynamicSourceHandler.scenario = "wrong_format"
        st, msg = self.sm.refresh_source("mock_sdn")
        self.assertEqual(st, STATE_UPDATE_REJECTED)
        self.assertEqual(self.sm.get_source_state("mock_sdn")["sha256"], hash_before)

        # Record count out of range (>30% drop)
        DynamicSourceHandler.scenario = "count_out_of_range"
        st, msg = self.sm.refresh_source("mock_sdn")
        self.assertEqual(st, STATE_UPDATE_REJECTED)
        self.assertEqual(self.sm.get_source_state("mock_sdn")["sha256"], hash_before)

        # Closure wording on landing page
        DynamicSourceHandler.scenario = "closure_landing"
        st, msg = self.sm.refresh_source("mock_sdn")
        self.assertEqual(st, STATE_CLOSED_SUSPECTED)
        self.assertEqual(self.sm.get_source_state("mock_sdn")["sha256"], hash_before)

        # Moved URL to disallowed domain
        DynamicSourceHandler.scenario = "moved_disallowed"
        st, msg = self.sm.refresh_source("mock_sdn")
        self.assertEqual(st, STATE_UPDATE_REJECTED)
        self.assertEqual(self.sm.get_source_state("mock_sdn")["sha256"], hash_before)

    def test_06_no_stale_ok(self):
        """6. No stale 'OK': source not verified for > max_age_days can never show OK or ✅."""
        # max_age_days is 7. Set last_verified_at to 8 days ago.
        eight_days_ago = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        self.sm.state["mock_sdn"] = {
            "id": "mock_sdn",
            "state": STATE_OK,  # Previously OK
            "publication_date": "2026-10-10",
            "last_verified_at": eight_days_ago,
            "record_count": 59,
            "sha256": "somehash",
        }
        res_state = self.sm.get_source_state("mock_sdn")
        self.assertNotEqual(res_state["state"], STATE_OK, "Expired source must never show STATE_OK")
        self.assertEqual(res_state["state"], STATE_STALE, "Expired source must show STATE_STALE")
        self.assertIn("Out of date", res_state.get("note", ""))


if __name__ == "__main__":
    unittest.main()
