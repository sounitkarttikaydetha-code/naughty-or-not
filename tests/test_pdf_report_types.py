"""
Test suite covering all 8 PDF report types, original script preservation (Cyrillic, Arabic),
drawn status markers, and error handling ("Copy details for IT").
"""
import pytest
from pathlib import Path
import pypdf
from unittest.mock import patch

from modules.reporting.generator import (
    generate_reports,
    generate_raw_reports,
    ReportGenerationError,
    ReportSelfCheckError,
    _self_check_pdf,
    format_name_with_translit,
)


def test_format_name_with_translit():
    # Cyrillic
    assert format_name_with_translit("Аэрофлот") == "Аэрофлот (Aeroflot)"
    # Arabic
    assert "حماس" in format_name_with_translit("حماس")
    # Latin unchanged
    assert format_name_with_translit("Aeroflot") == "Aeroflot"


def test_report_1_airline_aeroflot_cyrillic(tmp_path):
    """Report 1: Airline search (Aeroflot) with Cyrillic script."""
    cyrillic_name = "Аэрофлот — Российские авиалинии"
    pdf_path, excel_path = generate_reports(
        search_type="Aviation / Aircraft",
        inputs={"name": cyrillic_name, "aircraft_reg": "RA-89014"},
        overall_banner="🔴 POTENTIAL MATCH",
        source_statuses=[{"id": "us_csl", "name": "US CSL", "status": "HIT", "hit_count": 1}],
        sanctions_hits=[{
            "source_list": "us_csl",
            "source_id": "CSL-AERO-001",
            "primary_name": cyrillic_name,
            "matched_name": "Аэрофлот",
            "expanded_from": "AEROFLOT",
            "score": 0.98,
            "tier": "POTENTIAL_MATCH",
            "reason": "Entity List Airline",
        }],
        aviation_hits=[{
            "source": "US BIS Entity List",
            "finding": "EAR_RESTRICTION",
            "detail": "Export restrictions on Russian civil aviation fleet.",
            "note": "General Order No. 4 applies",
        }],
    )
    assert pdf_path.exists()
    reader = pypdf.PdfReader(str(pdf_path))
    full_text = "".join(p.extract_text() or "" for p in reader.pages)
    
    # Verify Cyrillic original script preserved in extracted PDF text
    assert "Аэрофлот" in full_text
    # Verify transliteration in brackets
    assert "Aeroflot" in full_text
    # Verify no raw [RED] tags
    assert "[RED]" not in full_text
    assert "LIKELY" in full_text


def test_report_2_organisation_hamas_arabic(tmp_path):
    """Report 2: Organisation search (HAMAS) with Arabic script."""
    arabic_name = "حركة المقاومة الإسلامية (حماس)"
    pdf_path, excel_path = generate_reports(
        search_type="Organisation",
        inputs={"name": f"HAMAS / {arabic_name}"},
        overall_banner="🔴 POTENTIAL MATCH",
        source_statuses=[{"id": "us_ofac", "name": "US OFAC", "status": "HIT", "hit_count": 1}],
        sanctions_hits=[{
            "source_list": "us_ofac",
            "source_id": "OFAC-HAMAS-01",
            "primary_name": f"HAMAS ({arabic_name})",
            "matched_name": "HAMAS",
            "score": 1.0,
            "tier": "POTENTIAL_MATCH",
            "reason": "SDGT designation",
        }],
    )
    assert pdf_path.exists()
    reader = pypdf.PdfReader(str(pdf_path))
    full_text = "".join(p.extract_text() or "" for p in reader.pages)
    
    # Verify Arabic script preserved in PDF text (either logical or visual RTL character order)
    assert "حماس" in full_text or "سامح" in full_text
    assert any('\u0600' <= c <= '\u06FF' for c in full_text)
    assert "HAMAS" in full_text
    assert "[RED]" not in full_text
    assert "LIKELY" in full_text


def test_report_3_text_search(tmp_path):
    """Report 3: Raw text index search report."""
    results = [
        {"source_list": "us_ofac", "entity_id": "12345", "field": "name", "term": "Gazprom", "snippet": "Gazprom Neft PJSC designated"},
        {"source_list": "eu_csl", "entity_id": "EU-456", "field": "alias", "term": "Gazprom", "snippet": "PJSC Gazprom subsidiaries"},
    ]
    pdf_path, excel_path = generate_raw_reports(
        query="Газпром / Gazprom",
        results=results,
        options={"case_sensitive": False, "sources": ["us_ofac", "eu_csl"]},
    )
    assert pdf_path.exists()
    reader = pypdf.PdfReader(str(pdf_path))
    full_text = "".join(p.extract_text() or "" for p in reader.pages)
    assert "Gazprom" in full_text
    assert "Raw Search Audit Report" in full_text
    assert "Total Matches: 2" in full_text


def test_report_4_manual_check(tmp_path):
    """Report 4: Report with manual official checks recorded."""
    pdf_path, excel_path = generate_reports(
        search_type="Individual",
        inputs={"name": "John Doe"},
        overall_banner="🟠 POSSIBLE MATCH (MANUAL REVIEW)",
        source_statuses=[{"id": "un_csl", "name": "UN SC", "status": "OK", "hit_count": 0}],
        manual_checks=[{
            "timestamp": "2026-11-10 12:00:00 UTC",
            "source_name": "INTERPOL Red Notices",
            "result": "CLEAR",
            "comment": "Checked official portal, no active Red Notice found.",
            "verify_url": "https://www.interpol.int/How-we-work/Notices/Red-Notices",
        }],
    )
    assert pdf_path.exists()
    reader = pypdf.PdfReader(str(pdf_path))
    full_text = "".join(p.extract_text() or "" for p in reader.pages)
    assert "Section D - Manual Official Checks Performed" in full_text
    assert "INTERPOL Red Notices" in full_text
    assert "https://www.interpol.int" in full_text


def test_report_5_country_check(tmp_path):
    """Report 5: Country risk report (FATF jurisdiction)."""
    pdf_path, excel_path = generate_reports(
        search_type="Country / Jurisdiction",
        inputs={"country": "Iran (Islamic Republic of)"},
        overall_banner="🔴 HIGH RISK JURISDICTION",
        source_statuses=[{"id": "fatf", "name": "FATF", "status": "HIT", "hit_count": 1}],
        country_risk_hits=[{
            "country": "Iran",
            "list_type": "FATF Black List",
            "summary": "High-risk jurisdiction subject to call for action.",
            "advisory": "Enhanced due diligence and counter-measures required.",
        }],
    )
    assert pdf_path.exists()
    reader = pypdf.PdfReader(str(pdf_path))
    full_text = "".join(p.extract_text() or "" for p in reader.pages)
    assert "Section C - Country Risk (FATF Jurisdictions)" in full_text
    assert "Iran" in full_text
    assert "FATF Black List" in full_text


def test_report_6_ownership_check(tmp_path):
    """Report 6: Ownership & control structure check (UBO)."""
    ubo_data = {
        "target_name": "Volga Marine Logistics LLC",
        "ofac_verdict": {"verdict_text": "BLOCKED (>=50% aggregate sanctioned ownership)"},
        "eu_verdict": {"verdict_text": "RESTRICTED (Criteria met for control / ownership)"},
        "uk_verdict": {"verdict_text": "RESTRICTED (>50% owned by designated person)"},
        "undisclosed_ownership_pct": 5.0,
    }
    pdf_path, excel_path = generate_reports(
        search_type="ownership",
        inputs={"target_name": "Volga Marine Logistics LLC", "ownership_data": ubo_data},
        overall_banner="🔴 SANCTIONED OWNERSHIP / CONTROL",
        source_statuses=[],
    )
    assert pdf_path.exists()
    reader = pypdf.PdfReader(str(pdf_path))
    full_text = "".join(p.extract_text() or "" for p in reader.pages)
    assert "Section E - Ownership & Control Analysis" in full_text
    assert "Volga Marine Logistics LLC" in full_text
    assert "BLOCKED (>=50% aggregate sanctioned ownership)" in full_text


def test_report_7_self_test_failed():
    """Report 7: Self-test failed session raises ReportSelfCheckError with IT diagnostic details."""
    impossible_hits = [{
        "source_list": "us_ofac",
        "source_id": "NON_EXISTENT_ID_99999",
        "tier": "POTENTIAL_MATCH",
    }]
    pdf_path, _ = generate_reports(
        search_type="Individual",
        inputs={"name": "Test Subject"},
        overall_banner="🔴 POTENTIAL MATCH",
        source_statuses=[],
        sanctions_hits=[{
            "source_list": "us_ofac",
            "source_id": "ACTUAL_ID_11111",
            "primary_name": "Test Subject",
            "tier": "POTENTIAL_MATCH",
        }],
    )
    with pytest.raises(ReportSelfCheckError) as exc_info:
        _self_check_pdf(pdf_path, "Test Subject", impossible_hits)
    
    msg = str(exc_info.value)
    assert "NON_EXISTENT_ID_99999" in msg


def test_report_8_zero_candidates():
    """Report 8: Clean entity with zero candidates."""
    pdf_path, excel_path = generate_reports(
        search_type="Individual",
        inputs={"name": "Alice Clean Individual"},
        overall_banner="✅ NO MATCH (CLEAR)",
        source_statuses=[{"id": "us_ofac", "name": "US OFAC", "status": "OK", "hit_count": 0}],
        sanctions_hits=[],
    )
    assert pdf_path.exists()
    reader = pypdf.PdfReader(str(pdf_path))
    full_text = "".join(p.extract_text() or "" for p in reader.pages)
    assert "Alice Clean Individual" in full_text
    assert "No sanctions candidates found on any active list" in full_text
    assert "NO MATCH" in full_text or "CLEAR" in full_text
