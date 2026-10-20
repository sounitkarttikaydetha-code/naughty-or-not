"""FATF (Financial Action Task Force) jurisdiction screening module.
Screens country names against:
1. High-risk jurisdictions subject to a call for action (Black list)
2. Jurisdictions under increased monitoring (Grey list)

Every finding carries the exact label: 'Country risk flag — not a sanctions finding'.
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SAFETY_LABEL = "Country risk flag — not a sanctions finding"

FATF_STATEMENT_DATE = "2026-06-28"

# High-Risk Jurisdictions subject to a Call for Action (Black list)
BLACK_LIST = {
    "dprk": "Democratic People's Republic of Korea",
    "democratic peoples republic of korea": "Democratic People's Republic of Korea",
    "north korea": "Democratic People's Republic of Korea",
    "iran": "Iran",
    "islamic republic of iran": "Iran",
    "myanmar": "Myanmar",
    "burma": "Myanmar",
}

# Jurisdictions under Increased Monitoring (Grey list)
GREY_LIST = {
    "angola": "Angola",
    "bolivia": "Bolivia",
    "bosnia and herzegovina": "Bosnia and Herzegovina",
    "bosnia": "Bosnia and Herzegovina",
    "bulgaria": "Bulgaria",
    "burkina faso": "Burkina Faso",
    "cameroon": "Cameroon",
    "cote d ivoire": "Côte d'Ivoire",
    "cote divoire": "Côte d'Ivoire",
    "ivory coast": "Côte d'Ivoire",
    "democratic republic of the congo": "Democratic Republic of the Congo",
    "democratic republic of congo": "Democratic Republic of the Congo",
    "drc": "Democratic Republic of the Congo",
    "haiti": "Haiti",
    "iraq": "Iraq",
    "kenya": "Kenya",
    "kuwait": "Kuwait",
    "lao pdr": "Lao PDR",
    "laos": "Lao PDR",
    "lebanon": "Lebanon",
    "monaco": "Monaco",
    "mozambique": "Mozambique",
    "namibia": "Namibia",
    "nepal": "Nepal",
    "nigeria": "Nigeria",
    "papua new guinea": "Papua New Guinea",
    "south africa": "South Africa",
    "south sudan": "South Sudan",
    "syria": "Syria",
    "syrian arab republic": "Syria",
    "tanzania": "Tanzania",
    "venezuela": "Venezuela",
    "vietnam": "Vietnam",
    "virgin islands british": "British Virgin Islands",
    "british virgin islands": "British Virgin Islands",
    "yemen": "Yemen",
}


def normalize_country(country: Optional[str]) -> str:
    """Normalize country string for lookup."""
    if not country:
        return ""
    clean = re.sub(r"[^\w\s]", " ", country.lower())
    return " ".join(clean.split())


def check_country(country: Optional[str]) -> Dict[str, Any]:
    """Check a country against FATF black and grey lists.
    Returns:
      {
        "tier": "POSSIBLE_MATCH_REVIEW" | "NO_MATCH",
        "tier_icon": "⚠️" | "✅",
        "finding": "FATF_HIGH_RISK" | "FATF_INCREASED_MONITORING" | "CLEAN",
        "country": str,
        "standardized_country": Optional[str],
        "statement_date": str,
        "risk_label": str,
        "source": "FATF",
      }
    """
    if not country or not country.strip():
        return {
            "tier": "NO_MATCH",
            "tier_icon": "✅",
            "finding": "CLEAN",
            "country": "",
            "standardized_country": None,
            "statement_date": FATF_STATEMENT_DATE,
            "risk_label": SAFETY_LABEL,
            "source": "FATF",
        }

    norm = normalize_country(country)

    # Check Black list (High Risk)
    if norm in BLACK_LIST:
        std = BLACK_LIST[norm]
        return {
            "tier": "POSSIBLE_MATCH_REVIEW",
            "tier_icon": "⚠️",
            "finding": "FATF_HIGH_RISK",
            "country": country,
            "standardized_country": std,
            "statement_date": FATF_STATEMENT_DATE,
            "action": "Subject to a Call for Action (Black list)",
            "risk_label": SAFETY_LABEL,
            "source": "FATF",
        }

    for k, std in BLACK_LIST.items():
        if k in norm or norm in k:
            return {
                "tier": "POSSIBLE_MATCH_REVIEW",
                "tier_icon": "⚠️",
                "finding": "FATF_HIGH_RISK",
                "country": country,
                "standardized_country": std,
                "statement_date": FATF_STATEMENT_DATE,
                "action": "Subject to a Call for Action (Black list)",
                "risk_label": SAFETY_LABEL,
                "source": "FATF",
            }

    # Check Grey list (Increased Monitoring)
    if norm in GREY_LIST:
        std = GREY_LIST[norm]
        return {
            "tier": "POSSIBLE_MATCH_REVIEW",
            "tier_icon": "⚠️",
            "finding": "FATF_INCREASED_MONITORING",
            "country": country,
            "standardized_country": std,
            "statement_date": FATF_STATEMENT_DATE,
            "action": "Jurisdiction under Increased Monitoring (Grey list)",
            "risk_label": SAFETY_LABEL,
            "source": "FATF",
        }

    for k, std in GREY_LIST.items():
        if k == norm or (len(k) > 4 and k in norm):
            return {
                "tier": "POSSIBLE_MATCH_REVIEW",
                "tier_icon": "⚠️",
                "finding": "FATF_INCREASED_MONITORING",
                "country": country,
                "standardized_country": std,
                "statement_date": FATF_STATEMENT_DATE,
                "action": "Jurisdiction under Increased Monitoring (Grey list)",
                "risk_label": SAFETY_LABEL,
                "source": "FATF",
            }

    return {
        "tier": "NO_MATCH",
        "tier_icon": "✅",
        "finding": "CLEAN",
        "country": country,
        "standardized_country": country,
        "statement_date": FATF_STATEMENT_DATE,
        "risk_label": SAFETY_LABEL,
        "source": "FATF",
    }
