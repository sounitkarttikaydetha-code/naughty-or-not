"""
Schema Migration Framework for Clearance Check Canary.
Tracks applied versions in schema_migrations table, supporting both upgrade and downgrade.
"""
import sqlite3
import time
from pathlib import Path
from typing import Callable, Dict, List, Tuple


class Migration:
    def __init__(self, version: int, name: str, up: Callable[[sqlite3.Connection], None], down: Callable[[sqlite3.Connection], None]):
        self.version = version
        self.name = name
        self.up = up
        self.down = down


_MIGRATIONS: List[Migration] = []


def register_migration(version: int, name: str, up: Callable[[sqlite3.Connection], None], down: Callable[[sqlite3.Connection], None]):
    _MIGRATIONS.append(Migration(version, name, up, down))
    _MIGRATIONS.sort(key=lambda m: m.version)


def ensure_migration_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        );
    """)
    conn.commit()


def get_applied_versions(conn: sqlite3.Connection) -> List[int]:
    ensure_migration_table(conn)
    cur = conn.cursor()
    cur.execute("SELECT version FROM schema_migrations ORDER BY version ASC")
    return [row[0] for row in cur.fetchall()]


def migrate_up(conn: sqlite3.Connection) -> List[int]:
    """Apply all pending migrations in order."""
    ensure_migration_table(conn)
    applied = set(get_applied_versions(conn))
    applied_now = []

    for m in _MIGRATIONS:
        if m.version not in applied:
            m.up(conn)
            ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            conn.execute(
                "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                (m.version, m.name, ts),
            )
            conn.commit()
            applied_now.append(m.version)

    return applied_now


def migrate_down(conn: sqlite3.Connection, target_version: int = 0) -> List[int]:
    """Roll back migrations down to target_version."""
    ensure_migration_table(conn)
    applied = get_applied_versions(conn)
    rolled_back = []

    for m in reversed(_MIGRATIONS):
        if m.version in applied and m.version > target_version:
            m.down(conn)
            conn.execute("DELETE FROM schema_migrations WHERE version = ?", (m.version,))
            conn.commit()
            rolled_back.append(m.version)

    return rolled_back
