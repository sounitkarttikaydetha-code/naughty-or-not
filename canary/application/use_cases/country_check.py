"""
Country Check Use Case.
Evaluates FATF status and Comprehensive Sanctions standing for a country.
"""
from typing import Optional

from canary.application.identity.permissions import require_permission, Action
from canary.application.ports.idp import UserContext
from canary.application.ports.repository import RepositoryPort
from canary.domain.country.engine import evaluate_country
from canary.domain.models import CountryCheckResult


class CountryCheckUseCase:
    def __init__(self, repository: Optional[RepositoryPort] = None):
        self.repository = repository

    def execute(
        self,
        query: str,
        user: UserContext,
        iso_code: Optional[str] = None,
    ) -> CountryCheckResult:
        """Execute country evaluation."""
        require_permission(user, Action.CHECK_COUNTRY)

        result = evaluate_country(query=query, iso_code=iso_code)

        if self.repository is not None:
            self.repository.append_screening_log({
                "user_id": user.user_id,
                "user_display_name": user.display_name,
                "auth_provider": user.auth_provider,
                "search_type": "country",
                "query_type": "jurisdiction",
                "inputs": f"{query} ({result.iso_code})",
                "result": result.fatf_status,
                "top_match": result.country_name,
                "score": 1.0 if result.is_comprehensive_sanctioned else 0.0,
                "duration_ms": 1,
                "details_json": {
                    "fatf_status": result.fatf_status,
                    "fatf_statement": result.fatf_statement,
                    "comprehensive": result.is_comprehensive_sanctioned,
                    "regimes": result.regimes,
                },
            })

        return result
