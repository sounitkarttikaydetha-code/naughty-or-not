"""
Domain Tiering Rules and Constants.
Zero I/O.
"""
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class TieringThresholds:
    candidate_min_match: float = 0.60
    possible_match_threshold: float = 0.70
    potential_match_threshold: float = 0.80
    min_distinctive_word_len: int = 4
    fuzzy_min_similarity: float = 0.90


DEFAULT_THRESHOLDS = TieringThresholds()

REASON_EXACT_MATCH = "exact_match"
REASON_IDENTIFIER = "exact_identifier_match"
REASON_CORE_NAME = "core_name"
REASON_CORE_NAME_EQUAL = "core_name_equal"
REASON_SCORE_AND_CORE_NAME = "score_and_core_name"
REASON_SCORE = "score"
REASON_PHONETIC = "phonetic_and_token_overlap"
REASON_BELOW_THRESHOLD = "below_threshold"
REASON_NONE = "none"
