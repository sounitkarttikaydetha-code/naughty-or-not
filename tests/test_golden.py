"""
Golden Regression Suite
Validates screening results against verified expectations in tests/golden_set.json.
Only expectations marked with "verified": true cause test failures when mismatched.
"""

import json
from pathlib import Path
import unittest

from modules.screening.tiering import screen_query_all_lists
from modules.watchman.client import WatchmanClient

GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.json"


class TestGoldenRegression(unittest.TestCase):
    """Test suite ensuring verified golden expectations remain strictly unbroken."""

    @classmethod
    def setUpClass(cls):
        cls.client = WatchmanClient()
        health = cls.client.health()
        if not health.get("healthy"):
            raise unittest.SkipTest("Watchman service is not reachable on localhost:8084")

        with open(GOLDEN_SET_PATH, "r", encoding="utf-8") as f:
            cls.golden_data = json.load(f)

    def test_verified_golden_expectations(self):
        """
        Verify that all expectations marked as verified=True match the engine's output.
        Expectations marked as verified=False are recorded but do not fail the build.
        """
        verified_count = 0
        mismatches = []

        for query_name, entry in self.golden_data.items():
            query_type = entry.get("query_type")
            expected_lists = entry.get("lists", {})

            # Check if any list in this entry has verified == True
            has_verified = any(item.get("verified") is True for item in expected_lists.values())
            if not has_verified:
                continue

            # Run screening only if verified tests are present
            actual_results = screen_query_all_lists(
                query=query_name, client=self.client, query_type=query_type
            )

            for src, exp in expected_lists.items():
                if exp.get("verified") is True:
                    verified_count += 1
                    actual_tier = actual_results.get(src, {}).get("best_hit", {}).get("tier")
                    expected_tier = exp.get("tier")
                    evidence = exp.get("evidence", "")

                    if evidence == "known_clean_entity":
                        # Negative regression lock: MUST NOT be 🔴 on any list
                        if actual_tier == "POTENTIAL_MATCH":
                            matched_n = actual_results.get(src, {}).get("best_hit", {}).get("matched_name")
                            mismatches.append(
                                f"[{query_name}] on '{src}': FALSE RED! Clean entity got 🔴 POTENTIAL_MATCH (Matched: '{matched_n}')"
                            )
                    else:
                        # Positive regression lock: must match expected 🔴 or 🟠
                        if actual_tier not in ["POTENTIAL_MATCH", "POSSIBLE_MATCH_REVIEW"]:
                            mismatches.append(
                                f"[{query_name}] on '{src}': expected 🔴 or 🟠 ('{expected_tier}'), but got '{actual_tier}' (Evidence: {evidence})"
                            )
                        elif actual_tier != expected_tier:
                            mismatches.append(
                                f"[{query_name}] on '{src}': expected '{expected_tier}', got '{actual_tier}' (Evidence: {evidence})"
                            )


        if mismatches:
            self.fail(f"Golden regression mismatches on verified entries:\n" + "\n".join(mismatches))

        self.assertGreater(verified_count, 0, "Golden regression suite must verify at least one golden expectation")
        print(f"\n[Golden Regression] Verified entries checked: {verified_count} (all passed).")

    def test_part1_golden_locks(self):
        """
        Part 1 item 4 golden locks:
        - S7 (Airline) -> us_csl -> 🔴 'SIBERIAN AIRLINES D/B/A S7 AIRLINES', matched alias 'S7 AIRLINES'
        - S7 Airlines (Airline) -> us_csl, uk_csl -> 🔴 on both
        - Siberia Airlines (Airline) -> us_csl -> 🔴 via expanded_from
        - Siberian Airlines (Organisation) -> us_csl -> 🔴
        - S7 / Siberia Airlines -> us_ofac 'SIBERIA' record -> never 🔴
        - Aeroflot Russian Airlines (Airline) -> us_csl, uk_csl -> 🔴
        - Air India (Organisation) -> all lists -> never 🔴
        """
        # 1. S7 (Airline) on us_csl
        res_s7 = screen_query_all_lists("S7", client=self.client, query_type="airline")
        h_s7_csl = res_s7["us_csl"]["best_hit"]
        self.assertEqual(h_s7_csl.get("tier"), "POTENTIAL_MATCH")
        self.assertEqual(h_s7_csl.get("matched_name"), "S7 AIRLINES")
        self.assertIn("SIBERIAN AIRLINES", h_s7_csl.get("primary_name", ""))
        self.assertEqual(h_s7_csl.get("source_id"), "b04d5f6edf0e3b9ca1ff24074e5f382eb02ba47cf381db8217f9b8bd")

        # 2. S7 Airlines (Airline) on us_csl and uk_csl
        res_s7_air = screen_query_all_lists("S7 Airlines", client=self.client, query_type="airline")
        self.assertEqual(res_s7_air["us_csl"]["best_hit"].get("tier"), "POTENTIAL_MATCH")
        self.assertEqual(res_s7_air["uk_csl"]["best_hit"].get("tier"), "POTENTIAL_MATCH")

        # 3. Siberia Airlines (Airline) on us_csl via expanded_from
        res_sib_air = screen_query_all_lists("Siberia Airlines", client=self.client, query_type="airline")
        h_sib_csl = res_sib_air["us_csl"]["best_hit"]
        self.assertEqual(h_sib_csl.get("tier"), "POTENTIAL_MATCH")
        self.assertIsNotNone(h_sib_csl.get("expanded_from"))

        # 4. Siberian Airlines (Organisation) on us_csl
        res_sib_org = screen_query_all_lists("Siberian Airlines", client=self.client, query_type="organisation")
        self.assertEqual(res_sib_org["us_csl"]["best_hit"].get("tier"), "POTENTIAL_MATCH")

        # 5. S7 / Siberia Airlines on us_ofac "SIBERIA" record: never 🔴
        self.assertNotEqual(res_s7["us_ofac"]["best_hit"].get("tier"), "POTENTIAL_MATCH")
        self.assertNotEqual(res_sib_air["us_ofac"]["best_hit"].get("tier"), "POTENTIAL_MATCH")

        # 6. Aeroflot Russian Airlines (Airline) on us_csl and uk_csl: 🔴
        res_aero = screen_query_all_lists("Aeroflot Russian Airlines", client=self.client, query_type="airline")
        self.assertEqual(res_aero["us_csl"]["best_hit"].get("tier"), "POTENTIAL_MATCH")
        self.assertEqual(res_aero["uk_csl"]["best_hit"].get("tier"), "POTENTIAL_MATCH")

        # 7. Air India (Organisation) on all lists: never 🔴
        res_ai = screen_query_all_lists("Air India", client=self.client, query_type="organisation")
        for s in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]:
            self.assertNotEqual(res_ai[s]["best_hit"].get("tier"), "POTENTIAL_MATCH")


if __name__ == "__main__":
    unittest.main()
