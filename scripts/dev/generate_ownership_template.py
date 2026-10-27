"""
Generate the standard 7-sheet Ownership & Control Excel Template (T11.1 Section 1).
Sheets:
  1. Instructions
  2. Counterparty
  3. Parties
  4. Holdings
  5. Control
  6. Key_Persons
  7. Documents
Includes styling and data validation dropdowns for allowed values.
"""

from pathlib import Path
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATE_PATH = PROJECT_ROOT / "templates" / "ownership_template.xlsx"


def create_template():
    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")
    instruction_title_font = Font(name="Segoe UI", size=14, bold=True, color="1B365D")
    subheading_font = Font(name="Segoe UI", size=11, bold=True, color="333333")
    regular_font = Font(name="Segoe UI", size=10)
    italic_font = Font(name="Segoe UI", size=9, italic=True, color="666666")

    thin_border = Border(
        left=Side(style='thin', color='CCCCCC'),
        right=Side(style='thin', color='CCCCCC'),
        top=Side(style='thin', color='CCCCCC'),
        bottom=Side(style='thin', color='CCCCCC')
    )

    # 1. Instructions Sheet
    ws_inst = wb.create_sheet(title="Instructions")
    ws_inst.views.sheetView[0].showGridLines = True
    ws_inst.column_dimensions['A'].width = 5
    ws_inst.column_dimensions['B'].width = 30
    ws_inst.column_dimensions['C'].width = 75

    ws_inst.append([])
    ws_inst.append(["", "CLEARANCE CHECK — BENEFICIAL OWNERSHIP & CONTROL SCHEDULE (7-SHEET TEMPLATE)"])
    ws_inst.cell(row=2, column=2).font = instruction_title_font

    instructions_data = [
        ("Overview", "This workbook captures corporate shareholding, intermediate structures, board governance, key persons, and verification evidence for sanctions & UBO clearance."),
        ("1. Counterparty", "Details of the primary legal entity being screened. Enter jurisdiction, registration number, and corporate identifiers."),
        ("2. Parties", "All entities and individuals appearing in the corporate ownership tree. Specify entity type (Company, Natural Person, Trust, etc.)."),
        ("3. Holdings", "Every shareholding tier. Immediate Shareholder -> Held In Entity with shareholding % and voting %. Total holdings into any entity must not exceed 100%."),
        ("4. Control", "Governance and board control rights (majority board appointment, dominant influence, veto rights) to evaluate EU/UK control rules."),
        ("5. Key_Persons", "Directors, Senior Managing Officials, Trustees, and Settlors. For holders >=20%, ensure DOB and ID are provided to avoid KYC incomplete warnings."),
        ("6. Documents", "Proof of ownership and corporate registry documentation supporting verification levels."),
        ("Adani SOP Trigger", "Holdings of 20.0% or greater (direct or look-through) trigger enhanced diligence under Adani Airports Sanctions Compliance SOP."),
        ("Indian BO Marker", "Holdings of 10.0% or greater are flagged with the Indian beneficial-owner marker (Companies SBO Rules)."),
        ("Multilateral Sanctions", "Evaluated against US OFAC 50% Rule (50% or more, aggregate), EU 50% Rule (>=50% ownership or control), and UK OFSI (>50% shares/votes or board majority)."),
    ]

    curr_row = 4
    for topic, desc in instructions_data:
        ws_inst.cell(row=curr_row, column=2, value=topic).font = subheading_font
        ws_inst.cell(row=curr_row, column=3, value=desc).font = regular_font
        curr_row += 1

    # Helper function to style header row
    def style_headers(ws, headers, col_widths=None):
        ws.views.sheetView[0].showGridLines = True
        ws.append(headers)
        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = thin_border
            if col_widths and col_idx <= len(col_widths):
                col_letter = openpyxl.utils.get_column_letter(col_idx)
                ws.column_dimensions[col_letter].width = col_widths[col_idx - 1]
        ws.row_dimensions[1].height = 28

    # 2. Counterparty Sheet
    ws_cp = wb.create_sheet(title="Counterparty")
    cp_headers = ["Legal Name", "Jurisdiction", "Registration Number", "LEI / Tax ID", "Registered Address", "Primary Activity", "Screening Date", "Preparer Name"]
    style_headers(ws_cp, cp_headers, [35, 18, 25, 20, 35, 25, 18, 22])
    ws_cp.append([
        "Alpha Ground Services Private Limited",
        "India",
        "U63090MH2020PTC123456",
        "TAX-IN-12345678",
        "Chhatrapati Shivaji Maharaj International Airport, Mumbai 400099",
        "Aviation Ground Handling & Cargo Logistics",
        "2026-10-28",
        "Compliance Analyst"
    ])

    # 3. Parties Sheet
    ws_parties = wb.create_sheet(title="Parties")
    parties_headers = ["Party ID", "Legal Name", "Entity Type", "Country / Jurisdiction", "Registration / ID No", "Date of Birth / Incorporation", "Address", "Is Listed / Sanctioned (Self-Declared)", "Notes"]
    style_headers(ws_parties, parties_headers, [12, 32, 18, 22, 22, 22, 35, 25, 30])

    dv_entity_type = DataValidation(type="list", formula1='"Company,Natural Person,Trust,Partnership,Nominee,State-Owned,Other"', allow_blank=True)
    ws_parties.add_data_validation(dv_entity_type)
    dv_entity_type.add("C2:C500")

    dv_sanctioned = DataValidation(type="list", formula1='"No,Yes,Uncertain"', allow_blank=True)
    ws_parties.add_data_validation(dv_sanctioned)
    dv_sanctioned.add("H2:H500")

    ws_parties.append(["P1", "Alpha Ground Services Private Limited", "Company", "India", "U63090MH2020PTC123456", "2020-03-15", "Mumbai, India", "No", "Target counterparty"])
    ws_parties.append(["P2", "Alpha Holdings Corp", "Company", "US", "US-DEL-123456", "2015-06-10", "Delaware, US", "No", "Intermediate holding company"])
    ws_parties.append(["P3", "Beta Holdings Ltd", "Company", "Cyprus", "HE-987654", "2015-06-10", "Nicosia, Cyprus", "No", "Intermediate holding company"])
    ws_parties.append(["P4", "John Doe", "Natural Person", "Cyprus", "CY-ID-112233", "1975-08-20", "Limassol, Cyprus", "No", "UBO with board representation"])
    ws_parties.append(["P5", "Jane Smith", "Natural Person", "France", "FR-ID-445566", "1980-04-12", "Paris, France", "No", "Minority shareholder"])

    # 4. Holdings Sheet
    ws_holdings = wb.create_sheet(title="Holdings")
    holdings_headers = ["Holding ID", "Immediate Shareholder", "Held In Entity", "Shareholding %", "Voting Rights %", "Holding Type", "On Behalf Of", "Verification Level", "Source Document Reference", "Document Date"]
    style_headers(ws_holdings, holdings_headers, [12, 30, 30, 16, 16, 18, 22, 24, 28, 16])

    dv_holding_type = DataValidation(type="list", formula1='"Direct,Indirect,Nominee,Beneficial,Trust Interest,Bearer"', allow_blank=True)
    ws_holdings.add_data_validation(dv_holding_type)
    dv_holding_type.add("F2:F500")

    dv_verif_level = DataValidation(type="list", formula1='"Registry Verified,Audited Financials,Notary Verified,Independent Legal Opinion,Self-Declared"', allow_blank=True)
    ws_holdings.add_data_validation(dv_verif_level)
    dv_verif_level.add("H2:H500")

    ws_holdings.append(["H1", "Alpha Holdings Corp", "Alpha Ground Services Private Limited", 50.0, 50.0, "Direct", "", "Registry Verified", "MCA Certificate of Incorporation", "2026-09-30"])
    ws_holdings.append(["H2", "Beta Holdings Ltd", "Alpha Ground Services Private Limited", 50.0, 50.0, "Direct", "", "Registry Verified", "MCA Certificate of Incorporation", "2026-09-30"])
    ws_holdings.append(["H3", "John Doe", "Alpha Holdings Corp", 60.0, 60.0, "Direct", "", "Registry Verified", "Delaware Secretary of State Extract", "2026-06-15"])
    ws_holdings.append(["H4", "Jane Smith", "Alpha Holdings Corp", 40.0, 40.0, "Direct", "", "Registry Verified", "Delaware Secretary of State Extract", "2026-06-15"])

    # 5. Control Sheet
    ws_control = wb.create_sheet(title="Control")
    control_headers = ["Control ID", "Controlling Party", "Controlled Entity", "Control Type", "Board Seats Held", "Total Board Seats", "Description / Governance Powers"]
    style_headers(ws_control, control_headers, [12, 30, 30, 24, 16, 16, 40])

    dv_ctrl_type = DataValidation(type="list", formula1='"Majority Board Appointment,Board Representation,Veto Rights,Dominant Influence,Shareholder Agreement,Trustee Power,Power of Attorney"', allow_blank=True)
    ws_control.add_data_validation(dv_ctrl_type)
    dv_ctrl_type.add("D2:D500")

    ws_control.append(["C1", "Beta Holdings Ltd", "Alpha Ground Services Private Limited", "Board Representation", 2, 4, "Appoints 2 of 4 directors under Articles of Association clause 14"])
    ws_control.append(["C2", "Rajesh Sharma", "Alpha Ground Services Private Limited", "Board Representation", 2, 4, "Managing Director and appoints 2 of 4 directors"])

    # 6. Key_Persons Sheet
    ws_kp = wb.create_sheet(title="Key_Persons")
    kp_headers = ["Person ID", "Full Legal Name", "Entity / Position Held In", "Role", "Appointment Date", "Nationality", "ID / Passport No", "Date of Birth", "KYC Complete"]
    style_headers(ws_kp, kp_headers, [12, 30, 30, 24, 18, 18, 20, 16, 14])

    dv_kp_role = DataValidation(type="list", formula1='"Director,Senior Managing Official,Trustee,Settlor,Protector,Beneficiary,Power of Attorney"', allow_blank=True)
    ws_kp.add_data_validation(dv_kp_role)
    dv_kp_role.add("D2:D500")

    dv_kyc_comp = DataValidation(type="list", formula1='"Yes,No"', allow_blank=True)
    ws_kp.add_data_validation(dv_kyc_comp)
    dv_kyc_comp.add("I2:I500")

    ws_kp.append(["K1", "Rajesh Sharma", "Alpha Ground Services Private Limited", "Director", "2020-03-15", "India", "ABCPS1234F", "1975-08-20", "Yes"])
    ws_kp.append(["K2", "Sunita Sharma", "Alpha Ground Services Private Limited", "Director", "2021-01-10", "India", "XYZPS9876K", "1978-02-14", "Yes"])
    ws_kp.append(["K3", "Vikram Malhotra", "Alpha Ground Services Private Limited", "Senior Managing Official", "2022-05-01", "India", "MNOPS5544L", "1980-11-30", "Yes"])

    # 7. Documents Sheet
    ws_docs = wb.create_sheet(title="Documents")
    docs_headers = ["Document ID", "Document Type", "Issuing Authority / Source", "Issue Date", "Verification Status", "File Reference / Notes"]
    style_headers(ws_docs, docs_headers, [14, 28, 30, 16, 20, 35])

    dv_doc_type = DataValidation(type="list", formula1='"Certificate of Incorporation,Register of Members,Share Certificate,Trust Deed,Financial Statements,Regulatory Filing,Passport / ID,Other"', allow_blank=True)
    ws_docs.add_data_validation(dv_doc_type)
    dv_doc_type.add("B2:B500")

    dv_doc_status = DataValidation(type="list", formula1='"Verified,Pending,Expired,Self-Declared"', allow_blank=True)
    ws_docs.add_data_validation(dv_doc_status)
    dv_doc_status.add("E2:E500")

    ws_docs.append(["D1", "Certificate of Incorporation", "Ministry of Corporate Affairs, India", "2020-03-15", "Verified", "CIN U63090MH2020PTC123456 verified on MCA portal"])
    ws_docs.append(["D2", "Register of Members", "Statutory Company Records", "2026-09-30", "Verified", "Certified extract of Register of Members under Section 88"])
    ws_docs.append(["D3", "Regulatory Filing", "Cyprus Department of Registrar of Companies", "2026-06-15", "Verified", "HE-987654 annual return verified"])

    TEMPLATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(TEMPLATE_PATH))
    print(f"Generated 7-sheet template: {TEMPLATE_PATH} with sheets {wb.sheetnames}")


if __name__ == "__main__":
    create_template()
