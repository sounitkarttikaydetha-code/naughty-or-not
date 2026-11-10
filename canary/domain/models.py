"""
Domain Models for Clearance Check Canary (v2.0.1).
Pure data structures with ZERO I/O dependencies.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Tier(str, Enum):
    POTENTIAL_MATCH = "POTENTIAL_MATCH"          # 🔴
    POSSIBLE_MATCH_REVIEW = "POSSIBLE_MATCH_REVIEW"  # 🟠
    BELOW_THRESHOLD = "BELOW_THRESHOLD"          # ℹ️
    NO_MATCH = "NO_MATCH"                        # ✅
    NOT_CHECKED = "NOT_CHECKED"                  # ⚪


TIER_ICONS = {
    Tier.POTENTIAL_MATCH: "🔴",
    Tier.POSSIBLE_MATCH_REVIEW: "🟠",
    Tier.BELOW_THRESHOLD: "ℹ️",
    Tier.NO_MATCH: "✅",
    Tier.NOT_CHECKED: "⚪",
}

TIER_DRAWN_MARKERS = {
    Tier.POTENTIAL_MATCH: "● LIKELY MATCH",
    Tier.POSSIBLE_MATCH_REVIEW: "● POSSIBLE MATCH",
    Tier.BELOW_THRESHOLD: "● BELOW THRESHOLD",
    Tier.NO_MATCH: "● CLEAR",
    Tier.NOT_CHECKED: "● NOT CHECKED",
}


@dataclass(frozen=True)
class MatchHit:
    tier: str
    tier_icon: str
    score: float
    reason: str
    primary_name: str
    matched_name: str
    source_id: str
    expanded_from: Optional[str] = None
    below_threshold_count: int = 0
    matched_phonetic_codes: List[str] = field(default_factory=list)


@dataclass
class ScreeningResult:
    query: str
    query_type: str
    group: Optional[str] = None
    phonetic_codes: List[str] = field(default_factory=list)
    lists: Dict[str, MatchHit] = field(default_factory=dict)
    execution_time_ms: float = 0.0


@dataclass
class EntityRecord:
    source_id: str
    record_id: str
    primary_name: str
    entity_type: Optional[str] = None
    aliases: List[str] = field(default_factory=list)
    addresses: List[str] = field(default_factory=list)
    identification_numbers: List[str] = field(default_factory=list)
    programmes: List[str] = field(default_factory=list)
    remarks: Optional[str] = None
    raw_payload: Dict[str, Any] = field(default_factory=dict)
    updated_at: Optional[str] = None


@dataclass
class OwnershipNode:
    name: str
    entity_type: str
    direct_pct: float
    effective_pct: float
    is_blocked: bool = False
    blocked_source: Optional[str] = None
    children: List["OwnershipNode"] = field(default_factory=list)


@dataclass
class Disposition:
    status: str
    preparer: Optional[str] = None
    reviewer: Optional[str] = None
    timestamp: Optional[str] = None
    comment: Optional[str] = None


@dataclass
class UBOResult:
    target_name: str
    ofac_blocked: bool
    eu_blocked: bool
    uk_blocked: bool
    ofac_aggregate_pct: float
    nodes: List[OwnershipNode] = field(default_factory=list)
    disposition: Optional[Disposition] = None
    execution_time_ms: float = 0.0


@dataclass
class CountryCheckResult:
    country_name: str
    iso_code: str
    fatf_status: str  # "Call for Action", "Increased Monitoring", "Clean"
    fatf_statement: Optional[str] = None
    is_comprehensive_sanctioned: bool = False
    regimes: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
