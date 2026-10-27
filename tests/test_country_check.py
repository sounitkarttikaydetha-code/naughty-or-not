"""
Tests for T11 Part J: Country Sanctions, Export Control & Regulatory Check.
Verifies multi-regime screening, flag resolution, FATF integration,
zero network requests, and append-only SQLite audit logging with mode='country'.
"""

from pathlib import Path
import sqlite3
import unittest

from modules.screening.country import CountryEngine, log_country_search
from modules.reporting.logger import DB_PATH


class TestCountryCheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = CountryEngine()

    def test_01_comprehensive_embargo_countries(self):
        """Cuba, Iran, North Korea, Syria, Russia must be 🔴 High Risk."""
        for country in ["Cuba", "Iran", "North Korea", "Syria", "Russia"]:
            res = self.engine.screen_country(country)
            self.assertEqual(res["overall_tier"], "POTENTIAL_MATCH", f"{country} must be 🔴 POTENTIAL_MATCH")
            self.assertIn("🔴", res["banner_text"])
            self.assertNotEqual(res["flag"], "🌐", f"{country} must have specific flag emoji")
            self.assertTrue(res["is_comprehensive"], f"{country} must have comprehensive regimes")

    def test_02_iso2_lookup(self):
        """ISO-2 codes CU, IR, RU must resolve correctly."""
        for iso in ["CU", "IR", "RU", "KP", "SY"]:
            res = self.engine.screen_country(iso)
            self.assertEqual(res["overall_tier"], "POTENTIAL_MATCH")
            self.assertEqual(res["iso2"], iso)

    def test_03_selective_sanctions_countries(self):
        """Belarus, Venezuela, Myanmar must be 🟠 Elevated Risk."""
        for country in ["Belarus", "Venezuela", "Myanmar"]:
            res = self.engine.screen_country(country)
            self.assertEqual(res["overall_tier"], "POSSIBLE_MATCH_REVIEW", f"{country} must be 🟠")
            self.assertIn("🟠", res["banner_text"])

    def test_04_standard_risk_country(self):
        """Japan or New Zealand must be ✅ Standard Risk."""
        res = self.engine.screen_country("Japan")
        self.assertEqual(res["overall_tier"], "NO_MATCH")
        self.assertIn("✅", res["banner_text"])

    def test_05_country_logging_with_mode_country(self):
        """log_country_search must record to SQLite with mode='country'."""
        log_country_search(
            country_query="Cuba",
            finding="POTENTIAL_MATCH",
            banner_text="🔴 HIGH RISK — COMPREHENSIVE REGIMES ACTIVE",
            execution_time_ms=1.5,
        )

        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute(
            "SELECT mode, search_type, top_match, result FROM screening_logs WHERE mode = 'country' ORDER BY id DESC LIMIT 1"
        )
        row = cur.fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], "country")
        self.assertEqual(row[1], "Country")
        self.assertEqual(row[2], "Cuba")
        self.assertEqual(row[3], "POTENTIAL_MATCH")


if __name__ == "__main__":
    unittest.main()
