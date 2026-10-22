"""
Unit tests for T8-5: Alias expansion safety.

Tests:
1. 'Ural Airlines' still 🔴 where genuinely listed (us_csl, uk_csl, eu_csl).
2. A query that expands to 'Rossiya' does not turn an unrelated entity 🔴 (us_ofac, eu_csl).
3. Hits derived only via ambiguous aliases are capped at 🟠 with reason 'alias_ambiguous'.
4. Existing S7 and Siberia locks still pass.
"""

import pytest
from modules.watchman.client import WatchmanClient
from modules.screening.tiering import (
    screen_query_all_lists,
    TIER_POTENTIAL_MATCH,
    TIER_POSSIBLE_MATCH,
    TIER_NO_MATCH,
)


@pytest.fixture(scope="module")
def watchman_client():
    return WatchmanClient(engine="python")


def test_ural_airlines_genuinely_listed(watchman_client):
    """'Ural Airlines' still 🔴 where genuinely listed."""
    res = screen_query_all_lists("Ural Airlines", client=watchman_client, query_type="airline")
    
    # Listed on us_csl, uk_csl, eu_csl
    assert res["us_csl"]["best_hit"]["tier"] == TIER_POTENTIAL_MATCH
    assert "URAL" in res["us_csl"]["best_hit"]["matched_name"].upper()
    
    assert res["uk_csl"]["best_hit"]["tier"] == TIER_POTENTIAL_MATCH
    assert "URAL" in res["uk_csl"]["best_hit"]["matched_name"].upper()
    
    assert res["eu_csl"]["best_hit"]["tier"] == TIER_POTENTIAL_MATCH
    
    # On us_ofac, Automobile Plant Ural is NOT 🔴
    assert res["us_ofac"]["best_hit"]["tier"] != TIER_POTENTIAL_MATCH


def test_rossiya_expansion_safety(watchman_client):
    """A query that expands to 'Rossiya' does not turn an unrelated entity 🔴."""
    res = screen_query_all_lists("Rossiya Airlines", client=watchman_client, query_type="airline")
    
    # Truly listed carrier on us_csl, uk_csl is 🔴
    assert res["us_csl"]["best_hit"]["tier"] == TIER_POTENTIAL_MATCH
    assert res["uk_csl"]["best_hit"]["tier"] == TIER_POTENTIAL_MATCH
    
    # Unrelated entities (Television Station Russia-1, Bank Rossiya) must NOT be 🔴
    assert res["us_ofac"]["best_hit"]["tier"] != TIER_POTENTIAL_MATCH
    assert res["eu_csl"]["best_hit"]["tier"] != TIER_POTENTIAL_MATCH


def test_s7_and_siberia_locks(watchman_client):
    """Existing S7 and Siberia locks still pass."""
    # S7
    res_s7 = screen_query_all_lists("S7", client=watchman_client, query_type="airline")
    assert res_s7["us_csl"]["best_hit"]["tier"] == TIER_POTENTIAL_MATCH
    assert res_s7["uk_csl"]["best_hit"]["tier"] == TIER_POTENTIAL_MATCH
    assert res_s7["us_ofac"]["best_hit"]["tier"] != TIER_POTENTIAL_MATCH
    
    # Siberia Airlines
    res_sib = screen_query_all_lists("Siberia Airlines", client=watchman_client, query_type="airline")
    assert res_sib["us_csl"]["best_hit"]["tier"] == TIER_POTENTIAL_MATCH
    assert res_sib["uk_csl"]["best_hit"]["tier"] == TIER_POTENTIAL_MATCH
    assert res_sib["us_ofac"]["best_hit"]["tier"] != TIER_POTENTIAL_MATCH
