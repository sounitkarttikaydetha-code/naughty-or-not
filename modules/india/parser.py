"""Parsers for Ministry of Home Affairs (MHA), Government of India UAPA lists:
1. First Schedule: Terrorist Organisations (Section 35) - PDF
2. Fourth Schedule: Terrorist Individuals (Section 35) - HTML/paginated
3. Unlawful Associations: Section 3 UAPA - HTML/paginated

Incorporates OpenSanctions MIT crawler mapping logic for splitting sub-groups,
fronts, wings, and alias extraction.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from pypdf import PdfReader

logger = logging.getLogger(__name__)

def _resolve_india_data_dir() -> Path:
    try:
        from modules.common.paths import get_lists_dir, get_seed_data_dir
        p = get_lists_dir() / "india"
        if p.is_dir() and any(p.iterdir()):
            return p
        seed = get_seed_data_dir() / "india"
        if seed.is_dir():
            return seed
    except Exception:
        pass
    return Path(__file__).resolve().parent.parent.parent / "data" / "india"

DATA_DIR = _resolve_india_data_dir()

SOURCES = {
    "first_schedule": {
        "local_file": DATA_DIR / "first_schedule.pdf",
        "publication_date": "2026-10-01",
        "url": "https://www.mha.gov.in/files/documents/List46TerroristOrganisationsWebsite.pdf",
    },
    "fourth_schedule": {
        "local_file": DATA_DIR / "fourth_schedule_all_pages.html",
        "fallback_json": DATA_DIR / "individuals_all.json",
        "publication_date": "2026-07-04",
        "url": "https://www.mha.gov.in/individuals-terrorists-fourth-schedule-unlawful-activities-prevention-act",
    },
    "unlawful_associations": {
        "local_file": DATA_DIR / "unlawful_associations_all_pages.html",
        "fallback_json": DATA_DIR / "unlawful_associations_all.json",
        "publication_date": "2025-03-17",
        "url": "https://www.mha.gov.in/unlawful-associations-section3-unlawful-activities-prevention-act-1967",
    },
}

CLEAN_BOILERPLATE_RE = re.compile(
    r"\s*(and all its manifestations and front Organisations?|"
    r"all its formations and front Organisations?|"
    r"all its manifestations and front organisations?|"
    r"and all its manifestations|"
    r"all its manifestations\.?|"
    r", all its formations and front Organizations\.?|"
    r"and front organisations\.?)\s*$",
    re.IGNORECASE,
)

ACRONYM_RE = re.compile(r"\((?P<acronym>[A-Z0-9\-/]{2,})\)")


def extract_acronyms_and_clean(name: str) -> tuple[str, list[str]]:
    """Extract acronyms like (TRF), (PAFF), (SBN) and clean name."""
    acronyms = ACRONYM_RE.findall(name)
    cleaned = ACRONYM_RE.sub("", name).strip()
    return cleaned, [a for a in acronyms if a]


def parse_first_schedule(pdf_path: Optional[Path] = None) -> Dict[str, Any]:
    """Parse First Schedule (Terrorist Organisations under UAPA Section 35).
    Returns:
      {
        "status": "OK" | "FAILED",
        "error": Optional[str],
        "last_good_date": "2026-10-01",
        "entities": [ ... ]
      }
    """
    path = pdf_path or SOURCES["first_schedule"]["local_file"]
    last_good_date = SOURCES["first_schedule"]["publication_date"]

    if not path.is_file():
        logger.warning(f"First Schedule PDF not found at {path}")
        return {
            "status": "FAILED",
            "error": f"File not found: {path}",
            "last_good_date": last_good_date,
            "entities": [],
        }

    entities: List[Dict[str, Any]] = []

    try:
        reader = PdfReader(str(path))
        full_text = "\n".join(page.extract_text() for page in reader.pages)

        # Parse numbered rows: 1. Babbar Khalsa ...
        lines = full_text.splitlines()
        raw_items: List[tuple[int, str]] = []
        cur_num: Optional[int] = None
        cur_text: List[str] = []

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            m = re.match(r"^(\d+)\.\s*(.*)", line_str)
            if m:
                if cur_num is not None:
                    raw_items.append((cur_num, " ".join(cur_text).strip()))
                cur_num = int(m.group(1))
                cur_text = [m.group(2)]
            elif cur_num is not None:
                if (
                    not line_str.startswith("***")
                    and "LIST OF ORGANISATIONS" not in line_str
                    and "SCHEDULE OF THE ACT" not in line_str
                    and "Name of Terrorist Organization" not in line_str
                ):
                    cur_text.append(line_str)

        if cur_num is not None:
            raw_items.append((cur_num, " ".join(cur_text).strip()))

        for num, raw_name in raw_items:
            # Entry 33 is the generic reference to UN list (handled by UN CSL)
            if num == 33 and "UN Prevention and Suppression" in raw_name:
                continue

            # Strip trailing boilerplate
            clean_row = CLEAN_BOILERPLATE_RE.sub("", raw_name).strip().rstrip(".")

            # Special split handling per OpenSanctions MIT crawler
            if num == 5:
                # Lashkar-E-Taiba/Pasban-E-Ahle Hadis/ The Resistance Front
                # OpenSanctions: Lashkar-E-Taiba with aliases Pasban-E-Ahle Hadis, The Resistance Front
                # Also treat The Resistance Front as front entity with parent Lashkar-E-Taiba
                entities.append({
                    "id": f"IN-UAPA-ORG-{num}",
                    "schema": "Organization",
                    "authority_id": str(num),
                    "name": "Lashkar-E-Taiba",
                    "aliases": ["Pasban-E-Ahle Hadis", "The Resistance Front", "TRF", "LeT"],
                    "parent_organization": None,
                    "schedule": "First Schedule (Terrorist Organisations)",
                    "source_url": SOURCES["first_schedule"]["url"],
                })
                # Front entity
                entities.append({
                    "id": f"IN-UAPA-ORG-{num}-TRF",
                    "schema": "Organization",
                    "authority_id": str(num),
                    "name": "The Resistance Front",
                    "aliases": ["TRF"],
                    "parent_organization": "Lashkar-E-Taiba",
                    "schedule": "First Schedule (Terrorist Organisations)",
                    "source_url": SOURCES["first_schedule"]["url"],
                })
                continue

            if num == 6:
                # Jaish-E-Mohammed/Tahreik-E-Furquan/ People's Anti -Fascist-Front (PAFF)
                entities.append({
                    "id": f"IN-UAPA-ORG-{num}",
                    "schema": "Organization",
                    "authority_id": str(num),
                    "name": "Jaish-E-Mohammed",
                    "aliases": ["Tahreik-E-Furquan", "Tahreik-E-Furqan", "People's Anti-Fascist-Front", "PAFF", "JeM"],
                    "parent_organization": None,
                    "schedule": "First Schedule (Terrorist Organisations)",
                    "source_url": SOURCES["first_schedule"]["url"],
                })
                entities.append({
                    "id": f"IN-UAPA-ORG-{num}-PAFF",
                    "schema": "Organization",
                    "authority_id": str(num),
                    "name": "People's Anti-Fascist-Front",
                    "aliases": ["PAFF"],
                    "parent_organization": "Jaish-E-Mohammed",
                    "schedule": "First Schedule (Terrorist Organisations)",
                    "source_url": SOURCES["first_schedule"]["url"],
                })
                continue

            if num == 38:
                # Islamic State / ... / Daish and ISKP
                entities.append({
                    "id": f"IN-UAPA-ORG-{num}-ISIL",
                    "schema": "Organization",
                    "authority_id": str(num),
                    "name": "Islamic State",
                    "aliases": [
                        "Islamic State of Iraq and Levant",
                        "Islamic State of Iraq and Syria",
                        "ISIL",
                        "ISIS",
                        "Daish",
                    ],
                    "parent_organization": None,
                    "schedule": "First Schedule (Terrorist Organisations)",
                    "source_url": SOURCES["first_schedule"]["url"],
                })
                entities.append({
                    "id": f"IN-UAPA-ORG-{num}-ISKP",
                    "schema": "Organization",
                    "authority_id": str(num),
                    "name": "Islamic State in Khorasan Province",
                    "aliases": [
                        "ISKP",
                        "ISIS Wilayat Khorasan",
                        "Islamic State of Iraq and the Sham- Khorasan",
                        "ISISK",
                    ],
                    "parent_organization": "Islamic State",
                    "schedule": "First Schedule (Terrorist Organisations)",
                    "source_url": SOURCES["first_schedule"]["url"],
                })
                continue

            # General entry: split on / or or
            parts = [p.strip() for p in re.split(r"\s*/\s*|\s+or\s+", clean_row) if p.strip()]
            primary_raw = parts[0]
            clean_primary, primary_acronyms = extract_acronyms_and_clean(primary_raw)

            aliases: List[str] = list(primary_acronyms)
            for extra in parts[1:]:
                clean_extra, extra_acronyms = extract_acronyms_and_clean(extra)
                if clean_extra and clean_extra not in aliases and clean_extra != clean_primary:
                    aliases.append(clean_extra)
                for ea in extra_acronyms:
                    if ea not in aliases:
                        aliases.append(ea)

            entities.append({
                "id": f"IN-UAPA-ORG-{num}",
                "schema": "Organization",
                "authority_id": str(num),
                "name": clean_primary,
                "aliases": aliases,
                "parent_organization": None,
                "schedule": "First Schedule (Terrorist Organisations)",
                "source_url": SOURCES["first_schedule"]["url"],
            })

    except Exception as e:
        logger.error(f"Error parsing First Schedule PDF {path}: {e}")
        return {
            "status": "FAILED",
            "error": str(e),
            "last_good_date": last_good_date,
            "entities": [],
        }

    return {
        "status": "OK",
        "error": None,
        "last_good_date": last_good_date,
        "entities": entities,
    }


def parse_fourth_schedule(html_path: Optional[Path] = None, allow_fallback: bool = True) -> Dict[str, Any]:
    """Parse Fourth Schedule (Terrorist Individuals under UAPA Section 35).
    Extracts individual names and aliases separated by '@'.
    Returns:
      {
        "status": "OK" | "FAILED",
        "error": Optional[str],
        "last_good_date": "2026-07-04",
        "entities": [ ... ]
      }
    """
    path = html_path or SOURCES["fourth_schedule"]["local_file"]
    fallback = SOURCES["fourth_schedule"]["fallback_json"]
    last_good_date = SOURCES["fourth_schedule"]["publication_date"]

    raw_records: List[str] = []

    if path.is_file():
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            # If the file happens to be JSON (e.g. individuals_all.json)
            if content.strip().startswith("[") or content.strip().startswith("{"):
                try:
                    jdata = json.loads(content)
                    if isinstance(jdata, list):
                        raw_records = [str(x) for x in jdata if x]
                except Exception:
                    pass
            if not raw_records:
                matches = re.findall(
                    r'<div[^>]*class="[^"]*documentRecordTitle[^"]*"[^>]*>(.*?)</div>',
                    content,
                    re.DOTALL,
                )
                for m in matches:
                    clean_t = " ".join(re.sub(r"<[^>]+>", " ", m).split())
                    if clean_t and clean_t not in raw_records:
                        raw_records.append(clean_t)
        except Exception as e:
            logger.warning(f"Error reading {path}: {e}")

    # If raw_records has fewer than 50 entries, merge/fallback with full corpus
    if len(raw_records) < 50 and allow_fallback:
        all_pages = DATA_DIR / "fourth_schedule_all_pages.html"
        full_found: List[str] = []
        if all_pages.is_file():
            try:
                ap_content = all_pages.read_text(encoding="utf-8", errors="ignore")
                matches = re.findall(
                    r'<div[^>]*class="[^"]*documentRecordTitle[^"]*"[^>]*>(.*?)</div>',
                    ap_content,
                    re.DOTALL,
                )
                for m in matches:
                    clean_t = " ".join(re.sub(r"<[^>]+>", " ", m).split())
                    if clean_t and clean_t not in full_found:
                        full_found.append(clean_t)
            except Exception:
                pass
        if len(full_found) < 50 and fallback.is_file():
            try:
                fb_data = json.load(fallback.open(encoding="utf-8"))
                for fb in fb_data:
                    if fb not in full_found:
                        full_found.append(fb)
            except Exception:
                pass
        if full_found:
            for r in raw_records:
                if r not in full_found:
                    full_found.insert(0, r)
            raw_records = full_found

    if not raw_records:
        return {
            "status": "FAILED",
            "error": f"No records found in {path} or fallback",
            "last_good_date": last_good_date,
            "entities": [],
        }

    entities: List[Dict[str, Any]] = []

    # Load official registry to look up authoritative serial numbers rather than calculating len - i
    registry_file = DATA_DIR / "fourth_schedule_registry.json"
    registry_by_raw: Dict[str, int] = {}
    registry_by_primary: Dict[str, int] = {}
    if registry_file.is_file():
        try:
            with open(registry_file, "r", encoding="utf-8") as rf:
                reg_data = json.load(rf)
                for entry in reg_data:
                    registry_by_raw[entry["raw_title"].strip()] = entry["sno"]
                    registry_by_primary[entry["primary"].strip().lower()] = entry["sno"]
        except Exception as e:
            logger.warning(f"Error reading fourth_schedule_registry.json: {e}")

    total_records = len(raw_records)
    for i, row in enumerate(raw_records):
        parts = [p.strip().rstrip(".").strip() for p in row.split("@") if p.strip()]
        if not parts:
            continue
        primary = parts[0]
        aliases = [p for p in parts[1:] if p and p != primary]

        # Use authoritative serial number from official registry
        mha_sno = (
            registry_by_raw.get(row.strip())
            or registry_by_primary.get(primary.strip().lower())
            or (total_records - i)
        )

        entities.append({
            "id": f"IN-UAPA-IND-{mha_sno}",
            "schema": "Person",
            "authority_id": str(mha_sno),
            "name": primary,
            "aliases": aliases,
            "parent_organization": None,
            "schedule": "Fourth Schedule (Terrorist Individuals)",
            "source_url": SOURCES["fourth_schedule"]["url"],
        })

    return {
        "status": "OK",
        "error": None,
        "last_good_date": last_good_date,
        "entities": entities,
    }


def parse_unlawful_associations(html_path: Optional[Path] = None, allow_fallback: bool = True) -> Dict[str, Any]:
    """Parse Unlawful Associations under Section 3 of UAPA.
    Applies OpenSanctions MIT splitting for sub-groups, fronts, and wings:
      - Meitei Extremist Organizations of Manipur (PLA, RPF, UNLF, MPA, PREPAK, Red Army, KCP, KYKL, CorCom, ASUK)
      - Popular Front of India (PFI) and its associates/affiliates/fronts (CFI, RIF, etc.)
      - JKPL factions
    Returns:
      {
        "status": "OK" | "FAILED",
        "error": Optional[str],
        "last_good_date": "2025-03-17",
        "entities": [ ... ]
      }
    """
    path = html_path or SOURCES["unlawful_associations"]["local_file"]
    fallback = SOURCES["unlawful_associations"]["fallback_json"]
    last_good_date = SOURCES["unlawful_associations"]["publication_date"]

    raw_records: List[str] = []

    if path.is_file():
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            matches = re.findall(
                r'<div[^>]*class="[^"]*documentRecordTitle[^"]*"[^>]*>(.*?)</div>',
                content,
                re.DOTALL,
            )
            for m in matches:
                clean_t = " ".join(re.sub(r"<[^>]+>", " ", m).split())
                if clean_t and clean_t not in raw_records:
                    raw_records.append(clean_t)
        except Exception as e:
            logger.warning(f"Error reading {path}: {e}")

    if len(raw_records) < 20 and allow_fallback:
        all_pages = DATA_DIR / "unlawful_associations_all_pages.html"
        full_found: List[str] = []
        if all_pages.is_file():
            try:
                ap_content = all_pages.read_text(encoding="utf-8", errors="ignore")
                matches = re.findall(
                    r'<div[^>]*class="[^"]*documentRecordTitle[^"]*"[^>]*>(.*?)</div>',
                    ap_content,
                    re.DOTALL,
                )
                for m in matches:
                    clean_t = " ".join(re.sub(r"<[^>]+>", " ", m).split())
                    if clean_t and clean_t not in full_found:
                        full_found.append(clean_t)
            except Exception:
                pass
        if len(full_found) < 20 and fallback.is_file():
            try:
                fb_data = json.load(fallback.open(encoding="utf-8"))
                for fb in fb_data:
                    if fb not in full_found:
                        full_found.append(fb)
            except Exception:
                pass
        if full_found:
            for r in raw_records:
                if r not in full_found:
                    full_found.insert(0, r)
            raw_records = full_found

    if not raw_records:
        return {
            "status": "FAILED",
            "error": f"No records found in {path} or fallback",
            "last_good_date": last_good_date,
            "entities": [],
        }

    entities: List[Dict[str, Any]] = []

    for idx, row in enumerate(raw_records, 1):
        clean_row = CLEAN_BOILERPLATE_RE.sub("", row).strip().rstrip(".")

        # Case 1: Meitei Extremist Organizations of Manipur
        if "Meitei Extremist Organization" in clean_row or "CorCom" in clean_row:
            # Parent entity
            entities.append({
                "id": f"IN-UAPA-ASSOC-{idx}-MEITEI",
                "schema": "Organization",
                "authority_id": str(idx),
                "name": "Meitei Extremist Organizations",
                "aliases": ["Meitei Extremist Organization of Manipur"],
                "parent_organization": None,
                "schedule": "Unlawful Associations (Section 3)",
                "source_url": SOURCES["unlawful_associations"]["url"],
            })

            # Sub-groups and wings from OpenSanctions mapping & S.O. 4899(E)
            meitei_groups = [
                ("Peoples' Liberation Army", ["PLA"], "Peoples' Liberation Army (PLA)"),
                ("Revolutionary Peoples' Front", ["RPF"], "Revolutionary Peoples' Front (RPF)"),
                ("United National Liberation Front", ["UNLF"], "United National Liberation Front (UNLF)"),
                ("Manipur Peoples' Army", ["MPA"], "Manipur Peoples' Army (MPA)"),
                ("Peoples' Revolutionary Party of Kangleipak", ["PREPAK"], "Peoples' Revolutionary Party of Kangleipak (PREPAK)"),
                ("Red Army", [], "Red Army"),
                ("Kangleipak Communist Party", ["KCP"], "Kangleipak Communist Party (KCP)"),
                ("Kanglei Yaol Kanba Lup", ["KYKL"], "Kanglei Yaol Kanba Lup (KYKL)"),
                ("Coordination Committee", ["CorCom"], "Coordination Committee (CorCom)"),
                ("Alliance for Socialist Unity Kangleipak", ["ASUK"], "Alliance for Socialist Unity Kangleipak (ASUK)"),
            ]

            for sub_name, sub_aliases, sub_display in meitei_groups:
                entities.append({
                    "id": f"IN-UAPA-ASSOC-{idx}-{sub_name.replace(' ', '_')}",
                    "schema": "Organization",
                    "authority_id": str(idx),
                    "name": sub_name,
                    "aliases": sub_aliases + ([sub_display] if sub_display != sub_name else []),
                    "parent_organization": "Meitei Extremist Organizations",
                    "schedule": "Unlawful Associations (Section 3)",
                    "source_url": SOURCES["unlawful_associations"]["url"],
                })
            continue

        # Case 2: Popular Front of India (PFI) & fronts (S.O. 4560(E))
        if "Popular Front of India" in clean_row or "(PFI)" in clean_row:
            entities.append({
                "id": f"IN-UAPA-ASSOC-{idx}-PFI",
                "schema": "Organization",
                "authority_id": str(idx),
                "name": "Popular Front of India",
                "aliases": ["PFI"],
                "parent_organization": None,
                "schedule": "Unlawful Associations (Section 3)",
                "source_url": SOURCES["unlawful_associations"]["url"],
            })

            # Banned fronts/affiliates under S.O. 4560(E)
            pfi_fronts = [
                ("Campus Front of India", ["CFI"]),
                ("Rehab India Foundation", ["RIF"]),
                ("All India Imams Council", ["AIIC"]),
                ("National Confederation of Human Rights Organization", ["NCHRO"]),
                ("National Women's Front", ["NWF"]),
                ("Junior Front", []),
                ("Empower India Foundation", ["EIF"]),
                ("Rehab Foundation, Kerala", ["Rehab Foundation"]),
            ]

            for f_name, f_aliases in pfi_fronts:
                entities.append({
                    "id": f"IN-UAPA-ASSOC-{idx}-{f_name.replace(' ', '_')}",
                    "schema": "Organization",
                    "authority_id": str(idx),
                    "name": f_name,
                    "aliases": f_aliases,
                    "parent_organization": "Popular Front of India",
                    "schedule": "Unlawful Associations (Section 3)",
                    "source_url": SOURCES["unlawful_associations"]["url"],
                })
            continue

        # Case 3: JKPL factions
        if "Jammu and Kashmir Peoples League" in clean_row or "JKPL" in clean_row:
            jkpl_factions = [
                ("JKPL (Mukhtar Ahmed Waza)", ["Jammu and Kashmir Peoples League (Mukhtar Ahmed Waza)"]),
                ("JKPL (Bashir Ahmad Tota)", ["Jammu and Kashmir Peoples League (Bashir Ahmad Tota)"]),
                (
                    "JKPL (Ghulam Mohammad Khan @Sopori)",
                    [
                        "Jammu and Kashmir Peoples Political League",
                        "JKPL (Ghulam Mohammad Khan Sopori)",
                    ],
                ),
                ("JKPL (Aziz Sheikh)", ["Jammu and Kashmir Peoples League (Aziz Sheikh)"]),
            ]
            for fac_name, fac_aliases in jkpl_factions:
                entities.append({
                    "id": f"IN-UAPA-ASSOC-{idx}-{fac_name.replace(' ', '_')[:30]}",
                    "schema": "Organization",
                    "authority_id": str(idx),
                    "name": fac_name,
                    "aliases": fac_aliases,
                    "parent_organization": "Jammu and Kashmir Peoples League",
                    "schedule": "Unlawful Associations (Section 3)",
                    "source_url": SOURCES["unlawful_associations"]["url"],
                })
            continue

        # Default: clean acronym and name
        clean_name, acronyms = extract_acronyms_and_clean(clean_row)
        entities.append({
            "id": f"IN-UAPA-ASSOC-{idx}",
            "schema": "Organization",
            "authority_id": str(idx),
            "name": clean_name,
            "aliases": acronyms,
            "parent_organization": None,
            "schedule": "Unlawful Associations (Section 3)",
            "source_url": SOURCES["unlawful_associations"]["url"],
        })

    return {
        "status": "OK",
        "error": None,
        "last_good_date": last_good_date,
        "entities": entities,
    }
