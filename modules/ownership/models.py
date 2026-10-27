"""
Beneficial Ownership & Control Data Models (T11 Part E).
Defines structures for nodes in corporate hierarchy, multi-tier chains,
screening status, four-eyes disposition, and sanctions determination results.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class OwnershipNode:
    """Represents a direct or indirect shareholder, UBO, or director."""
    name: str
    ownership_pct: float = 0.0
    parent_name: str = ""
    entity_type: str = "company"  # "company", "person", "trust"
    country: str = ""
    is_board_member: bool = False
    has_appointment_power: bool = False
    notes: str = ""
    node_id: str = ""
    is_blocked: bool = False
    blocked_source: str = ""
    screening_hit: Optional[Dict[str, Any]] = None
    user_override: Optional[str] = None  # "BLOCKED", "CLEAR", None
    effective_look_through_pct: float = 0.0

    def __post_init__(self):
        if not self.node_id:
            clean = self.name.strip().lower().replace(" ", "_")
            parent_clean = self.parent_name.strip().lower().replace(" ", "_")
            self.node_id = f"{clean}_in_{parent_clean}" if parent_clean else clean
        if self.user_override == "BLOCKED":
            self.is_blocked = True
            if not self.blocked_source:
                self.blocked_source = "user_override"
        elif self.user_override == "CLEAR":
            self.is_blocked = False
            self.blocked_source = ""


@dataclass
class FourEyesReview:
    """Four-eyes compliance sign-off workflow."""
    preparer: str = ""
    reviewer: str = ""
    status: str = "PENDING"  # "PENDING", "APPROVED", "ESCALATED", "REJECTED"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: str = ""


@dataclass
class UBOResult:
    """Complete multilateral beneficial ownership screening evaluation."""
    target_name: str
    nodes: List[OwnershipNode] = field(default_factory=list)

    # US OFAC 50% Rule determination (FAQs 399, 401)
    ofac_blocked: bool = False
    ofac_aggregate_pct: float = 0.0
    ofac_blocked_contributors: List[Dict[str, Any]] = field(default_factory=list)
    ofac_path_traces: List[str] = field(default_factory=list)

    # EU Ownership & Control determination
    eu_blocked: bool = False
    eu_ownership_blocked: bool = False
    eu_control_blocked: bool = False
    eu_reasons: List[str] = field(default_factory=list)

    # UK Ownership & Control determination (Sanctions Regulations)
    uk_blocked: bool = False
    uk_condition_1_shares: bool = False
    uk_condition_2_board: bool = False
    uk_condition_3_conduct: bool = False
    uk_reasons: List[str] = field(default_factory=list)

    # Look-through comparison (Sanctions legal rules vs economic look-through)
    look_through_summary: List[Dict[str, Any]] = field(default_factory=list)

    # Review disposition
    disposition: FourEyesReview = field(default_factory=FourEyesReview)
    execution_time_ms: float = 0.0
