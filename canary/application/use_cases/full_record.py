"""
Full Record Lookup Use Case.
Retrieves full entity record formatted across the 13 standard sections.
"""
from typing import Any, Dict, Optional

from canary.application.identity.permissions import require_permission, Action
from canary.application.ports.idp import UserContext
from canary.application.ports.index_provider import IndexProviderPort
from canary.application.ports.repository import RepositoryPort


class FullRecordUseCase:
    def __init__(
        self,
        repository: RepositoryPort,
        index_provider: Optional[IndexProviderPort] = None,
    ):
        self.repository = repository
        self.index_provider = index_provider

    def execute(
        self,
        source_id: str,
        record_id: str,
        user: UserContext,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve full record by source and record ID."""
        require_permission(user, Action.VIEW_RECORDS)

        # 1. Check local structured record store
        record = self.repository.get_record(source_id=source_id, record_id=record_id)
        if record:
            return record

        # 2. Check index provider if available
        if self.index_provider is not None:
            raw = self.index_provider.get_raw_record(source_id=source_id, record_id=record_id)
            if raw:
                return {
                    "source_id": source_id,
                    "record_id": record_id,
                    "primary_name": raw.get("name") or raw.get("primary_name") or "—",
                    "entity_type": raw.get("entityType") or "entity",
                    "payload": raw,
                }

        return None
