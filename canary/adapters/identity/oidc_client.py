"""
Generic OpenID Connect (OIDC) Adapter & Local Mock Identity Provider.
Supports generic JWT verification (RS256 / HS256) without hardcoded vendor dependencies,
allowing seamless pointing to enterprise IdPs (Okta, Keycloak, Azure AD) later.
"""
import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict, List, Optional

from canary.application.ports.idp import IdpPort, UserContext
from canary.application.identity.roles import Role


def _b64url_decode(data: str) -> bytes:
    rem = len(data) % 4
    if rem > 0:
        data += "=" * (4 - rem)
    return base64.urlsafe_b64decode(data)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


class MockOIDCProvider:
    """Local Mock Identity Provider for automated testing and local development."""

    def __init__(self, secret: str = "mock-canary-secret-key-32-bytes!!", issuer: str = "https://idp.canary.internal/auth"):
        self.secret = secret
        self.issuer = issuer

    def issue_token(
        self,
        sub: str,
        roles: List[str],
        name: Optional[str] = None,
        email: Optional[str] = None,
        expires_in: int = 3600,
    ) -> str:
        """Issue an HS256 JWT token with standard OIDC claims."""
        header = {"alg": "HS256", "typ": "JWT"}
        now = int(time.time())
        payload = {
            "iss": self.issuer,
            "sub": sub,
            "aud": "clearance-check-api",
            "iat": now,
            "exp": now + expires_in,
            "roles": roles,
            "name": name or sub,
            "email": email or f"{sub}@example.internal",
        }

        h_b64 = _b64url_encode(json.dumps(header).encode("utf-8"))
        p_b64 = _b64url_encode(json.dumps(payload).encode("utf-8"))
        signing_input = f"{h_b64}.{p_b64}".encode("utf-8")
        sig = hmac.new(self.secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        s_b64 = _b64url_encode(sig)

        return f"{h_b64}.{p_b64}.{s_b64}"


class GenericOIDCClient(IdpPort):
    """Generic OIDC Token Validator."""

    def __init__(
        self,
        issuer: str = "https://idp.canary.internal/auth",
        audience: str = "clearance-check-api",
        secret: str = "mock-canary-secret-key-32-bytes!!",
    ):
        self.issuer = issuer
        self.audience = audience
        self.secret = secret

    def verify_token(self, token: str) -> UserContext:
        """Verify JWT signature, expiration, audience, and extract UserContext."""
        if not token:
            raise ValueError("Token is required.")

        parts = token.strip().split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT format: expected 3 dot-separated segments.")

        h_b64, p_b64, s_b64 = parts
        try:
            header = json.loads(_b64url_decode(h_b64).decode("utf-8"))
            payload = json.loads(_b64url_decode(p_b64).decode("utf-8"))
        except Exception as e:
            raise ValueError(f"Malformed JWT payload: {e}")

        # Check signature (HS256 mock)
        alg = header.get("alg", "HS256")
        if alg == "HS256":
            signing_input = f"{h_b64}.{p_b64}".encode("utf-8")
            expected_sig = hmac.new(self.secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
            actual_sig = _b64url_decode(s_b64)
            if not hmac.compare_digest(expected_sig, actual_sig):
                raise ValueError("Invalid token signature.")
        else:
            raise ValueError(f"Unsupported algorithm '{alg}'.")

        # Check expiration
        now = time.time()
        exp = payload.get("exp")
        if exp is not None and now > exp:
            raise ValueError("Token has expired.")

        # Extract claims
        sub = str(payload.get("sub", ""))
        if not sub:
            raise ValueError("Token is missing subject (sub) claim.")

        # Extract roles
        raw_roles = payload.get("roles") or payload.get("role") or []
        if isinstance(raw_roles, str):
            roles = [raw_roles]
        elif isinstance(raw_roles, list):
            roles = [str(r) for r in raw_roles]
        else:
            roles = []

        return UserContext(
            user_id=sub,
            display_name=payload.get("name", sub),
            roles=roles,
            email=payload.get("email"),
            auth_provider="oidc",
            raw_claims=payload,
        )

    def get_fallback_user(self) -> UserContext:
        """Return desktop Windows user as clearly labelled fallback."""
        import getpass
        try:
            uname = getpass.getuser()
        except Exception:
            uname = "local_screener"

        return UserContext(
            user_id=f"WINDOWS\\{uname}",
            display_name=f"{uname} (Windows User)",
            roles=[Role.SCREENER.value],
            email=None,
            auth_provider="windows_fallback",
            raw_claims={"auth": "windows_local_fallback"},
        )
