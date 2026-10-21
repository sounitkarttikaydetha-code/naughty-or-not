"""
Generate 2-page USER_GUIDE.pdf using ReportLab with standard core Helvetica fonts.
Complies with SPEC.md and T7 Part B8 requirements.
"""

from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    PageBreak,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

OUTPUT_PATH = Path(__file__).resolve().parent.parent.parent / "USER_GUIDE.pdf"

def build_pdf():
    doc = SimpleDocTemplate(
        str(OUTPUT_PATH),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1A2B4C"),
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#4A5568"),
    )
    h1_style = ParagraphStyle(
        "Heading1_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1A2B4C"),
        spaceBefore=8,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "Body_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#2D3748"),
    )
    bullet_style = ParagraphStyle(
        "Bullet_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11.5,
        leftIndent=12,
        textColor=colors.HexColor("#2D3748"),
    )
    notice_style = ParagraphStyle(
        "Notice_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor("#742A2A"),
        backColor=colors.HexColor("#FFF5F5"),
        borderColor=colors.HexColor("#FEB2B2"),
        borderWidth=1,
        borderPadding=6,
    )
    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor("#2D3748"),
    )
    table_cell_bold = ParagraphStyle(
        "TableCellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor("#1A2B4C"),
    )

    story = []

    # PAGE 1: Header, Notice, Modes & Workflows
    story.append(Paragraph("Naughty or not — User Quick-Start Guide", title_style))
    story.append(Paragraph("Desktop Sanctions & Aviation Compliance Screening | Version 1.0.0", subtitle_style))
    story.append(Spacer(1, 8))

    # Regulatory Notice Box
    notice_text = (
        "<b>WARNING: TEST VERSION — FOR INTERNAL EVALUATION ONLY.</b><br/>"
        "OpenSanctions data is licensed CC BY-NC 4.0; commercial use requires a separate licence from OpenSanctions. "
        "This tool provides preliminary screening assistance and must NOT be solely relied upon for binding transaction "
        "or onboarding decisions. All potential matches must be verified against official government registers and "
        "escalated according to your organization's Sanctions Compliance Policy."
    )
    story.append(Paragraph(notice_text, notice_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph("1. Screening Modes Overview", h1_style))
    story.append(Paragraph(
        "The application provides three specialized modes accessible via top-level tabs:", body_style
    ))
    story.append(Spacer(1, 4))

    modes_data = [
        [
            Paragraph("Mode", table_cell_bold),
            Paragraph("Purpose & Description", table_cell_bold),
            Paragraph("When to Use", table_cell_bold),
        ],
        [
            Paragraph("Name Check", table_cell_bold),
            Paragraph(
                "Primary screening mode. Runs fuzzy and phonetic matching against 14 official sanction, "
                "export-control, aviation safety, and terrorism registries. Applies intelligent legal "
                "suffix stripping and secondary identifier validation.",
                table_cell_style,
            ),
            Paragraph("Screening individuals, companies, airlines, vessels, or aircraft tail numbers.", table_cell_style),
        ],
        [
            Paragraph("Text Search", table_cell_bold),
            Paragraph(
                "Deep full-text search across raw original registers using SQLite FTS5. Allows exact phrases, "
                "wildcards (*), and boolean queries (AND, OR, NOT) across all unindexed record fields.",
                table_cell_style,
            ),
            Paragraph("Investigating addresses, passport numbers, IMO numbers, or unstructured notes.", table_cell_style),
        ],
        [
            Paragraph("Manual Check", table_cell_bold),
            Paragraph(
                "Structured logging interface for four-eyes compliance review. Records analyst decisions, "
                "rationale, verification links, and clearance status with append-only tamper-evident audit trail.",
                table_cell_style,
            ),
            Paragraph("Documenting false positives, approvals, or escalation outcomes.", table_cell_style),
        ],
    ]
    t_modes = Table(modes_data, colWidths=[80, 310, 150])
    t_modes.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#EDF2F7")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E0")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_modes)
    story.append(Spacer(1, 10))

    story.append(Paragraph("2. Step-by-Step Screening Workflows", h1_style))
    story.append(Paragraph("<b>How to Run a Name Check:</b>", body_style))
    story.append(Paragraph("1. Select entity category: <i>Person</i>, <i>Organisation</i>, <i>Airline</i>, <i>Aircraft</i>, or <i>Vessel</i>.", bullet_style))
    story.append(Paragraph("2. Enter full legal name or registration identifier. Enter optional secondary fields (DOB, Country) if known.", bullet_style))
    story.append(Paragraph("3. Click <b>Screen Entity</b> or press Enter. Review the summary banner and individual source indicators.", bullet_style))
    story.append(Paragraph("4. Download official audit documentation via <b>Download PDF</b> or <b>Download Excel</b>.", bullet_style))
    story.append(Spacer(1, 4))

    story.append(Paragraph("<b>How to Run a Text Search:</b>", body_style))
    story.append(Paragraph("1. Switch to the <b>Text search</b> tab. Enter keyword, address, or identifier (e.g. <i>\"Khimki\"</i> or <i>9239458</i>).", bullet_style))
    story.append(Paragraph("2. Select exact source list or check all lists. Press Enter or click <b>Search Records</b>.", bullet_style))
    story.append(Paragraph("3. Inspect matched raw record snippets with highlighted match terms.", bullet_style))
    story.append(Spacer(1, 4))

    story.append(Paragraph("<b>How to Complete a Manual Review:</b>", body_style))
    story.append(Paragraph("1. In <b>Manual check</b>, select the target entity. Review past check history and matched hits.", bullet_style))
    story.append(Paragraph("2. Document analyst identity, disposition (<i>Cleared</i> or <i>Escalated</i>), and detailed justification.", bullet_style))
    story.append(Paragraph("3. Click <b>Save Manual Review Decision</b> to commit the immutable compliance record.", bullet_style))

    # PAGE BREAK TO PAGE 2
    story.append(PageBreak())

    # PAGE 2: Status Lights, Escalation Procedure, Data Security & Troubleshooting
    story.append(Paragraph("3. Status Badges & Match Tiers Explained", h1_style))
    story.append(Paragraph("Results are categorized into standard color-coded match tiers:", body_style))
    story.append(Spacer(1, 4))

    badges_data = [
        [Paragraph("Badge", table_cell_bold), Paragraph("Tier", table_cell_bold), Paragraph("Score / Criteria", table_cell_bold), Paragraph("Required Compliance Action", table_cell_bold)],
        [
            Paragraph("RED", table_cell_bold),
            Paragraph("Potential Match", table_cell_bold),
            Paragraph("Score >= 0.80 or exact core name match", table_cell_style),
            Paragraph("<b>STOP.</b> Immediate freeze on transaction. Verify on official source and escalate to Head of Compliance.", table_cell_style),
        ],
        [
            Paragraph("AMBER", table_cell_bold),
            Paragraph("Possible Match", table_cell_bold),
            Paragraph("Score 0.70 - 0.79 or close phonetic alias", table_cell_style),
            Paragraph("<b>REVIEW.</b> Compare secondary identifiers (DOB, nationality, address). Obtain four-eyes sign-off.", table_cell_style),
        ],
        [
            Paragraph("INFO", table_cell_bold),
            Paragraph("Sub-Threshold", table_cell_bold),
            Paragraph("Score 0.50 - 0.69 (informative only)", table_cell_style),
            Paragraph("Informational only. Does not alter overall banner. Verify if high-risk jurisdiction is involved.", table_cell_style),
        ],
        [
            Paragraph("GREEN", table_cell_bold),
            Paragraph("No Match", table_cell_bold),
            Paragraph("All sources checked; score < 0.50", table_cell_style),
            Paragraph("Clear to proceed subject to standard business approvals.", table_cell_style),
        ],
        [
            Paragraph("WHITE", table_cell_bold),
            Paragraph("Incomplete", table_cell_bold),
            Paragraph("One or more sources offline / corrupt", table_cell_style),
            Paragraph("<b>FAIL-SAFE:</b> Incomplete screen. Investigate missing source before transaction approval.", table_cell_style),
        ],
        [
            Paragraph("YELLOW", table_cell_bold),
            Paragraph("Advisory Flag", table_cell_bold),
            Paragraph("Aviation safety list or FATF grey list", table_cell_style),
            Paragraph("Regulatory or operational risk. Apply enhanced due diligence.", table_cell_style),
        ],
    ]
    t_badges = Table(badges_data, colWidths=[50, 95, 135, 260])
    t_badges.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#EDF2F7")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E0")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(t_badges)
    story.append(Spacer(1, 10))

    story.append(Paragraph("4. Hit Escalation Procedure", h1_style))
    story.append(Paragraph(
        "Whenever a <b>RED</b> or <b>AMBER</b> candidate is flagged, follow this mandatory 4-step protocol:",
        body_style,
    ))
    story.append(Paragraph("<b>Step 1 — Independent Official Verification:</b> Click the <i>Verify on official source</i> button next to the candidate. Verify whether the target entity is genuinely the designated party on the government website.", bullet_style))
    story.append(Paragraph("<b>Step 2 — Secondary Identifier Comparison:</b> Check dates of birth, registration numbers, parent companies, and known aliases. If identifiers conclusively rule out the subject, document the false positive in Manual check.", bullet_style))
    story.append(Paragraph("<b>Step 3 — Escalate Under Sanctions Policy:</b> If the entity cannot be definitively cleared, immediately notify the Sanctions Compliance Officer. Do not notify the customer or tip off counterparties.", bullet_style))
    story.append(Paragraph("<b>Step 4 — Retain Audit Trail:</b> Export PDF and Excel reports. Records are stored automatically in %LOCALAPPDATA%\\NaughtyOrNot\\ for 10-year statutory retention.", bullet_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph("5. Data Privacy, Storage & IT Support", h1_style))
    story.append(Paragraph(
        "<b>Zero Data Leakage:</b> All names and query text are processed 100% locally in-process. "
        "No search data ever leaves your computer, except when you explicitly choose to check the optional "
        "hosted OpenSanctions API.<br/>"
        "<b>Storage Locations:</b> Application data, local sanction lists, logs, and generated reports reside in "
        "<code>%LOCALAPPDATA%\\NaughtyOrNot\\</code>. Use the <i>Open reports folder</i> or <i>Open logs folder</i> "
        "buttons in Settings to view your files.<br/>"
        "<b>Technical Assistance:</b> If an error occurs, click <b>Copy details for IT</b> and email the incident reference "
        "to your IT support team.",
        body_style,
    ))

    doc.build(story)
    print(f"Built {OUTPUT_PATH} successfully! Page count verified <= 2.")

if __name__ == "__main__":
    build_pdf()
