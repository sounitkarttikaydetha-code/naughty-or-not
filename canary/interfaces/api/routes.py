"""
API Routes definition for Clearance Check Canary (/api/v1/...).
FastAPI router implementation wiring application use cases to HTTP endpoints.
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from fastapi.responses import Response

from canary.application.ports.idp import UserContext
from canary.adapters.identity.oidc_client import GenericOIDCClient
from canary.adapters.identity.windows_auth import get_windows_fallback_user
from canary.adapters.storage.sqlite_repo import SQLiteRepository
from canary.adapters.sources.index_adapter import PythonIndexAdapter
from canary.adapters.reports.pdf_writer import CanaryPDFWriter
from canary.adapters.reports.excel_writer import CanaryExcelWriter

from canary.application.use_cases.screen_entity import ScreenEntityUseCase
from canary.application.use_cases.batch_screen import BatchScreenUseCase
from canary.application.use_cases.ownership_check import OwnershipCheckUseCase
from canary.application.use_cases.country_check import CountryCheckUseCase
from canary.application.use_cases.full_record import FullRecordUseCase
from canary.application.use_cases.source_status import SourceStatusUseCase
from canary.application.use_cases.reports import ReportsUseCase
from canary.application.use_cases.health import HealthUseCase

from canary.interfaces.api.schemas import (
    ScreenRequest,
    ScreenResponse,
    MatchHitResponse,
    BatchScreenRequest,
    BatchSubmissionResponse,
    BatchStatusResponse,
    OwnershipCreateRequest,
    OwnershipReviewRequest,
    CountryCheckRequest,
    CountryCheckResponse,
)

router = APIRouter()

# Default repository & index provider dependencies (Desktop Canary path)
def _get_canary_db_path() -> Path:
    override = os.environ.get("CANARY_DATA_DIR")
    if override:
        return Path(override) / "logs" / "clearance_canary.db"
    local_app = os.environ.get("LOCALAPPDATA")
    if local_app:
        return Path(local_app) / "ClearanceCheckCanary" / "logs" / "clearance_canary.db"
    return Path("cache") / "clearance_canary.db"


_repo_instance: Optional[SQLiteRepository] = None
_index_instance: Optional[PythonIndexAdapter] = None
_oidc_instance: Optional[GenericOIDCClient] = None


def get_repository() -> SQLiteRepository:
    global _repo_instance
    if _repo_instance is None:
        _repo_instance = SQLiteRepository(_get_canary_db_path())
    return _repo_instance


def get_index_provider() -> PythonIndexAdapter:
    global _index_instance
    if _index_instance is None:
        _index_instance = PythonIndexAdapter()
    return _index_instance


def get_oidc_client() -> GenericOIDCClient:
    global _oidc_instance
    if _oidc_instance is None:
        _oidc_instance = GenericOIDCClient()
    return _oidc_instance


def get_current_user(
    authorization: Optional[str] = Header(None),
    oidc_client: GenericOIDCClient = Depends(get_oidc_client),
) -> UserContext:
    """
    Authenticate user via Bearer token (OIDC).
    If header is absent, falls back to Windows user with clear label.
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        try:
            return oidc_client.verify_token(token)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid bearer authentication token: {e}",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Desktop fallback
    return get_windows_fallback_user()


# ==============================================================================
# Endpoints
# ==============================================================================

@router.post("/api/v1/screen", response_model=ScreenResponse, tags=["Screening"])
def screen_entity(
    req: ScreenRequest,
    user: UserContext = Depends(get_current_user),
    repo: SQLiteRepository = Depends(get_repository),
    index: PythonIndexAdapter = Depends(get_index_provider),
):
    """Screen an entity name or identifier across all 5 mandatory sanctions lists."""
    use_case = ScreenEntityUseCase(index_provider=index, repository=repo)
    result = use_case.execute(
        query=req.query,
        user=user,
        query_type=req.query_type.value if req.query_type else "organisation",
        identifier_type=req.identifier_type,
        identifier_val=req.identifier_val,
    )

    list_hits = {}
    for src, hit in result.lists.items():
        list_hits[src] = MatchHitResponse(
            tier=hit.tier,
            tier_icon=hit.tier_icon,
            score=hit.score,
            reason=hit.reason,
            primary_name=hit.primary_name,
            matched_name=hit.matched_name,
            source_id=hit.source_id,
            expanded_from=hit.expanded_from,
            below_threshold_count=hit.below_threshold_count,
            matched_phonetic_codes=hit.matched_phonetic_codes,
        )

    return ScreenResponse(
        query=result.query,
        query_type=result.query_type,
        phonetic_codes=result.phonetic_codes,
        lists=list_hits,
        execution_time_ms=result.execution_time_ms,
        engine_version="2.0.1-canary.1",
        list_dates=index.get_source_publication_dates(),
    )


@router.post("/api/v1/batch", response_model=BatchSubmissionResponse, status_code=status.HTTP_202_ACCEPTED, tags=["Batch Screening"])
def submit_batch_screening(
    req: BatchScreenRequest,
    user: UserContext = Depends(get_current_user),
    repo: SQLiteRepository = Depends(get_repository),
    index: PythonIndexAdapter = Depends(get_index_provider),
):
    """Submit a batch screening request for asynchronous processing."""
    use_case = BatchScreenUseCase(index_provider=index, repository=repo)
    items_data = [{"query": it.query, "query_type": it.query_type.value if it.query_type else "organisation"} for it in req.items]
    sub = use_case.submit_batch(items_data, user)

    # Process batch synchronously for simplicity in Canary.1
    use_case.process_batch(sub["batch_id"], items_data, user)

    return BatchSubmissionResponse(
        batch_id=sub["batch_id"],
        status="ACCEPTED",
        total_items=sub["total_items"],
        created_at=sub["created_at"],
        message=sub["message"],
    )


@router.get("/api/v1/batch/{batch_id}", response_model=BatchStatusResponse, tags=["Batch Screening"])
def get_batch_status(
    batch_id: str,
    user: UserContext = Depends(get_current_user),
    repo: SQLiteRepository = Depends(get_repository),
    index: PythonIndexAdapter = Depends(get_index_provider),
):
    """Retrieve progress and results of a submitted batch screening job."""
    use_case = BatchScreenUseCase(index_provider=index, repository=repo)
    job = use_case.get_batch(batch_id, user)
    if not job:
        raise KeyError(f"Batch job '{batch_id}' not found.")

    return BatchStatusResponse(
        batch_id=job["batch_id"],
        user_id=job["user_id"],
        total_items=job["total_items"],
        processed_items=job["processed_items"],
        status=job["status"],
        results=job.get("results", []),
    )


@router.post("/api/v1/ownership", tags=["Ownership"])
def create_ownership_check(
    req: OwnershipCreateRequest,
    user: UserContext = Depends(get_current_user),
    repo: SQLiteRepository = Depends(get_repository),
):
    """Submit corporate ownership structure for 50% Rule and UBO evaluation."""
    use_case = OwnershipCheckUseCase(repository=repo)
    holdings_dict = [h.model_dump() for h in req.holdings]
    return use_case.create_check(
        target_name=req.target_name,
        holdings=holdings_dict,
        user=user,
    )


@router.get("/api/v1/ownership/{check_id}", tags=["Ownership"])
def get_ownership_check(
    check_id: int,
    user: UserContext = Depends(get_current_user),
    repo: SQLiteRepository = Depends(get_repository),
):
    """Retrieve ownership check details and historical audit trail."""
    use_case = OwnershipCheckUseCase(repository=repo)
    check = use_case.get_check(check_id, user)
    if not check:
        raise KeyError(f"Ownership check {check_id} not found.")
    return check


@router.post("/api/v1/ownership/{check_id}/submit", tags=["Ownership"])
def submit_ownership_check(
    check_id: int,
    user: UserContext = Depends(get_current_user),
    repo: SQLiteRepository = Depends(get_repository),
):
    """Submit draft ownership check for reviewer disposition."""
    use_case = OwnershipCheckUseCase(repository=repo)
    return use_case.submit_check(check_id, user)


@router.post("/api/v1/ownership/{check_id}/review", tags=["Ownership"])
def review_ownership_check(
    check_id: int,
    req: OwnershipReviewRequest,
    user: UserContext = Depends(get_current_user),
    repo: SQLiteRepository = Depends(get_repository),
):
    """Review and dispose ownership check with strict four-eyes maker-checker enforcement."""
    use_case = OwnershipCheckUseCase(repository=repo)
    return use_case.review_check(
        check_id=check_id,
        decision=req.decision,
        comment=req.comment,
        user=user,
    )


@router.post("/api/v1/country", response_model=CountryCheckResponse, tags=["Country Risk"])
def check_country_risk(
    req: CountryCheckRequest,
    user: UserContext = Depends(get_current_user),
    repo: SQLiteRepository = Depends(get_repository),
):
    """Evaluate country risk against FATF Black/Grey lists and Comprehensive Sanctions."""
    use_case = CountryCheckUseCase(repository=repo)
    res = use_case.execute(query=req.country, user=user, iso_code=req.iso_code)
    return CountryCheckResponse(
        country_name=res.country_name,
        iso_code=res.iso_code,
        fatf_status=res.fatf_status,
        fatf_statement=res.fatf_statement,
        is_comprehensive_sanctioned=res.is_comprehensive_sanctioned,
        regimes=res.regimes,
        notes=res.notes,
    )


@router.get("/api/v1/records/{source}/{record_id}", tags=["Records"])
def get_full_record(
    source: str,
    record_id: str,
    user: UserContext = Depends(get_current_user),
    repo: SQLiteRepository = Depends(get_repository),
    index: PythonIndexAdapter = Depends(get_index_provider),
):
    """Retrieve full structured 13-section record for an entity by source and ID."""
    use_case = FullRecordUseCase(repository=repo, index_provider=index)
    rec = use_case.execute(source_id=source, record_id=record_id, user=user)
    if not rec:
        raise KeyError(f"Record '{record_id}' not found in source '{source}'.")
    return rec


@router.get("/api/v1/sources", tags=["Sources"])
def get_source_status(
    user: UserContext = Depends(get_current_user),
    index: PythonIndexAdapter = Depends(get_index_provider),
):
    """Retrieve publication dates and counts for all active regulatory lists."""
    use_case = SourceStatusUseCase(index_provider=index)
    return use_case.execute(user)


@router.post("/api/v1/reports/pdf", tags=["Reports"])
def generate_pdf_report(
    payload: Dict[str, Any],
    user: UserContext = Depends(get_current_user),
):
    """Generate official PDF dossier with mandatory Canary header/footer notices."""
    writer = CanaryPDFWriter()
    use_case = ReportsUseCase(report_writer=writer)
    pdf_bytes = use_case.generate_pdf(payload, user)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=ClearanceCheck_Canary_Report.pdf"},
    )


@router.post("/api/v1/reports/excel", tags=["Reports"])
def generate_excel_report(
    payload: Dict[str, Any],
    user: UserContext = Depends(get_current_user),
):
    """Generate official Excel workbook with mandatory Canary evaluation banner."""
    writer = CanaryExcelWriter()
    use_case = ReportsUseCase(report_writer=writer)
    xlsx_bytes = use_case.generate_excel(payload, user)
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=ClearanceCheck_Canary_Workbook.xlsx"},
    )


@router.get("/health", tags=["Operational"])
def health():
    """Liveness probe."""
    use_case = HealthUseCase()
    return use_case.check_health()


@router.get("/ready", tags=["Operational"])
def ready(
    repo: SQLiteRepository = Depends(get_repository),
    index: PythonIndexAdapter = Depends(get_index_provider),
):
    """Readiness probe checking database connectivity and sanctions index."""
    use_case = HealthUseCase(repository=repo, index_provider=index)
    return use_case.check_readiness()


@router.get("/metrics", tags=["Operational"])
def metrics(
    repo: SQLiteRepository = Depends(get_repository),
    index: PythonIndexAdapter = Depends(get_index_provider),
):
    """Prometheus / JSON metrics probe."""
    use_case = HealthUseCase(repository=repo, index_provider=index)
    return use_case.get_metrics()
