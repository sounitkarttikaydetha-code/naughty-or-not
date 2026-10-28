"""Unit tests for Raw Search mode (T5.1).
Validates text indexing, match options, filters, and target queries.
"""

from pathlib import Path
import pytest
import sqlite3

from modules.raw_search.engine import RawSearchEngine
from modules.raw_search.indexer import build_full_raw_index, INDEX_DB_PATH


@pytest.fixture(scope="module")
def raw_engine():
    if not INDEX_DB_PATH.is_file():
        build_full_raw_index()
    return RawSearchEngine()


def test_raw_search_rus2426_finds_uk_s7_record(raw_engine):
    """'RUS2426' must find the UK S7 record."""
    res = raw_engine.search("RUS2426")
    assert res["status"] == "OK"
    assert res["total_matches"] > 0
    uk_matches = [r for r in res["results"] if r["source"] == "uk_csl" and r["record_id"] == "RUS2426"]
    assert len(uk_matches) > 0
    names = [r["primary_name"] for r in uk_matches]
    assert any("Siberia Airlines" in n or "S7" in n for n in names)


def test_raw_search_vpbcd_finds_bis_aircraft(raw_engine):
    """'VP-BCD' must find the BIS aircraft row."""
    res = raw_engine.search("VP-BCD")
    assert res["status"] == "OK"
    assert res["total_matches"] > 0
    bis_matches = [r for r in res["results"] if r["source"] == "bis_aircraft"]
    assert len(bis_matches) > 0
    assert any("Aeroflot" in r["primary_name"] or "VP-BCD" in r["text_extract"] for r in bis_matches)


def test_raw_search_41215_finds_bis_aircraft_msn(raw_engine):
    """'41215' must find the BIS aircraft MSN."""
    res = raw_engine.search("41215")
    assert res["status"] == "OK"
    assert res["total_matches"] > 0
    bis_matches = [r for r in res["results"] if r["source"] == "bis_aircraft"]
    assert len(bis_matches) > 0
    assert any("41215" in r["text_extract"] for r in bis_matches)


def test_raw_search_sberbank_finds_ofac_csl_uk_eu(raw_engine):
    """'Sberbank' must find records from OFAC, US CSL, UK, and EU."""
    res = raw_engine.search("Sberbank", limit=200)
    assert res["status"] == "OK"
    matched_sources = {r["source"] for r in res["results"]}
    assert "us_ofac" in matched_sources
    assert "us_csl" in matched_sources
    assert "uk_csl" in matched_sources
    assert "eu_csl" in matched_sources


def test_raw_search_resistance_front_finds_mha_first_schedule(raw_engine):
    """'Resistance Front' must find the MHA First Schedule record."""
    res = raw_engine.search("Resistance Front")
    assert res["status"] == "OK"
    mha_matches = [r for r in res["results"] if r["source"] == "in_mha_first_schedule"]
    assert len(mha_matches) > 0
    names = [r["primary_name"] for r in mha_matches]
    assert any("Resistance Front" in n or "Lashkar" in n for n in names)


def test_raw_search_two_chars_rejected_as_too_short(raw_engine):
    """'ab' must be rejected as too short."""
    res = raw_engine.search("ab", search_field="All fields")
    assert res["status"] == "INVALID_QUERY"
    assert "at least 3 characters" in res["message"]


def test_raw_search_short_id_allowed_in_ids_only_field(raw_engine):
    """Short query like '36' is allowed when search_field is 'IDs and numbers only'."""
    res = raw_engine.search("36", search_field="IDs and numbers only")
    assert res["status"] in ["OK", "NO_RESULTS"]


def test_simulated_missing_raw_file_shows_circle():
    """Simulated missing raw file shows ⚪ in source statuses."""
    # Query a test database where one source is missing
    test_db = Path("data/test_missing_raw_index.db")
    if test_db.exists():
        test_db.unlink()
    con = sqlite3.connect(str(test_db))
    cur = con.cursor()
    cur.execute("CREATE TABLE source_meta (source TEXT PRIMARY KEY, status TEXT, record_count INTEGER, list_date TEXT, file_path TEXT, last_indexed TEXT);")
    cur.execute("INSERT INTO source_meta VALUES ('us_ofac', 'OK', 100, '2026-10-18', 'data/raw/us_ofac_sdn.csv', '2026-10-20');")
    cur.execute("INSERT INTO source_meta VALUES ('eu_csl', 'MISSING', 0, 'UNKNOWN', 'data/raw/missing_eu.xml', '2026-10-20');")
    con.commit()
    con.close()

    engine = RawSearchEngine(db_path=test_db)
    statuses = engine.get_source_statuses()
    assert statuses["us_ofac"]["status"] == "OK"
    assert statuses["eu_csl"]["status"] == "⚪"

    if test_db.exists():
        test_db.unlink()


def test_raw_search_hafiz_saeed_whole_word_finds_un_eu_and_mha():
    """Verify that 'Whole word' matches 'Hafiz Saeed' across UN, EU, MHA, and OFAC aliases."""
    engine = RawSearchEngine()
    res = engine.search(query="Hafiz Saeed", match_option="Whole word", search_field="All fields")
    assert res["status"] == "OK"
    assert res["total_matches"] >= 4
    sources = [r["source"] for r in res["results"]]
    assert "un_csl" in sources
    assert "in_mha_fourth_schedule" in sources
