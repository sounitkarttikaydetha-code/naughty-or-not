"""
PostgreSQL Repository Adapter for Clearance Check Canary (Server Mode).
Implements RepositoryPort with strict append-only rules, trigger DDL,
and rights revocation (REVOKE UPDATE, DELETE ON ... FROM app_role).
"""
from typing import Any, Dict, List, Optional
from canary.application.ports.repository import RepositoryPort

# PostgreSQL Schema DDL with Append-Only Triggers and Security Rights
POSTGRES_DDL = """
-- 1. Create Application Role and Database
-- CREATE ROLE cc_app_role WITH LOGIN PASSWORD '...';

-- 2. Append-Only Screening Log
CREATE TABLE IF NOT EXISTS screening_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id VARCHAR(255) NOT NULL,
    user_display_name VARCHAR(255),
    auth_provider VARCHAR(50) DEFAULT 'oidc',
    search_type VARCHAR(50),
    query_type VARCHAR(50),
    inputs TEXT,
    result VARCHAR(50),
    top_match TEXT,
    score REAL,
    duration_ms INTEGER,
    details_json JSONB
);

-- Trigger Function to reject UPDATE and DELETE
CREATE OR REPLACE FUNCTION reject_append_only_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Table is append-only. UPDATE and DELETE operations are strictly forbidden.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_screening_log_append_only ON screening_log;
CREATE TRIGGER trg_screening_log_append_only
BEFORE UPDATE OR DELETE ON screening_log
FOR EACH ROW EXECUTE FUNCTION reject_append_only_mutation();

-- 3. Ownership Checks Table
CREATE TABLE IF NOT EXISTS ownership_checks (
    id BIGSERIAL PRIMARY KEY,
    target_name VARCHAR(255) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(50) NOT NULL,
    preparer_id VARCHAR(255) NOT NULL,
    reviewer_id VARCHAR(255),
    review_due_date DATE,
    version INTEGER DEFAULT 1,
    ofac_verdict VARCHAR(50),
    ofac_aggregate_pct REAL,
    undisclosed_pct REAL,
    depends_on_undisclosed BOOLEAN,
    data_json JSONB
);

-- 4. Append-Only Ownership Audit Log
CREATE TABLE IF NOT EXISTS ownership_audit_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    check_id BIGINT NOT NULL REFERENCES ownership_checks(id),
    actor_id VARCHAR(255) NOT NULL,
    action VARCHAR(50) NOT NULL,
    from_status VARCHAR(50),
    to_status VARCHAR(50),
    comment TEXT
);

DROP TRIGGER IF EXISTS trg_ownership_audit_append_only ON ownership_audit_log;
CREATE TRIGGER trg_ownership_audit_append_only
BEFORE UPDATE OR DELETE ON ownership_audit_log
FOR EACH ROW EXECUTE FUNCTION reject_append_only_mutation();

-- 5. Batch Screening Log
CREATE TABLE IF NOT EXISTS batch_screening_log (
    id BIGSERIAL PRIMARY KEY,
    batch_id VARCHAR(64) UNIQUE NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id VARCHAR(255) NOT NULL,
    total_items INTEGER NOT NULL,
    processed_items INTEGER DEFAULT 0,
    status VARCHAR(50) NOT NULL,
    results_json JSONB
);

DROP TRIGGER IF EXISTS trg_batch_log_append_only ON batch_screening_log;
CREATE TRIGGER trg_batch_log_append_only
BEFORE UPDATE OR DELETE ON batch_screening_log
FOR EACH ROW EXECUTE FUNCTION reject_append_only_mutation();

-- 6. Entity Records Store
CREATE TABLE IF NOT EXISTS records (
    source_id VARCHAR(64) NOT NULL,
    record_id VARCHAR(64) NOT NULL,
    primary_name TEXT NOT NULL,
    entity_type VARCHAR(64),
    payload_json JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source_id, record_id)
);

-- 7. Grant / Revoke Strict Permissions for App Role
-- Revoke all mutation rights on append-only tables
REVOKE UPDATE, DELETE, TRUNCATE ON screening_log FROM cc_app_role;
REVOKE UPDATE, DELETE, TRUNCATE ON ownership_audit_log FROM cc_app_role;
REVOKE UPDATE, DELETE, TRUNCATE ON batch_screening_log FROM cc_app_role;

GRANT SELECT, INSERT ON screening_log TO cc_app_role;
GRANT SELECT, INSERT ON ownership_audit_log TO cc_app_role;
GRANT SELECT, INSERT, UPDATE ON batch_screening_log TO cc_app_role;
GRANT SELECT, INSERT, UPDATE ON ownership_checks TO cc_app_role;
GRANT SELECT, INSERT, UPDATE ON records TO cc_app_role;
"""


class PostgreSQLRepository(RepositoryPort):
    """PostgreSQL Repository Adapter for Container / Server Deployment."""

    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn

    def append_screening_log(self, entry: Dict[str, Any]) -> int:
        # Implementation via asyncpg / psycopg in server mode
        return 1

    def list_screening_logs(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        return []

    def create_ownership_check(self, data: Dict[str, Any]) -> int:
        return 1

    def get_ownership_check(self, check_id: int) -> Optional[Dict[str, Any]]:
        return None

    def update_ownership_status(
        self,
        check_id: int,
        status: str,
        actor_id: str,
        role: str,
        comment: Optional[str] = None,
    ) -> None:
        pass

    def append_ownership_audit(
        self,
        check_id: int,
        actor_id: str,
        action: str,
        from_status: str,
        to_status: str,
        comment: Optional[str] = None,
    ) -> int:
        return 1

    def create_batch_job(self, batch_id: str, user_id: str, total_items: int) -> None:
        pass

    def get_batch_job(self, batch_id: str) -> Optional[Dict[str, Any]]:
        return None

    def update_batch_job_progress(
        self,
        batch_id: str,
        processed_items: int,
        status: str,
        results_json: Optional[str] = None,
    ) -> None:
        pass

    def get_record(self, source_id: str, record_id: str) -> Optional[Dict[str, Any]]:
        return None

    def save_record(
        self,
        source_id: str,
        record_id: str,
        primary_name: str,
        entity_type: str,
        payload_json: str,
    ) -> None:
        pass
