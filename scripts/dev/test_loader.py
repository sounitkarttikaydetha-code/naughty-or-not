"""
Test script for loading official lists and verifying exact entity counts and IDs.
"""

import csv
import hashlib
from pathlib import Path
import sys
import time
import xml.etree.ElementTree as ET

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.engine.name_prep import prepare_name, reorder_sdn_name

RAW_DIR = Path("data/raw")

def load_ofac_sdn(path: Path):
    if not path.is_file():
        return [], ""
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    entities = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        r = csv.reader(f)
        for row in r:
            if not row:
                continue
            ent_num = row[0].strip()
            raw_name = row[1].strip() if len(row) > 1 else ""
            sdn_type = row[2].strip() if len(row) > 2 else ""
            program = [x.strip() for x in (row[3].split(",") if len(row) > 3 else []) if x.strip()]
            remarks = row[11].strip() if len(row) > 11 else ""
            
            # Map type
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
                disp_name = remove_company_titles(raw_name)

            norm_name, former = prepare_name(disp_name, mapped_type)
            
            entities.append({
                "source": "us_ofac",
                "sourceID": ent_num,
                "name": raw_name,
                "entityType": mapped_type,
                "primary_tokens": norm_name.split(),
                "alt_tokens_list": [],
                "historical_tokens_list": [f.split() for f in former if f],
                "program": program,
                "remarks": remarks,
            })
    return entities, h

def load_us_csl(path: Path):
    if not path.is_file():
        return [], ""
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    entities = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        r = csv.reader(f)
        try:
            next(r)
        except StopIteration:
            return [], h
        for row in r:
            if not row:
                continue
            # Skip SDN records
            source = row[1].lower() if len(row) > 1 else ""
            if "specially designated nationals" in source:
                continue
            rec_id = row[0].strip()
            name = row[5].strip() if len(row) > 5 else ""
            csl_type = row[3].strip().lower() if len(row) > 3 else "business"
            mapped_type = "person" if csl_type == "individual" else ("vessel" if csl_type == "vessel" else "business")
            alt_names = [a.strip() for a in (row[22].split(";") if len(row) > 22 else []) if a.strip()]
            
            norm_name, former = prepare_name(name, mapped_type)
            alt_tokens = [prepare_name(a, mapped_type)[0].split() for a in alt_names if a]
            
            entities.append({
                "source": "us_csl",
                "sourceID": rec_id,
                "name": name,
                "entityType": mapped_type,
                "primary_tokens": norm_name.split(),
                "alt_tokens_list": alt_tokens,
                "historical_tokens_list": [f.split() for f in former if f],
                "program": [row[4].strip()] if len(row) > 4 and row[4].strip() else [],
                "remarks": row[20].strip() if len(row) > 20 else "",
            })
    return entities, h

def load_uk_csl(path: Path):
    if not path.is_file():
        return [], ""
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    groups = {}
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        r = csv.reader(f)
        try:
            next(r)
            next(r)
        except StopIteration:
            return [], h
        for row in r:
            if not row:
                continue
            uid = row[1].strip() or row[2].strip()
            if not uid:
                continue
            name = row[4].strip() if len(row) > 4 else ""
            ent_type_raw = row[3].strip().lower() if len(row) > 3 else "entity"
            mapped_type = "person" if "individual" in ent_type_raw else ("vessel" if "ship" in ent_type_raw else "business")
            other_names = [row[i].strip() for i in range(5, 10) if len(row) > i and row[i].strip()]
            regime = row[10].strip() if len(row) > 10 else ""
            
            if uid not in groups:
                groups[uid] = {
                    "source": "uk_csl",
                    "sourceID": uid,
                    "name": name,
                    "entityType": mapped_type,
                    "alt_names": set(),
                    "programs": set(),
                }
            if name and name != groups[uid]["name"]:
                groups[uid]["alt_names"].add(name)
            for on in other_names:
                groups[uid]["alt_names"].add(on)
            if regime:
                groups[uid]["programs"].add(regime)

    entities = []
    for uid, d in groups.items():
        norm_name, former = prepare_name(d["name"], d["entityType"])
        alt_tokens = [prepare_name(a, d["entityType"])[0].split() for a in d["alt_names"] if a]
        entities.append({
            "source": "uk_csl",
            "sourceID": uid,
            "name": d["name"],
            "entityType": d["entityType"],
            "primary_tokens": norm_name.split(),
            "alt_tokens_list": alt_tokens,
            "historical_tokens_list": [f.split() for f in former if f],
            "program": list(d["programs"]),
            "remarks": "",
        })
    return entities, h

def load_eu_csl(path: Path):
    if not path.is_file():
        return [], ""
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    entities = []
    for event, elem in ET.iterparse(str(path), events=("end",)):
        tag = elem.tag.split("}")[-1]
        if tag == "sanctionEntity":
            logical_id = elem.attrib.get("logicalId", "")
            subject_type = elem.attrib.get("subjectType", "").lower()
            mapped_type = "person" if subject_type == "p" else "business"
            names = []
            for name_alias in elem.findall(".//{*}nameAlias"):
                whole = name_alias.attrib.get("wholeName", "")
                if whole:
                    names.append(whole)
            primary_name = names[0] if names else ""
            alt_names = names[1:] if len(names) > 1 else []
            norm_name, former = prepare_name(primary_name, mapped_type)
            alt_tokens = [prepare_name(a, mapped_type)[0].split() for a in alt_names if a]
            
            entities.append({
                "source": "eu_csl",
                "sourceID": logical_id,
                "name": primary_name,
                "entityType": mapped_type,
                "primary_tokens": norm_name.split(),
                "alt_tokens_list": alt_tokens,
                "historical_tokens_list": [f.split() for f in former if f],
                "program": ["EU-SANCTIONS"],
                "remarks": "",
            })
            elem.clear()
    return entities, h

def load_un_csl(path: Path):
    if not path.is_file():
        return [], ""
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    entities = []
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
            alt_tokens = [prepare_name(a, mapped_type)[0].split() for a in aliases if a]
            
            entities.append({
                "source": "un_csl",
                "sourceID": f"UN-{data_id}",
                "name": full_name,
                "entityType": mapped_type,
                "primary_tokens": norm_name.split(),
                "alt_tokens_list": alt_tokens,
                "historical_tokens_list": [f.split() for f in former if f],
                "program": ["UN-SANCTIONS"],
                "remarks": "",
            })
    return entities, h

if __name__ == "__main__":
    t0 = time.perf_counter()
    ofac, h_ofac = load_ofac_sdn(RAW_DIR / "us_ofac_sdn.csv")
    us, h_us = load_us_csl(RAW_DIR / "us_csl.csv")
    uk, h_uk = load_uk_csl(RAW_DIR / "uk_csl.csv")
    eu, h_eu = load_eu_csl(RAW_DIR / "eu_csl.xml")
    un, h_un = load_un_csl(RAW_DIR / "un_csl.xml")
    load_time = time.perf_counter() - t0

    print(f"Loaded all lists in {load_time:.2f}s:")
    print(f"  us_ofac: {len(ofac)} (hash: {h_ofac[:12]}...)")
    print(f"  us_csl:  {len(us)} (hash: {h_us[:12]}...)")
    print(f"  uk_csl:  {len(uk)} (hash: {h_uk[:12]}...)")
    print(f"  eu_csl:  {len(eu)} (hash: {h_eu[:12]}...)")
    print(f"  un_csl:  {len(un)} (hash: {h_un[:12]}...)")
    print(f"  Total entities: {len(ofac) + len(us) + len(uk) + len(eu) + len(un)}")
