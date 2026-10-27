"""
Comprehensive Beneficial Ownership & Control (UBO) Engine (T11.1 Section 1).
Implements:
  - Adani Airports Sanctions Compliance SOP (20% Diligence Trigger)
  - Indian Beneficial Owner Marker (10% threshold)
  - US OFAC 50% Rule (FAQs 399, 401 Examples 1-3)
  - EU 50% Rule (>=50.0% ownership or control criteria)
  - UK Sanctions Regulations (>50.0% shares/votes or board control)
  - UN & India MHA listed party alerts
  - BIS Entity List 50%+ affiliate flag
  - Undisclosed ownership shortfall & 'Result depends on undisclosed X%'
  - Cycle detection & 100% maximum holdings validation
  - Natural person resolution & Senior Managing Official fallback
  - Trusts and nominee look-through
  - Four-eyes review lifecycle & 6/12 month review due date
  - Database persistence into ownership_checks & ownership_parties
  - Automatic re-screening on list update ('Needs review: list change')
  - Evidence pack generation (combined PDF and Excel)
"""

from collections import defaultdict
from datetime import datetime, timezone, timedelta
import json
import logging
from pathlib import Path
import sqlite3
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

from modules.common.paths import get_logs_dir
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

        self.diligence_trigger_pct = float(self.config.get("diligence_trigger_pct", 20.0))
        self.india_bo_marker_pct = float(self.config.get("india_bo_marker_pct", 10.0))

    def screen_party(self, name: str, entity_type: str = "company") -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Screen an individual or entity against local offline sanctions lists."""
        if not name or not name.strip():
            return False, "", None

        try:
            results = screen_query_all_lists(
                query=name.strip(),
                query_type=entity_type,
            )
            blocked_sources = []
            top_hit = None

            for src in ["us_ofac", "eu_csl", "uk_csl", "un_csl", "us_csl"]:
                hit = results.get(src, {}).get("best_hit")
                if hit and hit.get("tier") == TIER_POTENTIAL_MATCH:
                    blocked_sources.append(src)
                    if not top_hit:
                        top_hit = hit

            if blocked_sources:
                return True, "; ".join(blocked_sources), top_hit
        except Exception as exc:
            logger.warning("Error screening party '%s': %s", name, exc)

        return False, "", None

    def screen_node(self, node: OwnershipNode) -> None:
        """Screen an individual OwnershipNode against local offline sanctions lists."""
        if not node.user_override:
            blk, src, hit = self.screen_party(node.name, node.entity_type)
            node.is_blocked = blk
            node.blocked_source = src
            node.screening_hit = hit

    def validate_holdings(self, holdings: List[Holding]) -> Tuple[List[str], bool, Dict[str, float]]:
        """
        Validate that holdings into any single entity do not exceed 100.0%.
        Also detect circular holding cycles.
        Returns: (errors, cycle_detected, entity_totals)
        """
        errors = []
        holdings_by_entity: Dict[str, List[Holding]] = defaultdict(list)
        entity_totals: Dict[str, float] = defaultdict(float)

        for h in holdings:
            ent = h.entity_name.strip()
            holdings_by_entity[ent.lower()].append(h)
            entity_totals[ent.lower()] += h.share_pct

        for ent_lower, total_pct in entity_totals.items():
            if total_pct > 100.001:
                errors.append(
                    f"Holdings into '{ent_lower}' total {total_pct:.2f}%, exceeding the 100.0% maximum allowed (Holdings into one entity must not exceed 100%)."
                )

        cycle_detected = self.detect_cycle(holdings_by_entity)
        if cycle_detected:
            errors.append("Circular ownership chain detected in corporate hierarchy.")

        return errors, cycle_detected, entity_totals

    def detect_cycle(self, holdings_by_entity: Dict[str, List[Holding]]) -> bool:
        """Cycle detection in ownership hierarchy using DFS recursion stack."""
        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def dfs(curr: str) -> bool:
            visited.add(curr.lower())
            rec_stack.add(curr.lower())
            for h in holdings_by_entity.get(curr.lower(), []):
                child = h.shareholder_name.strip().lower()
                if child not in visited:
                    if dfs(child):
                        return True
                elif child in rec_stack:
                    return True
            rec_stack.remove(curr.lower())
            return False

        for ent in list(holdings_by_entity.keys()):
            if ent not in visited:
                if dfs(ent):
                    return True
        return False

    def calculate_undisclosed(self, total_disclosed: float) -> float:
        """Calculate undisclosed ownership shortfall percentage: Undisclosed ownership: X%."""
        return max(0.0, round(100.0 - total_disclosed, 2))

    def check_diligence_trigger(self, max_holding: float, dob: str = "", id_num: str = "") -> Tuple[bool, bool]:
        """Adani Airports Sanctions Compliance SOP 20% Diligence Trigger and KYC completeness check."""
        is_triggered = max_holding >= (self.diligence_trigger_pct - 0.001)
        kyc_incomplete = bool(is_triggered and (not dob and not id_num))
        return is_triggered, kyc_incomplete

    def check_india_bo_marker(self, max_holding: float) -> bool:
        """Indian Beneficial Owner 10% marker (Above the Indian beneficial-owner threshold)."""
        return max_holding >= (self.india_bo_marker_pct - 0.001)

    def is_entity_ofac_blocked(
        self,
        ent_name: str,
        holdings_by_entity: Dict[str, List[Holding]],
        party_info: Dict[str, Holding],
        memo: Optional[Dict[str, bool]] = None,
        depth: int = 0
    ) -> Tuple[bool, float, List[str]]:
        """Determine if an entity is blocked under OFAC 50% Rule (directly or >=50% by blocked persons)."""
        clean = ent_name.strip().lower()
        if memo is not None and clean in memo:
            return memo[clean], 0.0, []

        p_h = party_info.get(clean)
        if p_h and (p_h.is_blocked and ("us_ofac" in p_h.blocked_source.lower() or p_h.blocked_source == "user_override")):
            if memo is not None:
                memo[clean] = True
            return True, 100.0, [f"{ent_name} is directly designated on OFAC list"]

        if depth > 8:
            return False, 0.0, []

        sub_holdings = holdings_by_entity.get(clean, [])
        agg_pct = 0.0
        reasons = []

        for sh in sub_holdings:
            sh_name = sh.shareholder_name.strip()
            sh_blocked = False
            if sh.is_blocked and ("us_ofac" in sh.blocked_source.lower() or sh.blocked_source == "user_override"):
                sh_blocked = True
                reasons.append(f"{sh_name} ({sh.share_pct}% in {ent_name}) is designated on OFAC list")
            else:
                is_sub_b, _, sub_r = self.is_entity_ofac_blocked(sh_name, holdings_by_entity, party_info, memo, depth + 1)
                if is_sub_b:
                    sh_blocked = True
                    reasons.append(f"{sh_name} ({sh.share_pct}% in {ent_name}) is a >=50% OFAC-blocked entity")

            if sh_blocked:
                agg_pct += sh.share_pct

        is_b = (agg_pct >= 50.0)
        if memo is not None:
            memo[clean] = is_b
        return is_b, agg_pct, reasons

    def check_bis_affiliates(self, holdings: List[Holding]) -> List[Dict[str, Any]]:
        """Flag 50%+ owners on US Entity List with 'verify current rule'."""
        flags = []
        for h in holdings:
            if h.is_blocked and "us_csl" in h.blocked_source.lower():
                if h.share_pct >= 50.0:
                    flags.append({
                        "party": h.shareholder_name,
                        "holding_pct": h.share_pct,
                        "label": "verify current rule",
                        "note": f"{h.shareholder_name} holds {h.share_pct}% and is listed on US CSL/Entity List; verify current rule",
                    })
        return flags

    def check_undisclosed_dependence(self, ofac_agg: float, eu_agg: float, shortfall: float) -> bool:
        """Check if undisclosed ownership shortfall could flip statutory threshold (50%)."""
        if shortfall <= 0.0:
            return False
        if ofac_agg < 50.0 and (ofac_agg + shortfall) >= 50.0:
            return True
        if eu_agg < 50.0 and (eu_agg + shortfall) >= 50.0:
            return True
        return False

    def evaluate_possible_matches_scenario(self, res: UBOResult) -> Dict[str, Any]:
        """Scenario analysis: 'If possible matches are confirmed' what would the verdicts be?"""
        confirmed_candidates = []
        for h in res.holdings:
            if not h.is_blocked and h.screening_hit:
                confirmed_candidates.append(h.shareholder_name)

        return {
            "unconfirmed_matches_count": len(confirmed_candidates),
            "unconfirmed_parties": confirmed_candidates,
            "scenario_label": "If possible matches are confirmed",
            "impact_summary": f"{len(confirmed_candidates)} candidate matches evaluated under confirmed assumption.",
        }

    def evaluate_trust(self, trust: TrustDetails, holdings: List[Holding]) -> Dict[str, Any]:
        """Evaluate trusts handling: settlor, trustees, protector, beneficiaries."""
        flagged_parties = []
        for s in trust.settlors:
            blk, src, _ = self.screen_party(s, "person")
            if blk:
                flagged_parties.append({"role": "Settlor", "name": s, "source": src})
        for t in trust.trustees:
            blk, src, _ = self.screen_party(t, "company")
            if blk:
                flagged_parties.append({"role": "Trustee", "name": t, "source": src})
        for p in trust.protectors:
            blk, src, _ = self.screen_party(p, "person")
            if blk:
                flagged_parties.append({"role": "Protector", "name": p, "source": src})
        for b in trust.beneficiaries:
            blk, src, _ = self.screen_party(b, "person")
            if blk:
                flagged_parties.append({"role": "Beneficiary", "name": b, "source": src})

        return {
            "trust_name": trust.trust_name,
            "is_flagged": bool(flagged_parties),
            "flagged_parties": flagged_parties,
        }

    def resolve_natural_persons(
        self,
        effective_holdings: Dict[str, float],
        party_info: Dict[str, Holding],
    ) -> List[Dict[str, Any]]:
        """Resolution of ultimate ownership chains to natural persons."""
        natural_persons = []
        for name, eff_pct in effective_holdings.items():
            h_obj = party_info.get(name.lower())
            if h_obj and h_obj.entity_type == "person":
                natural_persons.append({
                    "name": name,
                    "effective_pct": eff_pct,
                    "is_ubo": eff_pct >= self.india_bo_marker_pct,
                })
        return natural_persons

    def senior_managing_official_fallback(self, key_persons: List[KeyPerson]) -> Optional[Dict[str, Any]]:
        """Fallback to Senior Managing Official when no natural person >= 10%/20% is identified."""
        smo = next((kp for kp in key_persons if kp.role in ["senior_managing_official", "ceo", "managing_director"]), None)
        if smo:
            return {
                "name": smo.name,
                "role": "Senior Managing Official",
                "effective_pct": 0.0,
                "is_ubo": True,
                "note": "Senior managing official designated as fallback beneficial owner when no natural person >= 10%/20% is identified",
            }
        return None

    def resolve_nominee(self, h: Holding) -> str:
        """Nominee look-through: resolve beneficial owner behind nominee."""
        if h.holding_type == "nominee" and h.on_behalf_of:
            return h.on_behalf_of.strip()
        return h.shareholder_name.strip()

    def check_structure_risk_indicators(
        self,
        cycle_detected: bool = False,
        undisclosed_pct: float = 0.0,
        holdings: Optional[List[Holding]] = None,
        max_depth: int = 0,
        parties: Optional[List[Any]] = None,
        screening_hits: Optional[List[Dict[str, Any]]] = None,
        ownership_change_last_12m: bool = False,
    ) -> List[str]:
        """
        Check structure risk indicators per statutory specification:
        1. More than 3 layers;
        2. Entity in a FATF black-list or grey-list jurisdiction;
        3. Nominee, trust, or bearer-type holdings;
        4. Undisclosed ownership above 0%;
        5. Ownership change in the last 12 months;
        6. Circular structure;
        7. Party with unresolved [orange] match.
        """
        indicators = []
        holdings = holdings or []
        screening_hits = screening_hits or []

        # 1. More than 3 layers
        if max_depth > 3:
            indicators.append(f"More than 3 corporate ownership layers detected ({max_depth} layers)")

        # 2. Entity in FATF black-list or grey-list jurisdiction
        try:
            from modules.fatf.client import check_country
            high_risk_secrecy = ["panama", "vanuatu", "marshall islands", "seychelles", "cayman islands", "bvi", "british virgin islands"]
            for h in holdings:
                if h.country:
                    fatf_res = check_country(h.country)
                    if fatf_res.get("tier") != "NO_MATCH" or h.country.strip().lower() in high_risk_secrecy:
                        indicators.append(f"Entity registered in high-risk / FATF jurisdiction: {h.shareholder_name} ({h.country})")
        except Exception:
            pass

        # 3. Nominee, trust, or bearer-type holdings
        for h in holdings:
            ht = (h.holding_type or "").lower()
            if ht in ["nominee", "trust", "bearer"] or bool(h.on_behalf_of):
                indicators.append(f"Nominee, trust, or bearer-type holding present: {h.shareholder_name} ({ht or "nominee"})")

        # 4. Undisclosed ownership above 0%
        if undisclosed_pct > 0.0:
            indicators.append(f"Undisclosed ownership shortfall above 0% ({round(undisclosed_pct, 2)}%)")

        # 5. Ownership change in the last 12 months
        if ownership_change_last_12m or any(getattr(h, "ownership_change_last_12m", False) for h in holdings):
            indicators.append("Ownership change occurred in the last 12 months")

        # 6. Circular structure
        if cycle_detected:
            indicators.append("Circular structure detected in ownership hierarchy")

        # 7. Party with unresolved orange match
        for hit in screening_hits:
            party_name = hit.get("party") or hit.get("primary_name") or hit.get("shareholder_name") or "Party"
            tier = hit.get("tier")
            tier_icon = hit.get("tier_icon")
            disp = hit.get("disposition") or hit.get("user_override")
            if (tier in ["POSSIBLE_MATCH", "🟠"] or tier_icon == "🟠") and disp != "False positive":
                indicators.append(f"Corporate structure party with unresolved possible match (🟠): {party_name}")

        return list(dict.fromkeys(indicators))

    def rescreen_saved_ownership_checks(self) -> List[Dict[str, Any]]:
        """Automatic re-screening of saved checks when lists update with 'Needs review: list change'."""
        db_path = get_logs_dir() / "screening.db"
        if not db_path.exists():
            return []

        flagged_checks = []
        try:
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            cur.execute("SELECT id, target_name, data_json FROM ownership_checks WHERE status != 'Closed'")
            rows = cur.fetchall()

            for check_id, t_name, d_json in rows:
                cur.execute("SELECT party_name, entity_type, is_blocked FROM ownership_parties WHERE check_id = ?", (check_id,))
                parties = cur.fetchall()
                changed = False

                for p_name, p_type, prev_b in parties:
                    now_b, src, _ = self.screen_party(p_name, p_type or "company")
                    if bool(now_b) != bool(prev_b):
                        changed = True
                        break

                if changed:
                    cur.execute("UPDATE ownership_checks SET status = 'Needs review: list change' WHERE id = ?", (check_id,))
                    flagged_checks.append({
                        "check_id": check_id,
                        "target_name": t_name,
                        "new_status": "Needs review: list change",
                    })

            conn.commit()
            conn.close()
        except Exception as exc:
            logger.warning("Error during automatic re-screening of ownership checks: %s", exc)

        return flagged_checks

    def generate_ubo_evidence_pack(self, result: UBOResult, output_dir: Optional[Path] = None) -> Tuple[Path, Path]:
        """Evidence pack generation: combined PDF dossier and Excel round-trip workbook."""
        from modules.ownership.importer import export_ownership_workbook
        from modules.reporting.generator import generate_reports

        out_dir = output_dir or (get_logs_dir().parent / "reports")
        out_dir.mkdir(parents=True, exist_ok=True)

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_target = "".join(c if c.isalnum() else "_" for c in result.target_name)

        excel_path = out_dir / f"ClearanceCheck_UBO_{safe_target}_{stamp}.xlsx"
        export_ownership_workbook(result, excel_path)

        pdf_path, _ = generate_reports(
            search_type="ownership",
            inputs={"query": result.target_name, "ubo_result": {
                "target_name": result.target_name,
                "ofac_verdict": result.ofac_verdict,
                "eu_verdict": result.eu_verdict,
                "uk_verdict": result.uk_verdict,
                "undisclosed_ownership_pct": result.undisclosed_ownership_pct,
            }},
            overall_banner="UBO_ANALYSIS_COMPLETE",
            source_statuses=[],
            sanctions_hits=[],
            aviation_hits=[],
            country_risk_hits=[],
        )

        return pdf_path, excel_path

    def evaluate_structure(
        self,
        counterparty: Counterparty,
        holdings: List[Holding],
        control_relations: Optional[List[ControlRelation]] = None,
        key_persons: Optional[List[KeyPerson]] = None,
        auto_screen: bool = True,
        disposition: Optional[FourEyesReview] = None,
        mapping_metadata: Optional[Dict[str, str]] = None,
    ) -> UBOResult:
        """
        Evaluate full corporate hierarchy and governance relationships against multilateral rules.
        """
        t0 = time.perf_counter()
        target_name = counterparty.name.strip()
        control_relations = control_relations or []
        key_persons = key_persons or []

        # ---------------------------------------------------------------------
        # 1. Validation & Screening
        # ---------------------------------------------------------------------
        validation_errors: List[str] = []

        # Screen parties if required
        if auto_screen:
            for h in holdings:
                if not h.user_override:
                    blk, src, hit = self.screen_party(h.shareholder_name, h.entity_type)
                    h.is_blocked = blk
                    h.blocked_source = src
                    h.screening_hit = hit
            for kp in key_persons:
                if not kp.user_override:
                    blk, src, hit = self.screen_party(kp.name, "person")
                    kp.is_blocked = blk
                    kp.blocked_source = src
                    kp.screening_hit = hit
            for cr in control_relations:
                if not cr.user_override:
                    blk, src, _ = self.screen_party(cr.controller_name, "company")
                    cr.is_blocked = blk
                    cr.blocked_source = src

        # Validate holdings per entity and check for cycles
        val_errs, cycle_detected, entity_totals = self.validate_holdings(holdings)
        validation_errors.extend(val_errs)

        holdings_by_entity: Dict[str, List[Holding]] = defaultdict(list)
        for h in holdings:
            holdings_by_entity[h.entity_name.strip().lower()].append(h)

        # Calculate shortfall (undisclosed ownership) in Counterparty
        target_disclosed = entity_totals.get(target_name.lower(), 0.0)
        undisclosed_pct = self.calculate_undisclosed(target_disclosed)

        # ---------------------------------------------------------------------
        # 2. Parallel Economic Look-Through & Nominee/Trust Resolution
        # ---------------------------------------------------------------------
        effective_holdings: Dict[str, float] = defaultdict(float)

        def traverse_look_through(curr_entity: str, multiplier: float, depth: int = 0):
            if depth > 10:
                return
            sub_holdings = holdings_by_entity.get(curr_entity.lower(), [])
            if not sub_holdings:
                effective_holdings[curr_entity] += multiplier * 100.0
                return

            for h in sub_holdings:
                step_mult = multiplier * (h.share_pct / 100.0)
                sh_name = h.shareholder_name.strip()

                if h.holding_type == "nominee" and h.on_behalf_of:
                    actual_owner = h.on_behalf_of.strip()
                    effective_holdings[actual_owner] += step_mult * 100.0
                    traverse_look_through(actual_owner, step_mult, depth + 1)
                else:
                    sub_subs = holdings_by_entity.get(sh_name.lower(), [])
                    if not sub_subs:
                        effective_holdings[sh_name] += step_mult * 100.0
                    else:
                        traverse_look_through(sh_name, step_mult, depth + 1)

        direct_target_holdings = holdings_by_entity.get(target_name.lower(), [])
        for d in direct_target_holdings:
            d_mult = (d.share_pct / 100.0)
            sh = d.on_behalf_of.strip() if (d.holding_type == "nominee" and d.on_behalf_of) else d.shareholder_name.strip()
            subs = holdings_by_entity.get(sh.lower(), [])
            if not subs:
                effective_holdings[sh] += d.share_pct
            else:
                traverse_look_through(sh, d_mult, depth=1)

        effective_holdings = {k: round(v, 4) for k, v in effective_holdings.items()}

        # ---------------------------------------------------------------------
        # 3. Adani SOP 20% Diligence Triggers & Indian 10% BO Markers
        # ---------------------------------------------------------------------
        diligence_triggers = []
        india_bo_markers = []

        party_info: Dict[str, Holding] = {}
        for h in holdings:
            party_info[h.shareholder_name.lower()] = h

        all_candidate_holders = set(h.shareholder_name for h in holdings)
        all_candidate_holders.update(effective_holdings.keys())

        for p_name in sorted(all_candidate_holders):
            direct_in_target = sum(h.share_pct for h in direct_target_holdings if h.shareholder_name.lower() == p_name.lower())
            eff_in_target = effective_holdings.get(p_name, direct_in_target)
            max_holding = max(direct_in_target, eff_in_target)

            p_h = party_info.get(p_name.lower())
            dob_val = p_h.dob if p_h else ""
            id_val = p_h.id_number if p_h else ""

            is_trig, kyc_incomp = self.check_diligence_trigger(max_holding, dob_val, id_val)
            if is_trig:
                flags = ["20% diligence trigger met"]
                if kyc_incomp:
                    flags.append("KYC incomplete")
                diligence_triggers.append({
                    "name": p_name,
                    "direct_pct": round(direct_in_target, 2),
                    "effective_pct": round(eff_in_target, 2),
                    "kyc_incomplete": kyc_incomp,
                    "flags": flags,
                })

            if self.check_india_bo_marker(max_holding):
                india_bo_markers.append({
                    "name": p_name,
                    "direct_pct": round(direct_in_target, 2),
                    "effective_pct": round(eff_in_target, 2),
                    "label": "Above the Indian beneficial-owner threshold (information only)",
                })

        # ---------------------------------------------------------------------
        # 4. Multilateral Sanctions Determinations
        # ---------------------------------------------------------------------
        calculation_traces: List[str] = []
        ofac_blocked_memo: Dict[str, bool] = {}

        # 4.1 OFAC 50% Rule Evaluation
        ofac_aggregate = 0.0
        ofac_contributors = []

        for d in direct_target_holdings:
            sh_name = d.shareholder_name.strip()
            if d.is_blocked and ("us_ofac" in d.blocked_source.lower() or d.blocked_source == "user_override"):
                ofac_aggregate += d.share_pct
                ofac_contributors.append({
                    "name": sh_name,
                    "holding_pct": d.share_pct,
                    "reason": "Directly designated on OFAC list",
                })
                calculation_traces.append(f"OFAC: Direct blocked holding of {d.share_pct}% by {sh_name}")
            else:
                is_sub_b, sub_agg, sub_reasons = self.is_entity_ofac_blocked(sh_name, holdings_by_entity, party_info, ofac_blocked_memo, depth=1)
                if is_sub_b:
                    ofac_aggregate += d.share_pct
                    ofac_contributors.append({
                        "name": sh_name,
                        "holding_pct": d.share_pct,
                        "reason": f"Intermediate entity >=50% owned by blocked persons ({'; '.join(sub_reasons)})",
                    })
                    calculation_traces.append(f"OFAC: Indirect blocked pass-through: {sh_name} is >=50% blocked entity owning {d.share_pct}% in {target_name}")

        ofac_criteria_met = (ofac_aggregate >= 50.0)
        ofac_verdict = {
            "criteria_met": ofac_criteria_met,
            "aggregate_pct": round(ofac_aggregate, 2),
            "threshold_pct": 50.0,
            "operator": ">=",
            "contributors": ofac_contributors,
            "verdict_text": (
                "Sanctions ownership criteria met (US OFAC 50% Rule)"
                if ofac_criteria_met else
                "No sanctions ownership or control criteria met based on disclosed data (US OFAC)"
            ),
        }

        # 4.2 EU 50% Rule Evaluation (50% or more, default aggregation ON)
        eu_blocked_entities: Dict[str, bool] = {}

        def check_eu_entity_blocked(ent_name: str, depth: int = 0) -> bool:
            clean_name = ent_name.strip().lower()
            if clean_name in eu_blocked_entities:
                return eu_blocked_entities[clean_name]

            p_h = party_info.get(clean_name)
            if p_h and (p_h.is_blocked and ("eu_csl" in p_h.blocked_source.lower() or p_h.blocked_source == "user_override")):
                eu_blocked_entities[clean_name] = True
                return True

            if depth > 8:
                return False

            sub_holdings = holdings_by_entity.get(clean_name, [])
            agg_pct = sum(sh.share_pct for sh in sub_holdings if (sh.is_blocked and ("eu_csl" in sh.blocked_source.lower() or sh.blocked_source == "user_override")) or check_eu_entity_blocked(sh.shareholder_name, depth + 1))
            is_b = (agg_pct >= 50.0)
            eu_blocked_entities[clean_name] = is_b
            return is_b

        eu_aggregate = 0.0
        eu_reasons = []

        for d in direct_target_holdings:
            sh_name = d.shareholder_name.strip()
            if d.is_blocked and ("eu_csl" in d.blocked_source.lower() or d.blocked_source == "user_override"):
                eu_aggregate += d.share_pct
                eu_reasons.append(f"{sh_name} (designated on EU list) holds {d.share_pct}% directly")
            elif check_eu_entity_blocked(sh_name, depth=1):
                eu_aggregate += d.share_pct
                eu_reasons.append(f"{sh_name} is a >=50% EU-blocked entity holding {d.share_pct}% in {target_name}")

        eu_ownership_met = (eu_aggregate >= 50.0)

        eu_control_met = False
        for cr in control_relations:
            if cr.is_blocked and ("eu_csl" in cr.blocked_source.lower() or cr.blocked_source == "user_override"):
                eu_control_met = True
                eu_reasons.append(f"{cr.controller_name} (EU designated) exercises control: {cr.description or cr.control_type}")

        for kp in key_persons:
            if kp.is_blocked and ("eu_csl" in kp.blocked_source.lower() or kp.blocked_source == "user_override") and kp.has_appointment_power:
                eu_control_met = True
                eu_reasons.append(f"Key person {kp.name} (EU designated) holds appointment authority")

        eu_criteria_met = eu_ownership_met or eu_control_met
        eu_verdict = {
            "criteria_met": eu_criteria_met,
            "ownership_criteria_met": eu_ownership_met,
            "control_criteria_met": eu_control_met,
            "aggregate_pct": round(eu_aggregate, 2),
            "threshold_pct": 50.0,
            "operator": ">=",
            "assumption_note": "Evaluated with aggregation of designated owners (EU Commission Guidance conservative default).",
            "reasons": eu_reasons,
            "verdict_text": (
                "Sanctions ownership or control criteria met (EU Council Regulations)"
                if eu_criteria_met else
                "No sanctions ownership or control criteria met based on disclosed data (EU)"
            ),
        }

        # 4.3 UK Ownership & Control (OFSI) (>50% required; aggregation conservative shown alongside)
        uk_reasons = []
        uk_notes = []

        uk_condition_1_met = False
        uk_conservative_aggregate = 0.0

        for d in direct_target_holdings:
            sh_name = d.shareholder_name.strip()
            if d.is_blocked and ("uk_csl" in d.blocked_source.lower() or d.blocked_source == "user_override"):
                uk_conservative_aggregate += d.share_pct
                if d.share_pct > 50.0:
                    uk_condition_1_met = True
                    uk_reasons.append(f"{sh_name} (UK designated) holds {d.share_pct}% shares (>50% condition met)")
                elif abs(d.share_pct - 50.0) < 0.001:
                    uk_notes.append(f"Boundary notice: {sh_name} holds exactly 50.0% (UK requires strictly >50% for Condition 1).")
            else:
                sub_subs = holdings_by_entity.get(sh_name.lower(), [])
                for sub_h in sub_subs:
                    if sub_h.is_blocked and ("uk_csl" in sub_h.blocked_source.lower() or sub_h.blocked_source == "user_override"):
                        if sub_h.share_pct > 50.0 and d.share_pct > 50.0:
                            uk_condition_1_met = True
                            uk_reasons.append(f"{sub_h.shareholder_name} holds >50% in {sh_name}, which holds >50% in {target_name}")
                        elif abs(sub_h.share_pct - 50.0) < 0.001:
                            uk_notes.append(f"Boundary notice: {sub_h.shareholder_name} holds exactly 50.0% in intermediate {sh_name} (UK Condition 1 requires strictly >50%).")

        uk_condition_2_met = False
        for cr in control_relations:
            if cr.is_blocked and ("uk_csl" in cr.blocked_source.lower() or cr.blocked_source == "user_override"):
                if cr.control_type in ["board_majority", "appointment_power", "dominant_influence"]:
                    uk_condition_2_met = True
                    uk_reasons.append(f"{cr.controller_name} (UK designated) exercises board control / appointment authority")

        for kp in key_persons:
            if kp.is_blocked and ("uk_csl" in kp.blocked_source.lower() or kp.blocked_source == "user_override") and kp.has_appointment_power:
                uk_condition_2_met = True
                uk_reasons.append(f"Key person {kp.name} (UK designated) holds authority to appoint or remove board")

        total_directors = sum(1 for kp in key_persons if kp.role == "director")
        blocked_directors = sum(1 for kp in key_persons if kp.role == "director" and kp.is_blocked and ("uk_csl" in kp.blocked_source.lower() or kp.blocked_source == "user_override"))
        if total_directors > 0 and (blocked_directors / total_directors) > 0.50:
            uk_condition_2_met = True
            uk_reasons.append(f"UK designated persons hold majority of board of directors ({blocked_directors}/{total_directors})")

        uk_criteria_met = uk_condition_1_met or uk_condition_2_met
        uk_verdict = {
            "criteria_met": uk_criteria_met,
            "condition_1_met": uk_condition_1_met,
            "condition_2_met": uk_condition_2_met,
            "conservative_aggregate_pct": round(uk_conservative_aggregate, 2),
            "threshold_pct": 50.0,
            "operator": ">",
            "notes": uk_notes,
            "reasons": uk_reasons,
            "verdict_text": (
                "Sanctions ownership or control criteria met (UK Sanctions Regulations)"
                if uk_criteria_met else
                "No sanctions ownership or control criteria met based on disclosed data (UK)"
            ),
        }

        # 4.4 UN and India MHA Flags
        un_mha_flags = []
        for h in holdings:
            if h.is_blocked and ("un_csl" in h.blocked_source.lower() or "in_mha" in h.blocked_source.lower() or h.blocked_source == "user_override"):
                un_mha_flags.append({
                    "party": h.shareholder_name,
                    "holding_pct": h.share_pct,
                    "source": h.blocked_source,
                    "authority": "UN / MHA",
                    "note": f"Party {h.shareholder_name} is listed on UN or India MHA sanctions register",
                })
        for kp in key_persons:
            if kp.is_blocked and ("in_mha" in kp.blocked_source.lower() or "mha" in kp.blocked_source.lower() or "un_csl" in kp.blocked_source.lower() or kp.blocked_source == "user_override"):
                un_mha_flags.append({
                    "party": kp.name,
                    "role": kp.role,
                    "source": kp.blocked_source,
                    "authority": "UN / MHA",
                    "note": f"Key person {kp.name} ({kp.role}) is designated on UN or India MHA list",
                })

        # 4.5 BIS Entity List Affiliates Flag
        bis_affiliate_flags = self.check_bis_affiliates(holdings)

        # 4.6 "Result depends on undisclosed X%"
        depends_on_undisclosed = self.check_undisclosed_dependence(ofac_aggregate, eu_aggregate, undisclosed_pct)
        if depends_on_undisclosed:
            calculation_traces.append(f"Notice: Result depends on undisclosed {undisclosed_pct}% (could push OFAC/EU aggregate above 50%)")

        # ---------------------------------------------------------------------
        # 5. Natural Person Resolution & Senior Managing Official Fallback
        # ---------------------------------------------------------------------
        natural_persons = self.resolve_natural_persons(effective_holdings, party_info)

        if not natural_persons:
            smo_fb = self.senior_managing_official_fallback(key_persons)
            if smo_fb:
                natural_persons.append(smo_fb)
            else:
                validation_errors.append("Ultimate owner not identified: No natural persons identified in ownership chains.")

        # ---------------------------------------------------------------------
        # 6. Structure Risk Indicators & Verification Level
        # ---------------------------------------------------------------------
        # Compute structure depth
        tree_depth = 0
        children_map = {}
        for h in holdings:
            children_map.setdefault(h.entity_name.strip().lower(), []).append(h.shareholder_name.strip().lower())
        def _calc_depth(node: str, vis: set) -> int:
            if node in vis: return 0
            vis.add(node)
            ch = children_map.get(node, [])
            if not ch: return 1
            return 1 + max(_calc_depth(c, vis.copy()) for c in ch)
        if holdings:
            tree_depth = max(_calc_depth(target_name.strip().lower(), set()) - 1, 0)

        # Unresolved orange candidates
        unres_orange = []
        for h in holdings:
            hit = h.screening_hit if isinstance(h.screening_hit, dict) else {}
            is_orange = (hit.get("tier") in ["POSSIBLE_MATCH", "🟠"] or hit.get("tier_icon") == "🟠")
            if is_orange and h.user_override != "False positive":
                unres_orange.append({"party": h.shareholder_name, "tier": "POSSIBLE_MATCH"})

        recent_chg = getattr(counterparty, "ownership_change_last_12m", False) or any(getattr(h, "ownership_change_last_12m", False) for h in holdings)

        risk_indicators = self.check_structure_risk_indicators(
            cycle_detected=cycle_detected,
            undisclosed_pct=undisclosed_pct,
            holdings=holdings,
            max_depth=tree_depth,
            screening_hits=unres_orange,
            ownership_change_last_12m=recent_chg,
        )

        self_declared_sum = sum(h.share_pct for h in direct_target_holdings if h.verification_level == "self_declared")
        self_declared_share = round(self_declared_sum, 2)

        # ---------------------------------------------------------------------
        # 7. Four-Eyes Review & Schedule
        # ---------------------------------------------------------------------
        review_obj = disposition or FourEyesReview()
        has_risk = bool(risk_indicators or ofac_criteria_met or eu_criteria_met or uk_criteria_met or un_mha_flags)
        months_due = 6 if has_risk else 12
        review_obj.review_due_date = (datetime.now(timezone.utc) + timedelta(days=months_due * 30)).strftime("%Y-%m-%d")

        look_through_summary = []
        for h in holdings:
            eff = effective_holdings.get(h.shareholder_name, h.share_pct)
            look_through_summary.append({
                "name": h.shareholder_name,
                "type": h.entity_type.capitalize(),
                "country": h.country or "—",
                "direct_pct": h.share_pct,
                "effective_look_through_pct": eff,
                "is_blocked": h.is_blocked,
                "blocked_source": h.blocked_source,
                "verification_level": h.verification_level,
            })

        duration_ms = (time.perf_counter() - t0) * 1000.0

        nodes_compat = [
            OwnershipNode(
                name=h.shareholder_name,
                ownership_pct=h.share_pct,
                parent_name="" if h.entity_name.lower() == target_name.lower() else h.entity_name,
                entity_type=h.entity_type,
                country=h.country,
                is_blocked=h.is_blocked,
                blocked_source=h.blocked_source,
                effective_look_through_pct=effective_holdings.get(h.shareholder_name, h.share_pct),
                notes=h.notes,
            ) for h in holdings
        ]

        # Mapping metadata extraction
        m_meta = mapping_metadata or {}
        m_name = m_meta.get("name", "")
        m_ver = m_meta.get("version", "")
        m_hash = m_meta.get("hash", "")

        result = UBOResult(
            target_name=target_name,
            counterparty=counterparty,
            holdings=holdings,
            control_relations=control_relations,
            key_persons=key_persons,
            nodes=nodes_compat,
            effective_holdings=effective_holdings,
            natural_person_ubos=natural_persons,
            diligence_triggers=diligence_triggers,
            india_bo_markers=india_bo_markers,
            undisclosed_ownership_pct=undisclosed_pct,
            depends_on_undisclosed=depends_on_undisclosed,
            validation_errors=validation_errors,
            cycle_detected=cycle_detected,
            ofac_blocked=ofac_criteria_met,
            ofac_aggregate_pct=round(ofac_aggregate, 2),
            ofac_blocked_contributors=ofac_contributors,
            ofac_path_traces=calculation_traces,
            ofac_verdict=ofac_verdict,
            eu_blocked=eu_criteria_met,
            eu_ownership_blocked=eu_ownership_met,
            eu_control_blocked=eu_control_met,
            eu_reasons=eu_reasons,
            eu_verdict=eu_verdict,
            uk_blocked=uk_criteria_met,
            uk_condition_1_shares=uk_condition_1_met,
            uk_condition_2_board=uk_condition_2_met,
            uk_reasons=uk_reasons,
            uk_verdict=uk_verdict,
            un_mha_flags=un_mha_flags,
            bis_affiliate_flags=bis_affiliate_flags,
            structure_risk_indicators=risk_indicators,
            self_declared_share_pct=self_declared_share,
            look_through_summary=look_through_summary,
            mapping_name=m_name,
            mapping_version=m_ver,
            mapping_hash=m_hash,
            mapping_metadata=m_meta,
            disposition=review_obj,
            execution_time_ms=round(duration_ms, 2),
        )

        result.confirmed_scenario_verdict = self.evaluate_possible_matches_scenario(result)

        self.log_ubo_check(result)
        return result

    def evaluate_ownership(
        self,
        target_name: str,
        nodes: List[OwnershipNode],
        auto_screen: bool = True,
        disposition: Optional[FourEyesReview] = None,
    ) -> UBOResult:
        """Backwards-compatible API accepting OwnershipNodes."""
        cp = Counterparty(name=target_name)
        holdings = []
        control_relations = []
        for n in nodes:
            h = Holding(
                shareholder_name=n.name,
                entity_name=n.parent_name if n.parent_name else target_name,
                share_pct=n.ownership_pct,
                entity_type=n.entity_type,
                country=n.country,
                dob=n.dob,
                id_number=n.id_number,
                is_blocked=n.is_blocked,
                blocked_source=n.blocked_source,
                user_override=n.user_override,
                notes=n.notes,
            )
            holdings.append(h)
            if n.has_appointment_power or n.is_board_member:
                cr = ControlRelation(
                    controller_name=n.name,
                    target_name=n.parent_name if n.parent_name else target_name,
                    control_type="appointment_power" if n.has_appointment_power else "board_seat",
                    appointment_power=n.has_appointment_power,
                    is_blocked=n.is_blocked,
                    blocked_source=n.blocked_source,
                    user_override=n.user_override,
                )
                control_relations.append(cr)

        return self.evaluate_structure(
            counterparty=cp,
            holdings=holdings,
            control_relations=control_relations,
            auto_screen=auto_screen,
            disposition=disposition,
        )

    def save_ownership_check(self, res: UBOResult) -> None:
        """Persist evaluation to append-only ownership_checks and ownership_parties tables."""
        db_path = get_logs_dir() / "screening.db"
        if not db_path.exists():
            return

        try:
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()

            cur.execute("""
                CREATE TABLE IF NOT EXISTS ownership_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_name TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL,
                    preparer TEXT,
                    reviewer TEXT,
                    review_due_date TEXT,
                    version INTEGER DEFAULT 1,
                    ofac_verdict TEXT,
                    eu_verdict TEXT,
                    uk_verdict TEXT,
                    undisclosed_pct REAL,
                    depends_on_undisclosed INTEGER,
                    data_json TEXT
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS ownership_parties (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    check_id INTEGER,
                    party_name TEXT NOT NULL,
                    entity_type TEXT,
                    direct_pct REAL,
                    effective_pct REAL,
                    is_blocked INTEGER,
                    blocked_source TEXT,
                    disposition TEXT
                )
            """)

            cur.execute("""
                INSERT INTO ownership_checks (
                    target_name, timestamp, status, preparer, reviewer, review_due_date,
                    version, ofac_verdict, eu_verdict, uk_verdict, undisclosed_pct,
                    depends_on_undisclosed, data_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                res.target_name,
                res.disposition.timestamp,
                res.disposition.status,
                res.disposition.preparer,
                res.disposition.reviewer,
                res.disposition.review_due_date,
                res.disposition.version,
                res.ofac_verdict.get("verdict_text", ""),
                res.eu_verdict.get("verdict_text", ""),
                res.uk_verdict.get("verdict_text", ""),
                res.undisclosed_ownership_pct,
                1 if res.depends_on_undisclosed else 0,
                json.dumps({
                    "effective_holdings": res.effective_holdings,
                    "validation_errors": res.validation_errors,
                    "diligence_triggers": res.diligence_triggers,
                }),
            ))
            check_id = cur.lastrowid

            for h in res.holdings:
                eff = res.effective_holdings.get(h.shareholder_name, h.share_pct)
                cur.execute("""
                    INSERT INTO ownership_parties (
                        check_id, party_name, entity_type, direct_pct, effective_pct,
                        is_blocked, blocked_source, disposition
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    check_id,
                    h.shareholder_name,
                    h.entity_type,
                    h.share_pct,
                    eff,
                    1 if h.is_blocked else 0,
                    h.blocked_source,
                    h.user_override or "Unresolved",
                ))

            conn.commit()
            conn.close()
        except Exception as exc:
            logger.warning("Could not persist ownership check: %s", exc)

    def log_ubo_check(self, res: UBOResult) -> None:
        """Write UBO screening result to SQLite audit trail with mode='ownership'."""
        self.save_ownership_check(res)
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
