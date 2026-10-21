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
