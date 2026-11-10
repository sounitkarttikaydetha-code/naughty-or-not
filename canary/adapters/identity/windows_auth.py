"""
Windows User Authentication Fallback Adapter.
Provides fallback identity for the Desktop Canary when no OIDC bearer token is supplied.
"""
import getpass
import os
from canary.application.ports.idp import UserContext
from canary.application.identity.roles import Role


def get_windows_fallback_user() -> UserContext:
    """Extract Windows user name and domain, clearly labelled as fallback."""
    try:
        user = getpass.getuser()
    except Exception:
        user = "DesktopUser"

    domain = os.environ.get("USERDOMAIN", "LOCAL")

    return UserContext(
        user_id=f"{domain}\\{user}",
        display_name=f"{user} ({domain})",
        roles=[Role.SCREENER.value],
        email=None,
        auth_provider="windows_fallback",
        raw_claims={"domain": domain, "username": user},
    )
