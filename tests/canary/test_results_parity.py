"""
Automated Results Parity Tests for Canary.1 against v1.2.1 baseline.
Asserts 100% parity:
- Identical tiers
- Identical record IDs
- Identical raw scores (4 decimal places)
- Identical reason codes
across baseline queries in reviews/baseline_v1.1.3.json.
"""
import json
import pytest
from pathlib import Path
from starlette.testclient import TestClient

from canary.interfaces.api.app import app
from canary.adapters.identity.oidc_client import MockOIDCProvider

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BASELINE_PATH = PROJECT_ROOT / "reviews" / "baseline_v1.1.3.json"
LIST_NAMES = ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]


@pytest.fixture(scope="module")
def api_client():
    client = TestClient(app)
    mock_idp = MockOIDCProvider()
    token = mock_idp.issue_token("screener_parity", ["Screener"])
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


@pytest.fixture(scope="module")
def baseline_data():
    with open(BASELINE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_baseline_fixture_exists(baseline_data):
    assert len(baseline_data) >= 60


@pytest.mark.parametrize("query_key", [
    # Match / Critical entities
    "Sberbank::organisation",
    "Aeroflot Russian Airlines::airline",
    "Mahan Air::airline",
    "IRGC::organisation",
    "ZTE::organisation",
    "Kim Jong Un::person",
    "Vladimir Putin::person",
    # Clear non-matches / Indian entities
    "Adani Airport Holdings Limited::organisation",
    "Jaipur International Airport Limited::organisation",
    "Air India::organisation",
    "Tata Steel::organisation",
    "Rajesh Kumar::person",
    # Script variations
    "Сбербанк::organisation",
    "طيران ماهان::airline",
])
def test_parity_critical_queries(api_client, baseline_data, query_key):
    """Verify exact match on tiers, scores, IDs, and reason codes for critical queries."""
    entry = baseline_data[query_key]
    query = entry["query"]
    q_type = entry.get("query_type", "organisation")

    resp = api_client.post("/api/v1/screen", json={"query": query, "query_type": q_type})
    assert resp.status_code == 200
    api_data = resp.json()
    api_lists = api_data.get("lists", {})

    for l_name in LIST_NAMES:
        base_hit = entry.get("lists", {}).get(l_name, {})
        api_hit = api_lists.get(l_name, {})

        base_tier = base_hit.get("tier", "NO_MATCH")
        api_tier = api_hit.get("tier", "NO_MATCH")
        assert api_tier == base_tier, f"Query '{query}' list '{l_name}' tier mismatch: {api_tier} != {base_tier}"

        base_score = round(float(base_hit.get("score", 0.0)), 4)
        api_score = round(float(api_hit.get("score", 0.0)), 4)
        assert abs(api_score - base_score) < 0.0001, (
            f"Query '{query}' list '{l_name}' score mismatch: {api_score} != {base_score}"
        )

        base_id = str(base_hit.get("source_id", "—"))
        api_id = str(api_hit.get("source_id", "—"))
        assert api_id == base_id, f"Query '{query}' list '{l_name}' source_id mismatch: {api_id} != {base_id}"

        base_reason = base_hit.get("reason", "none")
        api_reason = api_hit.get("reason", "none")
        assert api_reason == base_reason, (
            f"Query '{query}' list '{l_name}' reason mismatch: {api_reason} != {base_reason}"
        )


def test_full_baseline_60_query_parity(api_client, baseline_data):
    """Run all 60 queries in baseline_v1.1.3.json and assert zero differences."""
    mismatches = []
    for key, entry in baseline_data.items():
        query = entry["query"]
        q_type = entry.get("query_type", "organisation")

        resp = api_client.post("/api/v1/screen", json={"query": query, "query_type": q_type})
        assert resp.status_code == 200
        api_data = resp.json()
        api_lists = api_data.get("lists", {})

        for l_name in LIST_NAMES:
            base_hit = entry.get("lists", {}).get(l_name, {})
            api_hit = api_lists.get(l_name, {})

            base_tier = base_hit.get("tier", "NO_MATCH")
            api_tier = api_hit.get("tier", "NO_MATCH")

            base_score = round(float(base_hit.get("score", 0.0)), 4)
            api_score = round(float(api_hit.get("score", 0.0)), 4)

            base_id = str(base_hit.get("source_id", "—"))
            api_id = str(api_hit.get("source_id", "—"))

            base_reason = base_hit.get("reason", "none")
            api_reason = api_hit.get("reason", "none")

            if base_tier != api_tier or abs(base_score - api_score) >= 0.0001 or base_id != api_id or base_reason != api_reason:
                mismatches.append({
                    "query": query,
                    "list": l_name,
                    "expected": {"tier": base_tier, "score": base_score, "id": base_id, "reason": base_reason},
                    "got": {"tier": api_tier, "score": api_score, "id": api_id, "reason": api_reason},
                })

    assert len(mismatches) == 0, f"Found {len(mismatches)} parity mismatches: {mismatches[:3]}"
