from modules.common.branding import APP_NAME, MAIN_TITLE
import os
import re
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone
import getpass
import platform

import anyascii
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from modules.common.paths import get_reports_dir, get_app_data_dir
from modules.common.records_store import get_record, build_13_sections
import shutil
import tempfile


class ReportGenerationError(Exception):
    """Raised when report generation fails. Retains optional reference to Excel export."""
    def __init__(self, message: str, excel_path: Optional[Path] = None, details: str = ""):
        super().__init__(message)
        self.excel_path = excel_path
        self.details = details


class ReportSelfCheckError(ReportGenerationError):
    """Raised when PDF self-check validation fails (blank pages, missing record IDs, etc.)."""
    pass


def _ensure_safe_tempdir():
    try:
        cur_temp = tempfile.gettempdir()
        if shutil.disk_usage(cur_temp).free < 50 * 1024 * 1024:
            alt_tmp = get_app_data_dir() / ".tmp"
            alt_tmp.mkdir(parents=True, exist_ok=True)
            if shutil.disk_usage(str(alt_tmp)).free > 50 * 1024 * 1024:
                tempfile.tempdir = str(alt_tmp)
                os.environ["TEMP"] = str(alt_tmp)
                os.environ["TMP"] = str(alt_tmp)
    except Exception:
        pass

_ensure_safe_tempdir()

def _get_base_reports_dir() -> Path:
    if getattr(sys, "frozen", False):
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app:
            return Path(local_app) / "NaughtyOrNot" / "reports"
    try:
        return get_reports_dir()
    except Exception:
        return Path("reports")

def _get_reports_dir() -> Path:
    return _get_base_reports_dir()

REPORTS_DIR = _get_base_reports_dir()

NOTICE_TEXT = (
    "COMPLIANCE NOTICE: Naughty or not (Sanction checK) performs name-matching and open-source intelligence aggregation only. "
    "It does not provide legal advice, official sanctions determinations, or comprehensive ownership/control analysis (e.g. EU/OFAC 50% rules). "
    "The local audit log is append-only, not tamper-evident. Verify all findings against official publications."
)

def _safe_filename(s: str) -> str:
    return re.sub(r"[^\w\-]", "_", s)


def soft_wrap_text(text: Any) -> str:
    """Pass-through text for ReportLab Paragraph; wrapping is handled natively via wordWrap='CJK'."""
    if text is None:
        return "—"
    return str(text)


def sanitize_for_pdf(text: Any) -> str:
    """
    Sanitize text for ReportLab Helvetica rendering.
    Replaces status emojis with plain-text status tags, replaces typography dashes/quotes,
    transliterates non-Latin characters using anyascii to avoid missing-glyph boxes,
    and preserves basic HTML formatting.
    """
    if text is None:
        return "—"
    s = str(text)

    # 1. Map known status markers and emojis to plain-text tags
    emoji_map = {
        "🔴": "[RED] ",
        "🟠": "[AMBER] ",
        "ℹ️": "[INFO] ",
        "ℹ": "[INFO] ",
        "✅": "[CLEAR] ",
        "⚪": "[NOT CHECKED] ",
        "✈️": "[SAFETY] ",
        "✈": "[SAFETY] ",
        "📦": "[EXPORT CONTROL] ",
        "⚠️": "[WARNING] ",
        "⚠": "[WARNING] ",
        "🔍": "[SEARCH] ",
        "📸": "[PHOTO] ",
        "🕵️": "[AGENT] ",
        "🕵": "[AGENT] ",
        "—": "-",
        "–": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "…": "...",
        "•": "*",
        "\u200b": "", # Zero-width space causes missing glyph square in Helvetica
    }
    for k, v in emoji_map.items():
        s = s.replace(k, v)

    # 2. Transliterate non-Latin characters using anyascii
    out = []
    for ch in s:
        try:
            ch.encode("latin-1")
            out.append(ch)
        except UnicodeEncodeError:
            out.append(anyascii.anyascii(ch))
    clean = "".join(out)

    # 3. Escape XML entities where necessary without breaking simple tags
    parts = re.split(r'(</?[a-zA-Z0-9]+(?: [^>]+)?>)', clean)
    final_parts = []
    for p in parts:
        if p.startswith('<') and p.endswith('>'):
            final_parts.append(p)
        else:
            final_parts.append(p.replace("&", "&amp;"))
    return "".join(final_parts)


def format_chip_text(tier_or_status: str) -> str:
    """Format status with both symbol and word for accessibility and colour-blind support."""
    mapping = {
        "POTENTIAL_MATCH": "🔴 LIKELY",
        "POSSIBLE_MATCH_REVIEW": "🟠 POSSIBLE",
        "BELOW_THRESHOLD": "ℹ️ INFO",
        "NO_MATCH": "✅ CLEAR",
        "NOT_CHECKED": "⚪ NOT CHECKED",
        "FAILED": "⚪ NOT CHECKED",
        "NOT_RUN": "⚪ NOT RUN",
        "SAFETY": "✈️ SAFETY",
        "EXPORT_CONTROL": "📦 EXPORT CONTROL",
        "EAR_RESTRICTION": "📦 EXPORT CONTROL",
    }
    return mapping.get(str(tier_or_status), str(tier_or_status))


def _self_check_pdf(
    pdf_path: Path,
    searched_name: str,
    hits: List[Dict[str, Any]],
) -> None:
    """
    Self-check every PDF before presenting it as successful:
    1. Confirm file exists and size >= 1000 bytes.
    2. Confirm at least 1 page.
    3. Confirm extracted text contains searched name.
    4. Confirm each 🔴 and 🟠 record ID is present in extracted text.
    5. Confirm no page is blank.
    Raises ReportSelfCheckError if any check fails.
    """
    if not pdf_path.is_file() or pdf_path.stat().st_size < 1000:
        sz = pdf_path.stat().st_size if pdf_path.is_file() else 0
        raise ReportSelfCheckError(f"PDF validation failed: file missing or truncated ({sz} bytes)")

    import pypdf
    try:
        reader = pypdf.PdfReader(str(pdf_path))
    except Exception as e:
        raise ReportSelfCheckError(f"PDF validation failed: unable to parse PDF ({e})")

    if len(reader.pages) < 1:
        raise ReportSelfCheckError("PDF validation failed: 0 pages generated")

    full_text = ""
    for page_idx, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""
        if not page_text.strip():
            raise ReportSelfCheckError(f"PDF validation failed: Page {page_idx + 1} is blank with no readable content")
        full_text += page_text + "\n"

    # Normalized text comparison (alphanumeric only)
    full_norm = re.sub(r'[^a-z0-9]', '', anyascii.anyascii(full_text).lower())

    # Confirm searched name (or transliterated name)
    clean_search = re.sub(r'[^a-z0-9]', '', anyascii.anyascii(str(searched_name)).lower())
    if clean_search and len(clean_search) >= 3:
        # Check if full name or prominent token is present
        if clean_search not in full_norm:
            search_tokens = [tok for tok in clean_search.split() if len(tok) >= 3]
            if not search_tokens or not any(tok in full_norm for tok in search_tokens):
                raise ReportSelfCheckError(f"PDF validation failed: Searched name '{searched_name}' not found in report text")

    # Confirm each 🔴 and 🟠 hit record ID is present
    for h in hits:
        tier = h.get("tier", "")
        if tier in ("POTENTIAL_MATCH", "POSSIBLE_MATCH_REVIEW") or "🔴" in str(tier) or "🟠" in str(tier):
            rid_raw = str(h.get("source_id", "")).strip()
            rid_norm = re.sub(r'[^a-z0-9]', '', anyascii.anyascii(rid_raw).lower())
            if rid_norm and len(rid_norm) >= 2 and rid_norm not in full_norm:
                raise ReportSelfCheckError(f"PDF validation failed: Matching record ID '{rid_raw}' not found in report text")


def generate_reports(
    search_type: str,
    inputs: Dict[str, Any],
    overall_banner: str,
    source_statuses: List[Dict[str, Any]],
    sanctions_hits: Optional[List[Dict[str, Any]]] = None,
    aviation_hits: Optional[List[Dict[str, Any]]] = None,
    country_risk_hits: Optional[List[Dict[str, Any]]] = None,
    opensanctions_used: bool = False,
    threshold: str = "Potential Match >= 0.80 | Possible Match >= 0.70 | Sub-threshold core >= 0.60",
    manual_checks: Optional[List[Dict[str, Any]]] = None,
    all_candidates: Optional[List[Dict[str, Any]]] = None,
    phonetic_enabled: Optional[bool] = None,
    include_full_records: bool = True,
    skip_self_check: bool = False,
) -> Tuple[Path, Path]:
    """
    Generate PDF and Excel reports for a screening search.
    Guarantees Excel generation first so evidence is never lost.
    Self-checks PDF before presentation. Never silently swallows exceptions.
    Returns (pdf_path, excel_path).
    """
    if phonetic_enabled is None:
        try:
            from modules.screening.config import PHONETIC_ENABLED
            phonetic_enabled = PHONETIC_ENABLED
        except Exception:
            phonetic_enabled = True

    sanctions_hits = sanctions_hits or []
    aviation_hits = aviation_hits or []
    country_risk_hits = country_risk_hits or []
    source_statuses = source_statuses or []

    reports_dir = _get_base_reports_dir()
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    entity_key = (
        inputs.get("name")
        or inputs.get("tail")
        or inputs.get("tail_number")
        or inputs.get("registration")
        or inputs.get("query")
        or inputs.get("country")
        or "Search"
    )
    safe_name = _safe_filename(entity_key)[:30]
    base_name = f"Screening_Report_{search_type}_{safe_name}_{ts}"

    pdf_path = reports_dir / f"{base_name}.pdf"
    excel_path = reports_dir / f"{base_name}.xlsx"

    user = getpass.getuser()
    machine = platform.node()
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # 1. Build Excel Report first (ensures Excel is always available if PDF fails)
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
        phonetic_enabled=phonetic_enabled,
        include_full_records=include_full_records,
    )

    # 2. Build PDF Report & Self-Check
    try:
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
            phonetic_enabled=phonetic_enabled,
            include_full_records=include_full_records,
        )

        if not skip_self_check:
            hits_to_check = all_candidates if (all_candidates is not None and len(all_candidates) > 0) else sanctions_hits
            _self_check_pdf(pdf_path, entity_key, hits_to_check)

    except Exception as e:
        tb = traceback.format_exc()
        raise ReportGenerationError(f"PDF Report generation failed: {e}", excel_path=excel_path, details=tb) from e

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
    phonetic_enabled: bool = True,
    include_full_records: bool = True,
) -> None:
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#0D47A1"),
        spaceAfter=6,
        wordWrap='CJK',
    )
    notice_style = ParagraphStyle(
        'Notice',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#B71C1C"),
        wordWrap='CJK',
    )
    meta_style = ParagraphStyle(
        'Meta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        wordWrap='CJK',
    )
    banner_style = ParagraphStyle(
        'Banner',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=colors.white,
        alignment=1, # Center
        wordWrap='CJK',
    )

    cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5,
        wordWrap='CJK',
    )
    cell_style_bold = ParagraphStyle(
        'TableCellBold',
        parent=cell_style,
        fontName='Helvetica-Bold',
        wordWrap='CJK',
    )
    appendix_header_style = ParagraphStyle(
        'AppendixHeader',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#0D47A1"),
        spaceBefore=8,
        spaceAfter=4,
        wordWrap='CJK',
    )
    sec_subhead_style = ParagraphStyle(
        'SecSubhead',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#263238"),
        spaceBefore=4,
        spaceAfter=2,
        wordWrap='CJK',
    )

    story = []

    # Title
    story.append(Paragraph(sanitize_for_pdf(f"<b>{APP_NAME} — {MAIN_TITLE} Screening Report</b>"), title_style))
    story.append(Spacer(1, 4))

    # Compliance Notice
    story.append(Paragraph(sanitize_for_pdf(NOTICE_TEXT), notice_style))
    story.append(Spacer(1, 8))

    # Resolve candidates to display
    hits_to_show = all_candidates if (all_candidates is not None and len(all_candidates) > 0) else sanctions_hits
    total_candidates_count = len(hits_to_show)

    # Meta Table
    ph_note = "ON" if phonetic_enabled else "OFF (Sound-alike matching OFF)"
    meta_data = [
        [Paragraph(sanitize_for_pdf(f"<b>Search Type:</b> {search_type}"), meta_style), Paragraph(sanitize_for_pdf(f"<b>Timestamp:</b> {timestamp_str}"), meta_style)],
        [Paragraph(sanitize_for_pdf(f"<b>User:</b> {user} ({machine})"), meta_style), Paragraph(sanitize_for_pdf(f"<b>OpenSanctions Used:</b> {'Yes' if opensanctions_used else 'No'}"), meta_style)],
        [Paragraph(sanitize_for_pdf(f"<b>Inputs:</b> {inputs}"), meta_style), Paragraph(sanitize_for_pdf(f"<b>Total Candidates:</b> {total_candidates_count}"), meta_style)],
        [Paragraph(sanitize_for_pdf(f"<b>Thresholds:</b> {threshold}"), meta_style), Paragraph(sanitize_for_pdf(f"<b>Sound-alike Matching:</b> {ph_note}"), meta_style)],
    ]
    t_meta = Table(meta_data, colWidths=[260, 263])
    t_meta.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 8))

    # Banner
    banner_bg = colors.HexColor("#D32F2F") if "POTENTIAL" in overall_banner or "🔴" in overall_banner or "[RED]" in overall_banner else (
        colors.HexColor("#F57C00") if "POSSIBLE" in overall_banner or "🟠" in overall_banner or "[AMBER]" in overall_banner or "SAFETY" in overall_banner else (
            colors.HexColor("#388E3C") if "NO MATCH" in overall_banner or "✅" in overall_banner or "[CLEAR]" in overall_banner else colors.HexColor("#616161")
        )
    )
    t_banner = Table([[Paragraph(sanitize_for_pdf(f"<b>OVERALL FINDING: {overall_banner}</b>"), banner_style)]], colWidths=[523])
    t_banner.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), banner_bg),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_banner)
    story.append(Spacer(1, 10))

    # Sources Checked Table
    story.append(Paragraph(sanitize_for_pdf("<b>Sources Checked & Status</b>"), styles["Heading3"]))
    src_table_data = [[
        Paragraph("<b>Source ID</b>", cell_style_bold),
        Paragraph("<b>Authority</b>", cell_style_bold),
        Paragraph("<b>Publication Date</b>", cell_style_bold),
        Paragraph("<b>Status</b>", cell_style_bold),
        Paragraph("<b>Result</b>", cell_style_bold),
    ]]
    for s in source_statuses:
        src_table_data.append([
            Paragraph(sanitize_for_pdf(str(s.get("id", "—"))), cell_style),
            Paragraph(sanitize_for_pdf(str(s.get("authority", "—"))), cell_style),
            Paragraph(sanitize_for_pdf(str(s.get("date", "—"))), cell_style),
            Paragraph(sanitize_for_pdf(str(s.get("status", "OK"))), cell_style),
            Paragraph(sanitize_for_pdf(format_chip_text(s.get("tier", "NO_MATCH"))), cell_style_bold),
        ])
    t_src = Table(src_table_data, colWidths=[80, 155, 95, 75, 118], repeatRows=1)
    t_src.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#ECEFF1")),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 7.5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CFD8DC")),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_src)
    story.append(Spacer(1, 10))

    # Section A: Sanctions
    story.append(Paragraph(sanitize_for_pdf("<b>Section A - Sanctions Findings & Candidates</b>"), styles["Heading3"]))
    story.append(Paragraph(sanitize_for_pdf("<i>Candidate matches below threshold are shown for information only. They are not matches.</i>"), meta_style))
    story.append(Spacer(1, 4))
    if hits_to_show:
        tier_weights = {"POTENTIAL_MATCH": 0, "POSSIBLE_MATCH_REVIEW": 1, "BELOW_THRESHOLD": 2}
        sorted_hits = sorted(hits_to_show, key=lambda h: (tier_weights.get(h.get("tier"), 9), -float(h.get("score") or 0.0)))

        sanc_data = [[
            Paragraph("<b>Source</b>", cell_style_bold),
            Paragraph("<b>Tier</b>", cell_style_bold),
            Paragraph("<b>Listed / Matched Name</b>", cell_style_bold),
            Paragraph("<b>ID</b>", cell_style_bold),
            Paragraph("<b>Score</b>", cell_style_bold),
            Paragraph("<b>Reason</b>", cell_style_bold),
        ]]
        for h in sorted_hits:
            m_name = h.get("matched_name", "—")
            p_name = h.get("primary_name", "—")
            exp = f" [via {h.get('expanded_from')}]" if h.get("expanded_from") else ""
            display_name = f"<b>{sanitize_for_pdf(p_name)}</b><br/><font color='#555555'>Matched: {sanitize_for_pdf(m_name)}{sanitize_for_pdf(exp)}</font>"
            sanc_data.append([
                Paragraph(sanitize_for_pdf(str(h.get("source_list") or h.get("source", "—"))), cell_style),
                Paragraph(sanitize_for_pdf(format_chip_text(h.get("tier", "—"))), cell_style_bold),
                Paragraph(display_name, cell_style),
                Paragraph(sanitize_for_pdf(str(h.get("source_id", "—"))), cell_style),
                Paragraph(f"{float(h.get('score') or 0.0):.4f}", cell_style),
                Paragraph(sanitize_for_pdf(str(h.get("reason") or h.get("reason_code", "—"))), cell_style),
            ])
        t_sanc = Table(sanc_data, colWidths=[60, 85, 195, 50, 45, 88], repeatRows=1)
        t_sanc.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#ECEFF1")),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 7),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CFD8DC")),
            ('TOPPADDING', (0,0), (-1,-1), 2.5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        story.append(t_sanc)
    else:
        story.append(Paragraph(sanitize_for_pdf("<i>No sanctions candidates found on any active list.</i>"), meta_style))
    story.append(Spacer(1, 10))

    # Section B: Aviation
    if aviation_hits:
        story.append(Paragraph(sanitize_for_pdf("<b>Section B - Aviation Safety & Export Controls</b>"), styles["Heading3"]))
        av_data = [[
            Paragraph("<b>Source / Scope</b>", cell_style_bold),
            Paragraph("<b>Type</b>", cell_style_bold),
            Paragraph("<b>Finding Details</b>", cell_style_bold),
            Paragraph("<b>Official Note</b>", cell_style_bold),
        ]]
        for a in aviation_hits:
            f_type = a.get("result_type") or a.get("finding") or "—"
            av_data.append([
                Paragraph(sanitize_for_pdf(str(a.get("source", "—"))), cell_style),
                Paragraph(sanitize_for_pdf(format_chip_text(f_type)), cell_style_bold),
                Paragraph(sanitize_for_pdf(str(a.get("detail", a.get("details", "—")))), cell_style),
                Paragraph(sanitize_for_pdf(str(a.get("note", "—"))), cell_style),
            ])
        t_av = Table(av_data, colWidths=[85, 105, 205, 128], repeatRows=1)
        t_av.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#ECEFF1")),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 7),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CFD8DC")),
            ('TOPPADDING', (0,0), (-1,-1), 2.5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        story.append(t_av)
        story.append(Spacer(1, 10))

    # Section C: Country Risk (FATF)
    if country_risk_hits:
        story.append(Paragraph(sanitize_for_pdf("<b>Section C - Country Risk (FATF Jurisdictions)</b>"), styles["Heading3"]))
        cr_data = [[
            Paragraph("<b>Country</b>", cell_style_bold),
            Paragraph("<b>List Type</b>", cell_style_bold),
            Paragraph("<b>Official Summary</b>", cell_style_bold),
            Paragraph("<b>Advisory</b>", cell_style_bold),
        ]]
        for c in country_risk_hits:
            cr_data.append([
                Paragraph(sanitize_for_pdf(str(c.get("country", "—"))), cell_style),
                Paragraph(sanitize_for_pdf(str(c.get("list_type", "—"))), cell_style_bold),
                Paragraph(sanitize_for_pdf(str(c.get("summary", c.get("call_to_action", "—")))), cell_style),
                Paragraph(sanitize_for_pdf(str(c.get("advisory", c.get("risk_label", "—")))), cell_style),
            ])
        t_cr = Table(cr_data, colWidths=[85, 95, 205, 138], repeatRows=1)
        t_cr.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#ECEFF1")),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 7),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CFD8DC")),
            ('TOPPADDING', (0,0), (-1,-1), 2.5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        story.append(t_cr)
        story.append(Spacer(1, 10))

    # Section D: Manual Official Checks
    if manual_checks:
        story.append(Paragraph(sanitize_for_pdf("<b>Section D - Manual Official Checks Performed</b>"), styles["Heading3"]))
        man_data = [[
            Paragraph("<b>Timestamp</b>", cell_style_bold),
            Paragraph("<b>Source / Portal</b>", cell_style_bold),
            Paragraph("<b>Result</b>", cell_style_bold),
            Paragraph("<b>Notes & Comments</b>", cell_style_bold),
            Paragraph("<b>Official Verify Link</b>", cell_style_bold),
        ]]
        for mc in manual_checks:
            man_data.append([
                Paragraph(sanitize_for_pdf(str(mc.get("timestamp", "—"))), cell_style),
                Paragraph(sanitize_for_pdf(str(mc.get("source_name", mc.get("source", "—")))), cell_style),
                Paragraph(sanitize_for_pdf(format_chip_text(mc.get("result", "—"))), cell_style_bold),
                Paragraph(sanitize_for_pdf(str(mc.get("comment", "—"))), cell_style),
                Paragraph(sanitize_for_pdf(str(mc.get("verify_url", "—"))), cell_style),
            ])
        t_man = Table(man_data, colWidths=[80, 105, 80, 130, 128], repeatRows=1)
        t_man.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#ECEFF1")),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 7),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CFD8DC")),
            ('TOPPADDING', (0,0), (-1,-1), 2.5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        story.append(t_man)
        story.append(Spacer(1, 10))

    # Section E: Ownership & Control Analysis
    ubo_data = inputs.get("ubo_result") or inputs.get("ownership_data")
    if ubo_data or search_type == "ownership":
        story.append(Paragraph(sanitize_for_pdf("<b>Section E - Ownership & Control Analysis</b>"), styles["Heading3"]))
        ubo_info = []
        if isinstance(ubo_data, dict):
            target_cp = ubo_data.get("target_name", "Target Entity")
            ofac_v = ubo_data.get("ofac_verdict", {}).get("verdict_text", "Not evaluated")
            eu_v = ubo_data.get("eu_verdict", {}).get("verdict_text", "Not evaluated")
            uk_v = ubo_data.get("uk_verdict", {}).get("verdict_text", "Not evaluated")
            shortfall = ubo_data.get("undisclosed_ownership_pct", 0.0)
            ubo_info.extend([
                [Paragraph("<b>Target Counterparty</b>", cell_style_bold), Paragraph(sanitize_for_pdf(str(target_cp)), cell_style)],
                [Paragraph("<b>US OFAC 50% Rule</b>", cell_style_bold), Paragraph(sanitize_for_pdf(str(ofac_v)), cell_style)],
                [Paragraph("<b>EU Sanctions (>=50% / Control)</b>", cell_style_bold), Paragraph(sanitize_for_pdf(str(eu_v)), cell_style)],
                [Paragraph("<b>UK OFSI (>50% / Majority)</b>", cell_style_bold), Paragraph(sanitize_for_pdf(str(uk_v)), cell_style)],
                [Paragraph("<b>Undisclosed Ownership Shortfall</b>", cell_style_bold), Paragraph(sanitize_for_pdf(f"{shortfall}%"), cell_style)],
            ])
        else:
            ubo_info.append([Paragraph("<b>Analysis</b>", cell_style_bold), Paragraph(sanitize_for_pdf("Ownership and control structure analyzed in compliance with multilateral sanctions rules."), cell_style)])

        t_ubo = Table(ubo_info, colWidths=[150, 373])
        t_ubo.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#ECEFF1")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CFD8DC")),
            ('TOPPADDING', (0,0), (-1,-1), 2.5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        story.append(t_ubo)
        story.append(Spacer(1, 10))

    # Section F: Full Records Appendix (Part B4 - ON by default for 🔴 and 🟠 hits)
    if include_full_records and hits_to_show:
        priority_hits = [h for h in hits_to_show if h.get("tier") in ("POTENTIAL_MATCH", "POSSIBLE_MATCH_REVIEW")]
        if not priority_hits:
            priority_hits = hits_to_show[:3] # Show up to top 3 hits if only info/weak hits

        if priority_hits:
            story.append(Spacer(1, 6))
            story.append(Paragraph(sanitize_for_pdf("<b>Section F - Full Regulatory Records Appendix (13 Standard Sections)</b>"), appendix_header_style))
            story.append(Paragraph(sanitize_for_pdf("<i>Full official publisher disclosures for all matching regulatory entries with zero field suppression.</i>"), meta_style))
            story.append(Spacer(1, 6))

            for h in priority_hits:
                src_list = str(h.get("source_list") or h.get("source") or "regulatory_source")
                rec_id = str(h.get("source_id") or "")
                rec_payload = get_record(src_list, rec_id) or h
                sections = build_13_sections(rec_payload, src_list)

                pname = h.get("primary_name") or rec_payload.get("name") or "—"
                mname = h.get("matched_name") or pname
                score_str = f"{float(h.get('score') or 0.0):.4f}"
                reason_str = str(h.get("reason") or h.get("reason_code") or "Match")

                hit_box = [
                    [Paragraph(sanitize_for_pdf(f"<b>Record: {src_list.upper()} — ID: {rec_id} ({pname})</b>"), cell_style_bold)],
                    [Paragraph(sanitize_for_pdf(f"Matched on '{mname}' | Score: {score_str} | Reason: {reason_str}"), cell_style)],
                ]
                t_hitbox = Table(hit_box, colWidths=[523])
                t_hitbox.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#E0F2FE")),
                    ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#0284C7")),
                    ('TOPPADDING', (0,0), (-1,-1), 3),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 3),
                ]))
                story.append(t_hitbox)
                story.append(Spacer(1, 4))

                for sec_title, items in sections.items():
                    story.append(Paragraph(sanitize_for_pdf(f"<b>{sec_title}</b>"), sec_subhead_style))
                    sec_rows = []
                    for label, val in items:
                        sec_rows.append([
                            Paragraph(sanitize_for_pdf(f"<b>{label}</b>"), cell_style_bold),
                            Paragraph(sanitize_for_pdf(val), cell_style),
                        ])
                    t_sec = Table(sec_rows, colWidths=[140, 383])
                    t_sec.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#F8FAFC")),
                        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
                        ('TOPPADDING', (0,0), (-1,-1), 2),
                        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
                        ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ]))
                    story.append(t_sec)
                    story.append(Spacer(1, 4))
                story.append(Spacer(1, 6))

    # Footer note
    story.append(Spacer(1, 10))
    story.append(Paragraph(sanitize_for_pdf("<i>End of Screening Report. Generated by Naughty or not (Sanction checK).</i>"), meta_style))

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
    phonetic_enabled: bool = True,
    include_full_records: bool = True,
) -> None:
    wb = openpyxl.Workbook()

    # Sheet 1: Summary & Meta
    ws_meta = wb.active
    ws_meta.title = "Screening Summary"

    ws_meta["A1"] = f"{APP_NAME} — {MAIN_TITLE} Screening Report"
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
        ("Sound-alike Matching", "ON" if phonetic_enabled else "OFF (Sound-alike matching OFF)"),
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
            format_chip_text(s.get("tier", "NO_MATCH")),
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
            format_chip_text(h.get("tier", "—")),
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
                format_chip_text(mc.get("result", "—")),
                mc.get("comment", "—"),
                mc.get("verify_url", "—"),
            ])

    # Sheet 7: Full records (Part B4 - long format: Source, Record ID, Section, Field, Value)
    if include_full_records and hits_to_show:
        ws_full = wb.create_sheet(title="Full records")
        headers_full = ["Source", "Record ID", "Section", "Field", "Value"]
        ws_full.append(headers_full)
        for cell in ws_full[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="ECEFF1", end_color="ECEFF1", fill_type="solid")

        priority_hits = [h for h in hits_to_show if h.get("tier") in ("POTENTIAL_MATCH", "POSSIBLE_MATCH_REVIEW")]
        if not priority_hits:
            priority_hits = hits_to_show[:3]

        for h in priority_hits:
            src_list = str(h.get("source_list") or h.get("source") or "regulatory_source")
            rec_id = str(h.get("source_id") or "")
            rec_payload = get_record(src_list, rec_id) or h
            sections = build_13_sections(rec_payload, src_list)
            for sec_title, items in sections.items():
                for label, val in items:
                    ws_full.append([src_list, rec_id, sec_title, label, val])

    # Column autofit and wrapping on all sheets
    for ws in wb.worksheets:
        for row in ws.iter_rows(min_row=2):
            max_lines = 1
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
                val = str(cell.value or "")
                lines = val.count("\n") + 1
                col_letter = openpyxl.utils.get_column_letter(cell.column)
                col_w = ws.column_dimensions[col_letter].width or 20
                est = max(lines, int(len(val) / max(col_w, 10)) + 1)
                if est > max_lines:
                    max_lines = min(est, 8)
            ws.row_dimensions[row[0].row].height = max(18, max_lines * 14)
        for col in ws.columns:
            max_len = max([len(str(cell.value or '')) for cell in col], default=0)
            col_letter = openpyxl.utils.get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = min(max(max_len + 2, 12), 45)

    wb.save(str(excel_path))


def generate_raw_reports(
    query: str,
    results: List[Dict[str, Any]],
    options: Dict[str, Any],
) -> Tuple[Path, Path]:
    """Generate reports specifically for Raw Text Index Searches."""
    sanctions_hits = sanctions_hits or []
    aviation_hits = aviation_hits or []
    country_risk_hits = country_risk_hits or []
    source_statuses = source_statuses or []

    reports_dir = _get_base_reports_dir()
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_q = _safe_filename(query)[:30]
    base_name = f"RawSearch_Report_{safe_q}_{ts}"
    pdf_path = reports_dir / f"{base_name}.pdf"
    excel_path = reports_dir / f"{base_name}.xlsx"

    # 1. Excel Report first (ensures Excel is always available if PDF fails)
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

    # 2. PDF Report & Self-Check
    try:
        doc = SimpleDocTemplate(str(pdf_path), pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
        styles = getSampleStyleSheet()
        story = [
            Paragraph(sanitize_for_pdf(f"<b>{APP_NAME} - {MAIN_TITLE} Raw Search Audit Report</b>"), styles['Heading1']),
            Spacer(1, 4),
            Paragraph(sanitize_for_pdf(NOTICE_TEXT), ParagraphStyle('N', parent=styles['Normal'], fontSize=7, textColor=colors.HexColor("#B71C1C"))),
            Spacer(1, 10),
            Paragraph(sanitize_for_pdf(f"<b>Query:</b> {query} | <b>Total Matches:</b> {len(results)} | <b>Options:</b> {options}"), styles['Normal']),
            Spacer(1, 10),
        ]
        t_data = [["Source", "Source ID", "Field", "Matched Term", "Snippet / Details"]]
        for r in results[:100]:
            t_data.append([
                r.get("source_id", "—"),
                r.get("entity_id", "—"),
                r.get("field", "—"),
                r.get("term", "—"),
                Paragraph(sanitize_for_pdf(str(r.get("snippet", "—"))[:200]), styles['Normal']),
            ])
        t = Table(t_data, colWidths=[80, 80, 70, 90, 203], repeatRows=1)
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
        _self_check_pdf(pdf_path, query, [])
    except Exception as e:
        tb = traceback.format_exc()
        raise ReportGenerationError(f"Raw Search PDF Report generation failed: {e}", excel_path=excel_path, details=tb) from e

    return pdf_path, excel_path
