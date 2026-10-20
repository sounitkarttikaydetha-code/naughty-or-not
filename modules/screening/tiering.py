"""
Match Tiering Layer
Performs candidate retrieval from Watchman (minMatch=0.65), entity normalization,
core-name equivalence checking, and multi-tier categorization.
"""

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from modules.screening.config import (
    CANDIDATE_MIN_MATCH,
    COMPANY_TYPE_WORDS,
    POTENTIAL_MATCH_THRESHOLD,
    REQUIRE_EXACT_CORE_MATCH,
)
from modules.watchman.client import WatchmanClient

# Tier Constants
TIER_POTENTIAL_MATCH = "POTENTIAL_MATCH"            # 🔴
TIER_POSSIBLE_MATCH = "POSSIBLE_MATCH_REVIEW"       # 🟠
TIER_NO_MATCH = "NO_MATCH"                          # ✅
TIER_NOT_CHECKED = "NOT_CHECKED"                    # ⚪

SOURCE_LISTS = ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]


def normalize_name(text: str) -> List[str]:
    """
    Normalise a name or alias string:
    - Lowercase
    - Fold accents / diacritics
    - Remove company-type phrases and words
    - Remove punctuation
    - Return list of core name tokens
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

    # 6. Remove single-word company-type words
    single_word_set = {
        w.lower() for w in COMPANY_TYPE_WORDS if " " not in w and "-" not in w
    }
    core_tokens = [w for w in tokens if w and w not in single_word_set]

    return core_tokens


def core_name_match(
    query: str,
    candidate_name: str,
    aliases: Optional[List[str]] = None,
    require_exact: Optional[bool] = None,
) -> Tuple[bool, str]:
    """
    Check if the core name of query matches candidate_name or any of its aliases.

    :param query: Input search query string
    :param candidate_name: Primary name of the candidate entity
    :param aliases: Optional list of alternate names / aliases
    :param require_exact: If True, core words must match exactly (set equality).
                          If False, all query words must be present in candidate words (subset).
    :return: (is_match, matched_name_or_alias)
    """
    if require_exact is None:
        require_exact = REQUIRE_EXACT_CORE_MATCH

    q_words = normalize_name(query)
    if not q_words:
        return False, candidate_name

    q_set = set(q_words)

    # Check primary name first
    names_to_check = [candidate_name]
    if aliases:
        names_to_check.extend(aliases)

    for target in names_to_check:
        if not target:
            continue
        c_words = normalize_name(target)
        if not c_words:
            continue
        c_set = set(c_words)

        if require_exact:
            # Exact core name equality: all query tokens equal all candidate tokens
            if q_set == c_set:
                return True, target
        else:
            # Subset mode: every remaining query word is present in remaining candidate words
            if q_set.issubset(c_set):
                return True, target

    return False, candidate_name


def extract_aliases(entity: Dict[str, Any]) -> List[str]:
    """Extract all available aliases from a Watchman entity payload."""
    aliases = []
    # Business altNames
    bus = entity.get("business") or {}
    for a in bus.get("altNames") or []:
        if a and a not in aliases:
            aliases.append(a)

    # Person altNames
    person = entity.get("person") or {}
    for a in person.get("altNames") or []:
        if a and a not in aliases:
            aliases.append(a)

    # Source data whole names (e.g. EU CSL)
    sd = entity.get("sourceData") or {}
    if isinstance(sd, dict):
        for a in sd.get("nameAliasWholeNames") or []:
            if a and a not in aliases:
                aliases.append(a)

    return aliases


def tier_entity(
    query: str,
    entity: Dict[str, Any],
    require_exact: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Assign a tier and evaluation metadata to a single entity candidate.
    """
    score = float(entity.get("match", 0.0))
    primary_name = entity.get("name", "")
    aliases = extract_aliases(entity)

    is_core_match, matched_name = core_name_match(
        query, primary_name, aliases, require_exact=require_exact
    )

    # Determine tier and reason
    if score >= POTENTIAL_MATCH_THRESHOLD and is_core_match:
        tier = TIER_POTENTIAL_MATCH
        reason = "score_and_core_name"
    elif score >= POTENTIAL_MATCH_THRESHOLD:
        tier = TIER_POTENTIAL_MATCH
        reason = "score"
    elif is_core_match:
        tier = TIER_POTENTIAL_MATCH
        reason = "core_name"
    elif score >= CANDIDATE_MIN_MATCH:
        tier = TIER_POSSIBLE_MATCH
        reason = "score"
    else:
        tier = TIER_NO_MATCH
        reason = "none"

    return {
        "tier": tier,
        "reason": reason,
        "score": score,
        "primary_name": primary_name,
        "matched_name": matched_name,
        "source_list": entity.get("sourceList", ""),
        "source_id": entity.get("sourceID", ""),
        "entity": entity,
    }


def screen_query_per_list(
    query: str,
    client: Optional[WatchmanClient] = None,
    require_exact: Optional[bool] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Screen a query against Watchman and return the best hit per source list.

    :param query: Name to screen
    :param client: Optional WatchmanClient instance
    :param require_exact: Optional override for exact core match
    :return: Dict mapping source_list -> best_hit_dict
    """
    if client is None:
        client = WatchmanClient()

    results_by_source: Dict[str, Dict[str, Any]] = {}

    if not query or not query.strip():
        for src in SOURCE_LISTS:
            results_by_source[src] = {
                "tier": TIER_NO_MATCH,
                "reason": "none",
                "score": 0.0,
                "primary_name": "—",
                "matched_name": "—",
                "source_list": src,
                "source_id": "—",
            }
        return results_by_source

    tier_order = {
        TIER_POTENTIAL_MATCH: 3,
        TIER_POSSIBLE_MATCH: 2,
        TIER_NO_MATCH: 1,
        TIER_NOT_CHECKED: 0,
    }

    for src in SOURCE_LISTS:
        resp = client.search(
            name=query, min_match=CANDIDATE_MIN_MATCH, source=src
        )

        if resp.get("status") == "unavailable":
            results_by_source[src] = {
                "tier": TIER_NOT_CHECKED,
                "reason": "watchman_unavailable",
                "score": 0.0,
                "primary_name": "—",
                "matched_name": "—",
                "source_list": src,
                "source_id": "—",
                "error": resp.get("error"),
            }
            continue

        raw_entities = resp.get("results", {}).get("entities") or []
        if not raw_entities:
            results_by_source[src] = {
                "tier": TIER_NO_MATCH,
                "reason": "none",
                "score": 0.0,
                "primary_name": "—",
                "matched_name": "—",
                "source_list": src,
                "source_id": "—",
            }
            continue

        # Evaluate each candidate and select the best hit
        evaluated_candidates = [
            tier_entity(query, ent, require_exact=require_exact)
            for ent in raw_entities
        ]

        # Sort by tier priority desc, then by score desc
        evaluated_candidates.sort(
            key=lambda x: (tier_order.get(x["tier"], 0), x["score"]),
            reverse=True,
        )

        best_hit = evaluated_candidates[0]
        results_by_source[src] = best_hit

    return results_by_source
