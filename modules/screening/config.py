"""
Configuration for screening tiering and normalisation.
Loads settings from tiering_config.json with safe fallbacks.
"""

import json
import os
from pathlib import Path
from typing import List, Set

CONFIG_PATH = Path(__file__).parent / "tiering_config.json"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "candidate_min_match": 0.65,
        "potential_match_threshold": 0.80,
        "require_exact_core_match": True,
        "company_type_words": [
            "Joint Stock Company",
            "Limited Liability Company",
            "Public Joint Stock Company",
            "PJSC", "JSC", "OJSC", "CJSC", "PAO", "AO", "OOO", "ZAO", "OAO",
            "LLC", "LLP", "Ltd", "Limited", "Pvt", "Private", "Public",
            "Company", "Co", "Corp", "Corporation", "Inc", "AG", "GmbH",
            "SA", "BV", "NV", "PLC", "FZE", "FZCO"
        ]
    }


_config = load_config()

CANDIDATE_MIN_MATCH: float = float(_config.get("candidate_min_match", 0.65))
POTENTIAL_MATCH_THRESHOLD: float = float(_config.get("potential_match_threshold", 0.80))
REQUIRE_EXACT_CORE_MATCH: bool = bool(_config.get("require_exact_core_match", True))
COMPANY_TYPE_WORDS: List[str] = _config.get("company_type_words", [])
