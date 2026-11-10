"""
Repository Port (Abstract Interface) for Clearance Check Canary.
Follows Clean Architecture: defines storage contracts without coupling to SQLite or PostgreSQL.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class RepositoryPort(ABC):
    """Abstract data repository interface."""

    # Append-only screening logs
    @abstractmethod
    def append_screening_log(self, entry: Dict[str, Any]) -> int:
        """Insert a new screening log record. Append-only: updates/deletes forbidden."""
        pass

    @abstractmethod
    def list_screening_logs(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """List screening logs in descending chronological order."""
        pass

    # Ownership checks and audit trail
    @abstractmethod
    def create_ownership_check(self, data: Dict[str, Any]) -> int:
        """Create new ownership check structure."""
        pass

    @abstractmethod
    def get_ownership_check(self, check_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve ownership check by ID."""
        pass

    @abstractmethod
    def update_ownership_status(
        self,
        check_id: int,
        status: str,
        actor_id: str,
        role: str,
        comment: Optional[str] = None,
    ) -> None:
        """Transition ownership check status with mandatory four-eyes validation."""
        pass

    @abstractmethod
    def append_ownership_audit(
        self,
        check_id: int,
        actor_id: str,
        action: str,
        from_status: str,
        to_status: str,
        comment: Optional[str] = None,
    ) -> int:
        """Append-only audit record for ownership actions."""
        pass

    # Batch screening
    @abstractmethod
    def create_batch_job(self, batch_id: str, user_id: str, total_items: int) -> None:
        """Record batch job submission. Append-only."""
        pass

    @abstractmethod
    def get_batch_job(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve batch job status and results."""
        pass

    @abstractmethod
    def update_batch_job_progress(
        self,
        batch_id: str,
        processed_items: int,
        status: str,
        results_json: Optional[str] = None,
    ) -> None:
        """Update batch progress."""
        pass

    # Full entity records
    @abstractmethod
    def get_record(self, source_id: str, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve structured 13-section record."""
        pass

    @abstractmethod
    def save_record(
        self,
        source_id: str,
        record_id: str,
        primary_name: str,
        entity_type: str,
        payload_json: str,
    ) -> None:
        """Upsert entity record."""
        pass
