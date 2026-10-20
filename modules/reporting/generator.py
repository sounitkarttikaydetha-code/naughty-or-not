"""
Report Generator for Sanction checK (T5).
Generates official PDF and Excel screening reports stored in reports/
per SPEC.md Sections 4.3 and prompt requirements.
"""

import getpass
import os
import platform
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "reports"
NOTICE_TEXT = (
    "TEST VERSION — for internal evaluation only. OpenSanctions data is licensed CC BY-NC 4.0; "
    "commercial use requires a licence from OpenSanctions. Not to be relied upon for transaction decisions."
)
DISCLAIMER_TEXT = (
    "Screening aid only. A result here is not a legal determination. "
    "Potential matches must be verified against the official source and escalated under the Sanctions Compliance Policy. "
    "Ownership/control (e.g. the US 50% rule) is not assessed. Antigravity and the developers accept no liability for reliance on this tool."
)


def _safe_filename(text: str) -> str:
    return re.sub(r"[^\w\-_]", "_", text).strip("_")


def generate_reports(
    search_type: str,
    inputs: Dict[str, Any],
    overall_banner: str,
    source_statuses: List[Dict[str, Any]],
    sanctions_hits: List[Dict[str, Any]],
    aviation_hits: List[Dict[str, Any]],
    country_risk_hits: List[Dict[str, Any]],
    opensanctions_used: bool = False,
    threshold: str = "Potential Match >= 0.80 | Possible Match >= 0.70 | Sub-threshold core >= 0.60",
    manual_checks: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[Path, Path]:
    """
    Generate PDF and Excel reports for a screening search.
    Returns (pdf_path, excel_path).
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    entity_key = (
        inputs.get("name")
        or inputs.get("tail")
        or inputs.get("tail_number")
        or inputs.get("registration")
        or inputs.get("query")
        or "Search"
    )
    safe_name = _safe_filename(entity_key)[:30]
    base_name = f"Screening_Report_{search_type}_{safe_name}_{ts}"

    pdf_path = REPORTS_DIR / f"{base_name}.pdf"
    excel_path = REPORTS_DIR / f"{base_name}.xlsx"

    user = getpass.getuser()
    machine = platform.node()
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # 1. Build PDF Report
    _build_pdf(
        pdf_path=pdf_path,
        search_type=search_type,
        inputs=inputs,
        overall_banner=overall_banner,
        source_statuses=source_statuses,
        sanctions_hits=sanctions_hits,
        aviation_hits=aviation_hits,
        country_risk_hits=country_risk_hits,
        opensanctions_used=opensanctions_used,
        threshold=threshold,
        user=user,
        machine=machine,
        timestamp_str=now_str,
        manual_checks=manual_checks,
    )

    # 2. Build Excel Report
    _build_excel(
        excel_path=excel_path,
        search_type=search_type,
        inputs=inputs,
        overall_banner=overall_banner,
        source_statuses=source_statuses,
        sanctions_hits=sanctions_hits,
        aviation_hits=aviation_hits,
        country_risk_hits=country_risk_hits,
        opensanctions_used=opensanctions_used,
        threshold=threshold,
        user=user,
        machine=machine,
        timestamp_str=now_str,
        manual_checks=manual_checks,
    )

    return pdf_path, excel_path


def _build_pdf(
    pdf_path: Path,
    search_type: str,
    inputs: Dict[str, Any],
    overall_banner: str,
    source_statuses: List[Dict[str, Any]],
    sanctions_hits: List[Dict[str, Any]],
    aviation_hits: List[Dict[str, Any]],
    country_risk_hits: List[Dict[str, Any]],
    opensanctions_used: bool,
    threshold: str,
    user: str,
    machine: str,
    timestamp_str: str,
    manual_checks: Optional[List[Dict[str, Any]]] = None,
) -> None:
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0D47A1"),
    )
    notice_style = ParagraphStyle(
        "Notice",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#B71C1C"),
        backColor=colors.HexColor("#FFEBEE"),
        borderPadding=6,
    )
    meta_style = ParagraphStyle(
        "Meta",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#37474F"),
    )
    banner_style = ParagraphStyle(
        "Banner",
        parent=styles["Heading2"],
        fontSize=14,
        leading=16,
        textColor=colors.whitesmoke,
        alignment=1,
    )
    disclaimer_style = ParagraphStyle(
        "Disclaimer",
        parent=styles["Italic"],
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#546E7A"),
    )

    story = []

    # Title & Notice
    story.append(Paragraph("Naughty or not — Sanction checK Screening Report", title_style))
    story.append(Spacer(1, 8))
    story.append(Paragraph(NOTICE_TEXT, notice_style))
    story.append(Spacer(1, 10))

    # Meta Table
    meta_data = [
        [Paragraph(f"<b>Search Type:</b> {search_type}", meta_style), Paragraph(f"<b>Timestamp:</b> {timestamp_str}", meta_style)],
        [Paragraph(f"<b>User:</b> {user} ({machine})", meta_style), Paragraph(f"<b>OpenSanctions Used:</b> {'Yes' if opensanctions_used else 'No'}", meta_style)],
        [Paragraph(f"<b>Inputs:</b> {inputs}", meta_style), Paragraph(f"<b>Thresholds:</b> {threshold}", meta_style)],
    ]
    t_meta = Table(meta_data, colWidths=[270, 270])
    t_meta.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 10))

    # Banner
    banner_bg = colors.HexColor("#D32F2F") if "POTENTIAL" in overall_banner or "🔴" in overall_banner else (
        colors.HexColor("#F57C00") if "POSSIBLE" in overall_banner or "⚠️" in overall_banner or "SAFETY" in overall_banner else (
            colors.HexColor("#388E3C") if "NO MATCH" in overall_banner or "✅" in overall_banner else colors.HexColor("#616161")
        )
    )
    t_banner = Table([[Paragraph(f"<b>OVERALL FINDING: {overall_banner}</b>", banner_style)]], colWidths=[540])
    t_banner.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), banner_bg),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_banner)
    story.append(Spacer(1, 12))

    # Sources Checked Table
    story.append(Paragraph("<b>Sources Checked & Status</b>", styles["Heading3"]))
    src_table_data = [["Source ID", "Authority", "Publication Date", "Status", "Result"]]
    for s in source_statuses:
        src_table_data.append([
            s.get("id", "—"),
            s.get("authority", "—"),
            s.get("date", "—"),
            s.get("status", "OK"),
            s.get("tier", "NO_MATCH"),
        ])
    t_src = Table(src_table_data, colWidths=[100, 160, 100, 70, 110])
    t_src.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#ECEFF1")),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CFD8DC")),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(t_src)
    story.append(Spacer(1, 12))

    # Section A: Sanctions
    story.append(Paragraph("<b>Section A — Sanctions Findings</b>", styles["Heading3"]))
    if sanctions_hits:
        sanc_data = [["Source", "Tier", "Listed / Matched Name", "ID", "Score", "Reason"]]
        for h in sanctions_hits:
            m_name = h.get("matched_name", "—")
            p_name = h.get("primary_name", "—")
            exp = f" [via {h.get('expanded_from')}]" if h.get("expanded_from") else ""
            display_name = f"{p_name}\n(Matched: {m_name}{exp})"
            sanc_data.append([
                h.get("source_list", "—"),
                h.get("tier", "—"),
                display_name,
                h.get("source_id", "—"),
                f"{h.get('score', 0.0):.4f}",
                h.get("reason", "—"),
            ])
        t_sanc = Table(sanc_data, colWidths=[70, 90, 200, 60, 50, 70])
        t_sanc.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#ECEFF1")),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 7),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CFD8DC")),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ]))
        story.append(t_sanc)
    else:
        story.append(Paragraph("<i>No sanctions matches found on any active list.</i>", meta_style))
    story.append(Spacer(1, 10))

    # Section B: Aviation
    if aviation_hits:
        story.append(Paragraph("<b>Section B — Aviation Safety & Export Controls</b>", styles["Heading3"]))
        av_data = [["Source / Scope", "Type", "Finding Details", "Official Note"]]
        for a in aviation_hits:
            av_data.append([
                a.get("source", "Aviation"),
                a.get("result_type", "FLAG"),
                a.get("details", "—"),
                a.get("label", "—"),
            ])
        t_av = Table(av_data, colWidths=[100, 90, 200, 150])
        t_av.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#ECEFF1")),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 7),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CFD8DC")),
        ]))
        story.append(t_av)
        story.append(Spacer(1, 10))

    # Section C: Country Risk
    if country_risk_hits:
        story.append(Paragraph("<b>Section C — FATF Country Risk</b>", styles["Heading3"]))
        cr_data = [["Country", "List Type", "Call to Action", "Finding Type"]]
        for c in country_risk_hits:
            cr_data.append([
                c.get("country", "—"),
                c.get("list_type", "—"),
                c.get("call_to_action", "—"),
                "Country risk flag — not a sanctions finding",
            ])
        t_cr = Table(cr_data, colWidths=[100, 110, 180, 150])
        t_cr.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#ECEFF1")),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 7),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CFD8DC")),
        ]))
        story.append(t_cr)
        story.append(Spacer(1, 10))

    # Section D: Manual Checks (if present)
    if manual_checks:
        story.append(Paragraph("<b>Section D — Manual Official Checks</b>", styles["Heading3"]))
        mc_data = [["Source", "Authority", "Status / Result", "User Comment"]]
        for m in manual_checks:
            mc_data.append([
                m.get("source", "—"),
                m.get("authority", "—"),
                m.get("result", "Not checked"),
                m.get("comment", "")[:60],
            ])
        t_mc = Table(mc_data, colWidths=[100, 150, 110, 180])
        t_mc.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#ECEFF1")),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 7),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CFD8DC")),
        ]))
        story.append(t_mc)
        story.append(Spacer(1, 10))

    # Disclaimer Footer
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#B0BEC5"), spaceBefore=10, spaceAfter=8))
    story.append(Paragraph(DISCLAIMER_TEXT, disclaimer_style))

    doc.build(story)


def _build_excel(
    excel_path: Path,
    search_type: str,
    inputs: Dict[str, Any],
    overall_banner: str,
    source_statuses: List[Dict[str, Any]],
    sanctions_hits: List[Dict[str, Any]],
    aviation_hits: List[Dict[str, Any]],
    country_risk_hits: List[Dict[str, Any]],
    opensanctions_used: bool,
    threshold: str,
    user: str,
    machine: str,
    timestamp_str: str,
    manual_checks: Optional[List[Dict[str, Any]]] = None,
) -> None:
    wb = openpyxl.Workbook()

    # Sheet 1: Summary & Meta
    ws_meta = wb.active
    ws_meta.title = "Screening Summary"

    ws_meta["A1"] = "Naughty or not — Sanction checK Screening Report"
    ws_meta["A1"].font = Font(size=14, bold=True, color="0D47A1")

    ws_meta["A2"] = NOTICE_TEXT
    ws_meta["A2"].font = Font(size=9, color="B71C1C", italic=True)

    rows_meta = [
        ("Search Type", search_type),
        ("Timestamp", timestamp_str),
        ("Windows User", user),
        ("Machine", machine),
        ("OpenSanctions Used", "Yes" if opensanctions_used else "No"),
        ("Thresholds", threshold),
        ("Inputs", str(inputs)),
        ("Overall Finding", overall_banner),
    ]
    for i, (k, v) in enumerate(rows_meta, start=4):
        ws_meta[f"A{i}"] = k
        ws_meta[f"A{i}"].font = Font(bold=True)
        ws_meta[f"B{i}"] = v

    # Sheet 2: Sources Status
    ws_src = wb.create_sheet(title="Sources Status")
    headers_src = ["Source ID", "Authority", "Publication Date", "Status", "Tier"]
    ws_src.append(headers_src)
    for cell in ws_src[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="ECEFF1", end_color="ECEFF1", fill_type="solid")
    for s in source_statuses:
        ws_src.append([
            s.get("id", "—"),
            s.get("authority", "—"),
            s.get("date", "—"),
            s.get("status", "OK"),
            s.get("tier", "NO_MATCH"),
        ])

    # Sheet 3: Sanctions Findings
    ws_sanc = wb.create_sheet(title="Sanctions Findings")
    headers_sanc = ["Source", "Tier", "Primary Name", "Matched Name", "Expanded From", "Record ID", "Score", "Reason", "Program"]
    ws_sanc.append(headers_sanc)
    for cell in ws_sanc[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="ECEFF1", end_color="ECEFF1", fill_type="solid")
    for h in sanctions_hits:
        ws_sanc.append([
            h.get("source_list", "—"),
            h.get("tier", "—"),
            h.get("primary_name", "—"),
            h.get("matched_name", "—"),
            h.get("expanded_from") or "—",
            h.get("source_id", "—"),
            h.get("score", 0.0),
            h.get("reason", "—"),
            h.get("program", "—"),
        ])

    # Sheet 4: Aviation & Risk
    ws_av = wb.create_sheet(title="Aviation and Country Risk")
    ws_av.append(["Category", "Source / Scope", "Type", "Details", "Label"])
    for cell in ws_av[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="ECEFF1", end_color="ECEFF1", fill_type="solid")
    for a in aviation_hits:
        ws_av.append([
            "Aviation",
            a.get("source", "Aviation"),
            a.get("result_type", "FLAG"),
            a.get("details", "—"),
            a.get("label", "—"),
        ])
    for c in country_risk_hits:
        ws_av.append([
            "Country Risk",
            c.get("country", "—"),
            c.get("list_type", "—"),
            c.get("call_to_action", "—"),
            "Country risk flag — not a sanctions finding",
        ])

    if manual_checks:
        ws_mc = wb.create_sheet(title="Manual Official Checks")
        ws_mc.append(["Source ID", "Authority", "Status / Result", "User Comment", "Official Verification Link"])
        for cell in ws_mc[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="ECEFF1", end_color="ECEFF1", fill_type="solid")
        for m in manual_checks:
            ws_mc.append([
                m.get("source", "—"),
                m.get("authority", "—"),
                m.get("result", "Not checked"),
                m.get("comment", ""),
                m.get("verify_url", "—"),
            ])

    wb.save(excel_path)


def generate_raw_reports(
    query: str,
    options: Dict[str, Any],
    results: List[Dict[str, Any]],
) -> Tuple[Path, Path]:
    """
    Generate PDF and Excel reports for a Raw text search.
    Returns (pdf_path, excel_path).
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_q = _safe_filename(query)[:30]
    base_name = f"Raw_Search_Report_{safe_q}_{ts}"

    pdf_path = REPORTS_DIR / f"{base_name}.pdf"
    excel_path = REPORTS_DIR / f"{base_name}.xlsx"

    user = getpass.getuser()
    machine = platform.node()
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # 1. Build PDF Report
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    styles = getSampleStyleSheet()
    notice_style = ParagraphStyle("NoticeStyle", parent=styles["Normal"], fontSize=8, leading=10, textColor=colors.HexColor("#757575"))
    meta_style = ParagraphStyle("MetaStyle", parent=styles["Normal"], fontSize=8, leading=11)
    text_style = ParagraphStyle("TextStyle", parent=styles["Normal"], fontSize=7, leading=9)

    story = []
    # Notice
    story.append(Paragraph(f"<b>{NOTICE_TEXT}</b>", notice_style))
    story.append(Spacer(1, 10))

    # Header
    story.append(Paragraph("<b>Sanction checK — Raw Text Search Report</b>", styles["Title"]))
    story.append(Spacer(1, 8))

    # Meta Table
    meta_data = [
        ["Query Term:", query, "Execution Time:", now_str],
        ["Match Option:", str(options.get("match_option", "Contains")), "User / Machine:", f"{user} @ {machine}"],
        ["Search Field:", str(options.get("search_field", "All fields")), "Total Results:", str(len(results))],
    ]
    t_meta = Table(meta_data, colWidths=[90, 180, 90, 180])
    t_meta.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CFD8DC")),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 12))

    # Mandatory label
    label_style = ParagraphStyle("LabelStyle", parent=styles["Normal"], fontSize=10, leading=13, fontName="Helvetica-Bold", textColor=colors.HexColor("#C2185B"), alignment=1)
    t_label = Table([[Paragraph("Raw text search — results are not scored matches. Review each record.", label_style)]], colWidths=[540])
    t_label.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FCE4EC")),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_label)
    story.append(Spacer(1, 12))

    # Flat Results Table
    if results:
        res_data = [["Source", "Record ID", "Primary Name", "Field", "Matched Extract", "List Date"]]
        for r in results[:100]:
            clean_extract = re.sub(r"<[^>]+>", "", r.get("text_extract", ""))[:80]
            res_data.append([
                r.get("source", "—"),
                r.get("record_id", "—"),
                r.get("primary_name", "—")[:30],
                r.get("matched_field", "—"),
                clean_extract,
                r.get("list_date", "—"),
            ])
        t_res = Table(res_data, colWidths=[65, 65, 110, 75, 165, 60])
        t_res.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#ECEFF1")),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 7),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CFD8DC")),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ]))
        story.append(t_res)
    else:
        story.append(Paragraph("No matches found for query.", styles["Normal"]))

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#B0BEC5"), spaceBefore=10, spaceAfter=8))
    story.append(Paragraph(DISCLAIMER_TEXT, notice_style))
    doc.build(story)

    # 2. Build Excel Report
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Raw Search Results"

    ws["A1"] = NOTICE_TEXT
    ws["A1"].font = Font(italic=True, size=9, color="757575")

    ws["A3"] = "Raw text search — results are not scored matches. Review each record."
    ws["A3"].font = Font(bold=True, size=11, color="C2185B")

    ws["A5"] = "Query:"
    ws["B5"] = query
    ws["A6"] = "Match Option:"
    ws["B6"] = options.get("match_option", "Contains")
    ws["A7"] = "Search Field:"
    ws["B7"] = options.get("search_field", "All fields")
    ws["A8"] = "Execution Time:"
    ws["B8"] = now_str
    ws["A9"] = "User / Machine:"
    ws["B9"] = f"{user} @ {machine}"

    for r_idx in range(5, 10):
        ws[f"A{r_idx}"].font = Font(bold=True)

    headers = ["Source", "Authority", "Record ID", "Primary Name", "Matched Field", "Matched Text Extract", "List Date", "Verification URL"]
    ws.append([])
    ws.append(headers)
    hdr_row = 11
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=hdr_row, column=col_idx)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="ECEFF1", end_color="ECEFF1", fill_type="solid")

    for r in results:
        clean_extract = re.sub(r"<[^>]+>", "", r.get("text_extract", ""))
        ws.append([
            r.get("source", "—"),
            r.get("authority", "—"),
            r.get("record_id", "—"),
            r.get("primary_name", "—"),
            r.get("matched_field", "—"),
            clean_extract,
            r.get("list_date", "—"),
            r.get("verify_url", "—"),
        ])

    if manual_checks:
        ws_mc = wb.create_sheet(title="Manual Official Checks")
        ws_mc.append(["Source ID", "Authority", "Status / Result", "User Comment", "Official Verification Link"])
        for cell in ws_mc[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="ECEFF1", end_color="ECEFF1", fill_type="solid")
        for m in manual_checks:
            ws_mc.append([
                m.get("source", "—"),
                m.get("authority", "—"),
                m.get("result", "Not checked"),
                m.get("comment", ""),
                m.get("verify_url", "—"),
            ])

    wb.save(excel_path)
    return pdf_path, excel_path

