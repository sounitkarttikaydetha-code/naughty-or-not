import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from modules.reporting.generator import generate_reports, generate_raw_reports
import pypdf

def test_reports():
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    test_cases = []
    
    # 1. Aeroflot (Airline) - 🔴, 🟠, ℹ️
    aeroflot_hits = [
        {
            "source_list": "us_csl",
            "source_id": "CSL-AERO-001",
            "tier": "POTENTIAL_MATCH",
            "primary_name": "Public Joint Stock Company Aeroflot - Russian Airlines",
            "matched_name": "PJSC Aeroflot",
            "expanded_from": "Aeroflot",
            "score": 0.9850,
            "reason": "name_exact_match",
        },
        {
            "source_list": "eu_csl",
            "source_id": "EU-1234",
            "tier": "POSSIBLE_MATCH_REVIEW",
            "primary_name": "Aeroflot Cargo CJSC",
            "matched_name": "Aeroflot Cargo",
            "score": 0.7600,
            "reason": "name_substring_match",
        },
        {
            "source_list": "un_csl",
            "source_id": "UN-5678",
            "tier": "BELOW_THRESHOLD",
            "primary_name": "Aero Transport Logistics",
            "matched_name": "Aero",
            "score": 0.6200,
            "reason": "token_match",
        }
    ]
    p1, x1 = generate_reports(
        search_type="Airline",
        inputs={"name": "Aeroflot"},
        overall_banner="🔴 POTENTIAL MATCH",
        source_statuses=[{"id": "us_csl", "authority": "US CSL", "date": "2026-10-27", "status": "OK", "tier": "POTENTIAL_MATCH"}],
        sanctions_hits=aeroflot_hits,
        aviation_hits=[{"source": "eu_safety", "result_type": "SAFETY", "detail": "EU Operating Ban - Annex A", "note": "Air carrier banned"}],
        country_risk_hits=[],
    )
    test_cases.append(("1. Name check: Aeroflot (Airline)", p1, x1))

    # 2. HAMAS (Organisation)
    hamas_hits = [
        {
            "source_list": "us_ofac",
            "source_id": "18715",
            "tier": "POTENTIAL_MATCH",
            "primary_name": "HAMAS",
            "matched_name": "HARAKAT AL-MUQAWAMA AL-ISLAMIYA",
            "score": 0.9500,
            "reason": "name_alias_match",
        }
    ]
    p2, x2 = generate_reports(
        search_type="Organisation",
        inputs={"name": "HAMAS"},
        overall_banner="🔴 POTENTIAL MATCH",
        source_statuses=[{"id": "us_ofac", "authority": "US OFAC", "date": "2026-10-27", "status": "OK", "tier": "POTENTIAL_MATCH"}],
        sanctions_hits=hamas_hits,
        aviation_hits=[],
        country_risk_hits=[],
    )
    test_cases.append(("2. Name check: HAMAS (Organisation)", p2, x2))

    # 3. Text search
    raw_results = [
        {"source_id": "us_ofac", "entity_id": "18715", "field": "alt_name", "term": "HAMAS", "snippet": "Known as HAMAS terrorist organization"}
    ]
    p3, x3 = generate_raw_reports(
        query="HAMAS",
        results=raw_results,
        options={"match_all": True},
    )
    test_cases.append(("3. Text search", p3, x3))

    # 4. Manual check
    manual_checks = [
        {
            "timestamp": "2026-11-10 10:00:00 UTC",
            "source_name": "UK Sanctions Search",
            "result": "POTENTIAL_MATCH",
            "comment": "Confirmed listing under ISIL/Al-Qaida regime",
            "verify_url": "https://sanctionssearchapp.ofsi.hmtreasury.gov.uk/",
        }
    ]
    p4, x4 = generate_reports(
        search_type="Organisation",
        inputs={"name": "Al-Qaida"},
        overall_banner="🔴 POTENTIAL MATCH",
        source_statuses=[{"id": "uk_csl", "authority": "UK FCDO", "date": "2026-10-27", "status": "OK", "tier": "POTENTIAL_MATCH"}],
        sanctions_hits=[],
        aviation_hits=[],
        country_risk_hits=[],
        manual_checks=manual_checks,
    )
    test_cases.append(("4. Manual check", p4, x4))

    # 5. Country check
    country_risk = [
        {
            "country": "Democratic People's Republic of Korea",
            "list_type": "FATF Black List",
            "summary": "High-risk jurisdiction subject to a call for action",
            "advisory": "Countermeasures required",
        }
    ]
    p5, x5 = generate_reports(
        search_type="Country",
        inputs={"country": "North Korea"},
        overall_banner="🔴 HIGH RISK JURISDICTION",
        source_statuses=[{"id": "fatf_jurisdictions", "authority": "FATF", "date": "2026-06-19", "status": "OK", "tier": "POTENTIAL_MATCH"}],
        sanctions_hits=[],
        aviation_hits=[],
        country_risk_hits=country_risk,
    )
    test_cases.append(("5. Country check", p5, x5))

    # 6. Ownership check
    ubo_data = {
        "target_name": "Sovcomflot Trading Ltd",
        "ofac_verdict": {"verdict_text": "BLOCKED (>=50% aggregate ownership by blocked persons)"},
        "eu_verdict": {"verdict_text": "SANCTIONED (Control exercised by designated person)"},
        "uk_verdict": {"verdict_text": "FROZEN (>50% majority interest by designated person)"},
        "undisclosed_ownership_pct": 0.0,
    }
    p6, x6 = generate_reports(
        search_type="ownership",
        inputs={"name": "Sovcomflot Trading Ltd", "ubo_result": ubo_data},
        overall_banner="🔴 BLOCKED UNDER 50% RULE",
        source_statuses=[{"id": "us_ofac", "authority": "US OFAC", "date": "2026-10-27", "status": "OK", "tier": "POTENTIAL_MATCH"}],
        sanctions_hits=[],
        aviation_hits=[],
        country_risk_hits=[],
    )
    test_cases.append(("6. Ownership check", p6, x6))

    # 7. Self-test-failed session
    p7, x7 = generate_reports(
        search_type="Organisation",
        inputs={"name": "Test Entity"},
        overall_banner="⚪ ENGINE_CANARY_FAILURE: Matching engine internal inconsistency detected",
        source_statuses=[{"id": "us_ofac", "authority": "US OFAC", "date": "2026-10-27", "status": "FAILED", "tier": "NOT_CHECKED"}],
        sanctions_hits=[],
        aviation_hits=[],
        country_risk_hits=[],
    )
    test_cases.append(("7. Self-test-failed session", p7, x7))

    # 8. Report with zero candidates
    p8, x8 = generate_reports(
        search_type="Organisation",
        inputs={"name": "Clean Global Trading Corp"},
        overall_banner="✅ NO MATCH",
        source_statuses=[{"id": "us_ofac", "authority": "US OFAC", "date": "2026-10-27", "status": "OK", "tier": "NO_MATCH"}],
        sanctions_hits=[],
        aviation_hits=[],
        country_risk_hits=[],
    )
    test_cases.append(("8. Zero candidates", p8, x8))

    print(f"{'Report Type':<35} | {'Size (B)':<10} | {'Pages':<6} | {'Text Extracted':<15} | {'Status'}")
    print("-" * 85)
    for name, pdf, xl in test_cases:
        size = pdf.stat().st_size
        reader = pypdf.PdfReader(str(pdf))
        num_pages = len(reader.pages)
        text = "".join(page.extract_text() or "" for page in reader.pages)
        is_blank = (len(text.strip()) == 0)
        has_text = "YES" if not is_blank else "NO (BLANK)"
        status = "FAIL (BLANK)" if is_blank else "OK"
        print(f"{name:<35} | {size:<10} | {num_pages:<6} | {has_text:<15} | {status}")
        print(f"   Sample text: {repr(text[:80])}")

if __name__ == "__main__":
    test_reports()
