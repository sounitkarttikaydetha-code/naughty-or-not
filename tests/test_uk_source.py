"""
Test for Item A1: UK Sanctions List (FCDO) Verification.
Confirms:
- uk_csl.csv contains post-28 Jan 2026 designations
- Header format is the official FCDO format with Report Date
- UK list is labeled 'UK Sanctions List (FCDO)'
"""

import csv
from datetime import datetime
from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from modules.common.source_manager import get_source_file_path, load_sources_registry


class TestUKSource(unittest.TestCase):
    def test_uk_sanctions_list_fcdo_post_jan_2026(self):
        path = get_source_file_path("uk_csl")
        self.assertTrue(path.is_file(), f"UK list file not found at {path}")

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            header_line = f.readline().strip()
            self.assertIn("Report Date", header_line)

            reader = csv.DictReader(f)
            post_jan_2026 = 0
            for row in reader:
                d = row.get("Date Designated", "").strip()
                if not d:
                    continue
                try:
                    dt = datetime.strptime(d, "%d/%m/%Y")
                    if dt > datetime(2026, 1, 28):
                        post_jan_2026 += 1
                except Exception:
                    pass

        self.assertGreater(post_jan_2026, 1000, f"Expected >1000 post-28 Jan 2026 designations, got {post_jan_2026}")

    def test_uk_source_label(self):
        reg = load_sources_registry()
        self.assertIn("uk_csl", reg)
        auth = reg["uk_csl"].get("authority", "")
        self.assertEqual(auth, "UK Sanctions List (FCDO)")


if __name__ == "__main__":
    unittest.main()
