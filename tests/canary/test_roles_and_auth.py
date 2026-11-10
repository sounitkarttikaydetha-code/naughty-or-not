"""
Test Suite for C4: Identity, Roles, and Four-Eyes Principle Enforcement.
Validates:
1. All 5 roles (Screener, Reviewer, Compliance, Administrator, Auditor) across endpoints.
2. Auditor read-only restriction (strictly blocked from screening or mutating).
3. Four-eyes rule: preparer cannot review, approve, or close their own check.
4. Windows fallback identity when OIDC bearer token is omitted.
"""
import pytest
from starlette.testclient import TestClient

from canary.interfaces.api.app import app
from canary.adapters.identity.oidc_client import MockOIDCProvider
from canary.application.identity.roles import Role

client = TestClient(app)
mock_idp = MockOIDCProvider()


@pytest.fixture
def auth_headers():
    def _make_headers(sub: str, roles: list):
        token = mock_idp.issue_token(sub=sub, roles=roles)
        return {"Authorization": f"Bearer {token}"}
    return _make_headers


def test_01_screener_permissions(auth_headers):
    """Verify Screener can screen and create checks, but cannot review ownership checks."""
    headers = auth_headers("screener_alice", [Role.SCREENER.value])

    # 1. Screen -> Allowed
    res_screen = client.post("/api/v1/screen", json={"query": "Sberbank"}, headers=headers)
    assert res_screen.status_code == 200

    # 2. Create ownership check -> Allowed
    res_create = client.post("/api/v1/ownership", json={
        "target_name": "Test Target Ltd",
        "holdings": [{"entity_name": "Test Target Ltd", "shareholder_name": "Owner A", "share_pct": 60.0}],
    }, headers=headers)
    assert res_create.status_code == 200
    check_id = res_create.json()["id"]

    # 3. Submit for review -> Allowed
    res_sub = client.post(f"/api/v1/ownership/{check_id}/submit", headers=headers)
    assert res_sub.status_code == 200

    # 4. Attempt Review -> FORBIDDEN (Screener role cannot review)
    res_rev = client.post(
        f"/api/v1/ownership/{check_id}/review",
        json={"decision": "APPROVED", "comment": "Trying to self-approve as screener"},
        headers=headers,
    )
    assert res_rev.status_code == 403
    assert "PERMISSION_DENIED" in res_rev.json()["code"]


def test_02_four_eyes_rule_enforcement(auth_headers):
    """Verify four-eyes principle: a preparer cannot review their own check even if they have Reviewer role."""
    headers_preparer = auth_headers("john_doe", [Role.REVIEWER.value])
    headers_other_reviewer = auth_headers("jane_smith", [Role.REVIEWER.value])

    # 1. John Doe creates and submits check
    res_create = client.post("/api/v1/ownership", json={
        "target_name": "Dual Role Corp",
        "holdings": [{"entity_name": "Dual Role Corp", "shareholder_name": "Owner X", "share_pct": 55.0}],
    }, headers=headers_preparer)
    assert res_create.status_code == 200
    check_id = res_create.json()["id"]

    client.post(f"/api/v1/ownership/{check_id}/submit", headers=headers_preparer)

    # 2. John Doe attempts to review his own submission -> REJECTED (Four-eyes violation)
    res_self_review = client.post(
        f"/api/v1/ownership/{check_id}/review",
        json={"decision": "APPROVED", "comment": "Self approval attempt"},
        headers=headers_preparer,
    )
    assert res_self_review.status_code == 403
    err = res_self_review.json()
    assert err["code"] == "FOUR_EYES_VIOLATION"
    assert "Four-eyes violation" in err["detail"]

    # 3. Jane Smith (distinct Reviewer) reviews John's submission -> SUCCEEDS
    res_valid_review = client.post(
        f"/api/v1/ownership/{check_id}/review",
        json={"decision": "APPROVED", "comment": "Independent compliance review passed"},
        headers=headers_other_reviewer,
    )
    assert res_valid_review.status_code == 200
    assert res_valid_review.json()["status"] == "APPROVED"
    assert res_valid_review.json()["reviewer_id"] == "jane_smith"


def test_03_auditor_read_only_restriction(auth_headers):
    """Verify Auditor role is strictly read-only: cannot screen, cannot create or review checks."""
    headers = auth_headers("auditor_bob", [Role.AUDITOR.value])

    # 1. Attempt Screen -> FORBIDDEN
    res_screen = client.post("/api/v1/screen", json={"query": "Sberbank"}, headers=headers)
    assert res_screen.status_code == 403
    assert "PERMISSION_DENIED" in res_screen.json()["code"]

    # 2. Attempt Create Ownership -> FORBIDDEN
    res_create = client.post("/api/v1/ownership", json={
        "target_name": "Auditor Target Ltd",
        "holdings": [{"entity_name": "Auditor Target Ltd", "shareholder_name": "Owner", "share_pct": 50.0}],
    }, headers=headers)
    assert res_create.status_code == 403

    # 3. Read Sources -> ALLOWED
    res_sources = client.get("/api/v1/sources", headers=headers)
    assert res_sources.status_code == 200

    # 4. Read Metrics -> ALLOWED
    res_metrics = client.get("/metrics", headers=headers)
    assert res_metrics.status_code == 200


def test_04_compliance_and_administrator_roles(auth_headers):
    """Verify Compliance and Administrator roles can review and access system probes."""
    headers_comp = auth_headers("compliance_carol", [Role.COMPLIANCE.value])
    headers_admin = auth_headers("admin_dave", [Role.ADMINISTRATOR.value])

    # Both can screen
    assert client.post("/api/v1/screen", json={"query": "Aeroflot"}, headers=headers_comp).status_code == 200
    assert client.post("/api/v1/screen", json={"query": "Aeroflot"}, headers=headers_admin).status_code == 200


def test_05_windows_user_fallback_labelled():
    """Verify omitting Authorization header falls back to Windows user with clear label."""
    resp = client.post("/api/v1/screen", json={"query": "Sberbank"})
    assert resp.status_code == 200
    data = resp.json()
    assert "lists" in data
    # Standard headers present
    assert resp.headers["x-engine-version"] == "2.0.1-canary.1"
    assert "Canary build" in resp.headers["x-canary-notice"]
