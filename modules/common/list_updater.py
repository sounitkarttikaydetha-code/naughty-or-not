"""
List update and initialization manager for Naughty or not.
Handles seed data copying, 24-hour freshness checks, background/manual updates,
and first-run index preparation.
"""

import logging
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from modules.common.paths import (
    get_app_data_dir,
    get_index_db_path,
    get_lists_dir,
    get_seed_data_dir,
)

logger = logging.getLogger(__name__)


def copy_tree_files(src: Path, dst: Path) -> None:
    """Recursively copy files from src to dst if dst does not have them."""
    if not src.is_dir():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            copy_tree_files(item, target)
        elif item.is_file():
            if not target.exists() or target.stat().st_size == 0:
                shutil.copy2(item, target)


def init_lists_from_seed() -> bool:
    """
    Ensure the user data directory (%LOCALAPPDATA%\\NaughtyOrNot\\lists) is populated
    with the bundled seed sanction lists on first run.
    """
    lists_dir = get_lists_dir()
    seed_dir = get_seed_data_dir()

    raw_dest = lists_dir / "raw"
    aviation_dest = lists_dir / "aviation"
    india_dest = lists_dir / "india"

    # Check if raw list files already exist
    has_raw = raw_dest.is_dir() and any(raw_dest.glob("*.csv"))
    if not has_raw and seed_dir.is_dir():
        logger.info(f"Initializing lists from bundled seed dir: {seed_dir}")
        copy_tree_files(seed_dir, lists_dir)
        return True
    return False


def get_lists_date() -> str:
    """Return the date of the current list copies for the offline banner."""
    # Look at us_ofac_sdn.csv or sources_meta.json
    lists_dir = get_lists_dir()
    ofac = lists_dir / "raw" / "us_ofac_sdn.csv"
    if not ofac.exists():
        ofac = get_seed_data_dir() / "raw" / "us_ofac_sdn.csv"
    if ofac.exists():
        mtime = datetime.fromtimestamp(ofac.stat().st_mtime, tz=timezone.utc)
        return mtime.strftime("%Y-%m-%d")
    return "2026-10-18"


def ensure_text_search_index(progress_callback: Optional[Callable[[str], None]] = None) -> bool:
    """
    Build the SQLite FTS5 index if raw_index.db is missing.
    Shows the user: 'Preparing text search… this happens once'.
    """
    index_path = get_index_db_path()
    if index_path.is_file() and index_path.stat().st_size > 1000:
        return True

    if progress_callback:
        progress_callback("Preparing text search… this happens once")

    try:
        from modules.raw_search.indexer import build_full_raw_index
        build_full_raw_index(db_path=index_path)
        return True
    except Exception as e:
        logger.error(f"Failed to build raw index on first run: {e}")
        return False
