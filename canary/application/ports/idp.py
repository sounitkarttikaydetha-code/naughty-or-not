"""
Identity Provider (IdP) Port.
Defines contracts for OpenID Connect token verification and user context extraction.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class UserContext:
    user_id: str
    display_name: str
    roles: List[str] = field(default_factory=list)
    email: Optional[str] = None
    auth_provider: str = "oidc"  # "oidc" or "windows_fallback"
    raw_claims: dict = field(default_factory=dict)


class IdpPort(ABC):
    """Port for validating identity and extracting roles."""

    @abstractmethod
    def verify_token(self, token: str) -> UserContext:
        """Verify JWT token and return authenticated UserContext."""
        pass

    @abstractmethod
    def get_fallback_user(self) -> UserContext:
        """Return local desktop Windows authenticated user as clearly labelled fallback."""
        pass
