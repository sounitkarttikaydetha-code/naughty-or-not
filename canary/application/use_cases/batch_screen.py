"""
Batch Screen Use Case.
Accepts batch screening submissions (202 Accepted) and processes items.
"""
import json
import time
import uuid
from typing import Any, Dict, List, Optional

from canary.application.identity.permissions import require_permission, Action
from canary.application.ports.idp import UserContext
from canary.application.ports.index_provider import IndexProviderPort
from canary.application.ports.repository import RepositoryPort
from canary.application.use_cases.screen_entity import ScreenEntityUseCase


class BatchScreenUseCase:
    def __init__(
        self,
        index_provider: IndexProviderPort,
        repository: RepositoryPort,
    ):
        self.index_provider = index_provider
        self.repository = repository
        self.screen_use_case = ScreenEntityUseCase(index_provider, repository=None)

    def submit_batch(
        self,
        items: List[Dict[str, Any]],
        user: UserContext,
    ) -> Dict[str, Any]:
        """Accept a list of screening queries, record batch job, and initiate processing."""
        require_permission(user, Action.BATCH_SCREEN)

        batch_id = f"batch-{uuid.uuid4().hex[:12]}"
        total = len(items)

        self.repository.create_batch_job(
            batch_id=batch_id,
            user_id=user.user_id,
            total_items=total,
        )

        return {
            "batch_id": batch_id,
            "status": "ACCEPTED",
            "total_items": total,
            "created_at": time.time(),
            "message": "Batch screening request accepted for asynchronous processing.",
        }

    def process_batch(self, batch_id: str, items: List[Dict[str, Any]], user: UserContext) -> None:
        """Process items synchronously or in background worker."""
        results = []
        for it in items:
            q = it.get("query", "")
            q_type = it.get("query_type", "organisation")
            res = self.screen_use_case.execute(query=q, user=user, query_type=q_type)
            results.append({
                "query": res.query,
                "query_type": res.query_type,
                "lists": {k: {"tier": v.tier, "score": v.score, "source_id": v.source_id} for k, v in res.lists.items()},
            })

        self.repository.update_batch_job_progress(
            batch_id=batch_id,
            processed_items=len(results),
            status="COMPLETED",
            results_json=json.dumps(results),
        )

    def get_batch(self, batch_id: str, user: UserContext) -> Optional[Dict[str, Any]]:
        """Retrieve batch job status and results."""
        require_permission(user, Action.VIEW_RECORDS)
        return self.repository.get_batch_job(batch_id)
