"""Unit tests for modules.fatf.client."""

import pytest
from modules.fatf.client import check_country, SAFETY_LABEL


def test_fatf_black_list_countries():
    """DPRK, Iran, Myanmar must return ⚠️ FATF_HIGH_RISK with the required label."""
    for c in ["DPRK", "North Korea", "Iran", "Myanmar", "Burma"]:
        res = check_country(c)
        assert res["tier_icon"] == "⚠️"
        assert res["finding"] == "FATF_HIGH_RISK"
        assert res["risk_label"] == SAFETY_LABEL
        assert "Call for Action" in res["action"]


def test_fatf_grey_list_countries():
    """Increased monitoring countries (e.g. Kenya, Syria, Bulgaria, Monaco) must return ⚠️ FATF_INCREASED_MONITORING."""
    for c in ["Kenya", "Syria", "Bulgaria", "Monaco", "Haiti", "Venezuela", "Yemen"]:
        res = check_country(c)
        assert res["tier_icon"] == "⚠️"
        assert res["finding"] == "FATF_INCREASED_MONITORING"
        assert res["risk_label"] == SAFETY_LABEL
        assert "Increased Monitoring" in res["action"]


def test_fatf_clean_countries():
    """Non-listed countries like India, United States, France must return ✅ NO_MATCH."""
    for c in ["India", "United States", "France", "Germany", "Japan"]:
        res = check_country(c)
        assert res["tier_icon"] == "✅"
        assert res["finding"] == "CLEAN"
        assert res["risk_label"] == SAFETY_LABEL


def test_exact_safety_label():
    """Every FATF finding must carry exact wording: 'Country risk flag — not a sanctions finding'."""
    assert SAFETY_LABEL == "Country risk flag — not a sanctions finding"


def test_fatf_plenary_refresh_cycle():
    """Verify refresh check tracks the 3 annual plenaries (Feb, June, Oct)."""
    from modules.fatf.client import check_plenary_refresh
    res = check_plenary_refresh()
    assert res["statement_date"] == "2026-06-28"
    assert "February / June / October" in res["plenary_cycle"]
    assert res["status"] == "UP_TO_DATE"
