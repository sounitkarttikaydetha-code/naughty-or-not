"""
Tests for Part 3:
1. Zero network socket calls during Text search, Manual check save, and offline screening.
2. Shutdown flush & SQLite PRAGMA integrity_check.
"""

import socket
import sqlite3
import pytest
from pathlib import Path
from modules.raw_search.engine import RawSearchEngine
from modules.reporting.logger import log_manual_check, DB_PATH
from desktop_launcher import shutdown_cleanly


def test_zero_network_during_text_search(monkeypatch):
    """Confirm Text search does not make any network calls."""
    network_calls = []
    orig_connect = socket.socket.connect

    def forbidden_connect(self, address):
        # Ignore localhost/127.0.0.1 connections
        host = address[0] if isinstance(address, tuple) else address
        if host not in ("127.0.0.1", "localhost", "::1"):
            network_calls.append(address)
            raise RuntimeError(f"Network call forbidden: {address}")
        return orig_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", forbidden_connect)

    engine = RawSearchEngine()
    res = engine.search("RUS2426")
    assert res["status"] == "OK"
    assert len(network_calls) == 0


def test_zero_network_during_manual_check_save(monkeypatch):
    """Confirm Manual check logging does not make any network calls."""
    network_calls = []
    orig_connect = socket.socket.connect

    def forbidden_connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if host not in ("127.0.0.1", "localhost", "::1"):
            network_calls.append(address)
            raise RuntimeError(f"Network call forbidden: {address}")
        return orig_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", forbidden_connect)

    # Save a manual check
    log_manual_check(
        name="Test Airline Parity",
        source="us_csl",
        result="CLEARED",
        comment="Offline manual check verification",
    )
    assert len(network_calls) == 0


def test_shutdown_flush_and_integrity():
    """Verify shutdown_cleanly checkpoints DB and PRAGMA integrity_check is ok."""
    shutdown_cleanly()
    if DB_PATH.exists():
        with sqlite3.connect(str(DB_PATH)) as con:
            res = con.execute("PRAGMA integrity_check;").fetchall()
            assert res == [("ok",)], f"Integrity check failed: {res}"


def test_shutdown_after_search_and_reopen_integrity():
    """Run search, immediate shutdown, reopen DB and verify PRAGMA integrity_check."""
    from modules.screening.tiering import screen_query_all_lists
    from modules.watchman.client import WatchmanClient
    from modules.reporting.logger import log_search

    client = WatchmanClient(engine="python")
    w_res = screen_query_all_lists("Aeroflot", client=client, query_type="airline")
    log_search(
        search_type="airline",
        inputs={"name": "Aeroflot"},
        source_results=[],
        overall_tier="LIKELY",
        duration_ms=45,
    )
    shutdown_cleanly()

    with sqlite3.connect(str(DB_PATH)) as con:
        res = con.execute("PRAGMA integrity_check;").fetchall()
        assert res == [("ok",)], f"Integrity check failed after search shutdown: {res}"


def test_deploy_and_toolbar_hidden():
    """Verify Deploy button and Streamlit developer menus are hidden in config and CSS."""
    cfg_path = Path(__file__).resolve().parent.parent / ".streamlit" / "config.toml"
    assert cfg_path.is_file()
    cfg_text = cfg_path.read_text(encoding="utf-8")
    assert 'toolbarMode = "viewer"' in cfg_text
    assert "showDeployButton = false" in cfg_text

    app_path = Path(__file__).resolve().parent.parent / "app.py"
    app_text = app_path.read_text(encoding="utf-8")
    assert ".stDeployButton" in app_text
    assert "#MainMenu" in app_text
