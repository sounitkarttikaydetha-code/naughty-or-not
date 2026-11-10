"""
Database Migration and Append-Only Storage Tests for Clearance Check Canary.
Validates:
1. Migration UP applies cleanly.
2. Migration DOWN rolls back cleanly.
3. Append-only triggers strictly forbid UPDATE and DELETE operations.
4. Import of v1.2.1 database fixture into v2 Canary schema without loss or mutation of v1 data.
"""
import gc
import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path
import pytest

from canary.adapters.storage.sqlite_repo import SQLiteRepository
from canary.adapters.storage.migrations.runner import migrate_up, migrate_down
from canary.adapters.storage.migrations.import_v1_migration import import_v1_database
import canary.adapters.storage.migrations.m001_initial_canary_schema  # Register migration 001


def test_01_migration_up_and_down():
    """Verify schema migrations up and down execute cleanly."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = Path(tf.name)

    conn = None
    try:
        conn = sqlite3.connect(str(db_path))

        # UP
        applied = migrate_up(conn)
        assert 1 in applied

        # Verify tables created
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [r[0] for r in cur.fetchall()]
        assert "screening_log" in tables
        assert "ownership_checks" in tables
        assert "ownership_audit_log" in tables
        assert "batch_screening_log" in tables
        assert "records" in tables

        # DOWN
        rolled_back = migrate_down(conn, target_version=0)
        assert 1 in rolled_back

        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'schema_migrations'")
        remaining = [r[0] for r in cur.fetchall()]
        assert len(remaining) == 0, f"Tables not cleaned up on downgrade: {remaining}"

    finally:
        if conn:
            conn.close()
        gc.collect()
        if db_path.exists():
            try:
                db_path.unlink()
            except OSError:
                pass


def test_02_append_only_triggers_enforcement():
    """Verify append-only SQLite triggers abort UPDATE and DELETE queries on audit tables."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = Path(tf.name)

    try:
        repo = SQLiteRepository(db_path)

        # 1. Insert valid screening log entry
        log_id = repo.append_screening_log({
            "user_id": "auditor_test",
            "inputs": "Test Query Corp",
            "result": "CLEAR",
            "score": 0.0,
            "duration_ms": 15,
        })
        assert log_id > 0

        # Attempt UPDATE on screening_log -> MUST FAIL
        with pytest.raises((sqlite3.OperationalError, sqlite3.IntegrityError)) as exc_upd:
            with repo.connection() as conn:
                conn.execute("UPDATE screening_log SET result = 'ALTERED' WHERE id = ?", (log_id,))
        assert "append-only" in str(exc_upd.value).lower()

        # Attempt DELETE on screening_log -> MUST FAIL
        with pytest.raises((sqlite3.OperationalError, sqlite3.IntegrityError)) as exc_del:
            with repo.connection() as conn:
                conn.execute("DELETE FROM screening_log WHERE id = ?", (log_id,))
        assert "append-only" in str(exc_del.value).lower()

        # 2. Append ownership audit log entry
        audit_id = repo.append_ownership_audit(
            check_id=1,
            actor_id="compliance1",
            action="APPROVE",
            from_status="PENDING",
            to_status="APPROVED",
            comment="Verified beneficial ownership.",
        )
        assert audit_id > 0

        # Attempt UPDATE on ownership_audit_log -> MUST FAIL
        with pytest.raises((sqlite3.OperationalError, sqlite3.IntegrityError)) as exc_aud_upd:
            with repo.connection() as conn:
                conn.execute("UPDATE ownership_audit_log SET comment = 'Tampered' WHERE id = ?", (audit_id,))
        assert "append-only" in str(exc_aud_upd.value).lower()

        # Attempt DELETE on ownership_audit_log -> MUST FAIL
        with pytest.raises((sqlite3.OperationalError, sqlite3.IntegrityError)) as exc_aud_del:
            with repo.connection() as conn:
                conn.execute("DELETE FROM ownership_audit_log WHERE id = ?", (audit_id,))
        assert "append-only" in str(exc_aud_del.value).lower()

    finally:
        del repo
        gc.collect()
        if db_path.exists():
            try:
                db_path.unlink()
            except OSError:
                pass


def test_03_v1_database_import_without_loss():
    """Verify importing a v1.2.1 database fixture into v2 Canary schema without loss or source alteration."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf_v1:
        v1_path = Path(tf_v1.name)
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf_v2:
        v2_path = Path(tf_v2.name)

    repo_v2 = None
    try:
        # Create mock v1.2.1 schema & records
        conn_v1 = sqlite3.connect(str(v1_path))
        conn_v1.execute("""
            CREATE TABLE screening_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                windows_user TEXT,
                machine_name TEXT,
                search_type TEXT,
                query_type TEXT,
                inputs TEXT,
                result TEXT,
                top_match TEXT,
                score REAL,
                duration_ms INTEGER,
                comment TEXT
            );
        """)
        conn_v1.execute("""
            CREATE TABLE ownership_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_name TEXT,
                timestamp TEXT,
                status TEXT,
                preparer TEXT,
                reviewer TEXT,
                review_due_date TEXT,
                version INTEGER,
                ofac_verdict TEXT,
                undisclosed_pct REAL,
                depends_on_undisclosed INTEGER,
                data_json TEXT
            );
        """)
        conn_v1.execute("""
            CREATE TABLE records (
                source_id TEXT,
                record_id TEXT,
                primary_name TEXT,
                entity_type TEXT,
                payload_json TEXT,
                updated_at TEXT,
                PRIMARY KEY (source_id, record_id)
            );
        """)

        # Insert sample v1 data
        conn_v1.execute("""
            INSERT INTO screening_logs (timestamp, windows_user, machine_name, inputs, result, score, duration_ms)
            VALUES ('2026-10-25T10:00:00Z', 'DOM\\screener1', 'WORKSTATION-01', 'Aeroflot', 'POTENTIAL_MATCH', 0.85, 42);
        """)
        conn_v1.execute("""
            INSERT INTO ownership_checks (target_name, timestamp, status, preparer, reviewer, ofac_verdict)
            VALUES ('Global Energy Ltd', '2026-10-25T11:00:00Z', 'Closed', 'DOM\\analyst1', 'DOM\\compliance1', 'BLOCKED');
        """)
        conn_v1.execute("""
            INSERT INTO records (source_id, record_id, primary_name, entity_type, payload_json, updated_at)
            VALUES ('us_ofac', '18715', 'JOINT STOCK COMPANY SBERBANK', 'organisation', '{"test": 1}', '2026-10-24');
        """)
        conn_v1.commit()
        conn_v1.close()

        # Compute initial hash of v1 database
        hash_before = hashlib.sha256(v1_path.read_bytes()).hexdigest()

        # Initialize v2 repo and import v1 database
        repo_v2 = SQLiteRepository(v2_path)
        with repo_v2.connection() as conn_v2:
            counts = import_v1_database(v1_path, conn_v2)

        # Assert counts imported
        assert counts["screening_logs"] == 1
        assert counts["ownership_checks"] == 1
        assert counts["records"] == 1

        # Verify imported content in v2
        with repo_v2.connection() as conn_v2:
            cur = conn_v2.cursor()
            cur.execute("SELECT * FROM screening_log WHERE inputs = 'Aeroflot'")
            row = cur.fetchone()
            assert row is not None
            assert row["user_id"] == "DOM\\screener1"
            assert row["auth_provider"] == "windows_fallback"
            assert row["result"] == "POTENTIAL_MATCH"

            cur.execute("SELECT * FROM ownership_checks WHERE target_name = 'Global Energy Ltd'")
            oc_row = cur.fetchone()
            assert oc_row is not None
            assert oc_row["ofac_verdict"] == "BLOCKED"

            cur.execute("SELECT * FROM records WHERE source_id = 'us_ofac' AND record_id = '18715'")
            rec_row = cur.fetchone()
            assert rec_row is not None
            assert "SBERBANK" in rec_row["primary_name"]

        # Assert v1 source file was NOT mutated (100% read-only integrity)
        hash_after = hashlib.sha256(v1_path.read_bytes()).hexdigest()
        assert hash_before == hash_after, "v1 database was modified during import! Violation of read-only contract."

    finally:
        del repo_v2
        gc.collect()
        if v1_path.exists():
            try:
                v1_path.unlink()
            except OSError:
                pass
        if v2_path.exists():
            try:
                v2_path.unlink()
            except OSError:
                pass
