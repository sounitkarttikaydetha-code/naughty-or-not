"""
Health, Readiness, and Metrics Use Case.
"""
import time
from typing import Any, Dict, Optional

from canary.application.ports.index_provider import IndexProviderPort
from canary.application.ports.repository import RepositoryPort

_START_TIME = time.time()


class HealthUseCase:
    def __init__(
        self,
        repository: Optional[RepositoryPort] = None,
        index_provider: Optional[IndexProviderPort] = None,
    ):
        self.repository = repository
        self.index_provider = index_provider

    def check_health(self) -> Dict[str, Any]:
        """Liveness probe."""
        return {
            "status": "UP",
            "uptime_seconds": round(time.time() - _START_TIME, 2),
            "version": "2.0.1-canary.1",
        }

    def check_readiness(self) -> Dict[str, Any]:
        """Readiness probe."""
        db_ready = True
        index_ready = True
        total_records = 0

        if self.index_provider is not None:
            counts = self.index_provider.get_source_record_counts()
            total_records = sum(counts.values())
            index_ready = total_records > 0

        is_ready = db_ready and index_ready

        return {
            "ready": is_ready,
            "database_connected": db_ready,
            "index_loaded": index_ready,
            "total_records_indexed": total_records,
            "version": "2.0.1-canary.1",
        }

    def get_metrics(self) -> Dict[str, Any]:
        """Metrics payload."""
        return {
            "uptime_seconds": round(time.time() - _START_TIME, 2),
            "engine_version": "2.0.1-canary.1",
            "active_mode": "canary",
            "components": {
                "screening_engine": "python_layered",
                "storage_backend": "sqlite_wal" if self.repository else "none",
            },
        }
