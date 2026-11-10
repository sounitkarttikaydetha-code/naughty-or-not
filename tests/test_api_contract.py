"""
API Contract Tests for Clearance Check Canary.
Validates HTTP endpoints and response schemas against docs/api/openapi.yaml.
"""
import json
from pathlib import Path
import pytest
import yaml
from starlette.testclient import TestClient

from canary.interfaces.api.app import app
from canary.adapters.identity.oidc_client import MockOIDCProvider

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OPENAPI_PATH = PROJECT_ROOT / "docs" / "api" / "openapi.yaml"

client = TestClient(app)
mock_idp = MockOIDCProvider()


@pytest.fixture(scope="module")
def openapi_spec():
    assert OPENAPI_PATH.exists(), "docs/api/openapi.yaml does not exist"
    with open(OPENAPI_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_01_openapi_spec_structure(openapi_spec):
    """Verify OpenAPI specification has all required enterprise paths."""
    assert openapi_spec["openapi"].startswith("3.1")
    assert "Clearance Check Canary" in openapi_spec["info"]["title"]
    assert "paths" in openapi_spec

    required_endpoints = [
        "/api/v1/screen",
        "/api/v1/batch",
        "/api/v1/batch/{batch_id}",
        "/api/v1/ownership",
        "/api/v1/ownership/{check_id}",
        "/api/v1/ownership/{check_id}/submit",
        "/api/v1/ownership/{check_id}/review",
        "/api/v1/country",
        "/api/v1/records/{source}/{record_id}",
        "/api/v1/sources",
        "/api/v1/reports/pdf",
        "/api/v1/reports/excel",
        "/health",
        "/ready",
        "/metrics",
    ]
    for ep in required_endpoints:
        assert ep in openapi_spec["paths"], f"Endpoint {ep} missing from OpenAPI specification"


def test_02_health_and_readiness_endpoints():
    """Verify /health and /ready return expected contract and Canary headers."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "UP"
    assert data["version"] == "2.0.1-canary.1"

    # Verify standard canary headers
    assert resp.headers["x-engine-version"] == "2.0.1-canary.1"
    assert "Canary build" in resp.headers["x-canary-notice"]

    resp_ready = client.get("/ready")
    assert resp_ready.status_code == 200
    r_data = resp_ready.json()
    assert r_data["ready"] is True


def test_03_screen_endpoint_contract():
    """Verify POST /api/v1/screen contract with OIDC authentication."""
    token = mock_idp.issue_token("screener1", ["Screener"])
    payload = {
        "query": "Sberbank",
        "query_type": "organisation",
    }
    resp = client.post(
        "/api/v1/screen",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["query"] == "Sberbank"
    assert data["query_type"] == "organisation"
    assert "lists" in data
    assert "us_ofac" in data["lists"]
    assert data["engine_version"] == "2.0.1-canary.1"
    assert "Canary build" in data["canary_notice"]

    # Verify list hit schema
    ofac_hit = data["lists"]["us_ofac"]
    assert "tier" in ofac_hit
    assert "score" in ofac_hit
    assert "primary_name" in ofac_hit
    assert "source_id" in ofac_hit


def test_04_validation_error_rfc7807_problem_details():
    """Verify input validation returns RFC 7807 problem details format without stack traces."""
    token = mock_idp.issue_token("screener1", ["Screener"])
    # Send invalid empty query
    resp = client.post(
        "/api/v1/screen",
        json={"query": "   "},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert resp.headers["content-type"] == "application/problem+json"
    data = resp.json()
    assert data["status"] == 422
    assert "title" in data
    assert "detail" in data
    assert "instance" in data
    assert data["code"] == "VALIDATION_ERROR"
    # Ensure zero traceback in body
    assert "Traceback" not in str(data)


def test_05_sources_endpoint_contract():
    """Verify GET /api/v1/sources returns all 5 mandatory sources."""
    token = mock_idp.issue_token("screener1", ["Screener"])
    resp = client.get("/api/v1/sources", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "sources" in data
    src_ids = [s["source_id"] for s in data["sources"]]
    for expected_src in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]:
        assert expected_src in src_ids


def test_06_country_check_contract():
    """Verify POST /api/v1/country contract."""
    token = mock_idp.issue_token("screener1", ["Screener"])
    resp = client.post(
        "/api/v1/country",
        json={"country": "North Korea", "iso_code": "KP"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["iso_code"] == "KP"
    assert data["fatf_status"] == "Call for Action"
    assert data["is_comprehensive_sanctioned"] is True


def test_07_reports_pdf_and_excel_contract():
    """Verify PDF and Excel report generation endpoints return binary documents."""
    token = mock_idp.issue_token("screener1", ["Screener"])
    report_payload = {
        "query": "Sberbank",
        "lists": {
            "us_ofac": {"tier": "POTENTIAL_MATCH", "score": 0.7790, "matched_name": "Sberbank", "source_id": "18715"}
        }
    }

    # PDF Report
    pdf_resp = client.post(
        "/api/v1/reports/pdf",
        json=report_payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert pdf_resp.content.startswith(b"%PDF")

    # Excel Report
    excel_resp = client.post(
        "/api/v1/reports/excel",
        json=report_payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert excel_resp.status_code == 200
    assert "sheet" in excel_resp.headers["content-type"]
    assert len(excel_resp.content) > 1000
