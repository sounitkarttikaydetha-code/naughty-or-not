"""FATF (Financial Action Task Force) jurisdiction screening module.
Screens country names against:
1. High-risk jurisdictions subject to a call for action (Black list - 3 jurisdictions)
2. Jurisdictions under increased monitoring (Grey list - 22 jurisdictions)

Every finding carries the exact label: 'Country risk flag — not a sanctions finding'.
Refresh schedule follows the three annual FATF plenaries: February, June, October.
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

SAFETY_LABEL = "Country risk flag — not a sanctions finding"

CONFIG_FATF_JSON = Path(__file__).resolve().parent.parent.parent / "config" / "fatf.json"
CONFIG_FATF_LISTS_JSON = Path(__file__).resolve().parent.parent.parent / "config" / "fatf_lists.json"


def _load_fatf_config() -> Tuple[Dict[str, Any], Path]:
    for p in [CONFIG_FATF_JSON, CONFIG_FATF_LISTS_JSON]:
        if p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "black_list" in data and "grey_list" in data:
                        return data, p
                    elif "details" in data and "body" in data.get("details", {}):
                        from modules.fatf.republication import parse_hm_treasury_html
                        parsed = parse_hm_treasury_html(data["details"]["body"], data.get("public_updated_at", ""))
                        if parsed and "black_list" in parsed:
                            return parsed, p
            except Exception as e:
                logger.warning(f"Could not load {p}: {e}")
    return {}, CONFIG_FATF_JSON


_cfg, ACTIVE_CONFIG_PATH = _load_fatf_config()
CONFIG_PATH = ACTIVE_CONFIG_PATH

FATF_STATEMENT_DATE = _cfg.get("statement_date", _cfg.get("fatf_statement_date", "2026-06-19"))
PLENARY_MONTHS = _cfg.get("plenary_months", [2, 6, 10])
PLENARY_CYCLE = _cfg.get("plenary_cycle", "February / June / October")
PLENARY_NOTE = _cfg.get(
    "plenary_note",
    "FATF Plenaries are held three times a year in February, June, and October. Next plenary: October 2026.",
)
SOURCE_URLS = _cfg.get(
    "source_urls",
    {
        "landing_page": "https://www.fatf-gafi.org/en/topics/high-risk-and-other-monitored-jurisdictions.html",
        "high_risk": "https://www.fatf-gafi.org/en/publications/High-risk-and-other-monitored-jurisdictions/Call-for-action-june-2026.html",
        "increased_monitoring": "https://www.fatf-gafi.org/en/publications/High-risk-and-other-monitored-jurisdictions/Increased-monitoring-june-2026.html",
    },
)


def normalize_country(country: Optional[str]) -> str:
    """Normalize country string for lookup."""
    if not country:
        return ""
    clean = re.sub(r"[^\w\s]", " ", country.lower())
    return " ".join(clean.split())


# Build lookup maps and country lists
BLACK_LIST_MAP: Dict[str, str] = {}
BLACK_LIST_COUNTRIES: List[str] = []
_raw_black = _cfg.get("black_list", [])
if isinstance(_raw_black, list):
    for entry in _raw_black:
        c_name = entry.get("name", "")
        if c_name:
            BLACK_LIST_COUNTRIES.append(c_name)
            BLACK_LIST_MAP[normalize_country(c_name)] = c_name
            for al in entry.get("aliases", []):
                BLACK_LIST_MAP[normalize_country(al)] = c_name
elif isinstance(_raw_black, dict):
    BLACK_LIST_MAP = dict(_raw_black)
    BLACK_LIST_COUNTRIES = sorted(list(set(_raw_black.values())))

GREY_LIST_MAP: Dict[str, str] = {}
GREY_LIST_COUNTRIES: List[str] = []
_raw_grey = _cfg.get("grey_list", [])
if isinstance(_raw_grey, list):
    for entry in _raw_grey:
        c_name = entry.get("name", "")
        if c_name:
            GREY_LIST_COUNTRIES.append(c_name)
            GREY_LIST_MAP[normalize_country(c_name)] = c_name
            for al in entry.get("aliases", []):
                GREY_LIST_MAP[normalize_country(al)] = c_name
elif isinstance(_raw_grey, dict):
    GREY_LIST_MAP = dict(_raw_grey)
    GREY_LIST_COUNTRIES = sorted(list(set(_raw_grey.values())))

# Maintain backwards compatibility aliases
BLACK_LIST = BLACK_LIST_MAP
GREY_LIST = GREY_LIST_MAP


def check_plenary_refresh(current_date: Optional[datetime] = None) -> Dict[str, Any]:
    """Check whether a new FATF plenary statement check is due.
    FATF holds 3 plenaries per year: February, June, October.
    October 2026 plenary runs 28-30 October; outcome update due from 31 October 2026.
    """
    now = current_date or datetime.now(timezone.utc)
    # The June 2026 statement remains current until October 31, 2026
    plenary_closure = datetime(2026, 10, 31, 0, 0, 0, tzinfo=timezone.utc)
    refresh_due = now >= plenary_closure
    status = "UPDATE_DUE" if refresh_due else "UP_TO_DATE"
    return {
        "statement_date": FATF_STATEMENT_DATE,
        "plenary_cycle": PLENARY_CYCLE,
        "plenary_note": PLENARY_NOTE,
        "last_checked": now.strftime("%Y-%m-%d"),
        "refresh_due": refresh_due,
        "status": status,
        "source_urls": SOURCE_URLS,
    }


def check_country(
    country: Optional[str],
    is_stale: bool = False,
    as_of_date: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Check a country against FATF black and grey lists.
    Returns:
      {
        "tier": "POSSIBLE_MATCH_REVIEW" | "NO_MATCH" | "NOT_CHECKED",
        "tier_icon": "⚠️" | "✅" | "⚪",
        "finding": "FATF_HIGH_RISK" | "FATF_INCREASED_MONITORING" | "CLEAN" | "STALE_SOURCE",
        "country": str,
        "standardized_country": Optional[str],
        "statement_date": str,
        "risk_label": str,
        "source": "FATF",
      }
    """
    if is_stale:
        return {
            "tier": "NOT_CHECKED",
            "tier_icon": "⚪",
            "finding": "STALE_SOURCE",
            "status": "STALE",
            "country": country or "",
            "standardized_country": None,
            "statement_date": FATF_STATEMENT_DATE,
            "action": "Source record is stale (> 45 days since last verification)",
            "risk_label": SAFETY_LABEL,
            "source": "FATF",
            "error": "FATF source data is stale (> 45 days old)",
        }

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

    # 1. Check Black list (High Risk)
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
        if k == norm or (len(k) >= 3 and (k in norm or norm in k)):
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

    # 2. Check Grey list (Increased Monitoring)
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

    def __init__(self, is_stale: Optional[bool] = None):
        if is_stale is not None:
            self.is_stale = is_stale
        else:
            self.is_stale = False
            # Check if source_manager detects staleness
            try:
                from modules.common.source_manager import SourceManager, STATE_STALE
                sm = SourceManager()
                st = sm.get_source_state("fatf_jurisdictions")
                if st.get("state") == STATE_STALE:
                    self.is_stale = True
            except Exception:
                pass

    def screen_country(self, country: str) -> Dict[str, Any]:
        return check_country(country, is_stale=self.is_stale)
