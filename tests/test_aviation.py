"""Unit tests for modules.aviation.client and modules.aviation.parser."""

import pytest
from pathlib import Path
from modules.aviation.client import (
    AviationClient,
    SAFETY_LABEL,
    BIS_EXPORT_CONTROL_LABEL,
)
from modules.aviation.parser import (
    parse_bis_aircraft,
    parse_eu_air_safety_list,
    parse_faa_iasa,
)


@pytest.fixture(scope="module")
def aviation_client():
    return AviationClient()


def test_bis_aircraft_ra73093_current_tail(aviation_client):
    """RA-73093 tested individually must return 🔴 EXPORT_CONTROL via tail number with EAR label."""
    res = aviation_client.check_aircraft(registration="RA-73093")
    assert res["tier_icon"] == "🔴"
    assert res["finding"] == "EXPORT_CONTROL"
    assert res["record"]["current_tail_number"] == "RA-73093"
    assert res["record"]["owner_operator"] == "Aeroflot"
    assert res["label"] == BIS_EXPORT_CONTROL_LABEL


def test_bis_aircraft_vpbcd_previous_tail(aviation_client):
    """VP-BCD (previous tail of RA-73093) tested individually must return 🔴 EXPORT_CONTROL."""
    res = aviation_client.check_aircraft(registration="VP-BCD")
    assert res["tier_icon"] == "🔴"
    assert res["finding"] == "EXPORT_CONTROL"
    assert res["record"]["previous_tail_number"] == "VP-BCD"
    assert res["record"]["current_tail_number"] == "RA-73093"
    assert res["label"] == BIS_EXPORT_CONTROL_LABEL


def test_bis_aircraft_msn_rule(aviation_client):
    """MSN rule:
    - MSN only -> 🟠 'confirm aircraft type'
    - MSN + matching type/operator -> 🔴
    """
    # MSN only -> 🟠
    res_msn_only = aviation_client.check_aircraft(msn="41215")
    assert res_msn_only["tier_icon"] == "🟠"
    assert res_msn_only["tier"] == "POSSIBLE_MATCH_REVIEW"
    assert "confirm aircraft type" in res_msn_only["reason"]
    assert res_msn_only["record"]["current_tail_number"] == "RA-73093"
    assert res_msn_only["label"] == BIS_EXPORT_CONTROL_LABEL

    # MSN + matching operator -> 🔴
    res_msn_operator = aviation_client.check_aircraft(msn="41215", operator="Aeroflot")
    assert res_msn_operator["tier_icon"] == "🔴"
    assert res_msn_operator["tier"] == "POTENTIAL_MATCH"
    assert res_msn_operator["label"] == BIS_EXPORT_CONTROL_LABEL

    # MSN + matching aircraft type -> 🔴
    res_msn_type = aviation_client.check_aircraft(msn="41215", aircraft_type="Boeing 737")
    assert res_msn_type["tier_icon"] == "🔴"
    assert res_msn_type["tier"] == "POTENTIAL_MATCH"
    assert res_msn_type["label"] == BIS_EXPORT_CONTROL_LABEL

    # MSN + non-matching aircraft type -> 🟠 (unconfirmed)
    res_msn_wrong_type = aviation_client.check_aircraft(msn="41215", aircraft_type="Airbus A320")
    assert res_msn_wrong_type["tier_icon"] == "🟠"
    assert res_msn_wrong_type["tier"] == "POSSIBLE_MATCH_REVIEW"
    assert res_msn_wrong_type["label"] == BIS_EXPORT_CONTROL_LABEL


def test_bis_aircraft_removals_never_match(aviation_client):
    """Aircraft officially in removals section must never match as active (returns ✅ NO_MATCH, no label)."""
    # Belavia EW-254PA, MSN 26294
    res_reg = aviation_client.check_aircraft(registration="EW-254PA")
    assert res_reg["tier_icon"] == "✅"
    assert res_reg["tier"] == "NO_MATCH"
    assert res_reg["finding"] == "REMOVAL"
    assert res_reg["label"] is None

    res_msn = aviation_client.check_aircraft(msn="26294")
    assert res_msn["tier_icon"] == "✅"
    assert res_msn["tier"] == "NO_MATCH"
    assert res_msn["label"] is None

    # 10 Oct 2025 removal: EW-001PA, MSN 33079
    res_new_rem = aviation_client.check_aircraft(registration="EW-001PA")
    assert res_new_rem["tier_icon"] == "✅"
    assert res_new_rem["tier"] == "NO_MATCH"
    assert res_new_rem["finding"] == "REMOVAL"
    assert res_new_rem["label"] is None

    res_new_msn = aviation_client.check_aircraft(msn="33079")
    assert res_new_msn["tier_icon"] == "✅"
    assert res_new_msn["tier"] == "NO_MATCH"
    assert res_new_msn["label"] is None


def test_eu_air_safety_list_aeroflot(aviation_client):
    """Aeroflot must flag SAFETY_BAN with safety label."""
    res = aviation_client.check_airline(name="Aeroflot")
    assert res["tier_icon"] == "⚠️"
    assert res["tier"] == "SAFETY_BAN"
    annex_a_findings = [f for f in res["findings"] if f["finding"] == "SAFETY_BAN"]
    assert len(annex_a_findings) > 0
    for f in res["findings"]:
        assert f["safety_label"] == SAFETY_LABEL


def test_eu_air_safety_list_s7(aviation_client):
    """S7 must resolve to Siberia Airlines and flag SAFETY_BAN."""
    res = aviation_client.check_airline(name="S7")
    assert res["tier_icon"] == "⚠️"
    assert res["tier"] == "SAFETY_BAN"
    annex_a_findings = [f for f in res["findings"] if f["finding"] == "SAFETY_BAN"]
    assert len(annex_a_findings) > 0
    assert any("SIBERIA AIRLINES" in f.get("airline", "") for f in annex_a_findings)
    for f in res["findings"]:
        assert f["safety_label"] == SAFETY_LABEL


def test_eu_air_safety_list_azur_air_reconciliation(aviation_client):
    """Azur Air reconciliation:
    - Not listed in EU Annex A or Annex B (Russia is not state-wide, 22 Russian airlines named).
    - But FAA IASA flags Russia as Category 2 (⚠️ SAFETY_OVERSIGHT).
    """
    res = aviation_client.check_airline(name="Azur Air")
    assert res["tier_icon"] == "⚠️"
    assert res["tier"] == "SAFETY_OVERSIGHT"

    # Verify EU ASL has NO findings for Azur Air
    eu_findings = [f for f in res["findings"] if "EU Air Safety List" in f.get("source", "")]
    assert len(eu_findings) == 0

    # Verify FAA IASA has the oversight finding
    faa_findings = [f for f in res["findings"] if f["finding"] == "SAFETY_OVERSIGHT"]
    assert len(faa_findings) == 1
    assert faa_findings[0]["country"] == "Russia"
    assert faa_findings[0]["safety_label"] == SAFETY_LABEL


def test_eu_air_safety_list_iran_air_annex_b(aviation_client):
    """Iran Air must flag SAFETY_RESTRICTED (Annex B) with permitted aircraft types."""
    res = aviation_client.check_airline(name="Iran Air")
    assert res["tier_icon"] == "⚠️"
    assert res["tier"] == "SAFETY_RESTRICTED"
    annex_b_findings = [f for f in res["findings"] if f["finding"] == "SAFETY_RESTRICTED"]
    assert len(annex_b_findings) == 1
    finding = annex_b_findings[0]
    assert "Fokker F100" in finding["restricted_aircraft_types"]
    assert "Boeing B747" in finding["restricted_aircraft_types"]
    assert finding["permitted_aircraft_types"]
    assert finding["safety_label"] == SAFETY_LABEL


def test_faa_iasa_russia_venezuela_category_2(aviation_client):
    """Russia and Venezuela must return ⚠️ SAFETY_OVERSIGHT with exact label."""
    res_ru = aviation_client.check_airline(name="Generic Carrier", aoc_state="Russia")
    assert res_ru["tier_icon"] == "⚠️"
    assert res_ru["tier"] == "SAFETY_OVERSIGHT"
    oversight_ru = [f for f in res_ru["findings"] if f["finding"] == "SAFETY_OVERSIGHT"]
    assert len(oversight_ru) == 1
    assert oversight_ru[0]["country"] == "Russia"
    assert oversight_ru[0]["category"] == "2"
    assert oversight_ru[0]["safety_label"] == SAFETY_LABEL

    res_ve = aviation_client.check_airline(name="Generic Carrier", aoc_state="Venezuela")
    assert res_ve["tier_icon"] == "⚠️"
    assert res_ve["tier"] == "SAFETY_OVERSIGHT"
    oversight_ve = [f for f in res_ve["findings"] if f["finding"] == "SAFETY_OVERSIGHT"]
    assert len(oversight_ve) == 1
    assert oversight_ve[0]["country"] == "Venezuela"
    assert oversight_ve[0]["category"] == "2"
    assert oversight_ve[0]["safety_label"] == SAFETY_LABEL


def test_clean_aircraft_and_airline(aviation_client):
    """IndiGo and VT- registrations must return clean ✅ NO_MATCH without flag labels."""
    res_airline = aviation_client.check_airline(name="IndiGo", icao="IGO")
    assert res_airline["tier_icon"] == "✅"
    assert res_airline["tier"] == "NO_MATCH"
    assert len(res_airline["findings"]) == 0
    assert res_airline["safety_label"] is None

    res_aircraft = aviation_client.check_aircraft(registration="VT-IFR")
    assert res_aircraft["tier_icon"] == "✅"
    assert res_aircraft["tier"] == "NO_MATCH"
    assert res_aircraft["finding"] == "CLEAN"
    assert res_aircraft["label"] is None


def test_visibility_of_failures_not_checked():
    """Simulate parse failure / corrupt file: must return ⚪ NOT_CHECKED with last_good_date."""
    non_existent = Path("data/aviation/does_not_exist.pdf")
    res_bis = parse_bis_aircraft(non_existent)
    assert res_bis["status"] == "FAILED"
    assert "File not found" in res_bis["error"]
    assert res_bis["last_good_date"] == "2025-10-10"

    res_eu = parse_eu_air_safety_list(non_existent)
    assert res_eu["status"] == "FAILED"
    assert "File not found" in res_eu["error"]
    assert res_eu["last_good_date"] == "2026-06-09"

    res_faa = parse_faa_iasa(non_existent)
    assert res_faa["status"] == "FAILED"
    assert "File not found" in res_faa["error"]
    assert res_faa["last_good_date"] == "2025-04-18"

    # Client behavior when data failed
    client = AviationClient()
    client.bis_data = res_bis
    res_check = client.check_aircraft(registration="RA-73093")
    assert res_check["tier_icon"] == "⚪"
    assert res_check["tier"] == "NOT_CHECKED"
    assert res_check["finding"] == "SOURCE_UNAVAILABLE"
    assert res_check["last_good_date"] == "2025-10-10"
