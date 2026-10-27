"""
Configuration loader for screening tiering, normalization, and thresholds.
Loads all rules and wordlists from tiering_config.json.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List

CONFIG_PATH = Path(__file__).parent / "tiering_config.json"


def load_config() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


_config = load_config()

# Screening engine: 'python' (default) or 'watchman' (reference container)
ENGINE: str = os.getenv("ENGINE", _config.get("engine", "python")).lower()
PHONETIC_ENABLED: bool = os.getenv("PHONETIC_ENABLED", str(_config.get("phonetic_enabled", "true"))).lower() in ("1", "true", "yes")

CANDIDATE_MIN_MATCH: float = float(_config.get("candidate_min_match", 0.60))
DISPLAY_MIN_MATCH: float = float(_config.get("display_min_match", 0.50))
DISPLAY_LIMIT: int = int(_config.get("display_limit", 25))
POSSIBLE_MATCH_THRESHOLD: float = float(_config.get("possible_match_threshold", 0.70))
POTENTIAL_MATCH_THRESHOLD: float = float(_config.get("potential_match_threshold", 0.80))
MIN_DISTINCTIVE_WORD_LEN: int = int(_config.get("min_distinctive_word_len", 4))

WEAK_WORDS: List[str] = _config.get("weak_words", [])
ALIAS_SPLIT_DELIMITERS: List[str] = _config.get("alias_split_delimiters", [])
COMPANY_TYPE_WORDS: List[str] = _config.get("company_type_words", [])


NAME_VARIANTS: Dict[str, str] = _config.get("name_variants", {
    "mohammed": "mohammad",
    "muhammad": "mohammad",
    "mohamed": "mohammad",
})


def load_curated_name_variants() -> Dict[str, str]:
    """Load name variants from config/name_variants.yaml, solely for phonetic matching."""
    yaml_path = Path("config/name_variants.yaml")
    if not yaml_path.is_file():
        yaml_path = Path(__file__).resolve().parent.parent.parent / "config" / "name_variants.yaml"
    if yaml_path.is_file():
        try:
            import yaml
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            v_map = {}
            for group, words in data.get("variants", {}).items():
                for w in words:
                    v_map[w.lower()] = group
            if v_map:
                return v_map
        except Exception:
            pass
    return {}


CURATED_NAME_VARIANTS: Dict[str, str] = load_curated_name_variants()
ENABLE_COUNTRY_WORDS_GUARD: bool = bool(_config.get("enable_country_words_guard", False))
COUNTRY_WORDS: List[str] = _config.get("country_words", [])
KNOWN_CITIES: List[str] = _config.get("known_cities", [])
FUZZY_WORD_MIN_LEN: int = int(_config.get("fuzzy_word_min_len", 5))
FUZZY_WORD_MIN_SIMILARITY: float = float(_config.get("fuzzy_word_min_similarity", 0.90))
