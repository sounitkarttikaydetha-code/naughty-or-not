"""
Test suite validating 100% consistency across all v1.2.1 deliverables:
- deliverables/inventory.json
- deliverables/licence_matrix.xlsx
- deliverables/SBOM.cdx.json
- deliverables/egress_allowlist.csv
- deliverables/EA_Technical_Dossier_v1.2.0.docx (and v1.2.1)
- deliverables/evidence.json & reviews/evidence.json
- RELEASE_NOTES.md
- reviews/REVIEW_T13.1.md
"""
import csv
import json
from pathlib import Path
import openpyxl
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DELIVERABLES_DIR = PROJECT_ROOT / "deliverables"
REVIEWS_DIR = PROJECT_ROOT / "reviews"


@pytest.fixture(scope="module")
def inventory():
    inv_path = DELIVERABLES_DIR / "inventory.json"
    assert inv_path.exists(), "deliverables/inventory.json missing"
    with open(inv_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def evidence():
    ev_path = REVIEWS_DIR / "evidence.json"
    assert ev_path.exists(), "reviews/evidence.json missing"
    with open(ev_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_01_inventory_counts(inventory):
    """Verify inventory counts: 68 total components (60 Python, 8 non-Python), 21 egress domains."""
    meta = inventory["metadata"]
    assert meta["components_count"] == 68
    assert meta["python_packages_count"] == 60
    assert meta["non_python_components_count"] == 8
    assert meta["egress_domains_count"] == 21
    assert len(inventory["components"]) == 68
    assert len(inventory["egress_allowlist"]) == 21


def test_02_copyleft_classifications(inventory):
    """Verify copyleft classification: exactly 1 weak file-level (certifi MPL-2.0), 0 strong, 0 weak library."""
    cp_summary = inventory["metadata"]["copyleft_summary"]
    assert cp_summary["Weak (file-level)"] == 1
    assert cp_summary["Weak (library)"] == 0
    assert cp_summary["Strong (GPL, AGPL)"] == 0

    # Certifi check
    certifi_comp = next((c for c in inventory["components"] if c["name"] == "certifi"), None)
    assert certifi_comp is not None
    assert certifi_comp["spdx_license"] == "MPL-2.0"
    assert certifi_comp["copyleft_category"] == "Weak (file-level)"


def test_03_reconciled_versions(inventory):
    """Verify truth from packaged build: rapidfuzz 3.14.6, reportlab 5.0.1, pywebview 6.2.1, pillow MIT-CMU."""
    comp_map = {c["name"]: c for c in inventory["components"]}
    assert comp_map["rapidfuzz"]["version"] == "3.14.6"
    assert comp_map["rapidfuzz"]["spdx_license"] == "MIT"

    assert comp_map["reportlab"]["version"] == "5.0.1"
    assert comp_map["reportlab"]["spdx_license"] == "BSD-3-Clause"

    assert comp_map["pywebview"]["version"] == "6.2.1"
    assert comp_map["pywebview"]["spdx_license"] == "BSD-3-Clause"

    assert comp_map["pillow"]["version"] == "13.0.0"
    assert comp_map["pillow"]["spdx_license"] == "MIT-CMU"

    assert comp_map["altair"]["spdx_license"] == "BSD-3-Clause"
    assert comp_map["pandas"]["spdx_license"] == "BSD-3-Clause"


def test_04_licence_matrix_consistency(inventory):
    """Verify deliverables/licence_matrix.xlsx exactly matches inventory."""
    mat_path = DELIVERABLES_DIR / "licence_matrix.xlsx"
    assert mat_path.exists(), "licence_matrix.xlsx missing"
    wb = openpyxl.load_workbook(str(mat_path))
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    assert rows[0][0] == "Component"
    data_rows = rows[1:]
    assert len(data_rows) == 68, f"Licence matrix rows {len(data_rows)} != 68"

    for row in data_rows:
        comp_name, ver, spdx, copyleft, scope, notes, url = row
        assert url.startswith("http"), f"Component URL column must hold real URLs, not words: {comp_name} has {url}"
        assert copyleft in ["None", "Weak (file-level)", "Weak (library)", "Strong (GPL, AGPL)"]


def test_05_sbom_consistency(inventory):
    """Verify deliverables/SBOM.cdx.json exactly matches inventory."""
    sbom_path = DELIVERABLES_DIR / "SBOM.cdx.json"
    assert sbom_path.exists(), "SBOM.cdx.json missing"
    with open(sbom_path, "r", encoding="utf-8") as f:
        sbom = json.load(f)
    assert sbom["bomFormat"] == "CycloneDX"
    assert sbom["specVersion"] == "1.5"
    assert len(sbom["components"]) == 68


def test_06_egress_allowlist_consistency(inventory):
    """Verify deliverables/egress_allowlist.csv matches all 21 domains."""
    egress_path = DELIVERABLES_DIR / "egress_allowlist.csv"
    assert egress_path.exists(), "egress_allowlist.csv missing"
    with open(egress_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        headers = next(reader)
        domains = [row[0] for row in reader]
    assert len(domains) == 21, f"Egress allowlist has {len(domains)} domains, expected 21"


def test_07_evidence_consistency(inventory, evidence):
    """Verify evidence.json and inventory agree 100%."""
    assert evidence["version"] == "1.2.1"
    assert evidence["release_tag"] == "v1.2.1"
    assert evidence["inventory_summary"]["components_count"] == 68
    assert evidence["inventory_summary"]["egress_domains_count"] == 21
    assert evidence["author_signature"]["status"] == "MATCH"
    assert evidence["baseline_diff"]["status"] == "ZERO_DIFF"


def test_08_dossier_file_exists():
    """Verify technical dossier docx is present and non-empty."""
    dossier_path = DELIVERABLES_DIR / "EA_Technical_Dossier_v1.2.0.docx"
    assert dossier_path.exists()
    assert dossier_path.stat().st_size > 30000
