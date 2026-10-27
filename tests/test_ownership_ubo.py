"""
Unit Tests for Beneficial Ownership & Control (UBO) Engine (T11 Part E).
Verifies:
- OFAC FAQ 399: Direct 50% ownership by blocked person blocks target entity.
- OFAC FAQ 401 Example 1: Multi-tier 50% blocked intermediate subsidiary pass-through.
- OFAC FAQ 401 Example 2: Intermediate entity <50% blocked does NOT pass through.
- OFAC FAQ 401 Example 3: Aggregation of distinct blocked persons (25% + 25% = 50%).
- UK Condition 2: Board appointment power and majority board control.
- EU Control: Decisive appointment authority.
- Parallel Economic Look-Through calculation.
- Four-eyes workflow and SQLite audit log (mode='ownership').
- Zero external socket / network egress during evaluation.
"""

from pathlib import Path
import socket
import sqlite3
import unittest
from unittest.mock import patch

from modules.common.paths import get_logs_dir
from modules.ownership.models import FourEyesReview, OwnershipNode, UBOResult
from modules.ownership.engine import UBOEngine
from modules.ownership.importer import parse_ownership_table


class TestOwnershipUBO(unittest.TestCase):
    """Test suite for UBO rules engine and sanctions ownership aggregation."""

    def setUp(self):
        self.engine = UBOEngine()

    def test_01_ofac_faq_399_direct_50_pct(self):
        """
        OFAC FAQ 399:
        An entity that is 50% or more owned by a blocked person is itself blocked.
        Target X has:
          - Blocked Person A: 50.0% direct ownership
          - Unblocked Co: 50.0% direct ownership
        Result: Target X is BLOCKED under OFAC 50% rule.
        """
        nodes = [
            OwnershipNode(name="Blocked Person A", ownership_pct=50.0, user_override="BLOCKED", entity_type="person"),
            OwnershipNode(name="Unblocked Co", ownership_pct=50.0, user_override="CLEAR", entity_type="company"),
        ]
        res = self.engine.evaluate_ownership("Target Enterprise Inc", nodes, auto_screen=False)
        self.assertTrue(res.ofac_blocked)
        self.assertEqual(res.ofac_aggregate_pct, 50.0)
        self.assertEqual(len(res.ofac_blocked_contributors), 1)
        self.assertIn("Blocked Person A", res.ofac_path_traces[0])

    def test_02_ofac_faq_401_example_1_multi_tier_blocked_pass_through(self):
        """
        OFAC FAQ 401 Example 1:
        Blocked Person X owns 50% of Entity A.
        Entity A owns 50% of Entity B.
        Determination:
          - Entity A is blocked (50% owned by X).
          - Entity B is blocked (50% owned by Entity A, which is a blocked person).
        """
        nodes = [
            # Direct shareholder in Target (Entity B)
            OwnershipNode(name="Entity A", ownership_pct=50.0, entity_type="company"),
            OwnershipNode(name="Clean Minority Partner", ownership_pct=50.0, user_override="CLEAR", entity_type="company"),
            # Shareholders in Entity A
            OwnershipNode(name="Blocked Person X", ownership_pct=50.0, parent_name="Entity A", user_override="BLOCKED", entity_type="person"),
            OwnershipNode(name="Unblocked Investor", ownership_pct=50.0, parent_name="Entity A", user_override="CLEAR", entity_type="person"),
        ]
        res = self.engine.evaluate_ownership("Entity B", nodes, auto_screen=False)
        self.assertTrue(res.ofac_blocked)
        self.assertEqual(res.ofac_aggregate_pct, 50.0)
        self.assertIn("Entity A", res.ofac_path_traces[0])

    def test_03_ofac_faq_401_example_2_non_blocked_intermediate(self):
        """
        OFAC FAQ 401 Example 2:
        Blocked Person X owns 40% of Entity A (A is NOT blocked).
        Entity A owns 100% of Entity B.
        Determination:
          - Entity A is NOT blocked under OFAC 50% rule (<50% owned by X).
          - Entity B is NOT blocked by virtue of X under OFAC 50% rule, because Entity A is not blocked.
          - Economic look-through is 40.0%, but OFAC aggregate blocked is 0.0%!
        """
        nodes = [
            OwnershipNode(name="Entity A", ownership_pct=100.0, entity_type="company"),
            OwnershipNode(name="Blocked Person X", ownership_pct=40.0, parent_name="Entity A", user_override="BLOCKED", entity_type="person"),
            OwnershipNode(name="Independent Partner", ownership_pct=60.0, parent_name="Entity A", user_override="CLEAR", entity_type="company"),
        ]
        res = self.engine.evaluate_ownership("Entity B", nodes, auto_screen=False)
        # Crucial: Under OFAC FAQ 401 Example 2, Entity B is NOT blocked!
        self.assertFalse(res.ofac_blocked)
        self.assertEqual(res.ofac_aggregate_pct, 0.0)
        # But economic look-through clearly reflects 40.0%
        x_node = next(n for n in res.nodes if n.name == "Blocked Person X")
        self.assertAlmostEqual(x_node.effective_look_through_pct, 40.0, places=1)

    def test_04_ofac_faq_401_example_3_aggregation_of_blocked_persons(self):
        """
        OFAC FAQ 401 Example 3:
        Blocked Person X owns 25% of Target C.
        Blocked Person Y owns 25% of Target C.
        Clean Partner owns 50% of Target C.
        Determination:
          - Aggregate ownership by blocked persons is 25% + 25% = 50.0%.
          - Target C is BLOCKED under OFAC 50% rule!
        """
        nodes = [
            OwnershipNode(name="Blocked Person X", ownership_pct=25.0, user_override="BLOCKED", entity_type="person"),
            OwnershipNode(name="Blocked Person Y", ownership_pct=25.0, user_override="BLOCKED", entity_type="person"),
            OwnershipNode(name="Clean Partner", ownership_pct=50.0, user_override="CLEAR", entity_type="company"),
        ]
        res = self.engine.evaluate_ownership("Target C", nodes, auto_screen=False)
        self.assertTrue(res.ofac_blocked)
        self.assertEqual(res.ofac_aggregate_pct, 50.0)
        self.assertEqual(len(res.ofac_blocked_contributors), 2)

    def test_05_uk_board_control_and_appointment_power(self):
        """
        UK Ownership and Control (OFSI Condition 2):
        Designated person has <50% shares (e.g. 15%), but holds right to appoint majority of board
        or holds majority of board seats (3 out of 5).
        Result: UK control condition triggered -> uk_blocked is True.
        """
        nodes = [
            OwnershipNode(
                name="UK Designated Oligarch",
                ownership_pct=15.0,
                user_override="BLOCKED",
                entity_type="person",
                is_board_member=True,
                has_appointment_power=True,  # Authority over board composition
            ),
            OwnershipNode(name="Institutional Investor A", ownership_pct=42.5, is_board_member=True, entity_type="company"),
            OwnershipNode(name="Institutional Investor B", ownership_pct=42.5, is_board_member=True, entity_type="company"),
        ]
        res = self.engine.evaluate_ownership("UK Trading Group PLC", nodes, auto_screen=False)
        self.assertTrue(res.uk_blocked)
        self.assertTrue(res.uk_condition_2_board)
        self.assertTrue(any("appoint" in r.lower() for r in res.uk_reasons))

    def test_06_four_eyes_workflow_and_sqlite_audit_logging(self):
        """
        Four-eyes review disposition and audit logging to SQLite screening.db
        with mode='ownership'.
        """
        disposition = FourEyesReview(
            preparer="Analyst A. Sharma",
            reviewer="Senior Compliance Officer J. Miller",
            status="ESCALATED",
            notes="Escalated due to complex 3-tier ownership in BVI and Cyprus.",
        )
        nodes = [
            OwnershipNode(name="Safe Holding Co", ownership_pct=100.0, user_override="CLEAR", entity_type="company")
        ]
        res = self.engine.evaluate_ownership("Maritime Logistics Ltd", nodes, auto_screen=False, disposition=disposition)
        self.assertEqual(res.disposition.status, "ESCALATED")
        self.assertEqual(res.disposition.preparer, "Analyst A. Sharma")

        # Verify audit log in SQLite
        db_path = get_logs_dir() / "screening.db"
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            cur.execute("SELECT mode, inputs, result FROM screening_logs WHERE mode = 'ownership' ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            conn.close()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "ownership")
            self.assertEqual(row[1], "Maritime Logistics Ltd")
            self.assertEqual(row[2], "CLEAR")

    def test_07_zero_network_socket_egress(self):
        """
        Privacy and security check: Ensure zero socket connections are made
        during ownership calculation.
        """
        with patch("socket.socket") as mock_sock:
            mock_sock.side_effect = RuntimeError("Network socket call strictly forbidden during UBO check")
            nodes = [
                OwnershipNode(name="Local Entity 1", ownership_pct=60.0, user_override="CLEAR"),
                OwnershipNode(name="Local Entity 2", ownership_pct=40.0, user_override="CLEAR"),
            ]
            res = self.engine.evaluate_ownership("Zero Network Target", nodes, auto_screen=False)
            self.assertFalse(res.ofac_blocked)

    def test_08_importer_template_parsing(self):
        """Verify Excel template parsing into OwnershipNode instances."""
        template_file = Path("templates") / "ownership_template.xlsx"
        self.assertTrue(template_file.exists(), "Template file must exist")
        nodes, warnings = parse_ownership_table(template_file)
        self.assertGreaterEqual(len(nodes), 4)
        names = [n.name for n in nodes]
        self.assertIn("Alpha Holdings Corp", names)
        self.assertIn("John Doe", names)

    def test_09_auto_screening_with_real_local_records(self):
        """Verify that auto_screen=True uses local sanctions engine to detect real designated entities."""
        nodes = [
            OwnershipNode(name="Sberbank", ownership_pct=51.0, entity_type="company"),
            OwnershipNode(name="Safe Co", ownership_pct=49.0, entity_type="company"),
        ]
        res = self.engine.evaluate_ownership("Venture Target LLC", nodes, auto_screen=True)
        self.assertTrue(res.ofac_blocked)
        sber_node = next(n for n in res.nodes if "Sberbank" in n.name)
        self.assertTrue(sber_node.is_blocked)
        self.assertIn("us_ofac", sber_node.blocked_source.lower())


if __name__ == "__main__":
    unittest.main()
