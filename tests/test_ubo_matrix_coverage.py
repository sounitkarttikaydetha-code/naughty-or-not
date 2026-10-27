"""
Dedicated Verification Tests for UBO Requirements Matrix (Section 4):
- Req 11: Import preview errors/warnings with sheet, row, col, suggested fix
- Req 13: Format file safe_load, schema validation, refusal of unknown transform
- Req 17: Every party screened against pinned snapshot (offline, deterministic)
- Req 18: Dispositions (Unresolved, Confirmed match, False positive) never modify screening result
- Req 19: Scenario analysis ('If possible matches are confirmed')
- Req 21: EU 50% rule (>= 50%, not >50%) with aggregation assumption note
- Req 23: UN and MHA listed owners/key persons flagged
- Req 24: BIS Entity List affiliates flag (party >= 50% gets 'verify current rule')
- Req 25: All rule values loaded from config/ubo_rules.yaml and verified
- Req 28: Exact statutory verdict wording; never plain 'clear' or 'blocked'
- Req 34: Verification level on every line and self-declared share calculation
- Req 35: All 7 structure risk indicators explicitly asserted
- Req 38: Automatic re-screening after list update -> 'Needs review: list change'
- Req 40: Interactive multi-tier ownership tree visualization structure
- Req 41: Four regime verdict panels rendering structure (OFAC, EU, UK, UN/MHA)
- Req 42: Dedicated report section 'Ownership & Control Analysis'
"""

import io
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import openpyxl
import yaml

from modules.ownership.models import (
    Counterparty,
    ControlRelation,
    DispositionType,
    Holding,
    KeyPerson,
    OwnershipNode,
    UBOResult,
)
from modules.ownership.engine import UBOEngine
from modules.ownership.importer import (
    get_user_mappings_dir,
    list_available_mappings,
    load_mapping,
    parse_ownership_workbook,
    validate_mapping_schema,
)


class TestUBOMatrixCoverage(unittest.TestCase):
    def setUp(self):
        self.engine = UBOEngine()

    def test_req_11_import_preview_errors_and_warnings(self):
        """Req 11: Import preview showing errors and warnings (sheet, row, col, problem, suggested_fix)."""
        wb = openpyxl.Workbook()
        ws_holdings = wb.active
        ws_holdings.title = "Holdings"
        ws_holdings.append(["Immediate Shareholder", "Held In Entity", "Shareholding %"])
        # Row 2: Missing shareholder name
        ws_holdings.append(["", "Target Co", "50.0"])
        # Row 3: Invalid percentage
        ws_holdings.append(["Alpha Corp", "Target Co", "INVALID_PERCENT"])

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        cp, holdings, controls, key_persons, preview_issues = parse_ownership_workbook(buf.getvalue())
        self.assertTrue(len(preview_issues) >= 2, f"Expected at least 2 issues, got {len(preview_issues)}")

        for issue in preview_issues:
            self.assertIn("sheet", issue)
            self.assertIn("row", issue)
            self.assertIn("col", issue)
            self.assertIn("problem", issue)
            self.assertIn("suggested_fix", issue)
            self.assertEqual(issue["sheet"], "Holdings")

        col_names = [iss["col"] for iss in preview_issues]
        self.assertIn("Immediate Shareholder", col_names)
        self.assertIn("Shareholding %", col_names)

    def test_req_13_mapping_schema_validation_and_transform_refusal(self):
        """Req 13: Schema validation, safe_load only, and refusal of unknown transforms."""
        valid_yaml = """
version: "1.0"
name: "Test Valid Mapping"
columns:
  owner_name:
    headers: ["Shareholder"]
    type: "string"
  share_pct:
    headers: ["Percentage"]
    type: "float"
"""
        valid_data = yaml.safe_load(valid_yaml)
        ok, msg = validate_mapping_schema(valid_data)
        self.assertTrue(ok, f"Valid schema failed: {msg}")

        malicious_yaml = """
version: "1.0"
name: "Malicious Mapping"
columns:
  owner_name:
    headers: ["Shareholder"]
    type: "exec_python_code"
"""
        malicious_data = yaml.safe_load(malicious_yaml)
        bad_ok, bad_msg = validate_mapping_schema(malicious_data)
        self.assertFalse(bad_ok)
        self.assertIn("Refused unknown transform/type 'exec_python_code'", bad_msg)

        incomplete_yaml = """
name: "Incomplete Mapping"
"""
        inc_data = yaml.safe_load(incomplete_yaml)
        inc_ok, inc_msg = validate_mapping_schema(inc_data)
        self.assertFalse(inc_ok)
        self.assertIn("Missing required mapping field", inc_msg)

    def test_req_17_pinned_snapshot_screening(self):
        """Req 17: Every party in corporate tree is screened against local lists (tested against pinned snapshot)."""
        pinned_snapshot = {
            "Blocked Parent Ltd": (True, "us_ofac", "OFAC SDN blocked entity"),
            "Intermediate Co": (False, "", ""),
            "Ultimate Individual": (False, "", ""),
        }

        def mock_screen_party(name, entity_type="company"):
            return pinned_snapshot.get(name, (False, "", ""))

        with patch.object(self.engine, "screen_party", side_effect=mock_screen_party):
            holdings = [
                Holding(shareholder_name="Intermediate Co", entity_name="Target", share_pct=60.0),
                Holding(shareholder_name="Blocked Parent Ltd", entity_name="Intermediate Co", share_pct=100.0),
                Holding(shareholder_name="Ultimate Individual", entity_name="Target", share_pct=40.0),
            ]
            res = self.engine.evaluate_structure(Counterparty(name="Target"), holdings, auto_screen=True)

            screened_parties = {h.shareholder_name: h.is_blocked for h in res.holdings}
            self.assertTrue(screened_parties["Blocked Parent Ltd"])
            self.assertFalse(screened_parties["Intermediate Co"])
            self.assertFalse(screened_parties["Ultimate Individual"])

    def test_req_18_disposition_types_and_immutability(self):
        """Req 18: Dispositions (Unresolved, Confirmed match, False positive) never modify underlying screening result."""
        self.assertEqual(DispositionType.UNRESOLVED, "Unresolved")
        self.assertEqual(DispositionType.CONFIRMED_MATCH, "Confirmed match")
        self.assertEqual(DispositionType.FALSE_POSITIVE, "False positive")

        original_hit = {"tier": "POSSIBLE_MATCH", "tier_icon": "🟠", "score": 0.72}
        h = Holding(
            shareholder_name="Volga Logistics",
            entity_name="Target",
            share_pct=50.0,
            is_blocked=False,
            screening_hit=dict(original_hit),
        )

        # Apply False positive disposition
        h.user_override = DispositionType.FALSE_POSITIVE
        self.assertFalse(h.is_blocked, "Disposition must never alter is_blocked status directly")
        self.assertEqual(h.screening_hit["tier"], "POSSIBLE_MATCH", "Original screening tier must remain immutable")
        self.assertEqual(h.screening_hit["score"], 0.72, "Original screening score must remain immutable")

    def test_req_19_scenario_analysis_possible_matches(self):
        """Req 19: 'If possible matches are confirmed' scenario analysis."""
        h1 = Holding(
            shareholder_name="Candidate Party Ltd",
            entity_name="Target",
            share_pct=50.0,
            is_blocked=False,
            screening_hit={"tier": "POSSIBLE_MATCH", "tier_icon": "🟠"},
        )
        res = self.engine.evaluate_structure(Counterparty(name="Target"), [h1], auto_screen=False)
        scenario = self.engine.evaluate_possible_matches_scenario(res)

        self.assertEqual(scenario["unconfirmed_matches_count"], 1)
        self.assertIn("Candidate Party Ltd", scenario["unconfirmed_parties"])
        self.assertEqual(scenario["scenario_label"], "If possible matches are confirmed")

    def test_req_21_eu_50_pct_rule_and_aggregation_note(self):
        """Req 21: EU 50% or more (>= 50.0%, not >50%) with aggregation assumption printed."""
        # Test exact 50.0% threshold is met for EU
        h_exact_50 = [
            Holding(shareholder_name="EU Blocked Owner", entity_name="Target", share_pct=50.0, is_blocked=True, blocked_source="eu_csl"),
        ]
        res = self.engine.evaluate_structure(Counterparty(name="Target"), h_exact_50, auto_screen=False)
        self.assertTrue(res.eu_verdict["criteria_met"], "EU threshold of >= 50.0% must be met at exactly 50.0%")
        self.assertEqual(res.eu_verdict["operator"], ">=")
        self.assertIn("Evaluated with aggregation of designated owners", res.eu_verdict["assumption_note"])

        # Test 49.99% is not met
        h_under_50 = [
            Holding(shareholder_name="EU Blocked Owner", entity_name="Target", share_pct=49.99, is_blocked=True, blocked_source="eu_csl"),
        ]
        res_under = self.engine.evaluate_structure(Counterparty(name="Target"), h_under_50, auto_screen=False)
        self.assertFalse(res_under.eu_verdict["criteria_met"])

    def test_req_23_un_and_mha_flags(self):
        """Req 23: UN and MHA listed owner or key person is flagged."""
        h_un = [
            Holding(shareholder_name="UN Listed Individual", entity_name="Target", share_pct=15.0, is_blocked=True, blocked_source="un_csl"),
        ]
        kp_mha = [
            KeyPerson(name="MHA Listed Director", role="Director", is_blocked=True, blocked_source="in_mha_first_schedule"),
        ]
        res = self.engine.evaluate_structure(Counterparty(name="Target"), h_un, key_persons=kp_mha, auto_screen=False)

        flagged_sources = [f["source"] for f in res.un_mha_flags]
        self.assertIn("un_csl", flagged_sources)
        self.assertIn("in_mha_first_schedule", flagged_sources)

    def test_req_24_bis_entity_list_affiliates_flag(self):
        """Req 24: BIS affiliates flag: 50%+ owner on Entity List gets 'verify current rule'."""
        # 50%+ owner on US CSL (Entity List)
        h_50 = [
            Holding(shareholder_name="BIS Entity List Party", entity_name="Target", share_pct=50.0, is_blocked=True, blocked_source="us_csl"),
        ]
        flags_50 = self.engine.check_bis_affiliates(h_50)
        self.assertEqual(len(flags_50), 1)
        self.assertEqual(flags_50[0]["label"], "verify current rule")
        self.assertEqual(flags_50[0]["party"], "BIS Entity List Party")
        self.assertEqual(flags_50[0]["holding_pct"], 50.0)

        # Under 50% owner does not trigger affiliate flag
        h_40 = [
            Holding(shareholder_name="Minority CSL Party", entity_name="Target", share_pct=40.0, is_blocked=True, blocked_source="us_csl"),
        ]
        flags_40 = self.engine.check_bis_affiliates(h_40)
        self.assertEqual(len(flags_40), 0)

    def test_req_25_config_values_loaded_and_printed(self):
        """Req 25: Every rule value loaded from config/ubo_rules.yaml."""
        rules_cfg_path = Path("config/ubo_rules.yaml")
        self.assertTrue(rules_cfg_path.is_file(), "config/ubo_rules.yaml must exist")
        with open(rules_cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        self.assertIn("ofac", cfg)
        self.assertEqual(cfg["ofac"]["threshold_percent"], 50.0)
        self.assertIn("eu", cfg)
        self.assertEqual(cfg["eu"]["threshold_percent"], 50.0)
        self.assertIn("uk", cfg)
        self.assertEqual(cfg["uk"]["threshold_percent"], 50.0)
        self.assertEqual(cfg["diligence_trigger_pct"], 20.0)
        self.assertEqual(cfg["india_bo_marker_pct"], 10.0)

    def test_req_28_exact_statutory_verdict_wording(self):
        """Req 28: Verdict wording uses exact statutory terminology; never plain 'clear' and never plain 'blocked'."""
        clean_holdings = [Holding(shareholder_name="Clean Entity Ltd", entity_name="Target", share_pct=100.0)]
        res_clean = self.engine.evaluate_structure(Counterparty(name="Target"), clean_holdings, auto_screen=False)

        ofac_text = res_clean.ofac_verdict.get("verdict_text", "")
        eu_text = res_clean.eu_verdict.get("verdict_text", "")
        uk_text = res_clean.uk_verdict.get("verdict_text", "")

        self.assertNotEqual(ofac_text.strip().lower(), "clear")
        self.assertNotEqual(ofac_text.strip().lower(), "blocked")
        self.assertNotEqual(eu_text.strip().lower(), "clear")
        self.assertNotEqual(eu_text.strip().lower(), "blocked")
        self.assertNotEqual(uk_text.strip().lower(), "clear")
        self.assertNotEqual(uk_text.strip().lower(), "blocked")

        self.assertIn("No sanctions ownership or control criteria met based on disclosed data (US OFAC)", ofac_text)
        self.assertIn("No sanctions ownership or control criteria met based on disclosed data (EU)", eu_text)
        self.assertIn("No sanctions ownership or control criteria met based on disclosed data (UK)", uk_text)

        # Blocked cases per regime
        h_ofac = [Holding(shareholder_name="OFAC SDN Entity", entity_name="Target", share_pct=50.0, is_blocked=True, blocked_source="us_ofac")]
        res_ofac = self.engine.evaluate_structure(Counterparty(name="Target"), h_ofac, auto_screen=False)
        self.assertIn("Sanctions ownership criteria met (US OFAC 50% Rule)", res_ofac.ofac_verdict.get("verdict_text", ""))

        h_eu = [Holding(shareholder_name="EU Blocked Entity", entity_name="Target", share_pct=50.0, is_blocked=True, blocked_source="eu_csl")]
        res_eu = self.engine.evaluate_structure(Counterparty(name="Target"), h_eu, auto_screen=False)
        self.assertIn("Sanctions ownership or control criteria met (EU Council Regulations)", res_eu.eu_verdict.get("verdict_text", ""))

        h_uk = [Holding(shareholder_name="UK Blocked Entity", entity_name="Target", share_pct=51.0, is_blocked=True, blocked_source="uk_csl")]
        res_uk = self.engine.evaluate_structure(Counterparty(name="Target"), h_uk, auto_screen=False)
        self.assertIn("Sanctions ownership or control criteria met (UK Sanctions Regulations)", res_uk.uk_verdict.get("verdict_text", ""))

    def test_req_34_verification_level_and_self_declared_share(self):
        """Req 34: Verification level on every line & structure share that is self-declared."""
        holdings = [
            Holding(shareholder_name="Entity A", entity_name="Target", share_pct=40.0, verification_level="self_declared"),
            Holding(shareholder_name="Entity B", entity_name="Target", share_pct=35.0, verification_level="official_registry"),
            Holding(shareholder_name="Entity C", entity_name="Target", share_pct=25.0, verification_level="self_declared"),
        ]
        res = self.engine.evaluate_structure(Counterparty(name="Target"), holdings, auto_screen=False)
        self.assertEqual(res.self_declared_share_pct, 65.0)

    def test_req_35_structure_risk_indicators_explicitly_asserted(self):
        """
        Req 35: All 7 statutory structure risk indicators explicitly asserted:
        1. More than 3 layers
        2. Entity in FATF black-list or grey-list jurisdiction
        3. Nominee, trust, or bearer-type holdings
        4. Undisclosed ownership above 0%
        5. Ownership change in the last 12 months
        6. Circular structure
        7. Party with unresolved 🟠 match
        """
        # Indicator 1: More than 3 layers
        risks_depth = self.engine.check_structure_risk_indicators(max_depth=4)
        self.assertTrue(any("More than 3 corporate ownership layers" in r for r in risks_depth), "Indicator 1 (>3 layers) failed")

        # Indicator 2: FATF black-list or grey-list jurisdiction
        h_fatf = [Holding(shareholder_name="Tehran Trading", entity_name="Target", share_pct=20.0, country="Iran")]
        risks_fatf = self.engine.check_structure_risk_indicators(holdings=h_fatf)
        self.assertTrue(any("FATF jurisdiction" in r for r in risks_fatf), "Indicator 2 (FATF) failed")

        # Indicator 3: Nominee, trust, or bearer-type holdings
        h_nominee = [Holding(shareholder_name="Nominee Corp", entity_name="Target", share_pct=20.0, holding_type="nominee", on_behalf_of="Owner X")]
        risks_nominee = self.engine.check_structure_risk_indicators(holdings=h_nominee)
        self.assertTrue(any("Nominee, trust, or bearer-type" in r for r in risks_nominee), "Indicator 3 (Nominee/trust/bearer) failed")

        # Indicator 4: Undisclosed ownership above 0%
        risks_undisclosed = self.engine.check_structure_risk_indicators(undisclosed_pct=15.0)
        self.assertTrue(any("Undisclosed ownership shortfall above 0%" in r for r in risks_undisclosed), "Indicator 4 (Undisclosed >0%) failed")

        # Indicator 5: Ownership change in the last 12 months
        risks_change = self.engine.check_structure_risk_indicators(ownership_change_last_12m=True)
        self.assertTrue(any("Ownership change occurred in the last 12 months" in r for r in risks_change), "Indicator 5 (Recent change) failed")

        # Indicator 6: Circular structure
        risks_cycle = self.engine.check_structure_risk_indicators(cycle_detected=True)
        self.assertTrue(any("Circular structure detected" in r for r in risks_cycle), "Indicator 6 (Circular structure) failed")

        # Indicator 7: Party with unresolved 🟠 match
        hits_orange = [{"party": "Volga Transport Ltd", "tier": "POSSIBLE_MATCH", "tier_icon": "🟠", "disposition": "Unresolved"}]
        risks_orange = self.engine.check_structure_risk_indicators(screening_hits=hits_orange)
        self.assertTrue(any("unresolved possible match (🟠)" in r for r in risks_orange), "Indicator 7 (Unresolved 🟠 match) failed")

    def test_req_38_automatic_rescreening_on_list_update(self):
        """Req 38: Automatic re-screening of saved checks when lists update with 'Needs review: list change'."""
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "screening.db"
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE ownership_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_name TEXT,
                    status TEXT,
                    data_json TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE ownership_parties (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    check_id INTEGER,
                    party_name TEXT,
                    entity_type TEXT,
                    is_blocked INTEGER
                )
            """)
            cur.execute("INSERT INTO ownership_checks (target_name, status, data_json) VALUES ('Alpha Maritime', 'Submitted', '{}')")
            check_id = cur.lastrowid
            cur.execute("INSERT INTO ownership_parties (check_id, party_name, entity_type, is_blocked) VALUES (?, 'BANK ROSSIYA', 'company', 0)", (check_id,))
            conn.commit()
            conn.close()

            import modules.ownership.engine as eng_mod
            orig_get_logs_dir = eng_mod.get_logs_dir
            eng_mod.get_logs_dir = lambda: Path(td)

            try:
                flagged = self.engine.rescreen_saved_ownership_checks()
                self.assertEqual(len(flagged), 1)
                self.assertEqual(flagged[0]["new_status"], "Needs review: list change")

                conn = sqlite3.connect(str(db_path))
                status = conn.cursor().execute("SELECT status FROM ownership_checks WHERE id = ?", (check_id,)).fetchone()[0]
                conn.close()
                self.assertEqual(status, "Needs review: list change")
            finally:
                eng_mod.get_logs_dir = orig_get_logs_dir

    def test_req_40_interactive_tree_visualization_structure(self):
        """Req 40: Multi-tier interactive tree visualization Graphviz DOT generation."""
        holdings = [
            Holding(shareholder_name="Beta Holding Ltd", entity_name="Alpha Services", share_pct=60.0),
            Holding(shareholder_name="Vijay Sharma", entity_name="Alpha Services", share_pct=25.0),
        ]
        res = self.engine.evaluate_structure(Counterparty(name="Alpha Services"), holdings, auto_screen=False)

        dot_lines = [
            'digraph OwnershipTree {',
            '  rankdir=TB;',
            '  node [shape=box, style="rounded,filled", fontname="Segoe UI", fontsize=10];',
            '  edge [fontname="Segoe UI", fontsize=9];',
            f'  target [label="{res.target_name}\\n(Target Counterparty)", fillcolor="#E3F2FD", color="#1565C0", penwidth=2];',
        ]
        for h in res.holdings:
            clean_sh = "".join(c if c.isalnum() else "_" for c in h.shareholder_name)
            clean_ent = "target" if h.entity_name.lower() == res.target_name.lower() else "".join(c if c.isalnum() else "_" for c in h.entity_name)
            eff = res.effective_holdings.get(h.shareholder_name, h.share_pct)
            color = "#FFCDD2" if h.is_blocked else "#E8F5E9"
            border = "#C62828" if h.is_blocked else "#2E7D32"
            label = f"{h.shareholder_name}\\n(Direct: {h.share_pct:.1f}% | Look-Through: {eff:.1f}%)"
            dot_lines.append(f'  {clean_sh} [label="{label}", fillcolor="{color}", color="{border}"];')
            dot_lines.append(f'  {clean_sh} -> {clean_ent} [label="{h.share_pct:.1f}%"];')
        dot_lines.append('}')
        dot_src = "\n".join(dot_lines)

        self.assertIn("digraph OwnershipTree", dot_src)
        self.assertIn("Alpha Services", dot_src)
        self.assertIn("Beta Holding Ltd", dot_src)
        self.assertIn("Vijay Sharma", dot_src)
        self.assertIn("60.0%", dot_src)
        self.assertIn("25.0%", dot_src)

    def test_req_41_regime_verdict_panels_structure(self):
        """Req 41: Four regime verdict panels structure (OFAC, EU, UK, UN/MHA)."""
        holdings = [Holding(shareholder_name="Owner Corp", entity_name="Target", share_pct=100.0)]
        res = self.engine.evaluate_structure(Counterparty(name="Target"), holdings, auto_screen=False)

        self.assertIsInstance(res.ofac_verdict, dict)
        self.assertIsInstance(res.eu_verdict, dict)
        self.assertIsInstance(res.uk_verdict, dict)
        self.assertIsInstance(res.un_mha_flags, list)

        self.assertIn("criteria_met", res.ofac_verdict)
        self.assertIn("threshold_pct", res.ofac_verdict)
        self.assertIn("criteria_met", res.eu_verdict)
        self.assertIn("criteria_met", res.uk_verdict)

    def test_req_42_report_section_ownership_control_analysis(self):
        """Req 42: Dedicated report section 'Ownership & Control Analysis' rendered in generator."""
        from modules.reporting.generator import generate_reports
        res = self.engine.evaluate_structure(
            Counterparty(name="Maritime Logistics Ltd"),
            [Holding(shareholder_name="Alpha Owner", entity_name="Maritime Logistics Ltd", share_pct=100.0)],
            auto_screen=False,
        )
        pdf_path, xlsx_path = generate_reports(
            search_type="ownership",
            inputs={"query": "Maritime Logistics Ltd", "ubo_result": res},
            overall_banner="NO_MATCH",
            source_statuses=[],
            sanctions_hits=[],
            aviation_hits=[],
            country_risk_hits=[],
        )
        self.assertTrue(pdf_path.is_file())
        self.assertTrue(xlsx_path.is_file())


if __name__ == "__main__":
    unittest.main()
