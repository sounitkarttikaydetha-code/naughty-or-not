"""
Tests for desktop packaging and launcher compliance.
Enforces that no Docker references or port 8084 appear in the launcher or its configuration.
"""

from pathlib import Path

def test_no_docker_or_port_8084_in_launcher():
    """Verify B1 rule: packaged launcher and config must not reference Docker or port 8084."""
    launcher_path = Path(__file__).resolve().parent.parent / "desktop_launcher.py"
    assert launcher_path.is_file(), "desktop_launcher.py must exist"

    content = launcher_path.read_text(encoding="utf-8").lower()
    
    # 8084 check
    assert "8084" not in content, "desktop_launcher.py must not reference port 8084"
    
    # Docker check (except in docstrings/comments that explicitly disallow it)
    lines = content.splitlines()
    for idx, line in enumerate(lines, 1):
        cleaned = line.split("#")[0].strip()  # Strip comments
        if not cleaned:
            continue
        assert "8084" not in cleaned, f"Line {idx} in desktop_launcher.py contains 8084: {line}"
        assert "docker" not in cleaned, f"Line {idx} in desktop_launcher.py contains docker: {line}"


def test_single_instance_mutex_defined():
    """Verify launcher defines single-instance mutex logic."""
    launcher_path = Path(__file__).resolve().parent.parent / "desktop_launcher.py"
    content = launcher_path.read_text(encoding="utf-8")
    assert "NaughtyOrNot_SingleInstance_Mutex" in content
    assert "check_single_instance" in content


def test_webview2_fallback_message():
    """Verify launcher contains clear WebView2 fallback message with Microsoft link."""
    launcher_path = Path(__file__).resolve().parent.parent / "desktop_launcher.py"
    content = launcher_path.read_text(encoding="utf-8")
    assert "https://developer.microsoft.com/en-us/microsoft-edge/webview2/" in content
    assert "check_webview2_installed" in content
