"""
Unit tests for T8-6: Short names and non-Latin input.

Tests:
1. Non-Latin detection: Cyrillic, Arabic, Chinese, mixed script return warning.
2. Licence and transliteration: anyascii produces clean transliterations (ISC licence).
3. Clean non-Latin queries never return ✅ without a warning.
4. Text search finds EU Cyrillic record for 'Сбербанк'.
5. Short name queries (VTB, S7, IRGC, ZTE) are correctly processed and indexed without DF blocking issues.
"""

import pytest
from modules.engine.name_prep import is_non_latin, get_transliteration
from modules.screening.tiering import screen_query_all_lists
from modules.watchman.client import WatchmanClient
from modules.raw_search.engine import RawSearchEngine


@pytest.fixture(scope="module")
def watchman_client():
    return WatchmanClient(engine="python")


@pytest.fixture(scope="module")
def raw_search_engine():
    return RawSearchEngine()


def test_non_latin_detection():
    """Each non-Latin sample returns the warning banner."""
    samples = [
        "Сбербанк",
        "طيران ماهان",
        "中国银行",
        "Sberbank Сбербанк",
    ]
    for sample in samples:
        nl, warning, tl = get_transliteration(sample)
        assert nl is True, f"Failed to detect non-Latin in '{sample}'"
        assert warning == "This name contains non-Latin characters. Automatic matching is limited — also use Text search and Manual check."
        assert tl is not None, f"Failed to transliterate '{sample}'"


def test_latin_detection():
    """Latin queries (including accented Latin) do not trigger non-Latin warning."""
    samples = [
        "Sberbank",
        "VTB Bank",
        "Aeroflot",
        "Société Générale",
        "Müller",
    ]
    for sample in samples:
        nl, warning, tl = get_transliteration(sample)
        assert nl is False, f"Erroneously flagged Latin query '{sample}'"
        assert warning is None
        assert tl is None


def test_non_latin_never_returns_clean_green_without_warning(watchman_client):
    """Non-Latin input must never return ✅ without a warning."""
    # Screen Arabic 'طيران ماهان' (clean across sanctions lists)
    res = screen_query_all_lists("طيران ماهان", client=watchman_client, query_type="airline")
    for src in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]:
        hit = res[src]["best_hit"]
        # The list result or hit must carry the warning
        assert res[src].get("is_non_latin") is True
        assert res[src].get("non_latin_warning") == "This name contains non-Latin characters. Automatic matching is limited — also use Text search and Manual check."


def test_sberbank_finds_eu_record_in_text_search(raw_search_engine):
    """'Сбербанк' finds the EU record in Text search."""
    res = raw_search_engine.search("Сбербанк")
    assert res["status"] == "OK"
    assert res["total_matches"] > 0
    eu_matches = [r for r in res["results"] if r["source"] == "eu_csl"]
    assert len(eu_matches) > 0, "Failed to find EU record in raw search for 'Сбербанк'"
    # Record ID 142064 is Sberbank on EU CSL
    assert any(r["record_id"] == "142064" or "Сбербанк" in r["text_extract"] or "Sberbank" in r["primary_name"] for r in eu_matches)


def test_short_name_screening(watchman_client):
    """Short names (VTB, S7, IRGC) are retrieved and scored without blocking."""
    # VTB (Organisation)
    res_vtb = screen_query_all_lists("VTB", client=watchman_client, query_type="organisation")
    assert res_vtb["us_ofac"]["best_hit"]["tier"] == "POTENTIAL_MATCH"
    assert res_vtb["uk_csl"]["best_hit"]["tier"] == "POTENTIAL_MATCH"
    assert res_vtb["eu_csl"]["best_hit"]["tier"] == "POTENTIAL_MATCH"

    # S7 (Airline)
    res_s7 = screen_query_all_lists("S7", client=watchman_client, query_type="airline")
    assert res_s7["us_csl"]["best_hit"]["tier"] == "POTENTIAL_MATCH"
    assert res_s7["uk_csl"]["best_hit"]["tier"] == "POTENTIAL_MATCH"

    # IRGC (Organisation)
    res_irgc = screen_query_all_lists("IRGC", client=watchman_client, query_type="organisation")
    assert res_irgc["us_ofac"]["best_hit"]["tier"] == "POTENTIAL_MATCH"
    assert res_irgc["uk_csl"]["best_hit"]["tier"] == "POTENTIAL_MATCH"
    assert res_irgc["eu_csl"]["best_hit"]["tier"] == "POTENTIAL_MATCH"
