"""Test for %LOCALAPPDATA% path fallback when frozen (Finding A-10)."""

import sys
import unittest
from unittest.mock import patch
from pathlib import Path

from modules.reporting.logger import _get_base_data_dir
from modules.reporting.generator import _get_reports_dir


class TestLocalAppDataFallback(unittest.TestCase):
    def test_frozen_fallback_to_localappdata(self):
        """When sys.frozen is True, base dirs should fall back to LOCALAPPDATA."""
        with patch.object(sys, "frozen", True, create=True), \
             patch.dict("os.environ", {"LOCALAPPDATA": r"C:\Users\testuser\AppData\Local"}):
            base_dir = _get_base_data_dir()
            reports_dir = _get_reports_dir()
            self.assertEqual(str(base_dir), r"C:\Users\testuser\AppData\Local\NaughtyOrNot")
            self.assertEqual(str(reports_dir), r"C:\Users\testuser\AppData\Local\NaughtyOrNot\reports")


if __name__ == "__main__":
    unittest.main()
