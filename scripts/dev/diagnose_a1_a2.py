import os
import sys
import json
import traceback
from pathlib import Path

# Ensure project root is in path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import pypdf
try:
    import pdfplumber
except ImportError:
    pdfplumber = None

from modules.reporting.generator import generate_reports, generate_raw_reports
from modules.common.paths import get_reports_dir

def run_reproduction_suite(env_name: str, frozen: bool):
    print(f"\n=======================================================")
    print(f"RUNNING SUITE: {env_name} (sys.frozen={frozen})")
    print(f"=======================================================")
    
    old_frozen = getattr(sys, "frozen", False)
    if frozen:
        sys.frozen = True
    else:
        if hasattr(sys, "frozen"):
            del sys.frozen

    results = []

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
    cases = [
        (
            "Name check (Aeroflot Airline)",
            lambda: generate_reports(
                search_type="Airline",
                inputs={"name": "Aeroflot"},
                overall_banner="🔴 POTENTIAL MATCH",
                source_statuses=[{"id": "us_csl", "authority": "US CSL", "date": "2026-10-27", "status": "OK", "tier": "POTENTIAL_MATCH"}],
                sanctions_hits=aeroflot_hits,
                aviation_hits=[{"source": "eu_safety", "result_type": "SAFETY", "detail": "EU Operating Ban - Annex A", "note": "Air carrier banned"}],
                country_risk_hits=[],
            )
        ),
        (
            "Name check (HAMAS Organisation)",
            lambda: generate_reports(
                search_type="Organisation",
                inputs={"name": "HAMAS"},
                overall_banner="🔴 POTENTIAL MATCH",
                source_statuses=[{"id": "us_ofac", "authority": "US OFAC", "date": "2026-10-27", "status": "OK", "tier": "POTENTIAL_MATCH"}],
                sanctions_hits=[{
                    "source_list": "us_ofac",
                    "source_id": "18715",
                    "tier": "POTENTIAL_MATCH",
                    "primary_name": "HAMAS",
                    "matched_name": "HARAKAT AL-MUQAWAMA AL-ISLAMIYA",
                    "score": 0.9500,
                    "reason": "name_alias_match",
                }],
                aviation_hits=[],
                country_risk_hits=[],
            )
        ),
        (
            "Text search",
            lambda: generate_raw_reports(
                query="HAMAS",
                results=[{"source_id": "us_ofac", "entity_id": "18715", "field": "alt_name", "term": "HAMAS", "snippet": "Known as HAMAS terrorist organization"}],
                options={"match_all": True},
            )
        ),
        (
            "Manual check",
            lambda: generate_reports(
                search_type="Organisation",
                inputs={"name": "Al-Qaida"},
                overall_banner="🔴 POTENTIAL MATCH",
                source_statuses=[{"id": "uk_csl", "authority": "UK FCDO", "date": "2026-10-27", "status": "OK", "tier": "POTENTIAL_MATCH"}],
                sanctions_hits=[],
                aviation_hits=[],
                country_risk_hits=[],
                manual_checks=[{
                    "timestamp": "2026-11-10 10:00:00 UTC",
                    "source_name": "UK Sanctions Search",
                    "result": "POTENTIAL_MATCH",
                    "comment": "Confirmed listing under ISIL/Al-Qaida regime",
                    "verify_url": "https://sanctionssearchapp.ofsi.hmtreasury.gov.uk/",
                }],
            )
        ),
        (
            "Country check",
            lambda: generate_reports(
                search_type="Country",
                inputs={"country": "North Korea"},
                overall_banner="🔴 HIGH RISK JURISDICTION",
                source_statuses=[{"id": "fatf_jurisdictions", "authority": "FATF", "date": "2026-06-19", "status": "OK", "tier": "POTENTIAL_MATCH"}],
                sanctions_hits=[],
                aviation_hits=[],
                country_risk_hits=[{
                    "country": "Democratic People's Republic of Korea",
                    "list_type": "FATF Black List",
                    "summary": "High-risk jurisdiction subject to a call for action",
                    "advisory": "Countermeasures required",
                }],
            )
        ),
        (
            "Ownership check",
            lambda: generate_reports(
                search_type="ownership",
                inputs={
                    "name": "Sovcomflot Trading Ltd",
                    "ubo_result": {
                        "target_name": "Sovcomflot Trading Ltd",
                        "ofac_verdict": {"verdict_text": "BLOCKED (>=50% aggregate ownership by blocked persons)"},
                        "eu_verdict": {"verdict_text": "SANCTIONED (Control exercised by designated person)"},
                        "uk_verdict": {"verdict_text": "FROZEN (>50% majority interest by designated person)"},
                        "undisclosed_ownership_pct": 0.0,
                    }
                },
                overall_banner="🔴 BLOCKED UNDER 50% RULE",
                source_statuses=[{"id": "us_ofac", "authority": "US OFAC", "date": "2026-10-27", "status": "OK", "tier": "POTENTIAL_MATCH"}],
                sanctions_hits=[],
                aviation_hits=[],
                country_risk_hits=[],
            )
        ),
        (
            "Self-test-failed session",
            lambda: generate_reports(
                search_type="Organisation",
                inputs={"name": "Test Entity"},
                overall_banner="⚪ ENGINE_CANARY_FAILURE: Matching engine internal inconsistency detected",
                source_statuses=[{"id": "us_ofac", "authority": "US OFAC", "date": "2026-10-27", "status": "FAILED", "tier": "NOT_CHECKED"}],
                sanctions_hits=[],
                aviation_hits=[],
                country_risk_hits=[],
            )
        ),
        (
            "Zero candidates",
            lambda: generate_reports(
                search_type="Organisation",
                inputs={"name": "Clean Global Trading Corp"},
                overall_banner="✅ NO MATCH",
                source_statuses=[{"id": "us_ofac", "authority": "US OFAC", "date": "2026-10-27", "status": "OK", "tier": "NO_MATCH"}],
                sanctions_hits=[],
                aviation_hits=[],
                country_risk_hits=[],
            )
        ),
    ]

    for title, gen_func in cases:
        rec = {"title": title, "env": env_name}
        try:
            pdf_path, xl_path = gen_func()
            rec["pdf_path"] = str(pdf_path)
            rec["excel_path"] = str(xl_path)
            rec["pdf_size"] = pdf_path.stat().st_size
            rec["excel_size"] = xl_path.stat().st_size
            
            # Inspect PDF
            reader = pypdf.PdfReader(str(pdf_path))
            rec["pages"] = len(reader.pages)
            full_text = ""
            for p_idx, page in enumerate(reader.pages):
                full_text += (page.extract_text() or "") + "\n"
            
            rec["text_len"] = len(full_text.strip())
            rec["is_blank"] = (len(full_text.strip()) == 0 or rec["pages"] == 0)
            
            # Check for missing-glyph squares (ReportLab uses \u25a0 for unencodable chars in Type 1 fonts)
            missing_glyph_count = full_text.count('\u25a0') + full_text.count('■')
            rec["missing_glyph_count"] = missing_glyph_count
            rec["has_unencodable_glyphs"] = missing_glyph_count > 0
            
            # Verify with pdfplumber if available
            if pdfplumber is not None:
                with pdfplumber.open(str(pdf_path)) as plum:
                    rec["pdfplumber_pages"] = len(plum.pages)
            
            rec["status"] = "BLANK" if rec["is_blank"] else ("GLYPH_ERRORS" if rec["has_unencodable_glyphs"] else "OK")
        except Exception as e:
            rec["exception"] = f"{type(e).__name__}: {e}"
            rec["traceback"] = traceback.format_exc()
            rec["status"] = "EXCEPTION"

        results.append(rec)
        print(f"[{rec['status']:<12}] {title:<35} | Size: {rec.get('pdf_size', 0):<6} B | Pages: {rec.get('pages', 0)} | Missing Glyphs: {rec.get('missing_glyph_count', 0)}")
        if rec.get("exception"):
            print(f"   -> EXCEPTION: {rec['exception']}")

    # Restore sys.frozen
    if old_frozen:
        sys.frozen = old_frozen
    elif hasattr(sys, "frozen"):
        del sys.frozen

    return results

if __name__ == "__main__":
    dev_res = run_reproduction_suite("Development (.venv314)", frozen=False)
    pkg_res = run_reproduction_suite("Packaged Build Simulation (sys.frozen=True)", frozen=True)
    
    with open("reviews/pdf_diagnosis_evidence.json", "w", encoding="utf-8") as f:
        json.dump({"dev": dev_res, "packaged": pkg_res}, f, indent=2)
    print("\nSaved diagnostics to reviews/pdf_diagnosis_evidence.json")
