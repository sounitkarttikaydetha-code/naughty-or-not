"""
SQLite Audit Logger for Sanction checK (T5/T8-8).
Maintains an append-only audit trail at logs/screening.db per SPEC.md Section 4.3 and T8-8.
"""

import csv
import getpass
import hashlib
import json
import logging
import os
import platform
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
APP_VERSION = "1.0.3"


def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Get connection to SQLite audit database, initializing tables if needed."""
    target_path = db_path or DB_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS screening_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            windows_user TEXT,
            machine_name TEXT,
            mode TEXT DEFAULT 'screened',
            search_type TEXT,
            query_type TEXT,
            inputs TEXT,
            threshold TEXT,
            source TEXT,
            sources_checked TEXT,
            result TEXT,
            top_match TEXT,
            score REAL,
            duration_ms INTEGER,
            result_hash TEXT,
            candidate_count INTEGER DEFAULT 0,
            red_count INTEGER DEFAULT 0,
            orange_count INTEGER DEFAULT 0,
            info_count INTEGER DEFAULT 0,
            list_version TEXT,
            opensanctions_used TEXT,
            report_file_name TEXT,
            app_version TEXT,
            acknowledged INTEGER,
            comment TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS screening_hits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_id INTEGER,
            source TEXT,
            source_id TEXT,
            tier TEXT,
            score REAL,
            matched_name TEXT,
            primary_name TEXT,
            reason_code TEXT,
            is_top_hit INTEGER DEFAULT 0,
            FOREIGN KEY(log_id) REFERENCES screening_logs(id)
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

    # Schema migration to add any missing columns in screening_logs on older databases
    try:
        cur = conn.cursor()
        cols = {c[1] for c in cur.execute("PRAGMA table_info(screening_logs);").fetchall()}
        col_defs = {
            "mode": "TEXT DEFAULT 'screened'",
            "comment": "TEXT",
            "query_type": "TEXT",
            "sources_checked": "TEXT",
            "duration_ms": "INTEGER",
            "result_hash": "TEXT",
            "candidate_count": "INTEGER DEFAULT 0",
            "red_count": "INTEGER DEFAULT 0",
            "orange_count": "INTEGER DEFAULT 0",
            "info_count": "INTEGER DEFAULT 0",
        }
        for col_name, col_type in col_defs.items():
            if col_name not in cols:
                conn.execute(f"ALTER TABLE screening_logs ADD COLUMN {col_name} {col_type};")
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
    query_type: Optional[str] = None,
    sources_checked: Optional[List[str]] = None,
    duration_ms: Optional[int] = None,
    all_candidates: Optional[List[Dict[str, Any]]] = None,
    result_hash: Optional[str] = None,
    overall_tier: Optional[str] = None,
    top_match: Optional[str] = None,
    top_score: Optional[float] = None,
    db_conn: Optional[sqlite3.Connection] = None,
) -> int:
    """
    Log screening search into screening_logs and record all candidates into screening_hits.
    Returns the inserted log_id.
    """
    user = getpass.getuser()
    machine = platform.node()
    now_iso = datetime.now(timezone.utc).isoformat()
    inputs_json = json.dumps(inputs)
    os_used_str = "Y" if opensanctions_used else "N"
    ack_int = 1 if acknowledged else 0

    candidates = all_candidates or []
    red_count = sum(1 for c in candidates if c.get("tier") in ("POTENTIAL_MATCH", "RED"))
    orange_count = sum(1 for c in candidates if c.get("tier") in ("POSSIBLE_MATCH_REVIEW", "ORANGE"))
    info_count = sum(1 for c in candidates if c.get("tier") in ("BELOW_THRESHOLD", "INFO"))
    candidate_count = red_count + orange_count + info_count

    # If no separate candidates passed, fall back to counts from source_results
    if not candidates and source_results:
        red_count = sum(1 for r in source_results if r.get("tier") == "POTENTIAL_MATCH")
        orange_count = sum(1 for r in source_results if r.get("tier") == "POSSIBLE_MATCH_REVIEW")
        info_count = sum(r.get("below_count", 0) for r in source_results)
        candidate_count = red_count + orange_count + info_count

    q_type = query_type or search_type.lower()
    sources_list = sources_checked or [
        r.get("id") or r.get("source") for r in source_results if r.get("id") or r.get("source")
    ]
    sources_checked_json = json.dumps(sources_list)

    # Resolve overall finding, top match name, and score
    if not overall_tier:
        if red_count > 0:
            overall_tier = "POTENTIAL_MATCH"
        elif orange_count > 0:
            overall_tier = "POSSIBLE_MATCH_REVIEW"
        else:
            overall_tier = "NO_MATCH"

    if top_score is None:
        top_score = max([float(c.get("score") or 0.0) for c in candidates], default=0.0)

    if not top_match:
        if candidates:
            top_match = candidates[0].get("matched_name") or candidates[0].get("primary_name") or "—"
        elif source_results:
            top_match = source_results[0].get("top_match") or source_results[0].get("matched_name") or "—"
        else:
            top_match = "—"

    if not result_hash:
        raw_hash_data = f"{now_iso}|{q_type}|{inputs_json}|{candidate_count}|{overall_tier}|{top_score:.4f}"
        result_hash = hashlib.sha256(raw_hash_data.encode("utf-8")).hexdigest()[:16]

    close_after = False
    conn = db_conn
    if conn is None:
        conn = get_db_connection()
        close_after = True

    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO screening_logs (
                timestamp, windows_user, machine_name, mode, search_type, query_type, inputs,
                threshold, source, sources_checked, result, top_match, score, duration_ms,
                result_hash, candidate_count, red_count, orange_count, info_count,
                list_version, opensanctions_used, report_file_name, app_version, acknowledged
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now_iso, user, machine, "screened", search_type, q_type, inputs_json,
                threshold, "all_sources", sources_checked_json, overall_tier, top_match, float(top_score),
                duration_ms, result_hash, candidate_count, red_count, orange_count, info_count,
                "current", os_used_str, report_file_name or "—", app_version, ack_int,
            ),
        )
        log_id = cur.lastrowid

        # Insert every candidate into screening_hits
        for c in candidates:
            conn.execute(
                """
                INSERT INTO screening_hits (
                    log_id, source, source_id, tier, score, matched_name, primary_name, reason_code, is_top_hit
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log_id,
                    c.get("source_list") or c.get("source") or "unknown",
                    str(c.get("source_id") or "—"),
                    c.get("tier") or "BELOW_THRESHOLD",
                    float(c.get("score") or 0.0),
                    c.get("matched_name") or "—",
                    c.get("primary_name") or "—",
                    c.get("reason") or c.get("reason_code") or "score",
                    1 if c.get("is_top_hit") else 0,
                ),
            )

        conn.commit()
        return log_id
    finally:
        if close_after:
            conn.close()


def get_total_opensanctions_credits() -> int:
    """Read total OpenSanctions credits consumed from logs/opensanctions_usage.csv."""
    usage_csv = LOGS_DIR / "opensanctions_usage.csv"
    if not usage_csv.is_file():
        return 0
    try:
        with open(usage_csv, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
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
                timestamp, windows_user, machine_name, mode, search_type, query_type, inputs,
                threshold, source, sources_checked, result, top_match, score, duration_ms,
                result_hash, candidate_count, red_count, orange_count, info_count,
                list_version, opensanctions_used, report_file_name, app_version, acknowledged
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now_iso, user, machine, "raw", "raw_search", "text", inputs_json,
                "none", "raw_index", json.dumps(["raw_index"]), f"{result_count} hits", query, float(result_count),
                0, "raw", result_count, 0, 0, result_count,
                "current", "N", report_file_name or "—", app_version, 1,
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
                timestamp, windows_user, machine_name, mode, search_type, query_type, inputs,
                threshold, source, sources_checked, result, top_match, score, duration_ms,
                result_hash, candidate_count, red_count, orange_count, info_count,
                list_version, opensanctions_used, report_file_name, app_version, acknowledged, comment
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now_iso, user, machine, "manual", "manual_check", "manual", inputs_json,
                "none", source, json.dumps([source]), result, name, 0.0, 0,
                "manual", 1, 0, 0, 0,
                "current", "N", report_file_name or "—", app_version, 1, comment,
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


def export_screening_logs_to_csv(
    output_path: Optional[Path] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> Path:
    """Export screening_logs table to CSV format."""
    out_file = output_path or (LOGS_DIR / "screening_logs.csv")
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM screening_logs ORDER BY id ASC")
        rows = cur.fetchall()
        headers = [d[0] for d in cur.description]
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        return out_file
    finally:
        if close_conn:
            conn.close()


def export_screening_hits_to_csv(
    output_path: Optional[Path] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> Path:
    """Export screening_hits table to CSV format."""
    out_file = output_path or (LOGS_DIR / "screening_hits.csv")
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM screening_hits ORDER BY id ASC")
        rows = cur.fetchall()
        headers = [d[0] for d in cur.description]
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        return out_file
    finally:
        if close_conn:
            conn.close()
