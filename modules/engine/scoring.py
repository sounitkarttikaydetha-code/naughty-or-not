"""
Scoring Pipeline
Ported from moov-io/watchman (v1.2.2):
- internal/stringscore/jaro_winkler.go
- internal/stringscore/phonetics.go
- internal/stringscore/soundex.go
- pkg/search/similarity.go
- pkg/search/similarity_fuzzy.go
"""

from functools import lru_cache
from typing import List, Tuple
import rapidfuzz.distance.JaroWinkler as rjw

SOUNDEX_MAP = {
    "A": "A", "E": "A", "I": "A", "O": "A", "U": "A", "Y": "A",
    "B": "B", "F": "B", "P": "B", "V": "B",
    "C": "C", "G": "C", "J": "C", "K": "C", "Q": "C", "S": "C", "X": "C", "Z": "C",
    "D": "D", "T": "D",
    "L": "L",
    "M": "M", "N": "M",
    "R": "R",
    "H": "H", "W": "H",
}

SOUNDEX_MAP_LOWER = {k.lower(): v for k, v in SOUNDEX_MAP.items()}
SOUNDEX_MAP_LOWER.update(SOUNDEX_MAP)

# Watchman scoring constants (DefaultScoringConfig)
LENGTH_DIFFERENCE_CUTOFF_FACTOR = 0.90
LENGTH_DIFFERENCE_PENALTY_WEIGHT = 0.30
DIFFERENT_LETTER_PENALTY_WEIGHT = 0.90
UNMATCHED_INDEX_TOKEN_WEIGHT = 0.15

# Name search penalty blend: low_coverage (0.95) * min_required_fields (0.90) * name_only (0.95)
NAME_ONLY_PENALTY_MULTIPLIER = 0.81225


def get_phonetic_class(s: str) -> str:
    """Port of phonetics.go getPhoneticClass."""
    if not s:
        return " "
    first = s[0].upper()
    return SOUNDEX_MAP.get(first, first)


def first_char_soundex_match(s1: str, s2: str) -> bool:
    """Port of phonetics.go firstCharacterSoundexMatch."""
    if not s1 or not s2:
        return False
    return get_phonetic_class(s1) == get_phonetic_class(s2)


@lru_cache(maxsize=32768)
def _generate_word_combinations_cached(tokens_tuple: Tuple[str, ...]) -> Tuple[Tuple[str, ...], ...]:
    """Internal cached generator for word combinations."""
    tokens = list(tokens_tuple)
    if len(tokens) <= 1:
        return (tokens_tuple,)

    result = [tokens_tuple]

    # Forward combination (short word + next word)
    forward: List[str] = []
    skip = False
    for i in range(len(tokens)):
        if skip:
            skip = False
            continue
        if i < len(tokens) - 1 and len(tokens[i]) <= 3:
            forward.append(tokens[i] + tokens[i + 1])
            skip = True
        else:
            forward.append(tokens[i])

    if len(forward) < len(tokens):
        f_tup = tuple(forward)
        result.append(f_tup)

        # Backward combination (combine short word with previous word)
        backward: List[str] = []
        for i in range(len(tokens)):
            if i > 0 and len(tokens[i]) <= 3 and len(backward) > 0:
                backward[-1] = backward[-1] + tokens[i]
            else:
                backward.append(tokens[i])

        b_tup = tuple(backward)
        if len(backward) < len(tokens) and b_tup != f_tup and b_tup != tokens_tuple:
            result.append(b_tup)

    return tuple(result)


def generate_word_combinations(tokens: List[str]) -> List[List[str]]:
    """
    Port of jaro_winkler.go GenerateWordCombinations.
    Generates variations by combining short words (<= 3 chars) with neighbors.
    """
    cached = _generate_word_combinations_cached(tuple(tokens))
    return [list(c) for c in cached]


@lru_cache(maxsize=65536)
def _token_similarity_cached(s: str, t: str) -> float:
    """Cached rapidfuzz Jaro-Winkler score with length penalty."""
    score = rjw.similarity(t, s, prefix_weight=0.1)
    ls, lt = len(s), len(t)
    ld = min(ls, lt) / max(ls, lt) if max(ls, lt) > 0 else 1.0
    if ld < LENGTH_DIFFERENCE_CUTOFF_FACTOR:
        score *= (1.0 - (1.0 - ld) * LENGTH_DIFFERENCE_PENALTY_WEIGHT)
    return score


def best_pairs_jaro_winkler(search_tokens: Tuple[str, ...], index_tokens: Tuple[str, ...]) -> float:
    """
    Port of jaro_winkler.go BestPairsJaroWinklerWithConfig.
    Evaluates pairwise token similarities and combines them via length-weighted average
    and unmatched indexed token penalties.
    """
    # Fast path for single search token (all distinctive word passes & single-word queries)
    if len(search_tokens) == 1:
        s = search_tokens[0]
        if not s:
            return 0.0
        s_cls = SOUNDEX_MAP_LOWER.get(s[0], s[0])
        best_score = 0.0
        best_len = 0
        total_idx_len = 0
        for t in index_tokens:
            total_idx_len += len(t)
            if t and s_cls == SOUNDEX_MAP_LOWER.get(t[0], t[0]):
                sc = _token_similarity_cached(s, t)
                if sc > best_score:
                    best_score = sc
                    best_len = len(t)
        if best_score == 0.0 or total_idx_len == 0:
            return 0.0
        scaling = 1.0 - (1.0 - (best_len / total_idx_len)) * UNMATCHED_INDEX_TOKEN_WEIGHT
        return best_score * scaling

    scores: List[Tuple[float, int, int]] = []
    s_lens = [len(x) for x in search_tokens]
    i_lens = [len(x) for x in index_tokens]
    s_classes = [SOUNDEX_MAP_LOWER.get(s[0], s[0]) if s else " " for s in search_tokens]
    i_classes = [SOUNDEX_MAP_LOWER.get(t[0], t[0]) if t else " " for t in index_tokens]

    for s_idx, s in enumerate(search_tokens):
        s_cls = s_classes[s_idx]
        for i_idx, t in enumerate(index_tokens):
            if s_cls == i_classes[i_idx]:
                score = _token_similarity_cached(s, t)
                scores.append((score, s_idx, i_idx))

    scores.sort(key=lambda x: x[0], reverse=True)

    matched_search = set()
    matched_index = set()
    total_weighted_scores = 0.0
    matched_index_tokens_len = 0

    for score, s_idx, i_idx in scores:
        if s_idx not in matched_search and i_idx not in matched_index:
            matched_search.add(s_idx)
            matched_index.add(i_idx)
            total_weighted_scores += score * (s_lens[s_idx] + i_lens[i_idx])
            matched_index_tokens_len += i_lens[i_idx]

    search_tokens_len = sum(s_lens)
    index_tokens_len = sum(i_lens)

    if (search_tokens_len + matched_index_tokens_len) > 0:
        length_weighted_avg = total_weighted_scores / (search_tokens_len + matched_index_tokens_len)
    else:
        length_weighted_avg = 0.0

    if index_tokens_len > 0:
        matched_frac = matched_index_tokens_len / index_tokens_len
    else:
        matched_frac = 0.0

    # Scale by fraction of indexed term matched
    scaling_factor = 1.0 - (1.0 - matched_frac) * UNMATCHED_INDEX_TOKEN_WEIGHT
    return length_weighted_avg * scaling_factor


def best_pair_combination_jaro_winkler(search_tokens: List[str], index_tokens: List[str]) -> float:
    """
    Port of jaro_winkler.go BestPairCombinationJaroWinklerWithConfig.
    Evaluates variations across word combinations and returns maximum match score.
    """
    s_combs = _generate_word_combinations_cached(tuple(search_tokens))
    i_combs = _generate_word_combinations_cached(tuple(index_tokens))

    max_score = 0.0
    for sc in s_combs:
        for ic in i_combs:
            score = best_pairs_jaro_winkler(sc, ic)
            if score > max_score:
                max_score = score
    return max_score


def is_name_close_enough(
    query_name: str,
    index_name: str,
    q_tokens: List[str],
    i_tokens: List[str],
) -> bool:
    """
    Port of similarity_fuzzy.go isNameCloseEnough.
    Term counts are calculated from the prepared name strings (number of spaces + 1).
    Term containment is checked between query and indexed token lists.
    """
    if not query_name or not index_name:
        return False

    q_term_count = query_name.count(" ") + 1
    i_term_count = index_name.count(" ") + 1

    ratio = q_term_count / i_term_count
    if ratio < 0.3 or ratio > 3.0:
        return False

    match_count = 0
    for q in q_tokens:
        for it in i_tokens:
            if it in q or q in it:
                match_count += 1
                break

    return (match_count / q_term_count) >= 0.4


def score_query_against_entity_names(
    query_tokens: List[str],
    primary_tokens: List[str],
    alt_names_tokens: List[List[str]],
    historical_tokens: List[List[str]] = None,
    query_name: str = "",
    primary_name: str = "",
) -> float:
    """
    Port of similarity_fuzzy.go compareNameWithTFIDF and calculateFinalScore.
    Computes best name match across primary, alternate, and historical names,
    applies quality and coverage adjustments, and multiplies by final name-only penalty.
    """
    if not query_tokens or not primary_tokens:
        return 0.0

    # Primary name
    best_match = best_pair_combination_jaro_winkler(query_tokens, primary_tokens)
    best_tokens = primary_tokens

    # Alternate names (if not already exact >= 0.99)
    if best_match < 0.99 and alt_names_tokens:
        for alt_tokens in alt_names_tokens:
            if not alt_tokens:
                continue
            cand = best_pair_combination_jaro_winkler(query_tokens, alt_tokens)
            if cand > best_match:
                best_match = cand
                best_tokens = alt_tokens
                if best_match >= 0.99:
                    break

    # Historical names (penalized by 0.95 factor)
    if best_match < 0.99 and historical_tokens:
        for h_tokens in historical_tokens:
            if not h_tokens:
                continue
            cand = best_pair_combination_jaro_winkler(query_tokens, h_tokens) * 0.95
            if cand > best_match:
                best_match = cand
                best_tokens = h_tokens
                if best_match >= 0.99:
                    break

    # Adjust score based on quality: require >= 2 matching terms for multi-term query
    # Port of similarity_fuzzy.go adjustScoreBasedOnQuality
    if len(query_tokens) >= 2:
        matching_terms = len(query_tokens) if best_match > 0.90 else 0
        if matching_terms < 2:
            best_match *= 0.80

    # Close enough check on matched name
    qn = query_name or " ".join(query_tokens)
    matched_target_name = " ".join(best_tokens) if best_tokens != primary_tokens else (primary_name or " ".join(primary_tokens))
    if not is_name_close_enough(qn, matched_target_name, query_tokens, best_tokens):
        best_match *= 0.85

    # Final score with name-only coverage penalty
    return best_match * NAME_ONLY_PENALTY_MULTIPLIER
