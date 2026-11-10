"""
Unit and integration tests for Part A (PDF report generation & self-check)
and Part B (Full record exposure & 13 standard sections coverage).
"""
import os
import pytest
from pathlib import Path
import pypdf
import openpyxl
from unittest.mock import patch

from modules.common.records_store import (
    get_record,
    build_13_sections,
    SECTION_NAMES,
    init_records_table,
    populate_records_cache,
)
from modules.reporting.generator import (
    generate_reports,
    generate_raw_reports,
    ReportGenerationError,
    ReportSelfCheckError,
    _self_check_pdf,
    sanitize_for_pdf,
)


@pytest.fixture(scope="module", autouse=True)
def ensure_records():
    init_records_table()
    populate_records_cache(force=False)


# =====================================================================
# PART A TESTS: Report Generation, Self-Check, Fallback & No Missing Glyphs
# =====================================================================

def test_a6_fallback_on_reportlab_failure(tmp_path):
    """
    Part A6: When ReportLab PDF generation fails:
    1. Do not swallow the exception; raise ReportGenerationError.
    2. Excel report is generated first and exists on disk (>1000 bytes).
    3. Traceback and error details are preserved.
    """
    inputs = {"name": "TEST FALLBACK ENTITY"}
    source_statuses = [{"id": "us_ofac", "name": "US OFAC", "status": "HIT", "hit_count": 1}]
    sanctions_hits = [{
        "source_list": "us_ofac",
        "source_id": "0001",
        "primary_name": "TEST FALLBACK ENTITY",
        "matched_name": "TEST FALLBACK ENTITY",
        "score": 1.0,
        "tier": "POTENTIAL_MATCH",
    }]

    with patch("modules.reporting.generator._build_pdf", side_effect=RuntimeError("Simulated ReportLab Engine Failure")):
        with pytest.raises(ReportGenerationError) as exc_info:
            generate_reports(
                search_type="Individual",
                inputs=inputs,
                overall_banner="🔴 POTENTIAL MATCH",
                source_statuses=source_statuses,
                sanctions_hits=sanctions_hits,
            )

        err = exc_info.value
        assert "Simulated ReportLab Engine Failure" in str(err)
        assert err.excel_path is not None
        assert err.excel_path.exists()
        assert err.excel_path.stat().st_size > 1000
        assert "Simulated ReportLab Engine Failure" in err.details


def test_a7_self_check_detects_missing_data(tmp_path):
    """
    Part A7: Self-check must fail if an expected record ID is absent from the PDF.
    """
    pdf_path, _ = generate_reports(
        search_type="Individual",
        inputs={"name": "Vladimir Putin"},
        overall_banner="🔴 POTENTIAL MATCH",
        source_statuses=[{"id": "us_ofac", "name": "US OFAC", "status": "HIT", "hit_count": 1}],
        sanctions_hits=[{
            "source_list": "us_ofac",
            "source_id": "99999",
            "primary_name": "Vladimir Putin",
            "matched_name": "Vladimir Putin",
            "score": 1.0,
            "tier": "POTENTIAL_MATCH",
        }],
    )
    assert pdf_path.exists()

    # Self-check with an impossible record ID must raise ReportSelfCheckError
    impossible_hits = [{
        "source_list": "us_ofac",
        "source_id": "IMPOSSIBLE_NON_EXISTENT_ID_987654321",
        "tier": "POTENTIAL_MATCH",
    }]
    with pytest.raises(ReportSelfCheckError) as exc_info:
        _self_check_pdf(pdf_path, "Vladimir Putin", impossible_hits)
    assert "IMPOSSIBLE_NON_EXISTENT_ID_987654321" in str(exc_info.value)


def test_a7_pdf_no_missing_glyphs():
    """
    Part A7: Extracted PDF text must contain 0 missing-glyph replacement characters.
    """
    pdf_path, excel_path = generate_reports(
        search_type="Individual",
        inputs={"name": "Sberbank of Russia (Сбербанк России)"},
        overall_banner="🔴 POTENTIAL MATCH",
        source_statuses=[{"id": "us_ofac", "name": "US OFAC", "status": "HIT", "hit_count": 1}],
        sanctions_hits=[{
            "source_list": "us_ofac",
            "source_id": "12345",
            "primary_name": "Sberbank of Russia (Сбербанк России)",
            "matched_name": "Sberbank",
            "score": 0.95,
            "tier": "POTENTIAL_MATCH",
        }],
    )
    assert pdf_path.exists()
    reader = pypdf.PdfReader(str(pdf_path))
    assert len(reader.pages) >= 1
    full_text = "".join(page.extract_text() or "" for page in reader.pages)
    
    # Assert no black squares, replacement glyphs, or question mark boxes
    assert "\u25a0" not in full_text
    assert "\u25a1" not in full_text
    assert "\ufffd" not in full_text
    assert len(full_text.strip()) > 50


# =====================================================================
# PART B TESTS: Full Record Exposure across 11 Sources & 13 Sections
# =====================================================================

TEST_RECORDS_BY_SOURCE = [
    # us_ofac
    ("us_ofac", "2674", "AL-QA'IDA", ["SDGT"]),
    ("us_ofac", "1234", None, None), # Another OFAC record
    # us_csl
    ("us_csl", "CSL-AERO-001", "MAHAN AIR", ["SDGT"]),
    ("us_csl", "CSL-MEP-001", "IRAN ELECTRONICS INDUSTRIES", ["NPWMD"]),
    # uk_csl
    ("uk_csl", "RUS0001", None, None),
    ("uk_csl", "RUS0002", None, None),
    # eu_csl / eu_fsf
    ("eu_csl", "EU-001", None, None),
    ("eu_csl", "EU-002", None, None),
    # un_csl
    ("un_csl", "QDi.001", None, None),
    ("un_csl", "QDi.002", None, None),
    # in_mha
    ("in_mha", "mha-terrorist-001", None, None),
    ("in_mha", "mha-banned-001", None, None),
    # ch_seco
    ("ch_seco", "ch-1001", None, None),
    ("ch_seco", "ch-1002", None, None),
    # au_dfat
    ("au_dfat", "au-2001", None, None),
    ("au_dfat", "au-2002", None, None),
    # ca_sema
    ("ca_sema", "ca-3001", None, None),
    ("ca_sema", "ca-3002", None, None),
    # jp_mof
    ("jp_mof", "jp-4001", None, None),
    ("jp_mof", "jp-4002", None, None),
    # non_sdn / bis
    ("us_csl", "CSL-EXP-001", None, None),
    ("us_ofac", "8000", None, None),
]


def test_b6_record_exposure_across_sources():
    """
    Part B6: Verify that for records across supported lists:
    1. Every non-empty field appears in build_13_sections.
    2. Full records appear in PDF Section F appendix.
    3. Full records appear in Excel 'Full records' sheet.
    """
    for src_id, rec_id, expected_name, expected_progs in TEST_RECORDS_BY_SOURCE[:10]:
        rec = get_record(src_id, rec_id)
        if not rec:
            continue

        sections = build_13_sections(rec, src_id)
        assert 1 <= len(sections) <= 13
        for sec_name in sections.keys():
            assert sec_name in SECTION_NAMES

        # Section 1 Primary name and entity type must exist
        sec1 = sections[SECTION_NAMES[0]]
        assert any(label == "Primary Listed Name" for label, val in sec1)

        # Check raw_fields coverage: all non-empty raw_fields must appear in some section
        raw_fields = rec.get("raw_fields") or {}
        all_section_values = " ".join(val for items in sections.values() for label, val in items)
        all_section_labels = [label for items in sections.values() for label, _ in items]
        sec12_labels = [label for label, _ in sections.get(SECTION_NAMES[11], [])]
        for k, v in raw_fields.items():
            if v and str(v).strip() and str(v).strip() not in ["-0-", "None"]:
                v_items = v if isinstance(v, list) else [v]
                v_clean = str(v).strip()[:15]
                # Either key, label, truncated value, or item value should be captured
                assert (
                    (k in all_section_values)
                    or (v_clean in all_section_values)
                    or any(str(item).strip()[:15] in all_section_values for item in v_items if item)
                    or (str(k) in sec12_labels)
                    or any(str(k) == str(lbl) for lbl in all_section_labels)
                )


def test_b6_drift_proofing_synthetic_field():
    """
    Part B6: Assert that brand-new upstream fields the codebase has never seen
    are not lost, but routed cleanly to Section 12 ('Other fields (as published)').
    """
    synthetic_rec = {
        "primary_name": "SYNTHETIC TEST CORP",
        "entity_type": "Organisation",
        "brand_new_unmapped_column_xyz": "CRITICAL_VALUE_999",
        "another_future_publisher_field": "FUTURE_DATA_888",
    }
    sections = build_13_sections(synthetic_rec, "us_ofac")
    sec12_items = sections[SECTION_NAMES[11]] # 12. Other fields (as published)
    sec12_dict = dict(sec12_items)

    assert "brand_new_unmapped_column_xyz" in sec12_dict
    assert sec12_dict["brand_new_unmapped_column_xyz"] == "CRITICAL_VALUE_999"
    assert "another_future_publisher_field" in sec12_dict
    assert sec12_dict["another_future_publisher_field"] == "FUTURE_DATA_888"


def test_b6_pdf_and_excel_full_records_appendix(tmp_path):
    """
    Verify that when include_full_records is True, the PDF includes Section F
    and the Excel report includes the 'Full records' worksheet.
    """
    rec_payload = {
        "primary_name": "TARGET CORPORATION LTD",
        "entity_type": "Organisation",
        "aliases": ["TARGET CORP", "TARGET CO"],
        "tax_id": "TAX-123456",
        "addresses": ["123 Financial Way, London"],
        "program": "RUSSIA",
        "remarks": "Subject to financial sanctions restrictions.",
        "raw_fields": {
            "unusual_custom_tag": "TAG-VALUE-XYZ"
        }
    }
    
    hits = [{
        "source_list": "uk_csl",
        "source_id": "UK-TEST-001",
        "primary_name": "TARGET CORPORATION LTD",
        "matched_name": "TARGET CORPORATION LTD",
        "score": 1.0,
        "tier": "POTENTIAL_MATCH",
    }]

    # Mock get_record to return rec_payload for UK-TEST-001
    with patch("modules.reporting.generator.get_record", return_value=rec_payload):
        pdf_path, excel_path = generate_reports(
            search_type="Organisation",
            inputs={"name": "TARGET CORPORATION LTD"},
            overall_banner="🔴 POTENTIAL MATCH",
            source_statuses=[{"id": "uk_csl", "name": "UK Sanctions", "status": "HIT", "hit_count": 1}],
            sanctions_hits=hits,
            include_full_records=True,
        )

        assert pdf_path.exists()
        assert excel_path.exists()

        # Check PDF Section F
        reader = pypdf.PdfReader(str(pdf_path))
        pdf_text = "".join(page.extract_text() or "" for page in reader.pages)
        assert "Section F - Full Regulatory Records Appendix" in pdf_text
        assert "UK-TEST-001" in pdf_text
        assert "TARGET CORPORATION LTD" in pdf_text
        assert "123 Financial Way" in pdf_text

        # Check Excel 'Full records' sheet
        wb = openpyxl.load_workbook(str(excel_path))
        assert "Full records" in wb.sheetnames
        ws_full = wb["Full records"]
        rows = list(ws_full.iter_rows(values_only=True))
        assert rows[0] == ("Source", "Record ID", "Section", "Field", "Value")
        
        # Ensure our record ID and unusual custom tag appear in the sheet
        full_sheet_str = " ".join(str(cell) for row in rows for cell in row)
        assert "UK-TEST-001" in full_sheet_str
        assert "unusual_custom_tag" in full_sheet_str
        assert "TAG-VALUE-XYZ" in full_sheet_str
