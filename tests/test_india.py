"""Unit tests for modules.india.client and modules.india.parser."""

import pytest
from pathlib import Path
from modules.india.client import IndiaClient
from modules.india.parser import (
    parse_first_schedule,
    parse_fourth_schedule,
    parse_unlawful_associations,
)


@pytest.fixture(scope="module")
def india_client():
    return IndiaClient()


def test_the_resistance_front_with_parent(india_client):
    """'The Resistance Front' must return 🔴 POTENTIAL_MATCH with parent Lashkar-E-Taiba."""
    res = india_client.screen("The Resistance Front")
    assert res["tier_icon"] == "🔴"
    assert res["tier"] == "POTENTIAL_MATCH"
    assert res["top_match"] is not None
    assert res["parent_organization"] == "Lashkar-E-Taiba"
    assert "First Schedule" in res["schedule"]


def test_hafiz_saeed_individual(india_client):
    """'Hafiz Saeed' must return 🔴 POTENTIAL_MATCH (Fourth Schedule individual)."""
    res = india_client.screen("Hafiz Saeed")
    assert res["tier_icon"] == "🔴"
    assert res["tier"] == "POTENTIAL_MATCH"
    assert res["top_match"] is not None
    assert "Fourth Schedule" in res["schedule"]
    assert any("Hafiz Saeed" in (m["matched_name"] or "") for m in res["matches"])


def test_revolutionary_peoples_front_with_parent(india_client):
    """'Revolutionary People's Front' must return 🔴 POTENTIAL_MATCH with parent 'Meitei Extremist Organizations'."""
    res = india_client.screen("Revolutionary People's Front")
    assert res["tier_icon"] == "🔴"
    assert res["tier"] == "POTENTIAL_MATCH"
    assert res["top_match"] is not None
    assert res["parent_organization"] == "Meitei Extremist Organizations"
    assert "Unlawful Associations" in res["schedule"]


def test_campus_front_of_india(india_client):
    """'Campus Front of India' must return 🔴 POTENTIAL_MATCH with parent 'Popular Front of India'."""
    res = india_client.screen("Campus Front of India")
    assert res["tier_icon"] == "🔴"
    assert res["tier"] == "POTENTIAL_MATCH"
    assert res["top_match"] is not None
    assert res["parent_organization"] == "Popular Front of India"
    assert "Unlawful Associations" in res["schedule"]


def test_shahzad_bhatti_network(india_client):
    """'Shahzad Bhatti Network' (#46 in First Schedule) must return 🔴 POTENTIAL_MATCH."""
    res = india_client.screen("Shahzad Bhatti Network")
    assert res["tier_icon"] == "🔴"
    assert res["tier"] == "POTENTIAL_MATCH"
    assert res["top_match"] is not None
    assert res["top_match"]["authority_id"] == "46"
    assert "First Schedule" in res["schedule"]


def test_clean_entities_no_match(india_client):
    """Clean commercial entities like 'Jaipur International Airport Limited' and 'Air India' must return ✅ NO_MATCH."""
    res_airport = india_client.screen("Jaipur International Airport Limited")
    assert res_airport["tier_icon"] == "✅"
    assert res_airport["tier"] == "NO_MATCH"
    assert len(res_airport["matches"]) == 0

    res_airline = india_client.screen("Air India")
    assert res_airline["tier_icon"] == "✅"
    assert res_airline["tier"] == "NO_MATCH"
    assert len(res_airline["matches"]) == 0


def test_visibility_of_parse_failure():
    """If a source fails or file is corrupt, client must return ⚪ NOT_CHECKED with last_good_date."""
    non_existent = Path("data/india/does_not_exist.pdf")
    res_fs = parse_first_schedule(non_existent)
    assert res_fs["status"] == "FAILED"
    assert "File not found" in res_fs["error"]
    assert res_fs["last_good_date"] == "2026-10-01"

    client = IndiaClient(first_schedule_path=non_existent)
    res_screen = client.screen("Hafiz Saeed")
    assert res_screen["tier_icon"] == "⚪"
    assert res_screen["tier"] == "NOT_CHECKED"
    assert res_screen["finding"] == "SOURCE_UNAVAILABLE"
    assert res_screen["last_good_date"] == "2026-10-01"


def test_reconciliation_entity_counts():
    """Verify entity counts against OpenSanctions baseline (80 individuals, 46 base first schedule)."""
    fs = parse_first_schedule()
    assert fs["status"] == "OK"
    assert len(fs["entities"]) >= 46

    ind = parse_fourth_schedule()
    assert ind["status"] == "OK"
    assert len(ind["entities"]) == 80  # Exactly 80 individuals from MHA Fourth Schedule

    unl = parse_unlawful_associations()
    assert unl["status"] == "OK"
    assert len(unl["entities"]) >= 23  # 23 base rows expanded with sub-groups and fronts
