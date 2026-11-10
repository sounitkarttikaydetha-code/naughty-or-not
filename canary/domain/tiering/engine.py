"""
Pure Domain Tiering Engine.
Evaluates entity matches into standard tiers (🔴 POTENTIAL_MATCH, 🟠 POSSIBLE_MATCH_REVIEW, ℹ️ BELOW_THRESHOLD, ✅ NO_MATCH).
Zero I/O.
"""
import re
from typing import Any, Dict, List, Optional, Tuple, Set

from canary.domain.models import Tier, MatchHit, TIER_ICONS
from canary.domain.matching.normalizer import (
    normalize_tokens,
    split_alias_text,
    DEFAULT_WEAK_WORDS,
    DEFAULT_COUNTRY_WORDS,
    DEFAULT_COMPANY_TYPE_WORDS,
)
from canary.domain.matching.scoring import (
    check_core_name_match,
    MIN_DISTINCTIVE_WORD_LEN,
)
from canary.domain.matching.phonetic import get_tokens_phonetic_codes
from canary.domain.tiering.rules import (
    DEFAULT_THRESHOLDS,
    TieringThresholds,
)


def extract_candidate_aliases(entity: Dict[str, Any]) -> List[str]:
    """Extract and split all alias representations from candidate payload."""
    raw_names: List[str] = []
    pname = entity.get("name") or entity.get("primary_name") or ""
    if pname:
        raw_names.append(pname)

    # Aliases
    aliases = entity.get("aliases") or entity.get("altNames") or []
    for a in aliases:
        if a and a not in raw_names:
            raw_names.append(a)

    person = entity.get("person") or {}
    for a in person.get("altNames") or []:
        if a and a not in raw_names:
            raw_names.append(a)

    sd = entity.get("sourceData") or {}
    if isinstance(sd, dict):
        for field in ["Names", "nameAliasWholeNames"]:
            for a in sd.get(field) or []:
                if a and a not in raw_names:
                    raw_names.append(a)
        sdn_name = sd.get("sdnName")
        if sdn_name and sdn_name not in raw_names:
            raw_names.append(sdn_name)
        remarks = sd.get("remarks") or ""
        if remarks:
            aka_matches = re.findall(r"a\.k\.a\.\s*['\"]([^'\"]+)['\"]", remarks, re.IGNORECASE)
            for aka in aka_matches:
                if aka and aka not in raw_names:
                    raw_names.append(aka)

    expanded: List[str] = []
    for name in raw_names:
        parts = split_alias_text(name)
        for part in parts:
            if part and part not in expanded:
                expanded.append(part)

    return expanded if expanded else ([pname] if pname else [])


def evaluate_candidate_tier(
    query: str,
    entity: Dict[str, Any],
    query_type: Optional[str] = None,
    thresholds: Optional[TieringThresholds] = None,
    weak_words: Optional[List[str]] = None,
    country_words: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Tier a single candidate entity against the query using pure domain rules.
    Returns evaluated tier dictionary or None if discarded.
    """
    if not query or not query.strip():
        return None

    th = thresholds or DEFAULT_THRESHOLDS
    score = float(entity.get("match", entity.get("score", 0.0)))
    primary_name = entity.get("name") or entity.get("primary_name") or ""
    all_aliases = extract_candidate_aliases(entity)

    is_person = False
    if query_type:
        is_person = (query_type.lower() == "person")
    else:
        ent_type = str(entity.get("entityType") or entity.get("type") or "").lower()
        is_person = (ent_type == "person" or bool(entity.get("person")))

    q_words = normalize_tokens(query)

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
        c_words = normalize_tokens(candidate_alias)
        is_m, m_type = check_core_name_match(
            q_words, c_words, is_person=is_person,
            weak_words=weak_words, country_words=country_words
        )
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

    q_words_norm = normalize_tokens(query)
    c_words_matched = normalize_tokens(best_matched_name)
    ww = set(w.lower() for w in (weak_words or DEFAULT_WEAK_WORDS))
    cw = set(w.lower() for w in (country_words or DEFAULT_COUNTRY_WORDS))
    effective_weak = ww | cw

    q_distinctive = [w for w in q_words_norm if len(w) >= MIN_DISTINCTIVE_WORD_LEN and w not in effective_weak]
    c_distinctive = [w for w in c_words_matched if len(w) >= MIN_DISTINCTIVE_WORD_LEN and w not in effective_weak]

    is_single_word_reverse_partial = (
        best_match_type == "core_name_reverse"
        and len(c_distinctive) <= 1
        and set(q_distinctive) != set(c_distinctive)
    )

    tier = Tier.NO_MATCH.value
    reason = "none"

    if best_match_type == "core_name_fuzzy":
        tier = Tier.POSSIBLE_MATCH_REVIEW.value
        reason = "core_name_fuzzy"
    elif is_person:
        if score < 0.60:
            tier = Tier.BELOW_THRESHOLD.value
            reason = "below_threshold"
        elif best_match_type == "partial_name_person":
            tier = Tier.POSSIBLE_MATCH_REVIEW.value
            reason = "partial_name_person"
        elif score >= th.potential_match_threshold:
            tier = Tier.POTENTIAL_MATCH.value
            reason = "score_and_core_name" if best_match_type == "core_name_equal" else "score"
        elif best_match_type == "core_name_equal":
            tier = Tier.POTENTIAL_MATCH.value
            reason = "core_name"
        elif score >= th.possible_match_threshold:
            tier = Tier.POSSIBLE_MATCH_REVIEW.value
            reason = "score"
        else:
            tier = Tier.BELOW_THRESHOLD.value
            reason = "below_threshold"
    else:
        # Organisation / Entity Rule
        if best_match_type == "core_name_reverse" and is_single_word_reverse_partial:
            tier = Tier.POSSIBLE_MATCH_REVIEW.value
            reason = "core_name_reverse"
        elif score >= th.potential_match_threshold and best_match_type == "core_name_reverse":
            tier = Tier.POTENTIAL_MATCH.value
            reason = "score_and_core_name_reverse"
        elif best_match_type == "core_name_reverse":
            tier = Tier.POTENTIAL_MATCH.value
            reason = "core_name_reverse"
        elif score >= th.potential_match_threshold and core_pass:
            tier = Tier.POTENTIAL_MATCH.value
            reason = "score_and_core_name"
        elif core_pass:
            tier = Tier.POTENTIAL_MATCH.value
            reason = "core_name"
        elif score >= th.potential_match_threshold:
            tier = Tier.POTENTIAL_MATCH.value
            reason = "score"
        elif score >= th.possible_match_threshold:
            tier = Tier.POSSIBLE_MATCH_REVIEW.value
            reason = "score"
        else:
            tier = Tier.BELOW_THRESHOLD.value
            reason = "below_threshold"

    # Discard candidate below threshold if no core pass and score < 0.70
    if not core_pass and best_match_type != "core_name_fuzzy" and score < th.possible_match_threshold:
        return None

    # Phonetic codes for matched name
    matched_phonetics = get_tokens_phonetic_codes(c_words_matched)

    return {
        "tier": tier,
        "tier_icon": TIER_ICONS.get(Tier(tier), "✅"),
        "score": score,
        "reason": reason,
        "primary_name": primary_name,
        "matched_name": best_matched_name,
        "source_id": str(entity.get("sourceID") or entity.get("source_id") or entity.get("id") or "—"),
        "expanded_from": entity.get("expanded_from"),
        "matched_phonetic_codes": matched_phonetics,
    }
