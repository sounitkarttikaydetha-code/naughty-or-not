"""
Pure Domain Country Evaluation Engine.
Evaluates FATF status (Call for Action, Increased Monitoring) and Comprehensive Sanctions.
Zero I/O.
"""
from typing import Dict, List, Optional, Set
from dataclasses import dataclass

from canary.domain.models import CountryCheckResult

# Pinned Regulatory Invariants (Rule 10 deterministic reference)
FATF_CALL_FOR_ACTION: Set[str] = {
    "KP", "IR", "MM",  # ISO-2: Democratic People's Republic of Korea, Iran, Myanmar
    "DEMOCRATIC PEOPLE'S REPUBLIC OF KOREA", "NORTH KOREA", "DPRK", "IRAN", "MYANMAR", "BURMA"
}

FATF_INCREASED_MONITORING: Set[str] = {
    "DZ", "AO", "BG", "BF", "CM", "CI", "CD", "HT", "KE", "LB", "ML", "MC", "MZ",
    "NA", "NG", "PH", "ZA", "SS", "SY", "TZ", "VE", "VN", "YE", "BO", "BA", "KW",
    "LA", "NP", "PG", "VG",
    "ALGERIA", "ANGOLA", "BOLIVIA", "BOSNIA AND HERZEGOVINA", "BULGARIA", "BURKINA FASO",
    "CAMEROON", "COTE D'IVOIRE", "DEMOCRATIC REPUBLIC OF THE CONGO", "HAITI", "KENYA",
    "KUWAIT", "LAO PDR", "LEBANON", "MALI", "MONACO", "MOZAMBIQUE", "NAMIBIA", "NEPAL",
    "NIGERIA", "PAPUA NEW GUINEA", "PHILIPPINES", "SOUTH AFRICA", "SOUTH SUDAN",
    "SYRIA", "TANZANIA", "VENEZUELA", "VIETNAM", "YEMEN", "VIRGIN ISLANDS (UK)", "BRITISH VIRGIN ISLANDS"
}

COMPREHENSIVE_SANCTIONED_COUNTRIES: Set[str] = {
    "CU", "IR", "KP", "SY",
    "CUBA", "IRAN", "NORTH KOREA", "DPRK", "SYRIA"
}


def evaluate_country(query: str, iso_code: Optional[str] = None) -> CountryCheckResult:
    """
    Evaluate country regulatory standing across FATF and Comprehensive Sanctions.
    Pure function, zero I/O.
    """
    q_clean = query.strip().upper()
    iso = (iso_code or (q_clean if len(q_clean) == 2 else "—")).upper()

    is_call_for_action = (q_clean in FATF_CALL_FOR_ACTION or iso in FATF_CALL_FOR_ACTION)
    is_increased_monitoring = (
        q_clean in FATF_INCREASED_MONITORING or iso in FATF_INCREASED_MONITORING
    )
    is_comp_sanctioned = (
        q_clean in COMPREHENSIVE_SANCTIONED_COUNTRIES or iso in COMPREHENSIVE_SANCTIONED_COUNTRIES
    )

    fatf_status = "Clean"
    fatf_statement = None
    if is_call_for_action:
        fatf_status = "Call for Action"
        fatf_statement = "High-Risk Jurisdiction subject to a Call for Action (FATF Black List)"
    elif is_increased_monitoring:
        fatf_status = "Increased Monitoring"
        fatf_statement = "Jurisdiction under Increased Monitoring (FATF Grey List)"

    regimes: List[str] = []
    notes: List[str] = []

    if is_call_for_action:
        regimes.append("FATF-BlackList")
        notes.append("Mandatory enhanced customer due diligence and counter-measures required.")
    if is_increased_monitoring:
        regimes.append("FATF-GreyList")
        notes.append("Enhanced customer due diligence and ongoing monitoring required.")
    if is_comp_sanctioned:
        regimes.append("OFAC-Comprehensive")
        notes.append("Subject to comprehensive country-wide sanctions under OFAC and related regimes.")

    return CountryCheckResult(
        country_name=query.strip().title(),
        iso_code=iso,
        fatf_status=fatf_status,
        fatf_statement=fatf_statement,
        is_comprehensive_sanctioned=is_comp_sanctioned,
        regimes=regimes,
        notes=notes,
    )
