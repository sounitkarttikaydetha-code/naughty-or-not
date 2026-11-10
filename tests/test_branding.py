"""
Tests for Part C: Product Renaming & Branding.
Verifies Clearance Check branding, exact main title "Sanction checK",
and codename/signature isolation.
"""

from pathlib import Path
import unittest

from modules.common.branding import APP_NAME, APP_SUBTITLE, MAIN_TITLE, SHORT_NAME, VERSION_LABEL, CODENAME

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestBranding(unittest.TestCase):
    def test_01_branding_constants(self):
        """Verify branding config loads correct values."""
        self.assertEqual(APP_NAME, "Clearance Check")
        self.assertEqual(MAIN_TITLE, "Sanction checK", "Main title must strictly have capital K")
        self.assertEqual(SHORT_NAME, "ClearanceCheck")
        self.assertEqual(VERSION_LABEL, "v1.2.1")
        self.assertEqual(CODENAME, "Naughty or not")

    def test_02_app_title_and_main_screen(self):
        """app.py sets title to 'Sanction checK' and branding in page config."""
        app_py = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('st.title(MAIN_TITLE)', app_py)
        self.assertIn('page_title=f"{APP_NAME} — {MAIN_TITLE}"', app_py)
        self.assertIn('**Internal codename:** Naughty or not', app_py)

    def test_03_desktop_launcher_branding(self):
        """desktop_launcher.py uses APP_NAME and MAIN_TITLE."""
        dl = (PROJECT_ROOT / "desktop_launcher.py").read_text(encoding="utf-8")
        self.assertIn('APP_TITLE = f"{APP_NAME} — {MAIN_TITLE} — {VERSION_LABEL}"', dl)

    def test_04_reports_branding(self):
        """Reporting generator uses Clearance Check — Sanction checK."""
        gen = (PROJECT_ROOT / "modules" / "reporting" / "generator.py").read_text(encoding="utf-8")
        self.assertIn('<b>{APP_NAME} — {MAIN_TITLE} Screening Report</b>', gen)
        self.assertIn('ws_meta["A1"] = f"{APP_NAME} — {MAIN_TITLE} Screening Report"', gen)


if __name__ == "__main__":
    unittest.main()
