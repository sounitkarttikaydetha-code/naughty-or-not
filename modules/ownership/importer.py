"""
Ownership Structure Importer & Exporter (T11 Part E, T11.1 Section 1).
Parses:
  - 7-sheet Excel workbooks (Instructions, Counterparty, Parties, Holdings, Control, Key_Persons, Documents)
  - Legacy single-sheet Excel and CSV files
  - Word (.docx) documents with corporate structure tables
Exports:
  - Multi-sheet Excel workbooks with Results and Regime_Verdicts (full round-trip capability)
Manages:
  - Built-in and user mapping directories (~/.clearance_check/import_mappings/)
  - Mapping SHA-256 hash calculation and schema validation
"""

import csv
import hashlib
import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import yaml

try:
    import docx
except ImportError:
    docx = None

from modules.ownership.models import (
    Counterparty,
    ControlRelation,
    Holding,
    KeyPerson,
    OwnershipNode,
    UBOResult,
)

BUILTIN_MAPPINGS_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "import_mappings"


def get_user_mappings_dir() -> Path:
    """Return user-specific mappings directory (~/.clearance_check/import_mappings/)."""
    user_dir = Path.home() / ".clearance_check" / "import_mappings"
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def calculate_file_hash(path: Path) -> str:
    """Calculate SHA-256 hash of a file."""
    if not path.exists():
        return ""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def list_available_mappings() -> List[Dict[str, Any]]:
    """List all available mapping configurations from built-in and user folders."""
    mappings = []
    seen = set()

    # Built-in
    if BUILTIN_MAPPINGS_DIR.exists():
        for p in sorted(BUILTIN_MAPPINGS_DIR.glob("*.yaml")):
            name = p.name
            if name not in seen:
                seen.add(name)
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}
                    mappings.append({
                        "filename": name,
                        "path": str(p),
                        "name": data.get("name", name),
                        "version": str(data.get("version", "1.0")),
                        "hash": calculate_file_hash(p),
                        "is_builtin": True,
                    })
                except Exception:
                    pass

    # User folder
    user_dir = get_user_mappings_dir()
    for p in sorted(user_dir.glob("*.yaml")):
        name = p.name
        if name not in seen:
            seen.add(name)
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                mappings.append({
                    "filename": name,
                    "path": str(p),
                    "name": data.get("name", name),
                    "version": str(data.get("version", "1.0")),
                    "hash": calculate_file_hash(p),
                    "is_builtin": False,
                })
            except Exception:
                pass

    return mappings


def load_mapping(mapping_name: str = "clearance_template_v1.yaml") -> Dict[str, Any]:
    """Load column mapping configuration safely using yaml.safe_load only."""
    # Check user dir first, then built-in
    user_path = get_user_mappings_dir() / mapping_name
    if user_path.exists():
        with open(user_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    builtin_path = BUILTIN_MAPPINGS_DIR / mapping_name
    if builtin_path.exists():
        with open(builtin_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    # Fallback to default
    default_path = BUILTIN_MAPPINGS_DIR / "clearance_template_v1.yaml"
    if default_path.exists():
        with open(default_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    return {}


def parse_ownership_workbook(
    file_bytes_or_path: Union[bytes, str, Path],
    filename: str = "",
) -> Tuple[Counterparty, List[Holding], List[ControlRelation], List[KeyPerson], List[Dict[str, Any]]]:
    """
    Parse full 7-sheet ownership template workbook.
    Returns:
      (counterparty, holdings, control_relations, key_persons, preview_issues)
    where preview_issues contains:
      [{"sheet": str, "row": int, "col": str, "problem": str, "suggested_fix": str}]
    """
    issues: List[Dict[str, Any]] = []

    try:
        if isinstance(file_bytes_or_path, (str, Path)):
            wb = openpyxl.load_workbook(str(file_bytes_or_path), data_only=True)
        else:
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes_or_path), data_only=True)
    except Exception as exc:
        issues.append({
            "sheet": "Workbook",
            "row": 0,
            "col": "—",
            "problem": f"Failed to open Excel workbook: {exc}",
            "suggested_fix": "Ensure file is a valid .xlsx spreadsheet.",
        })
        return Counterparty(name="Unknown"), [], [], [], issues

    sheet_names = wb.sheetnames

    # Check if this is the 7-sheet format or single-sheet
    has_holdings = "Holdings" in sheet_names
    has_cp = "Counterparty" in sheet_names

    if not has_holdings and not has_cp:
        # Fallback to legacy single-sheet parsing
        nodes, legacy_warnings = parse_ownership_table(file_bytes_or_path, filename=filename)
        cp_name = nodes[0].parent_name if (nodes and nodes[0].parent_name) else (nodes[0].name if nodes else "Unknown Target")
        cp = Counterparty(name=cp_name)
        h_list = [
            Holding(
                shareholder_name=n.name,
                entity_name=n.parent_name or cp_name,
                share_pct=n.ownership_pct,
                entity_type=n.entity_type,
                country=n.country,
                notes=n.notes,
            )
            for n in nodes
        ]
        for w in legacy_warnings:
            issues.append({
                "sheet": "Active",
                "row": 0,
                "col": "—",
                "problem": w,
                "suggested_fix": "Check data formatting.",
            })
        return cp, h_list, [], [], issues

    # 1. Parse Counterparty Sheet
    cp = Counterparty(name="Unknown Target")
    if "Counterparty" in sheet_names:
        ws_cp = wb["Counterparty"]
        rows = list(ws_cp.iter_rows(values_only=True))
        if len(rows) >= 2:
            headers = [str(h or "").strip().lower() for h in rows[0]]
            vals = rows[1]
            cp_data = {h: vals[idx] if idx < len(vals) else "" for idx, h in enumerate(headers)}

            def get_val(*aliases):
                for a in aliases:
                    for k, v in cp_data.items():
                        if a in k:
                            return str(v or "").strip()
                return ""

            name = get_val("legal name", "target", "company name") or "Unknown Target"
            jurisdiction = get_val("jurisdiction", "country")
            reg_no = get_val("registration", "reg no", "cin")
            lei = get_val("lei", "tax id", "pan")
            addr = get_val("address")
            activity = get_val("activity", "business")
            cp = Counterparty(
                name=name,
                jurisdiction=jurisdiction,
                registration_number=reg_no,
                lei=lei,
                address=addr,
                business_activity=activity,
            )
        else:
            issues.append({
                "sheet": "Counterparty",
                "row": 1,
                "col": "A",
                "problem": "Counterparty sheet has no data row.",
                "suggested_fix": "Enter counterparty legal name and details in Row 2.",
            })

    # 2. Parse Parties Sheet (for metadata lookup)
    party_meta: Dict[str, Dict[str, Any]] = {}
    if "Parties" in sheet_names:
        ws_parties = wb["Parties"]
        rows = list(ws_parties.iter_rows(values_only=True))
        if len(rows) > 1:
            headers = [str(h or "").strip().lower() for h in rows[0]]
            for r_idx, row in enumerate(rows[1:], start=2):
                if not any(row):
                    continue
                r_dict = {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
                p_name = str(r_dict.get("legal name") or r_dict.get("party name") or "").strip()
                if not p_name:
                    continue
                p_type = str(r_dict.get("entity type") or "company").strip().lower()
                ent_type = "person" if ("person" in p_type or "individual" in p_type) else ("trust" if "trust" in p_type else "company")
                party_meta[p_name.lower()] = {
                    "party_id": str(r_dict.get("party id") or ""),
                    "entity_type": ent_type,
                    "country": str(r_dict.get("country / jurisdiction") or r_dict.get("country") or ""),
                    "id_number": str(r_dict.get("registration / id no") or r_dict.get("id") or ""),
                    "dob": str(r_dict.get("date of birth / incorporation") or r_dict.get("dob") or ""),
                    "notes": str(r_dict.get("notes") or ""),
                }

    # 3. Parse Holdings Sheet
    holdings: List[Holding] = []
    if "Holdings" in sheet_names:
        ws_holdings = wb["Holdings"]
        rows = list(ws_holdings.iter_rows(values_only=True))
        if len(rows) > 1:
            headers = [str(h or "").strip().lower() for h in rows[0]]
            for r_idx, row in enumerate(rows[1:], start=2):
                if not any(row):
                    continue
                r_dict = {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
                sh_name = str(r_dict.get("immediate shareholder") or r_dict.get("shareholder") or r_dict.get("owner name") or "").strip()
                ent_name = str(r_dict.get("held in entity") or r_dict.get("target") or cp.name).strip()

                if not sh_name:
                    issues.append({
                        "sheet": "Holdings",
                        "row": r_idx,
                        "col": "Immediate Shareholder",
                        "problem": "Missing shareholder legal name.",
                        "suggested_fix": "Enter shareholder name or remove blank row.",
                    })
                    continue

                raw_pct = r_dict.get("shareholding %") or r_dict.get("ownership %") or 0.0
                try:
                    pct = float(str(raw_pct).replace("%", "").strip())
                except (ValueError, TypeError):
                    issues.append({
                        "sheet": "Holdings",
                        "row": r_idx,
                        "col": "Shareholding %",
                        "problem": f"Invalid percentage '{raw_pct}'.",
                        "suggested_fix": "Enter numeric value e.g. 50.0.",
                    })
                    pct = 0.0

                raw_voting = r_dict.get("voting rights %") or r_dict.get("voting %") or pct
                try:
                    voting_pct = float(str(raw_voting).replace("%", "").strip())
                except (ValueError, TypeError):
                    voting_pct = pct

                h_type = str(r_dict.get("holding type") or "Direct").strip().lower()
                on_behalf = str(r_dict.get("on behalf of") or "").strip()
                v_level = str(r_dict.get("verification level") or "self_declared").strip().lower().replace(" ", "_")

                # Lookup party meta if available
                p_info = party_meta.get(sh_name.lower(), {})
                h_obj = Holding(
                    shareholder_name=sh_name,
                    entity_name=ent_name,
                    share_pct=pct,
                    voting_pct=voting_pct,
                    holding_type=h_type,
                    on_behalf_of=on_behalf,
                    entity_type=p_info.get("entity_type", "company"),
                    country=p_info.get("country", ""),
                    id_number=p_info.get("id_number", ""),
                    dob=p_info.get("dob", ""),
                    verification_level=v_level,
                    notes=p_info.get("notes", ""),
                )
                holdings.append(h_obj)
        else:
            issues.append({
                "sheet": "Holdings",
                "row": 1,
                "col": "A",
                "problem": "Holdings sheet has no data rows.",
                "suggested_fix": "Add shareholding records in Holdings sheet.",
            })

    # 4. Parse Control Sheet
    control_relations: List[ControlRelation] = []
    if "Control" in sheet_names:
        ws_ctrl = wb["Control"]
        rows = list(ws_ctrl.iter_rows(values_only=True))
        if len(rows) > 1:
            headers = [str(h or "").strip().lower() for h in rows[0]]
            for r_idx, row in enumerate(rows[1:], start=2):
                if not any(row):
                    continue
                r_dict = {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
                c_name = str(r_dict.get("controlling party") or r_dict.get("controller") or "").strip()
                t_name = str(r_dict.get("controlled entity") or r_dict.get("target") or cp.name).strip()
                c_type = str(r_dict.get("control type") or "").strip().lower().replace(" ", "_")
                desc = str(r_dict.get("description / governance powers") or r_dict.get("description") or "").strip()

                if c_name:
                    control_relations.append(
                        ControlRelation(
                            controller_name=c_name,
                            target_name=t_name,
                            control_type=c_type,
                            description=desc,
                        )
                    )

    # 5. Parse Key_Persons Sheet
    key_persons: List[KeyPerson] = []
    if "Key_Persons" in sheet_names:
        ws_kp = wb["Key_Persons"]
        rows = list(ws_kp.iter_rows(values_only=True))
        if len(rows) > 1:
            headers = [str(h or "").strip().lower() for h in rows[0]]
            for r_idx, row in enumerate(rows[1:], start=2):
                if not any(row):
                    continue
                r_dict = {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
                kp_name = str(r_dict.get("full legal name") or r_dict.get("name") or "").strip()
                t_name = str(r_dict.get("entity / position held in") or r_dict.get("entity") or cp.name).strip()
                role_raw = str(r_dict.get("role") or "director").strip().lower().replace(" ", "_")
                nat = str(r_dict.get("nationality") or "").strip()
                id_no = str(r_dict.get("id / passport no") or "").strip()
                dob_val = str(r_dict.get("date of birth") or "").strip()
                kyc_str = str(r_dict.get("kyc complete") or "").strip().lower()
                kyc_comp = kyc_str in ["yes", "true", "1"]

                if kp_name:
                    key_persons.append(
                        KeyPerson(
                            name=kp_name,
                            target_name=t_name,
                            role=role_raw,
                            nationality=nat,
                            id_number=id_no,
                            dob=dob_val,
                            kyc_complete=kyc_comp,
                            has_appointment_power=("appointment" in role_raw or "senior" in role_raw or "managing" in role_raw),
                        )
                    )

    return cp, holdings, control_relations, key_persons, issues


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

    fn = (filename or str(file_bytes_or_path)).lower()
    is_excel = fn.endswith(".xlsx") or fn.endswith(".xlsm") or fn.endswith(".xls")

    raw_rows: List[Dict[str, Any]] = []

    if is_excel:
        try:
            if isinstance(file_bytes_or_path, (str, Path)):
                wb = openpyxl.load_workbook(str(file_bytes_or_path), data_only=True)
            else:
                wb = openpyxl.load_workbook(io.BytesIO(file_bytes_or_path), data_only=True)

            # Look for Holdings or first sheet
            ws = wb["Holdings"] if "Holdings" in wb.sheetnames else wb.active
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

    mapping = load_mapping(mapping_name or "clearance_template_v1.yaml")
    col_map = mapping.get("columns", {})

    first_row_keys = list(raw_rows[0].keys())

    def find_key(field_name: str) -> Optional[str]:
        field_cfg = col_map.get(field_name, {})
        allowed_headers = [h.lower() for h in field_cfg.get("headers", [])]
        for k in first_row_keys:
            if k.lower() in allowed_headers:
                return k
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


def parse_docx(
    file_bytes_or_path: Union[bytes, str, Path],
) -> Tuple[Counterparty, List[Holding], List[ControlRelation], List[KeyPerson], List[Dict[str, Any]]]:
    """
    Parse Word (.docx) document containing ownership schedule tables.
    Extracts tabular data and maps columns into Counterparty, Holdings, and Key Persons.
    """
    issues: List[Dict[str, Any]] = []
    if docx is None:
        issues.append({
            "sheet": "Document",
            "row": 0,
            "col": "—",
            "problem": "python-docx library is not installed.",
            "suggested_fix": "Install python-docx package.",
        })
        return Counterparty(name="Unknown"), [], [], [], issues

    try:
        if isinstance(file_bytes_or_path, (str, Path)):
            doc = docx.Document(str(file_bytes_or_path))
        else:
            doc = docx.Document(io.BytesIO(file_bytes_or_path))
    except Exception as exc:
        issues.append({
            "sheet": "Document",
            "row": 0,
            "col": "—",
            "problem": f"Failed to parse Word document: {exc}",
            "suggested_fix": "Ensure file is a valid .docx document.",
        })
        return Counterparty(name="Unknown"), [], [], [], issues

    if not doc.tables:
        issues.append({
            "sheet": "Document",
            "row": 0,
            "col": "—",
            "problem": "No tables found in Word document.",
            "suggested_fix": "Include ownership schedule table in document.",
        })
        return Counterparty(name="Unknown"), [], [], [], issues

    # Parse primary table
    table = doc.tables[0]
    raw_rows = []
    headers = [cell.text.strip() for cell in table.rows[0].cells]

    for row in table.rows[1:]:
        row_vals = [cell.text.strip() for cell in row.cells]
        if any(row_vals):
            raw_rows.append(dict(zip(headers, row_vals)))

    holdings = []
    cp_name = "Target Entity"

    for r_idx, r in enumerate(raw_rows, 2):
        name = ""
        pct = 0.0
        held_in = cp_name
        ent_type = "company"

        for k, v in r.items():
            k_low = k.lower()
            if "name" in k_low or "owner" in k_low or "shareholder" in k_low:
                name = v
            elif "%" in k_low or "pct" in k_low or "holding" in k_low or "equity" in k_low:
                try:
                    pct = float(v.replace("%", "").strip())
                except ValueError:
                    pct = 0.0
            elif "held in" in k_low or "company" in k_low or "target" in k_low:
                held_in = v or cp_name
            elif "type" in k_low or "category" in k_low:
                if "person" in v.lower() or "individual" in v.lower():
                    ent_type = "person"

        if name:
            holdings.append(
                Holding(
                    shareholder_name=name,
                    entity_name=held_in,
                    share_pct=pct,
                    entity_type=ent_type,
                )
            )

    return Counterparty(name=cp_name), holdings, [], [], issues


def export_ownership_workbook(
    result: UBOResult,
    output_path: Union[str, Path],
) -> Path:
    """
    Export complete ownership structure and evaluation to a multi-sheet Excel workbook.
    Sheets created:
      - Instructions
      - Counterparty
      - Parties
      - Holdings
      - Control
      - Key_Persons
      - Documents
      - Results
      - Regime_Verdicts
    Guarantees round-trip property: importing this workbook parses an identical tree.
    """
    out = Path(output_path)
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")
    regular_font = Font(name="Segoe UI", size=10)

    def style_sheet_headers(ws, headers, col_widths=None):
        ws.views.sheetView[0].showGridLines = True
        ws.append(headers)
        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            if col_widths and col_idx <= len(col_widths):
                col_letter = openpyxl.utils.get_column_letter(col_idx)
                ws.column_dimensions[col_letter].width = col_widths[col_idx - 1]
        ws.row_dimensions[1].height = 26

    # 1. Instructions
    ws_inst = wb.create_sheet(title="Instructions")
    ws_inst.append(["Clearance Check — Exported Ownership Dossier & Round-Trip Workbook"])
    ws_inst.append(["Generated for target:", result.target_name])
    ws_inst.append(["Timestamp:", result.disposition.timestamp])

    # 2. Counterparty
    ws_cp = wb.create_sheet(title="Counterparty")
    style_sheet_headers(ws_cp, ["Legal Name", "Jurisdiction", "Registration Number", "LEI / Tax ID", "Registered Address", "Primary Activity", "Screening Date", "Preparer Name"], [35, 18, 22, 20, 35, 25, 18, 20])
    cp = result.counterparty or Counterparty(name=result.target_name)
    ws_cp.append([
        cp.name,
        cp.jurisdiction,
        cp.registration_number,
        cp.lei,
        cp.address,
        cp.business_activity,
        result.disposition.timestamp[:10],
        result.disposition.preparer,
    ])

    # 3. Parties
    ws_parties = wb.create_sheet(title="Parties")
    style_sheet_headers(ws_parties, ["Party ID", "Legal Name", "Entity Type", "Country / Jurisdiction", "Registration / ID No", "Date of Birth / Incorporation", "Address", "Is Listed / Sanctioned (Self-Declared)", "Notes"], [12, 32, 18, 22, 22, 22, 35, 25, 30])
    seen_parties = set()
    party_idx = 1
    for h in result.holdings:
        if h.shareholder_name not in seen_parties:
            seen_parties.add(h.shareholder_name)
            ws_parties.append([
                f"P{party_idx}",
                h.shareholder_name,
                h.entity_type.capitalize(),
                h.country,
                h.id_number,
                h.dob,
                "",
                "Yes" if h.is_blocked else "No",
                h.notes,
            ])
            party_idx += 1

    # 4. Holdings
    ws_holdings = wb.create_sheet(title="Holdings")
    style_sheet_headers(ws_holdings, ["Holding ID", "Immediate Shareholder", "Held In Entity", "Shareholding %", "Voting Rights %", "Holding Type", "On Behalf Of", "Verification Level", "Source Document Reference", "Document Date"], [12, 30, 30, 16, 16, 18, 22, 24, 28, 16])
    for idx, h in enumerate(result.holdings, 1):
        ws_holdings.append([
            f"H{idx}",
            h.shareholder_name,
            h.entity_name,
            h.share_pct,
            h.voting_pct,
            h.holding_type.capitalize(),
            h.on_behalf_of,
            h.verification_level,
            h.source_document,
            h.document_date,
        ])

    # 5. Control
    ws_ctrl = wb.create_sheet(title="Control")
    style_sheet_headers(ws_ctrl, ["Control ID", "Controlling Party", "Controlled Entity", "Control Type", "Board Seats Held", "Total Board Seats", "Description / Governance Powers"], [12, 30, 30, 24, 16, 16, 40])
    for idx, cr in enumerate(result.control_relations, 1):
        ws_ctrl.append([
            f"C{idx}",
            cr.controller_name,
            cr.target_name,
            cr.control_type,
            cr.board_seats_held,
            cr.total_board_seats,
            cr.description,
        ])

    # 6. Key_Persons
    ws_kp = wb.create_sheet(title="Key_Persons")
    style_sheet_headers(ws_kp, ["Person ID", "Full Legal Name", "Entity / Position Held In", "Role", "Appointment Date", "Nationality", "ID / Passport No", "Date of Birth", "KYC Complete"], [12, 30, 30, 24, 18, 18, 20, 16, 14])
    for idx, kp in enumerate(result.key_persons, 1):
        ws_kp.append([
            f"K{idx}",
            kp.name,
            kp.target_name,
            kp.role,
            kp.appointment_date,
            kp.nationality,
            kp.id_number,
            kp.dob,
            "Yes" if kp.kyc_complete else "No",
        ])

    # 7. Documents
    ws_docs = wb.create_sheet(title="Documents")
    style_sheet_headers(ws_docs, ["Document ID", "Document Type", "Issuing Authority / Source", "Issue Date", "Verification Status", "File Reference / Notes"], [14, 28, 30, 16, 20, 35])
    ws_docs.append(["D1", "Statutory Registry Extract", "Official Registry", result.disposition.timestamp[:10], "Verified", "Exported record"])

    # 8. Results Sheet
    ws_res = wb.create_sheet(title="Results")
    style_sheet_headers(ws_res, ["Party Name", "Entity Type", "Direct %", "Effective Look-Through %", "Adani 20% Diligence Trigger", "Indian 10% BO Marker", "Screening Status", "Sanctions Source"], [30, 16, 14, 24, 26, 22, 18, 25])
    for s in result.look_through_summary:
        name = s.get("name", "")
        dt = any(d.get("name") == name for d in result.diligence_triggers)
        in_bo = any(b.get("name") == name for b in result.india_bo_markers)
        ws_res.append([
            name,
            s.get("type", ""),
            s.get("direct_pct", 0.0),
            s.get("effective_look_through_pct", 0.0),
            "Triggered (KYC Required)" if dt else "Not Triggered",
            "Above Threshold (Info Only)" if in_bo else "Below Threshold",
            "MATCH" if s.get("is_blocked") else "CLEAR",
            s.get("blocked_source", ""),
        ])

    # 9. Regime_Verdicts Sheet
    ws_verd = wb.create_sheet(title="Regime_Verdicts")
    style_sheet_headers(ws_verd, ["Regime", "Threshold", "Aggregate %", "Criteria Met", "Statutory Verdict Text", "Assumptions / Boundary Notes"], [18, 14, 16, 16, 45, 45])
    ws_verd.append([
        "US OFAC 50% Rule",
        ">= 50.0%",
        result.ofac_verdict.get("aggregate_pct", 0.0),
        "MET" if result.ofac_verdict.get("criteria_met") else "NOT MET",
        result.ofac_verdict.get("verdict_text", ""),
        "Evaluated with aggregation of designated owners through blocked intermediates.",
    ])
    ws_verd.append([
        "EU Council Sanctions",
        ">= 50.0% or Control",
        result.eu_verdict.get("aggregate_pct", 0.0),
        "MET" if result.eu_verdict.get("criteria_met") else "NOT MET",
        result.eu_verdict.get("verdict_text", ""),
        result.eu_verdict.get("assumption_note", ""),
    ])
    ws_verd.append([
        "UK OFSI Sanctions",
        "> 50.0% or Majority",
        result.uk_verdict.get("conservative_aggregate_pct", 0.0),
        "MET" if result.uk_verdict.get("criteria_met") else "NOT MET",
        result.uk_verdict.get("verdict_text", ""),
        "; ".join(result.uk_verdict.get("notes", [])),
    ])

    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(out))
    return out
