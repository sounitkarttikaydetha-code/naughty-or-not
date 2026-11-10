"""
Ownership & UBO Check Use Case.
Implements corporate hierarchy submission, 50% rule calculation,
four-eyes maker-checker review, and append-only audit trail logging.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from canary.application.identity.four_eyes import enforce_four_eyes_rule, FourEyesViolationError
from canary.application.identity.permissions import require_permission, Action
from canary.application.ports.idp import UserContext
from canary.application.ports.repository import RepositoryPort
from canary.domain.ownership.engine import (
    HoldingEntry,
    validate_ownership_structure,
    calculate_undisclosed_shortfall,
    check_undisclosed_dependence,
    calculate_effective_ofac_blocked,
)


class OwnershipCheckUseCase:
    def __init__(self, repository: RepositoryPort):
        self.repository = repository

    def create_check(
        self,
        target_name: str,
        holdings: List[Dict[str, Any]],
        user: UserContext,
    ) -> Dict[str, Any]:
        """Create new ownership structure evaluation in DRAFT status."""
        require_permission(user, Action.CREATE_OWNERSHIP)

        holding_entries = [
            HoldingEntry(
                entity_name=h.get("entity_name", target_name),
                shareholder_name=h.get("shareholder_name", ""),
                share_pct=float(h.get("share_pct", 0.0)),
                entity_type=h.get("entity_type", "company"),
                is_blocked=bool(h.get("is_blocked", False)),
                blocked_source=h.get("blocked_source", ""),
            )
            for h in holdings
        ]

        val_res = validate_ownership_structure(holding_entries)
        if not val_res.is_valid:
            raise ValueError(f"Invalid ownership structure: {'; '.join(val_res.errors)}")

        # Pure domain calculations
        is_ofac_b, ofac_agg, ofac_reasons = calculate_effective_ofac_blocked(target_name, holding_entries)
        total_disclosed = sum(h.share_pct for h in holding_entries if h.entity_name.strip().lower() == target_name.strip().lower())
        shortfall = calculate_undisclosed_shortfall(total_disclosed)
        depends_on_shortfall = check_undisclosed_dependence(ofac_agg, 0.0, shortfall)

        check_data = {
            "target_name": target_name,
            "status": "DRAFT",
            "preparer_id": user.user_id,
            "reviewer_id": None,
            "review_due_date": None,
            "ofac_verdict": "BLOCKED" if is_ofac_b else "CLEAR",
            "ofac_aggregate_pct": ofac_agg,
            "undisclosed_pct": shortfall,
            "depends_on_undisclosed": depends_on_shortfall,
            "holdings": [
                {
                    "entity_name": h.entity_name,
                    "shareholder_name": h.shareholder_name,
                    "share_pct": h.share_pct,
                    "entity_type": h.entity_type,
                    "is_blocked": h.is_blocked,
                    "blocked_source": h.blocked_source,
                }
                for h in holding_entries
            ],
            "reasons": ofac_reasons,
        }

        check_id = self.repository.create_ownership_check(check_data)
        self.repository.append_ownership_audit(
            check_id=check_id,
            actor_id=user.user_id,
            action="CREATE",
            from_status="NONE",
            to_status="DRAFT",
            comment="Initial structure entered.",
        )

        check_data["id"] = check_id
        return check_data

    def get_check(self, check_id: int, user: UserContext) -> Optional[Dict[str, Any]]:
        """Retrieve ownership check details."""
        require_permission(user, Action.VIEW_RECORDS)
        return self.repository.get_ownership_check(check_id)

    def submit_check(self, check_id: int, user: UserContext) -> Dict[str, Any]:
        """Submit ownership check for maker-checker review."""
        require_permission(user, Action.SUBMIT_OWNERSHIP)
        check = self.repository.get_ownership_check(check_id)
        if not check:
            raise KeyError(f"Ownership check {check_id} not found.")

        if check["status"] != "DRAFT":
            raise ValueError(f"Check is in '{check['status']}' state; only DRAFT checks can be submitted.")

        self.repository.update_ownership_status(
            check_id=check_id,
            status="SUBMITTED_FOR_REVIEW",
            actor_id=user.user_id,
            role="Preparer",
            comment="Submitted for review.",
        )
        self.repository.append_ownership_audit(
            check_id=check_id,
            actor_id=user.user_id,
            action="SUBMIT",
            from_status="DRAFT",
            to_status="SUBMITTED_FOR_REVIEW",
            comment="Submitted for review.",
        )

        check["status"] = "SUBMITTED_FOR_REVIEW"
        return check

    def review_check(
        self,
        check_id: int,
        decision: str,  # "APPROVED" or "REJECTED"
        comment: str,
        user: UserContext,
    ) -> Dict[str, Any]:
        """
        Review, approve, or reject an ownership check.
        Strictly enforces the four-eyes rule: preparer cannot review their own check.
        """
        require_permission(user, Action.REVIEW_OWNERSHIP)

        check = self.repository.get_ownership_check(check_id)
        if not check:
            raise KeyError(f"Ownership check {check_id} not found.")

        if check["status"] not in ("SUBMITTED_FOR_REVIEW", "PENDING_REVIEW"):
            raise ValueError(f"Check is in '{check['status']}' state; cannot be reviewed.")

        # Hard Rule: Four-Eyes Principle
        enforce_four_eyes_rule(check["preparer_id"], user.user_id)

        target_status = "APPROVED" if decision.upper() == "APPROVED" else "REJECTED"

        self.repository.update_ownership_status(
            check_id=check_id,
            status=target_status,
            actor_id=user.user_id,
            role="Reviewer",
            comment=comment,
        )
        self.repository.append_ownership_audit(
            check_id=check_id,
            actor_id=user.user_id,
            action=f"REVIEW_{target_status}",
            from_status=check["status"],
            to_status=target_status,
            comment=comment,
        )

        check["status"] = target_status
        check["reviewer_id"] = user.user_id
        return check
