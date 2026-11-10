"""
Pydantic Schemas for Clearance Check Canary API (/api/v1/...).
Includes strict input validation, length bounds, regex, and enums.
"""
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class QueryType(str, Enum):
    ORGANISATION = "organisation"
    AIRLINE = "airline"
    PERSON = "person"
    VESSEL = "vessel"
    AIRCRAFT = "aircraft"


class ScreenRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Name or phrase to screen")
    query_type: Optional[QueryType] = Field(default=QueryType.ORGANISATION, description="Entity type category")
    identifier_type: Optional[str] = Field(default=None, max_length=50, description="Optional identifier type (e.g. IMO, Passport)")
    identifier_val: Optional[str] = Field(default=None, max_length=100, description="Optional identifier value")

    @field_validator("query")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Query string cannot be empty or whitespace only.")
        return s


class MatchHitResponse(BaseModel):
    tier: str
    tier_icon: str
    score: float
    reason: str
    primary_name: str
    matched_name: str
    source_id: str
    expanded_from: Optional[str] = None
    below_threshold_count: int = 0
    matched_phonetic_codes: List[str] = Field(default_factory=list)


class ScreenResponse(BaseModel):
    query: str
    query_type: str
    phonetic_codes: List[str]
    lists: Dict[str, MatchHitResponse]
    execution_time_ms: float
    engine_version: str = "2.0.1-canary.1"
    list_dates: Dict[str, str] = Field(default_factory=dict)
    canary_notice: str = "Canary build — for evaluation only. Not for screening decisions."


class BatchScreenItem(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    query_type: Optional[QueryType] = Field(default=QueryType.ORGANISATION)


class BatchScreenRequest(BaseModel):
    items: List[BatchScreenItem] = Field(..., min_length=1, max_length=1000)


class BatchSubmissionResponse(BaseModel):
    batch_id: str
    status: str
    total_items: int
    created_at: float
    message: str
    engine_version: str = "2.0.1-canary.1"


class BatchStatusResponse(BaseModel):
    batch_id: str
    user_id: str
    total_items: int
    processed_items: int
    status: str
    results: List[Dict[str, Any]] = Field(default_factory=list)
    engine_version: str = "2.0.1-canary.1"


class HoldingItem(BaseModel):
    entity_name: str = Field(..., min_length=1, max_length=255)
    shareholder_name: str = Field(..., min_length=1, max_length=255)
    share_pct: float = Field(..., ge=0.0, le=100.0)
    entity_type: Optional[str] = Field(default="company", max_length=50)
    is_blocked: Optional[bool] = Field(default=False)
    blocked_source: Optional[str] = Field(default="", max_length=100)


class OwnershipCreateRequest(BaseModel):
    target_name: str = Field(..., min_length=1, max_length=255)
    holdings: List[HoldingItem] = Field(..., min_length=1)


class OwnershipReviewRequest(BaseModel):
    decision: str = Field(..., description="'APPROVED' or 'REJECTED'")
    comment: str = Field(..., min_length=3, max_length=2000, description="Mandatory justification for disposition")

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, v: str) -> str:
        u = v.strip().upper()
        if u not in ("APPROVED", "REJECTED"):
            raise ValueError("Decision must be either 'APPROVED' or 'REJECTED'.")
        return u


class CountryCheckRequest(BaseModel):
    country: str = Field(..., min_length=1, max_length=100)
    iso_code: Optional[str] = Field(default=None, max_length=3)


class CountryCheckResponse(BaseModel):
    country_name: str
    iso_code: str
    fatf_status: str
    fatf_statement: Optional[str] = None
    is_comprehensive_sanctioned: bool
    regimes: List[str]
    notes: List[str]
    engine_version: str = "2.0.1-canary.1"
    canary_notice: str = "Canary build — for evaluation only. Not for screening decisions."


class ProblemDetails(BaseModel):
    type: str = "https://clearancecheck.canary/errors/problem"
    title: str
    status: int
    detail: str
    instance: str
    code: str
