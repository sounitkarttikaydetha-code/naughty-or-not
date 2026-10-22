"""
Synthetic OpenSanctions FollowTheMoney (FtM) JSON Lines Generator per T10-2.
Generates invented test entities only, with visible synthetic markers:
- Dataset ID: 'synthetic_opensanctions_test'
- Header marker: 'SYNTHETIC TEST DATA - EVALUATION ONLY'
- Fixed seed (42) for deterministic output
- Edge cases: aliases, non-Latin scripts (Cyrillic, Arabic, Devanagari), empty fields,
  very long names, duplicate IDs, malformed lines.
"""

import json
import os
import random
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Invented name pools (all strictly fictional / synthetic)
FIRST_NAMES = [
    "Aarav", "Zephyr", "Kaelen", "Morrigan", "Siddhartha", "Liora", "Tariq",
    "Dmitri", "Bran", "Cassian", "Vespera", "Elysia", "Theron", "Ronan", "Nadira"
]
LAST_NAMES = [
    "Vanderberg", "Novikov", "Al-Qasimi", "Chakraborty", "Silverstone", "Kowalski",
    "Drakos", "Montague", "Belmont", "Haverford", "Pendleton", "Al-Mansoor", "Sharma"
]
CORP_PREFIXES = [
    "AeroSynthetica", "QuantumFreight", "SolarisLogistics", "VortexVentures",
    "ZephyrHolding", "CaspianMaritime", "HyperionIndustrial", "PangeaEnergy"
]
CORP_SUFFIXES = [
    "Global Trade LLC", "Holdings Corp", "International JSC", "Enterprises Group",
    "Shipping Lines S.A.", "Logistics FZE", "Industries Limited", "Consulting PJSC"
]

NON_LATIN_PAIRS = [
    ("АэроСинтетика Логистикс", "ru"),
    ("شركة النورس للملاحة", "ar"),
    ("सिंथेथिक्स इंटरनेशनल कॉर्पोरेशन", "hi"),
    ("Восточно-Европейский Торговый Дом", "ru"),
]


def generate_synthetic_record(idx: int, is_edge_case: bool = False) -> dict:
    """Generate a single FollowTheMoney entity object."""
    entity_id = f"synthetic-ent-{idx:07d}"
    is_person = (idx % 2 == 0)

    if is_person:
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        name = f"{first} {last}"
        schema = "Person"
        aliases = [f"{last}, {first}"]
        if idx % 3 == 0:
            aliases.append(f"{first[0]}. {last}")
        props = {
            "name": [name],
            "alias": aliases,
            "birthDate": [f"{1960 + (idx % 40):04d}-{(idx % 12) + 1:02d}-{(idx % 28) + 1:02d}"],
            "nationality": [random.choice(["ae", "in", "cy", "sg", "ch", "ru"])],
            "topics": ["sanction"],
            "notes": ["SYNTHETIC TEST DATA - Evaluation only"],
        }
    else:
        prefix = random.choice(CORP_PREFIXES)
        suffix = random.choice(CORP_SUFFIXES)
        name = f"{prefix} {suffix}"
        schema = "Company"
        aliases = [f"{prefix} Group", f"{prefix} {suffix.split()[0]}"]
        props = {
            "name": [name],
            "alias": aliases,
            "jurisdiction": [random.choice(["ae", "in", "cy", "sg", "ch", "ru"])],
            "topics": ["sanction"],
            "notes": ["SYNTHETIC TEST DATA - Evaluation only"],
        }

    # Edge cases
    if is_edge_case:
        case_type = idx % 5
        if case_type == 0:
            # Multi-script non-Latin
            nl_name, lang = random.choice(NON_LATIN_PAIRS)
            props["name"].append(nl_name)
            props["alias"].append(nl_name)
        elif case_type == 1:
            # Empty optional fields
            props["alias"] = []
            if "birthDate" in props:
                del props["birthDate"]
        elif case_type == 2:
            # Very long name (> 150 chars)
            long_name = f"Consolidated International Synthetic Trading Transport And Multimodal Logistics Conglomerate Branch {idx:05d} Corporation Limited"
            props["name"] = [long_name]
        elif case_type == 3:
            # Duplicate ID candidate (reuse previous ID)
            entity_id = f"synthetic-ent-{max(1, idx - 1):07d}"

    return {
        "id": entity_id,
        "schema": schema,
        "caption": props["name"][0],
        "properties": props,
        "datasets": ["synthetic_opensanctions_test"],
    }


def generate_synthetic_dataset(count: int, output_path: Path, seed: int = 42):
    """Write synthetic FollowTheMoney JSON Lines file."""
    random.seed(seed)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    header_meta = {
        "_synthetic_header": True,
        "dataset": "synthetic_opensanctions_test",
        "marker": "SYNTHETIC TEST DATA",
        "total_records": count,
        "seed": seed,
        "license": "CC0-Synthetic-Evaluation",
    }

    with open(output_path, "w", encoding="utf-8") as f:
        # 1. Header marker line
        f.write(json.dumps(header_meta) + "\n")

        # 2. Entity lines
        for i in range(1, count + 1):
            is_edge = (i % 25 == 0)
            rec = generate_synthetic_record(i, is_edge_case=is_edge)
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

            # Insert one deliberate malformed row near index 500 for robustness testing
            if i == 500:
                f.write('{"id": "malformed_row", "schema": "InvalidSchema", UNTERMINATED_JSON\n')

    print(f"Generated {count} synthetic records at {output_path} ({output_path.stat().st_size / (1024*1024):.2f} MB)")


def main():
    fixtures_dir = PROJECT_ROOT / "tests" / "fixtures"

    print("Generating synthetic OpenSanctions fixtures (seed=42)...")
    # 1k fixture
    generate_synthetic_dataset(1_000, fixtures_dir / "synthetic_os_1k.ftm.json", seed=42)

    # 50k fixture
    generate_synthetic_dataset(50_000, fixtures_dir / "synthetic_os_50k.ftm.json", seed=42)

    # 500k fixture
    # Note: 500k is generated on-demand or during stress test run
    if "--all" in sys.argv or "--500k" in sys.argv:
        generate_synthetic_dataset(500_000, fixtures_dir / "synthetic_os_500k.ftm.json", seed=42)


if __name__ == "__main__":
    main()
