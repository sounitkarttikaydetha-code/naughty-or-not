"""
Tests for T11 Part H: Identifiers, Corroboration, Conflict Downgrades, IMO Validation, and Transliteration.
"""

from pathlib import Path
import unittest

from modules.screening.identifiers import (
    validate_imo,
    match_identifiers,
    assess_corroboration,
    apply_identifier_and_conflict_rules,
)
from modules.screening.tiering import (
    TIER_POTENTIAL_MATCH,
    TIER_POSSIBLE_MATCH,
    TIER_BELOW_THRESHOLD,
    TIER_NO_MATCH,
    screen_query_all_lists,
)
from modules.watchman.client import WatchmanClient


class TestIdentifiersAndTranslit(unittest.TestCase):
    def test_01_imo_check_digit_validation(self):
        # IMO 9074729: 9*7 + 0*6 + 7*5 + 4*4 + 7*3 + 2*2 = 63+0+35+16+21+4 = 139 -> check digit 9
        ok, res = validate_imo("9074729")
        self.assertTrue(ok)
        self.assertEqual(res, "IMO 9074729")

        # Invalid check digit (1 instead of 9)
        bad_ok, bad_msg = validate_imo("9074721")
        self.assertFalse(bad_ok)
        self.assertIn("Invalid IMO check digit", bad_msg)

        # Variations
        ok2, res2 = validate_imo("IMO 9074729")
        self.assertTrue(ok2)
        ok3, res3 = validate_imo("imo-9074729")
        self.assertTrue(ok3)

    def test_02_exact_id_match_upgrades_to_red(self):
        mock_entity = {
            "name": "Target Subject",
            "sourceID": "OFAC-12345",
            "identifications": [
                {"type": "Passport", "number": "P88990011"},
                {"type": "National ID", "number": "NAT-9988-77"},
            ],
            "sourceData": {"remarks": "IMO 9074729; tail RA-73093"},
        }
        # Match on passport
        corrob_pass = assess_corroboration(mock_entity, identifiers=["P88990011"])
        self.assertEqual(corrob_pass["id_status"], "MATCH")
        t, r = apply_identifier_and_conflict_rules(TIER_POSSIBLE_MATCH, "score", corrob_pass)
        self.assertEqual(t, TIER_POTENTIAL_MATCH)
        self.assertEqual(r, "id_match")

        # Match on IMO from remarks
        corrob_imo = assess_corroboration(mock_entity, identifiers=["9074729"])
        self.assertEqual(corrob_imo["id_status"], "MATCH")
        t_imo, r_imo = apply_identifier_and_conflict_rules(TIER_BELOW_THRESHOLD, "score", corrob_imo)
        self.assertEqual(t_imo, TIER_POTENTIAL_MATCH)
        self.assertEqual(r_imo, "id_match")

    def test_03_corroboration_upgrade_orange_to_red(self):
        """🟠 with full DOB + nationality match upgrades to 🔴 name_dob_nat_match."""
        mock_entity = {
            "name": "Vladimir Petrov",
            "person": {
                "birthDate": "1980-05-12",
                "nationalities": ["Russian"],
            },
        }
        corrob = assess_corroboration(
            mock_entity,
            dob="1980-05-12",
            nationality="Russian",
        )
        self.assertEqual(corrob["dob_status"], "MATCH")
        self.assertEqual(corrob["nat_status"], "MATCH")
        self.assertTrue(corrob["corroboration_upgrade"])

        tier, reason = apply_identifier_and_conflict_rules(TIER_POSSIBLE_MATCH, "score", corrob)
        self.assertEqual(tier, TIER_POTENTIAL_MATCH)
        self.assertEqual(reason, "name_dob_nat_match")

    def test_04_controlled_conflict_downgrades(self):
        """1 conflict -> 🔴 to 🟠; 2 conflicts -> 🔴 to 🟠, 🟠 to ℹ️. Never NO_MATCH."""
        mock_entity = {
            "name": "Ivan Ivanov",
            "person": {
                "birthDate": "1975-01-01",
                "nationalities": ["Russian"],
            },
        }

        # 1 Conflict (DOB 1988 != 1975, no nationality provided)
        c1 = assess_corroboration(mock_entity, dob="1988-02-02")
        self.assertEqual(c1["conflict_count"], 1)
        t1, r1 = apply_identifier_and_conflict_rules(TIER_POTENTIAL_MATCH, "core_name", c1)
        self.assertEqual(t1, TIER_POSSIBLE_MATCH)
        self.assertEqual(r1, "conflict_downgrade_1")

        # 2 Conflicts (DOB 1988 != 1975 AND nationality German != Russian)
        c2 = assess_corroboration(mock_entity, dob="1988-02-02", nationality="German")
        self.assertEqual(c2["conflict_count"], 2)

        # Potential match downgrades to Possible match (never hidden)
        t2, r2 = apply_identifier_and_conflict_rules(TIER_POTENTIAL_MATCH, "core_name", c2)
        self.assertEqual(t2, TIER_POSSIBLE_MATCH)
        self.assertEqual(r2, "conflict_downgrade_2")

        # Possible match downgrades to Below threshold (never NO_MATCH)
        t3, r3 = apply_identifier_and_conflict_rules(TIER_POSSIBLE_MATCH, "score", c2)
        self.assertEqual(t3, TIER_BELOW_THRESHOLD)
        self.assertEqual(r3, "conflict_downgrade_2")


if __name__ == "__main__":
    unittest.main()
