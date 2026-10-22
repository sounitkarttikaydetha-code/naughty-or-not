"""
Plain-English reason translations for Naughty or not.
Translates internal engine reason codes into non-technical language.
"""

from typing import Optional

PLAIN_REASONS = {
    "core_name": "Same name once 'Ltd/PJSC' etc. are ignored",
    "core_name_fuzzy": "Same name with minor spelling variation once company terms are ignored",
    "core_name_reverse": "Same name once 'Ltd/PJSC' etc. are ignored (reverse match)",
    "score_and_core_name": "High similarity score and matching core business name",
    "score_and_core_name_reverse": "High similarity score and matching core business name",
    "score": "High name similarity score",
    "type_mismatch": "Similar name, but this is a vessel/person, not an airline",
    "partial_name_person": "Part of the name matches — check date of birth / nationality",
    "below_threshold": "Low similarity score — below match review threshold",
    "secondary_identifier_conflict": "Different country, city or identifier",
    "phonetic_match": "Sounds like a listed name (different spelling). Check carefully.",
    "phonetic_name_person": "Name sounds similar. Check date of birth and nationality.",
    "phonetic_weak": "Shown for information.",
    "alias_ambiguous": "Matched via common or short alias — review required",
    "mha_core_match": "Direct match on Indian MHA designated schedule",
    "mha_partial": "Partial match on Indian MHA designated schedule",
    "opensanctions_score": "High similarity match from OpenSanctions database",
    "none": "No matching records found",
    "watchman_unavailable": "Sanctions list engine was unavailable",
    "service_unavailable": "Service unavailable",
}


def translate_reason(code: Optional[str]) -> str:
    """Return a plain-English explanation for an internal reason code."""
    if not code:
        return ""
    code_str = str(code).strip()
    return PLAIN_REASONS.get(code_str, code_str)
