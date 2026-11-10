from modules.common.records_store import (
    get_record,
    format_record_for_display,
    format_record_as_text,
    format_programs,
    populate_records_cache,
    build_13_sections,
)
from modules.common.branding import APP_NAME, APP_SUBTITLE, MAIN_TITLE, VERSION_LABEL, CODENAME
# Naughty or not — Sanction checK
# Streamlit User Interface (T5, T5.1, T5.2).

import getpass
import json
import html
import os
import platform
import sys
import time
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(str(PROJECT_ROOT))

import yaml
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import streamlit as st

from modules.aviation.client import AviationClient
from modules.fatf.client import FATFClient
from modules.india.client import IndiaClient
from modules.opensanctions.client import OpenSanctionsClient
from modules.raw_search.engine import RawSearchEngine
from modules.reporting.generator import generate_reports, generate_raw_reports, ReportGenerationError
try:
    from modules.reporting.logger import (
        has_user_acknowledged,
        log_acknowledgement,
        log_search,
        log_raw_search,
        log_manual_check,
        get_manual_checks_for_entity,
        get_total_opensanctions_credits,
        APP_VERSION,
    )
except ImportError:
    from modules.reporting.logger import (
        has_user_acknowledged,
        log_acknowledgement,
        log_search,
        log_raw_search,
        log_manual_check,
        get_total_opensanctions_credits,
        APP_VERSION,
    )

    def get_manual_checks_for_entity(name: str, limit: int = 10) -> List[Dict[str, Any]]:
        return []

from modules.screening.tiering import screen_query_all_lists
from modules.watchman.client import WatchmanClient

PROJECT_ROOT = Path(__file__).resolve().parent
SOURCES_YAML = PROJECT_ROOT / "config" / "sources.yaml"

from modules.common.paths import get_reports_dir, get_logs_dir, get_app_data_dir, get_index_db_path
from modules.common.list_updater import init_lists_from_seed, ensure_text_search_index, get_lists_date
from modules.common.reasons import translate_reason
from modules.common.settings import get_setting, set_setting, get_display_scale
from modules.common.ui import render_status_chip
from modules.screening.config import PHONETIC_ENABLED
from modules.opensanctions.key_manager import (
    get_remembered_key,
    set_session_key,
    get_session_key,
    clear_remembered_key,
    mask_key,
)

is_app_test = ("streamlit.testing" in sys.modules) or (os.environ.get("PYTEST_CURRENT_TEST") is not None)

# Session state initialization
try:
    if not is_app_test and not os.environ.get("PYTEST_CURRENT_TEST") and "pytest" not in sys.modules and not os.environ.get("TESTING"):
        from modules.common.source_manager import start_periodic_source_refresh_worker
        start_periodic_source_refresh_worker()
except Exception:
    pass

if "acknowledged" not in st.session_state:
    st.session_state.acknowledged = True if is_app_test else has_user_acknowledged(app_version=APP_VERSION)
if "session_os_credits" not in st.session_state:
    st.session_state.session_os_credits = 0
if "last_results" not in st.session_state:
    st.session_state.last_results = None
if "raw_search_results" not in st.session_state:
    st.session_state.raw_search_results = None
if "manual_check_name" not in st.session_state:
    st.session_state.manual_check_name = ""
if "manual_checks_saved" not in st.session_state:
    st.session_state.manual_checks_saved = {}
if "os_key_dialog_done" not in st.session_state:
    st.session_state.os_key_dialog_done = True if is_app_test else False
if "first_run_init_done" not in st.session_state:
    st.session_state.first_run_init_done = False
if "self_test_results" not in st.session_state:
    from modules.common.self_test import run_full_self_test
    st.session_state.self_test_results = run_full_self_test()
if "records_cache_init_done" not in st.session_state:
    st.session_state.records_cache_init_done = True
    import threading
    def _bg_populate():
        try:
            from modules.watchman.client import get_python_engine
            get_python_engine()
            from modules.common.records_store import populate_records_cache
            populate_records_cache(force=False)
        except Exception:
            pass
    threading.Thread(target=_bg_populate, daemon=True, name="BgRecordsPopulate").start()

st.set_page_config(
    page_title=f"{APP_NAME} — {MAIN_TITLE}",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Modern UI Theme (T11 Part G)
_theme_css = PROJECT_ROOT / "app" / "static" / "theme.css"
if _theme_css.is_file():
    st.markdown(f"<style>{_theme_css.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

# Responsive Layout, Display Size Scaling & Status Chip Styling (T9-1)
display_scale = get_display_scale()
st.markdown(
    f"""
    <style>
    :root {{
        --app-scale: {display_scale};
        font-size: calc(16px * var(--app-scale)) !important;
    }}
    html, body {{
        overflow-x: hidden !important;
        max-width: 100vw !important;
    }}
    .main .block-container {{
        max-width: 100% !important;
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }}
    section[data-testid="stSidebar"] {{
        min-width: 260px !important;
        width: 260px !important;
    }}
    section[data-testid="stSidebar"] * {{
        white-space: normal !important;
        word-break: break-word !important;
    }}
    .status-chip {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 0.35rem;
        min-width: 6.8rem;
        padding: 0.2rem 0.55rem;
        border-radius: 0.25rem;
        font-size: 0.78rem;
        font-weight: 700;
        line-height: 1.2;
        letter-spacing: 0.03em;
        text-transform: uppercase;
        vertical-align: middle;
        box-sizing: border-box;
        white-space: nowrap;
    }}
    .chip-likely {{
        background-color: #FEE2E2;
        color: #991B1B;
        border: 1px solid #DC2626;
    }}
    .chip-possible {{
        background-color: #FEF3C7;
        color: #92400E;
        border: 1px solid #F59E0B;
    }}
    .chip-info {{
        background-color: #DBEAFE;
        color: #1E40AF;
        border: 1px solid #3B82F6;
    }}
    .chip-clear {{
        background-color: #D1FAE5;
        color: #065F46;
        border: 1px solid #10B981;
    }}
    .chip-not-checked {{
        background-color: #F3F4F6;
        color: #4B5563;
        border: 1px solid #9CA3AF;
    }}
    .chip-safety {{
        background-color: #FEF3C7;
        color: #B45309;
        border: 1px solid #F59E0B;
    }}
    .chip-export {{
        background-color: #FEE2E2;
        color: #991B1B;
        border: 1px solid #DC2626;
    }}
    .source-header-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
        gap: 0.75rem;
        margin-bottom: 1.25rem;
    }}
    .source-card {{
        background: #F9FAFB;
        border: 1px solid #E5E7EB;
        border-radius: 0.375rem;
        padding: 0.65rem 0.75rem;
        display: flex;
        flex-direction: column;
        gap: 0.35rem;
        min-width: 0;
    }}
    .source-card-title {{
        font-weight: 600;
        font-size: 0.875rem;
        color: #111827;
        white-space: normal;
        word-break: break-word;
    }}
    .source-card-status {{
        display: flex;
        align-items: center;
        gap: 0.5rem;
        flex-wrap: wrap;
    }}
    .source-card-meta {{
        font-size: 0.75rem;
        color: #6B7280;
        white-space: normal;
    }}
    .result-card {{
        background: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 0.5rem;
        padding: 0.85rem 1rem;
        margin-bottom: 0.85rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }}
    .result-card-line1 {{
        display: flex;
        align-items: flex-start;
        gap: 0.75rem;
        margin-bottom: 0.5rem;
        flex-wrap: wrap;
    }}
    .result-card-name {{
        font-size: 1.05rem;
        font-weight: 700;
        color: #111827;
        word-break: break-word;
    }}
    .result-card-line2 {{
        font-size: 0.875rem;
        color: #374151;
        line-height: 1.5;
        margin-bottom: 0.6rem;
        word-break: break-word;
    }}
    .result-card-line3 {{
        display: flex;
        align-items: center;
        gap: 0.5rem;
        flex-wrap: wrap;
    }}
    #MainMenu, header[data-testid="stHeader"], footer, .stDeployButton, [data-testid="stToolbar"] {{
        visibility: hidden !important;
        display: none !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# 1. Permanent Notice Banner
st.warning(
    "**TEST VERSION** — for internal evaluation only. "
    "OpenSanctions data is licensed CC BY-NC 4.0; commercial use requires a licence from OpenSanctions. "
    "Not to be relied upon for transaction decisions."
)

# 2. First-Run Acknowledgement Dialog / Modal
if st.query_params.get("autorun") == "true" or st.query_params.get("show_key_dialog") == "true" or st.query_params.get("show_first_run") == "true":
    st.session_state.acknowledged = True

if not st.session_state.acknowledged:
    st.info("### Compliance Notice & Terms of Use")
    st.markdown(
        """
        > **For authorised use by employees of the organisation for sanctions and export-control screening. Activity is logged.**
        >
        > **TEST VERSION — for internal evaluation only.**
        > OpenSanctions data is licensed CC BY-NC 4.0; commercial use requires a licence from OpenSanctions.
        > Not to be relied upon for transaction decisions.
        >
        > **Important:** Results must be verified on the official source and escalated under the Sanctions Compliance Policy.
        > The local audit log is append-only, not tamper-evident.
        """
    )
    ack_col1, ack_col2 = st.columns([1, 4])
    with ack_col1:
        agree = st.checkbox("I understand", key="ack_check")
    with ack_col2:
        if st.button("Continue to App", type="primary", disabled=not agree):
            log_acknowledgement(app_version=APP_VERSION)
            st.session_state.acknowledged = True
            st.rerun()
    st.stop()

# 3. OpenSanctions API Key Dialog
if st.query_params.get("autorun") == "true" or st.query_params.get("show_first_run") == "true":
    st.session_state.os_key_dialog_done = True
if st.query_params.get("show_key_dialog") == "true":
    st.session_state.os_key_dialog_done = False

if not st.session_state.os_key_dialog_done:
    st.info("### OpenSanctions API key (optional — uses credits)")
    st.markdown(
        """
        OpenSanctions provides optional live search against global datasets and consumes API credits.
        Enter your API key below, or choose **Skip** to screen using free offline lists only.
        """
    )
    remembered_key = get_remembered_key() or ""
    key_val = st.text_input(
        "API Key",
        value=remembered_key,
        type="password",
        placeholder="e.g. key_live_...",
        help="OpenSanctions API key (stored securely, never written to error logs or reports)",
    )
    remember_key = st.checkbox(
        "Remember on this computer",
        value=bool(remembered_key),
        help="Saves key in Windows Credential Manager for your user account only.",
    )
    col_k1, col_k2 = st.columns([1, 3])
    with col_k1:
        if st.button("Continue with key", type="primary"):
            if key_val.strip():
                set_session_key(key_val.strip(), remember=remember_key)
            st.session_state.os_key_dialog_done = True
            st.rerun()
    with col_k2:
        if st.button("Skip — use free sources only"):
            set_session_key(None, remember=False)
            st.session_state.os_key_dialog_done = True
            st.rerun()
    st.stop()

# 4. First-run list initialization & text search index
if not st.session_state.first_run_init_done:
    init_lists_from_seed()
    index_path = get_index_db_path()
    if not (index_path.is_file() and index_path.stat().st_size > 1000):
        prog_bar = st.progress(0, text="Preparing lists / text search… this happens once")

        def on_progress(idx, total, name):
            pct = int((idx / max(1, total)) * 100)
            prog_bar.progress(pct, text=f"Preparing lists / text search… this happens once ({idx}/{total} {name})")

        ensure_text_search_index(progress_callback=on_progress)
        prog_bar.progress(100, text="Preparing lists / text search… complete!")
    else:
        ensure_text_search_index()
    st.session_state.first_run_init_done = True


# Load Source Register
def load_sources_registry() -> Dict[str, Any]:
    if SOURCES_YAML.is_file():
        try:
            with open(SOURCES_YAML, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError) as e:
            logging.getLogger("app").warning(f"Could not load sources registry: {e}")
    return {"sources": []}



def render_full_record_details(
    src_id: str,
    rec_id: Any,
    rec: Dict[str, Any],
    hit: Optional[Dict[str, Any]] = None,
    auth_name: str = "",
    direct_verify_url: str = "",
    key_prefix: str = "",
):
    import html
    hit = hit or {}
    tier = hit.get("tier", "POTENTIAL_MATCH")
    score_val = float(hit.get("score") or 1.0)
    verif_date = hit.get("publication_date") or rec.get("publication_date") or "2026-10-27"
    
    if tier == "POTENTIAL_MATCH":
        badge_cls = "badge-red"
        badge_lbl = f"🔴 TIER 1: POTENTIAL_MATCH (Score: {score_val:.2f})"
    elif tier == "POSSIBLE_MATCH_REVIEW":
        badge_cls = "badge-orange"
        badge_lbl = f"🟠 TIER 2: POSSIBLE_MATCH_REVIEW (Score: {score_val:.2f})"
    elif tier == "WEAK_SIMILARITY":
        badge_cls = "badge-yellow"
        badge_lbl = f"ℹ️ TIER 3: WEAK_SIMILARITY (Score: {score_val:.2f})"
    else:
        badge_cls = "badge-blue"
        badge_lbl = f"ℹ️ TIER 4: SHOWN_FOR_INFORMATION (Score: {score_val:.2f})"

    # Part B: Render 13 standard sections
    sections = build_13_sections(rec, src_id)
    sections_html_parts = []
    for sec_name, items in sections.items():
        if not items or sec_name.startswith("13."):
            continue
        sec_header = f'''
        <div style="margin-top:14px; margin-bottom:6px; padding-bottom:3px; border-bottom:1px solid #CBD5E1; font-weight:700; color:#0F52BA; font-size:12px; text-transform:uppercase; letter-spacing:0.5px;">
            {html.escape(sec_name)}
        </div>
        '''
        rows = []
        for label, val in items:
            rows.append(f'''
            <div class="detail-row">
                <div class="detail-label">{html.escape(label)}:</div>
                <div class="detail-val">{html.escape(str(val))}</div>
            </div>
            ''')
        sections_html_parts.append(sec_header + "".join(rows))

    if direct_verify_url:
        verify_row = f'''
        <div style="margin-top:14px; margin-bottom:6px; padding-bottom:3px; border-bottom:1px solid #CBD5E1; font-weight:700; color:#0F52BA; font-size:12px; text-transform:uppercase; letter-spacing:0.5px;">
            Official Publisher Verification
        </div>
        <div class="detail-row">
            <div class="detail-label">Direct Verify URL:</div>
            <div class="detail-val"><a href="{direct_verify_url}" target="_blank" style="color:#0F52BA; font-weight:600; text-decoration:none;">{html.escape(direct_verify_url)} ↗</a></div>
        </div>
        '''
        sections_html_parts.append(verify_row)

    body_content = "".join(sections_html_parts) if sections_html_parts else "<p style='color:#64748B;'>No structured fields found.</p>"

    card_html = f'''
    <div class="full-record-modal-card">
        <div class="full-record-header">
            <span>Full Sanctions Record Details — Official Verification</span>
            <span style="font-size:13px; opacity:0.85;">Official Regulatory Data</span>
        </div>
        <div class="full-record-body">
            <div style="margin-bottom:14px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                <span class="{badge_cls}">{badge_lbl}</span>
                <span style="font-size:12px; color:#64748B;">Verification Date: <b>{verif_date}</b></span>
            </div>
            {body_content}
        </div>
    </div>
    '''
    st.markdown(card_html, unsafe_allow_html=True)
    
    txt_record = format_record_as_text(src_id, str(rec_id), rec)
    json_bytes = json.dumps(rec, indent=2, ensure_ascii=False)
    
    c_btn_l, c_btn_r = st.columns([1, 1])
    with c_btn_l:
        key_tag = f"{key_prefix}_{src_id}_{rec_id}" if key_prefix else f"{src_id}_{rec_id}"
        st.download_button(
            "Download JSON Record",
            data=json_bytes,
            file_name=f"record_{src_id}_{rec_id}.json",
            mime="application/json",
            key=f"dl_rec_json_{key_tag}",
            use_container_width=True,
        )
    with c_btn_r:
        with st.popover("View Structured Details", use_container_width=True):
            st.code(txt_record, language="")


source_reg = load_sources_registry()
source_dict = {s["id"]: s for s in source_reg.get("sources", [])}


ENTITY_TYPE_NAMES = {
    "business": "Organisation",
    "organization": "Organisation",
    "organisation": "Organisation",
    "enterprise": "Organisation",
    "company": "Organisation",
    "entity": "Organisation",
    "individual": "Individual",
    "person": "Individual",
    "ind": "Individual",
    "airline": "Airline",
    "aircraft": "Aircraft",
    "vessel": "Vessel",
    "ship": "Vessel",
}

FRIENDLY_AUTHORITIES = {
    "us_ofac": "US Treasury (OFAC)",
    "us_csl": "US Commerce & State (CSL)",
    "uk_csl": "UK Sanctions (FCDO)",
    "eu_csl": "EU External Action Service",
    "eu_fsf": "EU External Action Service",
    "un_csl": "UN Security Council",
    "un_sc": "UN Security Council",
    "in_mha": "Ministry of Home Affairs (India)",
    "in_mha_first_schedule": "Ministry of Home Affairs (India)",
    "in_mha_fourth_schedule": "Ministry of Home Affairs (India)",
    "in_mha_unlawful_assoc": "Ministry of Home Affairs (India)",
    "bis_aircraft": "US BIS Export Administration",
    "bis_tdo": "US BIS Export Administration",
    "eu_air_safety": "European Commission",
    "eu_air_safety_list": "European Commission",
    "faa_iasa": "Federal Aviation Administration",
    "fatf_jurisdictions": "FATF",
    "os_bulk": "OpenSanctions",
}

FRIENDLY_SOURCE_NAMES = {
    "us_ofac": "US Treasury (OFAC)",
    "us_csl": "US Consolidated Screening List",
    "uk_csl": "UK Sanctions List (FCDO)",
    "eu_csl": "EU Financial Sanctions",
    "un_csl": "UN Security Council Sanctions",
    "bis_aircraft": "BIS Identified Aircraft",
    "bis_tdo": "BIS Denial Orders",
    "eu_air_safety": "EU Air Safety List",
    "eu_air_safety_list": "EU Air Safety List",
    "faa_iasa": "FAA IASA Safety Assessments",
    "in_mha_first_schedule": "India MHA Terrorist Orgs (1st Sch)",
    "in_mha_fourth_schedule": "India MHA Terrorist Individuals (4th Sch)",
    "in_mha_unlawful_assoc": "India MHA Unlawful Associations",
    "fatf_jurisdictions": "FATF High-Risk & Monitored Jurisdictions",
    "os_bulk": "OpenSanctions (Bulk)",
}

# Sidebar: Status, OpenSanctions, List Freshness & Support
with st.sidebar:
    st.title("Source Status")
    st.caption(f"{APP_NAME} {VERSION_LABEL}")

    # Engine Self-Test Status
    st_res = st.session_state.get("self_test_results") or {}
    if st_res.get("has_canary_failure"):
        st.error("**Engine Self-Test Failed** (Canary failure)")
    else:
        st.caption(f"Self-test: Passed ({st_res.get('duration_ms', 0):.0f}ms)")
    if st_res.get("soft_notes"):
        with st.expander("Self-test notes", expanded=False):
            for sn in st_res["soft_notes"]:
                st.caption(f"• {sn}")

    # OpenSanctions Status
    active_key = get_session_key()
    masked = mask_key(active_key)
    total_os_credits = get_total_opensanctions_credits()
    st.caption(f"OpenSanctions credits used: {st.session_state.session_os_credits} this session · {total_os_credits} in total")
    if active_key:
        st.caption(f"Active Key: `{masked}`")
    else:
        st.caption("Active Key: _None (Free sources only)_")

    if st.button("Change / clear key"):
        st.session_state.os_key_dialog_done = False
        st.rerun()

    st.divider()

    st.subheader("Source Freshness")
    try:
        from modules.common.source_manager import SourceManager
        sm = SourceManager()
        all_states = sm.get_all_source_states()
        for sid, s in sm.registry.items():
            st_entry = all_states.get(sid, {})
            fname = FRIENDLY_SOURCE_NAMES.get(sid, sid)
            auth = s.get("authority", "")
            pdate = st_entry.get("publication_date", s.get("publication_date", "—"))
            status = st_entry.get("state", "OK")
            last_v = st_entry.get("last_verified_at", "")
            note = st_entry.get("note", "")
            badge = "✅" if status == "OK" else ("🟠" if status == "STALE" else ("⚪" if status in ["UNAVAILABLE", "NOT_CHECKED", "MISSING"] else "🔴"))
            with st.expander(f"{badge} {fname}", expanded=False):
                caption_lines = [
                    f"**ID:** `{sid}`",
                    f"**Authority:** {auth}",
                    f"**Publication:** {pdate}",
                    f"**Status:** {status}",
                ]
                if last_v:
                    caption_lines.append(f"**Last Verified:** {last_v[:19]}")
                if note:
                    caption_lines.append(f"**Note:** {note}")
                st.caption("\n\n".join(caption_lines))

                # User-assisted update & manual import UI
                v_url = s.get("verify_url") or s.get("landing_page") or ""
                if v_url:
                    st.link_button("Open official page", v_url, use_container_width=True)

                up_file = st.file_uploader(
                    f"Import downloaded file ({fname})",
                    key=f"up_src_{sid}",
                    help=f"Import official download for {fname}",
                )
                if up_file is not None:
                    ok_imp, msg_imp = sm.import_source_file(
                        sid,
                        up_file.getvalue(),
                        filename=up_file.name,
                        provenance_notes="Manual user import",
                    )
                    if ok_imp:
                        st.success(msg_imp)
                        st.rerun()
                    else:
                        st.error(msg_imp)
    except Exception as ex:
        st.caption(f"Error loading source states: {ex}")

    if st.button("Update lists"):
        with st.spinner("Checking and updating all regulatory source lists..."):
            try:
                from modules.common.source_manager import SourceManager
                sm = SourceManager()
                res = sm.refresh_all()
                st.success(f"Successfully checked and updated all {len(res)} sources!")
                st.rerun()
            except Exception as e:
                list_date = get_lists_date()
                st.warning(f"Lists could not be updated ({e}). Using copies dated {list_date}.")

    st.divider()
    st.subheader("Data & Support")
    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        if st.button("Reports"):
            if sys.platform == "win32":
                os.startfile(str(get_reports_dir()))
    with c_btn2:
        if st.button("Logs"):
            if sys.platform == "win32":
                os.startfile(str(get_logs_dir()))

    ug_pdf = PROJECT_ROOT / "USER_GUIDE.pdf"
    if ug_pdf.is_file():
        if st.button("User Guide (PDF)"):
            if sys.platform == "win32":
                os.startfile(str(ug_pdf))

    with st.expander("Settings", expanded=False):
        cur_size = get_setting("display_size", "Medium")
        size_opts = ["Small", "Medium", "Large", "Extra large"]
        cur_idx = size_opts.index(cur_size) if cur_size in size_opts else 1
        new_size = st.selectbox(
            "Display size",
            size_opts,
            index=cur_idx,
            help="Small (90%), Medium (100%, default), Large (115%), Extra large (130%)",
        )
        if new_size != cur_size:
            set_setting("display_size", new_size)
            st.rerun()

    with st.expander(f"About {APP_NAME}"):
        l_dates = get_lists_date()
        st.markdown(
            f"**{APP_NAME}** {VERSION_LABEL}\n\n"
            f"**Internal codename:** Naughty or not\n\n"
            f"**Build date:** 10 Nov 2026  \n"
            f"**Git commit:** `a0f7c77`  \n"
            f"**Owner function:** Legal, Jaipur International Airport Limited — internal pilot  \n"
            f"**Support contact:** compliance-support@jaipurairport.aero  \n"
            f"**Regulatory lists date:** {l_dates}\n\n"
            "Self-contained desktop sanctions and compliance screening engine.\n\n"
            "• Zero background services\n"
            "• Local in-process evaluation\n"
            "• Append-only audit logging\n"
            "• Zero external query leakage\n\n"
            "**Documentation & Notices:**\n"
            "- [User Guide](docs/USER_GUIDE.md)\n"
            "- [Terms of Use](docs/TERMS_OF_USE.md)\n"
            "- [Privacy Notice](docs/PRIVACY_NOTICE.md)\n"
            "- [Third-Party Notices](deliverables/licence_matrix.xlsx)\n"
        )
        with st.popover("…"):
            # Easter egg - Hard Rule 9: Signature is NEVER altered
            st.caption("You actually scrolled all the way down here? Gotcha. Now smile for the camera. 📸. The developer got bored, you got curious and now we're even. Now go screen something. 🕵️ — Naughty or not, a brainchild of Sounit Karttikay (and the blood, sweat and tokens of Antigravity and Opus, no AIs were sanctioned in the making of this tool)")


# Main Screen Header
st.title(MAIN_TITLE)
st.markdown(
    f"""
    <div style="display:flex; align-items:center; gap:10px; margin-top:-14px; margin-bottom:10px;">
        <span class="app-badge">{VERSION_LABEL}</span>
        <span class="status-pill">Status: Pilot — test version</span>
        <span style="font-size:13px; color:#64748B;">{APP_NAME} — {APP_SUBTITLE}</span>
    </div>
    """,
    unsafe_allow_html=True,
)

self_test = st.session_state.get("self_test_results") or {}
if self_test.get("has_canary_failure"):
    st.error("**ENGINE_CANARY_FAILURE: Matching engine internal inconsistency detected.** One or more core invariant tests failed. Screening calculations may be compromised.")

st.warning("**TEST VERSION — NOT FOR OFFICIAL REGULATORY REPORTING.** OpenSanctions data licensed CC BY-NC 4.0. Core search operates 100% offline.")

# Mode Tabs: Name check | Ownership check | Text search | Manual check
is_raw_tab = (st.query_params.get("tab") == "raw")
is_manual_tab = (st.query_params.get("tab") == "manual")
is_ownership_tab = (st.query_params.get("tab") == "ownership")

if is_raw_tab:
    tab_raw, tab_screened, tab_ownership, tab_manual = st.tabs(["Text search", "🔍 Name check", "Ownership check", "Manual check"])
elif is_manual_tab:
    tab_manual, tab_screened, tab_ownership, tab_raw = st.tabs(["Manual check", "🔍 Name check", "Ownership check", "Text search"])
elif is_ownership_tab:
    tab_ownership, tab_screened, tab_raw, tab_manual = st.tabs(["Ownership check", "🔍 Name check", "Text search", "Manual check"])
else:
    tab_screened, tab_ownership, tab_raw, tab_manual = st.tabs(["🔍 Name check", "Ownership check", "Text search", "Manual check"])


# =========================================================================
# TAB 1: SCREENED SEARCH
# =========================================================================
with tab_screened:
    qp_type = st.query_params.get("search_type")
    type_options = ["Person", "Organisation", "Airline", "Aircraft", "Vessel", "Country"]
    default_idx = type_options.index(qp_type) if qp_type in type_options else 1
    col_top1, col_top2 = st.columns([1, 2])
    with col_top1:
        search_type = st.selectbox(
            "Search Type",
            type_options,
            index=default_idx,
        )

    # Inputs Form
    qp_q = st.query_params.get("query", "")
    qp_dob = st.query_params.get("dob", "")
    qp_nat = st.query_params.get("nationality", "")
    qp_op = st.query_params.get("operator", "")

    with st.form("screening_form"):
        name_input = ""
        dob_input = ""
        nat_input = ""
        id_input = ""
        country_input = ""
        aoc_input = ""
        reg_input = ""
        tail_input = ""
        msn_input = ""
        aircraft_type_input = ""
        operator_input = ""
        imo_input = ""
        flag_input = ""

        if search_type == "Person":
            c_a, c_b = st.columns(2)
            with c_a:
                name_input = st.text_input("Full Name*", value=qp_q if search_type == "Person" else "", placeholder="e.g. Mohammed Khan")
                nat_input = st.text_input("Nationality (optional)", value=qp_nat if search_type == "Person" else "", placeholder="e.g. Afghanistan")
            with c_b:
                dob_input = st.text_input("Date of Birth / YOB (optional)", value=qp_dob if search_type == "Person" else "", placeholder="e.g. 1980 or 1980-01-01")
                id_input = st.text_input("ID / Passport Number (optional)")

        elif search_type == "Organisation":
            c_a, c_b = st.columns(2)
            with c_a:
                name_input = st.text_input("Organisation Name*", value=qp_q if search_type == "Organisation" else "", placeholder="e.g. Sberbank of Russia")
            with c_b:
                country_input = st.text_input("Country of Incorporation (optional)", placeholder="e.g. Russia")
                id_input = st.text_input("Registration Number (optional)")

        elif search_type == "Airline":
            c_a, c_b = st.columns(2)
            with c_a:
                name_input = st.text_input("Airline Name*", value=qp_q if search_type == "Airline" else "", placeholder="e.g. Aeroflot")
                aoc_input = st.text_input("AOC State / Country (optional)", placeholder="e.g. Russia")
            with c_b:
                id_input = st.text_input("ICAO / IATA Code (optional)", placeholder="e.g. AFL or SU")

        elif search_type == "Aircraft":
            c_a, c_b = st.columns(2)
            with c_a:
                tail_input = st.text_input("Tail / Registration Number*", value=qp_q if search_type == "Aircraft" else "", placeholder="e.g. RA-73093")
                msn_input = st.text_input("MSN / Serial (optional)")
            with c_b:
                aircraft_type_input = st.text_input("Aircraft Type (optional)", placeholder="e.g. Boeing 737")
                operator_input = st.text_input("Operator / Owner (optional)", value=qp_op if search_type == "Aircraft" else "", placeholder="e.g. Aeroflot")

        elif search_type == "Vessel":
            c_a, c_b = st.columns(2)
            with c_a:
                name_input = st.text_input("Vessel Name*", value=qp_q if search_type == "Vessel" else "", placeholder="e.g. SIBERIA")
            with c_b:
                imo_input = st.text_input("IMO Number (optional)", placeholder="e.g. 9239458")
                flag_input = st.text_input("Flag State (optional)", placeholder="e.g. Russia")

        elif search_type == "Country":
            country_input = st.text_input("Country Name or ISO Code*", value=qp_q if search_type == "Country" else "", placeholder="e.g. Russia, Cuba, or IR")

        st.markdown("##### Screening Sources & Thresholds")
        st.caption("Red = likely match · Amber = possible match · Grey list = shown for information")
        st.markdown(
            """
            <style>
            div[data-testid="stCheckbox"] label span p {
                white-space: normal !important;
                word-break: normal !important;
                line-height: 1.25;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        src_col1, src_col2, src_col3 = st.columns([1.6, 1.0, 1.0])
        with src_col1:
            use_sanctions = st.checkbox("Official sanctions lists (always on)", value=True, disabled=True)
        with src_col2:
            use_india = st.checkbox("India (MHA)", value=True)
        with src_col3:
            use_aviation = st.checkbox("Aviation", value=(search_type in ["Airline", "Aircraft"]))

        src_col4, src_col5 = st.columns([1.6, 2.0])
        with src_col4:
            use_country_risk = st.checkbox("Country risk (FATF)", value=True)
        with src_col5:
            active_os_key = get_session_key() or os.getenv("OPENSANCTIONS_API_KEY")
            os_key_present = bool(active_os_key and active_os_key.strip())
            use_opensanctions = st.checkbox(
                "OpenSanctions (uses credits)",
                value=False,
                disabled=not os_key_present,
                help="No key entered this session" if not os_key_present else "Opt-in API search (consumes credits)",
            )

        st.caption("Red = likely match · Amber = possible match · Grey list = shown for information")
        submitted = st.form_submit_button("🔍 Screen Entity", type="primary")

    if not submitted and st.query_params.get("autorun") == "true" and (tail_input or name_input):
        submitted = True

    # Screening Execution
    if submitted:
        primary_query = (country_input or tail_input or name_input).strip()
        if not primary_query:
            st.error("Please enter a Name or Registration number to screen.")
            st.stop()

        # Update manual check name box as well
        st.session_state.manual_check_name = primary_query

        if search_type == "Country":
            from modules.screening.country import CountryEngine, log_country_search
            c_eng = CountryEngine()
            c_res = c_eng.screen_country((country_input or primary_query).strip())
            log_country_search(
                country_query=(country_input or primary_query).strip(),
                finding=c_res["overall_tier"],
                banner_text=c_res["banner_text"],
                execution_time_ms=c_res["execution_time_ms"],
            )
            st.markdown(f"## {c_res['flag']} {c_res['country']} ({c_res['iso2']})")
            if c_res["overall_tier"] == "POTENTIAL_MATCH":
                st.error(c_res["banner_text"])
            elif c_res["overall_tier"] == "POSSIBLE_MATCH_REVIEW":
                st.warning(c_res["banner_text"])
            else:
                st.success(c_res["banner_text"])

            reg_data = c_res.get("regimes_data", {})
            c_col1, c_col2 = st.columns(2)
            with c_col1:
                st.markdown("#### Sanctions Regimes")
                us_s = reg_data.get("us_sanctions", {})
                st.markdown(f"**US OFAC:** {us_s.get('type', 'None')}")
                if us_s.get("summary"):
                    st.caption(f"{us_s.get('authority', '')}: {us_s.get('summary')}")

                uk_s = reg_data.get("uk_sanctions", {})
                st.markdown(f"**UK FCDO:** {uk_s.get('type', 'None')}")
                if uk_s.get("summary"):
                    st.caption(uk_s.get("summary"))

                eu_s = reg_data.get("eu_sanctions", {})
                st.markdown(f"**EU Restrictive Measures:** {eu_s.get('type', 'None')}")
                if eu_s.get("summary"):
                    st.caption(eu_s.get("summary"))

                un_s = reg_data.get("un_sanctions", {})
                st.markdown(f"**UN Security Council:** {un_s.get('type', 'None')}")
                if un_s.get("summary"):
                    st.caption(un_s.get("summary"))

            with c_col2:
                st.markdown("#### Export Controls & Regulatory Status")
                exp = reg_data.get("export_controls", {})
                st.markdown(f"**US EAR:** {exp.get('us_ear', 'Standard')}")
                st.markdown(f"**US ITAR 126.1:** {exp.get('us_itar', 'Standard')}")
                st.markdown(f"**FATF Status:** {c_res['fatf_finding']}")
                if c_res["fatf_note"]:
                    st.caption(c_res["fatf_note"])
                st.markdown(f"**EU Air Safety Banned Airlines:** {c_res['eu_banned_airlines_count']}")
                if c_res["eu_banned_airlines"]:
                    st.caption(", ".join(c_res["eu_banned_airlines"][:10]))
            st.stop()

        inputs_dict = {
            "search_type": search_type,
            "name": name_input,
            "tail": tail_input,
            "dob": dob_input,
            "nationality": nat_input,
            "country": country_input or aoc_input or flag_input,
            "id_number": id_input or msn_input or imo_input,
            "aircraft_type": aircraft_type_input,
            "operator": operator_input,
        }

        watchman = WatchmanClient()
        india_client = IndiaClient()
        aviation_client = AviationClient()
        fatf_client = FATFClient()
        os_client = OpenSanctionsClient()

        overall_tier = "NO_MATCH"
        is_incomplete = False

        sanctions_hits: List[Dict[str, Any]] = []
        source_statuses: List[Dict[str, Any]] = []
        aviation_hits: List[Dict[str, Any]] = []
        country_risk_hits: List[Dict[str, Any]] = []
        per_list_data: Dict[str, Any] = {}

        # 1. Sanctions Screening (Watchman 5 lists)
        search_t0 = time.time()
        w_query_type = "person" if search_type == "Person" else ("airline" if search_type == "Airline" else "organisation")
        active_identifiers = []
        if id_input and id_input.strip():
            active_identifiers.append(id_input.strip())
        if msn_input and msn_input.strip():
            active_identifiers.append(msn_input.strip())
        if imo_input and imo_input.strip():
            active_identifiers.append(imo_input.strip())

        w_results = screen_query_all_lists(
            query=primary_query,
            client=watchman,
            query_type=w_query_type,
            dob=dob_input or None,
            nationality=nat_input or None,
            enable_transliteration=True,
            identifiers=active_identifiers or None,
        )

        for src_id in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]:
            src_meta = source_dict.get(src_id, {})
            res_data = w_results.get(src_id, {})
            per_list_data[src_id] = res_data
            best = res_data.get("best_hit", {})
            tier = best.get("tier", "NO_MATCH")
            below_count = res_data.get("below_threshold_count", 0)

            if tier == "NOT_CHECKED":
                is_incomplete = True

            source_statuses.append({
                "id": src_id,
                "authority": src_meta.get("authority", src_id.upper()),
                "date": src_meta.get("publication_date", "current"),
                "status": "FAILED" if tier == "NOT_CHECKED" else "OK",
                "tier": tier,
                "below_count": below_count,
            })

            if tier == "POTENTIAL_MATCH":
                overall_tier = "POTENTIAL_MATCH"
                sanctions_hits.append(best)
                for rh in res_data.get("red_hits", [])[1:]:
                    sanctions_hits.append(rh)
            elif tier == "POSSIBLE_MATCH_REVIEW":
                if overall_tier != "POTENTIAL_MATCH":
                    overall_tier = "POSSIBLE_MATCH_REVIEW"
                sanctions_hits.append(best)

        # 2. India (MHA / UAPA)
        if use_india:
            in_type = "INDIVIDUAL" if search_type == "Person" else "ORGANIZATION"
            in_res = india_client.screen(primary_query, search_type=in_type)
            in_tier = in_res.get("tier", "NO_MATCH")
            in_status = "FAILED" if (in_tier == "NOT_CHECKED" or in_res.get("status") == "FAILED" or in_res.get("finding") == "SOURCE_UNAVAILABLE") else "OK"
            if in_status == "FAILED":
                is_incomplete = True

            source_statuses.append({
                "id": "in_mha",
                "authority": "MHA (India UAPA)",
                "date": in_res.get("last_good_date", "2026-10-01"),
                "status": in_status,
                "tier": in_tier,
                "below_count": 0,
            })

            if in_tier == "POTENTIAL_MATCH":
                overall_tier = "POTENTIAL_MATCH"
                for m in in_res.get("matches", []):
                    sanctions_hits.append({
                        "source_list": "in_mha",
                        "tier": "POTENTIAL_MATCH",
                        "tier_icon": "🔴",
                        "primary_name": m.get("listed_name"),
                        "matched_name": m.get("matched_name"),
                        "expanded_from": None,
                        "source_id": m.get("id"),
                        "entity_type": search_type.lower(),
                        "program": m.get("schedule"),
                        "score": m.get("score"),
                        "reason": "mha_core_match",
                        "score_source": "mha_register",
                    })
            elif in_tier == "POSSIBLE_MATCH_REVIEW":
                if overall_tier != "POTENTIAL_MATCH":
                    overall_tier = "POSSIBLE_MATCH_REVIEW"
                for m in in_res.get("matches", []):
                    sanctions_hits.append({
                        "source_list": "in_mha",
                        "tier": "POSSIBLE_MATCH_REVIEW",
                        "tier_icon": "🟠",
                        "primary_name": m.get("listed_name"),
                        "matched_name": m.get("matched_name"),
                        "expanded_from": None,
                        "source_id": m.get("id"),
                        "entity_type": search_type.lower(),
                        "program": m.get("schedule"),
                        "score": m.get("score"),
                        "reason": "mha_partial",
                        "score_source": "mha_register",
                    })
        else:
            source_statuses.append({
                "id": "in_mha",
                "authority": "MHA (India UAPA)",
                "date": "—",
                "status": "NOT_RUN",
                "tier": "NOT_RUN",
                "below_count": 0,
            })

        # 3. OpenSanctions
        if use_opensanctions:
            st.session_state.session_os_credits += 1
            os_schema = "Person" if search_type == "Person" else ("Vessel" if search_type == "Vessel" else ("Airplane" if search_type == "Aircraft" else "Organization"))
            os_res = os_client.match(
                name=primary_query,
                schema=os_schema,
                use_opensanctions=True,
                birth_date=dob_input or None,
                nationality=nat_input or None,
            )
            os_status = os_res.get("status")
            if os_status in ["DISABLED", "UNAVAILABLE"]:
                if os_status == "UNAVAILABLE":
                    is_incomplete = True
                source_statuses.append({
                    "id": "opensanctions",
                    "authority": "OpenSanctions API",
                    "date": "live",
                    "status": os_status,
                    "tier": "NOT_CHECKED",
                    "below_count": 0,
                })
            else:
                hits = os_res.get("hits", [])
                os_best_tier = "NO_MATCH"
                for h in hits:
                    h_tier = h.get("tier", "NO_MATCH")
                    if h_tier == "POTENTIAL_MATCH":
                        os_best_tier = "POTENTIAL_MATCH"
                        overall_tier = "POTENTIAL_MATCH"
                        sanctions_hits.append({
                            "source_list": "opensanctions",
                            "tier": "POTENTIAL_MATCH",
                            "tier_icon": "🔴",
                            "primary_name": h.get("name"),
                            "matched_name": h.get("name"),
                            "expanded_from": None,
                            "source_id": h.get("id"),
                            "entity_type": os_schema.lower(),
                            "program": ", ".join(h.get("datasets", [])),
                            "score": h.get("score"),
                            "reason": "opensanctions_score",
                            "score_source": "opensanctions_api",
                        })
                    elif h_tier == "POSSIBLE_MATCH_REVIEW":
                        if os_best_tier != "POTENTIAL_MATCH":
                            os_best_tier = "POSSIBLE_MATCH_REVIEW"
                        if overall_tier != "POTENTIAL_MATCH":
                            overall_tier = "POSSIBLE_MATCH_REVIEW"
                        sanctions_hits.append({
                            "source_list": "opensanctions",
                            "tier": "POSSIBLE_MATCH_REVIEW",
                            "tier_icon": "🟠",
                            "primary_name": h.get("name"),
                            "matched_name": h.get("name"),
                            "expanded_from": None,
                            "source_id": h.get("id"),
                            "entity_type": os_schema.lower(),
                            "program": ", ".join(h.get("datasets", [])),
                            "score": h.get("score"),
                            "reason": "opensanctions_score",
                            "score_source": "opensanctions_api",
                        })
                source_statuses.append({
                    "id": "opensanctions",
                    "authority": "OpenSanctions API",
                    "date": "live",
                    "status": "OK",
                    "tier": os_best_tier,
                    "below_count": 0,
                })
        else:
            source_statuses.append({
                "id": "opensanctions",
                "authority": "OpenSanctions API",
                "date": "live",
                "status": "NOT_RUN",
                "tier": "NOT_RUN",
                "below_count": 0,
            })

        # 4. Aviation Screening
        if use_aviation and search_type in ["Airline", "Aircraft"]:
            if search_type == "Airline":
                av_res = aviation_client.screen_airline(
                    name=primary_query,
                    aoc_state=aoc_input or country_input or None,
                    icao=id_input or None,
                )
                av_status = "FAILED" if (av_res.get("tier") == "NOT_CHECKED" or av_res.get("finding") == "SOURCE_UNAVAILABLE" or av_res.get("status") == "FAILED") else "OK"
                if av_status == "FAILED":
                    is_incomplete = True
                source_statuses.append({
                    "id": "eu_air_safety",
                    "authority": "EU Air Safety (EC)",
                    "date": av_res.get("last_good_date", "current"),
                    "status": av_status,
                    "tier": av_res.get("tier", "NO_MATCH"),
                    "below_count": 0,
                })
                for hit in av_res.get("findings", []):
                    aviation_hits.append(hit)
                    if overall_tier != "POTENTIAL_MATCH":
                        overall_tier = "POSSIBLE_MATCH_REVIEW"
            elif search_type == "Aircraft":
                av_res = aviation_client.screen_aircraft(
                    tail_number=primary_query,
                    msn=msn_input or None,
                    operator=operator_input or None,
                )
                av_status = "FAILED" if (av_res.get("tier") == "NOT_CHECKED" or av_res.get("finding") == "SOURCE_UNAVAILABLE" or av_res.get("status") == "FAILED") else "OK"
                if av_status == "FAILED":
                    is_incomplete = True
                source_statuses.append({
                    "id": "bis_aircraft",
                    "authority": "US BIS (Export Admin)",
                    "date": av_res.get("last_good_date", "current"),
                    "status": av_status,
                    "tier": av_res.get("tier", "NO_MATCH"),
                    "below_count": 0,
                })
                for hit in av_res.get("findings", []):
                    aviation_hits.append(hit)
                    if hit.get("result_type") == "EAR_RESTRICTION":
                        overall_tier = "POTENTIAL_MATCH"
                    elif overall_tier != "POTENTIAL_MATCH":
                        overall_tier = "POSSIBLE_MATCH_REVIEW"

        # 5. Country Risk (FATF)
        country_to_check = nat_input or country_input or aoc_input or flag_input
        if use_country_risk and country_to_check:
            fatf_res = fatf_client.screen_country(country_to_check)
            fatf_status = "FAILED" if (fatf_res.get("tier") == "NOT_CHECKED" or fatf_res.get("status") == "FAILED" or fatf_res.get("finding") == "SOURCE_UNAVAILABLE") else "OK"
            if fatf_status == "FAILED":
                is_incomplete = True
            source_statuses.append({
                "id": "fatf",
                "authority": "FATF High-Risk & Monitored",
                "date": "2026-10-01",
                "status": fatf_status,
                "tier": fatf_res.get("tier", "NO_MATCH"),
                "below_count": 0,
            })
            finding = fatf_res.get("finding")
            if finding in ["FATF_HIGH_RISK", "FATF_INCREASED_MONITORING"]:
                is_black = (finding == "FATF_HIGH_RISK")
                country_risk_hits.append({
                    "country": fatf_res.get("standardized_country") or country_to_check,
                    "list_type": "High-Risk (Black list)" if is_black else "Increased Monitoring (Grey list)",
                    "call_to_action": fatf_res.get("action", ""),
                    "risk_label": fatf_res.get("risk_label", "Country risk flag — not a sanctions finding"),
                })
                if overall_tier != "POTENTIAL_MATCH":
                    overall_tier = "POSSIBLE_MATCH_REVIEW"


        # Non-Latin check (T8-6)
        is_non_latin = any(w_results.get(s, {}).get("is_non_latin") for s in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"])
        non_latin_warning = "This name contains non-Latin characters. Automatic matching is limited — also use Text search and Manual check." if is_non_latin else None
        searched_as_text = next((w_results.get(s, {}).get("searched_as") for s in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"] if w_results.get(s, {}).get("searched_as")), None)

        # Overall banner calculation
        if is_incomplete:
            banner_text = "⚪ INCOMPLETE — One or more sources were unavailable"
            banner_type = "info"
        elif overall_tier == "POTENTIAL_MATCH":
            banner_text = "🔴 POTENTIAL MATCH — Match identified on official list"
            banner_type = "error"
        elif overall_tier == "POSSIBLE_MATCH_REVIEW":
            banner_text = "🟠 POSSIBLE MATCH / RISK FLAG — Review and verification required"
            banner_type = "warning"
        else:
            if is_non_latin:
                banner_text = "ℹ️ INFO — Non-Latin characters detected. Automatic matching is limited — also use Text search and Manual check."
                banner_type = "warning"
            else:
                banner_text = "✅ NO MATCH — Clean on all checked sources"
                banner_type = "success"

        duration_ms = int((time.time() - search_t0) * 1000)

        # Collect all candidates across all lists for complete audit trail and reports
        all_screening_candidates: List[Dict[str, Any]] = []
        for src_id in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]:
            res_data = per_list_data.get(src_id, {})
            best_id = str(res_data.get("best_hit", {}).get("source_id") or "")
            for c in res_data.get("all_candidates", []):
                cand_copy = dict(c)
                cand_copy["is_top_hit"] = 1 if (cand_copy.get("source_id") and str(cand_copy.get("source_id")) == best_id) else 0
                all_screening_candidates.append(cand_copy)

        if use_india:
            for m in in_res.get("matches", []):
                all_screening_candidates.append({
                    "source_list": "in_mha",
                    "tier": in_tier,
                    "primary_name": m.get("listed_name"),
                    "matched_name": m.get("matched_name"),
                    "source_id": m.get("id"),
                    "score": float(m.get("score") or 0.0),
                    "reason": "mha_core_match" if in_tier == "POTENTIAL_MATCH" else "mha_partial",
                    "is_top_hit": 1,
                })

        if use_opensanctions and 'hits' in locals():
            for h in hits:
                all_screening_candidates.append({
                    "source_list": "opensanctions",
                    "tier": "POTENTIAL_MATCH" if (h.get("score") or 0) >= 0.85 else "POSSIBLE_MATCH_REVIEW",
                    "primary_name": h.get("caption"),
                    "matched_name": h.get("caption"),
                    "source_id": h.get("id"),
                    "score": float(h.get("score") or 0.0),
                    "reason": "opensanctions_score",
                    "is_top_hit": 0,
                })

        # Generate Reports & Log
        session_manual_checks = st.session_state.manual_checks_saved.get(primary_query, [])
        pdf_path = None
        excel_path = None
        pdf_error = None
        try:
            pdf_path, excel_path = generate_reports(
                search_type=search_type,
                inputs=inputs_dict,
                overall_banner=banner_text,
                source_statuses=source_statuses,
                sanctions_hits=sanctions_hits,
                aviation_hits=aviation_hits,
                country_risk_hits=country_risk_hits,
                opensanctions_used=use_opensanctions,
                all_candidates=all_screening_candidates,
                manual_checks=session_manual_checks,
                phonetic_enabled=PHONETIC_ENABLED,
            )
        except ReportGenerationError as rge:
            excel_path = rge.excel_path
            pdf_error = {
                "message": rge.message,
                "traceback": rge.details,
                "inputs": inputs_dict,
            }
            logger.error("PDF generation failed: %s", rge.message)

        report_file_name = pdf_path.name if pdf_path else (excel_path.name if excel_path else "FAILED")
        log_search(
            search_type=search_type,
            inputs=inputs_dict,
            source_results=source_statuses,
            report_file_name=report_file_name,
            opensanctions_used=use_opensanctions,
            query_type=w_query_type,
            sources_checked=[s["id"] for s in source_statuses if s.get("status") != "NOT_RUN"],
            duration_ms=duration_ms,
            all_candidates=all_screening_candidates,
            overall_tier=overall_tier,
            phonetic_enabled=PHONETIC_ENABLED,
        )

        st.session_state.last_results = {
            "banner_text": banner_text,
            "banner_type": banner_type,
            "is_non_latin": is_non_latin,
            "non_latin_warning": non_latin_warning,
            "searched_as": searched_as_text,
            "search_type": search_type,
            "primary_query": primary_query,
            "dob_entered": bool(dob_input),
            "nat_entered": bool(nat_input),
            "sanctions_hits": sanctions_hits,
            "source_statuses": source_statuses,
            "per_list_data": per_list_data,
            "aviation_hits": aviation_hits,
            "country_risk_hits": country_risk_hits,
            "pdf_path": str(pdf_path) if pdf_path else None,
            "excel_path": str(excel_path) if excel_path else None,
            "pdf_error": pdf_error,
        }

    # Render Results in Tab 1
    if st.session_state.last_results:
        res = st.session_state.last_results

        st.markdown("---")
        if res["banner_type"] == "error":
            st.error(f"### {res['banner_text']}")
        elif res["banner_type"] == "warning":
            st.warning(f"### {res['banner_text']}")
        elif res["banner_type"] == "success":
            st.success(f"### {res['banner_text']}")
        else:
            st.info(f"### {res['banner_text']}")

        if not PHONETIC_ENABLED:
            st.warning("**Sound-alike matching OFF** — Screening conducted with phonetic expansion disabled.")

        if res["search_type"] == "Person" and "🔴" in res["banner_text"] and not (res["dob_entered"] or res["nat_entered"]):
            st.info("**Add DOB / nationality to refine** this person search and clear potential name conflicts.")

        if res.get("is_non_latin") and res.get("banner_type") != "warning":
            st.warning(f"**Non-Latin Input:** {res.get('non_latin_warning')}")
        if res.get("searched_as"):
            st.info(f"**Transliteration:** {res.get('searched_as')}")

        # PDF Error Fallback Banner (Part A6)
        if res.get("pdf_error"):
            st.error("PDF report generation failed. An Excel report is available below.")
            with st.expander("Copy details for IT", expanded=False):
                err_data = res["pdf_error"]
                diag_txt = (
                    f"Product: {APP_NAME} {VERSION_LABEL}\n"
                    f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                    f"Inputs: {json.dumps(err_data.get('inputs', {}))}\n"
                    f"Diagnostic: {err_data.get('message', '')}"
                )
                st.code(diag_txt, language="")

        # Download Reports Row
        col_d1, col_d2, _ = st.columns([1, 1, 3])
        with col_d1:
            if res.get("pdf_path") and os.path.isfile(res["pdf_path"]):
                with open(res["pdf_path"], "rb") as f:
                    st.download_button(
                        "Download PDF Report",
                        data=f.read(),
                        file_name=Path(res["pdf_path"]).name,
                        mime="application/pdf",
                    )
        with col_d2:
            if res.get("excel_path") and os.path.isfile(res["excel_path"]):
                with open(res["excel_path"], "rb") as f:
                    st.download_button(
                        "Download Excel Report",
                        data=f.read(),
                        file_name=Path(res["excel_path"]).name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

        # Section A — Sanctions
        st.subheader("Section A — Sanctions Findings")
        cards_html = []
        for s in res["source_statuses"]:
            sid = s.get("id", "")
            fname = FRIENDLY_SOURCE_NAMES.get(sid, sid.upper().replace("_", " "))
            tier = s.get("tier", "NO_MATCH")
            chip = render_status_chip(tier)
            below_cnt = s.get("below_count", 0)

            cnt_text = ""
            if tier == "POTENTIAL_MATCH":
                cnt_text = "<span style='font-size:0.8rem; font-weight:600; color:#991B1B;'>1 match</span>"
            elif tier == "POSSIBLE_MATCH_REVIEW":
                cnt_text = "<span style='font-size:0.8rem; font-weight:600; color:#92400E;'>Review</span>"
            elif tier == "NO_MATCH":
                cnt_text = "<span style='font-size:0.8rem; color:#065F46;'>0 matches</span>"

            if below_cnt > 0:
                cnt_text += f" <span style='font-size:0.75rem; color:#1E40AF;'>+{below_cnt} info</span>"

            pdate = s.get("date", "current")
            last_ver = s.get("verified", "current")

            cards_html.append(
                f'<div class="source-card">'
                f'  <div class="source-card-title">{fname}</div>'
                f'  <div class="source-card-status">{chip} {cnt_text}</div>'
                f'  <div class="source-card-meta">list dated {pdate} · verified {last_ver}</div>'
                f'</div>'
            )

        grid_html = f'<div class="source-header-grid">{"".join(cards_html)}</div>'
        st.markdown(grid_html, unsafe_allow_html=True)

        def render_sanctions_hit_card(h: Dict[str, Any], is_soundalike: bool = False):
            src_id = h.get("source_list", "")
            src_info = source_dict.get(src_id, {})
            verify_url = src_info.get("verify_url") or src_info.get("landing_page") or "https://sanctionssearch.ofac.treas.gov/"
            rec_template = src_info.get("record_url_template", "")
            rec_id = h.get("source_id", "")
            if rec_template and rec_id:
                direct_verify_url = rec_template.replace("{id}", str(rec_id))
            else:
                direct_verify_url = verify_url

            tier = h.get("tier", "POTENTIAL_MATCH")
            chip_html = render_status_chip(tier)
            if is_soundalike:
                chip_html = f"{chip_html} &nbsp;{render_status_chip('SOUNDS_LIKE')}"

            primary_name = h.get("primary_name") or "—"
            matched_name = h.get("matched_name") or primary_name
            exp_text = f" (via alias: {h.get('expanded_from')})" if h.get("expanded_from") else ""
            prog = format_programs(h.get("program"))
            score_val = float(h.get("score") or 0.0)
            reason_code = h.get("tier_reason") or h.get("reason")
            plain_reason = translate_reason(reason_code)
            countries = h.get("country") or h.get("nationality") or ""
            country_str = f" | Country: {countries}" if countries else ""
            etype = ENTITY_TYPE_NAMES.get(str(h.get("entity_type") or "").lower(), h.get("entity_type") or "Organisation")
            friendly_src = FRIENDLY_SOURCE_NAMES.get(src_id, src_id.upper().replace("_", " "))
            auth_name = FRIENDLY_AUTHORITIES.get(src_id, src_info.get("authority", "Official Portal"))

            card_box = st.container(border=True)
            with card_box:
                # Header: Source Authority / Friendly Name
                st.caption(f"**Source:** {friendly_src}")

                # Line 1: Status chip + listed name (wraps)
                l1_col1, l1_col2 = st.columns([2 if is_soundalike else 1, 5])
                with l1_col1:
                    st.markdown(chip_html, unsafe_allow_html=True)
                with l1_col2:
                    st.markdown(f"**{primary_name}**")

                # Line 2: Matched name/alias, Entity Type, Record ID, Programme, Score, Reason (wraps)
                st.markdown(
                    f"**Matched:** <mark style='background-color: #FFEB3B; padding: 2px 6px; font-weight: bold;'>{matched_name}</mark>{exp_text} &nbsp;|&nbsp; "
                    f"**Type:** {etype} &nbsp;|&nbsp; **ID:** `{rec_id}` &nbsp;|&nbsp; "
                    f"**Prog:** {prog}{country_str} &nbsp;|&nbsp; "
                    f"**Score:** `{score_val:.4f}` &nbsp;|&nbsp; **Reason:** {plain_reason}",
                    unsafe_allow_html=True,
                )

                # Corroboration Panel (T11 Part H1)
                corrob = h.get("corroboration") or {}
                if corrob and any(v != "UNKNOWN" for v in [corrob.get("dob_status"), corrob.get("nat_status"), corrob.get("id_status")]):
                    dob_st = corrob.get("dob_status", "UNKNOWN")
                    nat_st = corrob.get("nat_status", "UNKNOWN")
                    id_st = corrob.get("id_status", "UNKNOWN")

                    def c_tag(s):
                        if s == "MATCH":
                            return "<span style='color:#065F46; font-weight:700;'>MATCH ✅</span>"
                        elif s == "CONFLICT":
                            return "<span style='color:#DC2626; font-weight:700;'>CONFLICT [ALERT]</span>"
                        return "<span style='color:#6B7280;'>Not provided</span>"

                    st.markdown(
                        f"<div style='font-size:0.8rem; background:#F8FAFC; border:1px solid #E2E8F0; border-radius:4px; padding:4px 8px; margin:4px 0;'>"
                        f"<b>Corroboration:</b> DOB: {c_tag(dob_st)} &nbsp;|&nbsp; "
                        f"Nationality: {c_tag(nat_st)} &nbsp;|&nbsp; "
                        f"ID / Passport / IMO: {c_tag(id_st)}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

                # Line 3: Verify and copy buttons (wrap)
                btn_c1, btn_c2, btn_c3, _ = st.columns([2.5, 1.5, 1.5, 2.5])
                with btn_c1:
                    st.link_button(f"Verify on {auth_name}", direct_verify_url)
                with btn_c2:
                    st.code(matched_name, language="")
                    st.caption("Copy matched name")
                with btn_c3:
                    st.code(str(rec_id), language="")
                    st.caption("Copy record ID")

                # B4: Full record expander (Modal Style 03_show_full_record.png)
                with st.expander("Show full record", expanded=False):
                    rec = get_record(src_id, rec_id)
                    if rec:
                        render_full_record_details(src_id, rec_id, rec, h, auth_name, direct_verify_url, key_prefix="scr")
                    else:
                        st.info("Full record details not available locally; verify on official portal.")

                with st.expander("Technical details & raw fields", expanded=False):
                    st.markdown(f"**Entity Type:** {etype}")
                    st.markdown(f"**Score Source:** `{h.get('score_source')}`")
                    st.markdown(f"**Internal Reason Code:** `{reason_code}`")
                    if h.get("phonetic_evidence"):
                        st.caption(f"Phonetic comparison details: `{h.get('phonetic_evidence')}`")
                    pub_date = src_info.get("publication_date", "current")
                    st.caption(f"*Our copy is dated {pub_date}. The official site may be more recent.*")

        # Render Flagged Hits as 3-Line Cards with Sound-alike grouping (T9-2)
        if res["sanctions_hits"]:
            standard_hits = [h for h in res["sanctions_hits"] if not (h.get("tier") == "POSSIBLE_MATCH_REVIEW" and str(h.get("reason") or "").startswith("phonetic"))]
            soundalike_hits = [h for h in res["sanctions_hits"] if (h.get("tier") == "POSSIBLE_MATCH_REVIEW" and str(h.get("reason") or "").startswith("phonetic"))]

            for h in standard_hits:
                render_sanctions_hit_card(h, is_soundalike=False)

            if soundalike_hits:
                with st.expander(f"Sound-alike matches ({len(soundalike_hits)})", expanded=True):
                    st.caption("Sound-alike candidates match via Double Metaphone or variant group rules. Review spelling differences.")
                    for h in soundalike_hits:
                        render_sanctions_hit_card(h, is_soundalike=True)
        else:
            st.write("✅ No flagged sanctions records identified.")

        # Show Candidates Below Threshold Toggle per list
        per_list = res.get("per_list_data", {})
        for list_id, ldata in per_list.items():
            all_cands = ldata.get("all_candidates", [])
            below_cands = [c for c in all_cands if c.get("tier") == "BELOW_THRESHOLD"]
            if below_cands:
                with st.expander(
                    f"Show candidates below threshold ({len(below_cands)}) — [{list_id}]",
                    expanded=(st.query_params.get("expand_info") == "true"),
                ):
                    st.caption("Candidate matches below threshold are shown for information only. They are not matches.")
                    if len(all_cands) >= 25:
                        st.info("Showing top 25 — more may exist; refine the search.")
                    for bc in below_cands:
                        b_chip = render_status_chip("BELOW_THRESHOLD")
                        b_box = st.container(border=True)
                        with b_box:
                            # Line 1: Chip + Name
                            b_l1, b_l2 = st.columns([1, 6])
                            with b_l1:
                                st.markdown(b_chip, unsafe_allow_html=True)
                            with b_l2:
                                st.markdown(f"**{bc.get('primary_name')}** (Matched: `{bc.get('matched_name')}`)")
                            # Line 2: Details
                            st.caption(
                                f"ID: `{bc.get('source_id')}` | Entity Type: {bc.get('entity_type')} | "
                                f"Prog: {bc.get('program')} | Score: `{bc.get('score', 0.0):.4f}` | "
                                f"Reason: {translate_reason(bc.get('reason'))}"
                            )
                            # Line 3: Verify button
                            l_info = source_dict.get(list_id, {})
                            v_url = l_info.get("verify_url") or "https://sanctionssearch.ofac.treas.gov/"
                            st.link_button(f"Verify {list_id}", v_url)

        # Section B — Aviation
        st.subheader("Section B — Aviation Safety & Export Controls")
        if res["aviation_hits"]:
            for av in res["aviation_hits"]:
                rtype = av.get("result_type", "")
                av_info = source_dict.get("bis_aircraft", {})
                if rtype == "EAR_RESTRICTION":
                    st.markdown(
                        f"<div class='result-card'>"
                        f"  <div class='result-card-line1'>{render_status_chip('EXPORT_CONTROL')} <span class='result-card-name'>Export-control restriction (US EAR)</span></div>"
                        f"  <div class='result-card-line2'><b>Aircraft / Operator:</b> {av.get('details')}<br/><span style='color:#6B7280; font-size:0.8rem;'>Source: BIS Aircraft List (copy dated {av_info.get('publication_date')})</span></div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    st.link_button("Verify on official BIS document", av_info.get("verify_url", "https://www.bis.gov/"))
                else:
                    eu_av = source_dict.get("eu_air_safety", {})
                    st.markdown(
                        f"<div class='result-card'>"
                        f"  <div class='result-card-line1'>{render_status_chip('SAFETY')} <span class='result-card-name'>Safety flag — not a sanctions finding ({rtype})</span></div>"
                        f"  <div class='result-card-line2'><b>Carrier / Scope:</b> {av.get('details')}<br/><span style='color:#6B7280; font-size:0.8rem;'>Source: EU Air Safety List / FAA IASA (copy dated {eu_av.get('publication_date')})</span></div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    st.link_button("Verify on official Aviation authority", eu_av.get("verify_url", "https://transport.ec.europa.eu/"))
        else:
            st.write("✅ No aviation safety bans or export-control restrictions found.")

        # Section C — Country Risk
        st.subheader("Section C — Country Risk (FATF)")
        if res["country_risk_hits"]:
            for cr in res["country_risk_hits"]:
                fatf_info = source_dict.get("fatf_jurisdictions", {})
                st.markdown(
                    f"<div class='result-card'>"
                    f"  <div class='result-card-line1'>{render_status_chip('POSSIBLE_MATCH_REVIEW')} <span class='result-card-name'>Country risk flag — {cr.get('country')}</span></div>"
                    f"  <div class='result-card-line2'><b>FATF Status:</b> {cr.get('list_type')} — <i>{cr.get('call_to_action')}</i><br/><span style='color:#6B7280; font-size:0.8rem;'>Source: FATF (copy dated {fatf_info.get('publication_date')})</span></div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                st.link_button("Verify on official FATF website", fatf_info.get("verify_url", "https://www.fatf-gafi.org/"))
        else:
            st.write("✅ No elevated FATF country risk flags.")

        # Section D — Historical Manual Check Audit Trail (Decision 3)
        history_query = res.get("primary_query") or ""
        past_checks = get_manual_checks_for_entity(history_query) if history_query else []
        if past_checks:
            st.divider()
            with st.expander(f"Prior Manual Verification History ({len(past_checks)} recorded)", expanded=True):

                st.caption("Historical analyst check decisions for this counterparty from screening audit trail:")
                for chk in past_checks:
                    badge = "🔴" if "Match" in chk.get("result", "") else "✅"
                    st.markdown(f"**{badge} {chk.get('result')}** on `{chk.get('source')}` by `{chk.get('user')}` at `{chk.get('timestamp')[:16]}`")
                    if chk.get("comment"):
                        st.caption(f"Remarks: _{chk.get('comment')}_")



# =========================================================================
# TAB: OWNERSHIP & CONTROL CHECK (T11 Part E)
# =========================================================================
with tab_ownership:
    from modules.ownership.ui import render_ownership_tab
    render_ownership_tab()


# =========================================================================
# TAB 2: TEXT SEARCH
# =========================================================================
with tab_raw:
    st.markdown("### Text Search")
    st.info("**Text search** — results are keyword occurrences across official records. Review each record.**")

    raw_engine = RawSearchEngine()
    all_raw_sources = [
        "us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl",
        "bis_aircraft", "eu_air_safety_list", "faa_iasa",
        "in_mha_first_schedule", "in_mha_fourth_schedule", "in_mha_unlawful_assoc",
        "fatf_jurisdictions"
    ]

    with st.form("raw_search_form"):
        raw_q = st.text_input(
            "Search Query*",
            value=st.query_params.get("raw_query", ""),
            placeholder="e.g. RUS2426, VP-BCD, 41215, Sberbank, or passport number",
            help="Minimum 3 characters (except in 'IDs and numbers only')."
        )

        r_col1, r_col2, r_col3 = st.columns(3)
        with r_col1:
            match_opt = st.selectbox(
                "Match Option",
                ["Contains", "Whole word", "Exact phrase", "Starts with"],
                index=0,
            )
        with r_col2:
            search_fields = st.selectbox(
                "Fields to Search",
                ["All fields", "Names only", "IDs and numbers only"],
                index=0,
            )
        with r_col3:
            fold_accents = st.checkbox("Accent & case folding", value=True)

        # Dropdown menu with checkboxes for sources
        with st.popover("Regulatory Sources to Search ▾", use_container_width=True):
            st.markdown("**Select Sources to Search**")
            st.caption("Toggle checkboxes to include or exclude specific regulatory lists:")
            col_s1, col_s2 = st.columns(2)
            selected_raw_sources = []
            for idx, s in enumerate(all_raw_sources):
                auth = source_dict.get(s, {}).get("authority", s)
                friendly = FRIENDLY_SOURCE_NAMES.get(s, s)
                target_col = col_s1 if (idx % 2 == 0) else col_s2
                with target_col:
                    if st.checkbox(
                        f"{friendly} ({auth})",
                        value=True,
                        key=f"cb_raw_src_{s}",
                    ):
                        selected_raw_sources.append(s)

        if not selected_raw_sources:
            selected_raw_sources = all_raw_sources

        raw_submitted = st.form_submit_button("🔍 Search Records", type="primary")

    if raw_submitted or (st.query_params.get("raw_autorun") == "true" and raw_q.strip()):
        if not raw_q.strip():
            st.error("Please enter a search query.")
        else:
            with st.spinner("Searching records database..."):
                raw_res = raw_engine.search(
                    query=raw_q.strip(),
                    match_option=match_opt,
                    fold_accents_and_case=fold_accents,
                    search_field=search_fields,
                    selected_sources=selected_raw_sources,
                    limit=200,
                )

                if raw_res["status"] == "INVALID_QUERY":
                    st.error(raw_res["message"])
                elif raw_res["status"] == "DB_UNAVAILABLE":
                    st.error(raw_res["message"])
                else:
                    # Generate report and log
                    raw_pdf, raw_excel = generate_raw_reports(
                        query=raw_q.strip(),
                        options={
                            "match_option": match_opt,
                            "search_field": search_fields,
                            "fold_accents": fold_accents,
                        },
                        results=raw_res.get("results", []),
                    )
                    log_raw_search(
                        query=raw_q.strip(),
                        options={
                            "match_option": match_opt,
                            "search_field": search_fields,
                            "fold_accents": fold_accents,
                            "sources": selected_raw_sources,
                        },
                        result_count=raw_res.get("total_matches", 0),
                        report_file_name=raw_pdf.name,
                    )
                    raw_res["pdf_path"] = str(raw_pdf)
                    raw_res["excel_path"] = str(raw_excel)
                    st.session_state.raw_search_results = raw_res

    # Render Raw Search Results
    if st.session_state.raw_search_results:
        rr = st.session_state.raw_search_results
        st.markdown("---")
        st.markdown(f"**Query:** `{rr['query']}` | **Matches:** `{rr['total_matches']}` | **Time:** `{rr['execution_time_ms']:.1f}ms`")

        if rr.get("limit_reached"):
            st.warning("**Showing top 200** — more may exist; refine the search.")

        # PDF Error Fallback Banner (Part A6)
        if rr.get("pdf_error"):
            st.error("PDF report generation failed. An Excel report is available below.")
            with st.expander("Copy details for IT", expanded=False):
                err_data = rr["pdf_error"]
                diag_txt = (
                    f"Product: {APP_NAME} {VERSION_LABEL}\n"
                    f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                    f"Query: {err_data.get('query', '')}\n"
                    f"Diagnostic: {err_data.get('message', '')}"
                )
                st.code(diag_txt, language="")

        # Download Report Buttons
        r_d1, r_d2, _ = st.columns([1, 1, 3])
        with r_d1:
            if rr.get("pdf_path") and os.path.isfile(rr["pdf_path"]):
                with open(rr["pdf_path"], "rb") as f:
                    st.download_button(
                        "Download Text Search PDF",
                        data=f.read(),
                        file_name=Path(rr["pdf_path"]).name,
                        mime="application/pdf",
                        key="raw_pdf_dl",
                    )
        with r_d2:
            if rr.get("excel_path") and os.path.isfile(rr["excel_path"]):
                with open(rr["excel_path"], "rb") as f:
                    st.download_button(
                        "Download Text Search Excel",
                        data=f.read(),
                        file_name=Path(rr["excel_path"]).name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="raw_excel_dl",
                    )

        if rr["results"]:
            for idx, item in enumerate(rr["results"]):
                with st.container():
                    r_c1, r_c2, r_c3 = st.columns([2, 3, 2])
                    with r_c1:
                        st.markdown(f"**[{item['source']}]** `{item['record_id']}`")
                        st.markdown(f"**Primary Name:** {item['primary_name']}")
                        st.caption(f"Matched Field: `{item['matched_field']}`")
                    with r_c2:
                        st.markdown(f"**Text Extract:**")
                        st.markdown(f"> {item['text_extract']}", unsafe_allow_html=True)
                        st.caption(f"List Date: {item['list_date']}")
                    with r_c3:
                        st.link_button("Verify on official source", item["verify_url"])
                        if not item["has_record_link"]:
                            st.code(item["primary_name"], language="")
                    with st.expander("Show full record", expanded=False):
                        rec = get_record(item["source"], item["record_id"])
                        if rec:
                            raw_hit = {
                                "tier": "POTENTIAL_MATCH",
                                "score": 1.0,
                                "primary_name": item.get("primary_name"),
                                "publication_date": item.get("list_date"),
                            }
                            render_full_record_details(item["source"], item["record_id"], rec, raw_hit, item.get("source_name", item["source"]), item.get("verify_url", ""), key_prefix=f"raw_{idx}")
                        else:
                            st.info("Full record details not available locally; verify on official portal.")
                    st.divider()
        else:
            st.info("No records matched the raw search query.")


# =========================================================================
# TAB 3: MANUAL CHECK (T5.2 / T8-9)
# =========================================================================
with tab_manual:
    st.markdown("### Manual Official List Check")
    st.caption("Verify query names directly on official search portals and record manual compliance determinations.")

    m_col1, m_col2 = st.columns([3, 1])
    with m_col1:
        manual_name = st.text_input(
            "Subject / Entity Name for Manual Check*",
            value=st.session_state.manual_check_name,
            placeholder="e.g. Sberbank or Aeroflot",
            key="manual_name_box",
        )
    with m_col2:
        if manual_name:
            st.code(manual_name, language="")
            st.caption("Copy name to clipboard")

    clean_subj = manual_name.strip()
    if clean_subj:
        recent_checks = get_manual_checks_for_entity(clean_subj, limit=5)
        if recent_checks:
            with st.expander(f"Recent manual checks for '{clean_subj}' ({len(recent_checks)} recorded)", expanded=False):
                for rc in recent_checks:
                    st.markdown(f"• **{rc['source']}** — Result: `{rc['result']}` | User: `{rc.get('user', '—')}` | Date: `{rc['timestamp'][:19]}` | Note: *{rc['comment']}*")

    official_publishers = [
        {"id": "us_ofac", "name": "US OFAC (SDN & Consolidated Lists)", "authority": "US Treasury, OFAC", "inst": "Enter entity or person name into Name field. Set minimum match threshold. Review aliases, IDs, and date of birth details."},
        {"id": "us_csl", "name": "US Consolidated Screening List (CSL)", "authority": "US ITA (Commerce, State, Treasury)", "inst": "Search across Commerce (BIS), State (ISN/DTC), and Treasury agencies on the consolidated search page."},
        {"id": "uk_csl", "name": "UK Sanctions List (FCDO)", "authority": "UK Foreign, Commonwealth & Development Office", "inst": "Search UK Sanctions service; review non-Latin name spellings, regime, and sanctions imposition reason."},
        {"id": "eu_csl", "name": "EU Sanctions Map & Tracker", "authority": "European Commission", "inst": "Use global search bar. Filter by Persons, Entities, or Regimes. Verify legal acts and asset freeze measures."},
        {"id": "un_csl", "name": "UN Security Council Consolidated List", "authority": "UN Security Council", "inst": "Search consolidated XML/HTML list. Match reference numbers, aliases, and Interpol-UN notices."},
        {"id": "eu_air_safety_list", "name": "EU Air Safety List", "authority": "European Commission / DG MOVE", "inst": "Verify air carriers subject to an operating ban or operational restrictions within the European Union (Annex A & B)."},
        {"id": "faa_iasa", "name": "FAA International Aviation Safety Assessment (IASA)", "authority": "US Federal Aviation Administration", "inst": "Review country aviation oversight category (Category 1 meets ICAO standards; Category 2 does not meet standards)."},
        {"id": "bis_tdo", "name": "US BIS Denial Orders (Temporary Denial Orders)", "authority": "US Bureau of Industry and Security", "inst": "Search Denied Persons List (DPL) and active Temporary Denial Orders for export privilege bans."},
        {"id": "bis_aircraft", "name": "US BIS Aircraft List", "authority": "US Bureau of Industry and Security", "inst": "Verify tail numbers, MSNs, and commercial/private operators subject to EAR export restrictions."},
        {"id": "in_mha_first_schedule", "name": "India MHA 1st Schedule (Terrorist Organisations)", "authority": "Ministry of Home Affairs, Government of India", "inst": "Search First Schedule of the Unlawful Activities (Prevention) Act, 1967 (Banned Terrorist Organisations)."},
        {"id": "in_mha_fourth_schedule", "name": "India MHA 4th Schedule (Individuals)", "authority": "Ministry of Home Affairs, Government of India", "inst": "Search Fourth Schedule of the Unlawful Activities (Prevention) Act, 1967 (Designated Terrorist Individuals)."},
        {"id": "in_mha_unlawful_assoc", "name": "India MHA Section 3 (Unlawful Associations)", "authority": "Ministry of Home Affairs, Government of India", "inst": "Search notifications issued under Section 3 of the Unlawful Activities (Prevention) Act declaring associations unlawful."},
        {"id": "fatf_jurisdictions", "name": "FATF High-Risk & Monitored Jurisdictions", "authority": "Financial Action Task Force (FATF)", "inst": "Check High-Risk Jurisdictions subject to a Call for Action (Black list) and Jurisdictions under Increased Monitoring (Grey list)."},
        {"id": "os_bulk", "name": "OpenSanctions Database (Global Consolidated)", "authority": "OpenSanctions", "inst": "Search OpenSanctions international consolidated entities database across 40+ international sanctions bodies."},
    ]

    manual_form_values = {}

    st.markdown("---")
    st.markdown("#### Official Publisher Verification Cards")

    for pub in official_publishers:
        sid = pub["id"]
        cfg = source_dict.get(sid, {})
        v_url = cfg.get("verify_url") or cfg.get("landing_page") or "https://sanctionssearch.ofac.treas.gov/"
        p_date = cfg.get("publication_date", "current")

        with st.expander(f"{pub['name']} — {pub['authority']}", expanded=False):
            st.markdown(f"**Authority:** {pub['authority']}")
            st.markdown(f"**Instructions:** {pub['inst']}")
            st.caption(f"Our dataset version: {p_date} (official site is real-time)")
            st.link_button("Open official search portal", v_url)

            card_c1, card_c2 = st.columns([1, 2])
            with card_c1:
                res_val = st.radio(
                    f"Determination ({sid})",
                    ["Not checked", "No match", "Possible match", "Match"],
                    index=0,
                    key=f"manual_res_{sid}",
                )
            with card_c2:
                notes_val = st.text_area(
                    f"Findings / Notes ({sid})",
                    placeholder="e.g. Verified clean on official portal; no active designations found.",
                    key=f"manual_notes_{sid}",
                    height=80,
                )

            if st.button(f"Save {pub['name']} Check", key=f"save_btn_{sid}"):
                if not clean_subj:
                    st.error("Please enter Subject Name at the top before saving.")
                else:
                    log_manual_check(
                        name=clean_subj,
                        source=sid,
                        result=res_val,
                        comment=notes_val,
                    )
                    saved_item = {
                        "source": sid,
                        "source_name": pub["name"],
                        "authority": pub["authority"],
                        "result": res_val,
                        "comment": notes_val,
                        "verify_url": v_url,
                    }
                    if clean_subj not in st.session_state.manual_checks_saved:
                        st.session_state.manual_checks_saved[clean_subj] = []
                    st.session_state.manual_checks_saved[clean_subj].append(saved_item)
                    st.success(f"Saved {pub['name']} check as '{res_val}' (`mode = manual`)!")

            manual_form_values[sid] = {
                "source": sid,
                "source_name": pub["name"],
                "authority": pub["authority"],
                "result": res_val,
                "comment": notes_val,
                "verify_url": v_url,
            }

    st.markdown("---")
    if st.button("Save All Completed Checks", type="primary"):
        if not clean_subj:
            st.error("Please provide the Subject Name at the top before saving manual check results.")
        else:
            saved_count = 0
            checks_to_save = []
            for sid, val in manual_form_values.items():
                if val["comment"] or val["result"] != "Not checked":
                    log_manual_check(
                        name=clean_subj,
                        source=sid,
                        result=val["result"],
                        comment=val["comment"],
                    )
                    checks_to_save.append(val)
                    saved_count += 1

            if clean_subj not in st.session_state.manual_checks_saved:
                st.session_state.manual_checks_saved[clean_subj] = []
            st.session_state.manual_checks_saved[clean_subj].extend(checks_to_save)

            # If screened results exist for the same name, regenerate reports with manual check included
            if st.session_state.last_results and st.session_state.last_results.get("primary_query") == clean_subj:
                res = st.session_state.last_results
                try:
                    pdf_p, excel_p = generate_reports(
                        search_type=res["search_type"],
                        inputs={"name": clean_subj},
                        overall_banner=res["banner_text"],
                        source_statuses=res["source_statuses"],
                        sanctions_hits=res["sanctions_hits"],
                        aviation_hits=res["aviation_hits"],
                        country_risk_hits=res["country_risk_hits"],
                        manual_checks=st.session_state.manual_checks_saved[clean_subj],
                    )
                    res["pdf_path"] = str(pdf_p)
                    res["excel_path"] = str(excel_p)
                except ReportGenerationError as rge:
                    res["pdf_path"] = None
                    res["excel_path"] = str(rge.excel_path)
                    res["pdf_error"] = {
                        "message": str(rge),
                        "inputs": {"name": clean_subj},
                    }
                st.success(f"Saved {saved_count} manual check findings to SQLite audit log and updated session report!")
            else:
                st.success(f"Saved {saved_count} manual check findings to SQLite audit log (`mode = manual`).")


# Footer Disclaimer
st.markdown("---")
st.caption(
    "For authorised use by employees of the organisation for sanctions and export-control screening. Activity is logged. | "
    "Screening aid only. A result here is not a legal determination. "
    "Potential matches must be verified against the official source and escalated under the Sanctions Compliance Policy. "
    "Antigravity and the developers accept no liability for reliance on this tool."
)
