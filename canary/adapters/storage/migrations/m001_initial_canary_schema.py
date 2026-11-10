"""
Migration 001: Initial Clearance Check Canary Schema.
Sets up tables and append-only triggers.
"""
import sqlite3
from canary.adapters.storage.migrations.runner import register_migration


def up_001(conn: sqlite3.Connection) -> None:
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
    conn.commit()


def down_001(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TRIGGER IF EXISTS trg_prevent_update_screening_log")
    conn.execute("DROP TRIGGER IF EXISTS trg_prevent_delete_screening_log")
    conn.execute("DROP TRIGGER IF EXISTS trg_prevent_update_ownership_audit")
    conn.execute("DROP TRIGGER IF EXISTS trg_prevent_delete_ownership_audit")
    conn.execute("DROP TABLE IF EXISTS screening_log")
    conn.execute("DROP TABLE IF EXISTS ownership_checks")
    conn.execute("DROP TABLE IF EXISTS ownership_audit_log")
    conn.execute("DROP TABLE IF EXISTS batch_screening_log")
    conn.execute("DROP TABLE IF EXISTS records")
    conn.commit()


register_migration(1, "001_initial_canary_schema", up_001, down_001)
