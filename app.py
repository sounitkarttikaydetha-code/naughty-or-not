"""
Naughty or not — Sanction checK
Streamlit User Interface (T5, T5.1, T5.2).
"""

import getpass
import os
import platform
import sys
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
from modules.reporting.generator import generate_reports, generate_raw_reports
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
from modules.opensanctions.key_manager import (
    get_remembered_key,
    set_session_key,
    get_session_key,
    clear_remembered_key,
    mask_key,
)

is_app_test = ("streamlit.testing" in sys.modules) or (os.environ.get("PYTEST_CURRENT_TEST") is not None)

# Session state initialization
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

st.set_page_config(
    page_title="Naughty or not",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 1. Permanent Notice Banner
st.warning(
    "⚠️ **TEST VERSION** — for internal evaluation only. "
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
        > **TEST VERSION — for internal evaluation only.**
        > OpenSanctions data is licensed CC BY-NC 4.0; commercial use requires a licence from OpenSanctions.
        > Not to be relied upon for transaction decisions.
        >
        > **Important:** Results must be verified on the official source and escalated under the Sanctions Compliance Policy.
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


source_reg = load_sources_registry()
source_dict = {s["id"]: s for s in source_reg.get("sources", [])}

FRIENDLY_SOURCE_NAMES = {
    "us_ofac": "US Treasury (OFAC)",
    "us_csl": "US Consolidated Screening List",
    "uk_csl": "UK Sanctions List (FCDO)",
    "eu_csl": "EU Financial Sanctions",
    "un_csl": "UN Security Council Sanctions",
    "bis_aircraft": "BIS Identified Aircraft",
    "bis_tdo": "BIS Denial Orders",
    "eu_air_safety": "EU Air Safety List",
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
    st.caption(f"Naughty or not v{APP_VERSION}")

    # OpenSanctions Status
    active_key = get_session_key()
    masked = mask_key(active_key)
    total_os_credits = get_total_opensanctions_credits()
    st.metric(
        label="OpenSanctions Credits",
        value=f"{st.session_state.session_os_credits} session",
        delta=f"{total_os_credits} total logged",
    )
    if active_key:
        st.caption(f"Active Key: `{masked}`")
    else:
        st.caption("Active Key: _None (Free sources only)_")

    if st.button("🔑 Change / clear key"):
        st.session_state.os_key_dialog_done = False
        st.rerun()

    st.divider()

    st.subheader("Source Freshness")
    for s in source_reg.get("sources", []):
        sid = s.get("id")
        fname = FRIENDLY_SOURCE_NAMES.get(sid, sid)
        auth = s.get("authority")
        pdate = s.get("publication_date", "—")
        status = s.get("status", "OK")
        badge = "🟢" if status == "OK" else ("🟠" if status == "STALE" else ("⚪" if status in ["UNAVAILABLE", "NOT_CHECKED", "MISSING"] else "🔴"))
        with st.expander(f"{badge} {fname}", expanded=False):
            st.caption(f"**ID:** `{sid}`\n\n**Authority:** {auth}\n\n**Publication:** {pdate}\n\n**Status:** {status}")

    if st.button("🔄 Update lists"):
        with st.spinner("Updating sources..."):
            try:
                from modules.aviation.parser import check_and_refresh_sources
                check_and_refresh_sources(force=True)
                from modules.raw_search.indexer import build_full_raw_index
                build_full_raw_index()
                st.success("Successfully updated all source lists!")
            except Exception as e:
                list_date = get_lists_date()
                st.warning(f"Lists could not be updated ({e}). Using copies dated {list_date}.")

    st.divider()
    st.subheader("Data & Support")
    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        if st.button("📁 Reports"):
            if sys.platform == "win32":
                os.startfile(str(get_reports_dir()))
    with c_btn2:
        if st.button("📁 Logs"):
            if sys.platform == "win32":
                os.startfile(str(get_logs_dir()))

    ug_pdf = PROJECT_ROOT / "USER_GUIDE.pdf"
    if ug_pdf.is_file():
        if st.button("📖 User Guide (PDF)"):
            if sys.platform == "win32":
                os.startfile(str(ug_pdf))

    with st.expander("About Naughty or not"):
        st.markdown(
            f"**Naughty or not** v{APP_VERSION}\n\n"
            "Self-contained desktop sanctions and compliance screening engine.\n\n"
            "• Zero background services\n"
            "• Local in-process evaluation\n"
            "• 10-year immutable audit logging\n"
            "• No query leakage to external servers"
        )


# Main Screen Header
st.title("Sanction checK")
st.caption("Naughty or not — Desktop Sanctions & Aviation Compliance Screening | Version 1.0.0")

# Mode Tabs: Name check | Text search | Manual check
is_raw_tab = (st.query_params.get("tab") == "raw")
is_manual_tab = (st.query_params.get("tab") == "manual")

if is_raw_tab:
    tab_raw, tab_screened, tab_manual = st.tabs(["📄 Text search", "🔍 Name check", "📋 Manual check"])
elif is_manual_tab:
    tab_manual, tab_screened, tab_raw = st.tabs(["📋 Manual check", "🔍 Name check", "📄 Text search"])
else:
    tab_screened, tab_raw, tab_manual = st.tabs(["🔍 Name check", "📄 Text search", "📋 Manual check"])


# =========================================================================
# TAB 1: SCREENED SEARCH
# =========================================================================
with tab_screened:
    qp_type = st.query_params.get("search_type")
    type_options = ["Person", "Organisation", "Airline", "Aircraft", "Vessel"]
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
        primary_query = (tail_input or name_input).strip()
        if not primary_query:
            st.error("Please enter a Name or Registration number to screen.")
            st.stop()

        # Update manual check name box as well
        st.session_state.manual_check_name = primary_query

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
        w_query_type = "person" if search_type == "Person" else ("airline" if search_type == "Airline" else "organisation")
        w_results = screen_query_all_lists(
            query=primary_query,
            client=watchman,
            query_type=w_query_type,
            dob=dob_input or None,
            nationality=nat_input or None,
            enable_transliteration=True,
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
            banner_text = "⚠️ POSSIBLE MATCH / RISK FLAG — Review and verification required"
            banner_type = "warning"
        else:
            if is_non_latin:
                banner_text = "⚠️ NO MATCH — This name contains non-Latin characters. Automatic matching is limited — also use Text search and Manual check."
                banner_type = "warning"
            else:
                banner_text = "✅ NO MATCH — Clean on all checked sources"
                banner_type = "success"

        # Generate Reports & Log
        pdf_path, excel_path = generate_reports(
            search_type=search_type,
            inputs=inputs_dict,
            overall_banner=banner_text,
            source_statuses=source_statuses,
            sanctions_hits=sanctions_hits,
            aviation_hits=aviation_hits,
            country_risk_hits=country_risk_hits,
            opensanctions_used=use_opensanctions,
        )

        log_search(
            search_type=search_type,
            inputs=inputs_dict,
            source_results=source_statuses,
            report_file_name=pdf_path.name,
            opensanctions_used=use_opensanctions,
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
            "pdf_path": str(pdf_path),
            "excel_path": str(excel_path),
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

        if res["search_type"] == "Person" and "🔴" in res["banner_text"] and not (res["dob_entered"] or res["nat_entered"]):
            st.info("💡 **Add DOB / nationality to refine** this person search and clear potential name conflicts.")

        if res.get("is_non_latin") and res.get("banner_type") != "warning":
            st.warning(f"⚠️ **Non-Latin Input:** {res.get('non_latin_warning')}")
        if res.get("searched_as"):
            st.info(f"ℹ️ **Transliteration:** {res.get('searched_as')}")

        # Download Reports Row
        col_d1, col_d2, _ = st.columns([1, 1, 3])
        with col_d1:
            if os.path.isfile(res["pdf_path"]):
                with open(res["pdf_path"], "rb") as f:
                    st.download_button(
                        "📥 Download PDF Report",
                        data=f.read(),
                        file_name=Path(res["pdf_path"]).name,
                        mime="application/pdf",
                    )
        with col_d2:
            if os.path.isfile(res["excel_path"]):
                with open(res["excel_path"], "rb") as f:
                    st.download_button(
                        "📥 Download Excel Report",
                        data=f.read(),
                        file_name=Path(res["excel_path"]).name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

        # Section A — Sanctions
        st.subheader("Section A — Sanctions Findings")
        status_cols = st.columns(len(res["source_statuses"]))
        for i, s in enumerate(res["source_statuses"]):
            with status_cols[i]:
                tier = s.get("tier")
                badge = "🔴" if tier == "POTENTIAL_MATCH" else ("🟠" if tier == "POSSIBLE_MATCH_REVIEW" else ("✅" if tier == "NO_MATCH" else "⚪"))
                friendly_tier_name = {
                    "POTENTIAL_MATCH": "Match to verify",
                    "POSSIBLE_MATCH_REVIEW": "Review recommended",
                    "NO_MATCH": "No match",
                    "NOT_CHECKED": "Incomplete",
                }.get(tier, tier)
                delta_str = s.get("status")
                below_cnt = s.get("below_count", 0)
                if below_cnt > 0:
                    delta_str = f"+{below_cnt}ℹ️ info"
                st.metric(label=s["id"].upper().replace("_", " "), value=f"{badge} {friendly_tier_name}", delta=delta_str)

        # Render Flagged Hits (Expanded by default for 🔴 and 🟠)
        if res["sanctions_hits"]:
            for idx, h in enumerate(res["sanctions_hits"]):
                src_id = h.get("source_list", "")
                src_info = source_dict.get(src_id, {})
                verify_url = src_info.get("verify_url") or src_info.get("landing_page") or "https://sanctionssearch.ofac.treas.gov/"
                rec_template = src_info.get("record_url_template", "")
                rec_id = h.get("source_id", "")
                if rec_template and rec_id:
                    direct_verify_url = rec_template.replace("{id}", str(rec_id))
                    has_direct_link = True
                else:
                    direct_verify_url = verify_url
                    has_direct_link = False

                tier_icon = h.get("tier_icon") or ("🔴" if h.get("tier") == "POTENTIAL_MATCH" else "🟠")
                exp_label = f" — *Expanded from alias: `{h.get('expanded_from')}`*" if h.get("expanded_from") else ""
                
                with st.expander(
                    f"{tier_icon} [{src_id}] {h.get('primary_name')} (Score: {h.get('score', 0.0):.4f}){exp_label}",
                    expanded=True, # 🔴 and 🟠 rows expanded by default per T1.7 / T5.2
                ):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(f"**Primary Name:** {h.get('primary_name')}")
                        st.markdown(f"**Matched Alias / Name:** <mark style='background-color: #FFEB3B; padding: 2px 6px; font-weight: bold;'>{h.get('matched_name')}</mark>", unsafe_allow_html=True)
                        if h.get("expanded_from"):
                            st.markdown(f"**Expanded From:** `{h.get('expanded_from')}`")
                        st.markdown(f"**Record ID:** `{rec_id}`")
                        st.markdown(f"**Entity Type:** {h.get('entity_type')}")
                    with c2:
                        st.markdown(f"**Programme / Regime:** {h.get('program')}")
                        reason_code = h.get("tier_reason") or h.get("reason")
                        plain_reason = translate_reason(reason_code)
                        st.markdown(f"**Reason:** {plain_reason}")
                        with st.expander("Technical details"):
                            st.markdown(f"**Match Score:** `{h.get('score', 0.0):.4f}`")
                            st.markdown(f"**Internal Reason Code:** `{reason_code}`")
                            st.markdown(f"**Score Source:** `{h.get('score_source')}`")
                        
                        # Official Verification link with Copy Name / Copy ID
                        st.link_button(f"🔗 Verify on official {src_id} source", direct_verify_url)
                        if not has_direct_link:
                            st.caption(f"Copy values for official search box:")
                            copy_c1, copy_c2 = st.columns(2)
                            with copy_c1:
                                st.code(h.get('matched_name') or h.get('primary_name') or "", language="")
                            with copy_c2:
                                st.code(str(rec_id), language="")
                        pub_date = src_info.get("publication_date", "current")
                        st.caption(f"*Our copy is dated {pub_date}. The official site may be more recent.*")
        else:
            st.write("✅ No flagged sanctions records identified.")

        # Show Candidates Below Threshold Toggle per list
        per_list = res.get("per_list_data", {})
        for list_id, ldata in per_list.items():
            all_cands = ldata.get("all_candidates", [])
            below_cands = [c for c in all_cands if c.get("tier") == "BELOW_THRESHOLD"]
            if below_cands:
                with st.expander(
                    f"ℹ️ Show candidates below threshold ({len(below_cands)}) — [{list_id}]",
                    expanded=(st.query_params.get("expand_info") == "true"),
                ):
                    st.caption("Candidate matches below threshold are shown for information only. They are not matches.")
                    if len(all_cands) >= 25:
                        st.info("Showing top 25 — more may exist; refine the search.")
                    for bc in below_cands:
                        b_c1, b_c2 = st.columns([2, 1])
                        with b_c1:
                            st.markdown(f"ℹ️ **{bc.get('primary_name')}** (Matched: `{bc.get('matched_name')}`)")
                            st.caption(f"ID: `{bc.get('source_id')}` | Entity Type: {bc.get('entity_type')} | Prog: {bc.get('program')}")
                        with b_c2:
                            st.markdown(f"Score: `{bc.get('score', 0.0):.4f}`")
                            st.caption(f"Reason: {translate_reason(bc.get('reason'))}")
                            # Verification link
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
                    st.error(
                        f"🔴 **Export-control restriction (US EAR) — verify before providing any service**\n\n"
                        f"**Aircraft / Operator:** {av.get('details')}\n\n*Source: BIS Aircraft List*"
                    )
                    st.link_button("🔗 Verify on official BIS document", av_info.get("verify_url", "https://www.bis.gov/"))
                    st.caption(f"*Our copy is dated {av_info.get('publication_date')}. The official site may be more recent.*")
                else:
                    eu_av = source_dict.get("eu_air_safety", {})
                    st.warning(
                        f"⚠️ **Safety flag — not a sanctions finding** ({rtype})\n\n"
                        f"**Carrier / Scope:** {av.get('details')}\n\n*Source: EU Air Safety List / FAA IASA*"
                    )
                    st.link_button("🔗 Verify on official Aviation authority", eu_av.get("verify_url", "https://transport.ec.europa.eu/"))
                    st.caption(f"*Our copy is dated {eu_av.get('publication_date')}. The official site may be more recent.*")
        else:
            st.write("✅ No aviation safety bans or export-control restrictions found.")

        # Section C — Country Risk
        st.subheader("Section C — Country Risk (FATF)")
        if res["country_risk_hits"]:
            for cr in res["country_risk_hits"]:
                fatf_info = source_dict.get("fatf_jurisdictions", {})
                st.warning(
                    f"⚠️ **Country risk flag — not a sanctions finding**\n\n"
                    f"**Jurisdiction:** {cr.get('country')}\n\n"
                    f"**FATF Status:** {cr.get('list_type')} — *{cr.get('call_to_action')}*"
                )
                st.link_button("🔗 Verify on official FATF website", fatf_info.get("verify_url", "https://www.fatf-gafi.org/"))
                st.caption(f"*Our copy is dated {fatf_info.get('publication_date')}. The official site may be more recent.*")
        else:
            st.write("✅ No elevated FATF country risk flags.")

        # Section D — Historical Manual Check Audit Trail (Decision 3)
        history_query = res.get("primary_query") or ""
        past_checks = get_manual_checks_for_entity(history_query) if history_query else []
        if past_checks:
            st.divider()
            with st.expander(f"📋 Prior Manual Verification History ({len(past_checks)} recorded)", expanded=True):

                st.caption("Historical analyst check decisions for this counterparty from screening audit trail:")
                for chk in past_checks:
                    badge = "🔴" if "Match" in chk.get("result", "") else "✅"
                    st.markdown(f"**{badge} {chk.get('result')}** on `{chk.get('source')}` by `{chk.get('user')}` at `{chk.get('timestamp')[:16]}`")
                    if chk.get("comment"):
                        st.caption(f"Remarks: _{chk.get('comment')}_")



# =========================================================================
# TAB 2: TEXT SEARCH
# =========================================================================
with tab_raw:
    st.markdown("### Text Search")
    st.info("📌 **Text search — results are keyword occurrences across official records. Review each record.**")

    raw_engine = RawSearchEngine()
    all_raw_sources = [
        "us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl",
        "bis_aircraft", "eu_air_safety", "faa_iasa",
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

        st.markdown("**Sources to Search** (all ticked by default)")
        selected_raw_sources = st.multiselect(
            "Selected Sources",
            options=all_raw_sources,
            default=all_raw_sources,
            format_func=lambda s: f"{s} ({source_dict.get(s, {}).get('authority', s)})",
        )

        raw_submitted = st.form_submit_button("🔎 Search Records", type="primary")

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
            st.warning("⚠️ **Showing top 200 — more may exist; refine the search.**")

        # Download Report Buttons
        r_d1, r_d2, _ = st.columns([1, 1, 3])
        with r_d1:
            if os.path.isfile(rr.get("pdf_path", "")):
                with open(rr["pdf_path"], "rb") as f:
                    st.download_button(
                        "📥 Download Text Search PDF",
                        data=f.read(),
                        file_name=Path(rr["pdf_path"]).name,
                        mime="application/pdf",
                        key="raw_pdf_dl",
                    )
        with r_d2:
            if os.path.isfile(rr.get("excel_path", "")):
                with open(rr["excel_path"], "rb") as f:
                    st.download_button(
                        "📥 Download Text Search Excel",
                        data=f.read(),
                        file_name=Path(rr["excel_path"]).name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="raw_excel_dl",
                    )

        if rr["results"]:
            for item in rr["results"]:
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
                        st.link_button("🔗 Verify on official source", item["verify_url"])
                        if not item["has_record_link"]:
                            st.code(item["primary_name"], language="")
                    st.divider()
        else:
            st.info("No records matched the raw search query.")


# =========================================================================
# TAB 3: MANUAL CHECK (T5.2)
# =========================================================================
with tab_manual:
    st.markdown("### Manual Official List Check")
    st.caption("Verify query names directly on official search portals and record manual compliance determinations.")

    manual_name = st.text_input(
        "Subject / Entity Name for Manual Check*",
        value=st.session_state.manual_check_name,
        placeholder="e.g. Sberbank or Aeroflot",
        key="manual_name_box",
    )

    official_manual_sources = [
        {"id": "us_ofac", "name": "US OFAC (SDN & Consolidated)", "authority": "US Treasury, OFAC", "inst": "Search by name; check aliases and date of birth."},
        {"id": "us_csl", "name": "US Consolidated Screening List", "authority": "US ITA (Commerce, State, Treasury)", "inst": "Search entity or person name across CSL agencies."},
        {"id": "uk_csl", "name": "UK Sanctions List", "authority": "UK FCDO", "inst": "Search UK Sanctions service; review designation details."},
        {"id": "eu_csl", "name": "EU Sanctions Map & Tracker", "authority": "European Commission", "inst": "Search EU Sanctions Map; verify regime and listing date."},
        {"id": "un_csl", "name": "UN SC Consolidated List", "authority": "UN Security Council", "inst": "Search UN Consolidated list by name or UN Reference number."},
        {"id": "bis_aircraft", "name": "BIS Commercial & Private Aircraft", "authority": "US BIS", "inst": "Search tail number, serial number (MSN), or operator."},
        {"id": "bis_tdo", "name": "BIS Temporary Denial Orders (TDO)", "authority": "US BIS Export Violations", "inst": "Check active Temporary Denial Orders and export violation notices."},
        {"id": "eu_air_safety", "name": "EU Air Safety List", "authority": "European Commission DG MOVE", "inst": "Check Annex A (banned carriers) and Annex B (operational restrictions)."},
        {"id": "faa_iasa", "name": "FAA IASA Program Results", "authority": "US FAA", "inst": "Check country civil aviation authority safety assessment (Category 2)."},
        {"id": "in_mha_first_schedule", "name": "MHA First Schedule (Terrorist Organisations)", "authority": "Ministry of Home Affairs, India", "inst": "Check terrorist organizations and designated fronts/aliases under UAPA."},
        {"id": "in_mha_fourth_schedule", "name": "MHA Fourth Schedule (Individual Terrorists)", "authority": "Ministry of Home Affairs, India", "inst": "Check individual terrorists designated under UAPA."},
        {"id": "in_mha_unlawful_assoc", "name": "MHA Section 3 Unlawful Associations", "authority": "Ministry of Home Affairs, India", "inst": "Check unlawful associations declared under Section 3 of UAPA."},
        {"id": "fatf_jurisdictions", "name": "FATF High-Risk & Monitored Jurisdictions", "authority": "Financial Action Task Force (FATF)", "inst": "Check FATF Black list (Call for Action) and Grey list (Increased Monitoring)."},
    ]

    manual_form_values = {}

    st.markdown("---")
    st.markdown("#### Official Search Verification Rows")

    for src in official_manual_sources:
        sid = src["id"]
        cfg = source_dict.get(sid, {})
        v_url = cfg.get("verify_url") or cfg.get("landing_page") or "https://sanctionssearch.ofac.treas.gov/"
        p_date = cfg.get("publication_date", "current")

        with st.container():
            m_c1, m_c2, m_c3, m_c4 = st.columns([3, 2, 2, 3])
            with m_c1:
                st.markdown(f"**{src['name']}**")
                st.caption(f"Authority: {src['authority']}\n\n*Instruction: {src['inst']}*")
                st.caption(f"Our copy: {p_date} (official site may be more recent)")
            with m_c2:
                st.link_button("🌐 Open official search", v_url)
                if manual_name:
                    st.caption("Copy name to clipboard:")
                    st.code(manual_name, language="")
            with m_c3:
                sel = st.selectbox(
                    f"Result ({sid})",
                    ["Not checked", "No match", "Possible match", "Match"],
                    index=0,
                    key=f"manual_res_{sid}",
                )
            with m_c4:
                comm = st.text_input(
                    f"Comment / Note ({sid})",
                    placeholder="e.g. Verified clean on official portal",
                    key=f"manual_comm_{sid}",
                )
            manual_form_values[sid] = {
                "source": sid,
                "authority": src["authority"],
                "result": sel,
                "comment": comm,
                "verify_url": v_url,
            }
            st.divider()

    if st.button("💾 Save Manual Check Results", type="primary"):
        if not manual_name.strip():
            st.error("Please provide the Subject Name at the top before saving manual check results.")
        else:
            saved_count = 0
            checks_to_save = []
            for sid, val in manual_form_values.items():
                if val["result"] != "Not checked" or val["comment"]:
                    log_manual_check(
                        name=manual_name.strip(),
                        source=sid,
                        result=val["result"],
                        comment=val["comment"],
                    )
                    checks_to_save.append(val)
                    saved_count += 1

            st.session_state.manual_checks_saved[manual_name.strip()] = checks_to_save

            # If screened results exist for the same name, regenerate reports with manual check included
            if st.session_state.last_results and st.session_state.last_results.get("primary_query") == manual_name.strip():
                res = st.session_state.last_results
                pdf_p, excel_p = generate_reports(
                    search_type=res["search_type"],
                    inputs={"name": manual_name.strip()},
                    overall_banner=res["banner_text"],
                    source_statuses=res["source_statuses"],
                    sanctions_hits=res["sanctions_hits"],
                    aviation_hits=res["aviation_hits"],
                    country_risk_hits=res["country_risk_hits"],
                    manual_checks=checks_to_save,
                )
                res["pdf_path"] = str(pdf_p)
                res["excel_path"] = str(excel_p)
                st.success(f"Saved {saved_count} manual check findings to SQLite audit log and updated session report!")
            else:
                st.success(f"Saved {saved_count} manual check findings to SQLite audit log (`mode = manual`).")


# Footer Disclaimer
st.markdown("---")
st.caption(
    "Screening aid only. A result here is not a legal determination. "
    "Potential matches must be verified against the official source and escalated under the Sanctions Compliance Policy. "
    "Ownership/control (e.g. the US 50% rule) is not assessed. Antigravity and the developers accept no liability for reliance on this tool."
)
