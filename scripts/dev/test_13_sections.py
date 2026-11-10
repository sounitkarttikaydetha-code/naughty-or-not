import json
from collections import OrderedDict
from typing import Any, Dict, List, Tuple

SECTION_NAMES = [
    "1. Primary name and entity type",
    "2. Aliases and alternative spellings",
    "3. Dates and places of birth",
    "4. Nationality and citizenship",
    "5. Addresses",
    "6. Identification documents",
    "7. Programmes, regimes and legal basis",
    "8. Listing details",
    "9. Remarks and statement of reasons",
    "10. Vessel, aircraft or entity specifics",
    "11. Related or linked entities",
    "12. Other fields (as published)",
    "13. Source link, and the date of our copy",
]

def format_val(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, (list, tuple)):
        clean = [format_val(x) for x in val if x and str(x).strip() not in ["", "-0-", "None", "null"]]
        return "; ".join(clean) if clean else ""
    if isinstance(val, dict):
        parts = [f"{k}: {format_val(v)}" for k, v in val.items() if v and str(v).strip() not in ["", "-0-", "None", "null"]]
        return ", ".join(parts) if parts else ""
    s = str(val).strip()
    return "" if s in ["", "-0-", "None", "null", "—"] else s

def build_13_sections(record: Dict[str, Any], source_id: str = "") -> Dict[str, List[Tuple[str, str]]]:
    if not record:
        return {}
    
    sections = OrderedDict((name, []) for name in SECTION_NAMES)
    claimed_keys = set()

    def add(sec_idx: int, label: str, val: Any, key_name: str = ""):
        fval = format_val(val)
        if fval:
            sections[SECTION_NAMES[sec_idx - 1]].append((label, fval))
            if key_name:
                claimed_keys.add(key_name)

    raw_fields = record.get("raw_fields") or {}
    sdata = record.get("sourceData") or {}
    person = record.get("person") or {}
    biz = record.get("business") or {}
    aircraft = record.get("aircraft") or {}
    vessel = record.get("vessel") or {}

    # Section 1: Primary name and entity type
    p_name = record.get("name") or record.get("primary_name") or record.get("sdnName") or raw_fields.get("sdn_name") or raw_fields.get("name")
    etype = record.get("entityType") or record.get("entity_type") or record.get("schema") or raw_fields.get("type") or raw_fields.get("sdn_type") or raw_fields.get("subjectType")
    add(1, "Primary Listed Name", p_name, "name")
    add(1, "Entity Type", etype, "entityType")
    claimed_keys.update(["primary_name", "sdnName", "schema", "entity_type"])

    # Section 2: Aliases and alternative spellings
    alts = (
        person.get("altNames")
        or biz.get("altNames")
        or record.get("aliases")
        or raw_fields.get("alt_names")
        or raw_fields.get("nameAlias")
        or raw_fields.get("INDIVIDUAL_ALIAS")
        or raw_fields.get("ENTITY_ALIAS")
    )
    add(2, "Alternate Names / Aliases", alts, "aliases")
    if "alt_types" in raw_fields:
        add(2, "Alias Types / Strength", raw_fields.get("alt_types"), "alt_types")
    if "Alias strength" in raw_fields:
        add(2, "Alias Strength", raw_fields.get("Alias strength"), "Alias strength")
    if "Name non-latin script" in raw_fields:
        add(2, "Non-Latin Script Name", raw_fields.get("Name non-latin script"), "Name non-latin script")
    claimed_keys.update(["altNames", "aliases", "nameAlias", "INDIVIDUAL_ALIAS", "ENTITY_ALIAS"])

    # Section 3: Dates and places of birth
    dobs = person.get("datesOfBirth") or raw_fields.get("dates_of_birth") or raw_fields.get("D.O.B") or raw_fields.get("dob") or raw_fields.get("birthdate") or raw_fields.get("INDIVIDUAL_DATE_OF_BIRTH")
    pobs = person.get("placesOfBirth") or raw_fields.get("places_of_birth") or raw_fields.get("Town of birth") or raw_fields.get("Country of birth") or raw_fields.get("INDIVIDUAL_PLACE_OF_BIRTH")
    add(3, "Dates of Birth", dobs, "dates_of_birth")
    add(3, "Places of Birth", pobs, "places_of_birth")
    claimed_keys.update(["datesOfBirth", "placesOfBirth", "D.O.B", "dob", "birthdate", "INDIVIDUAL_DATE_OF_BIRTH", "INDIVIDUAL_PLACE_OF_BIRTH", "Town of birth", "Country of birth"])

    # Section 4: Nationality and citizenship
    nats = person.get("nationalities") or person.get("citizenships") or raw_fields.get("nationalities") or raw_fields.get("citizenships") or raw_fields.get("Nationality(/ies)") or raw_fields.get("nationality") or raw_fields.get("citizenship") or raw_fields.get("NATIONALITY")
    add(4, "Nationality / Citizenship", nats, "nationalities")
    claimed_keys.update(["nationalities", "citizenships", "Nationality(/ies)", "nationality", "citizenship", "NATIONALITY"])

    # Section 5: Addresses
    addrs = record.get("addresses") or raw_fields.get("addresses") or raw_fields.get("address") or raw_fields.get("INDIVIDUAL_ADDRESS") or raw_fields.get("ENTITY_ADDRESS")
    # Also check UK address columns
    uk_addr_cols = [c for c in raw_fields if c.startswith("Address Line") or c in ["Address Postal Code", "Address Country"]]
    if uk_addr_cols and not addrs:
        addrs = [f"{c}: {raw_fields[c]}" for c in uk_addr_cols if raw_fields[c]]
    add(5, "Addresses", addrs, "addresses")
    claimed_keys.update(["addresses", "address", "INDIVIDUAL_ADDRESS", "ENTITY_ADDRESS"] + uk_addr_cols)

    # Section 6: Identification documents
    ids = record.get("identifications") or raw_fields.get("ids") or raw_fields.get("National Identifier number") or raw_fields.get("Passport number") or raw_fields.get("identification") or raw_fields.get("INDIVIDUAL_DOCUMENT") or raw_fields.get("passport_or_id")
    add(6, "Identification Documents", ids, "identifications")
    claimed_keys.update(["identifications", "ids", "National Identifier number", "Passport number", "identification", "INDIVIDUAL_DOCUMENT", "passport_or_id"])

    # Section 7: Programmes, regimes and legal basis
    progs = sdata.get("program") or record.get("programs") or record.get("program") or raw_fields.get("programs") or raw_fields.get("Regime Name") or raw_fields.get("schedule") or raw_fields.get("regulation")
    add(7, "Sanctions Programmes / Regimes", progs, "programs")
    if "Sanctions Imposed" in raw_fields:
        add(7, "Sanctions Imposed", raw_fields.get("Sanctions Imposed"), "Sanctions Imposed")
    claimed_keys.update(["program", "programs", "Regime Name", "schedule", "regulation", "Sanctions Imposed"])

    # Section 8: Listing details
    rid = record.get("sourceID") or record.get("id") or raw_fields.get("Unique ID") or raw_fields.get("OFSI Group ID") or raw_fields.get("UN Reference Number") or raw_fields.get("DATAID")
    add(8, "Source Record Identifier", rid, "sourceID")
    add(8, "Designation / Listed Date", raw_fields.get("Date Designated") or raw_fields.get("start_date") or raw_fields.get("LISTED_ON") or raw_fields.get("publication_date"), "start_date")
    add(8, "Last Updated Date", raw_fields.get("Last Updated") or raw_fields.get("LAST_DAY_UPDATED") or raw_fields.get("updated_at"), "Last Updated")
    add(8, "Federal Register Notice", raw_fields.get("federal_register_notice") or raw_fields.get("federal_register_citation") or raw_fields.get("notification_number"), "federal_register_notice")
    claimed_keys.update(["sourceID", "id", "Unique ID", "OFSI Group ID", "UN Reference Number", "DATAID", "Date Designated", "start_date", "LISTED_ON", "Last Updated", "LAST_DAY_UPDATED", "federal_register_notice", "federal_register_citation", "notification_number", "updated_at"])

    # Section 9: Remarks and statement of reasons
    rems = sdata.get("remarks") or record.get("remarks") or raw_fields.get("remarks") or raw_fields.get("UK Statement of Reasons") or raw_fields.get("Other Information") or raw_fields.get("COMMENTS1") or raw_fields.get("offenses_or_remarks") or raw_fields.get("summary")
    add(9, "Remarks / Statement of Reasons", rems, "remarks")
    claimed_keys.update(["remarks", "UK Statement of Reasons", "Other Information", "COMMENTS1", "offenses_or_remarks", "summary"])

    # Section 10: Vessel, aircraft or entity specifics
    # Aircraft
    add(10, "Tail Number", aircraft.get("current_tail_number") or raw_fields.get("current_tail_number") or raw_fields.get("tailNumber"), "current_tail_number")
    add(10, "Previous Tail", aircraft.get("previous_tail_number") or raw_fields.get("previous_tail_number"), "previous_tail_number")
    add(10, "Serial Number (MSN)", aircraft.get("msn") or raw_fields.get("msn") or raw_fields.get("serialNumber"), "msn")
    add(10, "Aircraft Type", aircraft.get("aircraft_type") or raw_fields.get("aircraft_type") or raw_fields.get("type"), "aircraft_type")
    add(10, "AOC Number", raw_fields.get("aoc_number"), "aoc_number")
    add(10, "ICAO Code", raw_fields.get("icao_code"), "icao_code")
    # Vessel
    add(10, "Call Sign", sdata.get("callSign") or raw_fields.get("call_sign"), "call_sign")
    add(10, "Vessel Flag", sdata.get("vesselFlag") or raw_fields.get("vessel_flag") or raw_fields.get("Current believed flag of ship"), "vessel_flag")
    add(10, "Vessel Type", sdata.get("vesselType") or raw_fields.get("vessel_type") or raw_fields.get("Type of ship"), "vessel_type")
    add(10, "Tonnage / GRT", sdata.get("tonnage") or sdata.get("grossRegisteredTonnage") or raw_fields.get("gross_tonnage") or raw_fields.get("Tonnage of ship"), "tonnage")
    add(10, "IMO Number", raw_fields.get("IMO number") or raw_fields.get("imo_number"), "IMO number")
    # Entity specifics
    add(10, "Title / Position", sdata.get("title") or raw_fields.get("title") or raw_fields.get("Position"), "title")
    add(10, "Gender", person.get("gender") or raw_fields.get("Gender") or raw_fields.get("gender"), "gender")
    add(10, "Business Registration Number", raw_fields.get("Business registration number (s)") or raw_fields.get("tax_id") or raw_fields.get("reg_number"), "Business registration number (s)")
    claimed_keys.update([
        "current_tail_number", "previous_tail_number", "msn", "aircraft_type", "aoc_number", "icao_code",
        "call_sign", "vessel_flag", "vessel_type", "tonnage", "gross_tonnage", "gross_registered_tonnage",
        "IMO number", "imo_number", "title", "Position", "gender", "Gender", "Business registration number (s)",
        "tailNumber", "serialNumber", "Current believed flag of ship", "Type of ship", "Tonnage of ship"
    ])

    # Section 11: Related or linked entities
    add(11, "Parent Organization", raw_fields.get("Parent company") or raw_fields.get("parent_organization"), "parent_organization")
    add(11, "Subsidiaries", raw_fields.get("Subsidiaries"), "Subsidiaries")
    add(11, "Owner / Operator", aircraft.get("owner_operator") or raw_fields.get("owner_operator") or raw_fields.get("Current owner/operator (s)"), "owner_operator")
    claimed_keys.update(["Parent company", "parent_organization", "Subsidiaries", "owner_operator", "Current owner/operator (s)"])

    # Section 13: Source link, and date of copy
    s_url = raw_fields.get("source_list_url") or raw_fields.get("source_information_url") or raw_fields.get("source_url") or raw_fields.get("publicationUrl") or raw_fields.get("Website")
    add(13, "Official Source URL", s_url, "source_url")
    s_list = record.get("sourceList") or record.get("source") or source_id
    add(13, "Source List Authority", s_list, "sourceList")
    claimed_keys.update(["source_list_url", "source_information_url", "source_url", "publicationUrl", "Website", "sourceList", "source", "sourceData", "person", "business", "aircraft", "vessel", "organization", "raw_fields"])

    # Section 12: Other fields (as published) - Catch all unmapped non-empty fields!
    # Check top-level record keys
    for k, v in record.items():
        if k not in claimed_keys and v is not None:
            fv = format_val(v)
            if fv:
                add(12, k, fv, k)
    # Check raw_fields keys
    for k, v in raw_fields.items():
        if k not in claimed_keys and v is not None:
            fv = format_val(v)
            if fv:
                add(12, k, fv, k)

    # Return only non-empty sections
    clean_sections = OrderedDict()
    for sec_name, items in sections.items():
        if items:
            clean_sections[sec_name] = items

    return clean_sections

if __name__ == "__main__":
    sample = {
        "name": "Acme Test Corp",
        "entityType": "Organisation",
        "sourceList": "uk_csl",
        "sourceID": "UK-999",
        "raw_fields": {
            "UK Statement of Reasons": "Involved in illicit proliferation finance.",
            "Business registration number (s)": "12345678",
            "CustomUnmappedNewField2026": "Value from future regulatory release",
        }
    }
    res = build_13_sections(sample, "uk_csl")
    for sec, fields in res.items():
        print(f"\n[{sec}]")
        for lbl, val in fields:
            print(f"  • {lbl}: {val}")
