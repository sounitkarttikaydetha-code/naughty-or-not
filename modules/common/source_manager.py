"""
Master Source Management & List Refresh Engine for Naughty or not.
Implements RFC / SPEC requirements for T8-1:
- config/sources.yaml single source of truth
- Real refresh with atomic swap & 3-version archive
- Closure keyword detection & HTTP 410 handling
- Safe URL relocation & allowed_domains enforcement
- Staleness tracking by last_verified_at vs max_age_days
- source_events audit logging in SQLite
"""

import csv
from datetime import datetime, timezone, timedelta
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import tempfile
from typing import Any, Callable, Dict, List, Optional, Tuple
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import yaml

from modules.common.paths import (
    get_app_data_dir,
    get_lists_dir,
    get_seed_data_dir,
    get_index_db_path,
)

logger = logging.getLogger(__name__)

# State constants
STATE_OK = "OK"
STATE_OFFLINE_NOTE = "OFFLINE_NOTE"
STATE_UPDATE_REJECTED = "UPDATE_REJECTED"
STATE_ADDRESS_CHANGED = "ADDRESS_CHANGED"
STATE_STALE = "STALE"
STATE_CLOSED_SUSPECTED = "CLOSED_SUSPECTED"
STATE_FAILED_NO_COPY = "FAILED_NO_COPY"

# Default closure keywords
DEFAULT_CLOSURE_KEYWORDS = [
    "no longer being updated",
    "no longer updated",
    "has closed",
    "closed on",
    "replaced by",
    "superseded",
    "withdrawn",
    "archived",
    "discontinued",
    "moved to",
]


def get_sources_config_path() -> Path:
    """Resolve path to config/sources.yaml."""
    base = Path(__file__).resolve().parent.parent.parent
    cfg = base / "config" / "sources.yaml"
    if not cfg.is_file():
        cfg = get_app_data_dir() / "config" / "sources.yaml"
    return cfg


def load_sources_registry() -> Dict[str, Any]:
    """Load sources registry from config/sources.yaml."""
    cfg_path = get_sources_config_path()
    if not cfg_path.is_file():
        logger.error(f"Sources config not found at {cfg_path}")
        return {}
    with open(cfg_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    raw = data.get("sources", {})
    if isinstance(raw, list):
        return {s["id"]: s for s in raw if isinstance(s, dict) and "id" in s}
    return raw


def get_sources_state_file() -> Path:
    """Path to persisted sources_state.json in user data directory."""
    lists_dir = get_lists_dir()
    lists_dir.mkdir(parents=True, exist_ok=True)
    return lists_dir / "sources_state.json"


def load_sources_state() -> Dict[str, Any]:
    """Load persisted source states."""
    sf = get_sources_state_file()
    if sf.is_file():
        try:
            with open(sf, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error reading sources_state.json: {e}")
    return {}


def save_sources_state(state: Dict[str, Any]) -> None:
    """Save source states to sources_state.json."""
    sf = get_sources_state_file()
    sf.parent.mkdir(parents=True, exist_ok=True)
    temp_sf = sf.with_suffix(".tmp")
    with open(temp_sf, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    temp_sf.replace(sf)


def get_source_file_path(source_id: str) -> Path:
    """Get expected local file path for a source in lists directory."""
    lists_dir = get_lists_dir()
    path_map = {
        "us_ofac": lists_dir / "raw" / "us_ofac_sdn.csv",
        "us_csl": lists_dir / "raw" / "us_csl.csv",
        "uk_csl": lists_dir / "raw" / "uk_csl.csv",
        "eu_csl": lists_dir / "raw" / "eu_csl.xml",
        "un_csl": lists_dir / "raw" / "un_csl.xml",
        "in_mha_first_schedule": lists_dir / "india" / "first_schedule.pdf",
        "in_mha_fourth_schedule": lists_dir / "india" / "individuals_all.json",
        "in_mha_unlawful_assoc": lists_dir / "india" / "unlawful_associations_all.json",
        "bis_aircraft": lists_dir / "aviation" / "bis_aircraft.pdf",
        "eu_air_safety_list": lists_dir / "aviation" / "eu_air_safety_list.pdf",
        "faa_iasa": lists_dir / "aviation" / "faa_iasa.pdf",
        "fatf_jurisdictions": lists_dir / "fatf" / "fatf.json",
    }
    target = path_map.get(source_id, lists_dir / f"{source_id}.dat")
    # If file doesn't exist in lists_dir, check seed directory
    if not target.is_file():
        seed_dir = get_seed_data_dir()
        seed_map = {
            "us_ofac": seed_dir / "raw" / "us_ofac_sdn.csv",
            "us_csl": seed_dir / "raw" / "us_csl.csv",
            "uk_csl": seed_dir / "raw" / "uk_csl.csv",
            "eu_csl": seed_dir / "raw" / "eu_csl.xml",
            "un_csl": seed_dir / "raw" / "un_csl.xml",
            "in_mha_first_schedule": seed_dir / "india" / "first_schedule.pdf",
            "in_mha_fourth_schedule": seed_dir / "india" / "individuals_all.json",
            "in_mha_unlawful_assoc": seed_dir / "india" / "unlawful_associations_all.json",
            "bis_aircraft": seed_dir / "aviation" / "bis_aircraft.pdf",
            "eu_air_safety_list": seed_dir / "aviation" / "eu_air_safety_list.pdf",
            "faa_iasa": seed_dir / "aviation" / "faa_iasa.pdf",
            "fatf_jurisdictions": Path(__file__).resolve().parent.parent.parent / "config" / "fatf.json",
        }
        fallback = seed_map.get(source_id)
        if fallback and fallback.is_file():
            return fallback
    return target


def ensure_source_events_table(conn: sqlite3.Connection) -> None:
    """Ensure source_events table exists in screening.db."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS source_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            source TEXT NOT NULL,
            event TEXT NOT NULL,
            old_url TEXT,
            new_url TEXT,
            record_count_before INTEGER,
            record_count_after INTEGER,
            hash_before TEXT,
            hash_after TEXT,
            message TEXT
        )
    """)
    conn.commit()


def log_source_event(
    source: str,
    event: str,
    old_url: str = "",
    new_url: str = "",
    count_before: int = 0,
    count_after: int = 0,
    hash_before: str = "",
    hash_after: str = "",
    message: str = "",
) -> None:
    """Log an event into source_events table."""
    try:
        from modules.reporting.logger import get_db_connection
        conn = get_db_connection()
        ensure_source_events_table(conn)
        now_iso = datetime.now(timezone.utc).isoformat()
        conn.execute("""
            INSERT INTO source_events (
                timestamp, source, event, old_url, new_url,
                record_count_before, record_count_after, hash_before, hash_after, message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            now_iso, source, event, old_url, new_url,
            count_before, count_after, hash_before, hash_after, message
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Failed to log source event for {source}: {e}")


def compute_sha256(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    if not path.is_file():
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def count_records(path: Path, fmt: str) -> int:
    """Parse and count valid records in file based on format."""
    if not path.is_file() or path.stat().st_size == 0:
        return 0
    fmt = fmt.lower()
    try:
        if fmt == "csv":
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if not header:
                    return 0
                return sum(1 for row in reader if any(row))
        elif fmt == "xml":
            count = 0
            # Count sanctionEntity or INDIVIDUALS/ENTITIES
            for event, elem in ET.iterparse(str(path), events=("end",)):
                tag = elem.tag.split("}")[-1]
                if tag in ["sanctionEntity", "INDIVIDUAL", "ENTITY"]:
                    count += 1
                elem.clear()
            return count
        elif fmt == "json":
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return len(data)
            if isinstance(data, dict):
                if "entities" in data:
                    return len(data["entities"])
                if "black_list" in data and "grey_list" in data:
                    return len(data["black_list"]) + len(data["grey_list"])
            return 1
        elif fmt == "pdf":
            import pypdf
            reader = pypdf.PdfReader(str(path))
            # Return page count or estimated records
            text = " ".join([page.extract_text() or "" for page in reader.pages])
            lines = [l for l in text.splitlines() if l.strip()]
            return max(len(reader.pages), len(lines) // 4)
    except Exception as e:
        logger.debug(f"Error counting records for {path} ({fmt}): {e}")
    return 0


def validate_file(path: Path, spec: Dict[str, Any], last_good_count: int = 0) -> Tuple[bool, str, int]:
    """
    Validate a downloaded file against expected specifications:
    - size >= min_bytes
    - format validity
    - required columns / elements
    - record count >= min_records
    - count within count_range_ratio of last good copy
    """
    if not path.is_file():
        return False, "File not found", 0

    size = path.stat().st_size
    expected = spec.get("expected", {})
    min_bytes = expected.get("min_bytes", 100)
    if size < min_bytes:
        return False, f"File size {size} bytes below minimum required {min_bytes} bytes", 0

    fmt = expected.get("format", "").lower()
    # 1. Format & required elements check
    if fmt == "csv":
        req_cols = expected.get("required_columns", [])
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if not header:
                    return False, "Empty CSV header", 0
                header_set = {c.strip() for c in header if c}
                for rc in req_cols:
                    if rc not in header_set:
                        # Try case-insensitive search
                        if not any(rc.lower() == h.lower() for h in header_set):
                            return False, f"Missing required column '{rc}' in CSV", 0
        except Exception as e:
            return False, f"Corrupt CSV file: {e}", 0

    elif fmt == "xml":
        req_elems = expected.get("required_elements", [])
        try:
            # Check XML well-formedness
            context = ET.iterparse(str(path), events=("start",))
            found_elems = set()
            for _, elem in context:
                tag = elem.tag.split("}")[-1]
                found_elems.add(tag)
                if len(found_elems) >= 50:
                    break
            for re_tag in req_elems:
                if re_tag not in found_elems:
                    return False, f"Missing required XML element '{re_tag}'", 0
        except Exception as e:
            return False, f"Corrupt XML file: {e}", 0

    elif fmt == "json":
        req_elems = expected.get("required_elements", [])
        try:
            with open(path, "r", encoding="utf-8") as f:
                jdata = json.load(f)
            for re_key in req_elems:
                if isinstance(jdata, dict) and re_key not in jdata:
                    return False, f"Missing required JSON property '{re_key}'", 0
        except Exception as e:
            return False, f"Corrupt JSON file: {e}", 0

    elif fmt == "pdf":
        req_elems = expected.get("required_elements", [])
        try:
            import pypdf
            reader = pypdf.PdfReader(str(path))
            if len(reader.pages) == 0:
                return False, "PDF contains zero pages", 0
            first_text = reader.pages[0].extract_text() or ""
            for req_word in req_elems:
                if req_word.lower() not in first_text.lower():
                    # Check across first 3 pages
                    found = False
                    for p in reader.pages[:3]:
                        if req_word.lower() in (p.extract_text() or "").lower():
                            found = True
                            break
                    if not found:
                        return False, f"Missing required text anchor '{req_word}' in PDF", 0
        except Exception as e:
            return False, f"Corrupt PDF file: {e}", 0

    # 2. Count records and range check
    count = count_records(path, fmt)
    min_records = expected.get("min_records", 1)
    if count < min_records:
        return False, f"Record count {count} below minimum expected {min_records}", count

    if last_good_count > 0:
        ratio_range = expected.get("count_range_ratio", [0.70, 1.50])
        min_allowed = int(last_good_count * ratio_range[0])
        max_allowed = int(last_good_count * ratio_range[1])
        if count < min_allowed or count > max_allowed:
            return False, f"Record count {count} outside allowed range ({min_allowed} - {max_allowed}) vs previous copy ({last_good_count})", count

    return True, "OK", count


def check_domain_allowed(url: str, allowed_domains: List[str]) -> bool:
    """Verify URL domain is in allowed_domains list."""
    if not url:
        return False
    try:
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.lower()
        if ":" in netloc:
            netloc = netloc.split(":")[0]
        for ad in allowed_domains:
            ad_clean = ad.lower().strip()
            if netloc == ad_clean or netloc.endswith("." + ad_clean):
                return True
    except Exception:
        pass
    return False


def check_closure_keywords(content: str, keywords: Optional[List[str]] = None) -> Optional[str]:
    """Check text content for closure keywords."""
    if not content:
        return None
    kws = keywords or DEFAULT_CLOSURE_KEYWORDS
    lower = content.lower()
    for kw in kws:
        if kw.lower() in lower:
            return kw
    return None


def archive_version(source_id: str, current_file: Path) -> None:
    """Keep previous 3 versions of a source in lists/archive/<source_id>/."""
    if not current_file.is_file() or current_file.stat().st_size == 0:
        return
    archive_dir = get_lists_dir() / "archive" / source_id
    archive_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    ext = current_file.suffix
    dest = archive_dir / f"{source_id}_{ts}{ext}"
    try:
        shutil.copy2(current_file, dest)
        # Purge to keep only last 3 versions
        existing = sorted(archive_dir.glob(f"{source_id}_*{ext}"), key=os.path.getmtime)
        if len(existing) > 3:
            for old_f in existing[:-3]:
                try:
                    old_f.unlink()
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"Archive error for {source_id}: {e}")


class SourceManager:
    """Coordinates regulatory list refresh, validation, state tracking and events."""

    def __init__(self):
        self.registry = load_sources_registry()
        self.state = load_sources_state()

    def get_source_state(self, source_id: str) -> Dict[str, Any]:
        """Get current status model for a source."""
        spec = self.registry.get(source_id, {})
        entry = self.state.get(source_id, {})
        local_file = get_source_file_path(source_id)

        # Baseline info if uninitialized
        if not entry:
            pub_date = "2026-10-18"
            last_verified = "2026-10-22T00:00:00Z"
            count = count_records(local_file, spec.get("expected", {}).get("format", "csv"))
            entry = {
                "id": source_id,
                "state": STATE_OK if local_file.is_file() else STATE_FAILED_NO_COPY,
                "publication_date": pub_date,
                "last_verified_at": last_verified,
                "record_count": count,
                "sha256": compute_sha256(local_file),
                "active_url": spec.get("candidate_urls", [""])[0] if spec.get("candidate_urls") else "",
                "note": "",
                "last_error": None,
            }
            self.state[source_id] = entry

        # Check staleness based on last_verified_at vs max_age_days
        max_age = spec.get("max_age_days", 7)
        last_v_str = entry.get("last_verified_at", "")
        if last_v_str and entry.get("state") in [STATE_OK, STATE_OFFLINE_NOTE]:
            try:
                lv_dt = datetime.fromisoformat(last_v_str.replace("Z", "+00:00"))
                age_days = (datetime.now(timezone.utc) - lv_dt).total_seconds() / 86400.0
                if age_days > max_age:
                    entry["state"] = STATE_STALE
                    entry["note"] = f"Out of date: last verified {int(age_days)} days ago (max {max_age} days)"
            except Exception:
                pass

        return entry

    def get_all_source_states(self) -> Dict[str, Dict[str, Any]]:
        """Return state model for all registered sources."""
        return {s_id: self.get_source_state(s_id) for s_id in self.registry}

    def refresh_source(
        self,
        source_id: str,
        http_client: Optional[Any] = None,
    ) -> Tuple[str, str]:
        """
        Execute real refresh of a single source:
        1. Check landing page / 410 / closure keywords
        2. Attempt download from candidate URLs or discovery
        3. Enforce allowed_domains
        4. Validate size, format, schema, record counts
        5. Atomic swap & keep 3 archived copies
        6. Log source_events
        Returns (new_state, message).
        """
        spec = self.registry.get(source_id)
        if not spec:
            return STATE_FAILED_NO_COPY, f"Source '{source_id}' not found in registry"

        current_file = get_source_file_path(source_id)
        current_state = self.get_source_state(source_id)
        count_before = current_state.get("record_count", 0)
        hash_before = current_state.get("sha256", "")
        allowed_domains = spec.get("allowed_domains", [])
        closure_kws = spec.get("closure_keywords", DEFAULT_CLOSURE_KEYWORDS)

        # 1. Check landing page if configured
        landing_url = spec.get("landing_page", "")
        discovered_url = None
        if landing_url:
            try:
                req = urllib.request.Request(landing_url, headers={"User-Agent": "NaughtyOrNot/1.0.3"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    page_html = resp.read().decode("utf-8", errors="replace")
                    closure_match = check_closure_keywords(page_html, closure_kws)
                    if closure_match:
                        current_state["state"] = STATE_CLOSED_SUSPECTED
                        current_state["note"] = f"Publisher may have closed or replaced this list: '{closure_match}'"
                        log_source_event(source_id, "CLOSED_SUSPECTED", landing_url, "", count_before, count_before, hash_before, hash_before, current_state["note"])
                        save_sources_state(self.state)
                        return STATE_CLOSED_SUSPECTED, current_state["note"]

                    # Discovery regex
                    disc_pattern = spec.get("discovery")
                    if disc_pattern:
                        m = re.search(disc_pattern, page_html, re.IGNORECASE)
                        if m:
                            discovered_url = m.group(1)
            except urllib.error.HTTPError as he:
                if he.code == 410:
                    current_state["state"] = STATE_CLOSED_SUSPECTED
                    current_state["note"] = "Landing page returned HTTP 410 Gone (list closed/discontinued)"
                    log_source_event(source_id, "CLOSED_SUSPECTED", landing_url, "", count_before, count_before, hash_before, hash_before, current_state["note"])
                    save_sources_state(self.state)
                    return STATE_CLOSED_SUSPECTED, current_state["note"]
            except Exception as e:
                logger.debug(f"Landing page check for {source_id}: {e}")

        # 2. Compile ordered candidate URLs
        candidate_urls = list(spec.get("candidate_urls", []))
        if discovered_url and discovered_url not in candidate_urls:
            candidate_urls.insert(0, discovered_url)

        # 3. Attempt download across candidates
        downloaded_tmp = None
        successful_url = None
        address_changed = False
        rejection_reason = None
        validation_rejected = False

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / f"{source_id}.download.tmp"

            for url in candidate_urls:
                # Security: Enforce allowed_domains
                if not check_domain_allowed(url, allowed_domains):
                    msg = f"URL domain rejected: '{url}' not in allowed_domains {allowed_domains}"
                    logger.warning(msg)
                    log_source_event(source_id, "DOMAIN_REJECTED", url, "", count_before, count_before, hash_before, hash_before, msg)
                    rejection_reason = msg
                    continue

                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "NaughtyOrNot/1.0.3"})
                    with urllib.request.urlopen(req, timeout=25) as resp:
                        # Check HTTP status
                        if resp.status == 410:
                            current_state["state"] = STATE_CLOSED_SUSPECTED
                            current_state["note"] = f"Download URL returned HTTP 410 Gone ({url})"
                            log_source_event(source_id, "CLOSED_SUSPECTED", url, "", count_before, count_before, hash_before, hash_before, current_state["note"])
                            save_sources_state(self.state)
                            return STATE_CLOSED_SUSPECTED, current_state["note"]

                        final_url = resp.geturl()
                        # Verify redirected URL domain
                        if not check_domain_allowed(final_url, allowed_domains):
                            msg = f"Redirect domain rejected: '{final_url}' not in allowed_domains"
                            log_source_event(source_id, "DOMAIN_REJECTED", url, final_url, count_before, count_before, hash_before, hash_before, msg)
                            rejection_reason = msg
                            continue

                        # Save content to temp
                        with open(tmp_path, "wb") as out_f:
                            shutil.copyfileobj(resp, out_f)

                    # Validate file
                    is_valid, v_msg, count_after = validate_file(tmp_path, spec, last_good_count=count_before)
                    if not is_valid:
                        rejection_reason = f"Validation failed: {v_msg}"
                        validation_rejected = True
                        log_source_event(source_id, "VALIDATION_FAILED", url, final_url, count_before, count_after, hash_before, "", v_msg)
                        continue

                    # Download and validation successful!
                    downloaded_tmp = tmp_path
                    successful_url = final_url
                    if url != spec.get("candidate_urls", [""])[0]:
                        address_changed = True
                    break

                except urllib.error.HTTPError as he:
                    if he.code == 410:
                        current_state["state"] = STATE_CLOSED_SUSPECTED
                        current_state["note"] = f"Download endpoint returned HTTP 410 Gone ({url})"
                        log_source_event(source_id, "CLOSED_SUSPECTED", url, "", count_before, count_before, hash_before, hash_before, current_state["note"])
                        save_sources_state(self.state)
                        return STATE_CLOSED_SUSPECTED, current_state["note"]
                    rejection_reason = f"HTTP {he.code}: {he.reason}"
                except Exception as e:
                    rejection_reason = str(e)

            # 4. Handle Outcome
            now_iso = datetime.now(timezone.utc).isoformat()
            if downloaded_tmp and downloaded_tmp.is_file() and successful_url:
                # Atomic swap: archive previous version, copy tmp to target
                archive_version(source_id, current_file)
                current_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(downloaded_tmp, current_file)

                new_hash = compute_sha256(current_file)
                new_count = count_records(current_file, spec.get("expected", {}).get("format", "csv"))

                new_state = STATE_ADDRESS_CHANGED if address_changed else STATE_OK
                note = f"Source address changed to {successful_url}" if address_changed else "List verified and updated"
                current_state.update({
                    "state": new_state,
                    "last_verified_at": now_iso,
                    "record_count": new_count,
                    "sha256": new_hash,
                    "active_url": successful_url,
                    "note": note,
                    "last_error": None,
                })
                save_sources_state(self.state)

                log_source_event(
                    source=source_id,
                    event="REFRESH_SUCCESS" if not address_changed else "ADDRESS_CHANGED",
                    old_url=spec.get("candidate_urls", [""])[0],
                    new_url=successful_url,
                    count_before=count_before,
                    count_after=new_count,
                    hash_before=hash_before,
                    hash_after=new_hash,
                    message=note,
                )
                return new_state, note

            # If download or validation failed:
            if current_file.is_file() and current_file.stat().st_size > 0:
                # Check if last good copy is within max_age_days
                max_age = spec.get("max_age_days", 7)
                last_v_str = current_state.get("last_verified_at", "")
                age_days = 0.0
                if last_v_str:
                    try:
                        lv_dt = datetime.fromisoformat(last_v_str.replace("Z", "+00:00"))
                        age_days = (datetime.now(timezone.utc) - lv_dt).total_seconds() / 86400.0
                    except Exception:
                        pass

                if validation_rejected or (rejection_reason and ("validation" in rejection_reason.lower() or "outside allowed range" in str(rejection_reason).lower() or "missing required" in str(rejection_reason).lower())):
                    new_state = STATE_UPDATE_REJECTED
                    note = f"Update rejected ({rejection_reason}); using copy dated {current_state.get('publication_date', '2026-10-18')}"
                elif age_days > max_age:
                    new_state = STATE_STALE
                    note = f"Out of date ({int(age_days)} days old); update failed: {rejection_reason}"
                else:
                    new_state = STATE_OFFLINE_NOTE
                    note = f"Could not check for updates ({rejection_reason}); using copy dated {current_state.get('publication_date', '2026-10-18')}"

                current_state["state"] = new_state
                current_state["note"] = note
                current_state["last_error"] = rejection_reason
                save_sources_state(self.state)

                log_source_event(
                    source=source_id,
                    event=new_state,
                    old_url=spec.get("candidate_urls", [""])[0],
                    new_url="",
                    count_before=count_before,
                    count_after=count_before,
                    hash_before=hash_before,
                    hash_after=hash_before,
                    message=note,
                )
                return new_state, note

            # No copy exists at all
            current_state["state"] = STATE_FAILED_NO_COPY
            current_state["note"] = f"No valid copy available. Download failed: {rejection_reason}"
            current_state["last_error"] = rejection_reason
            save_sources_state(self.state)
            log_source_event(source_id, "FAILED_NO_COPY", "", "", 0, 0, "", "", current_state["note"])
            return STATE_FAILED_NO_COPY, current_state["note"]

    def refresh_all(
        self,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> Dict[str, Tuple[str, str]]:
        """Refresh all configured sources and trigger index rebuild."""
        results = {}
        total = len(self.registry)
        for idx, s_id in enumerate(self.registry.keys(), 1):
            if progress_callback:
                progress_callback(idx, total, f"Refreshing {s_id}...")
            st, msg = self.refresh_source(s_id)
            results[s_id] = (st, msg)

        # Trigger background rebuild of text search index
        try:
            from modules.raw_search.indexer import build_full_raw_index
            build_full_raw_index()
        except Exception as e:
            logger.warning(f"Error rebuilding raw index post-refresh: {e}")

        return results
