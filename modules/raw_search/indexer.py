"""Local Raw Index builder for Naughty or not.
Indexes official raw lists into SQLite FTS5 for full-text raw searches.
"""

import csv
import hashlib
import json
import logging
from pathlib import Path
import re
import sqlite3
import sys
import unicodedata
import xml.etree.ElementTree as ET
from typing import Any, Callable, Dict, List, Optional, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw")
def _resolve_index_db_path() -> Path:
    try:
        from modules.common.paths import get_index_db_path
        return get_index_db_path()
    except Exception:
        return Path("data/raw_index.db")

INDEX_DB_PATH = _resolve_index_db_path()


def normalize_text_for_index(text: str) -> str:
    """Normalize text: flatten whitespaces, remove null bytes."""
    if not text:
        return ""
    return " ".join(str(text).replace("\x00", " ").split())


def get_connection(db_path: Path = INDEX_DB_PATH) -> sqlite3.Connection:
    """Open or create the SQLite FTS5 database."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    return con


def init_db(con: sqlite3.Connection) -> None:
    """Initialize the FTS5 virtual table and metadata tables."""
    cur = con.cursor()
    cur.execute("DROP TABLE IF EXISTS raw_index;")
    cur.execute("DROP TABLE IF EXISTS source_meta;")
    
    cur.execute("""
    CREATE TABLE source_meta (
        source TEXT PRIMARY KEY,
        status TEXT,
        record_count INTEGER,
        list_date TEXT,
        file_path TEXT,
        file_hash TEXT,
        last_indexed TEXT
    );
    """)

    # FTS5 virtual table with trigram tokenizer (with fallback to unicode61)
    try:
        cur.execute("""
        CREATE VIRTUAL TABLE raw_index USING fts5(
            source UNINDEXED,
            record_id,
            primary_name,
            all_names,
            all_text,
            source_url UNINDEXED,
            list_date UNINDEXED,
            tokenize='trigram'
        );
        """)
    except sqlite3.OperationalError:
        cur.execute("""
        CREATE VIRTUAL TABLE raw_index USING fts5(
            source UNINDEXED,
            record_id,
            primary_name,
            all_names,
            all_text,
            source_url UNINDEXED,
            list_date UNINDEXED,
            tokenize='unicode61 remove_diacritics 2'
        );
        """)
    con.commit()



def parse_ofac_sdn(path: Path) -> List[Tuple[str, str, str, str, str, str, str]]:
    """Parse US OFAC SDN CSV."""
    records = []
    if not path.is_file():
        return records
    list_date = "2026-10-21"
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            ent_num = row[0].strip()
            name = row[1].strip() if len(row) > 1 else ""
            ent_type = row[2].strip() if len(row) > 2 else ""
            program = row[3].strip() if len(row) > 3 else ""
            remarks = row[11].strip() if len(row) > 11 else ""
            all_text = " ".join([x for x in row if x and x != "-0- "])
            source_url = f"https://sanctionssearch.ofac.treas.gov/Details.aspx?id={ent_num}"
            records.append((
                "us_ofac",
                ent_num,
                name,
                name,
                normalize_text_for_index(all_text),
                source_url,
                list_date
            ))
    return records


def parse_ofac_cons(path: Path) -> List[Tuple[str, str, str, str, str, str, str]]:
    """Parse US OFAC Consolidated XML if present."""
    records = []
    if not path.is_file():
        return records
    list_date = "2026-10-19"
    try:
        from datetime import datetime
        tree = ET.parse(path)
        pub_date_el = tree.getroot().findtext(".//{*}Publish_Date", "") or tree.getroot().findtext(".//Publish_Date", "")
        if pub_date_el:
            try:
                list_date = datetime.strptime(pub_date_el.strip(), "%m/%d/%Y").strftime("%Y-%m-%d")
            except Exception:
                pass
        for entry in tree.getroot().iter():
            tag = entry.tag.split("}")[-1]
            if tag in ["sdnEntry", "consolidatedEntry"]:
                ent_num = entry.findtext(".//{*}uid", "") or entry.findtext(".//uid", "") or entry.findtext("uid", "")
                last_name = entry.findtext(".//{*}lastName", "") or entry.findtext("lastName", "")
                first_name = entry.findtext(".//{*}firstName", "") or entry.findtext("firstName", "")
                primary_name = f"{first_name} {last_name}".strip()
                all_text = " ".join(entry.itertext())
                source_url = f"https://sanctionssearch.ofac.treas.gov/Details.aspx?id={ent_num}"
                records.append((
                    "us_ofac",
                    ent_num,
                    primary_name,
                    primary_name,
                    normalize_text_for_index(all_text),
                    source_url,
                    list_date
                ))
    except Exception as e:
        logger.warning(f"Error parsing OFAC Consolidated XML: {e}")
    return records


def parse_us_csl(path: Path) -> List[Tuple[str, str, str, str, str, str, str]]:
    """Parse US Consolidated Screening List (CSL) CSV."""
    records = []
    if not path.is_file():
        return records
    list_date = "2026-10-27"
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        try:
            headers = next(reader)
        except StopIteration:
            return records
        for row in reader:
            if not row:
                continue
            rec_id = row[0].strip() if len(row) > 0 else ""
            ent_num = row[2].strip() if len(row) > 2 else ""
            name = row[5].strip() if len(row) > 5 else ""
            alt_names = row[22].strip() if len(row) > 22 else ""
            combined_names = f"{name}; {alt_names}" if alt_names else name
            all_text = " ".join(row)
            source_url = "https://www.trade.gov/data-visualization/csl-search"
            effective_id = rec_id or ent_num
            records.append((
                "us_csl",
                effective_id,
                name,
                combined_names,
                normalize_text_for_index(all_text),
                source_url,
                list_date
            ))
    return records


def parse_uk_csl(path: Path) -> List[Tuple[str, str, str, str, str, str, str]]:
    """Parse UK Sanctions List CSV."""
    records = []
    if not path.is_file():
        return records
    list_date = "2026-10-27"
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        line1 = f.readline()
        m = re.search(r"Report Date:\s*([0-3]?\d)-([A-Za-z]{3})-(202\d)", line1)
        if m:
            try:
                from datetime import datetime
                dt = datetime.strptime(f"{m.group(1)}-{m.group(2)}-{m.group(3)}", "%d-%b-%Y")
                list_date = dt.strftime("%Y-%m-%d")
            except Exception:
                pass
        f.seek(0)
        reader = csv.reader(f)
        try:
            next(reader) # metadata row
            headers = next(reader)
        except StopIteration:
            return records
        for row in reader:
            if not row:
                continue
            rec_id = row[1].strip() if len(row) > 1 else ""
            group_id = row[2].strip() if len(row) > 2 else ""
            name = row[4].strip() if len(row) > 4 else ""
            other_names = [row[i].strip() for i in range(5, 10) if len(row) > i and row[i].strip()]
            all_names_list = [name] + other_names
            all_names_str = "; ".join(filter(None, all_names_list))
            all_text = " ".join(row)
            source_url = "https://search-uk-sanctions-list.service.gov.uk/"
            records.append((
                "uk_csl",
                rec_id or group_id,
                name,
                all_names_str,
                normalize_text_for_index(all_text),
                source_url,
                list_date
            ))
    return records


def parse_eu_csl(path: Path) -> List[Tuple[str, str, str, str, str, str, str]]:
    """Parse EU Consolidated Sanctions XML."""
    records = []
    if not path.is_file():
        return records
    list_date = "2026-10-23"
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            chunk = f.read(4096)
            m = re.search(r'generationDate="([^"]+)"', chunk)
            if m:
                list_date = m.group(1)[:10]
    except Exception:
        pass
    try:
        for event, elem in ET.iterparse(str(path), events=("end",)):
            tag = elem.tag.split("}")[-1]
            if tag == "sanctionEntity":
                logical_id = elem.attrib.get("logicalId", "")
                eu_ref = elem.attrib.get("euReferenceNumber", "")
                names = []
                for name_alias in elem.findall(".//{*}nameAlias"):
                    whole = name_alias.attrib.get("wholeName", "")
                    if whole:
                        names.append(whole)
                primary_name = names[0] if names else ""
                all_names_str = "; ".join(names)
                all_text = " ".join(elem.itertext())
                source_url = "https://www.sanctionsmap.eu/#/main"
                rec_id = logical_id or eu_ref
                records.append((
                    "eu_csl",
                    rec_id,
                    primary_name,
                    all_names_str,
                    normalize_text_for_index(all_text),
                    source_url,
                    list_date
                ))
                elem.clear()
    except Exception as e:
        logger.warning(f"Error parsing EU CSL XML: {e}")
    return records


def parse_un_csl(path: Path) -> List[Tuple[str, str, str, str, str, str, str]]:
    """Parse UN Security Council Consolidated List XML."""
    records = []
    if not path.is_file():
        return records
    list_date = "2026-10-26"
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            chunk = f.read(4096)
            m = re.search(r'dateGenerated="([^"]+)"', chunk)
            if m:
                list_date = m.group(1)[:10]
    except Exception:
        pass
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        for item in root.iter():
            tag = item.tag.split("}")[-1]
            if tag in ["INDIVIDUAL", "ENTITY"]:
                data_id = item.findtext("DATAID", "") or item.findtext(".//DATAID", "")
                first_name = item.findtext("FIRST_NAME", "") or item.findtext(".//FIRST_NAME", "") or ""
                second_name = item.findtext("SECOND_NAME", "") or item.findtext(".//SECOND_NAME", "") or ""
                third_name = item.findtext("THIRD_NAME", "") or item.findtext(".//THIRD_NAME", "") or ""
                fourth_name = item.findtext("FOURTH_NAME", "") or item.findtext(".//FOURTH_NAME", "") or ""
                full_name = " ".join(filter(None, [first_name, second_name, third_name, fourth_name])).strip()
                
                aliases = []
                for alias_node in item.iter():
                    if alias_node.tag.split("}")[-1] in ["INDIVIDUAL_ALIAS", "ENTITY_ALIAS"]:
                        alias_name = alias_node.findtext("ALIAS_NAME", "") or ""
                        if alias_name:
                            aliases.append(alias_name)
                all_names_str = "; ".join([full_name] + aliases) if aliases else full_name
                all_text = " ".join(item.itertext())
                source_url = "https://main.un.org/securitycouncil/en/content/un-sc-consolidated-list"
                records.append((
                    "un_csl",
                    data_id,
                    full_name,
                    all_names_str,
                    normalize_text_for_index(all_text),
                    source_url,
                    list_date
                ))
    except Exception as e:
        logger.warning(f"Error parsing UN CSL XML: {e}")
    return records


def parse_bis_aircraft_records() -> List[Tuple[str, str, str, str, str, str, str]]:
    """Parse BIS Commercial and Private Aircraft in potential violation."""
    records = []
    from modules.aviation.parser import parse_bis_aircraft
    res = parse_bis_aircraft(Path("data/aviation/bis_aircraft.pdf"))
    active = res.get("active", [])
    for row in active:
        owner = row.get("owner_operator", "")
        cur_tail = row.get("current_tail_number", "")
        prev_tail = row.get("previous_tail_number") or ""
        msn = str(row.get("msn", ""))
        ac_type = row.get("aircraft_type", "")
        rec_id = cur_tail or prev_tail or msn
        p_name = f"{owner} ({cur_tail})" if cur_tail else owner
        all_names = f"{owner}; {cur_tail}; {prev_tail}; MSN {msn}; {ac_type}"
        all_text = f"Owner: {owner} Country: {row.get('country')} Current Tail: {cur_tail} Previous Tail: {prev_tail} MSN: {msn} Type: {ac_type}"
        source_url = "https://www.bis.gov/media/documents/2025.10.10-current-bis-list-commercial-private-aircraft-potential-violation-export-administration"
        records.append((
            "bis_aircraft",
            rec_id,
            p_name,
            all_names,
            normalize_text_for_index(all_text),
            source_url,
            "2025-10-10"
        ))
    return records


def parse_eu_air_safety_records() -> List[Tuple[str, str, str, str, str, str, str]]:
    """Parse EU Air Safety List banned carriers."""
    records = []
    from modules.aviation.parser import parse_eu_air_safety_list
    res = parse_eu_air_safety_list(Path("data/aviation/eu_air_safety_list.pdf"))
    for row in res.get("annex_a", []):
        airline = row.get("airline", "")
        aoc = row.get("aoc_number", "")
        icao = row.get("icao_code", "")
        state = row.get("state", "")
        all_text = f"Airline: {airline} AOC: {aoc} ICAO: {icao} State: {state} Annex A Banned"
        records.append((
            "eu_air_safety_list",
            aoc or airline,
            airline,
            f"{airline}; {icao}",
            normalize_text_for_index(all_text),
            "https://transport.ec.europa.eu/transport-themes/eu-air-safety-list_en",
            "2026-06-09"
        ))
    for row in res.get("annex_b", []):
        airline = row.get("airline", "")
        state = row.get("state", "")
        restrictions = row.get("restricted_aircraft", "")
        all_text = f"Airline: {airline} State: {state} Restrictions: {restrictions} Annex B"
        records.append((
            "eu_air_safety_list",
            airline,
            airline,
            airline,
            normalize_text_for_index(all_text),
            "https://transport.ec.europa.eu/transport-themes/eu-air-safety-list_en",
            "2026-06-09"
        ))
    return records


def compute_file_sha256(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    if not path.is_file():
        return ""
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def parse_faa_iasa_records() -> List[Tuple[str, str, str, str, str, str, str]]:
    """Parse FAA IASA Category 2 countries."""
    records = []
    from modules.aviation.parser import parse_faa_iasa
    res = parse_faa_iasa(Path("data/aviation/faa_iasa.pdf"))
    for row in res.get("countries", []):
        country = row.get("country", "")
        cat = row.get("category", "")
        all_text = f"Country: {country} FAA IASA Category: {cat} Non-compliant with ICAO standards"
        records.append((
            "faa_iasa",
            country,
            country,
            country,
            normalize_text_for_index(all_text),
            "https://www.faa.gov/about/initiatives/iasa/iasa-program-results",
            "2025-04-23"
        ))
    return records


def parse_india_records() -> List[Tuple[str, str, str, str, str, str, str]]:
    """Parse India MHA First Schedule, Fourth Schedule, and Unlawful Associations."""
    records = []
    from modules.india.parser import parse_first_schedule, parse_fourth_schedule, parse_unlawful_associations
    
    # 1. First Schedule
    fs = parse_first_schedule()
    for ent in fs.get("entities", []):
        eid = ent.get("id", "")
        name = ent.get("name", "")
        aliases = ent.get("aliases", [])
        parent = ent.get("parent_organization") or ""
        all_names = "; ".join([name] + aliases)
        all_text = f"ID: {eid} Name: {name} Aliases: {' '.join(aliases)} Parent: {parent} Schedule: First Schedule Terrorist Organisations"
        records.append((
            "in_mha_first_schedule",
            eid,
            name,
            all_names,
            normalize_text_for_index(all_text),
            ent.get("source_url") or "https://www.mha.gov.in/files/documents/List46TerroristOrganisationsWebsite.pdf",
            "2026-10-21"
        ))
        
    # 2. Fourth Schedule
    f4 = parse_fourth_schedule()
    for ent in f4.get("entities", []):
        eid = ent.get("id", "")
        name = ent.get("name", "")
        aliases = ent.get("aliases", [])
        all_names = "; ".join([name] + aliases)
        all_text = f"ID: {eid} Name: {name} Aliases: {' '.join(aliases)} Fourth Schedule Individual Terrorists"
        records.append((
            "in_mha_fourth_schedule",
            eid,
            name,
            all_names,
            normalize_text_for_index(all_text),
            ent.get("source_url") or "https://www.mha.gov.in/individuals-terrorists-fourth-schedule-unlawful-activities-prevention-act",
            "2026-10-27"
        ))

    # 3. Unlawful Associations (all pages: 44 entities)
    ua = parse_unlawful_associations()
    for ent in ua.get("entities", []):
        eid = ent.get("id", "")
        name = ent.get("name", "")
        aliases = ent.get("aliases", [])
        all_names = "; ".join([name] + aliases)
        all_text = f"ID: {eid} Name: {name} Aliases: {' '.join(aliases)} Unlawful Associations Section 3 UAPA"
        records.append((
            "in_mha_unlawful_assoc",
            eid,
            name,
            all_names,
            normalize_text_for_index(all_text),
            ent.get("source_url") or "https://www.mha.gov.in/unlawful-associations-section3-unlawful-activities-prevention-act-1967",
            "2026-10-27"
        ))
    return records


def parse_fatf_records() -> List[Tuple[str, str, str, str, str, str, str]]:
    """Parse FATF Jurisdictions under Call for Action / Increased Monitoring."""
    records = []
    from modules.fatf.client import BLACK_LIST, GREY_LIST, FATF_STATEMENT_DATE
    seen = set()
    for raw_k, cname in BLACK_LIST.items():
        if cname not in seen:
            seen.add(cname)
            all_text = f"Country: {cname} FATF High-Risk Jurisdictions subject to a Call for Action (Black list)"
            records.append((
                "fatf_jurisdictions",
                cname,
                cname,
                cname,
                normalize_text_for_index(all_text),
                "https://www.fatf-gafi.org/en/topics/high-risk-and-other-monitored-jurisdictions.html",
                FATF_STATEMENT_DATE
            ))
    for raw_k, cname in GREY_LIST.items():
        if cname not in seen:
            seen.add(cname)
            all_text = f"Country: {cname} FATF Jurisdictions under Increased Monitoring (Grey list)"
            records.append((
                "fatf_jurisdictions",
                cname,
                cname,
                cname,
                normalize_text_for_index(all_text),
                "https://www.fatf-gafi.org/en/topics/high-risk-and-other-monitored-jurisdictions.html",
                FATF_STATEMENT_DATE
            ))
    return records


def build_full_raw_index(
    db_path: Path = INDEX_DB_PATH,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Dict[str, Any]:
    """
    Build the SQLite FTS5 database from all raw files.
    Returns summary dict with counts per source.
    """
    con = get_connection(db_path)
    init_db(con)
    cur = con.cursor()

    source_stats = {}

    parsers = [
        ("us_ofac", "data/raw/us_ofac_sdn.csv", lambda: parse_ofac_sdn(RAW_DIR / "us_ofac_sdn.csv") + parse_ofac_cons(RAW_DIR / "us_ofac_cons.xml")),
        ("us_csl", "data/raw/us_csl.csv", lambda: parse_us_csl(RAW_DIR / "us_csl.csv")),
        ("uk_csl", "data/raw/uk_csl.csv", lambda: parse_uk_csl(RAW_DIR / "uk_csl.csv")),
        ("eu_csl", "data/raw/eu_csl.xml", lambda: parse_eu_csl(RAW_DIR / "eu_csl.xml")),
        ("un_csl", "data/raw/un_csl.xml", lambda: parse_un_csl(RAW_DIR / "un_csl.xml")),
        ("bis_aircraft", "data/aviation/bis_aircraft.pdf", parse_bis_aircraft_records),
        ("eu_air_safety_list", "data/aviation/eu_air_safety_list.pdf", parse_eu_air_safety_records),
        ("faa_iasa", "data/aviation/faa_iasa.pdf", parse_faa_iasa_records),
        ("in_mha_first_schedule", "data/india/first_schedule.pdf", lambda: [r for r in parse_india_records() if r[0] == "in_mha_first_schedule"]),
        ("in_mha_fourth_schedule", "data/india/individuals_all.json", lambda: [r for r in parse_india_records() if r[0] == "in_mha_fourth_schedule"]),
        ("in_mha_unlawful_assoc", "data/india/unlawful_associations_all_pages.html", lambda: [r for r in parse_india_records() if r[0] == "in_mha_unlawful_assoc"]),
        ("fatf_jurisdictions", "config/fatf.json", parse_fatf_records),
    ]

    total_records = 0
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()

    for idx, (src_id, file_path_str, parse_fn) in enumerate(parsers):
        if progress_callback:
            progress_callback(idx, len(parsers), src_id)
        p = Path(file_path_str)
        file_hash = compute_file_sha256(p)
        if not p.is_file() and "data/raw" in file_path_str:
            cur.execute(
                "INSERT INTO source_meta VALUES (?, ?, ?, ?, ?, ?, ?)",
                (src_id, "MISSING", 0, "UNKNOWN", file_path_str, "", now_iso)
            )
            source_stats[src_id] = {"status": "MISSING", "count": 0, "hash": ""}
            continue

        try:
            records = parse_fn()
            count = len(records)
            if count > 0:
                list_date = records[0][6] if len(records[0]) > 6 else ""
                cur.executemany(
                    "INSERT INTO raw_index(source, record_id, primary_name, all_names, all_text, source_url, list_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    records
                )
                cur.execute(
                    "INSERT INTO source_meta VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (src_id, "OK", count, list_date, file_path_str, file_hash, now_iso)
                )
                source_stats[src_id] = {"status": "OK", "count": count, "hash": file_hash, "list_date": list_date}
                total_records += count
            else:
                cur.execute(
                    "INSERT INTO source_meta VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (src_id, "EMPTY", 0, "", file_path_str, file_hash, now_iso)
                )
                source_stats[src_id] = {"status": "EMPTY", "count": 0, "hash": file_hash}
        except Exception as e:
            logger.error(f"Error indexing source {src_id}: {e}")
            cur.execute(
                "INSERT INTO source_meta VALUES (?, ?, ?, ?, ?, ?, ?)",
                (src_id, "FAILED", 0, "", file_path_str, file_hash, now_iso)
            )
            source_stats[src_id] = {"status": "FAILED", "count": 0, "hash": file_hash}

    con.commit()
    con.close()
    return {"total_records": total_records, "sources": source_stats}


if __name__ == "__main__":
    import time
    start = time.time()
    res = build_full_raw_index()
    duration = time.time() - start
    print(f"Index built in {duration:.2f}s:")
    print(f"Total records: {res['total_records']}")
    for s, data in res["sources"].items():
        print(f"  - {s}: {data['status']} ({data['count']} records)")
