"""Aviation screening client for aircraft and airlines against:
- BIS List of Commercial and Private Aircraft in Potential Violation of the EAR
- EU Air Safety List (Annex A bans and Annex B restrictions)
- FAA International Aviation Safety Assessment (IASA) Category 2 safety oversight
"""

import csv
import logging
import re
import unicodedata
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
BIS_EXPORT_CONTROL_LABEL = "Export-control restriction (US EAR) — verify before providing any service"

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "aviation"
ALIAS_FILE = DATA_DIR / "airline_aliases.csv"


def normalize_registration(reg: Optional[str]) -> str:
    """Normalize aircraft registration (tail number) by stripping hyphens, spaces, and uppercasing."""
    if not reg:
        return ""
    return re.sub(r'[^A-Za-z0-9]', '', reg).upper()


def normalize_token(s: Optional[str]) -> str:
    """Normalize string for fuzzy comparison by decomposing unicode accents and lowercasing."""
    if not s:
        return ""
    decomposed = unicodedata.normalize('NFKD', s)
    return re.sub(r'[^a-zA-Z0-9]', '', decomposed).lower()


WEAK_WORDS = {
    "air", "airlines", "airline", "airways", "aviation", "aero", "group", "holdings",
    "holding", "international", "services", "company", "co", "ltd", "llc", "jsc", "pjsc",
    "joint", "stock", "public", "limited", "the", "and", "of", "carrier", "carriers",
    "generic",
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
    q_words = [w.lower() for w in re.split(r'[^a-zA-Z0-9]', query) if w]
    t_words = [w.lower() for w in re.split(r'[^a-zA-Z0-9]', target) if w]

    # Distinctive non-weak words with length >= 4
    q_distinctive = {w for w in q_words if w not in WEAK_WORDS and len(w) >= 4}
    t_distinctive = {w for w in t_words if w not in WEAK_WORDS and len(w) >= 4}

    if q_distinctive and t_distinctive and (q_distinctive & t_distinctive):
        return True

    # Check substring containment if long enough
    if len(q_norm) >= 4 and len(t_norm) >= 4:
        if q_norm in t_norm or t_norm in q_norm:
            # Avoid generic short prefixes matching
            if q_words and q_words[0] not in WEAK_WORDS:
                return True

    return False


class AviationClient:
    """Screening client for Aviation safety and export controls."""

    def __init__(self):
        self.aliases: List[Dict[str, str]] = []
        self._load_aliases()
        self._load_data()

    def _load_aliases(self) -> None:
        """Load curated airline aliases mapping to official names and codes."""
        if not ALIAS_FILE.is_file():
            logger.warning(f"Airline aliases file not found at {ALIAS_FILE}")
            return
        try:
            with open(ALIAS_FILE, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                self.aliases = [row for row in reader]
        except Exception as e:
            logger.error(f"Error loading airline aliases: {e}")

    def _load_data(self) -> None:
        """Load and cache parsed data from local copies."""
        self.bis_data = parse_bis_aircraft()
        self.eu_data = parse_eu_air_safety_list()
        self.faa_data = parse_faa_iasa()

    def resolve_airline(
        self,
        name: Optional[str] = None,
        icao: Optional[str] = None,
        iata: Optional[str] = None
    ) -> Optional[Dict[str, str]]:
        """Resolve airline alias / code to canonical name and details."""
        clean_name = normalize_token(name)
        clean_icao = icao.strip().upper() if icao else None
        clean_iata = iata.strip().upper() if iata else None

        for row in self.aliases:
            canon = row.get("canonical airline") or row.get("canonical_airline") or ""
            aliases_str = row.get("aliases") or row.get("alias") or ""
            row_icao = (row.get("ICAO") or row.get("icao") or "").upper()
            row_iata = (row.get("IATA") or row.get("iata") or "").upper()
            row_country = row.get("country", "")

            ret_val = {
                "canonical_airline": canon,
                "country": row_country,
                "icao": row_icao,
                "iata": row_iata,
                "source_url": row.get("source_url", ""),
            }

            if clean_icao and row_icao == clean_icao:
                return ret_val
            if clean_iata and row_iata == clean_iata:
                return ret_val

            all_names = [canon] + [a.strip() for a in aliases_str.split(';') if a.strip()]
            for n in all_names:
                if clean_name and (clean_name == normalize_token(n) or clean_name == normalize_token(canon)):
                    return ret_val

        return None

    def check_aircraft(
        self,
        registration: Optional[str] = None,
        msn: Optional[str] = None,
        operator: Optional[str] = None,
        aircraft_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Screen aircraft against BIS potential violation list.
        Never matches aircraft in the removals section.
        Applies MSN rule:
          - Tail match (current or previous) -> 🔴 POTENTIAL_MATCH
          - MSN only -> 🟠 POSSIBLE_MATCH_REVIEW ('confirm aircraft type')
          - MSN + matching type or operator -> 🔴 POTENTIAL_MATCH
        Label: 'Export-control restriction (US EAR) — verify before providing any service'
        Clean result carries NO flag label.
        """
        # Check source failure
        if self.bis_data.get("status") == "FAILED":
            return {
                "tier": "NOT_CHECKED",
                "tier_icon": "⚪",
                "finding": "SOURCE_UNAVAILABLE",
                "error": self.bis_data.get("error", "Source unparseable"),
                "last_good_date": self.bis_data.get("last_good_date"),
                "label": BIS_EXPORT_CONTROL_LABEL,
            }

        try:
            norm_reg = normalize_registration(registration)
            clean_msn = str(msn).strip() if msn else ""

            if not norm_reg and not clean_msn:
                return {
                    "tier": "NO_MATCH",
                    "tier_icon": "✅",
                    "findings": [],
                    "message": "No registration or MSN provided",
                    "label": None,
                }

            # 1. Guard against removals: NEVER match removed aircraft
            for rem in self.bis_data.get("removals", []):
                rem_reg = normalize_registration(rem.get("tail_number"))
                rem_msn = str(rem.get("msn", "")).strip()
                if (norm_reg and norm_reg == rem_reg) or (clean_msn and clean_msn == rem_msn):
                    return {
                        "tier": "NO_MATCH",
                        "tier_icon": "✅",
                        "finding": "REMOVAL",
                        "findings": [],
                        "note": f"Aircraft {registration or msn} was officially removed from BIS list.",
                        "label": None,
                    }

            # 2. Match against active aircraft
            reg_matched_records = []
            msn_matched_records = []

            for item in self.bis_data.get("active", []):
                curr_reg = normalize_registration(item.get("current_tail_number"))
                prev_reg = normalize_registration(item.get("previous_tail_number"))
                item_msn = str(item.get("msn", "")).strip()

                if norm_reg and (norm_reg == curr_reg or norm_reg == prev_reg):
                    field = "current_tail_number" if norm_reg == curr_reg else "previous_tail_number"
                    rec = dict(item)
                    rec["matched_field"] = field
                    reg_matched_records.append(rec)

                if clean_msn and clean_msn == item_msn:
                    rec = dict(item)
                    rec["matched_field"] = "msn"
                    msn_matched_records.append(rec)

            # Rule: Tail number match -> 🔴
            if reg_matched_records:
                primary = reg_matched_records[0]
                return {
                    "tier": "POTENTIAL_MATCH",
                    "tier_icon": "🔴",
                    "finding": "EXPORT_CONTROL",
                    "reason": f"Matched BIS list via {primary['matched_field']}",
                    "label": BIS_EXPORT_CONTROL_LABEL,
                    "matched_records": reg_matched_records,
                    "record": primary,
                }

            # Rule: MSN match
            if msn_matched_records:
                primary = msn_matched_records[0]
                has_corroboration = False
                if operator and primary.get("owner_operator"):
                    if distinctive_match(operator, primary["owner_operator"]):
                        has_corroboration = True
                if aircraft_type and primary.get("aircraft_type"):
                    if distinctive_match(aircraft_type, primary["aircraft_type"]):
                        has_corroboration = True

                if has_corroboration:
                    return {
                        "tier": "POTENTIAL_MATCH",
                        "tier_icon": "🔴",
                        "finding": "EXPORT_CONTROL",
                        "reason": "MSN and matching aircraft type/operator",
                        "label": BIS_EXPORT_CONTROL_LABEL,
                        "matched_records": msn_matched_records,
                        "record": primary,
                    }
                else:
                    return {
                        "tier": "POSSIBLE_MATCH_REVIEW",
                        "tier_icon": "🟠",
                        "finding": "EXPORT_CONTROL",
                        "reason": "confirm aircraft type",
                        "message": "MSN matched. Confirm aircraft type or operator to verify.",
                        "label": BIS_EXPORT_CONTROL_LABEL,
                        "matched_records": msn_matched_records,
                        "record": primary,
                    }

            return {
                "tier": "NO_MATCH",
                "tier_icon": "✅",
                "finding": "CLEAN",
                "findings": [],
                "message": "No match found on BIS aircraft list",
                "label": None,
            }
        except Exception as e:
            logger.error(f"Error checking aircraft {registration}/{msn}: {e}")
            return {
                "tier": "NOT_CHECKED",
                "tier_icon": "⚪",
                "finding": "ERROR",
                "error": str(e),
                "label": BIS_EXPORT_CONTROL_LABEL,
            }

    def check_airline(
        self,
        name: Optional[str] = None,
        icao: Optional[str] = None,
        iata: Optional[str] = None,
        aoc_state: Optional[str] = None
    ) -> Dict[str, Any]:
        """Screen an airline against EU Air Safety List (Annex A, Annex B) and FAA IASA Cat 2.
        Result types for safety findings:
          - SAFETY_BAN (Annex A or State-level ban)
          - SAFETY_RESTRICTED (Annex B)
          - SAFETY_OVERSIGHT (FAA IASA Category 2)
        All safety findings carry: 'Safety flag — not a sanctions finding'.
        Clean result carries NO flag label.
        """
        # Check source failures
        if self.eu_data.get("status") == "FAILED" or self.faa_data.get("status") == "FAILED":
            err = self.eu_data.get("error") or self.faa_data.get("error")
            date = self.eu_data.get("last_good_date") or self.faa_data.get("last_good_date")
            return {
                "tier": "NOT_CHECKED",
                "tier_icon": "⚪",
                "finding": "SOURCE_UNAVAILABLE",
                "error": err,
                "last_good_date": date,
                "safety_label": SAFETY_LABEL,
            }

        try:
            # 1. Alias resolution
            resolved = self.resolve_airline(name=name, icao=icao, iata=iata)
            lookup_name = resolved["canonical_airline"] if resolved else (name or "")
            lookup_icao = resolved["icao"] if resolved else (icao.strip().upper() if icao else "")
            lookup_country = aoc_state.strip() if aoc_state else (resolved["country"] if resolved else "")

            findings = []

            # 2. Check EU Air Safety List Annex B (Restricted)
            for item in self.eu_data.get("annex_b", []):
                b_name = item.get("airline", "")
                b_icao = item.get("icao_code", "")
                name_match = lookup_name and distinctive_match(lookup_name, b_name)
                icao_match = (lookup_icao and b_icao and lookup_icao == b_icao.upper())

                if name_match or icao_match:
                    findings.append({
                        "finding": "SAFETY_RESTRICTED",
                        "tier": "SAFETY_RESTRICTED",
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
                        "tier": "SAFETY_BAN",
                        "tier_icon": "⚠️",
                        "source": "EU Air Safety List (Annex A)",
                        "airline": item.get("airline"),
                        "state": item.get("state"),
                        "aoc_number": item.get("aoc_number"),
                        "icao_code": item.get("icao_code"),
                        "safety_label": SAFETY_LABEL
                    })
                    annex_a_match = True
                    break

            # 4. Check EU Air Safety List State-Level Ban (16 states with all air carriers banned)
            if not annex_a_match and lookup_country:
                for b_state in self.eu_data.get("banned_states", []):
                    if normalize_token(lookup_country) == normalize_token(b_state) or \
                       normalize_token(lookup_country) in normalize_token(b_state):
                        findings.append({
                            "finding": "SAFETY_BAN",
                            "tier": "SAFETY_BAN",
                            "tier_icon": "⚠️",
                            "source": "EU Air Safety List (State-level ban)",
                            "state": lookup_country,
                            "airline": lookup_name or name,
                            "safety_label": SAFETY_LABEL
                        })
                        break

            # 5. Check FAA IASA (Category 2 Oversight)
            if lookup_country:
                for cat2_item in self.faa_data.get("countries", []):
                    c_name = cat2_item.get("country", "")
                    if normalize_token(lookup_country) == normalize_token(c_name) or \
                       normalize_token(c_name) in normalize_token(lookup_country):
                        findings.append({
                            "finding": "SAFETY_OVERSIGHT",
                            "tier": "SAFETY_OVERSIGHT",
                            "tier_icon": "⚠️",
                            "source": "FAA IASA Category 2",
                            "country": c_name,
                            "category": "2",
                            "airline": lookup_name or name,
                            "safety_label": SAFETY_LABEL
                        })
                        break

            if findings:
                # Severity order: SAFETY_BAN > SAFETY_RESTRICTED > SAFETY_OVERSIGHT
                finding_types = [f["finding"] for f in findings]
                if "SAFETY_BAN" in finding_types:
                    highest_tier = "SAFETY_BAN"
                elif "SAFETY_RESTRICTED" in finding_types:
                    highest_tier = "SAFETY_RESTRICTED"
                else:
                    highest_tier = "SAFETY_OVERSIGHT"

                return {
                    "tier": highest_tier,
                    "tier_icon": "⚠️",
                    "resolved_airline": resolved,
                    "findings": findings,
                    "safety_label": SAFETY_LABEL
                }

            return {
                "tier": "NO_MATCH",
                "tier_icon": "✅",
                "resolved_airline": resolved,
                "findings": [],
                "message": "Clean — no aviation safety bans or oversight flags found",
                "safety_label": None
            }

        except Exception as e:
            logger.error(f"Error checking airline {name}/{icao}/{iata}/{aoc_state}: {e}")
            return {
                "tier": "NOT_CHECKED",
                "tier_icon": "⚪",
                "findings": [],
                "error": str(e),
                "safety_label": SAFETY_LABEL
            }

    def screen_airline(
        self,
        name: Optional[str] = None,
        aoc_state: Optional[str] = None,
        icao: Optional[str] = None,
        iata: Optional[str] = None,
    ) -> Dict[str, Any]:
        """UI wrapper for airline screening returning formatted findings."""
        res = self.check_airline(name=name, aoc_state=aoc_state, icao=icao, iata=iata)
        ui_findings = []
        for f in res.get("findings", []):
            airline_name = f.get("airline") or name or "Unknown carrier"
            source = f.get("source") or "Aviation Safety List"
            state = f.get("state") or aoc_state or ""
            detail_str = f"{airline_name} — {source}"
            if state:
                detail_str += f" (State: {state})"
            ui_findings.append({
                "result_type": f.get("finding", "SAFETY_FLAG"),
                "details": detail_str,
                "source": source,
                "safety_label": f.get("safety_label", SAFETY_LABEL),
                "tier": f.get("tier", "POSSIBLE_MATCH_REVIEW"),
            })
        return {
            "tier": res.get("tier", "NO_MATCH"),
            "findings": ui_findings,
            "raw": res,
        }

    def screen_aircraft(
        self,
        tail_number: Optional[str] = None,
        msn: Optional[str] = None,
        operator: Optional[str] = None,
        aircraft_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """UI wrapper for aircraft screening returning formatted findings."""
        res = self.check_aircraft(registration=tail_number, msn=msn, operator=operator, aircraft_type=aircraft_type)
        ui_findings = []
        if res.get("finding") == "EXPORT_CONTROL":
            rec = res.get("record", {})
            curr_tail = rec.get("current_tail_number") or tail_number or "Unknown"
            owner = rec.get("owner_operator") or operator or "Unknown operator"
            rec_msn = rec.get("msn") or msn or ""
            details = f"Tail: {curr_tail} | Owner/Operator: {owner}"
            if rec_msn:
                details += f" | MSN: {rec_msn}"
            ui_findings.append({
                "result_type": "EAR_RESTRICTION",
                "details": details,
                "source": "BIS List of Aircraft in Potential Violation of the EAR",
                "label": res.get("label", BIS_EXPORT_CONTROL_LABEL),
                "tier": "POTENTIAL_MATCH",
            })
        return {
            "tier": res.get("tier", "NO_MATCH"),
            "findings": ui_findings,
            "raw": res,
        }

