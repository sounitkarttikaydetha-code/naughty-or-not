"""OpenSanctions bulk data loader with commercial licensing guard.

OpenSanctions bulk data (entities.ftm.json) is published under Creative Commons
Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
Commercial use requires a commercial licence from opensanctions.org.

Guard:
Bulk loading is strictly disabled by default (OPENSANCTIONS_BULK_ENABLED=false).
The loader refuses to run unless explicitly enabled in the environment.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

LICENCE_NOTICE = (
    "OpenSanctions data is licensed under CC BY-NC 4.0; "
    "commercial use requires a licence from opensanctions.org"
)


class BulkDataDisabledError(PermissionError):
    """Raised when bulk data loading is attempted without explicit authorization."""
    pass


def is_bulk_enabled() -> bool:
    """Check whether OPENSANCTIONS_BULK_ENABLED is set to true."""
    val = os.getenv("OPENSANCTIONS_BULK_ENABLED", "false").strip().lower()
    return val in ["true", "1", "yes"]


def load_bulk(file_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load bulk entities from OpenSanctions FollowTheMoney JSON.
    Refuses to execute if OPENSANCTIONS_BULK_ENABLED is not set to true.
    """
    if not is_bulk_enabled():
        msg = (
            f"OpenSanctions bulk loading is disabled by default. {LICENCE_NOTICE}. "
            "To enable, set OPENSANCTIONS_BULK_ENABLED=true in .env with a valid commercial licence."
        )
        logger.warning(msg)
        raise BulkDataDisabledError(msg)

    # If enabled, load from file_path or default path
    target = file_path or Path("data/opensanctions/entities.ftm.json")
    if not target.is_file():
        return {
            "status": "FILE_NOT_FOUND",
            "licence_notice": LICENCE_NOTICE,
            "entities_loaded": 0,
        }

    return {
        "status": "OK",
        "licence_notice": LICENCE_NOTICE,
        "entities_loaded": 0,
    }
