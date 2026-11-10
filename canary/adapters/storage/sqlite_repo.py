"""
SQLite Repository Adapter for Clearance Check Canary (Desktop Canary Mode).
Implements RepositoryPort with WAL mode, parameterized queries (Bandit B608 compliant),
and strict append-only SQLite triggers on audit tables.
"""
from contextlib import contextmanager
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Generator

from canary.application.ports.repository import RepositoryPort


class SQLiteRepository(RepositoryPort):
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=10000;")
        except Exception:
            pass
        return conn

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize schema and append-only database triggers."""
        with self.connection() as conn:
            # 1. Append-only screening log table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS screening_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    user_display_name TEXT,
                    auth_provider TEXT DEFAULT 'oidc',
                    search_type TEXT,
                    query_type TEXT,
                    inputs TEXT,
                    result TEXT,
                    top_match TEXT,
                    score REAL,
                    duration_ms INTEGER,
                    details_json TEXT
                );
            """)

            # Enforce append-only on screening_log via triggers
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS trg_prevent_update_screening_log
                BEFORE UPDATE ON screening_log
                BEGIN
                    SELECT RAISE(ABORT, 'Table screening_log is append-only. Updates are strictly forbidden.');
                END;
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_screening_log
                BEFORE DELETE ON screening_log
                BEGIN
                    SELECT RAISE(ABORT, 'Table screening_log is append-only. Deletions are strictly forbidden.');
                END;
            """)

            # 2. Ownership checks table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ownership_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_name TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL,
                    preparer_id TEXT NOT NULL,
                    reviewer_id TEXT,
                    review_due_date TEXT,
                    version INTEGER DEFAULT 1,
                    ofac_verdict TEXT,
                    ofac_aggregate_pct REAL,
                    undisclosed_pct REAL,
                    depends_on_undisclosed INTEGER,
                    data_json TEXT
                );
            """)

            # 3. Append-only ownership audit trail
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ownership_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    check_id INTEGER NOT NULL,
                    actor_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    from_status TEXT,
                    to_status TEXT,
                    comment TEXT
                );
            """)

            # Enforce append-only on ownership_audit_log via triggers
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS trg_prevent_update_ownership_audit
                BEFORE UPDATE ON ownership_audit_log
                BEGIN
                    SELECT RAISE(ABORT, 'Table ownership_audit_log is append-only. Updates are strictly forbidden.');
                END;
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_ownership_audit
                BEFORE DELETE ON ownership_audit_log
                BEGIN
                    SELECT RAISE(ABORT, 'Table ownership_audit_log is append-only. Deletions are strictly forbidden.');
                END;
            """)

            # 4. Batch screening jobs
            conn.execute("""
                CREATE TABLE IF NOT EXISTS batch_screening_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id TEXT UNIQUE NOT NULL,
                    timestamp TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    total_items INTEGER NOT NULL,
                    processed_items INTEGER DEFAULT 0,
                    status TEXT NOT NULL,
                    results_json TEXT
                );
            """)

            # 5. Full entity records store
            conn.execute("""
                CREATE TABLE IF NOT EXISTS records (
                    source_id TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    primary_name TEXT NOT NULL,
                    entity_type TEXT,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (source_id, record_id)
                );
            """)

    # Append-only screening log
    def append_screening_log(self, entry: Dict[str, Any]) -> int:
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        det_json = json.dumps(entry.get("details_json", {})) if isinstance(entry.get("details_json"), dict) else str(entry.get("details_json", ""))
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO screening_log (
                    timestamp, user_id, user_display_name, auth_provider,
                    search_type, query_type, inputs, result, top_match,
                    score, duration_ms, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ts,
                entry.get("user_id", "unknown"),
                entry.get("user_display_name", ""),
                entry.get("auth_provider", "oidc"),
                entry.get("search_type", "name"),
                entry.get("query_type", "organisation"),
                entry.get("inputs", ""),
                entry.get("result", ""),
                entry.get("top_match", ""),
                float(entry.get("score", 0.0)),
                int(entry.get("duration_ms", 0)),
                det_json,
            ))
            return cur.lastrowid

    def list_screening_logs(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM screening_log ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))
            return [dict(row) for row in cur.fetchall()]

    # Ownership checks and audit
    def create_ownership_check(self, data: Dict[str, Any]) -> int:
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        data_json = json.dumps(data)
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO ownership_checks (
                    target_name, timestamp, status, preparer_id, reviewer_id,
                    review_due_date, version, ofac_verdict, ofac_aggregate_pct,
                    undisclosed_pct, depends_on_undisclosed, data_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data["target_name"],
                ts,
                data.get("status", "DRAFT"),
                data["preparer_id"],
                data.get("reviewer_id"),
                data.get("review_due_date"),
                int(data.get("version", 1)),
                data.get("ofac_verdict", "CLEAR"),
                float(data.get("ofac_aggregate_pct", 0.0)),
                float(data.get("undisclosed_pct", 0.0)),
                1 if data.get("depends_on_undisclosed") else 0,
                data_json,
            ))
            return cur.lastrowid

    def get_ownership_check(self, check_id: int) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM ownership_checks WHERE id = ?", (check_id,))
            row = cur.fetchone()
            if not row:
                return None
            res = dict(row)
            try:
                res["data"] = json.loads(res.get("data_json", "{}"))
            except Exception:
                res["data"] = {}
            return res

    def update_ownership_status(
        self,
        check_id: int,
        status: str,
        actor_id: str,
        role: str,
        comment: Optional[str] = None,
    ) -> None:
        with self.connection() as conn:
            cur = conn.cursor()
            if role == "Reviewer":
                cur.execute("""
                    UPDATE ownership_checks
                    SET status = ?, reviewer_id = ?
                    WHERE id = ?
                """, (status, actor_id, check_id))
            else:
                cur.execute("""
                    UPDATE ownership_checks
                    SET status = ?
                    WHERE id = ?
                """, (status, check_id))

    def append_ownership_audit(
        self,
        check_id: int,
        actor_id: str,
        action: str,
        from_status: str,
        to_status: str,
        comment: Optional[str] = None,
    ) -> int:
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO ownership_audit_log (
                    timestamp, check_id, actor_id, action, from_status, to_status, comment
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (ts, check_id, actor_id, action, from_status, to_status, comment or ""))
            return cur.lastrowid

    # Batch screening
    def create_batch_job(self, batch_id: str, user_id: str, total_items: int) -> None:
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self.connection() as conn:
            conn.execute("""
                INSERT INTO batch_screening_log (
                    batch_id, timestamp, user_id, total_items, processed_items, status, results_json
                ) VALUES (?, ?, ?, ?, 0, 'ACCEPTED', '[]')
            """, (batch_id, ts, user_id, total_items))

    def get_batch_job(self, batch_id: str) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM batch_screening_log WHERE batch_id = ?", (batch_id,))
            row = cur.fetchone()
            if not row:
                return None
            res = dict(row)
            try:
                res["results"] = json.loads(res.get("results_json", "[]"))
            except Exception:
                res["results"] = []
            return res

    def update_batch_job_progress(
        self,
        batch_id: str,
        processed_items: int,
        status: str,
        results_json: Optional[str] = None,
    ) -> None:
        with self.connection() as conn:
            if results_json:
                conn.execute("""
                    UPDATE batch_screening_log
                    SET processed_items = ?, status = ?, results_json = ?
                    WHERE batch_id = ?
                """, (processed_items, status, results_json, batch_id))
            else:
                conn.execute("""
                    UPDATE batch_screening_log
                    SET processed_items = ?, status = ?
                    WHERE batch_id = ?
                """, (processed_items, status, batch_id))

    # Full records
    def get_record(self, source_id: str, record_id: str) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM records WHERE source_id = ? AND record_id = ?", (source_id, record_id))
            row = cur.fetchone()
            if not row:
                return None
            res = dict(row)
            try:
                res["payload"] = json.loads(res.get("payload_json", "{}"))
            except Exception:
                res["payload"] = {}
            return res

    def save_record(
        self,
        source_id: str,
        record_id: str,
        primary_name: str,
        entity_type: str,
        payload_json: str,
    ) -> None:
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self.connection() as conn:
            conn.execute("""
                INSERT INTO records (source_id, record_id, primary_name, entity_type, payload_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, record_id) DO UPDATE SET
                    primary_name = excluded.primary_name,
                    entity_type = excluded.entity_type,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
            """, (source_id, record_id, primary_name, entity_type, payload_json, ts))
