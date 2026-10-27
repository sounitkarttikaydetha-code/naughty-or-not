"""
Local Records Store (T11 Part B4).
Provides structured storage and retrieval of full entity records across all sanctions,
aviation, and domestic lists in SQLite (screening.db).
"""

import json
import logging
from pathlib import Path
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple

from modules.reporting.logger import DB_PATH

logger = logging.getLogger(__name__)


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_records_table(conn: Optional[sqlite3.Connection] = None) -> None:
    close = False
    if conn is None:
        conn = get_connection()
        close = True
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS records (
                source_id TEXT NOT NULL,
                record_id TEXT NOT NULL,
                primary_name TEXT NOT NULL,
                entity_type TEXT,
                payload_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (source_id, record_id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_records_source_id ON records (source_id)")
        conn.commit()
    finally:
        if close:
            conn.close()


def store_records_batch(records: List[Tuple[str, str, str, str, str, str]], db_path: Optional[Path] = None) -> int:
    """Batch insert or replace records into records table."""
    if not records:
        return 0
    conn = get_connection(db_path)
    try:
        init_records_table(conn)
        conn.executemany(
            """
            INSERT OR REPLACE INTO records (source_id, record_id, primary_name, entity_type, payload_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            records,
        )
        conn.commit()
        return len(records)
    finally:
        conn.close()


def populate_records_cache(db_path: Optional[Path] = None, force: bool = False) -> int:
    """
    Populate records table from all loaded sources if empty or forced.
    Sources: us_ofac, us_csl, uk_csl, eu_csl, un_csl, in_mha, bis_aircraft, eu_air_safety.
    """
    conn = get_connection(db_path)
    try:
        init_records_table(conn)
        if not force:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM records")
            count = cur.fetchone()[0]
            if count > 1000:
                logger.debug(f"Records table already populated with {count} records.")
                return count

        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        batch: List[Tuple[str, str, str, str, str, str]] = []

        # 1. Main Watchman sources (OFAC, US CSL, UK CSL, EU CSL, UN CSL)
        from modules.watchman.client import get_python_engine
        eng = get_python_engine()
        for src_id, entities in eng.records_by_source.items():
            for rec in entities:
                batch.append((
                    src_id,
                    str(rec.source_id),
                    rec.name or "",
                    rec.entity_type or "",
                    json.dumps(rec.raw_entity, ensure_ascii=False),
                    now_str,
                ))

        # 2. India MHA
        try:
            from modules.india.client import IndiaClient
            ic = IndiaClient()
            # Fourth schedule
            for item in ic.fourth_schedule.get("entities", []):
                rid = str(item.get("id") or item.get("authority_id") or "")
                batch.append((
                    "in_mha",
                    rid,
                    item.get("name") or "",
                    item.get("schema") or "Person",
                    json.dumps(item, ensure_ascii=False),
                    now_str,
                ))
            # Unlawful associations
            for item in ic.unlawful_associations.get("entities", []):
                rid = str(item.get("id") or item.get("authority_id") or "")
                batch.append((
                    "in_mha",
                    rid,
                    item.get("name") or "",
                    item.get("schema") or "Organisation",
                    json.dumps(item, ensure_ascii=False),
                    now_str,
                ))
        except Exception as e:
            logger.warning(f"Failed to load MHA records for records store: {e}")

        # 3. Aviation: BIS Aircraft
        try:
            from modules.aviation.client import AviationClient
            ac = AviationClient()
            for item in ac.bis_data.get("active", []):
                tail = item.get("current_tail_number") or ""
                msn = item.get("msn") or ""
                rid = tail or msn
                batch.append((
                    "bis_aircraft",
                    rid,
                    f"{tail} ({item.get('aircraft_type', 'Aircraft')})",
                    "Aircraft",
                    json.dumps(item, ensure_ascii=False),
                    now_str,
                ))
            # Aviation: EU Air Safety
            for item in ac.eu_data.get("annex_a", []) + ac.eu_data.get("annex_b", []):
                airline = item.get("airline") or ""
                aoc = item.get("aoc_number") or ""
                rid = aoc or airline
                batch.append((
                    "eu_air_safety",
                    rid,
                    airline,
                    "Airline",
                    json.dumps(item, ensure_ascii=False),
                    now_str,
                ))
        except Exception as e:
            logger.warning(f"Failed to load Aviation records for records store: {e}")

        conn.executemany(
            """
            INSERT OR REPLACE INTO records (source_id, record_id, primary_name, entity_type, payload_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            batch,
        )
        conn.commit()
        logger.info(f"Populated records table with {len(batch)} records.")
        return len(batch)
    finally:
        conn.close()


def get_record(source_id: str, record_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Retrieve full structured record by source_id and record_id."""
    if not source_id or not record_id:
        return None

    conn = get_connection(db_path)
    try:
        init_records_table(conn)
        cur = conn.cursor()
        cur.execute(
            "SELECT payload_json FROM records WHERE source_id = ? AND record_id = ?",
            (source_id, str(record_id)),
        )
        row = cur.fetchone()
        if row:
            try:
                return json.loads(row[0])
            except Exception:
                pass

        # Try case-insensitive or stripped lookup
        cur.execute(
            "SELECT payload_json FROM records WHERE source_id = ? AND LOWER(record_id) = LOWER(?)",
            (source_id, str(record_id).strip()),
        )
        row = cur.fetchone()
        if row:
            try:
                return json.loads(row[0])
            except Exception:
                pass
    finally:
        conn.close()

    # Fallback to in-memory lookup if not in SQLite table yet
    try:
        from modules.watchman.client import get_python_engine
        eng = get_python_engine()
        for rec in eng.records_by_source.get(source_id, []):
            if str(rec.source_id).lower() == str(record_id).lower():
                return rec.raw_entity
    except Exception:
        pass

    return None


def format_programs(prog_val: Any) -> str:
    """Format program strings, turning e.g. '[FTO] [SDGT]' into 'FTO; SDGT'."""
    if not prog_val:
        return "—"
    if isinstance(prog_val, list):
        items = [str(p).strip().strip("[]") for p in prog_val if str(p).strip()]
        return "; ".join(items) if items else "—"
    s = str(prog_val).replace("[", "").replace("]", " ")
    parts = [p.strip() for p in s.replace(";", " ").replace(",", " ").split() if p.strip()]
    return "; ".join(parts) if parts else str(prog_val)


def format_record_for_display(record: Dict[str, Any]) -> List[Tuple[str, str]]:
    """
    Format a record dictionary into an ordered list of (Label, Value) pairs.
    Excludes null, empty, or placeholder values.
    """
    if not record:
        return []

    fields: List[Tuple[str, str]] = []

    def add_field(label: str, val: Any):
        if val is None:
            return
        if isinstance(val, (list, tuple)):
            clean_list = [str(x).strip() for x in val if x and str(x).strip() not in ["", "-0-", "None", "null"]]
            if clean_list:
                fields.append((label, "; ".join(clean_list)))
        elif isinstance(val, dict):
            # Render non-empty dict items
            parts = []
            for k, v in val.items():
                if v and str(v).strip() not in ["", "-0-", "None", "null"]:
                    parts.append(f"{k}: {v}")
            if parts:
                fields.append((label, ", ".join(parts)))
        else:
            s = str(val).strip()
            if s and s not in ["-0-", "None", "null", "—"]:
                fields.append((label, s))

    # Basic identity
    add_field("Primary Name", record.get("name") or record.get("sdnName") or record.get("primary_name"))
    add_field("Entity Type", record.get("entityType") or record.get("schema") or record.get("entity_type"))
    add_field("Record ID", record.get("sourceID") or record.get("id") or record.get("authority_id"))
    add_field("Source List", record.get("sourceList") or record.get("source"))

    # Source Data block
    sdata = record.get("sourceData") or {}
    if isinstance(sdata, dict):
        prog = sdata.get("program") or record.get("program") or record.get("programs")
        if prog:
            add_field("Sanctions Program", format_programs(prog))
        add_field("Title / Position", sdata.get("title"))
        add_field("Call Sign", sdata.get("callSign"))
        add_field("Vessel Type", sdata.get("vesselType"))
        add_field("Vessel Flag", sdata.get("vesselFlag"))
        add_field("Vessel Owner", sdata.get("vesselOwner"))
        add_field("Tonnage / GRT", sdata.get("tonnage") or sdata.get("grossRegisteredTonnage"))
        add_field("Remarks", sdata.get("remarks"))

    # Person sub-object
    person = record.get("person") or {}
    if isinstance(person, dict):
        add_field("Alternate Names / Aliases", person.get("altNames"))
        add_field("Gender", person.get("gender"))
        add_field("Dates of Birth", person.get("datesOfBirth"))
        add_field("Places of Birth", person.get("placesOfBirth"))
        add_field("Nationalities", person.get("nationalities") or person.get("citizenships"))

    # Business sub-object
    biz = record.get("business") or {}
    if isinstance(biz, dict):
        add_field("Alternate Names / Aliases", biz.get("altNames"))

    # Aircraft sub-object
    aircraft = record.get("aircraft") or {}
    if isinstance(aircraft, dict):
        add_field("Tail Number", aircraft.get("current_tail_number") or aircraft.get("tailNumber"))
        add_field("Previous Tail", aircraft.get("previous_tail_number"))
        add_field("Serial Number (MSN)", aircraft.get("msn") or aircraft.get("serialNumber"))
        add_field("Aircraft Type", aircraft.get("aircraft_type") or aircraft.get("type"))
        add_field("Owner / Operator", aircraft.get("owner_operator") or aircraft.get("operator"))
        add_field("Country", aircraft.get("country"))

    # Top-level direct fields (Aviation & India)
    if "current_tail_number" in record:
        add_field("Tail Number", record.get("current_tail_number"))
        add_field("Previous Tail", record.get("previous_tail_number"))
        add_field("MSN", record.get("msn"))
        add_field("Aircraft Type", record.get("aircraft_type"))
        add_field("Owner / Operator", record.get("owner_operator"))
        add_field("Country", record.get("country"))

    if "aoc_number" in record:
        add_field("Airline", record.get("airline"))
        add_field("AOC Number", record.get("aoc_number"))
        add_field("ICAO Code", record.get("icao_code"))
        add_field("State / Country", record.get("state"))

    if "schedule" in record:
        add_field("MHA Schedule", record.get("schedule"))
        add_field("Authority ID", record.get("authority_id"))
        add_field("Aliases", record.get("aliases"))
        add_field("Parent Organization", record.get("parent_organization"))
        add_field("Official Notice URL", record.get("source_url"))

    # Addresses
    addrs = record.get("addresses") or []
    if isinstance(addrs, list) and addrs:
        addr_strs = []
        for a in addrs:
            if isinstance(a, dict):
                parts = [str(a.get(k)).strip() for k in ["address1", "city", "stateOrProvince", "postalCode", "country"] if a.get(k)]
                if parts:
                    addr_strs.append(", ".join(parts))
            elif isinstance(a, str) and a.strip():
                addr_strs.append(a.strip())
        if addr_strs:
            add_field("Addresses", addr_strs)

    # Identifications
    ids = record.get("identifications") or []
    if isinstance(ids, list) and ids:
        id_strs = []
        for item in ids:
            if isinstance(item, dict):
                itype = item.get("type") or "ID"
                inum = item.get("number") or item.get("id") or ""
                icountry = item.get("country") or ""
                id_strs.append(f"{itype}: {inum} ({icountry})" if icountry else f"{itype}: {inum}")
            elif isinstance(item, str) and item.strip():
                id_strs.append(item.strip())
        if id_strs:
            add_field("Identification Documents", id_strs)

    return fields


def format_record_as_text(source_id: str, record_id: str, record: Dict[str, Any]) -> str:
    """Format record as clean plain text suitable for clipboard copy."""
    lines = [
        f"--- FULL RECORD: {source_id.upper()} (ID: {record_id}) ---",
    ]
    fields = format_record_for_display(record)
    for label, val in fields:
        lines.append(f"{label}: {val}")
    lines.append("--- END RECORD ---")
    return "\n".join(lines)
