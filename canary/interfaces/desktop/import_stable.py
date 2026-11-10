"""
Import a Copy of Stable Data (Canary Desktop Feature).
Strictly read-only copy: reads from stable data directory (%LOCALAPPDATA%\\ClearanceCheck\\),
imports into Canary database, and guarantees that the stable database is NEVER written to or altered.
"""
import hashlib
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Dict, Any

from canary.adapters.storage.migrations.import_v1_migration import import_v1_database


def compute_file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def get_stable_data_dir() -> Path:
    local_app = os.environ.get("LOCALAPPDATA")
    if local_app:
        d1 = Path(local_app) / "ClearanceCheck"
        if d1.is_dir():
            return d1
        d2 = Path(local_app) / "NaughtyOrNot"
        if d2.is_dir():
            return d2
        return d1
    return Path.home() / ".clearance_check"


def get_canary_data_dir() -> Path:
    override = os.environ.get("CANARY_DATA_DIR")
    if override:
        return Path(override)
    local_app = os.environ.get("LOCALAPPDATA")
    if local_app:
        return Path(local_app) / "ClearanceCheckCanary"
    return Path.home() / ".clearance_check_canary"


def import_copy_of_stable_data(
    source_db_path: Path = None,
    target_db_path: Path = None,
) -> Dict[str, Any]:
    """
    Copy and import data from stable Clearance Check into Clearance Check Canary.
    Safety guarantee: stable files are opened strictly in read-only mode and hashes are verified.
    """
    stable_db = source_db_path or (get_stable_data_dir() / "logs" / "screening.db")
    canary_db = target_db_path or (get_canary_data_dir() / "logs" / "clearance_canary.db")

    if not stable_db.exists():
        return {
            "status": "SKIPPED",
            "message": f"Stable database not found at {stable_db}. No stable data to import.",
            "imported_counts": {"screening_logs": 0, "ownership_checks": 0, "records": 0},
        }

    # Verify initial hash of stable db
    initial_hash = compute_file_sha256(stable_db)

    # Initialize canary DB if needed
    canary_db.parent.mkdir(parents=True, exist_ok=True)
    from canary.adapters.storage.sqlite_repo import SQLiteRepository
    repo = SQLiteRepository(canary_db)

    with repo.get_connection() as conn:
        counts = import_v1_database(stable_db, conn)

    # Verify final hash of stable db to prove zero mutation
    final_hash = compute_file_sha256(stable_db)
    if initial_hash != final_hash:
        raise RuntimeError("FATAL INTEGRITY VIOLATION: Stable database was modified during import!")

    return {
        "status": "SUCCESS",
        "message": "Successfully imported a copy of stable data into Canary without modifying stable files.",
        "imported_counts": counts,
        "stable_file_verified_unaltered": True,
        "stable_sha256": final_hash,
    }
