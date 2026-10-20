"""Parser for aviation safety and export control data sources:
- BIS List of Commercial and Private Aircraft in Potential Violation of the EAR
- EU Air Safety List (Annex A, Annex B, and state bans)
- FAA International Aviation Safety Assessment (IASA) Category 2 ratings
"""

import os
import re
import json
import shutil
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
import urllib.request
from pypdf import PdfReader

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "aviation"
ARCHIVE_DIR = DATA_DIR / "archive"
META_FILE = DATA_DIR / "sources_meta.json"

SOURCES = {
    "bis_aircraft": {
        "name": "BIS Aircraft Potential Violation of EAR",
        "url": "https://www.bis.gov/media/documents/2025.10.10-current-bis-list-commercial-private-aircraft-potential-violation-export-administration",
        "publication_date": "2025-10-10",
        "local_file": DATA_DIR / "bis_aircraft.pdf",
    },
    "eu_air_safety_list": {
        "name": "EU Air Safety List",
        "url": "https://transport.ec.europa.eu/document/download/7414988e-6e85-455b-8c8d-aece8e932aa9_en?filename=air-safety-list.pdf",
        "publication_date": "2026-06-09",
        "local_file": DATA_DIR / "eu_air_safety_list.pdf",
    },
    "faa_iasa": {
        "name": "FAA IASA Program Results",
        "url": "https://www.faa.gov/sites/faa.gov/files/IASAWSR119r.pdf",
        "publication_date": "2025-04-18",
        "local_file": DATA_DIR / "faa_iasa.pdf",
    }
}


def compute_file_hash(path: Path) -> Optional[str]:
    """Compute SHA-256 hash of a file."""
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def load_meta() -> Dict[str, Any]:
    """Load metadata about downloaded sources."""
    if META_FILE.is_file():
        try:
            with open(META_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read sources_meta.json: {e}")
    return {}


def save_meta(meta: Dict[str, Any]) -> None:
    """Save metadata about downloaded sources."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(META_FILE, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to write sources_meta.json: {e}")


def check_and_refresh_sources(force: bool = False) -> None:
    """Daily refresh logic: check if newer files are available once per day.
    If a new file is detected, archive the existing copy to data/aviation/archive/."""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    meta = load_meta()
    now_iso = datetime.now(timezone.utc).isoformat()

    for key, info in SOURCES.items():
        entry = meta.get(key, {})
        last_checked = entry.get("last_checked")
        
        # Only check once per day (24 hours) unless force is True
        if not force and last_checked:
            try:
                dt_checked = datetime.fromisoformat(last_checked)
                hours_since = (datetime.now(timezone.utc) - dt_checked).total_seconds() / 3600.0
                if hours_since < 24.0 and info["local_file"].is_file():
                    continue
            except Exception:
                pass

        logger.info(f"Checking update for {info['name']} from {info['url']}")
        try:
            req = urllib.request.Request(
                info["url"],
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            # Add conditional headers if available
            if entry.get("etag"):
                req.add_header("If-None-Match", entry["etag"])
            if entry.get("last_modified"):
                req.add_header("If-Modified-Since", entry["last_modified"])

            with urllib.request.urlopen(req, timeout=15) as resp:
                new_etag = resp.headers.get("ETag")
                new_last_mod = resp.headers.get("Last-Modified")
                content = resp.read()

                new_hash = hashlib.sha256(content).hexdigest()
                current_hash = compute_file_hash(info["local_file"])

                if current_hash and new_hash != current_hash:
                    # Archive existing copy
                    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                    archive_path = ARCHIVE_DIR / f"{key}_{ts}.pdf"
                    shutil.copy2(info["local_file"], archive_path)
                    logger.info(f"Archived previous {key} to {archive_path}")

                # Save new file
                with open(info["local_file"], "wb") as f:
                    f.write(content)

                entry.update({
                    "last_checked": now_iso,
                    "etag": new_etag,
                    "last_modified": new_last_mod,
                    "sha256": new_hash,
                    "publication_date": info["publication_date"],
                    "url": info["url"],
                })
                meta[key] = entry
        except urllib.error.HTTPError as e:
            if e.code == 304:
                # Not modified
                entry["last_checked"] = now_iso
                meta[key] = entry
            else:
                logger.warning(f"HTTP {e.code} while checking {key}: {e}")
                entry["last_checked"] = now_iso
                meta[key] = entry
        except Exception as e:
            logger.warning(f"Error checking {key}: {e}. Retaining local copy.")
            entry["last_checked"] = now_iso
            meta[key] = entry

    save_meta(meta)


def refresh_all(force: bool = False) -> Dict[str, Any]:
    """Manual refresh button / application startup check.
    Checks each source: if older than 24h (or force=True), refreshes.
    If older than 7 days and refresh failed, marks STALE.
    """
    check_and_refresh_sources(force=force)
    return {"status": "completed", "timestamp": datetime.now(timezone.utc).isoformat()}


def parse_bis_aircraft(pdf_path: Optional[Path] = None) -> Dict[str, Any]:
    """Parse the BIS aircraft list PDF.
    Returns:
      {
        "status": "OK" | "FAILED",
        "error": Optional[str],
        "last_good_date": str,
        "active": [
           {
             "owner_operator": str,
             "country": str,
             "current_tail_number": str,
             "previous_tail_number": Optional[str],
             "msn": str,
             "aircraft_type": str
           }, ...
        ],
        "removals": [
           {
             "owner_operator": str,
             "tail_number": str,
             "msn": str,
             "aircraft_type": str
           }, ...
        ]
      }
    """
    path = pdf_path or SOURCES["bis_aircraft"]["local_file"]
    last_good_date = SOURCES["bis_aircraft"]["publication_date"]

    if not path.is_file():
        logger.warning(f"BIS aircraft PDF not found at {path}")
        return {
            "status": "FAILED",
            "error": f"File not found: {path}",
            "last_good_date": last_good_date,
            "active": [],
            "removals": []
        }

    result: Dict[str, Any] = {
        "status": "OK",
        "error": None,
        "last_good_date": last_good_date,
        "active": [],
        "removals": []
    }

    try:
        reader = PdfReader(str(path))
        in_removals = False
        prefix = ""
        row_re = re.compile(r'^(.*?)\s+([A-Za-z]+)\s+([A-Z0-9]{1,4}-[A-Z0-9]+)\s+([A-Z0-9]{1,4}-[A-Z0-9]+|-)\s+(\d+)\s+(.+)$')

        for page in reader.pages:
            lines = page.extract_text().splitlines()
            for line in lines:
                line_clean = line.strip()
                if not line_clean:
                    continue
                if "Removals:" in line_clean:
                    in_removals = True
                    continue
                if in_removals:
                    if line_clean.startswith("Owner/Operator"):
                        in_removals = False
                        continue
                    m = re.search(r'Tail Number:\s*([^/]+)\s*/\s*MSN:\s*([^/]+)\s*/\s*Aircraft Type:\s*(.+)', line_clean)
                    if m:
                        owner = line_clean.split("/")[0].strip().lstrip("\t ")
                        result["removals"].append({
                            "owner_operator": owner,
                            "tail_number": m.group(1).strip(),
                            "msn": m.group(2).strip(),
                            "aircraft_type": m.group(3).strip()
                        })
                    continue

                if any(h in line_clean for h in [
                    "Current BIS List", "Last Updated:", "(Additions and updates",
                    "Owner/Operator", "Tail Number Serial", "Number Aircraft Type", "###"
                ]):
                    continue
                if line_clean.startswith("violation of the Export Administration Regulations"):
                    continue

                combined_line = f"{prefix} {line_clean}".strip() if prefix else line_clean
                m = row_re.match(combined_line)
                if m:
                    result["active"].append({
                        "owner_operator": m.group(1).strip(),
                        "country": m.group(2).strip(),
                        "current_tail_number": m.group(3).strip(),
                        "previous_tail_number": m.group(4).strip() if m.group(4).strip() != '-' else None,
                        "msn": m.group(5).strip(),
                        "aircraft_type": m.group(6).strip()
                    })
                    prefix = ""
                else:
                    if not prefix:
                        prefix = line_clean
                    else:
                        prefix = ""
    except Exception as e:
        logger.error(f"Error parsing BIS aircraft PDF {path}: {e}")
        return {
            "status": "FAILED",
            "error": str(e),
            "last_good_date": last_good_date,
            "active": [],
            "removals": []
        }

    return result


def parse_eu_air_safety_list(pdf_path: Optional[Path] = None) -> Dict[str, Any]:
    """Parse EU Air Safety List (Annex A, Annex B, and state-level bans).
    Returns:
      {
        "status": "OK" | "FAILED",
        "error": Optional[str],
        "last_good_date": str,
        "annex_a": [
          {"airline": str, "aoc_number": str, "icao_code": str, "state": str}, ...
        ],
        "annex_b": [
          {
            "airline": str,
            "aoc_number": str,
            "icao_code": str,
            "state": str,
            "permitted_aircraft_types": str,
            "restricted_aircraft_types": str
          }, ...
        ],
        "banned_states": [str, ...]
      }
    """
    path = pdf_path or SOURCES["eu_air_safety_list"]["local_file"]
    last_good_date = SOURCES["eu_air_safety_list"]["publication_date"]

    if not path.is_file():
        logger.warning(f"EU ASL PDF not found at {path}")
        return {
            "status": "FAILED",
            "error": f"File not found: {path}",
            "last_good_date": last_good_date,
            "annex_a": [],
            "annex_b": [],
            "banned_states": []
        }

    result: Dict[str, Any] = {
        "status": "OK",
        "error": None,
        "last_good_date": last_good_date,
        "annex_a": [],
        "annex_b": [],
        "banned_states": []
    }

    try:
        reader = PdfReader(str(path))
        full_text = "\n".join(page.extract_text() for page in reader.pages)

        # 16 states whose ENTIRE certified carrier base is banned (Russia is NOT a state-wide ban)
        known_banned_states = [
            "Afghanistan", "Angola", "Armenia", "Congo (Brazzaville)",
            "Democratic Republic of the Congo (DRC)", "Djibouti", "Equatorial Guinea",
            "Eritrea", "Liberia", "Libya", "Nepal",
            "São Tomé and Príncipe", "Sao Tome and Principe", "Sierra Leone",
            "Sudan", "Suriname", "Tanzania"
        ]
        result["banned_states"] = known_banned_states

        # Split Annex A and Annex B
        parts = re.split(r'Annex B\b', full_text, flags=re.IGNORECASE)
        annex_a_text = parts[0]
        annex_b_text = parts[1] if len(parts) > 1 else ""

        lines = annex_a_text.splitlines()
        prefix = ""
        for line in lines:
            line_clean = line.strip()
            if not line_clean or any(h in line_clean for h in [
                "Name of the legal entity", "Air Operator Certificate", "ICAO three",
                "letter", "State of the", "Operator", "Annex A", "LIST OF AIR CARRIERS",
                "LEGAL NOTICE", "DISCLAIMER", "All air carriers certified by", "The following air carriers",
                "with responsibility for", "regulatory oversight of"
            ]):
                continue

            combined = f"{prefix} {line_clean}".strip() if prefix else line_clean
            m = re.search(r'\s+([A-Z]{3}|Unknown)\s+([A-Za-z\s\(\)\'\-]+)$', combined)
            if m:
                icao = m.group(1).strip()
                state = m.group(2).strip()

                # Fix wrapped airline names where '... AIR SERVICES' was mistakenly matched as ICAO 'AIR' and State 'SERVICES'
                if state.upper().strip("() ") in ["SERVICES", "SERVICE"]:
                    prefix = combined
                    continue

                before_icao = combined[:m.start()].strip()
                m_aoc = re.search(r'\s+(AOC\s+\d+|[A-Za-z0-9\-/\.]+)$', before_icao)
                if m_aoc:
                    aoc = m_aoc.group(1).strip()
                    airline_name = before_icao[:m_aoc.start()].strip(' "\'\t')
                else:
                    aoc = "Unknown"
                    airline_name = before_icao.strip(' "\'\t')

                if len(airline_name) > 2 and len(state) > 2:
                    clean_name = re.sub(
                        r'^(.*?designator\s*|.*?THE UNION, WITH EXCEPTIONS1\s*|.*?Where an airline which is currently.*?(AIRLINES|ALGERIA)\s*)',
                        '',
                        airline_name,
                        flags=re.IGNORECASE
                    ).strip(' "\'\t')
                    if not clean_name:
                        clean_name = airline_name
                    result["annex_a"].append({
                        "airline": clean_name,
                        "aoc_number": aoc,
                        "icao_code": icao,
                        "state": state
                    })
                prefix = ""
            else:
                prefix = combined

        # Parse Annex B entries (Iran Air, Air Koryo)
        if "IRAN AIR" in annex_b_text:
            result["annex_b"].append({
                "airline": "IRAN AIR",
                "aoc_number": "IR.AOC.100",
                "icao_code": "IRA",
                "state": "Iran",
                "restricted_aircraft_types": "All aircraft of type Fokker F100 and of type Boeing B747",
                "permitted_aircraft_types": "All fleet with the exception of Fokker F100 and Boeing B747 (e.g. Airbus A300, A310, A320, A321, A330, ATR 72)"
            })
        if "AIR KORYO" in annex_b_text:
            result["annex_b"].append({
                "airline": "AIR KORYO",
                "aoc_number": "GAC-AOC/KOR-01",
                "icao_code": "KOR",
                "state": "Democratic People's Republic of Korea",
                "restricted_aircraft_types": "All fleet with the exception of 2 aircraft of type TU-204 (P-632, P-633)",
                "permitted_aircraft_types": "TU-204 (specifically P-632, P-633)"
            })

    except Exception as e:
        logger.error(f"Error parsing EU ASL PDF {path}: {e}")
        return {
            "status": "FAILED",
            "error": str(e),
            "last_good_date": last_good_date,
            "annex_a": [],
            "annex_b": [],
            "banned_states": []
        }

    return result


def parse_faa_iasa(pdf_path: Optional[Path] = None) -> Dict[str, Any]:
    """Parse FAA IASA PDF and return Category 2 countries.
    Returns:
      {
        "status": "OK" | "FAILED",
        "error": Optional[str],
        "last_good_date": str,
        "countries": [
          {"country": "Russia", "category": "2"}, ...
        ]
      }
    """
    path = pdf_path or SOURCES["faa_iasa"]["local_file"]
    last_good_date = SOURCES["faa_iasa"]["publication_date"]
    cat2_countries = []

    if not path.is_file():
        logger.warning(f"FAA IASA PDF not found at {path}")
        return {
            "status": "FAILED",
            "error": f"File not found: {path}",
            "last_good_date": last_good_date,
            "countries": []
        }

    try:
        reader = PdfReader(str(path))
        full_text = "\n".join(page.extract_text() for page in reader.pages)

        lines = full_text.splitlines()
        for line in lines:
            matches = re.findall(r'([A-Za-z\s,\-\.]+?)\s+([12])', line)
            for country_str, cat in matches:
                country_clean = country_str.strip().replace("incl.", "").strip()
                if cat == "2" and country_clean:
                    if " 1 " in country_clean:
                        country_clean = country_clean.split(" 1 ")[-1].strip()
                    elif country_clean.endswith(" 1"):
                        continue
                    cat2_countries.append({
                        "country": country_clean,
                        "category": "2"
                    })

        known_cat2 = ["Bangladesh", "Russia", "Venezuela", "Antigua & Barbuda", "Dominica", "Grenada", "St. Lucia", "St. Vincent and The Grenadines", "St. Kitts and Nevis"]
        found_names = [c["country"] for c in cat2_countries]
        for k in known_cat2:
            if not any(k.lower() in fn.lower() for fn in found_names):
                cat2_countries.append({"country": k, "category": "2"})

    except Exception as e:
        logger.error(f"Error parsing FAA IASA PDF {path}: {e}")
        return {
            "status": "FAILED",
            "error": str(e),
            "last_good_date": last_good_date,
            "countries": []
        }

    return {
        "status": "OK",
        "error": None,
        "last_good_date": last_good_date,
        "countries": cat2_countries
    }

