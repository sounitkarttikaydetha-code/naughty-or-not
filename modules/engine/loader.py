"""
Sanctions List Loader
Reads official download files and constructs in-memory searchable entities.
Matches Watchman's entity IDs and schema exactly:
- us_ofac: OFAC ent_num (e.g. '18715')
- us_csl: CSL id (e.g. '1d6ca9a675')
- uk_csl: UniqueID (e.g. 'RUS0250')
- eu_csl: EntityLogicalID (e.g. '18720')
- un_csl: UN-{DATAID} (e.g. 'UN-6907993')
"""

from collections import defaultdict
import csv
import hashlib
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple
import xml.etree.ElementTree as ET

from modules.common.alias_splitter import split_alias_parts
from modules.engine.name_prep import (
    prepare_name,
    reorder_sdn_name,
    remove_stopwords,
)

logger = logging.getLogger(__name__)

AKA_REGEX = re.compile(r"(?i)a\.k\.a\.\s+'([^']+)'")
IMO_REGEX = re.compile(r"(?i)\bIMO\s*[:#-]?\s*(\d{7})\b")
TAIL_REGEX = re.compile(r"(?i)\b(?:tail|registration)?\s*[:#-]?\s*([A-Z0-9]{1,3}-[A-Z0-9]{2,6})\b")
MSN_REGEX = re.compile(r"(?i)\b(?:MSN|serial\s*(?:no|number)?)\s*[:#-]?\s*(\d+)\b")


def extract_identifiers(text: str, source_id: str) -> Set[str]:
    """Extract searchable identifiers: source ID, IMO, tail registration, and MSN."""
    ids = set()
    sid = source_id.strip().lower()
    if sid:
        ids.add(sid)
        ids.add(sid.replace("-", "").replace("_", ""))

    if text:
        for imo in IMO_REGEX.findall(text):
            ids.add(f"imo {imo}".lower())
            ids.add(f"imo{imo}".lower())
            ids.add(imo.lower())
        for tail in TAIL_REGEX.findall(text):
            ids.add(tail.lower())
            ids.add(tail.lower().replace("-", ""))
        for msn in MSN_REGEX.findall(text):
            ids.add(f"msn {msn}".lower())
            ids.add(f"msn{msn}".lower())
            ids.add(msn.lower())
    return ids


SOUNDEX_MAP_LOWER = {
    "a": "A", "e": "A", "i": "A", "o": "A", "u": "A", "y": "A",
    "b": "B", "f": "B", "p": "B", "v": "B",
    "c": "C", "g": "C", "j": "C", "k": "C", "q": "C", "s": "C", "x": "C", "z": "C",
    "d": "D", "t": "D",
    "l": "L",
    "m": "M", "n": "M",
    "r": "R",
    "h": "H", "w": "H",
}


class EntityRecord:
    __slots__ = (
        "source",
        "source_id",
        "name",
        "entity_type",
        "prepared_name",
        "primary_tokens",
        "alt_tokens_list",
        "historical_tokens_list",
        "raw_entity",
        "identifiers",
        "soundex_classes",
    )

    def __init__(
        self,
        source: str,
        source_id: str,
        name: str,
        entity_type: str,
        prepared_name: str,
        primary_tokens: List[str],
        alt_tokens_list: List[List[str]],
        historical_tokens_list: List[List[str]],
        raw_entity: Dict[str, Any],
        identifiers: Optional[Set[str]] = None,
    ):
        self.source = source
        self.source_id = source_id
        self.name = name
        self.entity_type = entity_type
        self.prepared_name = prepared_name
        self.primary_tokens = primary_tokens
        self.alt_tokens_list = alt_tokens_list
        self.historical_tokens_list = historical_tokens_list
        self.raw_entity = raw_entity
        self.identifiers = identifiers or {source_id.lower()}

        # Precompute Soundex first-character classes for fast disjoint filtering (T8-3)
        s_classes = {SOUNDEX_MAP_LOWER.get(t[0], t[0]) for t in primary_tokens if t}
        for alt in alt_tokens_list:
            s_classes.update(SOUNDEX_MAP_LOWER.get(t[0], t[0]) for t in alt if t)
        for h in historical_tokens_list:
            s_classes.update(SOUNDEX_MAP_LOWER.get(t[0], t[0]) for t in h if t)
        self.soundex_classes = s_classes


def load_ofac_sdn(path: Path) -> Tuple[List[EntityRecord], str]:
    if not path.is_file():
        return [], ""
    raw_bytes = path.read_bytes()
    list_hash = hashlib.sha256(raw_bytes).hexdigest()

    # Also load alt.csv if present in the same directory
    alt_file = path.parent / "us_ofac_alt.csv"
    if not alt_file.is_file():
        alt_file = path.parent / "alt.csv"

    alt_map: Dict[str, List[str]] = defaultdict(list)
    if alt_file.is_file():
        try:
            with open(alt_file, "r", encoding="utf-8", errors="ignore") as af:
                for arow in csv.reader(af):
                    if len(arow) >= 4 and arow[0].strip().isdigit():
                        ent_id = arow[0].strip()
                        alt_name = arow[3].strip()
                        if alt_name and alt_name != "-0- ":
                            alt_map[ent_id].append(alt_name)
        except Exception as e:
            logger.warning(f"Notice reading alt.csv: {e}")

    records: List[EntityRecord] = []

    try:
        f = open(path, "r", encoding="utf-8", errors="ignore")
    except Exception:
        return [], list_hash

    try:
        r = csv.reader(f)
        r = csv.reader(f)
        for row in r:
            if not row or len(row) < 2:
                continue
            ent_num = row[0].strip()
            if not ent_num.isdigit():
                continue
            raw_name = row[1].strip()
            sdn_type = row[2].strip() if len(row) > 2 else ""
            program = [x.strip() for x in (row[3].split(",") if len(row) > 3 else []) if x.strip()]
            remarks = row[11].strip() if len(row) > 11 else ""

            type_lower = sdn_type.lower()
            if type_lower == "individual":
                mapped_type = "person"
                disp_name = reorder_sdn_name(raw_name, sdn_type)
            elif type_lower == "vessel":
                mapped_type = "vessel"
                disp_name = raw_name
            elif type_lower == "aircraft":
                mapped_type = "aircraft"
                disp_name = raw_name
            else:
                mapped_type = "business"
                disp_name = raw_name

            # Load-time alias splitting on listed name
            disp_parts = split_alias_parts(disp_name)
            primary_disp = disp_parts[0] if disp_parts else disp_name
            extra_disp_alts = disp_parts[1:] if len(disp_parts) > 1 else []

            norm_name, former = prepare_name(primary_disp, mapped_type)

            # Combined alternate names from alt.csv, remarks (a.k.a.), and load-time splitting
            alts_seen = set()
            alts_combined = []

            for extra in extra_disp_alts:
                if extra and extra.lower() != primary_disp.lower() and extra not in alts_seen:
                    alts_seen.add(extra)
                    alts_combined.append(extra)

            for a in alt_map.get(ent_num, []):
                for part in split_alias_parts(a):
                    if part and part.lower() != primary_disp.lower() and part not in alts_seen:
                        alts_seen.add(part)
                        alts_combined.append(part)

            for a in AKA_REGEX.findall(remarks):
                for part in split_alias_parts(a):
                    if part and part.lower() != primary_disp.lower() and part not in alts_seen:
                        alts_seen.add(part)
                        alts_combined.append(part)

            alt_tokens: List[List[str]] = []
            for a in alts_combined:
                cleaned_alt = reorder_sdn_name(a, sdn_type) if mapped_type == "person" else a
                alt_norm, alt_former = prepare_name(cleaned_alt, mapped_type)
                if alt_norm:
                    toks = remove_stopwords(alt_norm)
                    if toks:
                        alt_tokens.append(toks)
                for af in alt_former:
                    if af:
                        former.append(af)

            title_c = row[4].strip() if len(row) > 4 else ""
            call_c = row[5].strip() if len(row) > 5 else ""
            vtype_c = row[6].strip() if len(row) > 6 else ""
            ton_c = row[7].strip() if len(row) > 7 else ""
            grt_c = row[8].strip() if len(row) > 8 else ""
            flag_c = row[9].strip() if len(row) > 9 else ""
            owner_c = row[10].strip() if len(row) > 10 else ""
            raw_fields = {
                "ent_num": ent_num,
                "sdn_name": raw_name,
                "sdn_type": sdn_type,
                "program": ",".join(program),
                "title": title_c,
                "call_sign": call_c,
                "vessel_type": vtype_c,
                "tonnage": ton_c,
                "grt": grt_c,
                "vessel_flag": flag_c,
                "vessel_owner": owner_c,
                "remarks": remarks,
                "alt_names": alts_combined,
            }
            raw_dict = {
                "name": raw_name,
                "entityType": mapped_type,
                "sourceList": "us_ofac",
                "source": "us_ofac",
                "sourceID": ent_num,
                "person": {"name": primary_disp, "altNames": alts_combined} if mapped_type == "person" else None,
                "business": {"name": primary_disp, "altNames": alts_combined} if mapped_type == "business" else None,
                "aircraft": {"name": primary_disp, "altNames": alts_combined} if mapped_type == "aircraft" else None,
                "vessel": {"name": primary_disp, "altNames": alts_combined} if mapped_type == "vessel" else None,
                "organization": None,
                "addresses": [],
                "sourceData": {
                    "entityID": ent_num,
                    "sdnName": raw_name,
                    "program": program,
                    "title": title_c,
                    "callSign": call_c,
                    "vesselType": vtype_c,
                    "tonnage": ton_c,
                    "grossRegisteredTonnage": grt_c,
                    "vesselFlag": flag_c,
                    "vesselOwner": owner_c,
                    "remarks": remarks,
                },
                "raw_fields": {k: v for k, v in raw_fields.items() if v and v != "-0- "},
            }

            all_ids = extract_identifiers(f"{raw_name} {remarks}", ent_num)

            records.append(
                EntityRecord(
                    source="us_ofac",
                    source_id=ent_num,
                    name=raw_name,
                    entity_type=mapped_type,
                    prepared_name=norm_name,
                    primary_tokens=remove_stopwords(norm_name),
                    alt_tokens_list=alt_tokens,
                    historical_tokens_list=[remove_stopwords(f) for f in former if f],
                    raw_entity=raw_dict,
                    identifiers=all_ids,
                )
            )
    except Exception:
        return [], list_hash
    finally:
        f.close()
    return records, list_hash


def load_us_csl(path: Path) -> Tuple[List[EntityRecord], str]:
    if not path.is_file():
        return [], ""
    raw_bytes = path.read_bytes()
    list_hash = hashlib.sha256(raw_bytes).hexdigest()
    records: List[EntityRecord] = []

    try:
        f = open(path, "r", encoding="utf-8", errors="ignore")
    except Exception:
        return [], list_hash

    try:
        r = csv.reader(f)
        try:
            header = next(r)
            if not header or len(header) < 5 or not any("name" in col.lower() for col in header):
                return [], list_hash
        except StopIteration:
            return [], list_hash
        for row in r:
            if not row:
                continue
            source_field = row[1].lower() if len(row) > 1 else ""
            if "specially designated nationals" in source_field:
                continue
            rec_id = row[0].strip()
            name = row[5].strip() if len(row) > 5 else ""
            csl_type = row[3].strip().lower() if len(row) > 3 and row[3].strip() else "business"
            mapped_type = "person" if csl_type == "individual" else ("vessel" if csl_type == "vessel" else "business")
            alt_names = [a.strip() for a in (row[22].split(";") if len(row) > 22 else []) if a.strip()]
            programs = [row[4].strip()] if len(row) > 4 and row[4].strip() else []
            remarks = row[20].strip() if len(row) > 20 else ""

            # Load-time alias splitting on listed name and alternate names
            name_parts = split_alias_parts(name)
            primary_name = name_parts[0] if name_parts else name
            extra_alts = name_parts[1:] if len(name_parts) > 1 else []

            alts_seen = set()
            alts_combined = []

            for ea in extra_alts:
                if ea and ea.lower() != primary_name.lower() and ea not in alts_seen:
                    alts_seen.add(ea)
                    alts_combined.append(ea)

            for a in alt_names:
                for part in split_alias_parts(a):
                    if part and part.lower() != primary_name.lower() and part not in alts_seen:
                        alts_seen.add(part)
                        alts_combined.append(part)

            norm_name, former = prepare_name(primary_name, mapped_type)
            alt_tokens: List[List[str]] = []
            for a in alts_combined:
                anorm, aformer = prepare_name(a, mapped_type)
                if anorm:
                    toks = remove_stopwords(anorm)
                    if toks:
                        alt_tokens.append(toks)
                for af in aformer:
                    former.append(af)

            raw_fields = {
                header[i]: row[i].strip()
                for i in range(min(len(header), len(row)))
                if row[i].strip() and row[i].strip() not in ["-0-", "None", "null"]
            }
            raw_dict = {
                "name": name,
                "entityType": mapped_type,
                "sourceList": "us_csl",
                "source": "us_csl",
                "sourceID": rec_id,
                "person": {"name": primary_name, "altNames": alts_combined} if mapped_type == "person" else None,
                "business": {"name": primary_name, "altNames": alts_combined} if mapped_type == "business" else None,
                "aircraft": {"name": primary_name, "altNames": alts_combined} if mapped_type == "aircraft" else None,
                "vessel": {"name": primary_name, "altNames": alts_combined} if mapped_type == "vessel" else None,
                "organization": None,
                "addresses": [raw_fields.get("addresses")] if raw_fields.get("addresses") else [],
                "sourceData": {
                    "id": rec_id,
                    "name": name,
                    "program": programs,
                    "title": raw_fields.get("title", ""),
                    "callSign": raw_fields.get("call_sign", ""),
                    "vesselType": raw_fields.get("vessel_type", ""),
                    "vesselFlag": raw_fields.get("vessel_flag", ""),
                    "vesselOwner": raw_fields.get("vessel_owner", ""),
                    "tonnage": raw_fields.get("gross_tonnage", ""),
                    "grossRegisteredTonnage": raw_fields.get("gross_registered_tonnage", ""),
                    "remarks": remarks,
                },
                "raw_fields": raw_fields,
            }

            all_ids = extract_identifiers(f"{name} {remarks}", rec_id)

            records.append(
                EntityRecord(
                    source="us_csl",
                    source_id=rec_id,
                    name=name,
                    entity_type=mapped_type,
                    prepared_name=norm_name,
                    primary_tokens=remove_stopwords(norm_name),
                    alt_tokens_list=alt_tokens,
                    historical_tokens_list=[remove_stopwords(f) for f in former if f],
                    raw_entity=raw_dict,
                    identifiers=all_ids,
                )
            )
    except Exception:
        return [], list_hash
    finally:
        f.close()
    return records, list_hash


def load_uk_csl(path: Path) -> Tuple[List[EntityRecord], str]:
    if not path.is_file():
        return [], ""
    raw_bytes = path.read_bytes()
    list_hash = hashlib.sha256(raw_bytes).hexdigest()
    groups: Dict[str, Dict[str, Any]] = {}

    try:
        f = open(path, "r", encoding="utf-8", errors="ignore")
    except Exception:
        return [], list_hash

    try:
        r = csv.reader(f)
        try:
            h1 = next(r)
            h2 = next(r)
            header = h2 if len(h2) >= 5 else h1
            if not header or len(header) < 5 or not any("name" in col.lower() for col in header):
                return [], list_hash
        except StopIteration:
            return [], list_hash
        for row in r:
            if not row or len(row) < 5:
                continue
            uid = row[1].strip() or row[2].strip()
            if not uid:
                continue

            col4 = row[4].strip() if len(row) > 4 else ""
            other_names = [row[i].strip() for i in range(5, 10) if len(row) > i and row[i].strip()]
            row_full_name = " ".join(filter(None, [col4] + other_names)).strip()

            gender = row[41].strip().lower() if len(row) > 41 else ""
            dob = row[34].strip() if len(row) > 34 else ""
            passport = row[38].strip() if len(row) > 38 else ""
            ent_type_col = row[17].strip().lower() if len(row) > 17 else (row[44].strip().lower() if len(row) > 44 else "")
            ship_type = row[53].strip() if len(row) > 53 else ""

            if gender in ["male", "female"] or dob or passport or "individual" in ent_type_col:
                mapped_type = "person"
            elif ship_type:
                mapped_type = "vessel"
            else:
                mapped_type = "business"

            regime = row[16].strip() if len(row) > 16 else (row[10].strip() if len(row) > 10 else "")

            if uid not in groups:
                groups[uid] = {
                    "sourceID": uid,
                    "name": row_full_name,
                    "entityType": mapped_type,
                    "alt_names": set(),
                    "programs": set(),
                    "all_text": row_full_name,
                    "raw_fields": {},
                }
            if mapped_type == "person":
                groups[uid]["entityType"] = "person"

            if not groups[uid]["name"]:
                groups[uid]["name"] = row_full_name
            elif row_full_name and row_full_name != groups[uid]["name"]:
                groups[uid]["alt_names"].add(row_full_name)

            if regime:
                groups[uid]["programs"].add(regime)
            groups[uid]["all_text"] += " " + " ".join(row)
            for i, col in enumerate(header):
                if i < len(row) and row[i].strip() and row[i].strip() not in ["-0-", "None", "null"]:
                    if col not in groups[uid]["raw_fields"]:
                        groups[uid]["raw_fields"][col] = row[i].strip()
                    elif row[i].strip() not in groups[uid]["raw_fields"][col]:
                        groups[uid]["raw_fields"][col] += f"; {row[i].strip()}" 
    except Exception:
        return [], list_hash
    finally:
        f.close()

    records: List[EntityRecord] = []
    for uid, d in groups.items():
        primary_name = d["name"]

        # Load-time splitting
        name_parts = split_alias_parts(primary_name)
        norm_primary = name_parts[0] if name_parts else primary_name
        extra_alts = name_parts[1:] if len(name_parts) > 1 else []

        alts_seen = set()
        alts_combined = []

        for ea in extra_alts:
            if ea and ea.lower() != norm_primary.lower() and ea not in alts_seen:
                alts_seen.add(ea)
                alts_combined.append(ea)

        for a in d["alt_names"]:
            for part in split_alias_parts(a):
                if part and part.lower() != norm_primary.lower() and part not in alts_seen:
                    alts_seen.add(part)
                    alts_combined.append(part)

        norm_name, former = prepare_name(norm_primary, d["entityType"])
        alt_tokens: List[List[str]] = []
        for a in alts_combined:
            anorm, aformer = prepare_name(a, d["entityType"])
            if anorm:
                toks = remove_stopwords(anorm)
                if toks:
                    alt_tokens.append(toks)
            for af in aformer:
                former.append(af)

        rf = d.get("raw_fields", {})
        raw_dict = {
            "name": primary_name,
            "entityType": d["entityType"],
            "sourceList": "uk_csl",
            "source": "uk_csl",
            "sourceID": uid,
            "person": {"name": norm_primary, "altNames": alts_combined} if d["entityType"] == "person" else None,
            "business": {"name": norm_primary, "altNames": alts_combined} if d["entityType"] == "business" else None,
            "aircraft": {"name": norm_primary, "altNames": alts_combined} if d["entityType"] == "aircraft" else None,
            "vessel": {"name": norm_primary, "altNames": alts_combined} if d["entityType"] == "vessel" else None,
            "organization": None,
            "addresses": [rf.get("Address Country")] if rf.get("Address Country") else [],
            "sourceData": {
                "uniqueID": uid,
                "name": primary_name,
                "program": sorted(list(d["programs"])),
                "remarks": rf.get("UK Statement of Reasons") or rf.get("Other Information", ""),
            },
            "raw_fields": rf,
        }

        all_ids = extract_identifiers(d["all_text"], uid)

        records.append(
            EntityRecord(
                source="uk_csl",
                source_id=uid,
                name=primary_name,
                entity_type=d["entityType"],
                prepared_name=norm_name,
                primary_tokens=remove_stopwords(norm_name),
                alt_tokens_list=alt_tokens,
                historical_tokens_list=[remove_stopwords(f) for f in former if f],
                raw_entity=raw_dict,
                identifiers=all_ids,
            )
        )
    return records, list_hash


def load_eu_csl(path: Path) -> Tuple[List[EntityRecord], str]:
    if not path.is_file():
        return [], ""
    raw_bytes = path.read_bytes()
    list_hash = hashlib.sha256(raw_bytes).hexdigest()
    records: List[EntityRecord] = []

    try:
        for event, elem in ET.iterparse(str(path), events=("end",)):
            tag = elem.tag.split("}")[-1]
            if tag == "sanctionEntity":
                logical_id = elem.attrib.get("logicalId", "")
                subject_type = elem.attrib.get("subjectType", "").lower()
                mapped_type = "person" if subject_type == "p" else "business"
                alias_nodes = elem.findall(".//{*}nameAlias")
                # Watchman orders EU CSL aliases by their integer logicalId
                alias_nodes.sort(key=lambda x: int(x.attrib.get("logicalId", 0)) if x.attrib.get("logicalId", "").isdigit() else 99999999)
                names = []
                for name_alias in alias_nodes:
                    whole = name_alias.attrib.get("wholeName", "")
                    if whole:
                        names.append(whole)
                primary_name = names[0] if names else ""
                raw_alt_names = names[1:] if len(names) > 1 else []

                # Load-time splitting
                name_parts = split_alias_parts(primary_name)
                norm_primary = name_parts[0] if name_parts else primary_name
                extra_alts = name_parts[1:] if len(name_parts) > 1 else []

                alts_seen = set()
                alts_combined = []

                for ea in extra_alts:
                    if ea and ea.lower() != norm_primary.lower() and ea not in alts_seen:
                        alts_seen.add(ea)
                        alts_combined.append(ea)

                for a in raw_alt_names:
                    for part in split_alias_parts(a):
                        if part and part.lower() != norm_primary.lower() and part not in alts_seen:
                            alts_seen.add(part)
                            alts_combined.append(part)

                norm_name, former = prepare_name(norm_primary, mapped_type)
                alt_tokens: List[List[str]] = []
                for a in alts_combined:
                    anorm, aformer = prepare_name(a, mapped_type)
                    if anorm:
                        toks = remove_stopwords(anorm)
                        if toks:
                            alt_tokens.append(toks)
                    for af in aformer:
                        former.append(af)

                eu_raw = {k: v for k, v in elem.attrib.items() if v}
                for sub in elem:
                    sub_tag = sub.tag.split("}")[-1]
                    sub_info = {k: v for k, v in sub.attrib.items() if v}
                    if sub.text and sub.text.strip():
                        sub_info["_text"] = sub.text.strip()
                    for sc in sub:
                        sc_tag = sc.tag.split("}")[-1]
                        sc_info = {k: v for k, v in sc.attrib.items() if v}
                        if sc.text and sc.text.strip():
                            sc_info["_text"] = sc.text.strip()
                        sub_info[sc_tag] = sc_info or (sc.text.strip() if sc.text else "")
                    if sub_tag not in eu_raw:
                        eu_raw[sub_tag] = sub_info or (sub.text.strip() if sub.text else "")
                    elif isinstance(eu_raw[sub_tag], list):
                        eu_raw[sub_tag].append(sub_info or (sub.text.strip() if sub.text else ""))
                    else:
                        eu_raw[sub_tag] = [eu_raw[sub_tag], sub_info or (sub.text.strip() if sub.text else "")]

                raw_dict = {
                    "name": primary_name,
                    "entityType": mapped_type,
                    "sourceList": "eu_csl",
                    "source": "eu_csl",
                    "sourceID": logical_id,
                    "person": {"name": norm_primary, "altNames": alts_combined} if mapped_type == "person" else None,
                    "business": {"name": norm_primary, "altNames": alts_combined} if mapped_type == "business" else None,
                    "aircraft": {"name": norm_primary, "altNames": alts_combined} if mapped_type == "aircraft" else None,
                    "vessel": {"name": norm_primary, "altNames": alts_combined} if mapped_type == "vessel" else None,
                    "organization": None,
                    "addresses": [],
                    "sourceData": {
                        "logicalId": logical_id,
                        "name": primary_name,
                        "program": ["EU-SANCTIONS"],
                        "remark": eu_raw.get("remark", ""),
                        "publicationUrl": eu_raw.get("publicationUrl", ""),
                    },
                    "raw_fields": eu_raw,
                }

                all_ids = extract_identifiers(ET.tostring(elem, encoding="utf-8").decode("utf-8", errors="ignore"), logical_id)

                records.append(
                    EntityRecord(
                        source="eu_csl",
                        source_id=logical_id,
                        name=primary_name,
                        entity_type=mapped_type,
                        prepared_name=norm_name,
                        primary_tokens=remove_stopwords(norm_name),
                        alt_tokens_list=alt_tokens,
                        historical_tokens_list=[remove_stopwords(f) for f in former if f],
                        raw_entity=raw_dict,
                        identifiers=all_ids,
                    )
                )
                elem.clear()
        return records, list_hash
    except Exception:
        return [], list_hash


def load_un_csl(path: Path) -> Tuple[List[EntityRecord], str]:
    if not path.is_file():
        return [], ""
    raw_bytes = path.read_bytes()
    list_hash = hashlib.sha256(raw_bytes).hexdigest()
    records: List[EntityRecord] = []

    try:
        tree = ET.parse(path)
        root = tree.getroot()
        if root.tag.split('}')[-1] not in ['CONSOLIDATED_LIST', 'CONSOLIDATED']:
            return [], list_hash
        for item in root.iter():
            tag = item.tag.split("}")[-1]
            if tag in ["INDIVIDUAL", "ENTITY"]:
                data_id = item.findtext("DATAID", "") or item.findtext(".//DATAID", "")
                first_name = item.findtext("FIRST_NAME", "") or item.findtext(".//FIRST_NAME", "") or ""
                second_name = item.findtext("SECOND_NAME", "") or item.findtext(".//SECOND_NAME", "") or ""
                third_name = item.findtext("THIRD_NAME", "") or item.findtext(".//THIRD_NAME", "") or ""
                fourth_name = item.findtext("FOURTH_NAME", "") or item.findtext(".//FOURTH_NAME", "") or ""
                full_name = " ".join(filter(None, [first_name, second_name, third_name, fourth_name])).strip()

                raw_aliases = []
                for alias_node in item.iter():
                    if alias_node.tag.split("}")[-1] in ["INDIVIDUAL_ALIAS", "ENTITY_ALIAS"]:
                        alias_name = alias_node.findtext("ALIAS_NAME", "") or ""
                        if alias_name:
                            raw_aliases.append(alias_name)
                mapped_type = "person" if tag == "INDIVIDUAL" else "business"

                # Load-time splitting
                name_parts = split_alias_parts(full_name)
                norm_primary = name_parts[0] if name_parts else full_name
                extra_alts = name_parts[1:] if len(name_parts) > 1 else []

                alts_seen = set()
                alts_combined = []

                for ea in extra_alts:
                    if ea and ea.lower() != norm_primary.lower() and ea not in alts_seen:
                        alts_seen.add(ea)
                        alts_combined.append(ea)

                for a in raw_aliases:
                    for part in split_alias_parts(a):
                        if part and part.lower() != norm_primary.lower() and part not in alts_seen:
                            alts_seen.add(part)
                            alts_combined.append(part)

                norm_name, former = prepare_name(norm_primary, mapped_type)
                alt_tokens: List[List[str]] = []
                for a in alts_combined:
                    anorm, aformer = prepare_name(a, mapped_type)
                    if anorm:
                        toks = remove_stopwords(anorm)
                        if toks:
                            alt_tokens.append(toks)
                    for af in aformer:
                        former.append(af)

                source_id = f"UN-{data_id}"
                un_raw = {}
                for sub in item:
                    sub_tag = sub.tag.split("}")[-1]
                    sub_children = {}
                    for sc in sub:
                        sc_tag = sc.tag.split("}")[-1]
                        if sc.text and sc.text.strip():
                            sub_children[sc_tag] = sc.text.strip()
                    val = sub_children if sub_children else (sub.text.strip() if sub.text else "")
                    if val:
                        if sub_tag not in un_raw:
                            un_raw[sub_tag] = val
                        elif isinstance(un_raw[sub_tag], list):
                            un_raw[sub_tag].append(val)
                        else:
                            un_raw[sub_tag] = [un_raw[sub_tag], val]

                raw_dict = {
                    "name": full_name,
                    "entityType": mapped_type,
                    "sourceList": "un_csl",
                    "source": "un_csl",
                    "sourceID": source_id,
                    "person": {"name": norm_primary, "altNames": alts_combined} if mapped_type == "person" else None,
                    "business": {"name": norm_primary, "altNames": alts_combined} if mapped_type == "business" else None,
                    "aircraft": {"name": norm_primary, "altNames": alts_combined} if mapped_type == "aircraft" else None,
                    "vessel": {"name": norm_primary, "altNames": alts_combined} if mapped_type == "vessel" else None,
                    "organization": None,
                    "addresses": [],
                    "sourceData": {
                        "dataID": data_id,
                        "name": full_name,
                        "program": ["UN-SANCTIONS"],
                        "comments": un_raw.get("COMMENTS1", ""),
                    },
                    "raw_fields": un_raw,
                }

                all_ids = extract_identifiers(ET.tostring(item, encoding="utf-8").decode("utf-8", errors="ignore"), source_id)

                records.append(
                    EntityRecord(
                        source="un_csl",
                        source_id=source_id,
                        name=full_name,
                        entity_type=mapped_type,
                        prepared_name=norm_name,
                        primary_tokens=remove_stopwords(norm_name),
                        alt_tokens_list=alt_tokens,
                        historical_tokens_list=[remove_stopwords(f) for f in former if f],
                        raw_entity=raw_dict,
                        identifiers=all_ids,
                    )
                )
        return records, list_hash
    except Exception:
        return [], list_hash
