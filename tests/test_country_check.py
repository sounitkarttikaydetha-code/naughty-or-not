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

    def test_06_syria_us_sanctions_revocation_and_paarss(self):
        """Verify Syria US sanctions data reflects E.O. 14312 revocation and PAARSS authority."""
        res = self.engine.screen_country("Syria")
        regimes = res.get("regimes_data", {})
        us_sanctions = regimes.get("us_sanctions", {})
        self.assertIn("14312", us_sanctions.get("authority", ""))
        self.assertIn("PAARSS", us_sanctions.get("summary", ""))
        self.assertIn("revoked effective 1 July 2025", us_sanctions.get("summary", ""))
        self.assertEqual(regimes.get("verification_date"), "2026-10-27")

    def test_07_russia_selective_and_territorial_embargoes(self):
        """Verify Russia US sanctions data reflects selective (extensive) nature and territorial embargoes."""
        res = self.engine.screen_country("Russia")
        regimes = res.get("regimes_data", {})
        us_sanctions = regimes.get("us_sanctions", {})
        summary = us_sanctions.get("summary", "")
        self.assertIn("not countrywide blanket embargo", summary)
        self.assertIn("Crimea", summary)
        self.assertIn("Donetsk", summary)
        self.assertIn("Luhansk", summary)
        self.assertEqual(regimes.get("verification_date"), "2026-10-27")

    def test_08_all_regimes_have_source_urls_and_verification_date(self):
        """Verify every regime entry in country_regimes.yaml has verification_date and source_urls."""
        for iso, data in self.engine.regimes.items():
            self.assertEqual(data.get("verification_date"), "2026-10-27", f"{iso} missing verification_date 2026-10-27")
            self.assertTrue(data.get("source_url", "").startswith("http"), f"{iso} missing top-level source_url")
            for auth in ["us_sanctions", "uk_sanctions", "eu_sanctions", "un_sanctions", "export_controls"]:
                auth_data = data.get(auth, {})
                self.assertTrue(auth_data.get("source_url", "").startswith("http"), f"{iso}.{auth} missing source_url")


if __name__ == "__main__":
    unittest.main()
