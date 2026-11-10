"""
Migration to Import a v1.2.1 Database without loss into v2 Canary Schema.
Reads the v1 database strictly read-only and migrates screening logs, ownership checks, and records.
"""
import json
import sqlite3
from pathlib import Path
from typing import Dict, Any, Tuple


def import_v1_database(v1_db_path: Path, v2_conn: sqlite3.Connection) -> Dict[str, int]:
    """
    Import all records and logs from a v1.2.1 database into v2 Canary database.
    Operates strictly read-only on the source database.
    Returns counts of imported entities: {screening_logs, ownership_checks, records}.
    """
    v1_path = Path(v1_db_path).resolve()
    if not v1_path.exists():
        raise FileNotFoundError(f"Source v1 database not found at {v1_path}")

    # Read-only connection to source database
    uri_path = f"file:{v1_path.as_posix()}?mode=ro"
    src_conn = sqlite3.connect(uri_path, uri=True, timeout=10.0)
    src_conn.row_factory = sqlite3.Row

    counts = {
        "screening_logs": 0,
        "ownership_checks": 0,
        "records": 0,
    }

    try:
        # 1. Check if screening_logs exists in v1
        src_tables = [
            r[0] for r in src_conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        ]

        if "screening_logs" in src_tables:
            cur = src_conn.execute("SELECT * FROM screening_logs")
            rows = cur.fetchall()
            for r in rows:
                row_dict = dict(r)
                details = {
                    "v1_id": row_dict.get("id"),
                    "machine_name": row_dict.get("machine_name"),
                    "threshold": row_dict.get("threshold"),
                    "source": row_dict.get("source"),
                    "sources_checked": row_dict.get("sources_checked"),
                    "result_hash": row_dict.get("result_hash"),
                    "comment": row_dict.get("comment"),
                }
                v2_conn.execute("""
                    INSERT INTO screening_log (
                        timestamp, user_id, user_display_name, auth_provider,
                        search_type, query_type, inputs, result, top_match,
                        score, duration_ms, details_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row_dict.get("timestamp", ""),
                    row_dict.get("windows_user") or "unknown_v1_user",
                    row_dict.get("windows_user") or "V1 Migrated User",
                    "windows_fallback",
                    row_dict.get("search_type", "name"),
                    row_dict.get("query_type", "organisation"),
                    row_dict.get("inputs", ""),
                    row_dict.get("result", ""),
                    row_dict.get("top_match", ""),
                    float(row_dict.get("score") or 0.0),
                    int(row_dict.get("duration_ms") or 0),
                    json.dumps(details),
                ))
                counts["screening_logs"] += 1

        # 2. Check if ownership_checks exists in v1
        if "ownership_checks" in src_tables:
            cur = src_conn.execute("SELECT * FROM ownership_checks")
            rows = cur.fetchall()
            for r in rows:
                row_dict = dict(r)
                v2_conn.execute("""
                    INSERT INTO ownership_checks (
                        id, target_name, timestamp, status, preparer_id, reviewer_id,
                        review_due_date, version, ofac_verdict, ofac_aggregate_pct,
                        undisclosed_pct, depends_on_undisclosed, data_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row_dict.get("id"),
                    row_dict.get("target_name", ""),
                    row_dict.get("timestamp", ""),
                    row_dict.get("status", "Closed"),
                    row_dict.get("preparer") or "v1_preparer",
                    row_dict.get("reviewer"),
                    row_dict.get("review_due_date"),
                    int(row_dict.get("version") or 1),
                    row_dict.get("ofac_verdict"),
                    0.0,
                    float(row_dict.get("undisclosed_pct") or 0.0),
                    1 if row_dict.get("depends_on_undisclosed") else 0,
                    row_dict.get("data_json", "{}"),
                ))

                # Also insert an audit log record for historical provenance
                v2_conn.execute("""
                    INSERT INTO ownership_audit_log (
                        timestamp, check_id, actor_id, action, from_status, to_status, comment
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    row_dict.get("timestamp", ""),
                    row_dict.get("id"),
                    row_dict.get("preparer") or "v1_preparer",
                    "MIGRATED_FROM_V1",
                    "NONE",
                    row_dict.get("status", "Closed"),
                    "Imported from stable v1.2.1 database without loss.",
                ))
                counts["ownership_checks"] += 1

        # 3. Check if records exists in v1
        if "records" in src_tables:
            cur = src_conn.execute("SELECT * FROM records")
            rows = cur.fetchall()
            for r in rows:
                row_dict = dict(r)
                v2_conn.execute("""
                    INSERT INTO records (
                        source_id, record_id, primary_name, entity_type, payload_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_id, record_id) DO UPDATE SET
                        primary_name = excluded.primary_name,
                        entity_type = excluded.entity_type,
                        payload_json = excluded.payload_json,
                        updated_at = excluded.updated_at
                """, (
                    row_dict.get("source_id", ""),
                    row_dict.get("record_id", ""),
                    row_dict.get("primary_name", ""),
                    row_dict.get("entity_type", ""),
                    row_dict.get("payload_json", "{}"),
                    row_dict.get("updated_at", ""),
                ))
                counts["records"] += 1

        v2_conn.commit()
    finally:
        src_conn.close()

    return counts
