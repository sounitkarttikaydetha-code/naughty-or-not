"""
SQLite Audit Logger for Sanction checK (T5).
Maintains an append-only audit trail at logs/screening.db per SPEC.md Section 4.3.
"""

import getpass
import json
import logging
import os
import platform
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _get_base_data_dir() -> Path:
    """Return base storage directory with %LOCALAPPDATA% fallback when frozen or in Program Files."""
    try:
        from modules.common.paths import get_app_data_dir
        return get_app_data_dir()
    except Exception:
        pass
    if getattr(sys, "frozen", False):
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app:
            return Path(local_app) / "NaughtyOrNot"
    base = Path(__file__).resolve().parent.parent.parent
    try:
        test_dir = base / "logs"
        test_dir.mkdir(parents=True, exist_ok=True)
        test_file = test_dir / ".write_test"
        test_file.touch()
        test_file.unlink()
        return base
    except (OSError, PermissionError):
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app:
            return Path(local_app) / "NaughtyOrNot"
        return base

BASE_DATA_DIR = _get_base_data_dir()
LOGS_DIR = BASE_DATA_DIR / "logs"
DB_PATH = LOGS_DIR / "screening.db"
APP_VERSION = "1.0.2"



def get_db_connection() -> sqlite3.Connection:
    """Get connection to SQLite audit database, initializing tables if needed."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS screening_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            windows_user TEXT,
            machine_name TEXT,
            mode TEXT DEFAULT 'screened',
            search_type TEXT,
            inputs TEXT,
            threshold TEXT,
            source TEXT,
            result TEXT,
            top_match TEXT,
            score REAL,
            list_version TEXT,
            opensanctions_used TEXT,
            report_file_name TEXT,
            app_version TEXT,
            acknowledged INTEGER,
            comment TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS acknowledgement_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            windows_user TEXT,
            machine_name TEXT,
            app_version TEXT
        )
    """)
    # Ensure mode and comment columns exist for backward compatibility
    try:
        cur = conn.cursor()
        cols = [c[1] for c in cur.execute("PRAGMA table_info(screening_logs);").fetchall()]
        if "mode" not in cols:
            conn.execute("ALTER TABLE screening_logs ADD COLUMN mode TEXT DEFAULT 'screened';")
        if "comment" not in cols:
            conn.execute("ALTER TABLE screening_logs ADD COLUMN comment TEXT;")
    except sqlite3.OperationalError as e:
        logger.debug("Schema migration notice for screening_logs: %s", e)

    conn.commit()
    return conn


def log_acknowledgement(
    user: Optional[str] = None,
    app_version: str = APP_VERSION,
) -> None:
    """Log user acceptance of the compliance notice."""
    user = user or getpass.getuser()
    machine = platform.node()
    now_iso = datetime.now(timezone.utc).isoformat()

    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO acknowledgement_logs (timestamp, windows_user, machine_name, app_version)
            VALUES (?, ?, ?, ?)
            """,
            (now_iso, user, machine, app_version),
        )
        conn.commit()
    finally:
        conn.close()


def has_user_acknowledged(
    user: Optional[str] = None,
    app_version: str = APP_VERSION,
) -> bool:
    """Check if the user has acknowledged the notice for the given app version."""
    user = user or getpass.getuser()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*) FROM acknowledgement_logs
            WHERE windows_user = ? AND app_version = ?
            """,
            (user, app_version),
        )
        count = cur.fetchone()[0]
        return count > 0
    finally:
        conn.close()


def log_search(
    search_type: str,
    inputs: Dict[str, Any],
    source_results: List[Dict[str, Any]],
    report_file_name: Optional[str] = None,
    opensanctions_used: bool = False,
    threshold: str = "0.80 / 0.70 / 0.60",
    app_version: str = APP_VERSION,
    acknowledged: bool = True,
) -> None:
    """
    Log one row per source per search into screening_logs.
    """
    user = getpass.getuser()
    machine = platform.node()
    now_iso = datetime.now(timezone.utc).isoformat()
    inputs_json = json.dumps(inputs)
    os_used_str = "Y" if opensanctions_used else "N"
    ack_int = 1 if acknowledged else 0

    conn = get_db_connection()
    try:
        for res in source_results:
            source = res.get("source", "unknown")
            result = res.get("tier", "NO_MATCH")
            top_match = res.get("top_match") or res.get("matched_name") or "—"
            score = float(res.get("score") or 0.0)
            list_version = str(res.get("list_version") or res.get("date") or "current")

            conn.execute(
                """
                INSERT INTO screening_logs (
                    timestamp, windows_user, machine_name, search_type, inputs,
                    threshold, source, result, top_match, score, list_version,
                    opensanctions_used, report_file_name, app_version, acknowledged
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now_iso, user, machine, search_type, inputs_json,
                    threshold, source, result, top_match, score, list_version,
                    os_used_str, report_file_name or "—", app_version, ack_int,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def get_total_opensanctions_credits() -> int:
    """Read total OpenSanctions credits consumed from logs/opensanctions_usage.csv."""
    usage_csv = LOGS_DIR / "opensanctions_usage.csv"
    if not usage_csv.is_file():
        return 0
    try:
        with open(usage_csv, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        # Subtract header line if present
        if lines and "credits" in lines[0].lower():
            return max(0, len(lines) - 1)
        return len(lines)
    except Exception:
        return 0


def log_raw_search(
    query: str,
    options: Dict[str, Any],
    result_count: int,
    user: Optional[str] = None,
    report_file_name: Optional[str] = None,
    app_version: str = APP_VERSION,
) -> None:
    """Log a raw search query with mode='raw'."""
    user = user or getpass.getuser()
    machine = platform.node()
    now_iso = datetime.now(timezone.utc).isoformat()
    inputs_json = json.dumps({"query": query, "options": options})

    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO screening_logs (
                timestamp, windows_user, machine_name, mode, search_type, inputs,
                threshold, source, result, top_match, score, list_version,
                opensanctions_used, report_file_name, app_version, acknowledged
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now_iso, user, machine, "raw", "raw_search", inputs_json,
                "none", "raw_index", f"{result_count} hits", query, float(result_count), "current",
                "N", report_file_name or "—", app_version, 1,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def log_manual_check(
    name: str,
    source: str,
    result: str,
    comment: str = "",
    user: Optional[str] = None,
    report_file_name: Optional[str] = None,
    app_version: str = APP_VERSION,
) -> None:
    """Log a manual check result with mode='manual'."""
    user = user or getpass.getuser()
    machine = platform.node()
    now_iso = datetime.now(timezone.utc).isoformat()
    inputs_json = json.dumps({"name": name, "source": source})

    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO screening_logs (
                timestamp, windows_user, machine_name, mode, search_type, inputs,
                threshold, source, result, top_match, score, list_version,
                opensanctions_used, report_file_name, app_version, acknowledged, comment
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now_iso, user, machine, "manual", "manual_check", inputs_json,
                "none", source, result, name, 0.0, "current",
                "N", report_file_name or "—", app_version, 1, comment,
            ),
        )
        conn.commit()
    finally:
        conn.close()



def get_manual_checks_for_entity(name: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Retrieve historical manual check records matching entity name."""
    if not name or not name.strip():
        return []
    clean_name = name.strip()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT timestamp, windows_user, source, result, comment, report_file_name
            FROM screening_logs
            WHERE mode = 'manual' AND LOWER(top_match) = LOWER(?)
            ORDER BY id DESC
            LIMIT ?
            """,
            (clean_name, limit),
        )
        rows = cur.fetchall()
        return [
            {
                "timestamp": r[0],
                "user": r[1],
                "source": r[2],
                "result": r[3],
                "comment": r[4] or "",
                "report_file_name": r[5] or "—",
            }
            for r in rows
        ]
    finally:
        conn.close()
