"""
Scoring Pipeline
Ported from moov-io/watchman (v1.2.2):
- internal/stringscore/jaro_winkler.go
- internal/stringscore/phonetics.go
- internal/stringscore/soundex.go
- pkg/search/similarity.go
- pkg/search/similarity_fuzzy.go
"""

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


def generate_word_combinations(tokens: List[str]) -> List[List[str]]:
    """
    Port of jaro_winkler.go GenerateWordCombinations.
    Generates variations by combining short words (<= 3 chars) with neighbors.
    """
    if len(tokens) <= 1:
        return [tokens]

    result = [tokens]

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
        result.append(forward)

        # Backward combination (combine short word with previous word)
        backward: List[str] = []
        for i in range(len(tokens)):
            if i > 0 and len(tokens[i]) <= 3 and len(backward) > 0:
                backward[-1] = backward[-1] + tokens[i]
            else:
                backward.append(tokens[i])

        if len(backward) < len(tokens) and backward != forward and backward != tokens:
            result.append(backward)

    return result


def best_pairs_jaro_winkler(search_tokens: List[str], index_tokens: List[str]) -> float:
    """
    Port of jaro_winkler.go BestPairsJaroWinklerWithConfig.
    Evaluates pairwise token similarities and combines them via length-weighted average
    and unmatched indexed token penalties.
    """
    scores: List[Tuple[float, int, int]] = []
    for s_idx, s in enumerate(search_tokens):
        for i_idx, t in enumerate(index_tokens):
            if first_char_soundex_match(s, t):
                # Token similarity using Jaro-Winkler
                score = rjw.similarity(t, s, prefix_weight=0.1)
                ls, lt = len(s), len(t)
                ld = min(ls, lt) / max(ls, lt) if max(ls, lt) > 0 else 1.0
                if ld < LENGTH_DIFFERENCE_CUTOFF_FACTOR:
                    score *= (1.0 - (1.0 - ld) * LENGTH_DIFFERENCE_PENALTY_WEIGHT)
                if not first_char_soundex_match(t, s):
                    score *= DIFFERENT_LETTER_PENALTY_WEIGHT
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
            total_weighted_scores += score * (len(search_tokens[s_idx]) + len(index_tokens[i_idx]))
            matched_index_tokens_len += len(index_tokens[i_idx])

    search_tokens_len = sum(len(x) for x in search_tokens)
    index_tokens_len = sum(len(x) for x in index_tokens)

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
    s_combs = generate_word_combinations(search_tokens)
    i_combs = generate_word_combinations(index_tokens)

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

    # Close enough check on primary name
    qn = query_name or " ".join(query_tokens)
    pn = primary_name or " ".join(primary_tokens)
    if not is_name_close_enough(qn, pn, query_tokens, primary_tokens):
        best_match *= 0.85

    # Final score with name-only coverage penalty
    return best_match * NAME_ONLY_PENALTY_MULTIPLIER
