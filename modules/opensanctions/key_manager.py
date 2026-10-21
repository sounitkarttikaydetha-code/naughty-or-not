"""
OpenSanctions Key Manager
Handles secure in-memory and Windows Credential Manager (keyring) storage of OpenSanctions API keys.
Guarantees keys are never written to disk, logs, reports, or environment files unless explicitly remembered in keyring.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

SERVICE_NAME = "NaughtyOrNot"
KEY_USERNAME = "opensanctions_api_key"

# In-memory session key store
_SESSION_KEY: Optional[str] = None


def get_remembered_key() -> Optional[str]:
    """Retrieve remembered key from Windows Credential Manager via keyring, if available."""
    try:
        import keyring

        val = keyring.get_password(SERVICE_NAME, KEY_USERNAME)
        if val and val.strip():
            return val.strip()
    except Exception as e:
        logger.warning(f"Failed to read from keyring: {e}")
    return None


def save_remembered_key(key: str) -> bool:
    """Store key in Windows Credential Manager via keyring."""
    if not key or not key.strip():
        return False
    try:
        import keyring

        keyring.set_password(SERVICE_NAME, KEY_USERNAME, key.strip())
        return True
    except Exception as e:
        logger.warning(f"Failed to save to keyring: {e}")
        return False


def clear_remembered_key() -> bool:
    """Remove key from Windows Credential Manager via keyring."""
    try:
        import keyring

        keyring.delete_password(SERVICE_NAME, KEY_USERNAME)
        return True
    except Exception as e:
        # Key may not have existed
        logger.info(f"Keyring delete: {e}")
        return False


def set_session_key(key: Optional[str], remember: bool = False) -> None:
    """Set active in-memory session key, optionally saving to keyring."""
    global _SESSION_KEY
    if key and key.strip():
        _SESSION_KEY = key.strip()
        if remember:
            save_remembered_key(key.strip())
        else:
            # If user unchecks remember, clear from keyring
            clear_remembered_key()
    else:
        _SESSION_KEY = None


def get_session_key() -> Optional[str]:
    """Get active in-memory session key."""
    return _SESSION_KEY


def mask_key(key: Optional[str]) -> str:
    """Format key to show only the last 4 characters, e.g. '••••••••1234'."""
    if not key:
        return "None"
    k = key.strip()
    if len(k) <= 4:
        return "••••"
    return f"••••••••{k[-4:]}"
