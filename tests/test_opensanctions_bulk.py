"""
Comprehensive Unit Tests for T10-1 & T10-2 OpenSanctions Bulk Gate & Loader.
Validates:
1. API key alone never enables bulk
2. All three gates (flag, permission ref, in-app acknowledgement) required
3. Rejection of unacknowledged or missing reference states
4. Loader runs on synthetic fixtures (1k) with verified 'SYNTHETIC TEST DATA' marker
5. Packaged build refuses fixtures
6. Failure handling: missing file, empty file, corrupt file, malformed rows
"""

import json
import os
import sys
import tempfile
from pathlib import Path
import pytest

from modules.opensanctions.bulk import (
    load_bulk,
    is_bulk_enabled,
    BulkDataDisabledError,
    LICENCE_NOTICE,
)
from modules.reporting.logger import (
    log_bulk_acknowledgement,
    has_user_bulk_acknowledged,
    APP_VERSION,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
FIXTURE_1K = FIXTURES_DIR / "synthetic_os_1k.ftm.json"


def test_gate_key_present_flag_false_refuses(monkeypatch):
    """1. Key present, flag false -> no bulk call, refuses with clear disabled error."""
    monkeypatch.setenv("OPENSANCTIONS_API_KEY", "live-key-xyz123")
    monkeypatch.setenv("OPENSANCTIONS_BULK_ENABLED", "false")
    monkeypatch.delenv("OPENSANCTIONS_BULK_PERMISSION_REF", raising=False)

    assert not is_bulk_enabled(check_ack=False)
    with pytest.raises(BulkDataDisabledError) as exc:
        load_bulk(check_ack=False)
    assert "disabled by default" in str(exc.value)


def test_gate_key_present_flag_true_no_permission_ref_refuses(monkeypatch):
    """2. Key present, flag true, no permission reference -> refuses with clear message."""
    monkeypatch.setenv("OPENSANCTIONS_API_KEY", "live-key-xyz123")
    monkeypatch.setenv("OPENSANCTIONS_BULK_ENABLED", "true")
    monkeypatch.delenv("OPENSANCTIONS_BULK_PERMISSION_REF", raising=False)

    assert not is_bulk_enabled(check_ack=False)
    with pytest.raises(BulkDataDisabledError) as exc:
        load_bulk(check_ack=False)
    assert "OPENSANCTIONS_BULK_PERMISSION_REF" in str(exc.value)


def test_gate_flag_true_and_ref_no_acknowledgement_refuses(monkeypatch):
    """3. Flag true and permission ref set, but no user acknowledgement -> refuses."""
    monkeypatch.setenv("OPENSANCTIONS_BULK_ENABLED", "true")
    monkeypatch.setenv("OPENSANCTIONS_BULK_PERMISSION_REF", "TEST-LIC-2026-REF1")

    # Use a dummy user who has NOT acknowledged
    unack_user = "unacknowledged_analyst_999"
    assert not is_bulk_enabled(user=unack_user, check_ack=True)
    with pytest.raises(BulkDataDisabledError) as exc:
        load_bulk(user=unack_user, check_ack=True)
    assert "in-app acknowledgement" in str(exc.value)


def test_gate_all_three_present_loader_runs(monkeypatch):
    """4. All three present (flag, ref, ack) -> loader runs on synthetic fixture."""
    monkeypatch.setenv("OPENSANCTIONS_BULK_ENABLED", "true")
    monkeypatch.setenv("OPENSANCTIONS_BULK_PERMISSION_REF", "COMMERCIAL-LIC-2026-X1")

    test_user = "test_compliance_officer_42"
    log_bulk_acknowledgement(permission_ref="COMMERCIAL-LIC-2026-X1", user=test_user, app_version=APP_VERSION)

    assert is_bulk_enabled(user=test_user, check_ack=True)
    res = load_bulk(file_path=FIXTURE_1K, user=test_user, check_ack=True)
    assert res["status"] == "OK"
    assert res["entities_loaded"] >= 990  # 1k minus header and 1 malformed row
    assert res["malformed_count"] == 1    # deliberate malformed row at index 500
    assert res["source_label"] == "OpenSanctions (evaluation)"


def test_gate_changing_key_alone_changes_nothing(monkeypatch):
    """5. Changing the API key alone never changes the bulk state."""
    monkeypatch.setenv("OPENSANCTIONS_BULK_ENABLED", "false")
    monkeypatch.delenv("OPENSANCTIONS_BULK_PERMISSION_REF", raising=False)

    # State before key
    state_before = is_bulk_enabled(check_ack=False)
    # Add key
    monkeypatch.setenv("OPENSANCTIONS_API_KEY", "brand-new-key-999")
    state_after = is_bulk_enabled(check_ack=False)
    assert state_before == state_after is False

    # Remove key
    monkeypatch.delenv("OPENSANCTIONS_API_KEY", raising=False)
    state_no_key = is_bulk_enabled(check_ack=False)
    assert state_no_key is False


def test_loader_failure_handling(monkeypatch, tmp_path):
    """Verify clean failure states for missing file, empty file, corrupt file."""
    monkeypatch.setenv("OPENSANCTIONS_BULK_ENABLED", "true")
    monkeypatch.setenv("OPENSANCTIONS_BULK_PERMISSION_REF", "LIC-REF")

    # Missing file
    res_missing = load_bulk(file_path=tmp_path / "nonexistent.json", check_ack=False)
    assert res_missing["status"] == "FILE_NOT_FOUND"
    assert res_missing["tier"] == "NOT_CHECKED"

    # Empty file
    empty_f = tmp_path / "empty.json"
    empty_f.write_text("", encoding="utf-8")
    res_empty = load_bulk(file_path=empty_f, check_ack=False)
    assert res_empty["status"] == "EMPTY_FILE"
    assert res_empty["tier"] == "NOT_CHECKED"

    # Corrupt / non-json file
    corrupt_f = tmp_path / "corrupt.json"
    corrupt_f.write_text("NOT_JSON_AT_ALL_GARBAGE\nANOTHER_CORRUPT_ROW\n", encoding="utf-8")
    res_corrupt = load_bulk(file_path=corrupt_f, check_ack=False)
    assert res_corrupt["entities_loaded"] == 0
    assert res_corrupt["malformed_count"] == 2


def test_packaged_build_refuses_fixtures(monkeypatch):
    """Packaged builds (frozen) strictly refuse test fixtures."""
    monkeypatch.setenv("OPENSANCTIONS_BULK_ENABLED", "true")
    monkeypatch.setenv("OPENSANCTIONS_BULK_PERMISSION_REF", "LIC-REF")
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    with pytest.raises(RuntimeError) as exc:
        load_bulk(file_path=FIXTURE_1K, check_ack=False)
    assert "refused in packaged production releases" in str(exc.value)
