"""
Match Tiering Layer (v2)
Performs candidate retrieval from Watchman (minMatch=0.60), alias splitting,
weak word filtering, two-way core-name equivalence, person-specific validation,
secondary identifier conflict checks, and multi-tier categorization.
"""

import re
import unicodedata
from typing import Any, Dict, List, Optional, Set, Tuple

from modules.screening.config import (
    ALIAS_SPLIT_DELIMITERS,
    CANDIDATE_MIN_MATCH,
    COMPANY_TYPE_WORDS,
    MIN_DISTINCTIVE_WORD_LEN,
    NAME_VARIANTS,
    POSSIBLE_MATCH_THRESHOLD,
    POTENTIAL_MATCH_THRESHOLD,
    WEAK_WORDS,
)
from modules.watchman.client import WatchmanClient

# Tier Constants
TIER_POTENTIAL_MATCH = "POTENTIAL_MATCH"            # 🔴
TIER_POSSIBLE_MATCH = "POSSIBLE_MATCH_REVIEW"       # 🟠
TIER_NO_MATCH = "NO_MATCH"                          # ✅
TIER_NOT_CHECKED = "NOT_CHECKED"                    # ⚪

SOURCE_LISTS = ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]


def split_alias_parts(text: str) -> List[str]:
    """
    Split a name/alias string on brackets and d/b/a, a.k.a., f.k.a., etc.
    Treats each extracted part as a separate standalone alias candidate.
    """
    if not text:
        return []

    # 1. Extract bracketed parts: (...) [...] {...}
    brackets = re.findall(r"[\(\[\{]([^\)\]\}]+)[\)\]\}]", text)
    outside = re.sub(r"[\(\[\{][^\)\]\}]*[\)\]\}]", " ", text)
    parts = [outside] + brackets

    # 2. Split on d/b/a, a.k.a., f.k.a., formerly, etc.
    split_pattern = r"(?:\b(?:d/?b/?a|dba|aka|fka|formerly|also known as)\b|a\.k\.a\.|f\.k\.a\.)"
    split_regex = re.compile(split_pattern, re.IGNORECASE)

    results: List[str] = []
    for p in parts:
        subparts = split_regex.split(p)
        for s in subparts:
            cleaned = s.strip(" .,;:-_")
            if cleaned and cleaned not in results:
                results.append(cleaned)

    return results if results else [text.strip()]


def extract_all_aliases(entity: Dict[str, Any]) -> List[str]:
    """
    Extract all raw aliases across schemas and expand them using alias splitting.
    """
    raw_names: List[str] = []

    # Primary Name
    pname = entity.get("name")
    if pname:
        raw_names.append(pname)

    # Business altNames
    bus = entity.get("business") or {}
    for a in bus.get("altNames") or []:
        if a and a not in raw_names:
            raw_names.append(a)

    # Person altNames
    person = entity.get("person") or {}
    for a in person.get("altNames") or []:
        if a and a not in raw_names:
            raw_names.append(a)

    # sourceData fields (UK CSL, EU CSL, US OFAC)
    sd = entity.get("sourceData") or {}
    if isinstance(sd, dict):
        for field in ["Names", "nameAliasWholeNames"]:
            for a in sd.get(field) or []:
                if a and a not in raw_names:
                    raw_names.append(a)

        sdn_name = sd.get("sdnName")
        if sdn_name and sdn_name not in raw_names:
            raw_names.append(sdn_name)

        # Remarks (often contain a.k.a. '...')
        remarks = sd.get("remarks") or ""
        if remarks:
            aka_matches = re.findall(r"a\.k\.a\.\s*['\"]([^'\"]+)['\"]", remarks, re.IGNORECASE)
            for aka in aka_matches:
                if aka and aka not in raw_names:
                    raw_names.append(aka)

    # Expand every raw name through alias splitting
    expanded_aliases: List[str] = []
    for name in raw_names:
        parts = split_alias_parts(name)
        for part in parts:
            if part and part not in expanded_aliases:
                expanded_aliases.append(part)

    return expanded_aliases if expanded_aliases else ([pname] if pname else [])


def normalize_name(text: str) -> List[str]:
    """
    Normalise a name or alias string:
    - Lowercase
    - Fold accents / diacritics
    - Remove multi-word and single-word company-type designations
    - Remove punctuation
    - Return list of core tokens
    """
    if not text:
        return []

    # 1. Lowercase
    s = text.lower()

    # 2. Fold accents
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("utf-8")

    # 3. Remove multi-word company phrases first
    multi_word_phrases = [
        w.lower() for w in COMPANY_TYPE_WORDS if " " in w or "-" in w
    ]
    for phrase in sorted(multi_word_phrases, key=len, reverse=True):
        pattern = r"\b" + re.escape(phrase) + r"\b"
        s = re.sub(pattern, " ", s)

    # 4. Remove punctuation & symbols
    s = re.sub(r"[^\w\s]", " ", s)

    # 5. Tokenize
    tokens = s.split()

    # 6. Remove single-word company-type words and apply transliteration name variants
    single_word_set = {
        w.lower() for w in COMPANY_TYPE_WORDS if " " not in w and "-" not in w
    }
    core_tokens = [
        NAME_VARIANTS.get(w, w)
        for w in tokens
        if w and w not in single_word_set
    ]

    return core_tokens


COUNTRY_WORDS = {
    "india", "russia", "russian", "iran", "iraq", "iraqi", "china", "chinese",
    "usa", "us", "uk", "uae", "afghanistan", "syria", "korea", "dprk", "cuba",
    "belarus", "myanmar", "sudan", "venezuela", "yemen"
}


def check_core_name_match(
    q_words: List[str],
    c_words: List[str],
    is_person: bool = False,
) -> Tuple[bool, str]:
    """
    Check core-name equivalence between query tokens and candidate tokens.
    Returns (is_match, match_type):
      match_type in ["core_name_equal", "core_name", "core_name_forward", "core_name_reverse", "partial_name_person", ""]
    """
    if not q_words or not c_words:
        return False, ""

    q_set = set(q_words)
    c_set = set(c_words)
    weak_set = {w.lower() for w in WEAK_WORDS}

    # Rule 2: A core-name pass is blocked ONLY if every shared word is a weak word
    shared = q_set & c_set
    if not shared:
        return False, ""
    if shared.issubset(weak_set):
        return False, ""

    # Exact equality (ignoring word order)
    if q_set == c_set:
        return True, "core_name_equal"

    # Forward subset check: q_set is subset of c_set (candidate has extra words)
    # Weak words that appear in the listed name but not in the query do not block a pass.
    if q_set.issubset(c_set):
        if is_person:
            return True, "partial_name_person"
        else:
            extra_cand_words = c_set - q_set
            if extra_cand_words.issubset(weak_set):
                return True, "core_name"
            return False, ""

    # Reverse subset check: c_set is subset of q_set (Rule 1)
    if c_set.issubset(q_set):
        # Candidate core must have at least 1 distinctive word of 4 or more chars (not weak and not a country)
        distinctive_candidate_words = [
            w for w in c_set if len(w) >= MIN_DISTINCTIVE_WORD_LEN and w not in weak_set and w not in COUNTRY_WORDS
        ]
        if distinctive_candidate_words:
            if is_person:
                return True, "partial_name_person"
            else:
                return True, "core_name_reverse"

    return False, ""


def check_secondary_identifier_conflict(
    entity: Dict[str, Any],
    dob: Optional[str] = None,
    yob: Optional[str] = None,
    nationality: Optional[str] = None,
) -> bool:
    """
    Check if user-provided DOB/YOB or nationality conflicts with candidate data.
    Missing candidate data never conflicts.
    Returns True if there is a CLEAR conflict.
    """
    person = entity.get("person") or {}
    sd = entity.get("sourceData") or {}

    # 1. DOB / Year of Birth check
    target_year = None
    if yob:
        target_year = str(yob).strip()
    elif dob:
        m = re.search(r"\b(19\d\d|20\d\d)\b", str(dob))
        if m:
            target_year = m.group(1)

    if target_year:
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

        cand_years = set()
        for cd in cand_dates:
            matches = re.findall(r"\b(19\d\d|20\d\d)\b", cd)
            for yr in matches:
                cand_years.add(yr)

        if cand_years and target_year not in cand_years:
            return True

    # 2. Nationality check
    if nationality:
        user_nat = nationality.strip().lower()
        cand_nats: List[str] = []
        if person.get("placeOfBirth"):
            cand_nats.append(str(person.get("placeOfBirth")).lower())
        if isinstance(sd, dict):
            for field in ["Nationality", "CountryOfBirth"]:
                val = sd.get(field)
                if val:
                    cand_nats.append(str(val).lower())
            for c in sd.get("addressCountryDescriptions") or []:
                cand_nats.append(str(c).lower())

        if cand_nats:
            # Check if any candidate country string contains or matches user nationality
            match_found = any(user_nat in cn or cn in user_nat for cn in cand_nats)
            if not match_found:
                return True

    return False


def extract_program_info(entity: Dict[str, Any]) -> str:
    """Extract sanctions programme or sub-list (e.g. 'Denied Persons List')."""
    sd = entity.get("sourceData") or {}
    if not isinstance(sd, dict):
        sd = {}

    # US CSL source or programs
    csl_source = sd.get("Source")
    if csl_source:
        return csl_source

    # UK CSL Regime
    regime = sd.get("Regime")
    if regime:
        return regime

    # OFAC programs
    sinfo = entity.get("sanctionsInfo") or {}
    if isinstance(sinfo, dict) and sinfo.get("programs"):
        return ", ".join(sinfo.get("programs"))

    if sd.get("program"):
        prog = sd.get("program")
        return ", ".join(prog) if isinstance(prog, list) else str(prog)

    if sd.get("entityRegulationProgramme"):
        return sd.get("entityRegulationProgramme")

    return sd.get("Programs") or entity.get("sourceList", "")


def tier_single_entity(
    query: str,
    entity: Dict[str, Any],
    query_type: Optional[str] = None,
    dob: Optional[str] = None,
    yob: Optional[str] = None,
    nationality: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Tier a single candidate entity against the query.
    Returns None if discarded by Rule 6 (< 0.70 without core-name match).
    """
    if not query or not query.strip():
        return None

    score = float(entity.get("match", 0.0))
    primary_name = entity.get("name", "")
    all_aliases = extract_all_aliases(entity)

    if query_type:
        is_person = (query_type.lower() == "person")
    else:
        is_person = (
            entity.get("entityType") == "person"
            or bool(entity.get("person"))
        )

    q_words = normalize_name(query)

    # Evaluate primary name and all aliases
    best_match_type = ""
    best_matched_name = primary_name

    priority_map = {
        "core_name_equal": 4,
        "core_name": 3,
        "core_name_forward": 3,
        "core_name_reverse": 3,
        "partial_name_person": 2,
        "": 0,
    }

    for candidate_alias in all_aliases:
        c_words = normalize_name(candidate_alias)
        is_m, m_type = check_core_name_match(q_words, c_words, is_person=is_person)
        if is_m:
            if priority_map.get(m_type, 0) > priority_map.get(best_match_type, 0):
                best_match_type = m_type
                best_matched_name = candidate_alias

    core_pass = best_match_type in [
        "core_name_equal",
        "core_name",
        "core_name_forward",
        "core_name_reverse",
    ]

    # Rule 6: Candidates scoring 0.60–0.70 kept ONLY if a core-name check passes
    if score < POSSIBLE_MATCH_THRESHOLD and not (core_pass or best_match_type == "partial_name_person"):
        return None

    # Determine Tier and Reason
    tier = TIER_NO_MATCH
    reason = "none"

    if is_person:
        # Rule 5: Person Rule
        if score >= POTENTIAL_MATCH_THRESHOLD:
            tier = TIER_POTENTIAL_MATCH
            reason = (
                "score_and_core_name" if best_match_type == "core_name_equal" else "score"
            )
        elif best_match_type == "core_name_equal":
            tier = TIER_POTENTIAL_MATCH
            reason = "core_name"
        elif best_match_type == "partial_name_person":
            tier = TIER_POSSIBLE_MATCH
            reason = "partial_name_person"
        elif score >= POSSIBLE_MATCH_THRESHOLD:
            tier = TIER_POSSIBLE_MATCH
            reason = "score"

        # Secondary identifier conflict check
        if tier == TIER_POTENTIAL_MATCH:
            if check_secondary_identifier_conflict(entity, dob=dob, yob=yob, nationality=nationality):
                tier = TIER_POSSIBLE_MATCH
                reason = "secondary_identifier_conflict"

    else:
        # Organisation / Entity Rule
        if score >= POTENTIAL_MATCH_THRESHOLD and best_match_type == "core_name_reverse":
            tier = TIER_POTENTIAL_MATCH
            reason = "score_and_core_name_reverse"
        elif best_match_type == "core_name_reverse":
            tier = TIER_POTENTIAL_MATCH
            reason = "core_name_reverse"
        elif score >= POTENTIAL_MATCH_THRESHOLD and core_pass:
            tier = TIER_POTENTIAL_MATCH
            reason = "score_and_core_name"
        elif core_pass:
            tier = TIER_POTENTIAL_MATCH
            reason = "core_name"
        elif score >= POTENTIAL_MATCH_THRESHOLD:
            tier = TIER_POTENTIAL_MATCH
            reason = "score"
        elif score >= POSSIBLE_MATCH_THRESHOLD:
            tier = TIER_POSSIBLE_MATCH
            reason = "score"

    return {
        "tier": tier,
        "tier_icon": "🔴" if tier == TIER_POTENTIAL_MATCH else ("🟠" if tier == TIER_POSSIBLE_MATCH else ("✅" if tier == TIER_NO_MATCH else "⚪")),
        "reason": reason,
        "score": score,
        "score_source": entity.get("score_source", "query"),
        "primary_name": primary_name,
        "matched_name": best_matched_name,
        "entity_type": "person" if is_person else (entity.get("entityType") or "organisation"),
        "program": extract_program_info(entity),
        "source_list": entity.get("sourceList", ""),
        "source_id": entity.get("sourceID", ""),
        "core_pass": core_pass or (best_match_type == "partial_name_person"),
        "entity": entity,
    }


def screen_query_all_lists(
    query: str,
    client: Optional[WatchmanClient] = None,
    query_type: Optional[str] = None,
    dob: Optional[str] = None,
    yob: Optional[str] = None,
    nationality: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Screen a query across all 5 lists, applying all rules.
    Returns for each list:
      - 'best_hit': Dict with top hit metadata
      - 'red_hits': All POTENTIAL_MATCH (🔴) hits
      - 'orange_hits': Top 3 POSSIBLE_MATCH_REVIEW (🟠) hits
    """
    if client is None:
        client = WatchmanClient()

    results_by_source: Dict[str, Dict[str, Any]] = {}

    if not query or not query.strip():
        for src in SOURCE_LISTS:
            empty_hit = {
                "tier": TIER_NO_MATCH,
                "tier_icon": "✅",
                "reason": "none",
                "score": 0.0,
                "score_source": "query",
                "primary_name": "—",
                "matched_name": "—",
                "entity_type": query_type or "organisation",
                "program": "—",
                "source_list": src,
                "source_id": "—",
            }
            results_by_source[src] = {
                "best_hit": empty_hit,
                "red_hits": [],
                "orange_hits": [],
            }
        return results_by_source

    tier_order = {
        TIER_POTENTIAL_MATCH: 3,
        TIER_POSSIBLE_MATCH: 2,
        TIER_NO_MATCH: 1,
        TIER_NOT_CHECKED: 0,
    }

    for src in SOURCE_LISTS:
        # Candidate retrieval at 0.45 with limit=50 to capture split aliases like 'S7 AIRLINES'
        resp = client.search(
            name=query, min_match=0.45, source=src, limit=50
        )

        raw_entities = resp.get("results", {}).get("entities") or []
        entity_map = {e.get("sourceID"): e for e in raw_entities if e.get("sourceID")}

        # Extra retrieval pass: Query distinctive words (>= 4 chars, non-weak)
        q_tokens = normalize_name(query)
        weak_set = {w.lower() for w in WEAK_WORDS}
        distinctive_tokens = [w for w in q_tokens if w not in weak_set and len(w) >= 4]

        for token in distinctive_tokens:
            extra_resp = client.search(
                name=token, min_match=0.45, source=src, limit=50
            )
            extra_entities = extra_resp.get("results", {}).get("entities") or []
            for ee in extra_entities:
                sid = ee.get("sourceID")
                if sid and sid not in entity_map:
                    ee_copy = dict(ee)
                    ee_copy["score_source"] = "token_pass"
                    entity_map[sid] = ee_copy

        merged_raw_entities = list(entity_map.values())

        if resp.get("status") == "unavailable" and not merged_raw_entities:
            unavail_hit = {
                "tier": TIER_NOT_CHECKED,
                "tier_icon": "⚪",
                "reason": "watchman_unavailable",
                "score": 0.0,
                "score_source": "query",
                "primary_name": "—",
                "matched_name": "—",
                "entity_type": query_type or "organisation",
                "program": "—",
                "source_list": src,
                "source_id": "—",
                "error": resp.get("error"),
            }
            results_by_source[src] = {
                "best_hit": unavail_hit,
                "red_hits": [],
                "orange_hits": [],
            }
            continue

        evaluated_candidates: List[Dict[str, Any]] = []

        for ent in merged_raw_entities:
            tiered = tier_single_entity(
                query=query,
                entity=ent,
                query_type=query_type,
                dob=dob,
                yob=yob,
                nationality=nationality,
            )
            if tiered is not None:
                evaluated_candidates.append(tiered)

        if not evaluated_candidates:
            no_match_hit = {
                "tier": TIER_NO_MATCH,
                "tier_icon": "✅",
                "reason": "none",
                "score": 0.0,
                "score_source": "query",
                "primary_name": "—",
                "matched_name": "—",
                "entity_type": query_type or "organisation",
                "program": "—",
                "source_list": src,
                "source_id": "—",
            }
            results_by_source[src] = {
                "best_hit": no_match_hit,
                "red_hits": [],
                "orange_hits": [],
            }
            continue

        # Rule 7: Sort by tier, then by core-name pass, then by score
        evaluated_candidates.sort(
            key=lambda x: (
                tier_order.get(x["tier"], 0),
                1 if x["core_pass"] else 0,
                x["score"],
            ),
            reverse=True,
        )

        red_hits = [h for h in evaluated_candidates if h["tier"] == TIER_POTENTIAL_MATCH]
        orange_hits = [h for h in evaluated_candidates if h["tier"] == TIER_POSSIBLE_MATCH][:3]

        best_hit = evaluated_candidates[0]

        results_by_source[src] = {
            "best_hit": best_hit,
            "red_hits": red_hits,
            "orange_hits": orange_hits,
        }

    return results_by_source


# Backward-compatible wrapper for previous smoke runner
def screen_query_per_list(
    query: str,
    client: Optional[WatchmanClient] = None,
    query_type: Optional[str] = None,
    dob: Optional[str] = None,
    yob: Optional[str] = None,
    nationality: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Backward compatible wrapper returning best_hit per source."""
    full_results = screen_query_all_lists(
        query=query,
        client=client,
        query_type=query_type,
        dob=dob,
        yob=yob,
        nationality=nationality,
    )
    return {src: data["best_hit"] for src, data in full_results.items()}
