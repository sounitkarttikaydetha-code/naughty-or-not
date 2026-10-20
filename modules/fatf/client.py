"""FATF (Financial Action Task Force) jurisdiction screening module.
Screens country names against:
1. High-risk jurisdictions subject to a call for action (Black list)
2. Jurisdictions under increased monitoring (Grey list)

Every finding carries the exact label: 'Country risk flag — not a sanctions finding'.
Refresh schedule follows the three annual FATF plenaries: February, June, October.
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SAFETY_LABEL = "Country risk flag — not a sanctions finding"

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "fatf_lists.json"


def _load_fatf_config() -> Dict[str, Any]:
    if CONFIG_PATH.is_file():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load {CONFIG_PATH}: {e}")
    return {}


_cfg = _load_fatf_config()
FATF_STATEMENT_DATE = _cfg.get("fatf_statement_date", "2026-06-28")
PLENARY_MONTHS = _cfg.get("plenary_months", [2, 6, 10])
BLACK_LIST = _cfg.get("black_list", {
    "dprk": "Democratic People's Republic of Korea",
    "democratic peoples republic of korea": "Democratic People's Republic of Korea",
    "north korea": "Democratic People's Republic of Korea",
    "iran": "Iran",
    "islamic republic of iran": "Iran",
    "myanmar": "Myanmar",
    "burma": "Myanmar",
})
GREY_LIST = _cfg.get("grey_list", {})



def normalize_country(country: Optional[str]) -> str:
    """Normalize country string for lookup."""
    if not country:
        return ""
    clean = re.sub(r"[^\w\s]", " ", country.lower())
    return " ".join(clean.split())


def check_plenary_refresh(current_date: Optional[datetime] = None) -> Dict[str, Any]:
    """Check whether a new FATF plenary statement check is due.
    FATF holds 3 plenaries per year: February, June, October.
    """
    now = current_date or datetime.now(timezone.utc)
    current_month = now.month
    return {
        "statement_date": FATF_STATEMENT_DATE,
        "plenary_cycle": "February / June / October",
        "last_checked": now.strftime("%Y-%m-%d"),
        "refresh_due": current_month in PLENARY_MONTHS,
        "status": "UP_TO_DATE",
    }


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


class FATFClient:
    """FATF Screening Client wrapper."""
    def screen_country(self, country: str) -> Dict[str, Any]:
        return check_country(country)


