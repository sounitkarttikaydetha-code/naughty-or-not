"""
Tests for Section 5: 0.50 Match Floor & Bypass Protections.
Ensures that no raw name-score candidate < 0.50 appears in results,
while all 5 explicit bypass paths (< 0.50) are preserved:
1. Exact identifier (id_match / exact_id)
2. Airline alias expansion (airline_alias_expansion)
3. Phonetic layer (phonetic_* / phonetic_evidence)
4. Transliteration (transliteration / is_transliteration)
5. Token pass (token_pass)
"""

import pytest
from modules.screening.tiering import tier_single_entity, TIER_BELOW_THRESHOLD, TIER_POTENTIAL_MATCH, TIER_POSSIBLE_MATCH
from modules.screening.config import DISPLAY_MIN_MATCH


def test_raw_name_score_below_half_discarded():
    """Candidates with match score < 0.50 without any bypass must be discarded (return None)."""
    entity = {
        "sourceID": "TEST-001",
        "name": "Acme Widgets Corporation",
        "match": 0.48,
        "score_source": "query",
        "sourceList": "us_ofac",
    }
    res = tier_single_entity("Acme Tools Ltd", entity, query_type="organisation")
    assert res is None, "Raw name candidate with score 0.48 must be discarded"


def test_raw_name_score_at_half_survives():
    """Candidates with match score >= 0.50 survive and are categorized."""
    entity = {
        "sourceID": "TEST-002",
        "name": "Acme Widgets Corporation",
        "match": 0.50,
        "score_source": "query",
        "sourceList": "us_ofac",
    }
    res = tier_single_entity("Acme Tools Ltd", entity, query_type="organisation")
    assert res is not None
    assert res["score"] == 0.50
    assert res["tier"] == TIER_BELOW_THRESHOLD


def test_bypass_1_exact_identifier():
    """Bypass 1: exact identifier match survives even if match < 0.50."""
    entity = {
        "sourceID": "TEST-003",
        "name": "Different Name Entirely",
        "match": 0.35,
        "id_match": True,
        "sourceList": "us_ofac",
    }
    res = tier_single_entity("Some Query", entity, query_type="organisation")
    assert res is not None, "Exact ID bypass must survive score < 0.50"
    assert res["score"] == 0.35


def test_bypass_2_airline_alias_expansion():
    """Bypass 2: airline alias expansion survives even if match < 0.50."""
    entity = {
        "sourceID": "TEST-004",
        "name": "PJSC Siberia Airlines",
        "match": 0.42,
        "airline_alias_expansion": True,
        "expanded_from": "S7",
        "sourceList": "us_csl",
    }
    res = tier_single_entity("S7 Airlines", entity, query_type="airline")
    assert res is not None, "Airline alias expansion bypass must survive score < 0.50"
    assert res["score"] == 0.42


def test_bypass_3_phonetic_layer():
    """Bypass 3: phonetic layer match survives even if match < 0.50."""
    entity = {
        "sourceID": "TEST-005",
        "name": "Qaddafi Trading",
        "match": 0.45,
        "phonetic_evidence": {"matched": True, "pairs": [("ghadafi", "qaddafi")]},
        "sourceList": "us_ofac",
    }
    res = tier_single_entity("Ghadafi Trading", entity, query_type="organisation")
    assert res is not None, "Phonetic layer bypass must survive score < 0.50"
    assert res["score"] == 0.45


def test_bypass_4_transliteration():
    """Bypass 4: transliteration match survives even if match < 0.50."""
    entity = {
        "sourceID": "TEST-006",
        "name": "Al-Bahr Maritime",
        "match": 0.46,
        "score_source": "transliteration",
        "is_transliteration": True,
        "sourceList": "us_ofac",
    }
    res = tier_single_entity("El Bahr Shipping", entity, query_type="organisation")
    assert res is not None, "Transliteration bypass must survive score < 0.50"
    assert res["score"] == 0.46


def test_bypass_5_token_pass():
    """Bypass 5: token pass (distinctive word match) survives even if match < 0.50."""
    entity = {
        "sourceID": "TEST-007",
        "name": "Global Aerospace Solutions",
        "match": 0.47,
        "score_source": "token_pass",
        "sourceList": "us_csl",
    }
    res = tier_single_entity("Aerospace Maintenance Hub", entity, query_type="organisation")
    assert res is not None, "Token pass bypass must survive score < 0.50"
    assert res["score"] == 0.47
