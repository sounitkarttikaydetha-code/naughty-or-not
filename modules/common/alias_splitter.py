"""
Alias Splitting and Bracket Handling Layer.
Shared between data loading and candidate tiering.
Splits names on d/b/a, a.k.a., f.k.a., formerly, and brackets.
Filters ignorable bracket text (countries, legal forms, cities, weak words).
"""

import re
import unicodedata
from typing import List

from modules.screening.config import (
    COMPANY_TYPE_WORDS,
    COUNTRY_WORDS,
    FUZZY_WORD_MIN_LEN,
    KNOWN_CITIES,
    NAME_VARIANTS,
    WEAK_WORDS,
)


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

    # 3. Remove multi-word company phrases first (normalize hyphens to spaces)
    s = s.replace("-", " ")
    multi_word_phrases = [
        w.lower().replace("-", " ") for w in COMPANY_TYPE_WORDS if " " in w or "-" in w
    ]
    for phrase in sorted(multi_word_phrases, key=len, reverse=True):
        pattern = r"\b" + re.escape(" ".join(phrase.split())) + r"\b"
        s = re.sub(pattern, " ", s)

    # 4. Remove punctuation & symbols
    s = re.sub(r"[^\w\s]", " ", s)

    # 5. Tokenize
    tokens = s.split()

    # 6. Remove single-word company-type words and apply transliteration name variants
    single_word_set = {
        w.lower() for w in COMPANY_TYPE_WORDS if " " not in w and "-" not in w
    }
    single_word_set.update({"joint", "stock", "commercial", "enterprise", "industrial"})
    core_tokens = [
        NAME_VARIANTS.get(w, w)
        for w in tokens
        if w and w not in single_word_set
    ]

    return core_tokens


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
    Split a name/alias string on brackets and d/b/a, a.k.a., f.k.a., formerly, etc.
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
