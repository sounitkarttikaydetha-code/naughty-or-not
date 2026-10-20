"""
Configuration loader for screening tiering, normalization, and thresholds.
Loads all rules and wordlists from tiering_config.json.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

CONFIG_PATH = Path(__file__).parent / "tiering_config.json"


def load_config() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


_config = load_config()

CANDIDATE_MIN_MATCH: float = float(_config.get("candidate_min_match", 0.60))
DISPLAY_MIN_MATCH: float = float(_config.get("display_min_match", 0.50))
DISPLAY_LIMIT: int = int(_config.get("display_limit", 25))
POSSIBLE_MATCH_THRESHOLD: float = float(_config.get("possible_match_threshold", 0.70))
POTENTIAL_MATCH_THRESHOLD: float = float(_config.get("potential_match_threshold", 0.80))
MIN_DISTINCTIVE_WORD_LEN: int = int(_config.get("min_distinctive_word_len", 4))

WEAK_WORDS: List[str] = _config.get("weak_words", [])
ALIAS_SPLIT_DELIMITERS: List[str] = _config.get("alias_split_delimiters", [])
COMPANY_TYPE_WORDS: List[str] = _config.get("company_type_words", [])
NAME_VARIANTS: Dict[str, str] = _config.get("name_variants", {})
ENABLE_COUNTRY_WORDS_GUARD: bool = bool(_config.get("enable_country_words_guard", False))
COUNTRY_WORDS: List[str] = _config.get("country_words", [])
KNOWN_CITIES: List[str] = _config.get("known_cities", [])
FUZZY_WORD_MIN_LEN: int = int(_config.get("fuzzy_word_min_len", 5))
FUZZY_WORD_MIN_SIMILARITY: float = float(_config.get("fuzzy_word_min_similarity", 0.90))

