"""Unit and regression tests for screening engine performance (T8-3)."""

import time
import pytest
from modules.watchman.client import WatchmanClient, get_python_engine
import modules.watchman.client as wc
from modules.screening.tiering import screen_query_all_lists


def test_disk_cache_load_timing():
    """Verify loading pre-built engine index from disk cache is fast (<= 5.0 s with generous CI buffer)."""
    wc._singleton_python_engine = None
    t0 = time.perf_counter()
    eng = get_python_engine()
    dt = time.perf_counter() - t0
    assert dt <= 5.0, f"Engine disk cache load took {dt:.3f} s (expected <= 5.0 s)"
    assert eng.health()["healthy"] is True


def test_clean_organisation_search_timing():
    """Verify screening a clean organisation completes in under generous CI buffer (<= 3.0 s)."""
    client = WatchmanClient(engine="python")
    # Warmup
    screen_query_all_lists("warmup", client=client)

    t0 = time.perf_counter()
    res = screen_query_all_lists("Jaipur International Airport Limited", client=client, query_type="organisation")
    dt = time.perf_counter() - t0
    assert dt <= 3.0, f"Clean organisation search took {dt:.3f} s (expected <= 3.0 s)"
    # Must be clean on all sources
    for src in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]:
        assert res[src]["best_hit"]["tier"] == "NO_MATCH"


def test_airline_alias_search_timing():
    """Verify screening an airline with alias expansion (Aeroflot) completes in <= 4.0 s."""
    client = WatchmanClient(engine="python")
    t0 = time.perf_counter()
    res = screen_query_all_lists("Aeroflot", client=client, query_type="airline")
    dt = time.perf_counter() - t0
    assert dt <= 4.0, f"Aeroflot airline search took {dt:.3f} s (expected <= 4.0 s)"
    # Must identify expected matches on US CSL and UK CSL
    assert res["us_csl"]["best_hit"]["tier"] == "POTENTIAL_MATCH"
    assert res["uk_csl"]["best_hit"]["tier"] == "POTENTIAL_MATCH"
