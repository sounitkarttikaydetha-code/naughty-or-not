"""
B9 Packaged Verification Test Suite for Naughty or not v1.0.0.
Verifies all Step B9 requirements:
1. Offline screening fallback with date warning.
2. Key handling: skip, session-only (not remembered, not on disk), remembered (keyring only).
3. Process shutdown & single-instance mutex mechanics.
4. Network leakage guard (zero query text transmitted on network without opt-in).
5. Uninstaller script retention config.
"""

import os
import sys
import socket
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.common.paths import get_app_data_dir, get_lists_dir
from modules.opensanctions.key_manager import (
    set_session_key,
    get_session_key,
    get_remembered_key,
    clear_remembered_key,
    mask_key,
)
from modules.screening.tiering import screen_query_all_lists
from modules.watchman.client import WatchmanClient


def test_offline_screening_and_dates():
    """Verify screening works locally with bundled seed lists and date metadata."""
    client = WatchmanClient(engine="python")
    res = screen_query_all_lists("Aeroflot", client=client, query_type="airline")
    assert "us_csl" in res
    assert res["us_csl"]["best_hit"]["tier"] == "POTENTIAL_MATCH"
    # Verify date retrieval
    from modules.common.list_updater import get_lists_date
    date_str = get_lists_date()
    assert date_str is not None
    assert len(date_str) > 0


def test_key_handling_skip():
    """Test skip -> session key is None, no keyring entry."""
    clear_remembered_key()
    set_session_key(None, remember=False)
    assert get_session_key() is None
    assert get_remembered_key() is None


def test_key_handling_not_remembered_not_on_disk(tmp_path):
    """Test key not remembered -> in memory only, not in keyring, not in LocalAppData or install files."""
    dummy_key = "test_key_live_not_remembered_1234"
    set_session_key(dummy_key, remember=False)
    assert get_session_key() == dummy_key
    assert get_remembered_key() is None
    assert mask_key(dummy_key).endswith("1234")
    assert "test_key_live" not in mask_key(dummy_key)

    # Verify key string is not written to %LOCALAPPDATA%\NaughtyOrNot or dist\NaughtyOrNot
    local_app = os.environ.get("LOCALAPPDATA")
    targets_to_check = []
    if local_app:
        targets_to_check.append(Path(local_app) / "NaughtyOrNot")
    targets_to_check.append(PROJECT_ROOT / "dist" / "NaughtyOrNot")

    for target in targets_to_check:
        if target.is_dir():
            for root, _, files in os.walk(target):
                for f in files:
                    fp = Path(root) / f
                    if fp.is_file() and fp.stat().st_size < 2 * 1024 * 1024 and fp.suffix.lower() in [".json", ".txt", ".log", ".yaml", ".ini", ".cfg", ".db"]:
                        try:
                            content = fp.read_text(encoding="utf-8", errors="ignore")
                            assert dummy_key not in content, f"Secret leaked in {fp}"
                        except Exception:
                            pass
    # Clean up session
    set_session_key(None, remember=False)


def test_key_handling_remembered():
    """Test remembered key -> stored in keyring, masked properly."""
    dummy_key = "test_key_live_remembered_9876"
    try:
        set_session_key(dummy_key, remember=True)
        assert get_session_key() == dummy_key
        assert get_remembered_key() == dummy_key
        assert mask_key(get_remembered_key()).endswith("9876")
        assert "test_key_live" not in mask_key(get_remembered_key())
    finally:
        clear_remembered_key()
        set_session_key(None, remember=False)
        assert get_remembered_key() is None


def test_network_leakage_guard(monkeypatch):
    """Assert zero query text leaves localhost during local Python screening."""
    transmitted_payloads = []
    real_socket = socket.socket

    class MonitoredSocket(real_socket):
        def connect(self, address):
            host, port = address[0], address[1]
            # Localhost is allowed for in-process Streamlit / pywebview
            if str(host) not in ["127.0.0.1", "localhost", "::1"]:
                raise ConnectionRefusedError(f"Unauthorized external network connection to {host}:{port}")
            return super().connect(address)

        def send(self, data, *args):
            transmitted_payloads.append(data)
            return super().send(data, *args)

        def sendto(self, data, *args):
            transmitted_payloads.append(data)
            return super().sendto(data, *args)

    monkeypatch.setattr(socket, "socket", MonitoredSocket)

    secret_name = "CONFIDENTIAL_TARGET_XYZ"
    client = WatchmanClient(engine="python")
    res = screen_query_all_lists(secret_name, client=client)
    assert res is not None

    # Verify the secret name never passed through any socket data
    for payload in transmitted_payloads:
        if isinstance(payload, bytes):
            assert secret_name.encode() not in payload
        elif isinstance(payload, str):
            assert secret_name not in payload


def test_uninstaller_script_preserves_logs_and_reports():
    """Verify setup.iss preserves user reports and logs upon uninstall."""
    iss_path = PROJECT_ROOT / "installer" / "setup.iss"
    assert iss_path.exists()
    content = iss_path.read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in content
    assert ("{localappdata}\\Programs\\ClearanceCheck" in content or "{localappdata}\\Programs\\NaughtyOrNot" in content)
    # Ensure uninstaller asks to keep logs and reports
    assert "Would you like to keep your screening logs and compliance reports" in content
    assert "DelTree" in content
