"""
Unit tests for Match Tiering Layer and Normalisation.
"""

import unittest
from modules.screening.tiering import (
    TIER_NO_MATCH,
    TIER_POSSIBLE_MATCH,
    TIER_POTENTIAL_MATCH,
    core_name_match,
    normalize_name,
    tier_entity,
)


class TestMatchTieringLayer(unittest.TestCase):
    """Test suite for Step 4 requirements."""

    def test_aeroflot_vs_pjsc_aeroflot_core_name(self):
        """
        'Aeroflot' vs 'PJSC Aeroflot' -> POTENTIAL_MATCH (🔴) via core_name.
        PJSC is stripped as a company suffix, leaving exact matching tokens ['aeroflot'].
        """
        is_match, matched_name = core_name_match("Aeroflot", "PJSC Aeroflot")
        self.assertTrue(is_match)
        self.assertEqual(matched_name, "PJSC Aeroflot")

        # Entity scoring below 0.80 should still be promoted to POTENTIAL_MATCH via core_name
        dummy_entity = {
            "name": "PJSC Aeroflot",
            "match": 0.7716,
            "sourceList": "uk_csl",
            "sourceID": "RUS1444",
        }
        tiered = tier_entity("Aeroflot", dummy_entity)
        self.assertEqual(tiered["tier"], TIER_POTENTIAL_MATCH)
        self.assertEqual(tiered["reason"], "core_name")
        self.assertEqual(tiered["score"], 0.7716)

    def test_air_india_vs_air_india_express(self):
        """
        'Air India' vs 'Air India Express' -> not POTENTIAL_MATCH (🔴) via core_name
        unless the score qualifies (score >= 0.80).
        """
        # 1. In exact core match mode, core_name_match fails because 'express' is an extra non-company word
        is_match, _ = core_name_match(
            "Air India", "Air India Express", require_exact=True
        )
        self.assertFalse(is_match)

        # 2. When score is between 0.65 and 0.80 (e.g. 0.72), tier is POSSIBLE_MATCH_REVIEW (🟠) via score, NOT core_name
        dummy_candidate_mid_score = {
            "name": "Air India Express",
            "match": 0.72,
            "sourceList": "us_csl",
            "sourceID": "12345",
        }
        res_mid = tier_entity("Air India", dummy_candidate_mid_score, require_exact=True)
        self.assertEqual(res_mid["tier"], TIER_POSSIBLE_MATCH)
        self.assertEqual(res_mid["reason"], "score")
        self.assertNotEqual(res_mid["reason"], "core_name")

        # 3. Only if score >= 0.80 does it qualify for POTENTIAL_MATCH (🔴), and the reason is 'score', not 'core_name'
        dummy_candidate_high_score = {
            "name": "Air India Express",
            "match": 0.85,
            "sourceList": "us_csl",
            "sourceID": "12345",
        }
        res_high = tier_entity("Air India", dummy_candidate_high_score, require_exact=True)
        self.assertEqual(res_high["tier"], TIER_POTENTIAL_MATCH)
        self.assertEqual(res_high["reason"], "score")

    def test_empty_query_handled_cleanly(self):
        """Empty or whitespace-only query is handled cleanly without crashing."""
        for empty_q in ["", "   ", ".,;"]:
            words = normalize_name(empty_q)
            self.assertEqual(words, [])

            is_match, _ = core_name_match(empty_q, "PJSC Sberbank")
            self.assertFalse(is_match)

            dummy_entity = {
                "name": "PJSC Sberbank",
                "match": 0.70,
                "sourceList": "us_ofac",
                "sourceID": "17018",
            }
            res = tier_entity(empty_q, dummy_entity)
            self.assertIn(res["tier"], [TIER_POSSIBLE_MATCH, TIER_NO_MATCH])
            self.assertNotEqual(res["reason"], "core_name")


if __name__ == "__main__":
    unittest.main()
