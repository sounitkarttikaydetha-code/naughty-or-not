"""Unit tests for modules.fatf.client and FATF data parity (T8-2)."""

import json
from pathlib import Path
import pytest
from modules.fatf.client import (
    check_country,
    check_plenary_refresh,
    FATFClient,
    SAFETY_LABEL,
    FATF_STATEMENT_DATE,
    BLACK_LIST_COUNTRIES,
    GREY_LIST_COUNTRIES,
    CONFIG_PATH,
)


def test_fatf_json_config_and_plenary():
    """Verify config/fatf.json holds official June 2026 plenary data (19 June 2026)."""
    assert CONFIG_PATH.name == "fatf.json"
    assert FATF_STATEMENT_DATE == "2026-06-19"

    # Exactly 3 black list jurisdictions and 22 grey list jurisdictions
    assert len(BLACK_LIST_COUNTRIES) == 3, f"Expected 3 black list countries, got {len(BLACK_LIST_COUNTRIES)}"
    assert set(BLACK_LIST_COUNTRIES) == {
        "Democratic People's Republic of Korea",
        "Iran",
        "Myanmar",
    }

    assert len(GREY_LIST_COUNTRIES) == 22, f"Expected 22 grey list countries, got {len(GREY_LIST_COUNTRIES)}"

    # Check plenary note and cycle
    refresh_info = check_plenary_refresh()
    assert refresh_info["statement_date"] == "2026-06-19"
    assert "February / June / October" in refresh_info["plenary_cycle"]
    assert "Next plenary: October 2026" in refresh_info["plenary_note"]
    assert "landing_page" in refresh_info["source_urls"]
    assert "high_risk" in refresh_info["source_urls"]
    assert "increased_monitoring" in refresh_info["source_urls"]


def test_fatf_black_list_countries():
    """Iran, Myanmar, and DPRK must return ⚠️ FATF_HIGH_RISK with the required safety label."""
    for c in ["Iran", "Islamic Republic of Iran", "Myanmar", "Burma", "DPRK", "North Korea"]:
        res = check_country(c)
        assert res["tier"] == "POSSIBLE_MATCH_REVIEW"
        assert res["tier_icon"] == "⚠️"
        assert res["finding"] == "FATF_HIGH_RISK"
        assert res["risk_label"] == SAFETY_LABEL
        assert "Call for Action" in res["action"]


def test_fatf_grey_list_countries():
    """22 Jurisdictions under increased monitoring must return ⚠️ FATF_INCREASED_MONITORING."""
    samples = [
        "Kenya",
        "Syria",
        "Bulgaria",
        "Monaco",
        "Haiti",
        "Venezuela",
        "Yemen",
        "Bolivia",
        "Bosnia and Herzegovina",
        "Iraq",
        "British Virgin Islands",
        "Cote d'Ivoire",
        "Democratic Republic of the Congo",
    ]
    for c in samples:
        res = check_country(c)
        assert res["tier"] == "POSSIBLE_MATCH_REVIEW"
        assert res["tier_icon"] == "⚠️"
        assert res["finding"] == "FATF_INCREASED_MONITORING"
        assert res["risk_label"] == SAFETY_LABEL
        assert "Increased Monitoring" in res["action"]


def test_fatf_clean_countries():
    """India and non-listed countries must return ✅ CLEAN. Also jurisdictions removed at June 2026 plenary (Namibia)."""
    clean_countries = ["India", "United States", "France", "Germany", "Japan", "Namibia"]
    for c in clean_countries:
        res = check_country(c)
        assert res["tier"] == "NO_MATCH"
        assert res["tier_icon"] == "✅"
        assert res["finding"] == "CLEAN"
        assert res["risk_label"] == SAFETY_LABEL


def test_fatf_stale_record_returns_white_circle():
    """A stale FATF record (> 45 days since verification) must return ⚪ NOT_CHECKED."""
    # Stale record on direct check
    res = check_country("Iran", is_stale=True)
    assert res["tier"] == "NOT_CHECKED"
    assert res["tier_icon"] == "⚪"
    assert res["finding"] == "STALE_SOURCE"
    assert res["status"] == "STALE"
    assert res["risk_label"] == SAFETY_LABEL

    # Stale record through FATFClient
    client_stale = FATFClient(is_stale=True)
    res_client = client_stale.screen_country("Kenya")
    assert res_client["tier"] == "NOT_CHECKED"
    assert res_client["tier_icon"] == "⚪"
    assert res_client["finding"] == "STALE_SOURCE"
    assert res_client["status"] == "STALE"


def test_exact_safety_label():
    """Every FATF finding must carry exact wording: 'Country risk flag — not a sanctions finding'."""
    assert SAFETY_LABEL == "Country risk flag — not a sanctions finding"
