"""
Tests for T8-6A: Sound-Alike Phonetic Matching (Double Metaphone + Curated Transliteration Variants).
"""

import os
import pytest
from modules.screening.tiering import (
    check_phonetic_match,
    screen_query_all_lists,
    TIER_POSSIBLE_MATCH,
    TIER_POTENTIAL_MATCH,
)
from modules.screening.config import (
    CURATED_NAME_VARIANTS,
    NAME_VARIANTS,
    PHONETIC_ENABLED,
)
from modules.watchman.client import WatchmanClient


def test_phonetic_check_unit_pairs():
    """Verify check_phonetic_match on core sound-alike pairs."""
    variants = {**NAME_VARIANTS, **CURATED_NAME_VARIANTS}

    # Evgeniy / Yevgeny
    is_s, is_w, ev = check_phonetic_match(["evgeniy"], ["yevgeny"], is_person=True, name_variants=variants)
    assert is_s is True, f"Expected Evgeniy/Yevgeny to match phonetically: {ev}"

    # Shaikh / Sheikh
    is_s, is_w, ev = check_phonetic_match(["shaikh"], ["sheikh"], is_person=True, name_variants=variants)
    assert is_s is True, f"Expected Shaikh/Sheikh to match phonetically: {ev}"

    # Kadhafi / Qadhafi
    is_s, is_w, ev = check_phonetic_match(["kadhafi"], ["qadhafi"], is_person=True, name_variants=variants)
    assert is_s is True, f"Expected Kadhafi/Qadhafi to match phonetically: {ev}"

    # Wladimir / Vladimir
    is_s, is_w, ev = check_phonetic_match(["wladimir"], ["vladimir"], is_person=True, name_variants=variants)
    assert is_s is True, f"Expected Wladimir/Vladimir to match phonetically: {ev}"

    # Choudhary / Chaudhary
    is_s, is_w, ev = check_phonetic_match(["choudhary"], ["chaudhary"], is_person=True, name_variants=variants)
    assert is_s is True, f"Expected Choudhary/Chaudhary to match phonetically: {ev}"

    # Husayn / Hussein
    is_s, is_w, ev = check_phonetic_match(["husayn"], ["hussein"], is_person=True, name_variants=variants)
    assert is_s is True, f"Expected Husayn/Hussein to match phonetically: {ev}"


def test_phonetic_negative_short_tokens():
    """Tokens < 4 chars are not matched phonetically."""
    is_s, is_w, ev = check_phonetic_match(["ali"], ["aly"], is_person=True)
    assert is_s is False


def test_phonetic_negative_person_token_count_mismatch():
    """A person search where candidate has different number of distinctive tokens is rejected."""
    is_s, is_w, ev = check_phonetic_match(["kadhafi"], ["qadhafi", "al-qadhafi"], is_person=True)
    assert is_s is False
    assert is_w is True


def test_phonetic_negative_length_ratio_guard():
    """Tokens with length ratio outside [0.6, 1.67] are not paired even if prefix matches."""
    # e.g., 'vlad' (4 chars) vs 'vladimirovich' (13 chars) ratio = 4/13 = 0.307
    is_s, is_w, ev = check_phonetic_match(["vlad"], ["vladimirovich"], is_person=True)
    assert is_s is False


def test_phonetic_integration_kadhafi_elevation():
    """
    Kadhafi on US OFAC elevates to 🟠 (POSSIBLE_MATCH_REVIEW) via phonetic matching
    on record 15258 (AL-QADHAFI).
    """
    client = WatchmanClient(engine="python")
    res = screen_query_all_lists("Kadhafi", client=client, query_type="person")
    ofac_hit = res.get("us_ofac", {}).get("best_hit", {})
    assert ofac_hit.get("tier") == TIER_POSSIBLE_MATCH
    assert ofac_hit.get("reason") in ("phonetic_name_person", "phonetic_match")
    assert ofac_hit.get("source_id") == "15258"


def test_phonetic_mutation_flag_disabled(monkeypatch):
    """
    Mutation test: setting PHONETIC_ENABLED = False disables the phonetic retrieval
    and prevents phonetic elevation.
    """
    import modules.screening.tiering as tiering_mod
    from modules.watchman.client import get_python_engine
    monkeypatch.setattr(tiering_mod, "PHONETIC_ENABLED", False)

    engine = get_python_engine()
    orig_flag = engine.phonetic_enabled
    engine.phonetic_enabled = False
    try:
        client = WatchmanClient(engine="python")
        res = screen_query_all_lists("Kadhafi", client=client, query_type="person")
        ofac_hit = res.get("us_ofac", {}).get("best_hit", {})
        assert ofac_hit.get("tier") != TIER_POSSIBLE_MATCH
        assert ofac_hit.get("reason") != "phonetic_name_person"
    finally:
        engine.phonetic_enabled = orig_flag
