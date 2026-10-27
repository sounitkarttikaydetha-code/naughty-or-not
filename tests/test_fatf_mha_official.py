"""Acceptance tests for FATF official republications and MHA official discovery (T11.2).
Enforces:
1. FATF parser reads June 2026 HM Treasury fixture (3 call-for-action, 22 increased monitoring).
2. Cross-source disagreement -> ⚪ with difference shown.
3. Republication lag -> 'FATF update due'.
4. MHA discovery reads CTCR fixture, finds 3 schedules.
5. MHA failure falls back to NIA mirror labelled 'via NIA (MHA)'.
6. e-Gazette notification dated after copy -> review flag.
7. Mutation: using an unofficial aggregator as primary source must break/fail.
"""

import pytest
from pathlib import Path
from modules.fatf.republication import (
    parse_hm_treasury_fixture,
    cross_check_fatf_sources,
    evaluate_republication_lag,
)
from modules.india.mha_discovery import (
    parse_ctcr_fixture,
    get_nia_mirror_entry,
    check_egazette_notifications,
)


def test_fatf_hm_treasury_fixture_parsing():
    """FATF parser reads June 2026 HM Treasury notice fixture: 3 call-for-action, 22 increased monitoring."""
    res = parse_hm_treasury_fixture()
    assert res["statement_date"] == "2026-06-19"
    assert "HM Treasury" in res["attribution"]
    assert len(res["black_list"]) == 3
    assert set(res["black_list"]) == {
        "Democratic People's Republic of Korea",
        "Iran",
        "Myanmar",
    }
    assert len(res["grey_list"]) == 22


def test_fatf_cross_source_disagreement():
    """Cross-source disagreement between HM Treasury and IFSCA/FinCEN -> ⚪ with difference shown."""
    # Disagreement simulation
    mock_hmt = {"statement_date": "2026-06-19", "black_list": ["Iran", "DPRK", "Myanmar"], "grey_list": ["Syria", "Yemen"]}
    mock_ifsca = {"statement_date": "2026-06-19", "black_list": ["Iran", "DPRK"], "grey_list": ["Syria", "Yemen", "NewCountry"]}
    
    result = cross_check_fatf_sources(mock_hmt, mock_ifsca)
    assert result["status"] == "DISAGREEMENT"
    assert result["tier_icon"] == "⚪"
    assert "Discrepancy" in result["note"] or "Difference" in result["note"]
    assert "MM" in result["note"] or "Myanmar" in result["note"]


def test_fatf_republication_lag():
    """The republication lag -> 'FATF update due' until a newer notice is found."""
    # Plenary ended 2026-10-30, check on 2026-10-31 with June notice
    lag_status = evaluate_republication_lag(
        current_notice_date="2026-06-22",
        last_plenary_end="2026-10-30",
        as_of_date="2026-10-31",
    )
    assert lag_status["update_due"] is True
    assert "FATF update due" in lag_status["status_label"]


def test_mha_ctcr_discovery_fixture():
    """MHA discovery reads a fixture of the CTCR page and finds all three links."""
    links = parse_ctcr_fixture()
    assert "first_schedule" in links
    assert "fourth_schedule" in links
    assert "unlawful_associations" in links
    assert "List46TerroristOrganisationsWebsite.pdf" in links["first_schedule"]
    assert "individuals-terrorists-fourth-schedule" in links["fourth_schedule"]


def test_mha_fallback_to_nia_mirror():
    """When MHA link fails, NIA mirror is used and labelled 'via NIA (MHA)'."""
    mirror = get_nia_mirror_entry("first_schedule")
    assert mirror["label"] == "via NIA (MHA)"
    assert "nia.mha.gov.in" in mirror["url"]


def test_egazette_notification_after_copy_flags_review():
    """An e-Gazette notification dated after our copy -> a review flag."""
    flag = check_egazette_notifications("2026-09-15")
    assert flag is not None
    assert "UAPA notification after our copy" in flag


def test_unofficial_aggregator_as_primary_source_refused():
    """Mutation: 'use an unofficial aggregator as the primary source' must break a test."""
    from modules.fatf.republication import set_primary_data_source
    
    # Attempting to set an unofficial aggregator as primary data source must fail
    with pytest.raises(PermissionError) as exc_info:
        set_primary_data_source("https://unofficial-aggregator.xyz/api/sanctions")
    assert "Aggregator sites are not permitted as primary data sources" in str(exc_info.value)
