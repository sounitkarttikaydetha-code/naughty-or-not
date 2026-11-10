import re
from pathlib import Path

LOADER_PY = Path("modules/engine/loader.py")
content = LOADER_PY.read_text(encoding="utf-8")

# 1. OFAC
old_ofac = """            raw_dict = {
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
                    "remarks": remarks,
                },
            }"""

new_ofac = """            title_c = row[4].strip() if len(row) > 4 else ""
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
            }"""

# 2. US CSL
old_us_csl = """            raw_dict = {
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
                "addresses": [],
                "sourceData": {
                    "id": rec_id,
                    "name": name,
                    "program": programs,
                    "remarks": remarks,
                },
            }"""

new_us_csl = """            raw_fields = {
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
            }"""

# 3. UK CSL group collection
old_uk_csl_grp = """            if uid not in groups:
                groups[uid] = {
                    "sourceID": uid,
                    "name": row_full_name,
                    "entityType": mapped_type,
                    "alt_names": set(),
                    "programs": set(),
                    "all_text": row_full_name,
                }
            if mapped_type == "person":
                groups[uid]["entityType"] = "person"

            if not groups[uid]["name"]:
                groups[uid]["name"] = row_full_name
            elif row_full_name and row_full_name != groups[uid]["name"]:
                groups[uid]["alt_names"].add(row_full_name)

            if regime:
                groups[uid]["programs"].add(regime)
            groups[uid]["all_text"] += " " + " ".join(row)"""

new_uk_csl_grp = """            if uid not in groups:
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
                        groups[uid]["raw_fields"][col] += f"; {row[i].strip()}" """

old_uk_csl_dict = """        raw_dict = {
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
            "addresses": [],
            "sourceData": {
                "uniqueID": uid,
                "name": primary_name,
                "program": list(d["programs"]),
            },
        }"""

new_uk_csl_dict = """        rf = d.get("raw_fields", {})
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
        }"""

# Normalize content newlines for replace
content_norm = content.replace("\r\n", "\n")

assert old_ofac in content_norm, "old_ofac not found"
content_norm = content_norm.replace(old_ofac, new_ofac, 1)

assert old_us_csl in content_norm, "old_us_csl not found"
content_norm = content_norm.replace(old_us_csl, new_us_csl, 1)

assert old_uk_csl_grp in content_norm, "old_uk_csl_grp not found"
content_norm = content_norm.replace(old_uk_csl_grp, new_uk_csl_grp, 1)

assert old_uk_csl_dict in content_norm, "old_uk_csl_dict not found"
content_norm = content_norm.replace(old_uk_csl_dict, new_uk_csl_dict, 1)

# 4. EU CSL
old_eu_csl = """                raw_dict = {
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
                    },
                }"""

new_eu_csl = """                eu_raw = {k: v for k, v in elem.attrib.items() if v}
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
                }"""

assert old_eu_csl in content_norm, "old_eu_csl not found"
content_norm = content_norm.replace(old_eu_csl, new_eu_csl, 1)

# 5. UN CSL
old_un_csl = """                raw_dict = {
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
                    },
                }"""

new_un_csl = """                un_raw = {}
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
                }"""

assert old_un_csl in content_norm, "old_un_csl not found"
content_norm = content_norm.replace(old_un_csl, new_un_csl, 1)

# Save back with CRLF
LOADER_PY.write_text(content_norm.replace("\n", "\r\n"), encoding="utf-8")
print("Successfully patched modules/engine/loader.py with full raw fields!")
