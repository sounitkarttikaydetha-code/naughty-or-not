"""
Screen Entity Use Case.
Coordinates candidate retrieval from index provider, pure domain tiering evaluation,
audit logging to append-only repository, and returns formatted result.
"""
import time
from typing import Any, Dict, List, Optional

from canary.application.identity.permissions import require_permission, Action
from canary.application.ports.idp import UserContext
from canary.application.ports.index_provider import IndexProviderPort
from canary.application.ports.repository import RepositoryPort
from canary.domain.models import ScreeningResult, MatchHit, Tier, TIER_ICONS
from canary.domain.matching.normalizer import normalize_tokens
from canary.domain.matching.phonetic import get_tokens_phonetic_codes

MANDATORY_LISTS = ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]


class ScreenEntityUseCase:
    def __init__(
        self,
        index_provider: IndexProviderPort,
        repository: Optional[RepositoryPort] = None,
    ):
        self.index_provider = index_provider
        self.repository = repository

    def execute(
        self,
        query: str,
        user: UserContext,
        query_type: Optional[str] = "organisation",
        identifier_type: Optional[str] = None,
        identifier_val: Optional[str] = None,
    ) -> ScreeningResult:
        """Execute screening against all mandatory lists with authorization and audit logging."""
        require_permission(user, Action.SCREEN)

        t0 = time.time()
        q_clean = query.strip()
        q_tokens = normalize_tokens(q_clean)
        q_phonetic_codes = get_tokens_phonetic_codes(q_tokens)

        # Retrieve screening results across all mandatory lists from index adapter
        raw_results = self.index_provider.screen_all_lists(
            query=q_clean,
            query_type=query_type,
            identifier_type=identifier_type,
            identifier_val=identifier_val,
        )

        list_hits: Dict[str, MatchHit] = {}

        for l_name in MANDATORY_LISTS:
            src_res = raw_results.get(l_name, {})
            best = src_res.get("best_hit", {})

            tier = best.get("tier", Tier.NO_MATCH.value)
            tier_icon = best.get("tier_icon", TIER_ICONS.get(Tier(tier), "✅") if tier in Tier.__members__.values() else "✅")
            score = float(best.get("score", 0.0))
            reason = best.get("reason", "none")
            p_name = best.get("primary_name", "—")
            m_name = best.get("matched_name", "—")
            s_id = str(best.get("source_id", "—"))
            below_cnt = int(best.get("below_threshold_count", 0))

            list_hits[l_name] = MatchHit(
                tier=tier,
                tier_icon=tier_icon,
                score=score,
                reason=reason,
                primary_name=p_name,
                matched_name=m_name,
                source_id=s_id,
                expanded_from=best.get("expanded_from"),
                below_threshold_count=below_cnt,
                matched_phonetic_codes=q_phonetic_codes,
            )

        duration_ms = (time.time() - t0) * 1000.0

        result = ScreeningResult(
            query=q_clean,
            query_type=query_type or "organisation",
            phonetic_codes=q_phonetic_codes,
            lists=list_hits,
            execution_time_ms=round(duration_ms, 2),
        )

        # Append-only audit logging
        if self.repository is not None:
            top_tier = Tier.NO_MATCH.value
            top_score = 0.0
            top_match_name = "—"
            for hit in list_hits.values():
                if hit.tier == Tier.POTENTIAL_MATCH.value:
                    top_tier = Tier.POTENTIAL_MATCH.value
                    top_score = max(top_score, hit.score)
                    top_match_name = hit.primary_name
                elif hit.tier == Tier.POSSIBLE_MATCH_REVIEW.value and top_tier != Tier.POTENTIAL_MATCH.value:
                    top_tier = Tier.POSSIBLE_MATCH_REVIEW.value
                    top_score = max(top_score, hit.score)
                    top_match_name = hit.primary_name

            self.repository.append_screening_log({
                "user_id": user.user_id,
                "user_display_name": user.display_name,
                "auth_provider": user.auth_provider,
                "search_type": "name",
                "query_type": query_type,
                "inputs": q_clean,
                "result": top_tier,
                "top_match": top_match_name,
                "score": top_score,
                "duration_ms": int(duration_ms),
                "details_json": {
                    "lists": {k: {"tier": v.tier, "score": v.score, "source_id": v.source_id} for k, v in list_hits.items()}
                },
            })

        return result
