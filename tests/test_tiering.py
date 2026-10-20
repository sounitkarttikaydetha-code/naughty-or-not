"""
Comprehensive unit tests for the updated Match Tiering Layer (v2).
Covers two-way core check, alias splitting, weak words, person rules, and identifier conflicts.
"""

import unittest
from modules.screening.tiering import (
    TIER_NO_MATCH,
    TIER_POSSIBLE_MATCH,
    TIER_POTENTIAL_MATCH,
    check_core_name_match,
    check_secondary_identifier_conflict,
    extract_all_aliases,
    normalize_name,
    split_alias_parts,
    tier_single_entity,
)


class TestMatchTieringLayerV2(unittest.TestCase):
    """Test suite covering all fixes specified in user request."""

    def test_1_two_way_core_name_check_reverse(self):
        """
        1. Two-way core-name check:
        'Sberbank of Russia' vs EU alias 'Sberbank' -> 🔴 via core_name_reverse.
        """
        q_words = normalize_name("Sberbank of Russia")
        c_words = normalize_name("Sberbank")
        is_m, m_type = check_core_name_match(q_words, c_words, is_person=False)
        self.assertTrue(is_m)
        self.assertEqual(m_type, "core_name_reverse")

        dummy_eu_entity = {
            "name": "Сбербанк",
            "match": 0.6904,
            "sourceList": "eu_csl",
            "sourceID": "142064",
            "business": {"altNames": ["Sberbank"]},
        }
        res = tier_single_entity("Sberbank of Russia", dummy_eu_entity)
        self.assertIsNotNone(res)
        self.assertEqual(res["tier"], TIER_POTENTIAL_MATCH)
        self.assertEqual(res["reason"], "core_name_reverse")

    def test_2_alias_splitting(self):
        """
        2. Alias splitting:
        Split on d/b/a, a.k.a., and brackets.
        'SIBERIAN AIRLINES D/B/A S7 AIRLINES' -> splits into separate aliases.
        """
        parts = split_alias_parts("SIBERIAN AIRLINES D/B/A S7 AIRLINES")
        self.assertIn("SIBERIAN AIRLINES", parts)
        self.assertIn("S7 AIRLINES", parts)

        bracket_parts = split_alias_parts("PJSC Sberbank (Public Joint-Stock Company Sberbank)")
        self.assertIn("PJSC Sberbank", bracket_parts)
        self.assertIn("Public Joint-Stock Company Sberbank", bracket_parts)

        # S7 Airlines matches S7 AIRLINES part
        dummy_csl = {
            "name": "SIBERIAN AIRLINES D/B/A S7 AIRLINES",
            "match": 0.8122,
            "sourceList": "us_csl",
            "sourceID": "b04d5f6e",
            "entityType": "organisation",
        }
        res_s7 = tier_single_entity("S7 Airlines", dummy_csl)
        self.assertIsNotNone(res_s7)
        self.assertEqual(res_s7["tier"], TIER_POTENTIAL_MATCH)
        self.assertEqual(res_s7["matched_name"], "S7 AIRLINES")

        # Siberia Airlines vs SIBERIAN AIRLINES:
        # 'siberia' vs 'siberian' is a stem difference and does not trigger core_name
        dummy_csl_low = {
            "name": "SIBERIAN AIRLINES D/B/A S7 AIRLINES",
            "match": 0.6482,
            "sourceList": "us_csl",
            "sourceID": "b04d5f6e",
            "entityType": "organisation",
        }
        res_siberia = tier_single_entity("Siberia Airlines", dummy_csl_low)
        # Does not force a core_name match. Because score 0.6482 < 0.70 without core match, discarded by Rule 6
        self.assertIsNone(res_siberia)

    def test_3_check_every_alias_rajesh_kumar(self):
        """
        3. Check every alias:
        'Rajesh Kumar' vs UK entry where primary is 'GUPTA Rajesh Kumar'.
        Ensures alias / bracket parsing runs and person rule properly categorizes it.
        """
        dummy_uk_gupta = {
            "name": "GUPTA Rajesh Kumar",
            "entityType": "person",
            "sourceList": "uk_csl",
            "sourceID": "GAC0018",
            "match": 0.7742,
            "person": {"name": "GUPTA Rajesh Kumar", "altNames": ["GUPTA Tony"]},
            "sourceData": {"Names": ["GUPTA Rajesh Kumar", "Rajesh Kumar GUPTA"]},
        }
        aliases = extract_all_aliases(dummy_uk_gupta)
        self.assertIn("Rajesh Kumar GUPTA", aliases)

        res = tier_single_entity("Rajesh Kumar", dummy_uk_gupta, query_type="person")
        self.assertIsNotNone(res)
        # Because query is a person and core words are a subset of candidate words, Person Rule 5 triggers 🟠 partial_name_person
        self.assertEqual(res["tier"], TIER_POSSIBLE_MATCH)
        self.assertEqual(res["reason"], "partial_name_person")
        self.assertNotEqual(res["tier"], TIER_POTENTIAL_MATCH)

        # High-score regression test: even with score 0.88 or 0.95, person partial match MUST NOT become 🔴
        dummy_high_score = dict(dummy_uk_gupta)
        dummy_high_score["match"] = 0.8800
        res_high = tier_single_entity("Rajesh Kumar", dummy_high_score, query_type="person")
        self.assertIsNotNone(res_high)
        self.assertEqual(res_high["tier"], TIER_POSSIBLE_MATCH)
        self.assertEqual(res_high["reason"], "partial_name_person")
        self.assertNotEqual(res_high["tier"], TIER_POTENTIAL_MATCH)

    def test_4_weak_generic_words(self):
        """
        4. Weak generic words (T1.4 correction):
        - A core-name pass is blocked only if every shared word is a weak word.
        - Weak words in listed name but not in query do not block a pass.
        - 'UTair' vs 'UTAIR AVIATION JSC' -> 🔴 core_name.
        - 'IndiGo' vs 'Indigo 3D' -> not 🔴.
        - 'S7 Airlines' vs 'S. Group Airlines' -> not 🔴.
        - 'Aeroflot' vs 'PJSC Aeroflot' -> 🔴.
        """
        # A. UTair vs UTAIR AVIATION JSC -> 🔴 core_name
        dummy_utair = {
            "name": "UTAIR AVIATION JSC,",
            "match": 0.7285,
            "sourceList": "us_csl",
            "sourceID": "1c9ad49f",
            "entityType": "organisation",
        }
        res_utair = tier_single_entity("UTair", dummy_utair)
        self.assertIsNotNone(res_utair)
        self.assertEqual(res_utair["tier"], TIER_POTENTIAL_MATCH)
        self.assertEqual(res_utair["reason"], "core_name")

        # B. IndiGo vs Indigo 3D (extra distinctive token '3D' prevents forward subset match)
        dummy_indigo = {
            "name": "LIMITED LIABILITY COMPANY INDIGO 3D",
            "match": 0.7635,
            "sourceList": "us_ofac",
            "sourceID": "33333",
            "entityType": "organisation",
        }
        res_indigo = tier_single_entity("IndiGo", dummy_indigo)
        self.assertIsNotNone(res_indigo)
        self.assertNotEqual(res_indigo["tier"], TIER_POTENTIAL_MATCH)
        self.assertEqual(res_indigo["tier"], TIER_POSSIBLE_MATCH)
        self.assertEqual(res_indigo["reason"], "score")

        # C. S7 Airlines vs S. Group Airlines (shared word 'airlines' is weak; no shared non-weak word)
        dummy_s_group = {
            "name": "S. GROUP AIRLINES LTD",
            "match": 0.7549,
            "sourceList": "us_ofac",
            "sourceID": "44444",
            "entityType": "organisation",
        }
        res_s7 = tier_single_entity("S7 Airlines", dummy_s_group)
        self.assertIsNotNone(res_s7)
        self.assertNotEqual(res_s7["tier"], TIER_POTENTIAL_MATCH)
        self.assertEqual(res_s7["tier"], TIER_POSSIBLE_MATCH)
        self.assertEqual(res_s7["reason"], "score")

        # D. Aeroflot vs PJSC Aeroflot (still 🔴)
        dummy_aeroflot = {
            "name": "PJSC Aeroflot",
            "match": 0.7716,
            "sourceList": "uk_csl",
            "sourceID": "RUS1444",
            "entityType": "organisation",
        }
        res_aero = tier_single_entity("Aeroflot", dummy_aeroflot)
        self.assertIsNotNone(res_aero)
        self.assertEqual(res_aero["tier"], TIER_POTENTIAL_MATCH)
        self.assertEqual(res_aero["reason"], "core_name")

    def test_5_person_rule_and_secondary_identifiers(self):
        """
        5. Person rule:
        - Subset match -> 🟠 partial_name_person
        - Secondary identifier conflict downgrades 🔴 to 🟠
        - Missing data does NOT downgrade
        """
        # A. Subset match only: 'Mohammed Khan' vs 'Haji Mohammad Khan'
        dummy_haji = {
            "name": "Haji Mohammad KHAN",
            "match": 0.7557,
            "entityType": "person",
            "sourceList": "us_ofac",
            "sourceID": "12588",
            "person": {"name": "Haji Mohammad KHAN", "birthDate": "1980-01-01T00:00:00Z"},
        }
        res_haji = tier_single_entity("Mohammed Khan", dummy_haji, query_type="person")
        self.assertIsNotNone(res_haji)
        self.assertEqual(res_haji["tier"], TIER_POSSIBLE_MATCH)
        self.assertEqual(res_haji["reason"], "partial_name_person")

        # B. Secondary identifier conflict: Mohammed Khan (ID 10898 has DOB 1955)
        # Query specifies YOB 1985 -> conflict downgrades 🔴 to 🟠
        dummy_mohammed_sdn = {
            "name": "Haji Asad Khan Zarkari MOHAMMADHASNI",
            "match": 0.8122,
            "entityType": "person",
            "sourceList": "us_ofac",
            "sourceID": "10898",
            "person": {
                "name": "Haji Asad Khan Zarkari MOHAMMADHASNI",
                "altNames": ["Mohammed KHAN"],
                "birthDate": "1955-01-01T00:00:00Z",
            },
            "sourceData": {"Nationality": "Afghanistan"},
        }
        # Without conflict: score >= 0.80 and exact alias match -> 🔴
        res_no_conflict = tier_single_entity("Mohammed Khan", dummy_mohammed_sdn, query_type="person")
        self.assertEqual(res_no_conflict["tier"], TIER_POTENTIAL_MATCH)

        # With conflicting YOB (1985 vs 1955) -> downgraded to 🟠
        res_conflict = tier_single_entity(
            "Mohammed Khan", dummy_mohammed_sdn, query_type="person", yob="1985"
        )
        self.assertEqual(res_conflict["tier"], TIER_POSSIBLE_MATCH)
        self.assertEqual(res_conflict["reason"], "secondary_identifier_conflict")

        # With matching YOB (1955) -> remains 🔴
        res_matching = tier_single_entity(
            "Mohammed Khan", dummy_mohammed_sdn, query_type="person", yob="1955"
        )
        self.assertEqual(res_matching["tier"], TIER_POTENTIAL_MATCH)

    def test_6_empty_query_handled_cleanly(self):
        """Empty query returns NO_MATCH cleanly."""
        dummy = {"name": "Aeroflot", "match": 0.75}
        res = tier_single_entity("", dummy)
        self.assertIsNone(res)

    def test_7_sberbank_of_russia_on_eu_csl_live(self):
        """T1.3 Item 1: 'Sberbank of Russia' on eu_csl must be 🔴 via core_name_reverse."""
        from modules.screening.tiering import screen_query_all_lists
        res = screen_query_all_lists("Sberbank of Russia", query_type="organisation")
        eu_hit = res["eu_csl"]["best_hit"]
        self.assertEqual(eu_hit["tier"], TIER_POTENTIAL_MATCH)
        self.assertEqual(eu_hit["reason"], "core_name_reverse")
        self.assertEqual(eu_hit["matched_name"], "Sberbank")

    def test_8_s7_airlines_on_us_csl_live(self):
        """T1.3/T1.4: 'S7 Airlines' on us_csl must return 'SIBERIAN AIRLINES D/B/A S7 AIRLINES'."""
        from modules.screening.tiering import screen_query_all_lists
        res = screen_query_all_lists("S7 Airlines", query_type="airline")
        csl_hit = res["us_csl"]["best_hit"]
        self.assertEqual(csl_hit["tier"], TIER_POTENTIAL_MATCH)
        self.assertEqual(csl_hit["primary_name"], "SIBERIAN AIRLINES D/B/A S7 AIRLINES")
        self.assertEqual(csl_hit["matched_name"], "S7 AIRLINES")
        self.assertEqual(csl_hit["reason"], "core_name")
        self.assertAlmostEqual(csl_hit["score"], 0.4971, places=3)
        self.assertEqual(csl_hit.get("score_source"), "query")

    def test_9_siberia_airlines_on_us_csl_stem_difference(self):
        """T1.4 Item 3: 'Siberia Airlines' vs 'SIBERIAN AIRLINES' stem difference -> NO_MATCH on us_csl."""
        from modules.screening.tiering import screen_query_all_lists
        res = screen_query_all_lists("Siberia Airlines", query_type="airline")
        csl_hit = res["us_csl"]["best_hit"]
        self.assertEqual(csl_hit["tier"], TIER_NO_MATCH)
        self.assertEqual(csl_hit["tier_icon"], "✅")



if __name__ == "__main__":
    unittest.main()
