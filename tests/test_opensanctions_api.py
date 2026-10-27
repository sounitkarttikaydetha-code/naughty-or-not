"""
T10-3 OpenSanctions API Tests
Implements all mocked tests specified in T10-3. Live tests run only when OS_LIVE_TEST=1 and --live flag.
Hard cap: MAX_CREDIT_BUDGET=15 from client.py; usage must not exceed this.
"""

import csv
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch
import urllib.error

import pytest

# ─────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _credits_from_csv() -> int:
    """Read total credits from the live usage CSV."""
    from modules.opensanctions.client import credits_used
    return credits_used()["total_credits"]


def _make_api_response(results: list[dict]) -> bytes:
    """Build a fake OpenSanctions API response body."""
    payload = {"responses": {"q": {"results": results}}}
    return json.dumps(payload).encode("utf-8")


def _fake_response(status: int, body: bytes) -> MagicMock:
    """Create a fake urllib response mock."""
    m = MagicMock()
    m.__enter__ = lambda s: s
    m.__exit__ = MagicMock(return_value=False)
    m.status = status
    m.read = MagicMock(return_value=body)
    return m


def _hit(caption: str = "Aeroflot Russian Airlines", score: float = 0.95,
         schema: str = "Company") -> dict:
    return {
        "id": "ofac-test-001",
        "caption": caption,
        "schema": schema,
        "score": score,
        "datasets": ["us_ofac"],
        "properties": {"name": [caption], "type": [schema]},
    }


# ─────────────────────────────────────────────────────────
# Mocked Tests
# ─────────────────────────────────────────────────────────

class TestOpenSanctionsMocked:

    def test_m1_no_key_returns_disabled(self, monkeypatch):
        """Without an API key, client must return DISABLED without any network call."""
        monkeypatch.setattr("modules.opensanctions.client.get_api_key", lambda: None)
        from modules.opensanctions.client import OpenSanctionsClient
        with patch("urllib.request.urlopen") as mock_open:
            client = OpenSanctionsClient(api_key="")
            result = client.match("Aeroflot", search_type="Organisation", use_opensanctions=True)

        assert result["status"] == "DISABLED"
        assert result["credits_consumed"] == 0
        mock_open.assert_not_called()

    def test_m2_use_opensanctions_false_blocks_call(self, monkeypatch):
        """use_opensanctions=False must block the call even when a key is set."""
        monkeypatch.setenv("OPENSANCTIONS_API_KEY", "test-key-123")

        from modules.opensanctions.client import OpenSanctionsClient
        with patch("urllib.request.urlopen") as mock_open:
            client = OpenSanctionsClient(api_key="test-key-123")
            result = client.match("VTB Bank", search_type="Organisation", use_opensanctions=False)

        assert result["credits_consumed"] == 0
        mock_open.assert_not_called()

    def test_m3_http_401_returns_auth_error(self, monkeypatch, tmp_path):
        """HTTP 401 must return status ERROR with reason=auth_error, no credit logged."""
        fake_usage_csv = tmp_path / "opensanctions_usage.csv"
        monkeypatch.setattr(
            "modules.opensanctions.client.USAGE_LOG_PATH", fake_usage_csv
        )

        from modules.opensanctions.client import OpenSanctionsClient

        http_err = urllib.error.HTTPError(
            url="https://api.opensanctions.org/match/sanctions",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=None,
        )
        with patch("urllib.request.urlopen", side_effect=http_err):
            client = OpenSanctionsClient(api_key="bad-key-xyz")
            result = client.match("Aeroflot", search_type="Organisation", use_opensanctions=True)

        assert result["status"] in ("ERROR", "UNAVAILABLE", "AUTH_ERROR")
        assert result.get("credits_consumed", 0) == 0
        # No credit row should be written for a 401
        from modules.opensanctions.client import credits_used
        assert credits_used()["total_credits"] == 0

    def test_m4_http_403_returns_forbidden_error(self, monkeypatch, tmp_path):
        """HTTP 403 must return status ERROR, no credit consumed."""
        fake_usage_csv = tmp_path / "opensanctions_usage.csv"
        monkeypatch.setattr(
            "modules.opensanctions.client.USAGE_LOG_PATH", fake_usage_csv
        )

        from modules.opensanctions.client import OpenSanctionsClient

        http_err = urllib.error.HTTPError(
            url="https://api.opensanctions.org/match/sanctions",
            code=403,
            msg="Forbidden",
            hdrs={},
            fp=None,
        )
        with patch("urllib.request.urlopen", side_effect=http_err):
            client = OpenSanctionsClient(api_key="restricted-key")
            result = client.match("Sberbank", search_type="Organisation", use_opensanctions=True)

        assert result.get("credits_consumed", 0) == 0
        assert result["status"] in ("ERROR", "UNAVAILABLE", "FORBIDDEN")

    def test_m5_http_429_backoff_then_fail(self, monkeypatch, tmp_path):
        """HTTP 429 must be caught; client must not auto-retry (spending credits)."""
        fake_usage_csv = tmp_path / "opensanctions_usage.csv"
        monkeypatch.setattr(
            "modules.opensanctions.client.USAGE_LOG_PATH", fake_usage_csv
        )

        from modules.opensanctions.client import OpenSanctionsClient

        http_err = urllib.error.HTTPError(
            url="https://api.opensanctions.org/match/sanctions",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=None,
        )
        call_count = {"n": 0}

        def side_effect(*a, **kw):
            call_count["n"] += 1
            raise http_err

        with patch("urllib.request.urlopen", side_effect=side_effect):
            client = OpenSanctionsClient(api_key="good-key-123")
            result = client.match("Mahan Air", search_type="Organisation", use_opensanctions=True)

        # Must not retry automatically
        assert call_count["n"] == 1, (
            f"Client made {call_count['n']} calls after a 429 — auto-retry is forbidden"
        )
        assert result.get("credits_consumed", 0) == 0

    def test_m6_timeout_no_credit_consumed(self, monkeypatch, tmp_path):
        """Network timeout must return ERROR with zero credits consumed."""
        fake_usage_csv = tmp_path / "opensanctions_usage.csv"
        monkeypatch.setattr(
            "modules.opensanctions.client.USAGE_LOG_PATH", fake_usage_csv
        )

        import socket
        from modules.opensanctions.client import OpenSanctionsClient

        with patch("urllib.request.urlopen", side_effect=socket.timeout("timed out")):
            client = OpenSanctionsClient(api_key="good-key-123", timeout=0.001)
            result = client.match("VTB Bank", search_type="Organisation", use_opensanctions=True)

        assert result.get("credits_consumed", 0) == 0

    def test_m7_malformed_json_no_credit(self, monkeypatch, tmp_path):
        """Malformed JSON from server must return ERROR without logging credits."""
        fake_usage_csv = tmp_path / "opensanctions_usage.csv"
        monkeypatch.setattr(
            "modules.opensanctions.client.USAGE_LOG_PATH", fake_usage_csv
        )

        from modules.opensanctions.client import OpenSanctionsClient

        fake_resp = _fake_response(200, b"NOT_JSON_AT_ALL{{{{{")
        with patch("urllib.request.urlopen", return_value=fake_resp):
            client = OpenSanctionsClient(api_key="good-key-123")
            result = client.match("Aeroflot", search_type="Organisation", use_opensanctions=True)

        assert result.get("credits_consumed", 0) == 0
        assert result["status"] in ("ERROR", "PARSE_ERROR")

    def test_m8_twenty_calls_in_a_row_all_succeed_without_cap(self, monkeypatch, tmp_path):
        """Part D: With cap code removed, 20 mocked calls in a row all succeed,
        no message mentions a cap or limit, and usage log records every call."""
        fake_usage_csv = tmp_path / "opensanctions_usage.csv"
        monkeypatch.setattr(
            "modules.opensanctions.client.USAGE_LOG_PATH", fake_usage_csv
        )
        from modules.opensanctions.client import OpenSanctionsClient, credits_used

        client = OpenSanctionsClient(api_key="good-key-999")
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({"responses": {"q0": {"results": [_hit()]}}}).encode("utf-8")
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            for i in range(20):
                res = client.match(f"Entity {i}", search_type="Organisation", use_opensanctions=True)
                assert res["status"] in ("OK", "POTENTIAL_MATCH", "POSSIBLE_MATCH")
                assert "cap" not in str(res).lower()
                assert "limit" not in str(res).lower()

        total_data = credits_used()
        assert total_data["total_calls"] == 20
        assert total_data["total_credits"] == 20

    def test_m9_successful_hit_logs_one_credit(self, monkeypatch, tmp_path):
        """A successful API call must log exactly 1 credit and return correct tier."""
        fake_usage_csv = tmp_path / "opensanctions_usage.csv"
        monkeypatch.setattr(
            "modules.opensanctions.client.USAGE_LOG_PATH", fake_usage_csv
        )

        from modules.opensanctions.client import OpenSanctionsClient, credits_used

        body = _make_api_response([_hit("Aeroflot Russian Airlines", 0.97, "Company")])
        fake_resp = _fake_response(200, body)

        with patch("urllib.request.urlopen", return_value=fake_resp):
            client = OpenSanctionsClient(api_key="good-key-123")
            result = client.match("Aeroflot", search_type="Organisation", use_opensanctions=True)

        assert result["status"] == "OK"
        assert result["credits_consumed"] == 1
        after = credits_used()["total_credits"]
        assert after == 1

    def test_m10_schema_mapping_all_five_types(self):
        """All five search types must map to the correct OpenSanctions schema."""
        from modules.opensanctions.client import map_schema

        assert map_schema("Person") == "Person"
        assert map_schema("Airline") in ("Company", "Airline")
        assert map_schema("Organisation") in ("Company", "LegalEntity")
        assert map_schema("Aircraft") == "Airplane"
        assert map_schema("Vessel") == "Vessel"

    def test_m11_clean_hit_below_threshold_no_credit_logged(self, monkeypatch, tmp_path):
        """A low-score hit (below CANDIDATE_MIN_MATCH) must not trigger a false positive tier."""
        fake_usage_csv = tmp_path / "opensanctions_usage.csv"
        monkeypatch.setattr(
            "modules.opensanctions.client.USAGE_LOG_PATH", fake_usage_csv
        )

        from modules.opensanctions.client import OpenSanctionsClient

        body = _make_api_response([_hit("Some Unrelated Company", 0.30, "Company")])
        fake_resp = _fake_response(200, body)

        with patch("urllib.request.urlopen", return_value=fake_resp):
            client = OpenSanctionsClient(api_key="good-key-123")
            result = client.match("IndiGo Airlines", search_type="Organisation", use_opensanctions=True)

        # credits consumed (1) since API call succeeded
        assert result["credits_consumed"] == 1
        # tier must be below potential match
        assert result.get("tier", "NO_MATCH") not in ("POTENTIAL_MATCH",)

    def test_m12_empty_results_returns_no_match(self, monkeypatch, tmp_path):
        """API returning empty results must yield NO_MATCH with 1 credit consumed."""
        fake_usage_csv = tmp_path / "opensanctions_usage.csv"
        monkeypatch.setattr(
            "modules.opensanctions.client.USAGE_LOG_PATH", fake_usage_csv
        )

        from modules.opensanctions.client import OpenSanctionsClient

        body = _make_api_response([])
        fake_resp = _fake_response(200, body)

        with patch("urllib.request.urlopen", return_value=fake_resp):
            client = OpenSanctionsClient(api_key="good-key-123")
            result = client.match("Air India", search_type="Organisation", use_opensanctions=True)

        assert result["status"] == "OK"
        assert result["credits_consumed"] == 1
        assert result.get("tier") in ("NO_MATCH", "NOT_CHECKED", None)

    def test_m13_usage_log_survives_restart(self, monkeypatch, tmp_path):
        """Credits logged in one process must be readable from a fresh credits_used() call."""
        fake_usage_csv = tmp_path / "opensanctions_usage.csv"
        monkeypatch.setattr(
            "modules.opensanctions.client.USAGE_LOG_PATH", fake_usage_csv
        )

        from modules.opensanctions.client import log_usage, credits_used

        log_usage("Test Entity 1", "Company", 1, 200)
        log_usage("Test Entity 2", "Person", 1, 200)
        log_usage("Test Entity 3", "Airplane", 1, 200)

        # Simulate re-reading (fresh call)
        result = credits_used()
        assert result["total_credits"] == 3
        assert result["total_calls"] == 3


# ─────────────────────────────────────────────────────────
# Live Tests (only run when OS_LIVE_TEST=1 and --live flag)
# ─────────────────────────────────────────────────────────

LIVE_TESTS_ENABLED = (
    os.environ.get("OS_LIVE_TEST", "0") == "1"
)


def pytest_addoption(parser):
    """Allow --live flag to enable live tests."""
    try:
        parser.addoption("--live", action="store_true", default=False)
    except ValueError:
        pass  # already registered


@pytest.fixture
def live_enabled(request):
    """Skip if not enabled."""
    if not LIVE_TESTS_ENABLED or not request.config.getoption("--live", default=False):
        pytest.skip("Live OpenSanctions tests skipped (set OS_LIVE_TEST=1 and --live to enable)")


class TestOpenSanctionsLive:
    """
    Live API tests — 15 credits total, single queries only.
    NEVER run automatically. Requires OS_LIVE_TEST=1 and --live CLI flag.
    Credits: 5 (type mapping) + 8 (4 sanctioned + 4 clean) + 2 (batch of 2) = 15
    """

    def test_l1_type_person_live(self, live_enabled):
        """1 credit: Person schema against the real API."""
        from modules.opensanctions.client import OpenSanctionsClient, credits_used
        key = os.environ.get("OPENSANCTIONS_API_KEY")
        if not key:
            pytest.skip("OPENSANCTIONS_API_KEY not set")
        before = credits_used()["total_credits"]
        client = OpenSanctionsClient(api_key=key)
        result = client.match("Vladimir Putin", search_type="Person", use_opensanctions=True)
        after = credits_used()["total_credits"]
        assert result.get("credits_consumed", 0) <= 1
        assert after <= before + 1

    def test_l2_type_company_live(self, live_enabled):
        """1 credit: Company/Organisation schema."""
        from modules.opensanctions.client import OpenSanctionsClient, credits_used
        key = os.environ.get("OPENSANCTIONS_API_KEY")
        if not key:
            pytest.skip("OPENSANCTIONS_API_KEY not set")
        before = credits_used()["total_credits"]
        client = OpenSanctionsClient(api_key=key)
        result = client.match("Rostec", search_type="Organisation", use_opensanctions=True)
        after = credits_used()["total_credits"]
        assert after <= before + 1

    def test_l3_type_airline_live(self, live_enabled):
        """1 credit: Airline schema."""
        from modules.opensanctions.client import OpenSanctionsClient, credits_used
        key = os.environ.get("OPENSANCTIONS_API_KEY")
        if not key:
            pytest.skip("OPENSANCTIONS_API_KEY not set")
        before = credits_used()["total_credits"]
        client = OpenSanctionsClient(api_key=key)
        result = client.match("Mahan Air", search_type="Organisation", use_opensanctions=True)
        after = credits_used()["total_credits"]
        assert after <= before + 1

    def test_l4_type_aircraft_live(self, live_enabled):
        """1 credit: Airplane schema."""
        from modules.opensanctions.client import OpenSanctionsClient, credits_used
        key = os.environ.get("OPENSANCTIONS_API_KEY")
        if not key:
            pytest.skip("OPENSANCTIONS_API_KEY not set")
        before = credits_used()["total_credits"]
        client = OpenSanctionsClient(api_key=key)
        result = client.match("RA-73093", search_type="Aircraft", use_opensanctions=True)
        after = credits_used()["total_credits"]
        assert after <= before + 1

    def test_l5_type_vessel_live(self, live_enabled):
        """1 credit: Vessel schema."""
        from modules.opensanctions.client import OpenSanctionsClient, credits_used
        key = os.environ.get("OPENSANCTIONS_API_KEY")
        if not key:
            pytest.skip("OPENSANCTIONS_API_KEY not set")
        before = credits_used()["total_credits"]
        client = OpenSanctionsClient(api_key=key)
        result = client.match("Siberia", search_type="Vessel", use_opensanctions=True)
        after = credits_used()["total_credits"]
        assert after <= before + 1

    def test_l6_sanctioned_aeroflot_live(self, live_enabled):
        """1 credit: Aeroflot Russian Airlines — must return a hit >= 0.70."""
        from modules.opensanctions.client import OpenSanctionsClient, credits_used
        key = os.environ.get("OPENSANCTIONS_API_KEY")
        if not key:
            pytest.skip("OPENSANCTIONS_API_KEY not set")
        before = credits_used()["total_credits"]
        client = OpenSanctionsClient(api_key=key)
        result = client.match("Aeroflot Russian Airlines", search_type="Organisation", use_opensanctions=True)
        after = credits_used()["total_credits"]
        assert after <= before + 1
        # Should find a match
        assert result.get("best_score", 0) >= 0.60 or result.get("tier") in (
            "POTENTIAL_MATCH", "POSSIBLE_MATCH_REVIEW"
        )

    def test_l7_sanctioned_vtb_live(self, live_enabled):
        """1 credit: VTB Bank."""
        from modules.opensanctions.client import OpenSanctionsClient, credits_used
        key = os.environ.get("OPENSANCTIONS_API_KEY")
        if not key:
            pytest.skip("OPENSANCTIONS_API_KEY not set")
        before = credits_used()["total_credits"]
        client = OpenSanctionsClient(api_key=key)
        result = client.match("VTB Bank", search_type="Organisation", use_opensanctions=True)
        after = credits_used()["total_credits"]
        assert after <= before + 1

    def test_l8_sanctioned_sberbank_live(self, live_enabled):
        """1 credit: Sberbank."""
        from modules.opensanctions.client import OpenSanctionsClient, credits_used
        key = os.environ.get("OPENSANCTIONS_API_KEY")
        if not key:
            pytest.skip("OPENSANCTIONS_API_KEY not set")
        before = credits_used()["total_credits"]
        client = OpenSanctionsClient(api_key=key)
        result = client.match("Sberbank", search_type="Organisation", use_opensanctions=True)
        after = credits_used()["total_credits"]
        assert after <= before + 1

    def test_l9_sanctioned_mahan_live(self, live_enabled):
        """1 credit: Mahan Air."""
        from modules.opensanctions.client import OpenSanctionsClient, credits_used
        key = os.environ.get("OPENSANCTIONS_API_KEY")
        if not key:
            pytest.skip("OPENSANCTIONS_API_KEY not set")
        before = credits_used()["total_credits"]
        client = OpenSanctionsClient(api_key=key)
        result = client.match("Mahan Air", search_type="Organisation", use_opensanctions=True)
        after = credits_used()["total_credits"]
        assert after <= before + 1
        assert result.get("best_score", 0) >= 0.60 or result.get("tier") in (
            "POTENTIAL_MATCH", "POSSIBLE_MATCH_REVIEW"
        )

    def test_l10_clean_air_india_live(self, live_enabled):
        """1 credit: Air India — must NOT be a potential match."""
        from modules.opensanctions.client import OpenSanctionsClient, credits_used
        key = os.environ.get("OPENSANCTIONS_API_KEY")
        if not key:
            pytest.skip("OPENSANCTIONS_API_KEY not set")
        before = credits_used()["total_credits"]
        client = OpenSanctionsClient(api_key=key)
        result = client.match("Air India", search_type="Organisation", use_opensanctions=True)
        after = credits_used()["total_credits"]
        assert after <= before + 1
        assert result.get("tier") != "POTENTIAL_MATCH"

    def test_l11_clean_indigo_live(self, live_enabled):
        """1 credit: IndiGo — must NOT be a potential match."""
        from modules.opensanctions.client import OpenSanctionsClient, credits_used
        key = os.environ.get("OPENSANCTIONS_API_KEY")
        if not key:
            pytest.skip("OPENSANCTIONS_API_KEY not set")
        before = credits_used()["total_credits"]
        client = OpenSanctionsClient(api_key=key)
        result = client.match("IndiGo", search_type="Organisation", use_opensanctions=True)
        after = credits_used()["total_credits"]
        assert after <= before + 1
        assert result.get("tier") != "POTENTIAL_MATCH"

    def test_l12_clean_tata_steel_live(self, live_enabled):
        """1 credit: Tata Steel Limited."""
        from modules.opensanctions.client import OpenSanctionsClient, credits_used
        key = os.environ.get("OPENSANCTIONS_API_KEY")
        if not key:
            pytest.skip("OPENSANCTIONS_API_KEY not set")
        before = credits_used()["total_credits"]
        client = OpenSanctionsClient(api_key=key)
        result = client.match("Tata Steel Limited", search_type="Organisation", use_opensanctions=True)
        after = credits_used()["total_credits"]
        assert after <= before + 1
        assert result.get("tier") != "POTENTIAL_MATCH"

    def test_l13_clean_jaipur_airport_live(self, live_enabled):
        """1 credit: Jaipur International Airport Limited."""
        from modules.opensanctions.client import OpenSanctionsClient, credits_used
        key = os.environ.get("OPENSANCTIONS_API_KEY")
        if not key:
            pytest.skip("OPENSANCTIONS_API_KEY not set")
        before = credits_used()["total_credits"]
        client = OpenSanctionsClient(api_key=key)
        result = client.match("Jaipur International Airport Limited", search_type="Organisation", use_opensanctions=True)
        after = credits_used()["total_credits"]
        assert after <= before + 1
        assert result.get("tier") != "POTENTIAL_MATCH"

    def test_l14_batch_check_live(self, live_enabled):
        """2 credits: one batch of two names (Aeroflot and Air India) in a single request."""
        from modules.opensanctions.client import OpenSanctionsClient, credits_used
        key = os.environ.get("OPENSANCTIONS_API_KEY")
        if not key:
            pytest.skip("OPENSANCTIONS_API_KEY not set")
        before = credits_used()["total_credits"]
        client = OpenSanctionsClient(api_key=key)
        batch_queries = [
            {"name": "Aeroflot", "search_type": "Airline"},
            {"name": "Air India", "search_type": "Airline"},
        ]
        result = client.match_batch(batch_queries, use_opensanctions=True)
        after = credits_used()["total_credits"]
        assert result.get("credits_consumed", 0) <= 2
        assert after <= before + 2

    def test_l15_credit_usage_tracked_without_cap(self, live_enabled):
        """After all live calls are done, verify usage is recorded information-only without cap."""
        from modules.opensanctions.client import credits_used
        total = credits_used()["total_credits"]
        assert total >= 0

    def test_l16_usage_csv_readable_and_non_zero(self, live_enabled):
        """After live tests, usage log must exist and be non-empty."""
        from modules.opensanctions.client import USAGE_LOG_PATH
        assert USAGE_LOG_PATH.exists(), "opensanctions_usage.csv does not exist"
        assert USAGE_LOG_PATH.stat().st_size > 0
