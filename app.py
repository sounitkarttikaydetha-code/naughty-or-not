"""
Naughty or not — Sanction checK
Streamlit User Interface (T5).
"""

import getpass
import os
import platform
import yaml
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

from modules.aviation.client import AviationClient
from modules.fatf.client import FATFClient
from modules.india.client import IndiaClient
from modules.opensanctions.client import OpenSanctionsClient
from modules.reporting.generator import generate_reports
from modules.reporting.logger import (
    has_user_acknowledged,
    log_acknowledgement,
    log_search,
    get_total_opensanctions_credits,
    APP_VERSION,
)
from modules.screening.tiering import screen_query_all_lists
from modules.watchman.client import WatchmanClient

PROJECT_ROOT = Path(__file__).resolve().parent
SOURCES_YAML = PROJECT_ROOT / "config" / "sources.yaml"

# Session state initialization
if "acknowledged" not in st.session_state:
    st.session_state.acknowledged = has_user_acknowledged(app_version=APP_VERSION)
if "session_os_credits" not in st.session_state:
    st.session_state.session_os_credits = 0
if "last_results" not in st.session_state:
    st.session_state.last_results = None

st.set_page_config(
    page_title="Sanction checK",
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

# 2. First-Run Dialog / Modal
if st.query_params.get("autorun") == "true":
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


# Load Source Register
def load_sources_registry() -> Dict[str, Any]:
    if SOURCES_YAML.is_file():
        try:
            with open(SOURCES_YAML, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            pass
    return {"sources": []}


source_reg = load_sources_registry()
source_dict = {s["id"]: s for s in source_reg.get("sources", [])}


# Sidebar: Freshness & OpenSanctions Credits
with st.sidebar:
    st.title("Source Status")
    st.caption(f"App Version: v{APP_VERSION} | Node: {platform.node()}")

    # OpenSanctions Credits
    total_os_credits = get_total_opensanctions_credits()
    st.metric(
        label="OpenSanctions Credits",
        value=f"{st.session_state.session_os_credits} session",
        delta=f"{total_os_credits} total logged",
    )
    st.divider()

    st.subheader("Source Freshness")
    for s in source_reg.get("sources", []):
        sid = s.get("id")
        auth = s.get("authority")
        pdate = s.get("publication_date", "—")
        status = s.get("status", "OK")
        badge = "🟢" if status == "OK" else ("🟡" if status == "STALE" else "🔴")
        st.markdown(f"**{badge} {sid}** ({auth})\n*Pub: {pdate}*")

    if st.button("🔄 Refresh All Sources"):
        with st.spinner("Refreshing sources..."):
            try:
                from modules.aviation.parser import check_and_refresh_sources
                check_and_refresh_sources(force=True)
                st.success("Refreshed aviation and local registers!")
            except Exception as e:
                st.error(f"Refresh error: {e}")


# Main Screen Title
st.title("Sanction checK")
st.caption("Comprehensive multi-source compliance screening across global sanctions, aviation safety, and country risk.")

# Search Type Selection (outside form to allow dynamic input fields to update)
qp_type = st.query_params.get("search_type")
type_options = ["Person", "Organisation", "Airline", "Aircraft", "Vessel"]
default_idx = type_options.index(qp_type) if qp_type in type_options else 1
if qp_type and qp_type in type_options:
    st.session_state["search_type_select"] = qp_type

col_top1, col_top2 = st.columns([1, 2])
with col_top1:
    search_type = st.selectbox(
        "Search Type",
        type_options,
        index=default_idx,
        key="search_type_select",
    )

# Inputs Form
qp_q = st.query_params.get("query", "")
qp_dob = st.query_params.get("dob", "")
qp_nat = st.query_params.get("nationality", "")
qp_op = st.query_params.get("operator", "")

with st.form("screening_form"):
    # Dynamic inputs
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
    src_col1, src_col2, src_col3, src_col4, src_col5 = st.columns(5)
    with src_col1:
        use_sanctions = st.checkbox("Sanctions (Watchman)", value=True, disabled=True)
    with src_col2:
        use_india = st.checkbox("India (MHA)", value=True)
    with src_col3:
        use_aviation = st.checkbox("Aviation", value=(search_type in ["Airline", "Aircraft"]))
    with src_col4:
        use_country_risk = st.checkbox("Country risk (FATF)", value=True)
    with src_col5:
        os_key_present = bool(os.getenv("OPENSANCTIONS_API_KEY"))
        use_opensanctions = st.checkbox(
            "OpenSanctions (uses credits)",
            value=False,
            disabled=not os_key_present,
            help="Requires OPENSANCTIONS_API_KEY in .env" if not os_key_present else "Opt-in API search (consumes API credits)",
        )

    st.caption("Thresholds: Potential Match >= 0.80 | Possible Match >= 0.70 | Sub-threshold core >= 0.60")

    submitted = st.form_submit_button("🔍 Screen Entity", type="primary")

if not submitted and st.query_params.get("autorun") == "true" and (tail_input or name_input):
    submitted = True


# Screening Execution
if submitted:
    primary_query = (tail_input or name_input).strip()
    if not primary_query:
        st.error("Please enter a Name or Registration number to screen.")
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

    # 1. Sanctions Screening (Watchman 5 lists)
    w_query_type = "person" if search_type == "Person" else ("airline" if search_type == "Airline" else "organisation")
    w_results = screen_query_all_lists(
        query=primary_query,
        client=watchman,
        query_type=w_query_type,
        dob=dob_input or None,
        nationality=nat_input or None,
    )

    for src_id in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]:
        src_meta = source_dict.get(src_id, {})
        res_data = w_results.get(src_id, {})
        best = res_data.get("best_hit", {})
        tier = best.get("tier", "NO_MATCH")

        if tier == "NOT_CHECKED":
            is_incomplete = True

        source_statuses.append({
            "id": src_id,
            "authority": src_meta.get("authority", src_id.upper()),
            "date": src_meta.get("publication_date", "current"),
            "status": "FAILED" if tier == "NOT_CHECKED" else "OK",
            "tier": tier,
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

        source_statuses.append({
            "id": "in_mha",
            "authority": "MHA (India UAPA)",
            "date": "2026-10-01",
            "status": "OK",
            "tier": in_tier,
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
            })
    else:
        source_statuses.append({
            "id": "opensanctions",
            "authority": "OpenSanctions API",
            "date": "live",
            "status": "NOT_RUN",
            "tier": "NOT_RUN",
        })

    # 4. Aviation Screening
    if use_aviation and search_type in ["Airline", "Aircraft"]:
        if search_type == "Airline":
            av_res = aviation_client.screen_airline(
                name=primary_query,
                aoc_state=aoc_input or country_input or None,
                icao=id_input or None,
            )
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

    # Compute overall banner
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
        "search_type": search_type,
        "primary_query": primary_query,
        "dob_entered": bool(dob_input),
        "nat_entered": bool(nat_input),
        "sanctions_hits": sanctions_hits,
        "source_statuses": source_statuses,
        "aviation_hits": aviation_hits,
        "country_risk_hits": country_risk_hits,
        "pdf_path": str(pdf_path),
        "excel_path": str(excel_path),
    }


# Render Results View
if st.session_state.last_results:
    res = st.session_state.last_results

    st.markdown("---")
    # Overall Finding Banner
    if res["banner_type"] == "error":
        st.error(f"### {res['banner_text']}")
    elif res["banner_type"] == "warning":
        st.warning(f"### {res['banner_text']}")
    elif res["banner_type"] == "success":
        st.success(f"### {res['banner_text']}")
    else:
        st.info(f"### {res['banner_text']}")

    # Person refinement prompt
    if res["search_type"] == "Person" and "🔴" in res["banner_text"] and not (res["dob_entered"] or res["nat_entered"]):
        st.info("💡 **Add DOB / nationality to refine** this person search and clear potential name conflicts.")

    # Reports Download Row
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
            st.metric(label=s["id"].upper(), value=f"{badge} {tier}", delta=s.get("status"))

    if res["sanctions_hits"]:
        for idx, h in enumerate(res["sanctions_hits"]):
            src_id = h.get("source_list", "")
            src_info = source_dict.get(src_id, {})
            verify_url = src_info.get("landing_page") or "https://sanctionssearch.ofac.treas.gov/"

            exp_label = f" — *Expanded from alias: `{h.get('expanded_from')}`*" if h.get("expanded_from") else ""
            with st.expander(
                f"{h.get('tier_icon')} [{h.get('source_list')}] {h.get('primary_name')} (Score: {h.get('score', 0.0):.4f}){exp_label}",
                expanded=(idx < 2),
            ):
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**Primary Name:** {h.get('primary_name')}")
                    st.markdown(f"**Matched Alias / Name:** <mark style='background-color: #FFEB3B; padding: 2px 6px; font-weight: bold;'>{h.get('matched_name')}</mark>", unsafe_allow_html=True)
                    if h.get("expanded_from"):
                        st.markdown(f"**Expanded From:** `{h.get('expanded_from')}`")
                    st.markdown(f"**Record ID:** `{h.get('source_id')}`")
                    st.markdown(f"**Entity Type:** {h.get('entity_type')}")
                with c2:
                    st.markdown(f"**Programme / Regime:** {h.get('program')}")
                    st.markdown(f"**Watchman Raw Score:** `{h.get('watchman_raw_score', h.get('score', 0.0)):.4f}`")
                    st.markdown(f"**Tier Reason:** `{h.get('tier_reason', h.get('reason'))}`")
                    st.markdown(f"**Score Source:** `{h.get('score_source')}`")
                    st.markdown(f"[🔗 Verify on official {src_id} source]({verify_url})")
    else:
        st.write("✅ No sanctions records identified on any active list.")

    # Section B — Aviation
    st.subheader("Section B — Aviation Safety & Export Controls")
    if res["aviation_hits"]:
        for av in res["aviation_hits"]:
            rtype = av.get("result_type", "")
            if rtype == "EAR_RESTRICTION":
                st.error(
                    f"🔴 **Export-control restriction (US EAR) — verify before providing any service**\n\n"
                    f"**Aircraft / Operator:** {av.get('details')}\n\n*Source: BIS Aircraft List*"
                )
            else:
                st.warning(
                    f"⚠️ **Safety flag — not a sanctions finding** ({rtype})\n\n"
                    f"**Carrier / Scope:** {av.get('details')}\n\n*Source: EU Air Safety List / FAA IASA*"
                )
    else:
        st.write("✅ No aviation safety bans or export-control restrictions found.")

    # Section C — Country Risk
    st.subheader("Section C — Country Risk (FATF)")
    if res["country_risk_hits"]:
        for cr in res["country_risk_hits"]:
            st.warning(
                f"⚠️ **Country risk flag — not a sanctions finding**\n\n"
                f"**Jurisdiction:** {cr.get('country')}\n\n"
                f"**FATF Status:** {cr.get('list_type')} — *{cr.get('call_to_action')}*"
            )
    else:
        st.write("✅ No elevated FATF country risk flags.")

# Footer Disclaimer
st.markdown("---")
st.caption(
    "Screening aid only. A result here is not a legal determination. "
    "Potential matches must be verified against the official source and escalated under the Sanctions Compliance Policy. "
    "Ownership/control (e.g. the US 50% rule) is not assessed. Antigravity and the developers accept no liability for reliance on this tool."
)
