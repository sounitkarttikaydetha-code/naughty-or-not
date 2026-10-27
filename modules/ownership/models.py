"""
Beneficial Ownership & Control Data Models (T11.1 Section 1).
Defines structures for:
  - Counterparties, multi-tier holdings, control relationships, key persons
  - Trusts and nominee arrangements
  - Verification levels, document records, and KYC completeness
  - Four-eyes review lifecycle (Draft -> Submitted -> Reviewed -> Closed/Escalated)
  - Multilateral statutory determinations and economic look-through
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple


class DispositionType:
    UNRESOLVED = "Unresolved"
    CONFIRMED_MATCH = "Confirmed match"
    FALSE_POSITIVE = "False positive"


@dataclass
class Counterparty:
    """The subject entity being screened and evaluated."""
    name: str
    jurisdiction: str = ""
    registration_number: str = ""
    tax_id: str = ""
    lei: str = ""
    address: str = ""
    business_activity: str = ""
    entity_type: str = "company"  # "company", "partnership", "trust", "spv", "state_owned"


@dataclass
class Holding:
    """Represents a shareholding / equity stake into an entity."""
    shareholder_name: str
    entity_name: str  # Immediate parent company or counterparty
    share_pct: float = 0.0
    voting_pct: Optional[float] = None  # None -> equals share_pct
    holding_type: str = "direct"  # "direct", "indirect", "nominee", "trust", "bearer"
    on_behalf_of: str = ""  # If nominee or held on behalf of someone else
    source_document: str = ""
    source_date: str = ""
    document_date: str = ""
    verification_level: str = "official_registry"  # "official_registry", "audited_financials", "corporate_certificate", "self_declared", "unverified"
    notes: str = ""

    # Optional party details for KYC verification
    entity_type: str = "company"  # "person", "company", "trust"
    country: str = ""
    dob: str = ""
    id_number: str = ""
    is_blocked: bool = False
    blocked_source: str = ""
    user_override: Optional[str] = None  # "BLOCKED", "CLEAR", "Confirmed match", "False positive", "Unresolved"
    screening_hit: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.voting_pct is None:
            self.voting_pct = self.share_pct
        if self.user_override in ["BLOCKED", "Confirmed match"]:
            self.is_blocked = True
            if not self.blocked_source:
                self.blocked_source = "user_override"
        elif self.user_override in ["CLEAR", "False positive"]:
            self.is_blocked = False
            self.blocked_source = ""


# Alias for backwards compatibility and requirement naming
OwnershipRow = Holding


@dataclass
class ControlRelation:
    """Represents a non-equity or governing control relationship."""
    controller_name: str
    target_name: str
    control_type: str = "board_seat"  # "board_seat", "board_majority", "appointment_power", "veto_rights", "dominant_influence", "other"
    board_seats: int = 0
    board_seats_held: int = 0
    total_board_seats: int = 0
    appointment_power: bool = False
    veto_power: bool = False
    percentage: Optional[float] = None
    description: str = ""
    source_document: str = ""
    is_blocked: bool = False
    blocked_source: str = ""
    user_override: Optional[str] = None


@dataclass
class KeyPerson:
    """Represents an individual officer, director, trustee, or senior managing official."""
    name: str
    role: str = "director"  # "director", "senior_managing_official", "trustee", "settlor", "protector", "beneficiary"
    entity_name: str = ""
    target_name: str = ""
    nationality: str = ""
    appointment_date: str = ""
    country: str = ""
    dob: str = ""
    id_number: str = ""
    kyc_complete: bool = False
    has_appointment_power: bool = False
    is_blocked: bool = False
    blocked_source: str = ""
    user_override: Optional[str] = None
    screening_hit: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if not self.entity_name and self.target_name:
            self.entity_name = self.target_name
        elif not self.target_name and self.entity_name:
            self.target_name = self.entity_name


@dataclass
class TrustDetails:
    """Trust structure elements."""
    trust_name: str
    settlors: List[str] = field(default_factory=list)
    trustees: List[str] = field(default_factory=list)
    protectors: List[str] = field(default_factory=list)
    beneficiaries: List[str] = field(default_factory=list)


@dataclass
class OwnershipNode:
    """
    Backwards-compatible wrapper node for tree traversal.
    Can be constructed directly or converted from Holding.
    """
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
    user_override: Optional[str] = None
    effective_look_through_pct: float = 0.0
    dob: str = ""
    id_number: str = ""
    verification_level: str = "official_registry"
    holding_type: str = "direct"
    on_behalf_of: str = ""

    def __post_init__(self):
        if not self.node_id:
            clean = self.name.strip().lower().replace(" ", "_")
            parent_clean = self.parent_name.strip().lower().replace(" ", "_")
            self.node_id = f"{clean}_in_{parent_clean}" if parent_clean else clean
        if self.user_override in ["BLOCKED", "Confirmed match"]:
            self.is_blocked = True
            if not self.blocked_source:
                self.blocked_source = "user_override"
        elif self.user_override in ["CLEAR", "False positive"]:
            self.is_blocked = False
            self.blocked_source = ""


@dataclass
class FourEyesReview:
    """Compliance four-eyes review with user separation and audit lifecycle."""
    preparer: str = ""
    reviewer: str = ""
    status: str = "Draft"  # "Draft", "Submitted", "Reviewed", "Closed", "Escalated"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    review_due_date: str = ""
    version: int = 1
    notes: str = ""
    is_read_only: bool = False

    def validate_user_separation(self) -> Tuple[bool, str]:
        """Ensure reviewer is a different individual than the preparer."""
        if not self.reviewer:
            return True, "Reviewer pending"
        if self.preparer.strip().lower() == self.reviewer.strip().lower():
            return False, "Four-Eyes Violation: Reviewer must be a different user than Preparer"
        return True, "User separation verified"


@dataclass
class UBOResult:
    """Comprehensive beneficial ownership evaluation result."""
    target_name: str
    counterparty: Counterparty = field(default_factory=lambda: Counterparty(name=""))
    holdings: List[Holding] = field(default_factory=list)
    control_relations: List[ControlRelation] = field(default_factory=list)
    key_persons: List[KeyPerson] = field(default_factory=list)
    nodes: List[OwnershipNode] = field(default_factory=list)

    # Effective economic look-through mapping: party_name -> effective %
    effective_holdings: Dict[str, float] = field(default_factory=dict)
    natural_person_ubos: List[Dict[str, Any]] = field(default_factory=list)

    # Adani SOP 20% Diligence Triggers & Indian 10% BO Markers
    diligence_triggers: List[Dict[str, Any]] = field(default_factory=list)
    india_bo_markers: List[Dict[str, Any]] = field(default_factory=list)

    # Disclosed vs Undisclosed holdings & shortfall
    undisclosed_ownership_pct: float = 0.0
    depends_on_undisclosed: bool = False
    validation_errors: List[str] = field(default_factory=list)
    cycle_detected: bool = False

    # US OFAC 50% Rule determination (FAQs 399, 401)
    ofac_blocked: bool = False
    ofac_aggregate_pct: float = 0.0
    ofac_blocked_contributors: List[Dict[str, Any]] = field(default_factory=list)
    ofac_path_traces: List[str] = field(default_factory=list)
    ofac_verdict: Dict[str, Any] = field(default_factory=dict)

    # EU Ownership & Control determination (>= 50%)
    eu_blocked: bool = False
    eu_ownership_blocked: bool = False
    eu_control_blocked: bool = False
    eu_reasons: List[str] = field(default_factory=list)
    eu_verdict: Dict[str, Any] = field(default_factory=dict)

    # UK Ownership & Control determination (> 50%)
    uk_blocked: bool = False
    uk_condition_1_shares: bool = False
    uk_condition_2_board: bool = False
    uk_condition_3_conduct: bool = False
    uk_reasons: List[str] = field(default_factory=list)
    uk_verdict: Dict[str, Any] = field(default_factory=dict)

    # UN & India MHA flags
    un_mha_flags: List[Dict[str, Any]] = field(default_factory=list)

    # BIS 50% Entity List Affiliates flag
    bis_affiliate_flags: List[Dict[str, Any]] = field(default_factory=list)

    # "If possible matches are confirmed" scenario analysis
    confirmed_scenario_verdict: Dict[str, Any] = field(default_factory=dict)

    # Structure risk indicators & verification level share
    structure_risk_indicators: List[str] = field(default_factory=list)
    self_declared_share_pct: float = 0.0

    # Look-through comparison summary table
    look_through_summary: List[Dict[str, Any]] = field(default_factory=list)

    # Mapping provenance
    mapping_name: str = ""
    mapping_version: str = ""
    mapping_hash: str = ""
    mapping_metadata: Dict[str, str] = field(default_factory=dict)

    # Four-Eyes review disposition
    disposition: FourEyesReview = field(default_factory=FourEyesReview)
    execution_time_ms: float = 0.0
