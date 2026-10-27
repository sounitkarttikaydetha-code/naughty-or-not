"""
Unit Tests for Start-up Self-Test Framework (T11 Part I).
Validates:
- Layer 1 Engine Canary invariant checks
- Canary tamper detection and ENGINE_CANARY_FAILURE
- Layer 2 Self-sampled live probes and nonsense string validation
- Layer 3 Named probes, drift reporting as soft notes (never hard-block)
- Full self-test execution time <= 2.0s
"""

from pathlib import Path
import tempfile
import unittest
import yaml

from modules.common.self_test import (
    run_layer1_canary,
    run_layer2_sampled_probes,
    run_layer3_named_probes,
    run_full_self_test,
)


class TestStartupSelfTest(unittest.TestCase):
    """Test suite for the 3-layer startup self-test engine."""

    def test_01_layer1_canary_passes_all_invariants(self):
        """Layer 1 canary must pass all 20 fixed matching invariants."""
        res = run_layer1_canary()
        self.assertTrue(res["passed"], f"Canary failures: {res.get('failures')}")
        self.assertEqual(res["failed_count"], 0)
        self.assertGreaterEqual(res["total"], 20)
        self.assertIsNone(res["error_code"])

    def test_02_layer1_canary_detects_tamper_and_sets_failure_code(self):
        """If a canary invariant fails, ENGINE_CANARY_FAILURE must be triggered."""
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as tf:
            # Create a tampered fixture where exact match expects NO_MATCH
            tampered_data = {
                "canaries": [
                    {
                        "id": "tampered_canary",
                        "query": "Omega Global Trade Ltd",
                        "entity": {"name": "Omega Global Trade Ltd", "match": 1.0, "entityType": "organization"},
                        "expected_tier": "NO_MATCH",  # Inconsistent: actual is POTENTIAL_MATCH
                    }
                ]
            }
            yaml.dump(tampered_data, tf)
            temp_path = Path(tf.name)

        try:
            res = run_layer1_canary(fixture_path=temp_path)
            self.assertFalse(res["passed"])
            self.assertEqual(res["error_code"], "ENGINE_CANARY_FAILURE")
            self.assertEqual(res["failed_count"], 1)
            self.assertEqual(res["failures"][0]["id"], "tampered_canary")
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_03_layer2_sampled_probes_and_clean_nonsense(self):
        """Layer 2 must resolve live sampled records and reject nonsense strings."""
        res = run_layer2_sampled_probes(sample_size=5)
        self.assertTrue(res["passed"])
        self.assertTrue(res["nonsense_clean"])
        self.assertGreaterEqual(res.get("sampled_matches", 0), 1)

    def test_04_layer3_named_probes_loads_and_soft_reports(self):
        """Layer 3 must check named probe entities and pass without blocking."""
        res = run_layer3_named_probes()
        self.assertTrue(res["passed"])
        self.assertEqual(res["probes_count"], 10)
        self.assertGreaterEqual(res["matched_count"], 9)

    def test_05_layer3_drift_records_soft_note_without_hard_blocking(self):
        """Delisted or missing named probe records soft note but never hard-blocks startup."""
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as tf:
            drift_data = {
                "probes": [
                    {
                        "id": "delisted_entity_probe",
                        "name": "NonExistentDesignationCorp999XYZ",
                        "expected_tier": "POTENTIAL_MATCH",
                    }
                ]
            }
            yaml.dump(drift_data, tf)
            temp_path = Path(tf.name)

        try:
            res = run_layer3_named_probes(config_path=temp_path)
            # Crucial: Layer 3 passed must still be True!
            self.assertTrue(res["passed"])
            self.assertEqual(res["matched_count"], 0)
            self.assertEqual(len(res["notes"]), 1)
            self.assertIn("NonExistentDesignationCorp999XYZ", res["notes"][0])
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_06_full_self_test_runs_under_two_seconds(self):
        """All 3 layers combined must complete execution in <= 2.0 seconds."""
        res = run_full_self_test()
        self.assertTrue(res["passed"])
        self.assertFalse(res["has_canary_failure"])
        self.assertTrue(res["within_budget"], f"Took {res['duration_ms']}ms, expected <= 2000ms")
        self.assertLessEqual(res["duration_ms"], 2000.0)
        self.assertIn("layer1", res)
        self.assertIn("layer2", res)
        self.assertIn("layer3", res)


if __name__ == "__main__":
    unittest.main()
