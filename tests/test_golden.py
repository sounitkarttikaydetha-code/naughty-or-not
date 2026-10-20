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
                    if actual_tier != exp.get("tier"):
                        mismatches.append(
                            f"[{query_name}] on '{src}': expected '{exp.get('tier')}', got '{actual_tier}'"
                        )

        if mismatches:
            self.fail(f"Golden regression mismatches on verified entries:\n" + "\n".join(mismatches))

        print(f"\n[Golden Regression] Verified entries checked: {verified_count} (all passed).")


if __name__ == "__main__":
    unittest.main()
