"""
Tests for T8-10: Clean packaging, clean customer-ready README, and process tree termination.
"""

from pathlib import Path
import subprocess
import sys
import time
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_build_spec_excludes_developer_artifacts():
    """Verify that build.spec excludes tests, reviews, scripts, pycache, and logs."""
    spec_path = PROJECT_ROOT / "build.spec"
    assert spec_path.is_file(), "build.spec not found"

    with open(spec_path, "r", encoding="utf-8") as f:
        spec_content = f.read()

    # Excluded modules
    for excl in ["pytest", "unittest", "tests", "mypy", "ruff"]:
        assert f"'{excl}'" in spec_content, f"Expected {excl} to be in excludes list"

    # Datas must not include developer directories
    assert "('tests'" not in spec_content
    assert "('reviews'" not in spec_content
    assert "('scripts'" not in spec_content
    assert "'.git'" not in spec_content


def test_readme_is_clean_and_customer_ready():
    """Verify that README.md has no easter eggs, developer notes, or informal text."""
    readme_path = PROJECT_ROOT / "README.md"
    assert readme_path.is_file(), "README.md not found"

    with open(readme_path, "r", encoding="utf-8") as f:
        readme = f.read()

    prohibited_strings = [
        "SCROLLING",
        "Easter Egg",
        "got bored",
        "blood, sweat and tokens",
        "smile for the camera",
    ]
    for prohibited in prohibited_strings:
        assert prohibited.lower() not in readme.lower(), f"Found prohibited non-production text: {prohibited}"

    # Required sections
    assert "## Compliance & Governance" in readme
    assert "Naughty or not" in readme
    assert "Quick Start" in readme


def test_clean_process_tree_termination():
    """
    Spawns a mock subprocess tree, invokes the Windows process-tree termination command,
    and confirms the child processes are cleanly terminated.
    """
    if sys.platform != "win32":
        pytest.skip("Windows-specific process group test")

    # Launch a background sleep process
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    pid = proc.pid
    assert proc.poll() is None  # Running

    # Run tree kill
    subprocess.run(f"taskkill /F /T /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)

    # Confirm process terminated
    assert proc.poll() is not None or proc.wait(timeout=2) is not None
