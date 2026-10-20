"""Unit tests for modules.aviation.client and modules.aviation.parser."""

import pytest
from pathlib import Path
from modules.aviation.client import AviationClient, SAFETY_LABEL
from modules.aviation.parser import (
    parse_bis_aircraft,
    parse_eu_air_safety_list,
    parse_faa_iasa,
)


@pytest.fixture(scope="module")
def aviation_client():
    return AviationClient()


def test_bis_aircraft_ra73093_current_tail(aviation_client):
    """RA-73093 tested individually must return 🔴 EXPORT_CONTROL."""
    res = aviation_client.check_aircraft(registration="RA-73093")
    assert res["tier_icon"] == "🔴"
    assert res["finding"] == "EXPORT_CONTROL"
    assert res["record"]["current_tail_number"] == "RA-73093"
    assert res["record"]["owner_operator"] == "Aeroflot"
    assert res["safety_label"] == SAFETY_LABEL


def test_bis_aircraft_vpbcd_previous_tail(aviation_client):
    """VP-BCD (previous tail of RA-73093) tested individually must return 🔴 EXPORT_CONTROL."""
    res = aviation_client.check_aircraft(registration="VP-BCD")
    assert res["tier_icon"] == "🔴"
    assert res["finding"] == "EXPORT_CONTROL"
    assert res["record"]["previous_tail_number"] == "VP-BCD"
    assert res["record"]["current_tail_number"] == "RA-73093"
    assert res["safety_label"] == SAFETY_LABEL


def test_bis_aircraft_41215_msn(aviation_client):
    """41215 (MSN of RA-73093) tested individually must return 🔴 EXPORT_CONTROL."""
    res = aviation_client.check_aircraft(msn="41215")
    assert res["tier_icon"] == "🔴"
    assert res["finding"] == "EXPORT_CONTROL"
    assert res["record"]["msn"] == "41215"
    assert res["record"]["current_tail_number"] == "RA-73093"
    assert res["safety_label"] == SAFETY_LABEL


def test_bis_aircraft_removals_never_match(aviation_client):
    """Aircraft officially in removals section must never match as active."""
    # Belavia EW-254PA, MSN 26294 was in Removals section
    res_reg = aviation_client.check_aircraft(registration="EW-254PA")
    assert res_reg["tier_icon"] == "⚪"
    assert res_reg["tier"] == "NO_MATCH"

    res_msn = aviation_client.check_aircraft(msn="26294")
    assert res_msn["tier_icon"] == "⚪"
    assert res_msn["tier"] == "NO_MATCH"


def test_eu_air_safety_list_aeroflot(aviation_client):
    """Aeroflot must flag Annex A operating ban with safety label."""
    res = aviation_client.check_airline(name="Aeroflot")
    assert res["tier_icon"] == "⚠️"
    annex_a_findings = [f for f in res["findings"] if f["finding"] == "SAFETY_BAN"]
    assert len(annex_a_findings) > 0
    for f in res["findings"]:
        assert f["safety_label"] == "Safety flag — not a sanctions finding"


def test_eu_air_safety_list_s7(aviation_client):
    """S7 must resolve to Siberia Airlines and flag Annex A operating ban."""
    res = aviation_client.check_airline(name="S7")
    assert res["tier_icon"] == "⚠️"
    annex_a_findings = [f for f in res["findings"] if f["finding"] == "SAFETY_BAN"]
    assert len(annex_a_findings) > 0
    assert any("SIBERIA AIRLINES" in f.get("airline", "") for f in annex_a_findings)
    for f in res["findings"]:
        assert f["safety_label"] == "Safety flag — not a sanctions finding"


def test_eu_air_safety_list_azur_air(aviation_client):
    """Azur Air (Russian carrier) must flag Annex A / state ban with safety label."""
    res = aviation_client.check_airline(name="Azur Air")
    assert res["tier_icon"] == "⚠️"
    ban_findings = [f for f in res["findings"] if f["finding"] == "SAFETY_BAN"]
    assert len(ban_findings) > 0
    for f in res["findings"]:
        assert f["safety_label"] == "Safety flag — not a sanctions finding"


def test_eu_air_safety_list_iran_air_annex_b(aviation_client):
    """Iran Air must flag Annex B with permitted aircraft types."""
    res = aviation_client.check_airline(name="Iran Air")
    assert res["tier_icon"] == "⚠️"
    annex_b_findings = [f for f in res["findings"] if f["finding"] == "SAFETY_RESTRICTED"]
    assert len(annex_b_findings) == 1
    finding = annex_b_findings[0]
    assert "Fokker F100" in finding["restricted_aircraft_types"]
    assert "Boeing B747" in finding["restricted_aircraft_types"]
    assert finding["permitted_aircraft_types"]
    assert finding["safety_label"] == "Safety flag — not a sanctions finding"


def test_faa_iasa_russia_venezuela_category_2(aviation_client):
    """Russia and Venezuela must return ⚠️ SAFETY_OVERSIGHT with exact label."""
    res_ru = aviation_client.check_airline(name="Generic Carrier", aoc_state="Russia")
    assert res_ru["tier_icon"] == "⚠️"
    oversight_ru = [f for f in res_ru["findings"] if f["finding"] == "SAFETY_OVERSIGHT"]
    assert len(oversight_ru) == 1
    assert oversight_ru[0]["country"] == "Russia"
    assert oversight_ru[0]["category"] == "2"
    assert oversight_ru[0]["safety_label"] == "Safety flag — not a sanctions finding"

    res_ve = aviation_client.check_airline(name="Generic Carrier", aoc_state="Venezuela")
    assert res_ve["tier_icon"] == "⚠️"
    oversight_ve = [f for f in res_ve["findings"] if f["finding"] == "SAFETY_OVERSIGHT"]
    assert len(oversight_ve) == 1
    assert oversight_ve[0]["country"] == "Venezuela"
    assert oversight_ve[0]["category"] == "2"
    assert oversight_ve[0]["safety_label"] == "Safety flag — not a sanctions finding"


def test_clean_aircraft_and_airline(aviation_client):
    """IndiGo and VT- registrations must return clean ⚪ without flags."""
    res_airline = aviation_client.check_airline(name="IndiGo", icao="IGO")
    assert res_airline["tier_icon"] == "⚪"
    assert len(res_airline["findings"]) == 0

    res_aircraft = aviation_client.check_aircraft(registration="VT-IFR")
    assert res_aircraft["tier_icon"] == "⚪"
    assert res_aircraft["finding"] == "CLEAN"


def test_resiliency_malformed_file_or_parse_failure():
    """Simulate parse failure or malformed file: must return ⚪ without unhandled exceptions."""
    non_existent = Path("data/aviation/does_not_exist.pdf")
    res_bis = parse_bis_aircraft(non_existent)
    assert res_bis == {"active": [], "removals": []}

    res_eu = parse_eu_air_safety_list(non_existent)
    assert res_eu == {"annex_a": [], "annex_b": [], "banned_states": []}

    res_faa = parse_faa_iasa(non_existent)
    assert res_faa == []

    # Corrupt empty file
    corrupt = Path("scratch/corrupt.pdf")
    corrupt.write_text("Not a real PDF file contents")
    assert parse_bis_aircraft(corrupt) == {"active": [], "removals": []}
    assert parse_eu_air_safety_list(corrupt) == {"annex_a": [], "annex_b": [], "banned_states": []}
    assert parse_faa_iasa(corrupt) == []
