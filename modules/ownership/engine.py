"""
Beneficial Ownership & Control (UBO) Screening Engine (T11 Part E).
Implements multilateral sanctions aggregation and control rules:
  - US OFAC 50% Rule (FAQs 399, 401 Examples 1-3)
  - EU 50% Rule & Control Criteria
  - UK Sanctions Regulations Ownership & Control Conditions
  - Parallel Economic Look-Through calculation
  - Four-Eyes review disposition logging
  - 100% offline; zero external network lookups
"""

from collections import defaultdict
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sqlite3
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

from modules.common.paths import get_logs_dir
from modules.ownership.models import FourEyesReview, OwnershipNode, UBOResult
from modules.screening.tiering import screen_query_all_lists, TIER_POTENTIAL_MATCH

logger = logging.getLogger(__name__)

UBO_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "ubo_rules.yaml"


class UBOEngine:
    """Evaluates corporate structures against multilateral sanctions ownership and control rules."""

    def __init__(self, config_path: Optional[Path] = None):
        cfg_file = config_path or UBO_CONFIG_PATH
        if cfg_file.exists():
            with open(cfg_file, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f) or {}
        else:
            self.config = {}

    def screen_node(self, node: OwnershipNode) -> OwnershipNode:
        """Screen a single ownership node against local offline sanctions lists."""
        if node.user_override == "BLOCKED":
            node.is_blocked = True
            node.blocked_source = "user_override"
            return node
        elif node.user_override == "CLEAR":
            node.is_blocked = False
            node.blocked_source = ""
            return node

        # Execute local offline screening
        try:
            results = screen_query_all_lists(
                query=node.name,
                query_type=node.entity_type,
            )
            # Check US OFAC
            ofac_hit = results.get("us_ofac", {}).get("best_hit")
            eu_hit = results.get("eu_csl", {}).get("best_hit")
            uk_hit = results.get("uk_csl", {}).get("best_hit")
            un_hit = results.get("un_csl", {}).get("best_hit")

            blocked_sources = []
            top_hit = None

            for src_name, hit_dict in [("us_ofac", ofac_hit), ("eu_csl", eu_hit), ("uk_csl", uk_hit), ("un_csl", un_hit)]:
                if hit_dict and hit_dict.get("tier") == TIER_POTENTIAL_MATCH:
                    blocked_sources.append(src_name)
                    if not top_hit:
                        top_hit = hit_dict

            if blocked_sources:
                node.is_blocked = True
                node.blocked_source = "; ".join(blocked_sources)
                node.screening_hit = top_hit
            else:
                node.is_blocked = False
                node.blocked_source = ""
        except Exception as exc:
            logger.warning("Error screening node '%s': %s", node.name, exc)

        return node

    def evaluate_ownership(
        self,
        target_name: str,
        nodes: List[OwnershipNode],
        auto_screen: bool = True,
        disposition: Optional[FourEyesReview] = None,
    ) -> UBOResult:
        """
        Evaluate full ownership tree for target_name against OFAC, EU, and UK rules.
        """
        t0 = time.perf_counter()
        target_clean = target_name.strip()

        # Step 1: Screen nodes if required
        if auto_screen:
            for node in nodes:
                self.screen_node(node)

        # Build parent-child relationships
        # Immediate parents: parent_name == "" or parent_name == target_name
        children_by_parent: Dict[str, List[OwnershipNode]] = defaultdict(list)
        node_by_name: Dict[str, OwnershipNode] = {}

        for n in nodes:
            node_by_name[n.name.lower()] = n
            p = n.parent_name.strip().lower()
            if not p or p == target_clean.lower():
                children_by_parent["target"].append(n)
            else:
                children_by_parent[p].append(n)

        # ---------------------------------------------------------------------
        # 1. OFAC 50% Rule Evaluation (FAQs 399, 401 Examples 1-3)
        # ---------------------------------------------------------------------
        # Determine blocked status of intermediate companies bottom-up / top-down
        # An entity is blocked under OFAC if owned >= 50% in the aggregate by blocked persons.
        # Once an intermediate entity is blocked, its ownership downstream is treated as 100% blocked.
        # If an intermediate entity is < 50% owned by blocked persons, its downstream ownership is NOT blocked (FAQ 401 Ex 2).

        # Helper to compute OFAC blocked status of an intermediate entity
        intermediate_blocked_cache: Dict[str, bool] = {}

        def is_entity_ofac_blocked(entity_name: str, depth: int = 0) -> Tuple[bool, float, List[str]]:
            clean_ent = entity_name.strip().lower()
            if clean_ent in intermediate_blocked_cache:
                return intermediate_blocked_cache[clean_ent], 0.0, []

            node_obj = node_by_name.get(clean_ent)
            # If directly blocked on OFAC
            if node_obj and (node_obj.is_blocked and "us_ofac" in node_obj.blocked_source.lower() or node_obj.blocked_source == "user_override"):
                intermediate_blocked_cache[clean_ent] = True
                return True, 100.0, [f"{entity_name} (directly designated)"]

            if depth > 8:
                return False, 0.0, []

            # Check shareholders of this intermediate entity
            shareholders = children_by_parent.get(clean_ent, [])
            agg_pct = 0.0
            reasons = []

            for sh in shareholders:
                sh_blocked = False
                # Is shareholder directly designated?
                if sh.is_blocked and ("us_ofac" in sh.blocked_source.lower() or sh.blocked_source == "user_override"):
                    sh_blocked = True
                    reasons.append(f"{sh.name} ({sh.ownership_pct}% in {entity_name}) is directly designated")
                else:
                    # Check if shareholder is itself a blocked entity
                    p_blocked, _, sub_reasons = is_entity_ofac_blocked(sh.name, depth + 1)
                    if p_blocked:
                        sh_blocked = True
                        reasons.append(f"{sh.name} ({sh.ownership_pct}% in {entity_name}) is >=50% blocked entity")

                if sh_blocked:
                    agg_pct += sh.ownership_pct

            is_blocked = (agg_pct >= 50.0)
            intermediate_blocked_cache[clean_ent] = is_blocked
            return is_blocked, agg_pct, reasons

        # Now evaluate Target Company for OFAC 50%
        ofac_aggregate_pct = 0.0
        ofac_contributors = []
        ofac_path_traces = []

        direct_shareholders = children_by_parent.get("target", [])

        for d_sh in direct_shareholders:
            is_d_blocked = False
            # Direct shareholder is designated
            if d_sh.is_blocked and ("us_ofac" in d_sh.blocked_source.lower() or d_sh.blocked_source == "user_override"):
                is_d_blocked = True
                ofac_contributors.append({
                    "name": d_sh.name,
                    "direct_pct": d_sh.ownership_pct,
                    "reason": "Directly designated on OFAC list",
                })
                ofac_path_traces.append(f"{d_sh.name} [BLOCKED] owns {d_sh.ownership_pct}% directly in {target_clean}")
                ofac_aggregate_pct += d_sh.ownership_pct
            else:
                # Is direct shareholder an entity owned >=50% by blocked persons?
                p_blocked, p_agg, p_reasons = is_entity_ofac_blocked(d_sh.name, depth=1)
                if p_blocked:
                    is_d_blocked = True
                    ofac_contributors.append({
                        "name": d_sh.name,
                        "direct_pct": d_sh.ownership_pct,
                        "reason": f"Intermediate entity is >=50% owned by blocked persons ({'; '.join(p_reasons)})",
                    })
                    ofac_path_traces.append(f"{d_sh.name} (>=50% blocked entity) owns {d_sh.ownership_pct}% in {target_clean}")
                    ofac_aggregate_pct += d_sh.ownership_pct

        ofac_blocked = (ofac_aggregate_pct >= 50.0)

        # ---------------------------------------------------------------------
        # 2. EU Ownership & Control Evaluation
        # ---------------------------------------------------------------------
        # Proprietary ownership > 50%
        # Control criteria: board appointment rights, majority of board, decisive influence
        eu_aggregate_pct = 0.0
        eu_ownership_blocked = False
        eu_control_blocked = False
        eu_reasons = []

        for d_sh in direct_shareholders:
            if d_sh.is_blocked and ("eu_csl" in d_sh.blocked_source.lower() or d_sh.blocked_source == "user_override"):
                eu_aggregate_pct += d_sh.ownership_pct
                eu_reasons.append(f"{d_sh.name} is designated on EU list ({d_sh.ownership_pct}% direct)")

        if eu_aggregate_pct > 50.0:
            eu_ownership_blocked = True

        # Check EU Control
        for n in nodes:
            if n.is_blocked and ("eu_csl" in n.blocked_source.lower() or n.blocked_source == "user_override"):
                if n.has_appointment_power:
                    eu_control_blocked = True
                    eu_reasons.append(f"{n.name} (EU designated) exercises appointment power over board / management")
                if n.is_board_member and n.ownership_pct >= 50.0:
                    eu_control_blocked = True
                    eu_reasons.append(f"{n.name} (EU designated) holds board representation with dominant stake")

        eu_blocked = eu_ownership_blocked or eu_control_blocked

        # ---------------------------------------------------------------------
        # 3. UK Ownership & Control Evaluation (OFSI)
        # ---------------------------------------------------------------------
        # Condition 1: > 50% shares or voting rights
        # Condition 2: Right to appoint or remove majority of board of directors
        # Condition 3: Dominant influence / conduct of affairs per wishes
        uk_aggregate_pct = 0.0
        uk_condition_1 = False
        uk_condition_2 = False
        uk_condition_3 = False
        uk_reasons = []

        for d_sh in direct_shareholders:
            if d_sh.is_blocked and ("uk_csl" in d_sh.blocked_source.lower() or d_sh.blocked_source == "user_override"):
                uk_aggregate_pct += d_sh.ownership_pct
                uk_reasons.append(f"{d_sh.name} is designated under UK sanctions ({d_sh.ownership_pct}% shares)")

        if uk_aggregate_pct > 50.0:
            uk_condition_1 = True

        # Condition 2: Board appointment or majority board
        total_board_members = sum(1 for n in nodes if n.is_board_member)
        blocked_board_members = sum(1 for n in nodes if n.is_board_member and n.is_blocked and ("uk_csl" in n.blocked_source.lower() or n.blocked_source == "user_override"))

        for n in nodes:
            if n.is_blocked and ("uk_csl" in n.blocked_source.lower() or n.blocked_source == "user_override"):
                if n.has_appointment_power:
                    uk_condition_2 = True
                    uk_reasons.append(f"{n.name} (UK designated) holds authority to appoint or remove majority of board")

        if total_board_members > 0 and (blocked_board_members / total_board_members) > 0.50:
            uk_condition_2 = True
            uk_reasons.append(f"UK designated persons hold majority of board ({blocked_board_members}/{total_board_members} directors)")

        uk_blocked = uk_condition_1 or uk_condition_2 or uk_condition_3

        # ---------------------------------------------------------------------
        # 4. Economic Look-Through Calculation
        # ---------------------------------------------------------------------
        # Pure mathematical multiplication along corporate tiers down to each UBO
        look_through_by_name: Dict[str, float] = defaultdict(float)

        def compute_look_through(entity_name: str, cumulative_multiplier: float, depth: int = 0):
            if depth > 8:
                return
            shs = children_by_parent.get(entity_name.lower(), [])
            if not shs:
                # Leaf node / UBO
                look_through_by_name[entity_name] += cumulative_multiplier
                return

            for sh in shs:
                branch_mult = cumulative_multiplier * (sh.ownership_pct / 100.0)
                sh.effective_look_through_pct = round(branch_mult * 100.0, 4)
                compute_look_through(sh.name, branch_mult, depth + 1)

        # Run look-through from target
        direct_shs = children_by_parent.get("target", [])
        for d in direct_shs:
            d_mult = (d.ownership_pct / 100.0)
            d.effective_look_through_pct = round(d.ownership_pct, 4)
            children = children_by_parent.get(d.name.lower(), [])
            if not children:
                look_through_by_name[d.name] += d_mult
            else:
                for c in children:
                    c_mult = d_mult * (c.ownership_pct / 100.0)
                    c.effective_look_through_pct = round(c_mult * 100.0, 4)
                    compute_look_through(c.name, c_mult, depth=1)

        # Build comparison summary table
        look_through_summary = []
        for n in nodes:
            look_through_summary.append({
                "name": n.name,
                "type": n.entity_type,
                "country": n.country,
                "direct_pct": n.ownership_pct,
                "effective_look_through_pct": n.effective_look_through_pct,
                "is_blocked": n.is_blocked,
                "blocked_source": n.blocked_source,
                "board_member": n.is_board_member,
            })

        duration_ms = (time.perf_counter() - t0) * 1000.0

        res = UBOResult(
            target_name=target_clean,
            nodes=nodes,
            ofac_blocked=ofac_blocked,
            ofac_aggregate_pct=round(ofac_aggregate_pct, 2),
            ofac_blocked_contributors=ofac_contributors,
            ofac_path_traces=ofac_path_traces,
            eu_blocked=eu_blocked,
            eu_ownership_blocked=eu_ownership_blocked,
            eu_control_blocked=eu_control_blocked,
            eu_reasons=eu_reasons,
            uk_blocked=uk_blocked,
            uk_condition_1_shares=uk_condition_1,
            uk_condition_2_board=uk_condition_2,
            uk_condition_3_conduct=uk_condition_3,
            uk_reasons=uk_reasons,
            look_through_summary=look_through_summary,
            disposition=disposition or FourEyesReview(),
            execution_time_ms=round(duration_ms, 2),
        )

        # Audit log into SQLite
        self.log_ubo_check(res)

        return res

    def log_ubo_check(self, res: UBOResult) -> None:
        """Write UBO screening result to SQLite audit trail with mode='ownership'."""
        db_path = get_logs_dir() / "screening.db"
        if not db_path.exists():
            return

        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            overall_verdict = "BLOCKED" if (res.ofac_blocked or res.eu_blocked or res.uk_blocked) else "CLEAR"
            details = {
                "target": res.target_name,
                "nodes_count": len(res.nodes),
                "ofac_blocked": res.ofac_blocked,
                "ofac_pct": res.ofac_aggregate_pct,
                "eu_blocked": res.eu_blocked,
                "uk_blocked": res.uk_blocked,
                "disposition_status": res.disposition.status,
                "preparer": res.disposition.preparer,
                "reviewer": res.disposition.reviewer,
            }

            cursor.execute("""
                INSERT INTO screening_logs (
                    timestamp, mode, search_type, inputs, result, duration_ms, comment
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now(timezone.utc).isoformat(),
                "ownership",
                "corporate_structure",
                res.target_name,
                overall_verdict,
                int(res.execution_time_ms),
                json.dumps(details),
            ))
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.warning("Could not log UBO check to screening_logs: %s", exc)
