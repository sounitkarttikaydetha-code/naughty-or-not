"""
Unit tests for T11 Part B4: Structured Records Store & Full Record Expander.
Validates local SQLite storage, fast retrieval, and display formatting
across OFAC, UK, EU, UN, US CSL, BIS aircraft, EU Air Safety, and MHA.
"""

from pathlib import Path
import unittest

from modules.common.records_store import (
    populate_records_cache,
    get_record,
    format_record_for_display,
    format_record_as_text,
    format_programs,
)


class TestRecordsStore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        populate_records_cache(force=False)

    def test_01_ofac_record(self):
        rec = get_record("us_ofac", "36")
        self.assertIsNotNone(rec, "OFAC entity 36 should exist")
        fields = dict(format_record_for_display(rec))
        self.assertIn("Primary Name", fields)
        self.assertIn("AEROCARIBBEAN", fields["Primary Name"])
        self.assertIn("Sanctions Program", fields)
        txt = format_record_as_text("us_ofac", "36", rec)
        self.assertIn("FULL RECORD: US_OFAC", txt)

    def test_02_uk_record(self):
        rec = get_record("uk_csl", "AFG0001")
        self.assertIsNotNone(rec, "UK entity AFG0001 should exist")
        fields = dict(format_record_for_display(rec))
        self.assertIn("Primary Name", fields)
        self.assertIn("HAJI", fields["Primary Name"])

    def test_03_eu_record(self):
        rec = get_record("eu_csl", "13")
        self.assertIsNotNone(rec, "EU entity 13 should exist")
        fields = dict(format_record_for_display(rec))
        self.assertIn("Primary Name", fields)

    def test_04_un_record(self):
        rec = get_record("un_csl", "UN-6907993")
        self.assertIsNotNone(rec, "UN entity UN-6907993 should exist")
        fields = dict(format_record_for_display(rec))
        self.assertIn("Primary Name", fields)
        self.assertIn("BADEGE", fields["Primary Name"])

    def test_05_us_csl_record(self):
        rec = get_record("us_csl", "17014")
        self.assertIsNotNone(rec, "US CSL entity 17014 should exist")
        fields = dict(format_record_for_display(rec))
        self.assertIn("Primary Name", fields)
        self.assertIn("Russian Agricultural Bank", fields["Primary Name"])

    def test_06_bis_aircraft_record(self):
        rec = get_record("bis_aircraft", "LX-RAY")
        self.assertIsNotNone(rec, "BIS Aircraft LX-RAY should exist")
        fields = dict(format_record_for_display(rec))
        self.assertIn("Tail Number", fields)
        self.assertEqual(fields["Tail Number"], "LX-RAY")
        self.assertIn("Aircraft Type", fields)

    def test_07_eu_air_safety_record(self):
        rec = get_record("eu_air_safety", "TA/010/2002")
        self.assertIsNotNone(rec, "EU Air Safety TA/010/2002 should exist")
        fields = dict(format_record_for_display(rec))
        self.assertIn("Airline", fields)
        self.assertIn("AOC Number", fields)

    def test_08_mha_record(self):
        rec = get_record("in_mha", "IN-UAPA-IND-80")
        self.assertIsNotNone(rec, "MHA entity IN-UAPA-IND-80 should exist")
        fields = dict(format_record_for_display(rec))
        self.assertIn("Primary Name", fields)
        self.assertIn("MHA Schedule", fields)

    def test_09_program_formatter(self):
        self.assertEqual(format_programs("[FTO] [SDGT]"), "FTO; SDGT")
        self.assertEqual(format_programs("FTO] [SDGT"), "FTO; SDGT")
        self.assertEqual(format_programs(["RUSSIA", "CYBER2"]), "RUSSIA; CYBER2")
        self.assertEqual(format_programs(None), "—")


if __name__ == "__main__":
    unittest.main()
