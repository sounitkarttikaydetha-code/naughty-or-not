"""
Identifier Matching, Corroboration & Conflict Engine (T11 Part H).
Handles:
- Exact ID/passport/IMO matching (id_match -> 🔴)
- IMO check-digit validation
- Corroboration upgrade (🟠 + DOB + Nat -> 🔴 name_dob_nat_match)
- Controlled conflict downgrades (1 conflict -> 🟠; 2 conflicts -> 🟠 / ℹ️)
- Never hides matches, never returns NO_MATCH if hit exists
"""

from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple
import yaml

from modules.screening.tiering import (
    TIER_POTENTIAL_MATCH,
    TIER_POSSIBLE_MATCH,
    TIER_BELOW_THRESHOLD,
    TIER_NO_MATCH,
)

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "identifier_rules.yaml"


def validate_imo(imo_input: str) -> Tuple[bool, Optional[str]]:
    """
    Validate an IMO ship identification number according to SOLAS regulation XI-1/3.
    Must consist of 'IMO' followed by 7 digits, where the 7th digit equals
    the check-digit: (d1*7 + d2*6 + d3*5 + d4*4 + d5*3 + d6*2) % 10.
    """
    if not imo_input:
        return False, "Empty IMO input"
    clean = re.sub(r"[^0-9]", "", str(imo_input))
    if len(clean) != 7:
        return False, f"IMO must have 7 digits (got {len(clean)})"

    digits = [int(c) for c in clean]
    weights = [7, 6, 5, 4, 3, 2]
    calc_sum = sum(d * w for d, w in zip(digits[:6], weights))
    expected_check = calc_sum % 10

    if digits[6] != expected_check:
        return False, f"Invalid IMO check digit: expected {expected_check}, got {digits[6]}"
    return True, f"IMO {clean}"


def extract_candidate_identifiers(entity: Dict[str, Any]) -> Set[str]:
    """Extract all normalized searchable identifiers from an entity record."""
    ids: Set[str] = set()
    if not entity:
        return ids

    # 1. Source ID
    sid = str(entity.get("sourceID") or entity.get("id") or entity.get("authority_id") or "").strip().lower()
    if sid:
        ids.add(sid)
        ids.add(sid.replace("-", "").replace("_", ""))

    # 2. Identifications list (passports, national IDs, tax IDs)
    identifications = entity.get("identifications") or []
    for item in identifications:
        if isinstance(item, dict):
            num = str(item.get("number") or item.get("id") or "").strip().lower()
            if num:
                ids.add(num)
                ids.add(re.sub(r"[^a-z0-9]", "", num))
        elif isinstance(item, str):
            s = item.strip().lower()
            if s:
                ids.add(s)
                ids.add(re.sub(r"[^a-z0-9]", "", s))

    # 3. SourceData identifiers
    sd = entity.get("sourceData") or {}
    if isinstance(sd, dict):
        for field in ["id", "idNumber", "passportNumber", "taxId", "vesselRegistration", "imoNumber"]:
            val = str(sd.get(field) or "").strip().lower()
            if val:
                ids.add(val)
                ids.add(re.sub(r"[^a-z0-9]", "", val))

    # 4. Remarks text search for IMO, tail, MSN
    remarks = str(sd.get("remarks") or entity.get("remarks") or "")
    if remarks:
        for imo in re.findall(r"(?i)\bIMO\s*[:#-]?\s*(\d{7})\b", remarks):
            ids.add(f"imo {imo}".lower())
            ids.add(imo.lower())
        for tail in re.findall(r"(?i)\b(?:tail|registration)?\s*[:#-]?\s*([A-Z0-9]{1,3}-[A-Z0-9]{2,6})\b", remarks):
            ids.add(tail.lower())
            ids.add(tail.lower().replace("-", ""))
        for msn in re.findall(r"(?i)\b(?:MSN|serial\s*(?:no|number)?)\s*[:#-]?\s*(\d+)\b", remarks):
            ids.add(msn.lower())

    # 5. Aircraft / Vessel direct fields
    for field in ["current_tail_number", "previous_tail_number", "msn", "aoc_number"]:
        v = str(entity.get(field) or "").strip().lower()
        if v:
            ids.add(v)
            ids.add(v.replace("-", ""))

    return ids


def match_identifiers(query_ids: List[str], entity: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Check if any query identifier exactly matches candidate identifiers."""
    if not query_ids or not entity:
        return False, None

    cand_ids = extract_candidate_identifiers(entity)
    for q in query_ids:
        q_norm = str(q).strip().lower()
        q_clean = re.sub(r"[^a-z0-9]", "", q_norm)
        if not q_clean:
            continue
        if q_norm in cand_ids or q_clean in cand_ids:
            return True, q.strip()
    return False, None


def assess_corroboration(
    entity: Dict[str, Any],
    dob: Optional[str] = None,
    yob: Optional[str] = None,
    nationality: Optional[str] = None,
    identifiers: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Evaluate corroborate factors and conflict status against candidate record.
    Returns dictionary with:
    - dob_status: 'MATCH' | 'CONFLICT' | 'UNKNOWN'
    - nat_status: 'MATCH' | 'CONFLICT' | 'UNKNOWN'
    - id_status: 'MATCH' | 'UNKNOWN'
    - matched_id: str or None
    - conflict_count: int
    - corroboration_upgrade: bool (True when both full DOB and Nationality match)
    """
    res = {
        "dob_status": "UNKNOWN",
        "nat_status": "UNKNOWN",
        "id_status": "UNKNOWN",
        "matched_id": None,
        "conflict_count": 0,
        "corroboration_upgrade": False,
    }

    # 1. Identifier Check
    if identifiers:
        id_matched, matched_val = match_identifiers(identifiers, entity)
        if id_matched:
            res["id_status"] = "MATCH"
            res["matched_id"] = matched_val

    # 2. DOB Check
    target_year = None
    target_dob_full = None
    if dob:
        clean_dob = str(dob).strip()
        m_full = re.search(r"\b(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})\b", clean_dob)
        if m_full:
            target_dob_full = m_full.group(1).replace("/", "-")
        m_yr = re.search(r"\b(19\d\d|20\d\d)\b", clean_dob)
        if m_yr:
            target_year = m_yr.group(1)
    elif yob:
        target_year = str(yob).strip()

    person = entity.get("person") or {}
    sd = entity.get("sourceData") or {}

    cand_dates: List[str] = []
    if person.get("birthDate"):
        cand_dates.append(str(person.get("birthDate")))
    if isinstance(sd, dict):
        if sd.get("DOB"):
            cand_dates.append(str(sd.get("DOB")))
        for bd in sd.get("birthDates") or []:
            cand_dates.append(str(bd))
        for by in sd.get("birthYears") or []:
            cand_dates.append(str(by))

    if target_year or target_dob_full:
        if not cand_dates:
            res["dob_status"] = "UNKNOWN"
        else:
            cand_years = set()
            exact_dob_hit = False
            for cd in cand_dates:
                cd_clean = cd.replace("/", "-")
                if target_dob_full and target_dob_full in cd_clean:
                    exact_dob_hit = True
                for yr in re.findall(r"\b(19\d\d|20\d\d)\b", cd):
                    cand_years.add(yr)

            if exact_dob_hit or (target_year and target_year in cand_years):
                res["dob_status"] = "MATCH"
            elif cand_years and target_year and target_year not in cand_years:
                res["dob_status"] = "CONFLICT"
                res["conflict_count"] += 1

    # 3. Nationality Check
    if nationality:
        user_nat = nationality.strip().lower()
        cand_nats: List[str] = []
        if person.get("placeOfBirth"):
            cand_nats.append(str(person.get("placeOfBirth")).lower())
        if person.get("nationalities"):
            for n in person.get("nationalities") or []:
                cand_nats.append(str(n).lower())
        if isinstance(sd, dict):
            for field in ["Nationality", "CountryOfBirth", "Citizenship"]:
                val = sd.get(field)
                if val:
                    cand_nats.append(str(val).lower())
            for c in sd.get("addressCountryDescriptions") or []:
                cand_nats.append(str(c).lower())

        if not cand_nats:
            res["nat_status"] = "UNKNOWN"
        else:
            nat_match = any(user_nat in cn or cn in user_nat for cn in cand_nats)
            if nat_match:
                res["nat_status"] = "MATCH"
            else:
                res["nat_status"] = "CONFLICT"
                res["conflict_count"] += 1

    # 4. Corroboration Upgrade Check
    # Triggers upgrade when both DOB and Nationality match
    if res["dob_status"] == "MATCH" and res["nat_status"] == "MATCH":
        res["corroboration_upgrade"] = True

    return res


def apply_identifier_and_conflict_rules(
    current_tier: str,
    current_reason: str,
    corroboration: Dict[str, Any],
) -> Tuple[str, str]:
    """
    Apply tier rules based on corroborated identifiers and conflicts.
    - Exact ID match -> 🔴 id_match
    - 🟠 + DOB + Nat match -> 🔴 name_dob_nat_match
    - 1 conflict: 🔴 -> 🟠 conflict_downgrade_1
    - 2 conflicts: 🔴 -> 🟠 conflict_downgrade_2; 🟠 -> ℹ️ conflict_downgrade_2
    - Never returns NO_MATCH if a candidate was matched.
    """
    # 1. Exact ID Match (Highest precedence)
    if corroboration.get("id_status") == "MATCH":
        return TIER_POTENTIAL_MATCH, "id_match"

    # 2. Corroboration Upgrade (🟠 -> 🔴)
    if current_tier == TIER_POSSIBLE_MATCH and corroboration.get("corroboration_upgrade"):
        return TIER_POTENTIAL_MATCH, "name_dob_nat_match"

    # 3. Controlled Conflict Downgrades
    conflicts = corroboration.get("conflict_count", 0)
    if conflicts == 1:
        if current_tier == TIER_POTENTIAL_MATCH:
            return TIER_POSSIBLE_MATCH, "conflict_downgrade_1"
    elif conflicts >= 2:
        if current_tier == TIER_POTENTIAL_MATCH:
            return TIER_POSSIBLE_MATCH, "conflict_downgrade_2"
        elif current_tier == TIER_POSSIBLE_MATCH:
            return TIER_BELOW_THRESHOLD, "conflict_downgrade_2"

    return current_tier, current_reason
