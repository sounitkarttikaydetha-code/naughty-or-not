"""
Match Tiering Layer (v2)
Performs candidate retrieval from Watchman (minMatch=0.60), alias splitting,
weak word filtering, two-way core-name equivalence, person-specific validation,
secondary identifier conflict checks, and multi-tier categorization.
"""

import csv
import difflib
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from modules.screening.config import (
    ALIAS_SPLIT_DELIMITERS,
    CANDIDATE_MIN_MATCH,
    DISPLAY_MIN_MATCH,
    DISPLAY_LIMIT,
    COMPANY_TYPE_WORDS,
    ENABLE_COUNTRY_WORDS_GUARD,
    COUNTRY_WORDS,
    FUZZY_WORD_MIN_LEN,
    FUZZY_WORD_MIN_SIMILARITY,
    MIN_DISTINCTIVE_WORD_LEN,
    NAME_VARIANTS,
    POSSIBLE_MATCH_THRESHOLD,
    POTENTIAL_MATCH_THRESHOLD,
    WEAK_WORDS,
    KNOWN_CITIES as CONFIG_KNOWN_CITIES,
)
from modules.watchman.client import WatchmanClient

# Tier Constants
TIER_POTENTIAL_MATCH = "POTENTIAL_MATCH"            # 🔴
TIER_POSSIBLE_MATCH = "POSSIBLE_MATCH_REVIEW"       # 🟠
TIER_BELOW_THRESHOLD = "BELOW_THRESHOLD"            # ℹ️
TIER_NO_MATCH = "NO_MATCH"                          # ✅
TIER_NOT_CHECKED = "NOT_CHECKED"                    # ⚪

SOURCE_LISTS = ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]

KNOWN_CITIES = set(CONFIG_KNOWN_CITIES)



def is_ignorable_bracket(content: str) -> bool:
    """
    Check if bracketed text is only a country, legal form, city, or weak word.
    Such text should NOT become a standalone alias candidate (e.g. '(India)', '(Pvt) Ltd', '(Dubai)').
    """
    tokens = normalize_name(content)
    if not tokens:
        return True

    ignorable_set = {
        w.lower() for w in (
            COUNTRY_WORDS + COMPANY_TYPE_WORDS + WEAK_WORDS + list(KNOWN_CITIES)
        )
    }
    return all(t in ignorable_set for t in tokens)


def split_alias_parts(text: str) -> List[str]:
    """
    Split a name/alias string on brackets and d/b/a, a.k.a., f.k.a., etc.
    Treats each extracted part as a separate standalone alias candidate.
    Discards bracket text that is purely a country, legal form, or city.
    """
    if not text:
        return []

    # 1. Extract bracketed parts: (...) [...] {...}
    raw_brackets = re.findall(r"[\(\[\{]([^\)\]\}]+)[\)\]\}]", text)
    outside = re.sub(r"[\(\[\{][^\)\]\}]*[\)\]\}]", " ", text)

    # Filter out ignorable brackets
    valid_brackets = [b for b in raw_brackets if not is_ignorable_bracket(b)]
    parts = [outside] + valid_brackets

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




def is_fuzzy_word_pair(w1: str, w2: str) -> bool:
    """Check if two words are a fuzzy match: >= 5 chars each and >= 90% similarity."""
    if len(w1) < FUZZY_WORD_MIN_LEN or len(w2) < FUZZY_WORD_MIN_LEN:
        return False
    # Stem differences (e.g. siberia vs siberian) are not fuzzy misspellings
    if w1 + "n" == w2 or w2 + "n" == w1:
        return False
    return difflib.SequenceMatcher(None, w1, w2).ratio() >= FUZZY_WORD_MIN_SIMILARITY


def check_core_name_match(
    q_words: List[str],
    c_words: List[str],
    is_person: bool = False,
) -> Tuple[bool, str]:
    """
    Check core-name equivalence between query tokens and candidate tokens.
    Treats country words as weak words: a core-name pass (forward or reverse)
    is blocked if every shared word is weak or a country word.
    Fuzzy word matching (>=5 chars, >=90% similarity) returns 'core_name_fuzzy'.
    Returns (is_match, match_type):
      match_type in ["core_name_equal", "core_name", "core_name_forward", "core_name_reverse", "partial_name_person", "core_name_fuzzy", ""]
    """
    if not q_words or not c_words:
        return False, ""

    q_set = set(q_words)
    c_set = set(c_words)
    weak_set = {w.lower() for w in WEAK_WORDS}
    country_set = {w.lower() for w in COUNTRY_WORDS}
    effective_weak = weak_set | country_set

    # Rule 2 / T1.6.1: A core-name pass is blocked if EVERY shared word is weak or a country word
    shared = q_set & c_set
    shared_has_distinctive = bool(shared and not shared.issubset(effective_weak))

    # Exact equality (ignoring word order)
    if q_set == c_set:
        if shared_has_distinctive:
            return True, "core_name_equal"

    # Forward subset check: q_set is subset of c_set (candidate has extra words)
    # Weak/country words that appear in the listed name but not in the query do not block a pass.
    if q_set.issubset(c_set) and shared_has_distinctive:
        if is_person:
            return True, "partial_name_person"
        else:
            extra_cand_words = c_set - q_set
            if extra_cand_words.issubset(effective_weak):
                return True, "core_name"

    # Reverse subset check: c_set is subset of q_set (Rule 1 / T1.6.1)
    if c_set.issubset(q_set):
        # Candidate core must have at least 1 distinctive word of 4 or more chars
        distinctive_candidate_words = [
            w for w in c_set if len(w) >= MIN_DISTINCTIVE_WORD_LEN and w not in effective_weak
        ]
        if distinctive_candidate_words:
            if is_person:
                return True, "partial_name_person"
            else:
                return True, "core_name_reverse"

    # Fuzzy word matching: words >= 5 chars with >= 85% similarity (T1.6.5)
    # Forward fuzzy: match all q_words to c_words
    matched_c = set()
    matched_q = set()
    has_fuzzy = False
    for q in q_words:
        if q in c_set and q not in matched_c:
            matched_q.add(q)
            matched_c.add(q)
    for q in q_words:
        if q not in matched_q:
            for c in c_words:
                if c not in matched_c and is_fuzzy_word_pair(q, c):
                    matched_q.add(q)
                    matched_c.add(c)
                    has_fuzzy = True
                    break
    if has_fuzzy and matched_q == q_set:
        extra = c_set - matched_c
        if extra.issubset(effective_weak) or is_person:
            distinctive = [w for w in matched_c if len(w) >= MIN_DISTINCTIVE_WORD_LEN and w not in effective_weak]
            if distinctive:
                return True, "core_name_fuzzy"

    # Reverse fuzzy: match all c_words to q_words
    matched_c2 = set()
    matched_q2 = set()
    has_fuzzy2 = False
    for c in c_words:
        if c in q_set and c not in matched_q2:
            matched_c2.add(c)
            matched_q2.add(c)
    for c in c_words:
        if c not in matched_c2:
            for q in q_words:
                if q not in matched_q2 and is_fuzzy_word_pair(c, q):
                    matched_c2.add(c)
                    matched_q2.add(q)
                    has_fuzzy2 = True
                    break
    if has_fuzzy2 and matched_c2 == c_set:
        distinctive = [w for w in c_set if len(w) >= MIN_DISTINCTIVE_WORD_LEN and w not in effective_weak]
        if distinctive:
            return True, "core_name_fuzzy"

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
        "core_name_equal": 5,
        "core_name": 4,
        "core_name_forward": 4,
        "core_name_reverse": 4,
        "partial_name_person": 3,
        "core_name_fuzzy": 2,
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

    q_words_norm = normalize_name(query)
    c_words_matched = normalize_name(best_matched_name)
    weak_set = {w.lower() for w in WEAK_WORDS} | {w.lower() for w in COUNTRY_WORDS}
    q_distinctive = [w for w in q_words_norm if len(w) >= MIN_DISTINCTIVE_WORD_LEN and w not in weak_set]
    c_distinctive = [w for w in c_words_matched if len(w) >= MIN_DISTINCTIVE_WORD_LEN and w not in weak_set]

    # T1.7.1: A reverse core-name match against a listed name of one word must be 🟠, never 🔴
    # When query has other distinctive words outside the 1-word matched core
    is_single_word_reverse_partial = (
        best_match_type == "core_name_reverse"
        and len(c_distinctive) <= 1
        and set(q_distinctive) != set(c_distinctive)
    )

    # Determine Tier and Reason
    tier = TIER_NO_MATCH
    reason = "none"

    if best_match_type == "core_name_fuzzy":
        # T1.6.5: A pass that relies on a fuzzy word gives 🟠 with reason core_name_fuzzy, NEVER 🔴
        tier = TIER_POSSIBLE_MATCH
        reason = "core_name_fuzzy"
    elif is_person:
        # Rule 5: Person Rule
        # T1.7.4: Person searches: candidates below 0.60 are shown as ℹ️ and can never become 🟠 or 🔴
        if score < 0.60:
            tier = TIER_BELOW_THRESHOLD
            reason = "below_threshold"
        elif best_match_type == "partial_name_person":
            tier = TIER_POSSIBLE_MATCH
            reason = "partial_name_person"
        elif score >= POTENTIAL_MATCH_THRESHOLD:
            tier = TIER_POTENTIAL_MATCH
            reason = (
                "score_and_core_name" if best_match_type == "core_name_equal" else "score"
            )
        elif best_match_type == "core_name_equal":
            tier = TIER_POTENTIAL_MATCH
            reason = "core_name"
        elif score >= POSSIBLE_MATCH_THRESHOLD:
            tier = TIER_POSSIBLE_MATCH
            reason = "score"
        else:
            tier = TIER_BELOW_THRESHOLD
            reason = "below_threshold"

        # Secondary identifier conflict check
        if tier == TIER_POTENTIAL_MATCH:
            if check_secondary_identifier_conflict(entity, dob=dob, yob=yob, nationality=nationality):
                tier = TIER_POSSIBLE_MATCH
                reason = "secondary_identifier_conflict"

    else:
        # Organisation / Entity Rule
        # T1.7.1: A reverse core-name match against a listed name of one word must be 🟠, never 🔴
        if best_match_type == "core_name_reverse" and is_single_word_reverse_partial:
            tier = TIER_POSSIBLE_MATCH
            reason = "core_name_reverse"
        elif score >= POTENTIAL_MATCH_THRESHOLD and best_match_type == "core_name_reverse":
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
        else:
            tier = TIER_BELOW_THRESHOLD
            reason = "below_threshold"

    # T1.7.1: For Airline and Organisation searches, a candidate whose entity type is
    # Vessel, Aircraft or Person must be 🟠 at most, with reason type_mismatch.
    is_airline_or_org = (
        query_type is not None
        and query_type.lower() in ["airline", "organisation", "organization"]
    )
    ent_type_raw = str(
        entity.get("entityType")
        or entity.get("type")
        or (entity.get("sourceData") or {}).get("sdnType")
        or ""
    ).lower()

    source_list = entity.get("sourceList", "")
    sd = entity.get("sourceData") or {}
    if not isinstance(sd, dict):
        sd = {}

    # Check raw words in primary name and aliases for corporate keywords before normalization stripped them
    all_raw_text = (primary_name + " " + " ".join(all_aliases)).lower()
    raw_name_tokens = set(re.findall(r"\b[A-Za-z0-9]+\b", all_raw_text))
    company_words_set = {w.lower() for w in COMPANY_TYPE_WORDS} | {w.lower() for w in WEAK_WORDS}
    has_company_words = bool(raw_name_tokens & company_words_set)

    is_truly_vessel = (
        ent_type_raw == "vessel"
        or entity.get("vessel") is not None
        or sd.get("sdnType") == "vessel"
    )
    is_truly_aircraft = (
        ent_type_raw == "aircraft"
        or entity.get("aircraft") is not None
        or sd.get("sdnType") == "aircraft"
    )

    is_truly_person = False
    if not has_company_words:
        if source_list == "us_ofac":
            is_truly_person = (sd.get("sdnType") == "individual" or ent_type_raw in ["person", "individual"])
        elif source_list == "us_csl":
            csl_src = str(sd.get("Source", ""))
            is_truly_person = ("Entity List" not in csl_src and ent_type_raw in ["person", "individual"])
        else:
            is_truly_person = (ent_type_raw in ["person", "individual"])

    is_mismatched_type = is_truly_vessel or is_truly_aircraft or is_truly_person

    if is_airline_or_org and is_mismatched_type:
        if tier in [TIER_POTENTIAL_MATCH, TIER_POSSIBLE_MATCH]:
            tier = TIER_POSSIBLE_MATCH
            reason = "type_mismatch"

    tier_icon = (
        "🔴" if tier == TIER_POTENTIAL_MATCH
        else ("🟠" if tier == TIER_POSSIBLE_MATCH
        else ("ℹ️" if tier == TIER_BELOW_THRESHOLD
        else ("✅" if tier == TIER_NO_MATCH else "⚪")))
    )

    label = None
    if tier == TIER_BELOW_THRESHOLD:
        label = "Shown for information — below match threshold"

    score_source = "token_pass" if score < 0.60 else entity.get("score_source", "query")

    return {
        "tier": tier,
        "tier_icon": tier_icon,
        "label": label,
        "reason": reason,
        "score": score,
        "watchman_raw_score": score,
        "tier_reason": reason,
        "score_source": score_source,
        "primary_name": primary_name,
        "matched_name": best_matched_name,
        "entity_type": "person" if is_person else (entity.get("entityType") or "organisation"),
        "program": extract_program_info(entity),
        "source_list": entity.get("sourceList", ""),
        "source_id": entity.get("sourceID", ""),
        "core_pass": core_pass or (best_match_type == "partial_name_person"),
        "entity": entity,
    }


AIRLINE_ALIASES_CSV = Path(__file__).resolve().parent.parent.parent / "data" / "aviation" / "airline_aliases.csv"


def get_airline_alias_row(query: str) -> Optional[Dict[str, Any]]:
    """Check if query matches any row in airline_aliases.csv by alias, canonical name, ICAO, or IATA."""
    if not AIRLINE_ALIASES_CSV.is_file():
        return None
    q_norm = " ".join(normalize_name(query))
    q_upper = query.strip().upper()
    try:
        with open(AIRLINE_ALIASES_CSV, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                canonical = row.get("canonical airline", "").strip()
                aliases = [a.strip() for a in row.get("aliases", "").split(";") if a.strip()]
                icao = row.get("ICAO", "").strip().upper()
                iata = row.get("IATA", "").strip().upper()

                matched = False
                if q_upper == icao or q_upper == iata:
                    matched = True
                elif " ".join(normalize_name(canonical)) == q_norm:
                    matched = True
                else:
                    for a in aliases:
                        if " ".join(normalize_name(a)) == q_norm:
                            matched = True
                            break
                if matched:
                    all_aliases = []
                    for name in [canonical] + aliases:
                        if name and name not in all_aliases:
                            all_aliases.append(name)
                    return {
                        "canonical": canonical,
                        "aliases": all_aliases,
                        "icao": icao,
                        "iata": iata,
                    }
    except Exception:
        pass
    return None


def _screen_direct_all_lists(
    query: str,
    client: WatchmanClient,
    query_type: Optional[str] = None,
    dob: Optional[str] = None,
    yob: Optional[str] = None,
    nationality: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Screen a query directly against all 5 lists."""
    results_by_source: Dict[str, Dict[str, Any]] = {}

    tier_order = {
        TIER_POTENTIAL_MATCH: 3,
        TIER_POSSIBLE_MATCH: 2,
        TIER_NO_MATCH: 1,
        TIER_NOT_CHECKED: 0,
    }

    is_person_search = (query_type and query_type.lower() == "person")

    for src in SOURCE_LISTS:
        # Candidate retrieval: DISPLAY_MIN_MATCH (0.50) for persons, 0.45 for organisations/airlines
        retrieval_min_match = DISPLAY_MIN_MATCH if is_person_search else min(DISPLAY_MIN_MATCH, 0.45)
        retrieval_limit = 50
        resp = client.search(
            name=query, min_match=retrieval_min_match, source=src, limit=retrieval_limit
        )

        raw_entities = resp.get("results", {}).get("entities") or []
        entity_map = {e.get("sourceID"): e for e in raw_entities if e.get("sourceID")}

        # Extra retrieval pass: Query distinctive words (>= 4 chars, non-weak)
        # T1.6.3: Run token pass ONLY for Organisation and Airline searches, NEVER for Person searches
        if not is_person_search and query_type and query_type.lower() in ["organisation", "organization", "airline"]:
            q_tokens = normalize_name(query)
            weak_set = {w.lower() for w in WEAK_WORDS}
            country_set = {w.lower() for w in COUNTRY_WORDS}
            effective_weak = weak_set | country_set
            distinctive_tokens = [w for w in q_tokens if w not in effective_weak and len(w) >= 4]

            for token in distinctive_tokens:
                extra_resp = client.search(
                    name=token, min_match=0.45, source=src, limit=retrieval_limit
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
                "expanded_from": None,
                "error": resp.get("error"),
                "below_threshold_count": 0,
                "red_count": 0,
                "orange_count": 0,
                "limit_reached": False,
            }
            results_by_source[src] = {
                "best_hit": unavail_hit,
                "red_hits": [],
                "orange_hits": [],
                "info_hits": [],
                "all_candidates": [],
                "limit_reached": False,
            }
            continue

        red_hits: List[Dict[str, Any]] = []
        orange_hits: List[Dict[str, Any]] = []
        info_hits: List[Dict[str, Any]] = []

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
                # Any hit below 0.60 must carry score_source: token_pass (T1.6.3 / T1.7.2)
                if tiered["score"] < 0.60:
                    tiered["score_source"] = "token_pass"
                tiered["expanded_from"] = None

                if tiered["tier"] == TIER_POTENTIAL_MATCH:
                    red_hits.append(tiered)
                elif tiered["tier"] == TIER_POSSIBLE_MATCH:
                    orange_hits.append(tiered)
                else:
                    info_hits.append(tiered)

        red_hits.sort(key=lambda x: x["score"], reverse=True)
        orange_hits.sort(key=lambda x: x["score"], reverse=True)
        info_hits.sort(key=lambda x: x["score"], reverse=True)

        all_candidates = red_hits + orange_hits + info_hits
        limit_reached = len(all_candidates) >= DISPLAY_LIMIT
        display_candidates = all_candidates[:DISPLAY_LIMIT]
        display_info = [c for c in display_candidates if c["tier"] == TIER_BELOW_THRESHOLD]
        display_red = [c for c in display_candidates if c["tier"] == TIER_POTENTIAL_MATCH]
        display_orange = [c for c in display_candidates if c["tier"] == TIER_POSSIBLE_MATCH]

        if display_red:
            best_hit = dict(display_red[0])
        elif display_orange:
            best_hit = dict(display_orange[0])
        else:
            best_hit = {
                "tier": TIER_NO_MATCH,
                "tier_icon": "✅",
                "reason": "none",
                "score": 0.0,
                "watchman_raw_score": 0.0,
                "tier_reason": "none",
                "score_source": "query",
                "primary_name": "—",
                "matched_name": "—",
                "entity_type": query_type or "organisation",
                "program": "—",
                "source_list": src,
                "source_id": "—",
                "expanded_from": None,
            }

        best_hit["below_threshold_count"] = len(display_info)
        best_hit["red_count"] = len(display_red)
        best_hit["orange_count"] = len(display_orange)
        best_hit["limit_reached"] = limit_reached
        if best_hit["tier"] == TIER_NO_MATCH and len(display_info) > 0:
            best_hit["note"] = f"({len(display_info)} candidates below threshold — see list)"

        results_by_source[src] = {
            "best_hit": best_hit,
            "red_hits": display_red,
            "orange_hits": display_orange,
            "info_hits": display_info,
            "all_candidates": display_candidates,
            "limit_reached": limit_reached,
        }

    return results_by_source


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
    If query matches airline_aliases.csv, expands across canonical name and all aliases.
    Returns for each list:
      - 'best_hit': Dict with top hit metadata (including 'expanded_from')
      - 'red_hits': All POTENTIAL_MATCH (🔴) hits
      - 'orange_hits': Top 3 POSSIBLE_MATCH_REVIEW (🟠) hits
      - 'info_hits': All BELOW_THRESHOLD (ℹ️) hits
      - 'all_candidates': All candidates sorted by tier then score
      - 'limit_reached': bool indicating if DISPLAY_LIMIT was reached
    """
    if client is None:
        client = WatchmanClient()

    if not query or not query.strip():
        results_by_source: Dict[str, Dict[str, Any]] = {}
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
                "expanded_from": None,
                "below_threshold_count": 0,
                "red_count": 0,
                "orange_count": 0,
                "limit_reached": False,
            }
            results_by_source[src] = {
                "best_hit": empty_hit,
                "red_hits": [],
                "orange_hits": [],
                "info_hits": [],
                "all_candidates": [],
                "limit_reached": False,
            }
        return results_by_source

    direct_results = _screen_direct_all_lists(
        query=query,
        client=client,
        query_type=query_type,
        dob=dob,
        yob=yob,
        nationality=nationality,
    )

    # T1.6.2: Query expansion through the airline alias table
    is_airline_or_org = (
        query_type is None
        or query_type.lower() in ["airline", "organisation", "organization"]
    )
    expansion_row = get_airline_alias_row(query) if is_airline_or_org else None

    if expansion_row:
        all_expanded_aliases = expansion_row.get("aliases", [])
        for exp_alias in all_expanded_aliases:
            if exp_alias.strip().lower() == query.strip().lower():
                continue
            exp_res = _screen_direct_all_lists(
                query=exp_alias,
                client=client,
                query_type="airline",
                dob=dob,
                yob=yob,
                nationality=nationality,
            )
            for src in SOURCE_LISTS:
                cur_best = direct_results[src]["best_hit"]
                exp_best = exp_res[src]["best_hit"]

                if exp_best["tier"] == TIER_POTENTIAL_MATCH:
                    if cur_best["tier"] != TIER_POTENTIAL_MATCH or (cur_best.get("expanded_from") and exp_best["score"] > cur_best["score"]):
                        exp_best_copy = dict(exp_best)
                        exp_best_copy["expanded_from"] = exp_alias
                        direct_results[src]["best_hit"] = exp_best_copy
                        if exp_best_copy not in direct_results[src]["red_hits"]:
                            direct_results[src]["red_hits"].insert(0, exp_best_copy)
                elif exp_best["tier"] == TIER_POSSIBLE_MATCH and cur_best["tier"] == TIER_NO_MATCH:
                    exp_best_copy = dict(exp_best)
                    exp_best_copy["expanded_from"] = exp_alias
                    direct_results[src]["best_hit"] = exp_best_copy
                    direct_results[src]["orange_hits"].append(exp_best_copy)

                # Merge expanded candidates into all_candidates and info_hits if not present
                existing_sids = {c.get("source_id") for c in direct_results[src]["all_candidates"]}
                for cand in exp_res[src].get("all_candidates", []):
                    sid = cand.get("source_id")
                    if sid and sid not in existing_sids:
                        cand_copy = dict(cand)
                        cand_copy["expanded_from"] = exp_alias
                        direct_results[src]["all_candidates"].append(cand_copy)
                        existing_sids.add(sid)
                        if cand_copy.get("tier") == TIER_BELOW_THRESHOLD:
                            direct_results[src]["info_hits"].append(cand_copy)
                        elif cand_copy.get("tier") == TIER_POSSIBLE_MATCH and cand_copy not in direct_results[src]["orange_hits"]:
                            direct_results[src]["orange_hits"].append(cand_copy)
                        elif cand_copy.get("tier") == TIER_POTENTIAL_MATCH and cand_copy not in direct_results[src]["red_hits"]:
                            direct_results[src]["red_hits"].append(cand_copy)

                # Refresh counts on best_hit
                direct_results[src]["best_hit"]["below_threshold_count"] = len(direct_results[src]["info_hits"])
                direct_results[src]["best_hit"]["red_count"] = len(direct_results[src]["red_hits"])
                direct_results[src]["best_hit"]["orange_count"] = len(direct_results[src]["orange_hits"])
                if direct_results[src]["best_hit"]["tier"] == TIER_NO_MATCH and len(direct_results[src]["info_hits"]) > 0:
                    direct_results[src]["best_hit"]["note"] = f"({len(direct_results[src]['info_hits'])} candidates below threshold — see list)"

    return direct_results



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
