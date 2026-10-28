"""
Standard path resolution for Naughty or not.
Handles data directories, %LOCALAPPDATA% storage, bundled seed lists, and settings.
"""

import os
import sys
from pathlib import Path
from typing import Optional


def get_base_dir() -> Path:
    """Return the base directory of the installed application or repository."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass and Path(meipass).is_dir():
            return Path(meipass)
        exe_parent = Path(sys.executable).resolve().parent
        if (exe_parent / "_internal").is_dir():
            return exe_parent / "_internal"
        return exe_parent
    return Path(__file__).resolve().parent.parent.parent


def get_app_data_dir() -> Path:
    """
    Return the per-user data directory (%LOCALAPPDATA%\\NaughtyOrNot).
    Uses NAUGHTY_DATA_DIR environment variable if specified.
    """
    override = os.environ.get("NAUGHTY_DATA_DIR")
    if override:
        p = Path(override)
        p.mkdir(parents=True, exist_ok=True)
        return p

    # If running in development without frozen flag and local data/ exists and no env override,
    # and not running desktop launcher, we can default to repo root for dev/test compatibility.
    if not getattr(sys, "frozen", False) and not os.environ.get("NAUGHTY_DESKTOP_MODE"):
        repo_data = get_base_dir() / "data"
        if repo_data.is_dir():
            return get_base_dir()

    # Portable mode: if .portable or portable.dat exists in application directory
    base = get_base_dir()
    if (base / ".portable").exists() or (base / "portable.dat").exists():
        app_dir = base / "data"
        app_dir.mkdir(parents=True, exist_ok=True)
        return app_dir

    local_app = os.environ.get("LOCALAPPDATA")
    if local_app:
        app_dir = Path(local_app) / "NaughtyOrNot"
    else:
        app_dir = Path.home() / ".naughty_or_not"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_lists_dir() -> Path:
    """Directory holding downloaded or active sanction lists."""
    p = get_app_data_dir() / "lists"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_logs_dir() -> Path:
    """Directory holding append-only audit database and logs."""
    p = get_app_data_dir() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_reports_dir() -> Path:
    """Directory holding generated PDF and Excel reports."""
    p = get_app_data_dir() / "reports"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_cache_dir() -> Path:
    """Directory holding binary index caches."""
    p = get_app_data_dir() / "cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_index_db_path() -> Path:
    """Path to SQLite raw search index."""
    # In development mode, check repo data/raw_index.db first
    if not getattr(sys, "frozen", False) and not os.environ.get("NAUGHTY_DESKTOP_MODE"):
        repo_index = get_base_dir() / "data" / "raw_index.db"
        if repo_index.is_file():
            return repo_index
    return get_app_data_dir() / "raw_index.db"


def get_settings_path() -> Path:
    """Path to application settings JSON."""
    return get_app_data_dir() / "settings.json"


def get_seed_data_dir() -> Path:
    """Path to bundled seed lists bundled with the installer."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            cand = Path(meipass) / "data"
            if cand.is_dir():
                return cand
        exe_parent = Path(sys.executable).resolve().parent
        cand_internal = exe_parent / "_internal" / "data"
        if cand_internal.is_dir():
            return cand_internal
        cand2 = exe_parent / "data"
        if cand2.is_dir():
            return cand2
    base = get_base_dir()
    if (base / "data").is_dir():
        return base / "data"
    if (base / "_internal" / "data").is_dir():
        return base / "_internal" / "data"
    return base / "data"
