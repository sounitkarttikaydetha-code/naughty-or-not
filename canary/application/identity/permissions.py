"""
Permissions Enforcement Layer.
Maps roles to permitted actions and endpoints.
"""
from typing import List, Set
from canary.application.identity.roles import Role
from canary.application.ports.idp import UserContext


class Action:
    SCREEN = "screen"
    BATCH_SCREEN = "batch_screen"
    VIEW_RECORDS = "view_records"
    CREATE_OWNERSHIP = "create_ownership"
    SUBMIT_OWNERSHIP = "submit_ownership"
    REVIEW_OWNERSHIP = "review_ownership"
    CHECK_COUNTRY = "check_country"
    VIEW_SOURCES = "view_sources"
    REFRESH_SOURCES = "refresh_sources"
    GENERATE_REPORTS = "generate_reports"
    VIEW_AUDIT_LOGS = "view_audit_logs"
    VIEW_SYSTEM_METRICS = "view_system_metrics"


# Role to Permitted Actions Mapping
ROLE_PERMISSIONS = {
    Role.SCREENER: {
        Action.SCREEN,
        Action.BATCH_SCREEN,
        Action.VIEW_RECORDS,
        Action.CREATE_OWNERSHIP,
        Action.SUBMIT_OWNERSHIP,
        Action.CHECK_COUNTRY,
        Action.VIEW_SOURCES,
        Action.GENERATE_REPORTS,
        Action.VIEW_AUDIT_LOGS,
    },
    Role.REVIEWER: {
        Action.SCREEN,
        Action.BATCH_SCREEN,
        Action.VIEW_RECORDS,
        Action.CREATE_OWNERSHIP,
        Action.SUBMIT_OWNERSHIP,
        Action.REVIEW_OWNERSHIP,
        Action.CHECK_COUNTRY,
        Action.VIEW_SOURCES,
        Action.GENERATE_REPORTS,
        Action.VIEW_AUDIT_LOGS,
    },
    Role.COMPLIANCE: {
        Action.SCREEN,
        Action.BATCH_SCREEN,
        Action.VIEW_RECORDS,
        Action.CREATE_OWNERSHIP,
        Action.SUBMIT_OWNERSHIP,
        Action.REVIEW_OWNERSHIP,
        Action.CHECK_COUNTRY,
        Action.VIEW_SOURCES,
        Action.GENERATE_REPORTS,
        Action.VIEW_AUDIT_LOGS,
        Action.VIEW_SYSTEM_METRICS,
    },
    Role.ADMINISTRATOR: {
        Action.SCREEN,
        Action.BATCH_SCREEN,
        Action.VIEW_RECORDS,
        Action.CREATE_OWNERSHIP,
        Action.SUBMIT_OWNERSHIP,
        Action.REVIEW_OWNERSHIP,
        Action.CHECK_COUNTRY,
        Action.VIEW_SOURCES,
        Action.REFRESH_SOURCES,
        Action.GENERATE_REPORTS,
        Action.VIEW_AUDIT_LOGS,
        Action.VIEW_SYSTEM_METRICS,
    },
    Role.AUDITOR: {
        # Strictly READ-ONLY. No screening, no batch screening, no mutations.
        Action.VIEW_RECORDS,
        Action.VIEW_SOURCES,
        Action.GENERATE_REPORTS,
        Action.VIEW_AUDIT_LOGS,
        Action.VIEW_SYSTEM_METRICS,
    },
}


class PermissionDeniedError(Exception):
    """Raised when an authenticated user attempts an unpermitted action."""
    pass


def has_permission(user: UserContext, action: str) -> bool:
    """Check if the user possesses permission for the given action in any of their assigned roles."""
    if not user.roles:
        # Default to Screener permissions if none specified
        user_roles = [Role.SCREENER]
    else:
        user_roles = []
        for r in user.roles:
            try:
                user_roles.append(Role(r))
            except ValueError:
                pass

    for r in user_roles:
        allowed_actions = ROLE_PERMISSIONS.get(r, set())
        if action in allowed_actions:
            return True
    return False


def require_permission(user: UserContext, action: str) -> None:
    """Raise PermissionDeniedError if action is not permitted for user."""
    if not has_permission(user, action):
        roles_str = ", ".join(user.roles) if user.roles else "None"
        raise PermissionDeniedError(
            f"Action '{action}' is forbidden for user '{user.user_id}' with roles [{roles_str}]."
        )
