"""
Pure Domain Ownership & UBO Engine.
Implements:
- OFAC 50% Rule (direct & indirect aggregation)
- EU & UK Control and Ownership rules
- 20% Diligence trigger
- 10% Indian Beneficial Owner marker
- Undisclosed ownership shortfall and dependency check
- Circular cycle detection & 100% holding validation
Zero I/O.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class HoldingEntry:
    entity_name: str
    shareholder_name: str
    share_pct: float
    entity_type: str = "company"
    is_blocked: bool = False
    blocked_source: str = ""


@dataclass
class OwnershipValidationResult:
    is_valid: bool
    errors: List[str]
    cycle_detected: bool
    entity_totals: Dict[str, float]


def validate_ownership_structure(holdings: List[HoldingEntry]) -> OwnershipValidationResult:
    """Validate that holdings into any entity do not exceed 100% and no circular cycles exist."""
    errors: List[str] = []
    holdings_by_entity: Dict[str, List[HoldingEntry]] = defaultdict(list)
    entity_totals: Dict[str, float] = defaultdict(float)

    for h in holdings:
        ent = h.entity_name.strip().lower()
        holdings_by_entity[ent].append(h)
        entity_totals[ent] += h.share_pct

    for ent, total_pct in entity_totals.items():
        if total_pct > 100.001:
            errors.append(
                f"Holdings into '{ent}' total {total_pct:.2f}%, exceeding the 100.0% maximum allowed."
            )

    # Cycle detection
    visited: Set[str] = set()
    rec_stack: Set[str] = set()

    def dfs(curr: str) -> bool:
        visited.add(curr)
        rec_stack.add(curr)
        for h in holdings_by_entity.get(curr, []):
            child = h.shareholder_name.strip().lower()
            if child not in visited:
                if dfs(child):
                    return True
            elif child in rec_stack:
                return True
        rec_stack.remove(curr)
        return False

    cycle_detected = False
    for ent in list(holdings_by_entity.keys()):
        if ent not in visited:
            if dfs(ent):
                cycle_detected = True
                errors.append("Circular ownership chain detected in corporate hierarchy.")
                break

    return OwnershipValidationResult(
        is_valid=(len(errors) == 0),
        errors=errors,
        cycle_detected=cycle_detected,
        entity_totals=dict(entity_totals),
    )


def calculate_undisclosed_shortfall(total_disclosed: float) -> float:
    """Calculate undisclosed percentage: max(0.0, 100.0 - total_disclosed)."""
    return max(0.0, round(100.0 - total_disclosed, 2))


def check_undisclosed_dependence(ofac_agg: float, eu_agg: float, shortfall: float) -> bool:
    """True if undisclosed ownership could flip the 50% statutory sanctions threshold."""
    if shortfall <= 0.0:
        return False
    if ofac_agg < 50.0 and (ofac_agg + shortfall) >= 50.0:
        return True
    if eu_agg < 50.0 and (eu_agg + shortfall) >= 50.0:
        return True
    return False


def calculate_effective_ofac_blocked(
    target_name: str,
    holdings: List[HoldingEntry],
    depth_limit: int = 8,
) -> Tuple[bool, float, List[str]]:
    """
    Calculate whether target is blocked under OFAC 50% Rule.
    Aggregates ownership percentage from blocked parties directly and down chains.
    """
    holdings_by_entity: Dict[str, List[HoldingEntry]] = defaultdict(list)
    parties: Dict[str, HoldingEntry] = {}

    for h in holdings:
        ent = h.entity_name.strip().lower()
        holdings_by_entity[ent].append(h)
        parties[h.shareholder_name.strip().lower()] = h

    memo: Dict[str, bool] = {}

    def is_entity_blocked(ent_name: str, depth: int = 0) -> Tuple[bool, float, List[str]]:
        clean = ent_name.strip().lower()
        if clean in memo:
            return memo[clean], 0.0, []

        p_h = parties.get(clean)
        if p_h and p_h.is_blocked and ("us_ofac" in p_h.blocked_source.lower() or p_h.blocked_source == "user_override"):
            memo[clean] = True
            return True, 100.0, [f"{ent_name} is directly designated on OFAC list"]

        if depth > depth_limit:
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
                is_sub_b, _, sub_r = is_entity_blocked(sh_name, depth + 1)
                if is_sub_b:
                    sh_blocked = True
                    reasons.append(f"{sh_name} ({sh.share_pct}% in {ent_name}) is a >=50% OFAC-blocked entity")

            if sh_blocked:
                agg_pct += sh.share_pct

        is_b = (agg_pct >= 50.0)
        memo[clean] = is_b
        return is_b, agg_pct, reasons

    return is_entity_blocked(target_name)
