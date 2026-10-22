"""OpenSanctions bulk data loader with commercial licensing guard.

OpenSanctions bulk data (entities.ftm.json) is published under Creative Commons
Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
Commercial use requires a commercial licence from opensanctions.org.

Guard:
Bulk loading is strictly disabled by default (OPENSANCTIONS_BULK_ENABLED=false).
The loader refuses to run unless ALL THREE conditions are met:
1. OPENSANCTIONS_BULK_ENABLED=true in environment
2. OPENSANCTIONS_BULK_PERMISSION_REF is set to a non-empty reference
3. User has completed the in-app acknowledgement in Settings for this version.

CRITICAL SECURITY RULE:
The presence or value of OPENSANCTIONS_API_KEY never enables or modifies the bulk state.
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

LICENCE_NOTICE = (
    "OpenSanctions data is licensed under CC BY-NC 4.0; "
    "commercial use requires a licence from opensanctions.org"
)


class BulkDataDisabledError(PermissionError):
    """Raised when bulk data loading is attempted without explicit authorization."""
    pass


def is_bulk_enabled(
    user: Optional[str] = None,
    app_version: Optional[str] = None,
    check_ack: bool = True,
) -> bool:
    """
    Check whether all three bulk prerequisites are satisfied:
    1. OPENSANCTIONS_BULK_ENABLED is true
    2. OPENSANCTIONS_BULK_PERMISSION_REF is non-empty
    3. User has acknowledged written permission in-app for the current version.
    
    The API key, by itself, never changes the bulk state.
    """
    val = os.getenv("OPENSANCTIONS_BULK_ENABLED", "false").strip().lower()
    enabled = val in ["true", "1", "yes"]
    perm_ref = os.getenv("OPENSANCTIONS_BULK_PERMISSION_REF", "").strip()

    if not enabled or not perm_ref:
        return False

    if check_ack:
        try:
            from modules.reporting.logger import APP_VERSION, has_user_bulk_acknowledged
            ver = app_version or APP_VERSION
            return has_user_bulk_acknowledged(user=user, app_version=ver)
        except Exception:
            return False

    return True


def load_bulk(
    file_path: Optional[Path] = None,
    user: Optional[str] = None,
    app_version: Optional[str] = None,
    check_ack: bool = True,
) -> Dict[str, Any]:
    """
    Load bulk entities from FollowTheMoney newline-delimited JSON.
    Refuses to execute unless all three gates pass.
    Refuses test fixtures in packaged / frozen releases.
    """
    val = os.getenv("OPENSANCTIONS_BULK_ENABLED", "false").strip().lower()
    enabled = val in ["true", "1", "yes"]
    perm_ref = os.getenv("OPENSANCTIONS_BULK_PERMISSION_REF", "").strip()

    if not enabled:
        msg = (
            f"OpenSanctions bulk loading is disabled by default. {LICENCE_NOTICE}. "
            "To enable, set OPENSANCTIONS_BULK_ENABLED=true and OPENSANCTIONS_BULK_PERMISSION_REF in .env."
        )
        logger.warning(msg)
        raise BulkDataDisabledError(msg)

    if not perm_ref:
        msg = (
            f"OpenSanctions bulk loading requires OPENSANCTIONS_BULK_PERMISSION_REF to be set. {LICENCE_NOTICE}."
        )
        logger.warning(msg)
        raise BulkDataDisabledError(msg)

    if check_ack:
        try:
            from modules.reporting.logger import APP_VERSION, has_user_bulk_acknowledged
            ver = app_version or APP_VERSION
            if not has_user_bulk_acknowledged(user=user, app_version=ver):
                msg = (
                    "OpenSanctions bulk loading requires in-app acknowledgement in Settings "
                    "confirming you hold written permission or a licence from OpenSanctions."
                )
                logger.warning(msg)
                raise BulkDataDisabledError(msg)
        except BulkDataDisabledError:
            raise
        except Exception as e:
            logger.error(f"Error checking bulk acknowledgement: {e}")
            raise BulkDataDisabledError(f"Could not verify bulk acknowledgement: {e}")

    target = Path(file_path) if file_path else Path("data/opensanctions/entities.ftm.json")

    # Guard: Packaged builds must refuse test fixtures
    if getattr(sys, "frozen", False) and "fixtures" in str(target).lower():
        msg = "Synthetic test fixtures are strictly refused in packaged production releases."
        logger.error(msg)
        raise RuntimeError(msg)

    if not target.is_file():
        return {
            "status": "FILE_NOT_FOUND",
            "tier": "NOT_CHECKED",
            "error": f"File not found: {target}",
            "licence_notice": LICENCE_NOTICE,
            "entities_loaded": 0,
            "entities": [],
        }

    if target.stat().st_size == 0:
        return {
            "status": "EMPTY_FILE",
            "tier": "NOT_CHECKED",
            "error": "OpenSanctions bulk file is empty (0 bytes)",
            "licence_notice": LICENCE_NOTICE,
            "entities_loaded": 0,
            "entities": [],
        }

    entities = []
    malformed_count = 0
    is_synthetic_fixture = "fixtures" in str(target).lower()
    has_synthetic_marker = False

    try:
        with open(target, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                clean_line = line.strip()
                if not clean_line:
                    continue

                try:
                    obj = json.loads(clean_line)
                except Exception:
                    malformed_count += 1
                    continue

                # Header marker check
                if obj.get("_synthetic_header"):
                    has_synthetic_marker = True
                    continue

                if "SYNTHETIC TEST DATA" in str(obj):
                    has_synthetic_marker = True

                # Must be FtM entity schema
                if not isinstance(obj, dict) or "id" not in obj or "schema" not in obj:
                    malformed_count += 1
                    continue

                props = obj.get("properties") or {}
                name_list = props.get("name") or [obj.get("caption", "")]
                name = name_list[0] if name_list else ""
                aliases = props.get("alias") or []

                entities.append({
                    "id": str(obj["id"]),
                    "schema": obj.get("schema", "LegalEntity"),
                    "name": name,
                    "aliases": aliases,
                    "caption": obj.get("caption", name),
                    "properties": props,
                    "datasets": obj.get("datasets", []),
                    "source": "os_bulk",
                    "source_label": "OpenSanctions (evaluation)",
                })

        if is_synthetic_fixture and not has_synthetic_marker:
            return {
                "status": "UNVERIFIED_FIXTURE",
                "tier": "NOT_CHECKED",
                "error": "Synthetic fixture missing mandatory 'SYNTHETIC TEST DATA' marker",
                "licence_notice": LICENCE_NOTICE,
                "entities_loaded": 0,
                "entities": [],
            }

        return {
            "status": "OK",
            "tier": "OK",
            "entities_loaded": len(entities),
            "malformed_count": malformed_count,
            "licence_notice": LICENCE_NOTICE,
            "source_label": "OpenSanctions (evaluation)",
            "entities": entities,
        }

    except Exception as e:
        logger.error(f"Error loading OpenSanctions bulk file {target}: {e}")
        return {
            "status": "CORRUPT_FILE",
            "tier": "NOT_CHECKED",
            "error": f"Error parsing bulk file: {e}",
            "licence_notice": LICENCE_NOTICE,
            "entities_loaded": 0,
            "entities": [],
        }
