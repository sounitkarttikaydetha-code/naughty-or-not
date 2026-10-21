#!/usr/bin/env python3
"""
scripts/init_data.py

Clean-room bootstrap utility for Sanction checK.
Initializes local data directories, downloads/refreshes authoritative data
from official government sources (EU ASL, FAA IASA, US BIS, India MHA),
and builds the SQLite FTS5 raw search database index.

Usage:
    python scripts/init_data.py [--verify-only] [--force]
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("init_data")

REQUIRED_DIRS = [
    PROJECT_ROOT / "data" / "aviation",
    PROJECT_ROOT / "data" / "india",
    PROJECT_ROOT / "data" / "fatf",
    PROJECT_ROOT / "data" / "raw_search",
    PROJECT_ROOT / "logs",
    PROJECT_ROOT / "reports",
]


def ensure_directories():
    """Ensure all required runtime data and log directories exist."""
    for d in REQUIRED_DIRS:
        d.mkdir(parents=True, exist_ok=True)
    logger.info("Checked/created all required data directories.")


def download_official_sanctions_lists(force: bool = False):
    """Download official raw sanctions lists if missing or force=True."""
    raw_dir = PROJECT_ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    sources_map = {
        "us_ofac_sdn.csv": "https://www.treasury.gov/ofac/downloads/sdn.csv",
        "us_csl.csv": "https://data.trade.gov/downloadable_consolidated_screening_list/v1/consolidated.csv",
        "uk_csl.csv": "https://sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.csv",
        "eu_csl.xml": "https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content?token=dG9rZW4tMjAxNw",
        "un_csl.xml": "https://scsanctions.un.org/resources/xml/en/consolidated.xml",
    }

    import urllib.request

    for fname, url in sources_map.items():
        dest = raw_dir / fname
        if force or not dest.exists() or dest.stat().st_size == 0:
            logger.info(f"Downloading {fname} from official source...")
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "SanctionCheck-Init/1.0"})
                with urllib.request.urlopen(req, timeout=30) as resp, open(dest, "wb") as out:
                    out.write(resp.read())
                logger.info(f"Successfully saved {fname}")
            except Exception as e:
                logger.warning(f"Could not download {fname}: {e}")


def bootstrap_data(force: bool = False, verify_only: bool = False):
    """Download/refresh official sources and build the FTS search index."""
    ensure_directories()

    if verify_only:
        raw_db = PROJECT_ROOT / "data" / "raw_search" / "raw_index.db"
        sources_yaml = PROJECT_ROOT / "config" / "sources.yaml"
        if not sources_yaml.is_file():
            logger.error("Missing config/sources.yaml")
            return 1
        logger.info("Verification complete: configurations and directories present.")
        return 0

    logger.info("1/3: Checking and refreshing raw sanctions lists...")
    download_official_sanctions_lists(force=force)

    logger.info("2/3: Checking and refreshing aviation & government data sources...")
    try:
        from modules.aviation.parser import check_and_refresh_sources
        check_and_refresh_sources(force=force)
        logger.info("Aviation data refreshed successfully.")
    except Exception as e:
        logger.warning(f"Aviation source refresh notice: {e}")

    logger.info("3/3: Building raw text search index (FTS5)...")
    try:
        from modules.raw_search.indexer import build_full_raw_index
        build_full_raw_index()
        logger.info("Raw search index built successfully.")
    except Exception as e:
        logger.error(f"Error building raw search index: {e}")
        return 1

    logger.info("Initialization complete! All sources and search indices ready.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Bootstrap and initialize Sanction checK data")
    parser.add_argument("--force", action="store_true", help="Force re-download of all external sources")
    parser.add_argument("--verify-only", action="store_true", help="Verify directories and configs only")
    args = parser.parse_args()

    sys.exit(bootstrap_data(force=args.force, verify_only=args.verify_only))


if __name__ == "__main__":
    main()
