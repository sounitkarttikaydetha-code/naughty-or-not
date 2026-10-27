"""
Ownership Structure Importer (T11 Part E).
Parses Excel (.xlsx) and CSV files into OwnershipNode instances based on
configurable column mappings or auto-detected headers.
"""

import csv
import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import openpyxl
import yaml

from modules.ownership.models import OwnershipNode

MAPPINGS_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "import_mappings"


def load_mapping(mapping_name: str = "clearance_template_v1.yaml") -> Dict[str, Any]:
    """Load column mapping configuration."""
    path = MAPPINGS_DIR / mapping_name
    if not path.exists():
        # Fallback to default
        path = MAPPINGS_DIR / "clearance_template_v1.yaml"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def parse_ownership_table(
    file_bytes_or_path: Union[bytes, str, Path],
    filename: str = "",
    mapping_name: Optional[str] = None,
) -> Tuple[List[OwnershipNode], List[str]]:
    """
    Parse Excel or CSV table into List[OwnershipNode].
    Returns (nodes, warnings).
    """
    nodes: List[OwnershipNode] = []
    warnings: List[str] = []

    # Detect file type
    fn = (filename or str(file_bytes_or_path)).lower()
    is_excel = fn.endswith(".xlsx") or fn.endswith(".xlsm") or fn.endswith(".xls")

    raw_rows: List[Dict[str, Any]] = []

    if is_excel:
        try:
            if isinstance(file_bytes_or_path, (str, Path)):
                wb = openpyxl.load_workbook(str(file_bytes_or_path), data_only=True)
            else:
                wb = openpyxl.load_workbook(io.BytesIO(file_bytes_or_path), data_only=True)

            ws = wb.active
            rows_iter = ws.iter_rows(values_only=True)
            header_row = next(rows_iter, None)
            if not header_row:
                warnings.append("Excel sheet is completely empty.")
                return [], warnings

            headers = [str(h).strip() if h is not None else "" for h in header_row]

            for row in rows_iter:
                if not any(row):
                    continue
                row_dict = {}
                for h, val in zip(headers, row):
                    if h:
                        row_dict[h] = val
                raw_rows.append(row_dict)
        except Exception as exc:
            warnings.append(f"Failed to read Excel workbook: {exc}")
            return [], warnings
    else:
        # CSV parsing
        try:
            if isinstance(file_bytes_or_path, (str, Path)):
                with open(file_bytes_or_path, "r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    raw_rows = list(reader)
            else:
                text = file_bytes_or_path.decode("utf-8-sig", errors="replace")
                reader = csv.DictReader(io.StringIO(text))
                raw_rows = list(reader)
        except Exception as exc:
            warnings.append(f"Failed to read CSV table: {exc}")
            return [], warnings

    if not raw_rows:
        warnings.append("No data rows found in uploaded file.")
        return [], warnings

    # Load mapping
    mapping = load_mapping(mapping_name or "clearance_template_v1.yaml")
    col_map = mapping.get("columns", {})

    # Match columns
    first_row_keys = list(raw_rows[0].keys())

    def find_key(field_name: str) -> Optional[str]:
        field_cfg = col_map.get(field_name, {})
        allowed_headers = [h.lower() for h in field_cfg.get("headers", [])]
        for k in first_row_keys:
            if k.lower() in allowed_headers:
                return k
        # Fallback to field_name substring
        for k in first_row_keys:
            if field_name.replace("_", " ") in k.lower():
                return k
        return None

    owner_key = find_key("owner_name")
    pct_key = find_key("ownership_pct")
    parent_key = find_key("parent_name")
    type_key = find_key("entity_type")
    country_key = find_key("country")
    board_key = find_key("is_board_member")
    appoint_key = find_key("has_appointment_power")
    notes_key = find_key("notes")

    if not owner_key or not pct_key:
        warnings.append(f"Could not identify required 'Owner Name' or 'Ownership %' columns. Found: {first_row_keys}")
        return [], warnings

    for idx, r in enumerate(raw_rows, 1):
        raw_name = str(r.get(owner_key) or "").strip()
        if not raw_name:
            continue

        # Parse percentage
        raw_pct = r.get(pct_key)
        try:
            if isinstance(raw_pct, (int, float)):
                pct = float(raw_pct)
            else:
                clean_pct_str = str(raw_pct).replace("%", "").strip()
                pct = float(clean_pct_str)
        except (ValueError, TypeError):
            warnings.append(f"Row {idx}: Invalid percentage value '{raw_pct}' for '{raw_name}'. Defaulted to 0.0%.")
            pct = 0.0

        raw_parent = str(r.get(parent_key) or "").strip() if parent_key else ""
        raw_type = str(r.get(type_key) or "company").strip().lower() if type_key else "company"
        if "person" in raw_type or "individual" in raw_type or "natural" in raw_type:
            ent_type = "person"
        elif "trust" in raw_type:
            ent_type = "trust"
        else:
            ent_type = "company"

        raw_country = str(r.get(country_key) or "").strip() if country_key else ""

        # Parse boolean flags
        def parse_bool(val: Any) -> bool:
            if isinstance(val, bool):
                return val
            s = str(val or "").strip().lower()
            return s in ["true", "yes", "y", "1"]

        is_board = parse_bool(r.get(board_key)) if board_key else False
        has_appoint = parse_bool(r.get(appoint_key)) if appoint_key else False
        notes_str = str(r.get(notes_key) or "").strip() if notes_key else ""

        nodes.append(
            OwnershipNode(
                name=raw_name,
                ownership_pct=pct,
                parent_name=raw_parent,
                entity_type=ent_type,
                country=raw_country,
                is_board_member=is_board,
                has_appointment_power=has_appoint,
                notes=notes_str,
            )
        )

    return nodes, warnings
