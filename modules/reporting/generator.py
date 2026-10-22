import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone
import getpass
import platform

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from modules.common.paths import get_app_data_dir

def _get_base_reports_dir() -> Path:
    if getattr(sys, "frozen", False):
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app:
            return Path(local_app) / "NaughtyOrNot" / "reports"
    try:
        return get_app_data_dir() / "reports"
    except Exception:
        return Path("reports")

REPORTS_DIR = _get_base_reports_dir()
_get_reports_dir = _get_base_reports_dir
NOTICE_TEXT = (
    "COMPLIANCE NOTICE: Naughty or not (Sanction checK) performs name-matching and open-source intelligence aggregation only. "
    "It does not provide legal advice, official sanctions determinations, or comprehensive ownership/control analysis (e.g. EU/OFAC 50% rules). "
    "Verify all findings against official publications."
)

def _safe_filename(s: str) -> str:
    return re.sub(r"[^\w\-]", "_", s)


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
    all_candidates: Optional[List[Dict[str, Any]]] = None,
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
        all_candidates=all_candidates,
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
        all_candidates=all_candidates,
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
    all_candidates: Optional[List[Dict[str, Any]]] = None,
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
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0D47A1"),
        spaceAfter=6,
    )
    notice_style = ParagraphStyle(
        'Notice',
        parent=styles['Normal'],
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#B71C1C"),
    )
    meta_style = ParagraphStyle(
        'Meta',
        parent=styles['Normal'],
        fontSize=8,
        leading=11,
    )
    banner_style = ParagraphStyle(
        'Banner',
        parent=styles['Normal'],
        fontSize=11,
        leading=14,
        textColor=colors.white,
        alignment=1, # Center
    )

    story = []

    # Title
    story.append(Paragraph("<b>Naughty or not — Sanction checK Screening Report</b>", title_style))
    story.append(Spacer(1, 4))

    # Compliance Notice
    story.append(Paragraph(NOTICE_TEXT, notice_style))
    story.append(Spacer(1, 10))

    # Resolve candidates to display
    hits_to_show = all_candidates if (all_candidates is not None and len(all_candidates) > 0) else sanctions_hits
    total_candidates_count = len(hits_to_show)

    # Meta Table
    meta_data = [
        [Paragraph(f"<b>Search Type:</b> {search_type}", meta_style), Paragraph(f"<b>Timestamp:</b> {timestamp_str}", meta_style)],
        [Paragraph(f"<b>User:</b> {user} ({machine})", meta_style), Paragraph(f"<b>OpenSanctions Used:</b> {'Yes' if opensanctions_used else 'No'}", meta_style)],
        [Paragraph(f"<b>Inputs:</b> {inputs}", meta_style), Paragraph(f"<b>Total Candidates:</b> {total_candidates_count}", meta_style)],
        [Paragraph(f"<b>Thresholds:</b> {threshold}", meta_style), Paragraph("", meta_style)],
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
    story.append(Paragraph("<b>Section A — Sanctions Findings & Candidates</b>", styles["Heading3"]))
    story.append(Paragraph("<i>Candidate matches below threshold are shown for information only. They are not matches.</i>", meta_style))
    story.append(Spacer(1, 4))
    if hits_to_show:
        # Group by tier: 🔴 first, then 🟠, then ℹ️
        tier_weights = {"POTENTIAL_MATCH": 0, "POSSIBLE_MATCH_REVIEW": 1, "BELOW_THRESHOLD": 2}
        sorted_hits = sorted(hits_to_show, key=lambda h: (tier_weights.get(h.get("tier"), 9), -float(h.get("score") or 0.0)))

        sanc_data = [["Source", "Tier", "Listed / Matched Name", "ID", "Score", "Reason"]]
        for h in sorted_hits:
            m_name = h.get("matched_name", "—")
            p_name = h.get("primary_name", "—")
            exp = f" [via {h.get('expanded_from')}]" if h.get("expanded_from") else ""
            display_name = f"{p_name}\n(Matched: {m_name}{exp})"
            sanc_data.append([
                h.get("source_list") or h.get("source", "—"),
                h.get("tier", "—"),
                display_name,
                h.get("source_id", "—"),
                f"{float(h.get('score') or 0.0):.4f}",
                h.get("reason") or h.get("reason_code", "—"),
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
        story.append(Paragraph("<i>No sanctions candidates found on any active list.</i>", meta_style))
    story.append(Spacer(1, 10))

    # Section B: Aviation
    if aviation_hits:
        story.append(Paragraph("<b>Section B — Aviation Safety & Export Controls</b>", styles["Heading3"]))
        av_data = [["Source / Scope", "Type", "Finding Details", "Official Note"]]
        for a in aviation_hits:
            av_data.append([
                a.get("source", "—"),
                a.get("finding", "—"),
                a.get("detail", "—"),
                a.get("note", "—"),
            ])
        t_av = Table(av_data, colWidths=[100, 110, 210, 120])
        t_av.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#ECEFF1")),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 7),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CFD8DC")),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ]))
        story.append(t_av)
        story.append(Spacer(1, 10))

    # Section C: Country Risk (FATF)
    if country_risk_hits:
        story.append(Paragraph("<b>Section C — Country Risk (FATF Jurisdictions)</b>", styles["Heading3"]))
        cr_data = [["Country", "List Type", "Official Summary", "Advisory"]]
        for c in country_risk_hits:
            cr_data.append([
                c.get("country", "—"),
                c.get("list_type", "—"),
                c.get("summary", "—"),
                c.get("advisory", "—"),
            ])
        t_cr = Table(cr_data, colWidths=[90, 80, 240, 130])
        t_cr.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#ECEFF1")),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 7),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CFD8DC")),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ]))
        story.append(t_cr)
        story.append(Spacer(1, 10))

    # Section D: Manual Official Checks
    if manual_checks:
        story.append(Paragraph("<b>Section D — Manual Official Checks Performed</b>", styles["Heading3"]))
        man_data = [["Timestamp", "Source / Portal", "Result", "Notes & Comments", "Official Verify Link"]]
        for mc in manual_checks:
            man_data.append([
                mc.get("timestamp", "—"),
                mc.get("source_name", mc.get("source", "—")),
                mc.get("result", "—"),
                mc.get("comment", "—"),
                mc.get("verify_url", "—"),
            ])
        t_man = Table(man_data, colWidths=[90, 110, 80, 130, 130])
        t_man.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#ECEFF1")),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 7),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CFD8DC")),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ]))
        story.append(t_man)
        story.append(Spacer(1, 10))

    # Footer note
    story.append(Spacer(1, 15))
    story.append(Paragraph("<i>End of Screening Report. Generated by Naughty or not (Sanction checK).</i>", meta_style))

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
    all_candidates: Optional[List[Dict[str, Any]]] = None,
) -> None:
    wb = openpyxl.Workbook()

    # Sheet 1: Summary & Meta
    ws_meta = wb.active
    ws_meta.title = "Screening Summary"

    ws_meta["A1"] = "Naughty or not — Sanction checK Screening Report"
    ws_meta["A1"].font = Font(size=14, bold=True, color="0D47A1")

    ws_meta["A2"] = NOTICE_TEXT
    ws_meta["A2"].font = Font(size=9, color="B71C1C", italic=True)

    hits_to_show = all_candidates if (all_candidates is not None and len(all_candidates) > 0) else sanctions_hits

    rows_meta = [
        ("Search Type", search_type),
        ("Timestamp", timestamp_str),
        ("Windows User", user),
        ("Machine", machine),
        ("OpenSanctions Used", "Yes" if opensanctions_used else "No"),
        ("Thresholds", threshold),
        ("Total Candidates", len(hits_to_show)),
        ("Inputs", str(inputs)),
        ("Overall Finding", overall_banner),
        ("Candidate Note", "Candidate matches below threshold are shown for information only. They are not matches."),
    ]
    for i, (k, v) in enumerate(rows_meta, start=4):
        ws_meta[f"A{i}"] = k
        ws_meta[f"A{i}"].font = Font(bold=True)
        ws_meta[f"B{i}"] = str(v)

    # Sheet 2: Sources Checked
    ws_src = wb.create_sheet(title="Sources Checked")
    headers_src = ["Source ID", "Authority", "Publication Date", "Status", "Result"]
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

    # Sheet 3: Sanctions Findings & Candidates
    ws_sanc = wb.create_sheet(title="Candidates & Findings")
    ws_sanc.append(["Candidate matches below threshold are shown for information only. They are not matches."])
    ws_sanc["A1"].font = Font(size=9, italic=True, color="555555")
    headers_sanc = ["Source", "Tier", "Primary Name", "Matched Name", "Expanded From", "Record ID", "Score", "Reason", "Program"]
    ws_sanc.append(headers_sanc)
    for cell in ws_sanc[2]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="ECEFF1", end_color="ECEFF1", fill_type="solid")

    tier_weights = {"POTENTIAL_MATCH": 0, "POSSIBLE_MATCH_REVIEW": 1, "BELOW_THRESHOLD": 2}
    sorted_hits = sorted(hits_to_show, key=lambda h: (tier_weights.get(h.get("tier"), 9), -float(h.get("score") or 0.0)))
    for h in sorted_hits:
        ws_sanc.append([
            h.get("source_list") or h.get("source", "—"),
            h.get("tier", "—"),
            h.get("primary_name", "—"),
            h.get("matched_name", "—"),
            h.get("expanded_from") or "—",
            h.get("source_id", "—"),
            float(h.get("score") or 0.0),
            h.get("reason") or h.get("reason_code", "—"),
            h.get("program", "—"),
        ])

    # Sheet 4: Aviation Safety & Export Controls
    if aviation_hits:
        ws_av = wb.create_sheet(title="Aviation Findings")
        headers_av = ["Source / Scope", "Type", "Finding Details", "Official Note"]
        ws_av.append(headers_av)
        for cell in ws_av[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="ECEFF1", end_color="ECEFF1", fill_type="solid")
        for a in aviation_hits:
            ws_av.append([
                a.get("source", "—"),
                a.get("finding", "—"),
                a.get("detail", "—"),
                a.get("note", "—"),
            ])

    # Sheet 5: Country Risk (FATF)
    if country_risk_hits:
        ws_cr = wb.create_sheet(title="Country Risk FATF")
        headers_cr = ["Country", "List Type", "Official Summary", "Advisory"]
        ws_cr.append(headers_cr)
        for cell in ws_cr[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="ECEFF1", end_color="ECEFF1", fill_type="solid")
        for c in country_risk_hits:
            ws_cr.append([
                c.get("country", "—"),
                c.get("list_type", "—"),
                c.get("summary", "—"),
                c.get("advisory", "—"),
            ])

    # Sheet 6: Manual Official Checks
    if manual_checks:
        ws_man = wb.create_sheet(title="Manual Official Checks")
        headers_man = ["Timestamp", "Source / Portal", "Result", "Notes & Comments", "Official Verify Link"]
        ws_man.append(headers_man)
        for cell in ws_man[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="ECEFF1", end_color="ECEFF1", fill_type="solid")
        for mc in manual_checks:
            ws_man.append([
                mc.get("timestamp", "—"),
                mc.get("source_name", mc.get("source", "—")),
                mc.get("result", "—"),
                mc.get("comment", "—"),
                mc.get("verify_url", "—"),
            ])

    # Column autofit on all sheets
    for ws in wb.worksheets:
        for col in ws.columns:
            max_len = max([len(str(cell.value or '')) for cell in col], default=0)
            col_letter = openpyxl.utils.get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 2, 12)

    wb.save(str(excel_path))


def generate_raw_reports(
    query: str,
    results: List[Dict[str, Any]],
    options: Dict[str, Any],
) -> Tuple[Path, Path]:
    """Generate reports specifically for Raw Text Index Searches."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_q = _safe_filename(query)[:30]
    base_name = f"RawSearch_Report_{safe_q}_{ts}"
    pdf_path = REPORTS_DIR / f"{base_name}.pdf"
    excel_path = REPORTS_DIR / f"{base_name}.xlsx"

    # PDF
    doc = SimpleDocTemplate(str(pdf_path), pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("<b>Naughty or not — Raw Search Audit Report</b>", styles['Heading1']),
        Spacer(1, 4),
        Paragraph(NOTICE_TEXT, ParagraphStyle('N', parent=styles['Normal'], fontSize=7, textColor=colors.HexColor("#B71C1C"))),
        Spacer(1, 10),
        Paragraph(f"<b>Query:</b> {query} | <b>Total Matches:</b> {len(results)} | <b>Options:</b> {options}", styles['Normal']),
        Spacer(1, 10),
    ]
    t_data = [["Source", "Source ID", "Field", "Matched Term", "Snippet / Details"]]
    for r in results[:100]:
        t_data.append([
            r.get("source_id", "—"),
            r.get("entity_id", "—"),
            r.get("field", "—"),
            r.get("term", "—"),
            Paragraph(r.get("snippet", "—")[:200], styles['Normal']),
        ])
    t = Table(t_data, colWidths=[80, 80, 70, 90, 220])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#ECEFF1")),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CFD8DC")),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(t)
    doc.build(story)

    # Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Raw Search Matches"
    ws.append(["Source", "Source ID", "Field", "Matched Term", "Snippet / Details"])
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="ECEFF1", end_color="ECEFF1", fill_type="solid")
    for r in results:
        ws.append([
            r.get("source_id", "—"),
            r.get("entity_id", "—"),
            r.get("field", "—"),
            r.get("term", "—"),
            r.get("snippet", "—"),
        ])
    wb.save(str(excel_path))
    return pdf_path, excel_path
