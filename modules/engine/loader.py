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
from typing import Any, Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET

from modules.engine.name_prep import (
    prepare_name,
    reorder_sdn_name,
    remove_stopwords,
)

logger = logging.getLogger(__name__)

AKA_REGEX = re.compile(r"(?i)a\.k\.a\.\s+'([^']+)'")


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

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
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

            norm_name, former = prepare_name(disp_name, mapped_type)

            # Combined alternate names from remarks (a.k.a.) and alt.csv
            alts_seen = set()
            alts_combined = []

            for a in alt_map.get(ent_num, []):
                if a not in alts_seen:
                    alts_seen.add(a)
                    alts_combined.append(a)

            for a in AKA_REGEX.findall(remarks):
                if a not in alts_seen:
                    alts_seen.add(a)
                    alts_combined.append(a)

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

            raw_dict = {
                "name": raw_name,
                "entityType": mapped_type,
                "sourceList": "us_ofac",
                "source": "us_ofac",
                "sourceID": ent_num,
                "person": {"name": disp_name, "altNames": alts_combined} if mapped_type == "person" else None,
                "business": {"name": disp_name, "altNames": alts_combined} if mapped_type == "business" else None,
                "organization": None,
                "aircraft": None,
                "vessel": None,
                "addresses": [],
                "sourceData": {
                    "entityID": ent_num,
                    "sdnName": raw_name,
                    "program": program,
                    "remarks": remarks,
                },
            }

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
                )
            )
    return records, list_hash


def load_us_csl(path: Path) -> Tuple[List[EntityRecord], str]:
    if not path.is_file():
        return [], ""
    raw_bytes = path.read_bytes()
    list_hash = hashlib.sha256(raw_bytes).hexdigest()
    records: List[EntityRecord] = []

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        r = csv.reader(f)
        try:
            next(r)
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

            norm_name, former = prepare_name(name, mapped_type)
            alt_tokens: List[List[str]] = []
            for a in alt_names:
                anorm, aformer = prepare_name(a, mapped_type)
                if anorm:
                    toks = remove_stopwords(anorm)
                    if toks:
                        alt_tokens.append(toks)
                for af in aformer:
                    former.append(af)

            raw_dict = {
                "name": name,
                "entityType": mapped_type,
                "sourceList": "us_csl",
                "source": "us_csl",
                "sourceID": rec_id,
                "person": {"name": name, "altNames": alt_names} if mapped_type == "person" else None,
                "business": {"name": name, "altNames": alt_names} if mapped_type == "business" else None,
                "organization": None,
                "aircraft": None,
                "vessel": None,
                "addresses": [],
                "sourceData": {
                    "id": rec_id,
                    "name": name,
                    "program": programs,
                    "remarks": remarks,
                },
            }

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
                )
            )
    return records, list_hash


def load_uk_csl(path: Path) -> Tuple[List[EntityRecord], str]:
    if not path.is_file():
        return [], ""
    raw_bytes = path.read_bytes()
    list_hash = hashlib.sha256(raw_bytes).hexdigest()
    groups: Dict[str, Dict[str, Any]] = {}

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        r = csv.reader(f)
        try:
            next(r)
            next(r)
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
            name_type = row[10].strip().lower() if len(row) > 10 else ""

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
                }
            if mapped_type == "person":
                groups[uid]["entityType"] = "person"

            if not groups[uid]["name"]:
                groups[uid]["name"] = row_full_name
            elif row_full_name and row_full_name != groups[uid]["name"]:
                groups[uid]["alt_names"].add(row_full_name)

            if regime:
                groups[uid]["programs"].add(regime)

    records: List[EntityRecord] = []
    for uid, d in groups.items():
        primary_name = d["name"]
        norm_name, former = prepare_name(primary_name, d["entityType"])
        alt_tokens: List[List[str]] = []
        alts_list = list(d["alt_names"])
        for a in alts_list:
            anorm, aformer = prepare_name(a, d["entityType"])
            if anorm:
                toks = remove_stopwords(anorm)
                if toks:
                    alt_tokens.append(toks)
            for af in aformer:
                former.append(af)

        raw_dict = {
            "name": primary_name,
            "entityType": d["entityType"],
            "sourceList": "uk_csl",
            "source": "uk_csl",
            "sourceID": uid,
            "person": {"name": primary_name, "altNames": alts_list} if d["entityType"] == "person" else None,
            "business": {"name": primary_name, "altNames": alts_list} if d["entityType"] == "business" else None,
            "organization": None,
            "aircraft": None,
            "vessel": None,
            "addresses": [],
            "sourceData": {
                "uniqueID": uid,
                "name": primary_name,
                "program": list(d["programs"]),
            },
        }

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
            )
        )
    return records, list_hash


def load_eu_csl(path: Path) -> Tuple[List[EntityRecord], str]:
    if not path.is_file():
        return [], ""
    raw_bytes = path.read_bytes()
    list_hash = hashlib.sha256(raw_bytes).hexdigest()
    records: List[EntityRecord] = []

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
            alt_names = names[1:] if len(names) > 1 else []

            norm_name, former = prepare_name(primary_name, mapped_type)
            alt_tokens: List[List[str]] = []
            for a in alt_names:
                anorm, aformer = prepare_name(a, mapped_type)
                if anorm:
                    toks = remove_stopwords(anorm)
                    if toks:
                        alt_tokens.append(toks)
                for af in aformer:
                    former.append(af)

            raw_dict = {
                "name": primary_name,
                "entityType": mapped_type,
                "sourceList": "eu_csl",
                "source": "eu_csl",
                "sourceID": logical_id,
                "person": {"name": primary_name, "altNames": alt_names} if mapped_type == "person" else None,
                "business": {"name": primary_name, "altNames": alt_names} if mapped_type == "business" else None,
                "organization": None,
                "aircraft": None,
                "vessel": None,
                "addresses": [],
                "sourceData": {
                    "logicalId": logical_id,
                    "name": primary_name,
                    "program": ["EU-SANCTIONS"],
                },
            }

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
                )
            )
            elem.clear()
    return records, list_hash


def load_un_csl(path: Path) -> Tuple[List[EntityRecord], str]:
    if not path.is_file():
        return [], ""
    raw_bytes = path.read_bytes()
    list_hash = hashlib.sha256(raw_bytes).hexdigest()
    records: List[EntityRecord] = []

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
            mapped_type = "person" if tag == "INDIVIDUAL" else "business"
            norm_name, former = prepare_name(full_name, mapped_type)
            alt_tokens: List[List[str]] = []
            for a in aliases:
                anorm, aformer = prepare_name(a, mapped_type)
                if anorm:
                    toks = remove_stopwords(anorm)
                    if toks:
                        alt_tokens.append(toks)
                for af in aformer:
                    former.append(af)

            source_id = f"UN-{data_id}"
            raw_dict = {
                "name": full_name,
                "entityType": mapped_type,
                "sourceList": "un_csl",
                "source": "un_csl",
                "sourceID": source_id,
                "person": {"name": full_name, "altNames": aliases} if mapped_type == "person" else None,
                "business": {"name": full_name, "altNames": aliases} if mapped_type == "business" else None,
                "organization": None,
                "aircraft": None,
                "vessel": None,
                "addresses": [],
                "sourceData": {
                    "dataID": data_id,
                    "name": full_name,
                    "program": ["UN-SANCTIONS"],
                },
            }

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
                )
            )
    return records, list_hash
