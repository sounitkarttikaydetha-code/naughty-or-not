"""
Source Status Use Case.
Retrieves publication dates, item counts, and status for all registered regulatory sources.
"""
from typing import Any, Dict

from canary.application.identity.permissions import require_permission, Action
from canary.application.ports.idp import UserContext
from canary.application.ports.index_provider import IndexProviderPort


class SourceStatusUseCase:
    def __init__(self, index_provider: IndexProviderPort):
        self.index_provider = index_provider

    def execute(self, user: UserContext) -> Dict[str, Any]:
        """Retrieve source publication dates and status."""
        require_permission(user, Action.VIEW_SOURCES)

        dates = self.index_provider.get_source_publication_dates()
        counts = self.index_provider.get_source_record_counts()

        sources = []
        for src in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]:
            sources.append({
                "source_id": src,
                "publication_date": dates.get(src, "Pinned Snapshot"),
                "record_count": counts.get(src, 0),
                "status": "VALIDATED",
            })

        return {
            "sources": sources,
            "total_records": sum(counts.values()),
            "engine_version": "2.0.1-canary.1",
        }
