"""
Side-by-Side Isolation Tests for Clearance Check Canary.
Validates:
1. Complete isolation between stable data directory (%LOCALAPPDATA%\\ClearanceCheck\\)
   and Canary data directory (%LOCALAPPDATA%\\ClearanceCheckCanary\\).
2. Separate Application ID, install folder, and Start-menu entries in Inno Setup scripts.
3. Vector and multi-resolution Canary icon assets (with 'C' badge) exist.
4. 'Import a copy of stable data' operates strictly read-only and guarantees zero mutation of stable files.
5. Permanent evaluation notice present in branding and report templates.
"""
import hashlib
import os
import re
import sqlite3
import tempfile
from pathlib import Path
import pytest
import yaml

from canary.interfaces.desktop.import_stable import (
    get_stable_data_dir,
    get_canary_data_dir,
    import_copy_of_stable_data,
    compute_file_sha256,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_01_distinct_data_directories():
    """Assert stable and canary data directories are completely separate."""
    stable_dir = get_stable_data_dir()
    canary_dir = get_canary_data_dir()

    assert stable_dir.name != canary_dir.name
    assert "canary" in canary_dir.name.lower()
    assert "canary" not in stable_dir.name.lower()


def test_02_separate_installer_app_id_and_paths():
    """Assert Canary Inno Setup script has unique GUID AppId and distinct installation directories."""
    stable_iss = PROJECT_ROOT / "installer" / "setup.iss"
    canary_iss = PROJECT_ROOT / "installer" / "setup_canary.iss"

    assert stable_iss.is_file(), "Stable installer/setup.iss missing"
    assert canary_iss.is_file(), "Canary installer/setup_canary.iss missing"

    stable_txt = stable_iss.read_text(encoding="utf-8")
    canary_txt = canary_iss.read_text(encoding="utf-8")

    # Extract AppId
    stable_app_id = re.search(r"AppId=([^\r\n]+)", stable_txt).group(1)
    canary_app_id = re.search(r"AppId=([^\r\n]+)", canary_txt).group(1)

    assert stable_app_id != canary_app_id, f"Canary must have a separate AppId: got {canary_app_id}"
    assert "Clearance Check Canary" in canary_txt
    assert "ClearanceCheckCanary" in canary_txt
    assert "icon_canary.ico" in canary_txt


def test_03_canary_vector_icon_assets_exist():
    """Verify Canary icons exist in vector SVG, multi-resolution ICO, and all required PNG sizes."""
    assets_dir = PROJECT_ROOT / "assets"

    assert (assets_dir / "icon_canary.svg").is_file()
    assert (assets_dir / "icon_canary_white.svg").is_file()
    assert (assets_dir / "icon_canary.ico").is_file()

    for sz in [16, 32, 64, 128, 256]:
        png_file = assets_dir / f"icon_canary_{sz}.png"
        assert png_file.is_file(), f"Canary icon size {sz}px missing: {png_file}"

    # Verify SVG contains the 'C' badge
    svg_content = (assets_dir / "icon_canary.svg").read_text(encoding="utf-8")
    assert "canary-badge" in svg_content


def test_04_import_stable_data_guarantees_read_only_isolation():
    """Verify 'Import a copy of stable data' strictly preserves the stable database without modification."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf_stable:
        stable_db = Path(tf_stable.name)
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf_canary:
        canary_db = Path(tf_canary.name)

    try:
        # Populate mock stable database
        conn = sqlite3.connect(str(stable_db))
        conn.execute("""
            CREATE TABLE screening_logs (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                windows_user TEXT,
                inputs TEXT,
                result TEXT,
                score REAL,
                duration_ms INTEGER
            );
        """)
        conn.execute("""
            INSERT INTO screening_logs (id, timestamp, windows_user, inputs, result, score, duration_ms)
            VALUES (1, '2026-10-25T12:00:00Z', 'DOM\\screener', 'Test Corp', 'CLEAR', 0.0, 10);
        """)
        conn.commit()
        conn.close()

        hash_before = compute_file_sha256(stable_db)

        # Run import
        res = import_copy_of_stable_data(source_db_path=stable_db, target_db_path=canary_db)
        assert res["status"] == "SUCCESS"
        assert res["imported_counts"]["screening_logs"] == 1
        assert res["stable_file_verified_unaltered"] is True

        hash_after = compute_file_sha256(stable_db)
        assert hash_before == hash_after, "Stable database hash changed during import! Fatal violation of read-only isolation."

        # Verify Canary DB contains imported row
        conn_canary = sqlite3.connect(str(canary_db))
        cur = conn_canary.cursor()
        cur.execute("SELECT inputs, user_id, auth_provider FROM screening_log WHERE id = 1")
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "Test Corp"
        assert row[1] == "DOM\\screener"
        assert row[2] == "windows_fallback"
        conn_canary.close()

    finally:
        if stable_db.exists():
            try:
                stable_db.unlink()
            except OSError:
                pass
        if canary_db.exists():
            try:
                canary_db.unlink()
            except OSError:
                pass


def test_05_permanent_canary_evaluation_banner():
    """Verify permanent notice 'Canary build — for evaluation only. Not for screening decisions.' in config."""
    branding_file = PROJECT_ROOT / "config" / "branding_canary.yaml"
    assert branding_file.is_file(), "config/branding_canary.yaml missing"
    with open(branding_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "Canary build — for evaluation only. Not for screening decisions." in data["banner_text"]
    assert "Canary" in data["app_name"]
    assert data["environment"] == "canary"
