"""Aviation screening client for aircraft and airlines against:
- BIS List of Commercial and Private Aircraft in Potential Violation of the EAR
- EU Air Safety List (Annex A bans and Annex B restrictions)
- FAA International Aviation Safety Assessment (IASA) Category 2 safety oversight
"""

import csv
import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Optional

from modules.aviation.parser import (
    parse_bis_aircraft,
    parse_eu_air_safety_list,
    parse_faa_iasa,
    check_and_refresh_sources,
)

logger = logging.getLogger(__name__)

SAFETY_LABEL = "Safety flag — not a sanctions finding"
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "aviation"
ALIAS_FILE = DATA_DIR / "airline_aliases.csv"


def normalize_registration(reg: Optional[str]) -> str:
    """Normalize aircraft registration (tail number) by stripping hyphens, spaces, and uppercasing."""
    if not reg:
        return ""
    return re.sub(r'[^A-Za-z0-9]', '', reg).upper()


def normalize_token(s: Optional[str]) -> str:
    """Normalize string for fuzzy comparison."""
    if not s:
        return ""
    return re.sub(r'[^a-zA-Z0-9]', '', s).lower()


WEAK_WORDS = {
    "air", "airlines", "airline", "airways", "aviation", "aero", "group", "holdings",
    "holding", "international", "services", "company", "co", "ltd", "llc", "jsc", "pjsc",
    "joint", "stock", "public", "limited", "the", "and", "of",
    # Geographic words that shouldn't alone correlate two different national carriers
    "iran", "russia", "russian", "iraq", "iraqi", "afghan", "afghanistan", "angola",
    "algeria", "zimbabwe", "congo", "libya", "libyan", "nepal", "sudan", "suriname"
}

def distinctive_match(query: str, target: str) -> bool:
    """Check if query and target share a distinctive non-weak word of length >= 4,
    or have identical normalized tokens."""
    q_norm = normalize_token(query)
    t_norm = normalize_token(target)
    if not q_norm or not t_norm:
        return False
    if q_norm == t_norm:
        return True

    # Tokenize into words
    q_words = {w for w in re.findall(r'[a-zA-Z0-9]+', query.lower()) if len(w) >= 3 and w not in WEAK_WORDS}
    t_words = {w for w in re.findall(r'[a-zA-Z0-9]+', target.lower()) if len(w) >= 3 and w not in WEAK_WORDS}

    shared = q_words & t_words
    return len(shared) > 0


class AviationClient:
    """Client for screening aircraft registrations, MSNs, and airline operators."""

    def __init__(self, auto_refresh: bool = False):
        if auto_refresh:
            try:
                check_and_refresh_sources(force=False)
            except Exception as e:
                logger.warning(f"Failed to auto-refresh aviation sources: {e}")

        self.aliases = self._load_aliases()
        self._load_data()

    def _load_aliases(self) -> List[Dict[str, Any]]:
        """Load airline aliases seed table."""
        aliases = []
        if not ALIAS_FILE.is_file():
            logger.warning(f"Airline aliases file not found at {ALIAS_FILE}")
            return aliases

        try:
            with open(ALIAS_FILE, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    aliases_list = [a.strip() for a in row.get("aliases", "").split(";") if a.strip()]
                    aliases.append({
                        "canonical_airline": row.get("canonical airline", "").strip(),
                        "aliases": aliases_list,
                        "icao": row.get("ICAO", "").strip().upper(),
                        "iata": row.get("IATA", "").strip().upper(),
                        "country": row.get("country", "").strip(),
                    })
        except Exception as e:
            logger.error(f"Error loading airline aliases: {e}")
        return aliases

    def _load_data(self) -> None:
        """Load and cache parsed data from local copies."""
        try:
            self.bis_data = parse_bis_aircraft()
        except Exception as e:
            logger.error(f"Error loading BIS aircraft data: {e}")
            self.bis_data = {"active": [], "removals": []}

        try:
            self.eu_data = parse_eu_air_safety_list()
        except Exception as e:
            logger.error(f"Error loading EU ASL data: {e}")
            self.eu_data = {"annex_a": [], "annex_b": [], "banned_states": []}

        try:
            self.faa_data = parse_faa_iasa()
        except Exception as e:
            logger.error(f"Error loading FAA IASA data: {e}")
            self.faa_data = []

    def resolve_airline(
        self,
        name: Optional[str] = None,
        icao: Optional[str] = None,
        iata: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Resolve airline name, ICAO, or IATA against airline_aliases.csv."""
        name_clean = name.strip() if name else ""
        name_norm = normalize_token(name_clean)
        icao_clean = icao.strip().upper() if icao else ""
        iata_clean = iata.strip().upper() if iata else ""

        for entry in self.aliases:
            if icao_clean and entry["icao"] == icao_clean:
                return entry
            if iata_clean and entry["iata"] == iata_clean:
                return entry
            if name_norm:
                if normalize_token(entry["canonical_airline"]) == name_norm:
                    return entry
                for alias in entry["aliases"]:
                    if normalize_token(alias) == name_norm:
                        return entry
                    # Substring check for full distinctive phrases
                    if len(name_norm) >= 4 and name_norm in normalize_token(alias):
                        return entry
                    if len(normalize_token(alias)) >= 4 and normalize_token(alias) in name_norm:
                        return entry
        return None

    def check_aircraft(
        self,
        registration: Optional[str] = None,
        msn: Optional[str] = None,
        operator: Optional[str] = None
    ) -> Dict[str, Any]:
        """Screen aircraft against BIS potential violation list.
        Never matches aircraft in the removals section.
        Returns:
          Dict with tier, finding, and details.
        """
        try:
            norm_reg = normalize_registration(registration)
            clean_msn = str(msn).strip() if msn else ""

            if not norm_reg and not clean_msn:
                return {
                    "tier": "NO_MATCH",
                    "tier_icon": "⚪",
                    "findings": [],
                    "message": "No registration or MSN provided"
                }

            # 1. Guard against removals: NEVER match removed aircraft
            for rem in self.bis_data.get("removals", []):
                rem_reg = normalize_registration(rem.get("tail_number"))
                rem_msn = str(rem.get("msn", "")).strip()
                if (norm_reg and norm_reg == rem_reg) or (clean_msn and clean_msn == rem_msn):
                    return {
                        "tier": "NO_MATCH",
                        "tier_icon": "⚪",
                        "findings": [],
                        "note": f"Aircraft {registration or msn} was officially removed from BIS list."
                    }

            # 2. Match against active aircraft
            matched_records = []
            for item in self.bis_data.get("active", []):
                curr_reg = normalize_registration(item.get("current_tail_number"))
                prev_reg = normalize_registration(item.get("previous_tail_number"))
                item_msn = str(item.get("msn", "")).strip()

                matched = False
                matched_field = None
                if norm_reg:
                    if curr_reg and norm_reg == curr_reg:
                        matched = True
                        matched_field = "current_tail_number"
                    elif prev_reg and norm_reg == prev_reg:
                        matched = True
                        matched_field = "previous_tail_number"

                if not matched and clean_msn:
                    if item_msn and clean_msn == item_msn:
                        matched = True
                        matched_field = "msn"

                if matched:
                    matched_records.append({
                        "matched_field": matched_field,
                        "owner_operator": item.get("owner_operator"),
                        "country": item.get("country"),
                        "current_tail_number": item.get("current_tail_number"),
                        "previous_tail_number": item.get("previous_tail_number"),
                        "msn": item.get("msn"),
                        "aircraft_type": item.get("aircraft_type"),
                    })

            if matched_records:
                primary = matched_records[0]
                return {
                    "tier": "POTENTIAL_MATCH",
                    "tier_icon": "🔴",
                    "finding": "EXPORT_CONTROL",
                    "reason": f"Matched BIS EAR potential violation list via {primary['matched_field']}",
                    "safety_label": SAFETY_LABEL,
                    "matched_records": matched_records,
                    "record": primary
                }

            return {
                "tier": "NO_MATCH",
                "tier_icon": "⚪",
                "finding": "CLEAN",
                "findings": [],
                "message": "No match found on BIS aircraft list"
            }
        except Exception as e:
            logger.error(f"Error checking aircraft {registration}/{msn}: {e}")
            return {
                "tier": "NO_MATCH",
                "tier_icon": "⚪",
                "finding": "ERROR",
                "error": str(e),
                "safety_label": SAFETY_LABEL
            }

    def check_airline(
        self,
        name: Optional[str] = None,
        icao: Optional[str] = None,
        iata: Optional[str] = None,
        aoc_state: Optional[str] = None
    ) -> Dict[str, Any]:
        """Screen an airline against EU Air Safety List (Annex A, Annex B) and FAA IASA Cat 2.
        All safety findings carry: 'Safety flag — not a sanctions finding'.
        """
        try:
            # 1. Alias resolution
            resolved = self.resolve_airline(name=name, icao=icao, iata=iata)
            lookup_name = resolved["canonical_airline"] if resolved else (name or "")
            lookup_icao = resolved["icao"] if resolved else (icao.strip().upper() if icao else "")
            lookup_country = aoc_state.strip() if aoc_state else (resolved["country"] if resolved else "")

            findings = []
            highest_tier = "NO_MATCH"
            tier_icon = "⚪"

            # 2. Check EU Air Safety List Annex B (Restricted)
            for item in self.eu_data.get("annex_b", []):
                b_name = item.get("airline", "")
                b_icao = item.get("icao_code", "")
                name_match = lookup_name and distinctive_match(lookup_name, b_name)
                icao_match = (lookup_icao and b_icao and lookup_icao == b_icao.upper())

                if name_match or icao_match:
                    findings.append({
                        "finding": "SAFETY_RESTRICTED",
                        "tier_icon": "⚠️",
                        "source": "EU Air Safety List (Annex B)",
                        "airline": item.get("airline"),
                        "state": item.get("state"),
                        "aoc_number": item.get("aoc_number"),
                        "icao_code": item.get("icao_code"),
                        "restricted_aircraft_types": item.get("restricted_aircraft_types"),
                        "permitted_aircraft_types": item.get("permitted_aircraft_types"),
                        "safety_label": SAFETY_LABEL
                    })
                    highest_tier = "POSSIBLE_MATCH_REVIEW"
                    tier_icon = "⚠️"

            # 3. Check EU Air Safety List Annex A (Banned)
            annex_a_match = False
            for item in self.eu_data.get("annex_a", []):
                a_name = item.get("airline", "")
                a_icao = item.get("icao_code", "")
                name_match = lookup_name and distinctive_match(lookup_name, a_name)
                icao_match = (lookup_icao and a_icao and a_icao != "Unknown" and lookup_icao == a_icao.upper())

                if name_match or icao_match:
                    findings.append({
                        "finding": "SAFETY_BAN",
                        "tier_icon": "⚠️",
                        "source": "EU Air Safety List (Annex A)",
                        "airline": item.get("airline"),
                        "state": item.get("state"),
                        "aoc_number": item.get("aoc_number"),
                        "icao_code": item.get("icao_code"),
                        "safety_label": SAFETY_LABEL
                    })
                    annex_a_match = True
                    highest_tier = "POSSIBLE_MATCH_REVIEW"
                    tier_icon = "⚠️"
                    break

            # 4. Check EU Air Safety List State-Level Ban
            if not annex_a_match and lookup_country:
                for b_state in self.eu_data.get("banned_states", []):
                    if normalize_token(lookup_country) == normalize_token(b_state) or \
                       normalize_token(lookup_country) in normalize_token(b_state):
                        findings.append({
                            "finding": "SAFETY_BAN",
                            "tier_icon": "⚠️",
                            "source": "EU Air Safety List (State-level ban)",
                            "state": lookup_country,
                            "airline": lookup_name or name,
                            "safety_label": SAFETY_LABEL
                        })
                        highest_tier = "POSSIBLE_MATCH_REVIEW"
                        tier_icon = "⚠️"
                        break

            # 5. Check FAA IASA (Category 2 Oversight)
            if lookup_country:
                for cat2_item in self.faa_data:
                    c_name = cat2_item.get("country", "")
                    if normalize_token(lookup_country) == normalize_token(c_name) or \
                       normalize_token(c_name) in normalize_token(lookup_country):
                        findings.append({
                            "finding": "SAFETY_OVERSIGHT",
                            "tier_icon": "⚠️",
                            "source": "FAA IASA Category 2",
                            "country": c_name,
                            "category": "2",
                            "airline": lookup_name or name,
                            "safety_label": SAFETY_LABEL
                        })
                        highest_tier = "POSSIBLE_MATCH_REVIEW"
                        tier_icon = "⚠️"
                        break

            if findings:
                return {
                    "tier": highest_tier,
                    "tier_icon": tier_icon,
                    "resolved_airline": resolved,
                    "findings": findings,
                    "safety_label": SAFETY_LABEL
                }

            return {
                "tier": "NO_MATCH",
                "tier_icon": "⚪",
                "resolved_airline": resolved,
                "findings": [],
                "message": "Clean — no aviation safety bans or oversight flags found"
            }

        except Exception as e:
            logger.error(f"Error checking airline {name}/{icao}/{iata}/{aoc_state}: {e}")
            return {
                "tier": "NO_MATCH",
                "tier_icon": "⚪",
                "findings": [],
                "error": str(e),
                "safety_label": SAFETY_LABEL
            }
