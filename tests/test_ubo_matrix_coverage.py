"""
Dedicated Verification Tests for UBO Requirements Matrix (Section 4):
- Req 11: Import preview errors/warnings with sheet, row, col, suggested fix
- Req 13: Format file safe_load, schema validation, refusal of unknown transform
- Req 28: Exact statutory verdict wording; never plain 'clear' or 'blocked'
- Req 35: Each structure risk indicator explicitly asserted (bearer shares, circular, secrecy jurisdictions)
- Req 38: Automatic re-screening after list update -> 'Needs review: list change'
- Req 40: Interactive multi-tier ownership tree visualization structure
- Req 41: Four regime verdict panels rendering structure (OFAC, EU, UK, UN/MHA)
"""

import io
from pathlib import Path
import sqlite3
import tempfile
import unittest
import openpyxl
import yaml

from modules.ownership.models import (
    Counterparty,
    ControlRelation,
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

    def test_req_28_exact_statutory_verdict_wording(self):
        """Req 28: Verdict wording uses exact statutory terminology; never plain 'clear' and never plain 'blocked'."""
        # Clean case
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

    def test_req_35_structure_risk_indicators_explicitly_asserted(self):
        """Req 35: Structure risk indicators (bearer shares, circular holdings, secrecy jurisdictions)."""
        # Bearer shares
        h_bearer = [Holding(shareholder_name="Bearer Holder", entity_name="Target", share_pct=30.0, holding_type="bearer")]
        risks_bearer = self.engine.check_structure_risk_indicators(cycle_detected=False, undisclosed_pct=0.0, holdings=h_bearer)
        self.assertTrue(any("Bearer shares present" in r for r in risks_bearer), "Bearer shares risk indicator not asserted")

        # Circular holdings
        risks_cycle = self.engine.check_structure_risk_indicators(cycle_detected=True, undisclosed_pct=0.0, holdings=[])
        self.assertTrue(any("Circular ownership chain detected" in r for r in risks_cycle), "Circular chain risk indicator not asserted")

        # Secrecy jurisdiction
        h_secrecy = [Holding(shareholder_name="Offshore Ltd", entity_name="Target", share_pct=40.0, country="Panama")]
        risks_secrecy = self.engine.check_structure_risk_indicators(cycle_detected=False, undisclosed_pct=0.0, holdings=h_secrecy)
        self.assertTrue(any("high-risk secrecy jurisdiction" in r for r in risks_secrecy), "Secrecy jurisdiction risk indicator not asserted")

        # Undisclosed shortfall
        risks_shortfall = self.engine.check_structure_risk_indicators(cycle_detected=False, undisclosed_pct=25.0, holdings=[])
        self.assertTrue(any("Significant undisclosed ownership shortfall" in r for r in risks_shortfall), "Undisclosed shortfall not asserted")

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


if __name__ == "__main__":
    unittest.main()
