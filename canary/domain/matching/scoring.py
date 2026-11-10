"""
Pure domain scoring algorithms: string similarity, token overlap, core name matching.
Zero I/O.
"""
import difflib
from functools import lru_cache
from typing import List, Tuple, Set, Optional

from canary.domain.matching.normalizer import (
    DEFAULT_WEAK_WORDS,
    DEFAULT_COUNTRY_WORDS,
)

FUZZY_WORD_MIN_LEN = 5
FUZZY_WORD_MIN_SIMILARITY = 0.90
MIN_DISTINCTIVE_WORD_LEN = 4


@lru_cache(maxsize=32768)
def is_fuzzy_word_pair(w1: str, w2: str) -> bool:
    """Check if two words are a fuzzy match (>= 5 chars each and >= 90% similarity)."""
    if len(w1) < FUZZY_WORD_MIN_LEN or len(w2) < FUZZY_WORD_MIN_LEN:
        return False
    if w1 + "n" == w2 or w2 + "n" == w1:
        return False
    return difflib.SequenceMatcher(None, w1, w2).ratio() >= FUZZY_WORD_MIN_SIMILARITY


def string_similarity(s1: str, s2: str) -> float:
    """Calculate SequenceMatcher similarity ratio between two strings."""
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0
    return difflib.SequenceMatcher(None, s1, s2).ratio()


def check_core_name_match(
    q_words: List[str],
    c_words: List[str],
    is_person: bool = False,
    weak_words: Optional[List[str]] = None,
    country_words: Optional[List[str]] = None,
) -> Tuple[bool, str]:
    """
    Check core-name equivalence between query tokens and candidate tokens.
    Returns (is_match, match_type).
    """
    if not q_words or not c_words:
        return False, ""

    q_set = set(q_words)
    c_set = set(c_words)
    weak_set = {w.lower() for w in (weak_words or DEFAULT_WEAK_WORDS)}
    country_set = {w.lower() for w in (country_words or DEFAULT_COUNTRY_WORDS)}
    effective_weak = weak_set | country_set

    shared = q_set & c_set
    shared_has_distinctive = bool(shared and not shared.issubset(effective_weak))

    # Exact equality (ignoring order)
    if q_set == c_set:
        if shared_has_distinctive:
            return True, "core_name_equal"

    # Forward subset check: q_set is subset of c_set
    if q_set.issubset(c_set) and shared_has_distinctive:
        if is_person:
            return True, "partial_name_person"
        else:
            extra_cand_words = c_set - q_set
            if extra_cand_words.issubset(effective_weak):
                return True, "core_name"

    # Reverse subset check: c_set is subset of q_set
    if c_set.issubset(q_set):
        distinctive_candidate_words = [
            w for w in c_set if len(w) >= MIN_DISTINCTIVE_WORD_LEN and w not in effective_weak
        ]
        if distinctive_candidate_words:
            if is_person:
                return True, "partial_name_person"
            else:
                return True, "core_name_reverse"

    # Forward fuzzy
    matched_c: Set[str] = set()
    matched_q: Set[str] = set()
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

    # Reverse fuzzy
    matched_c2: Set[str] = set()
    matched_q2: Set[str] = set()
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
