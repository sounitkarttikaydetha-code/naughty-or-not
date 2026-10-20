"""Unit tests for OpenSanctions bulk loader guard (Addendum C)."""

import os
import pytest
from modules.opensanctions.bulk import (
    load_bulk,
    is_bulk_enabled,
    BulkDataDisabledError,
    LICENCE_NOTICE,
)


def test_bulk_disabled_by_default(monkeypatch):
    """Bulk loading must be disabled by default and refuse to run."""
    monkeypatch.delenv("OPENSANCTIONS_BULK_ENABLED", raising=False)
    assert not is_bulk_enabled()

    with pytest.raises(BulkDataDisabledError) as exc_info:
        load_bulk()
    assert "CC BY-NC 4.0" in str(exc_info.value)
    assert "commercial use requires a licence" in str(exc_info.value)


def test_bulk_refuses_when_explicitly_false(monkeypatch):
    """When OPENSANCTIONS_BULK_ENABLED is false, bulk loader must refuse to run."""
    monkeypatch.setenv("OPENSANCTIONS_BULK_ENABLED", "false")
    assert not is_bulk_enabled()

    with pytest.raises(BulkDataDisabledError):
        load_bulk()


def test_bulk_allowed_when_enabled(monkeypatch):
    """When OPENSANCTIONS_BULK_ENABLED is true, bulk loader proceeds with licence notice."""
    monkeypatch.setenv("OPENSANCTIONS_BULK_ENABLED", "true")
    assert is_bulk_enabled()

    res = load_bulk()
    assert res["licence_notice"] == LICENCE_NOTICE
