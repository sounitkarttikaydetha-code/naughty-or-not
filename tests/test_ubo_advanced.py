"""
Advanced UBO & Compliance SOP Tests (T11.1 Section 1.2 & 1.3).
Tests:
- Worked Example 1: Effective 20% diligence trigger (40% of 50% = 20% effective -> flagged)
- Worked Example 2: Direct 19.9% -> not flagged by 20% trigger, but above 10% Indian BO marker
- Worked Example 3: 25% holder with missing DOB/ID -> 'KYC incomplete' flag
- Worked Example 4: Alpha Ground Services complex case (Beta 60%, Sharma 25%, 15% undisclosed, P 50% of Beta listed)
- 7-sheet Excel template import and round-trip export
- Word (.docx) import
- Shortfall: Undisclosed ownership: X% and 'Result depends on undisclosed X%'
- Cycle detection & holdings <= 100%
- EU 50% rule threshold (>= 50.0%) and UK conservative aggregate shown alongside
- UN and MHA listed party alerts
- Natural person resolution with fallback to Senior Managing Official
- Four-eyes review user separation, versioning, and review due date
- Evidence pack generation
- Re-screening of saved checks on list update
"""

import io
from pathlib import Path
import tempfile
import unittest

from modules.ownership.models import (
    Counterparty,
    ControlRelation,
    FourEyesReview,
    Holding,
    KeyPerson,
    OwnershipNode,
    TrustDetails,
    UBOResult,
)
from modules.ownership.engine import UBOEngine
from modules.ownership.importer import (
    export_ownership_workbook,
    get_user_mappings_dir,
    list_available_mappings,
    parse_docx,
    parse_ownership_workbook,
)


class TestUBOAdvanced(unittest.TestCase):
    """Test suite for advanced UBO requirements and worked examples."""

    def setUp(self):
        self.engine = UBOEngine()

    def test_we1_effective_20_pct_diligence_trigger(self):
        """
        Worked Example 1:
        A holds 40% of B, and B holds 50% of Counterparty.
        A's effective holding is 40% * 50% = 20.0%.
        A's direct holding in Counterparty is 0.0%.
        Result: A is flagged by the 20% diligence trigger (Adani SOP),
        even though direct holding is 0%.
        """
        holdings = [
            Holding(shareholder_name="Entity B", entity_name="Target Corp", share_pct=50.0),
            Holding(shareholder_name="Investor A", entity_name="Entity B", share_pct=40.0, dob="1975-01-01", id_number="ID123"),
            Holding(shareholder_name="Other Co", entity_name="Target Corp", share_pct=50.0),
        ]
        res = self.engine.evaluate_structure(
            counterparty=Counterparty(name="Target Corp"),
            holdings=holdings,
            auto_screen=False,
        )
        self.assertAlmostEqual(res.effective_holdings.get("Investor A", 0.0), 20.0, places=1)
        flagged_names = [d["name"] for d in res.diligence_triggers]
        self.assertIn("Investor A", flagged_names)

    def test_we2_direct_19_9_pct_marker_only(self):
        """
        Worked Example 2:
        Direct holding of 19.9% -> not flagged by 20% diligence trigger,
        but shown above the 10% Indian BO marker (info-only).
        """
        holdings = [
            Holding(shareholder_name="Partner C", entity_name="Target Corp", share_pct=19.9, dob="1980-05-10", id_number="PASS999"),
            Holding(shareholder_name="Majority Co", entity_name="Target Corp", share_pct=80.1),
        ]
        res = self.engine.evaluate_structure(
            counterparty=Counterparty(name="Target Corp"),
            holdings=holdings,
            auto_screen=False,
        )
        diligence_names = [d["name"] for d in res.diligence_triggers]
        self.assertNotIn("Partner C", diligence_names)

        marker_names = [m["name"] for m in res.india_bo_markers]
        self.assertIn("Partner C", marker_names)
        self.assertIn("Above the Indian beneficial-owner threshold", res.india_bo_markers[0]["label"])

    def test_we3_25_pct_holder_kyc_incomplete(self):
        """
        Worked Example 3:
        A 25% holder with missing Date of Birth and missing ID number
        must be flagged with 'KYC incomplete'.
        """
        holdings = [
            Holding(shareholder_name="Opaque Person D", entity_name="Target Corp", share_pct=25.0, dob="", id_number=""),
            Holding(shareholder_name="Remaining Co", entity_name="Target Corp", share_pct=75.0),
        ]
        res = self.engine.evaluate_structure(
            counterparty=Counterparty(name="Target Corp"),
            holdings=holdings,
            auto_screen=False,
        )
        d_item = next(d for d in res.diligence_triggers if d["name"] == "Opaque Person D")
        self.assertTrue(d_item["kyc_incomplete"])
        self.assertIn("KYC incomplete", d_item["flags"])

    def test_we4_alpha_ground_services_complex_case(self):
        """
        Worked Example 4: Alpha Ground Services
        - Target: Alpha Ground Services
        - Direct Holdings: Beta 60%, Sharma 25%, 15% undisclosed (shortfall)
        - Holdings in Beta: P 50%, Q 50%
        - Sanctions status: P is listed on OFAC/EU/UK/UN; Q, Sharma, Beta unlisted.
        Expected results:
          - OFAC: criteria met (Beta is 50% owned by P -> Beta is blocked; Beta owns 60% of Alpha -> Alpha is blocked)
          - EU: criteria met (Beta is 50% owned by P; Beta owns 60% of Alpha -> criteria met)
          - UK: not met at exactly 50% in Beta (>50% required), with boundary note
          - UN: scenario flag for listed owner P
          - Gaps: 15% undisclosed ownership reported
          - Beneficial owners: P and Q each at effective 30.0%
        """
        holdings = [
            Holding(shareholder_name="Beta Holdings", entity_name="Alpha Ground Services", share_pct=60.0),
            Holding(shareholder_name="R. Sharma", entity_name="Alpha Ground Services", share_pct=25.0, dob="1970-03-15", id_number="IND-PAN-1234"),
            Holding(shareholder_name="Person P", entity_name="Beta Holdings", share_pct=50.0, user_override="BLOCKED", dob="1965-08-20", id_number="RUS-1122"),
            Holding(shareholder_name="Person Q", entity_name="Beta Holdings", share_pct=50.0, user_override="CLEAR", dob="1968-11-05", id_number="CYP-3344"),
        ]
        res = self.engine.evaluate_structure(
            counterparty=Counterparty(name="Alpha Ground Services"),
            holdings=holdings,
            auto_screen=False,
        )
        self.assertAlmostEqual(res.undisclosed_ownership_pct, 15.0, places=1)
        self.assertAlmostEqual(res.effective_holdings.get("Person P", 0.0), 30.0, places=1)
        self.assertAlmostEqual(res.effective_holdings.get("Person Q", 0.0), 30.0, places=1)
        self.assertAlmostEqual(res.effective_holdings.get("R. Sharma", 0.0), 25.0, places=1)
        self.assertTrue(res.ofac_verdict["criteria_met"])
        self.assertTrue(res.eu_verdict["criteria_met"])
        self.assertFalse(res.uk_verdict["condition_1_met"])
        self.assertTrue(any("boundary" in note.lower() or "50%" in note for note in res.uk_verdict.get("notes", [])))
        self.assertTrue(len(res.un_mha_flags) > 0)

    def test_we5_seven_sheet_template_and_roundtrip(self):
        """Test parsing the 7-sheet template and round-trip export/import producing identical tree."""
        tpl_path = Path("templates/ownership_template.xlsx")
        self.assertTrue(tpl_path.exists())
        cp, holdings, control_rels, key_persons, issues = parse_ownership_workbook(tpl_path)
        self.assertEqual(cp.name, "Alpha Ground Services Private Limited")
        self.assertTrue(len(holdings) >= 4)

        # Evaluate structure
        res = self.engine.evaluate_structure(
            counterparty=cp,
            holdings=holdings,
            control_relations=control_rels,
            key_persons=key_persons,
            auto_screen=False,
        )
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tf:
            out_path = Path(tf.name)

        try:
            export_ownership_workbook(res, out_path)
            # Re-import exported workbook
            cp_re, h_re, cr_re, kp_re, re_issues = parse_ownership_workbook(out_path)
            self.assertEqual(cp_re.name, cp.name)
            self.assertEqual(len(h_re), len(holdings))
            # Verify tree holdings match exactly
            orig_pairs = {(h.shareholder_name, h.entity_name, round(h.share_pct, 2)) for h in holdings}
            re_pairs = {(h.shareholder_name, h.entity_name, round(h.share_pct, 2)) for h in h_re}
            self.assertEqual(orig_pairs, re_pairs)
        finally:
            if out_path.exists():
                out_path.unlink()

    def test_we6_word_docx_import(self):
        """Test Word (.docx) import capability."""
        import docx
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tf:
            doc_path = Path(tf.name)

        try:
            doc = docx.Document()
            doc.add_heading("Beneficial Ownership Schedule", 0)
            table = doc.add_table(rows=1, cols=3)
            hdr_cells = table.rows[0].cells
            hdr_cells[0].text = "Shareholder Name"
            hdr_cells[1].text = "Percentage Stake %"
            hdr_cells[2].text = "Immediate Company"

            row1 = table.add_row().cells
            row1[0].text = "Global Transport Corp"
            row1[1].text = "75.0%"
            row1[2].text = "Aviation Cargo Ltd"

            row2 = table.add_row().cells
            row2[0].text = "Individual Investor"
            row2[1].text = "25.0%"
            row2[2].text = "Aviation Cargo Ltd"

            doc.save(str(doc_path))

            cp, holdings, _, _, issues = parse_docx(doc_path)
            self.assertEqual(len(holdings), 2)
            self.assertEqual(holdings[0].shareholder_name, "Global Transport Corp")
            self.assertEqual(holdings[0].share_pct, 75.0)
        finally:
            if doc_path.exists():
                doc_path.unlink()

    def test_we7_holdings_exceed_100_and_cycle_detection(self):
        """Test validation: holdings > 100% and circular ownership detection."""
        # Holdings > 100%
        h_exceed = [
            Holding(shareholder_name="Co A", entity_name="Target", share_pct=70.0),
            Holding(shareholder_name="Co B", entity_name="Target", share_pct=45.0),
        ]
        res_exceed = self.engine.evaluate_structure(Counterparty(name="Target"), h_exceed, auto_screen=False)
        self.assertTrue(any("exceeding the 100.0% maximum allowed" in err for err in res_exceed.validation_errors))

        # Circular cycle (A -> B -> A)
        h_cycle = [
            Holding(shareholder_name="Entity B", entity_name="Target", share_pct=50.0),
            Holding(shareholder_name="Target", entity_name="Entity B", share_pct=50.0),
        ]
        res_cycle = self.engine.evaluate_structure(Counterparty(name="Target"), h_cycle, auto_screen=False)
        self.assertTrue(res_cycle.cycle_detected)
        self.assertTrue(any("Circular ownership chain" in err for err in res_cycle.validation_errors))

    def test_we8_trust_and_nominee_evaluation(self):
        """Test trusts handling and nominee look-through."""
        # Nominee look-through
        h_nom = [
            Holding(shareholder_name="Nominee Trustee Corp", entity_name="Target", share_pct=60.0, holding_type="nominee", on_behalf_of="Ultimate Beneficiary John"),
        ]
        res_nom = self.engine.evaluate_structure(Counterparty(name="Target"), h_nom, auto_screen=False)
        self.assertAlmostEqual(res_nom.effective_holdings.get("Ultimate Beneficiary John", 0.0), 60.0)

        # Trust evaluation
        trust = TrustDetails(
            trust_name="Alpha Family Trust",
            settlors=["Designated Settlor"],
            trustees=["Swiss Trust SA"],
            beneficiaries=["Beneficiary Child"],
        )
        trust_res = self.engine.evaluate_trust(trust, [])
        self.assertEqual(trust_res["trust_name"], "Alpha Family Trust")

    def test_we9_smo_fallback_and_natural_person_resolution(self):
        """Test natural person resolution and fallback to Senior Managing Official."""
        # Case with only corporate shareholders
        holdings = [
            Holding(shareholder_name="Corporate Owner Ltd", entity_name="Target", share_pct=100.0, entity_type="company"),
        ]
        key_persons = [
            KeyPerson(name="Vikram Malhotra", target_name="Target", role="senior_managing_official"),
        ]
        res = self.engine.evaluate_structure(
            counterparty=Counterparty(name="Target"),
            holdings=holdings,
            key_persons=key_persons,
            auto_screen=False,
        )
        self.assertEqual(len(res.natural_person_ubos), 1)
        self.assertEqual(res.natural_person_ubos[0]["name"], "Vikram Malhotra")
        self.assertEqual(res.natural_person_ubos[0]["role"], "Senior Managing Official")

    def test_we10_four_eyes_user_separation_and_due_date(self):
        """Test four-eyes review user separation validation and review-due date calculation."""
        review = FourEyesReview(preparer="Analyst A", reviewer="Analyst A")
        sep_ok, sep_msg = review.validate_user_separation()
        self.assertFalse(sep_ok)
        self.assertIn("Four-Eyes Violation", sep_msg)

        review_diff = FourEyesReview(preparer="Analyst A", reviewer="Officer B")
        sep_ok_diff, _ = review_diff.validate_user_separation()
        self.assertTrue(sep_ok_diff)

        # Due date: 6 months if sanctions criteria met, 12 months if clear
        h_blocked = [Holding(shareholder_name="Sanctioned Co", entity_name="Target", share_pct=50.0, is_blocked=True, blocked_source="us_ofac")]
        res_b = self.engine.evaluate_structure(Counterparty(name="Target"), h_blocked, auto_screen=False)
        self.assertTrue(res_b.disposition.review_due_date != "")

    def test_we11_evidence_pack_generation(self):
        """Test combined evidence pack generation (PDF and Excel)."""
        holdings = [Holding(shareholder_name="Owner Co", entity_name="Target", share_pct=100.0)]
        res = self.engine.evaluate_structure(Counterparty(name="Target"), holdings, auto_screen=False)
        with tempfile.TemporaryDirectory() as td:
            pdf_p, xlsx_p = self.engine.generate_ubo_evidence_pack(res, output_dir=Path(td))
            self.assertTrue(pdf_p.exists())
            self.assertTrue(xlsx_p.exists())

    def test_we12_mappings_and_sha256_hash(self):
        """Test discovery of mappings and SHA-256 hash recording."""
        user_dir = get_user_mappings_dir()
        self.assertTrue(user_dir.exists())
        mappings = list_available_mappings()
        self.assertTrue(len(mappings) >= 1)
        self.assertTrue(all(len(m["hash"]) == 64 for m in mappings))


if __name__ == "__main__":
    unittest.main()
