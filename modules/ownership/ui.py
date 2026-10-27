"""
Streamlit UI Component for Beneficial Ownership & Control (T11 Part E, T11.1 Section 1).
Renders the 'Ownership check' tab:
  - Target entity input, 7-sheet template download & mapping settings
  - Multi-sheet Excel workbook & Word (.docx) upload with error/warning preview (row, sheet, col, problem, suggested_fix)
  - Interactive multi-tier ownership tree visualization (Graphviz / hierarchical tree)
  - Multilateral sanctions evaluation panels (OFAC 50%, EU >=50%/Control, UK >50%/Majority, UN/MHA, BIS)
  - Adani SOP 20% diligence triggers, Indian 10% BO markers & undisclosed shortfall
  - Four-eyes workflow disposition (Draft -> Submitted -> Reviewed -> Closed/Escalated) with user separation check
  - Evidence pack export (combined PDF dossier + Excel round-trip workbook)
"""

import io
from pathlib import Path
from typing import Any, Dict, List, Optional
import streamlit as st

from modules.ownership.engine import UBOEngine
from modules.ownership.importer import (
    get_user_mappings_dir,
    list_available_mappings,
    load_mapping,
    parse_docx,
    parse_ownership_table,
    parse_ownership_workbook,
)
from modules.ownership.models import (
    Counterparty,
    ControlRelation,
    FourEyesReview,
    Holding,
    KeyPerson,
    OwnershipNode,
    UBOResult,
)

TEMPLATE_PATH = Path(__file__).resolve().parent.parent.parent / "templates" / "ownership_template.xlsx"


def render_ownership_tab():
    """Render the comprehensive Ownership Check tab."""
    st.markdown("### 🏢 Beneficial Ownership & Control (UBO) Screening")
    st.caption(
        "Multilateral 50% Rule and Control analysis covering US OFAC (FAQs 399, 401), "
        "EU Council Regulations, and UK OFSI Sanctions Regulations. "
        "Includes Adani SOP 20% diligence triggers and Indian 10% SBO markers. 100% offline; zero data egress."
    )

    # Top action bar: Template download and sample loader
    c_top1, c_top2 = st.columns([1, 1])
    with c_top1:
        if TEMPLATE_PATH.exists():
            with open(TEMPLATE_PATH, "rb") as tf:
                st.download_button(
                    "📥 Download 7-Sheet Excel Template",
                    data=tf.read(),
                    file_name="clearance_check_ownership_template.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
    with c_top2:
        if st.button("📋 Load Example: Alpha Ground Services (Worked Example 4)", use_container_width=True):
            st.session_state["ubo_counterparty"] = Counterparty(
                name="Alpha Ground Services Private Limited",
                jurisdiction="India",
                registration_number="U63090MH2020PTC123456",
            )
            st.session_state["ubo_holdings"] = [
                Holding(shareholder_name="Beta Holdings Ltd", entity_name="Alpha Ground Services Private Limited", share_pct=60.0),
                Holding(shareholder_name="Rajesh Sharma", entity_name="Alpha Ground Services Private Limited", share_pct=25.0, entity_type="person", dob="1975-08-20", id_number="ABCPS1234F"),
                Holding(shareholder_name="Person P", entity_name="Beta Holdings Ltd", share_pct=50.0, entity_type="person", is_blocked=True, blocked_source="us_ofac; eu_csl; uk_csl; un_csl"),
                Holding(shareholder_name="Person Q", entity_name="Beta Holdings Ltd", share_pct=50.0, entity_type="person"),
            ]
            st.session_state["ubo_control"] = [
                ControlRelation(controller_name="Beta Holdings Ltd", target_name="Alpha Ground Services Private Limited", control_type="board_seat", description="Appoints 2 of 4 directors"),
            ]
            st.session_state["ubo_key_persons"] = [
                KeyPerson(name="Rajesh Sharma", target_name="Alpha Ground Services Private Limited", role="director", dob="1975-08-20", id_number="ABCPS1234F", kyc_complete=True),
            ]
            st.rerun()

    st.divider()

    # Counterparty details
    cp_curr: Counterparty = st.session_state.get("ubo_counterparty", Counterparty(name=""))
    c_cp1, c_cp2, c_cp3 = st.columns([2, 1, 1])
    with c_cp1:
        target_name = st.text_input("Target Counterparty Name", value=cp_curr.name, placeholder="e.g. Alpha Ground Services Private Limited")
    with c_cp2:
        target_jur = st.text_input("Jurisdiction", value=cp_curr.jurisdiction, placeholder="e.g. India")
    with c_cp3:
        target_reg = st.text_input("Registration / CIN", value=cp_curr.registration_number, placeholder="e.g. U63090MH2020PTC123456")

    cp_curr.name = target_name
    cp_curr.jurisdiction = target_jur
    cp_curr.registration_number = target_reg
    st.session_state["ubo_counterparty"] = cp_curr

    # Input method tabs
    in_tab_upload, in_tab_word, in_tab_mappings = st.tabs(["📁 Excel Upload & Preview", "📄 Word (.docx) Import", "⚙️ Mappings & Settings"])

    with in_tab_upload:
        uploaded_file = st.file_uploader(
            "Upload 7-Sheet Ownership Workbook (.xlsx, .csv)",
            type=["xlsx", "csv"],
            key="ubo_file_uploader",
        )
        if uploaded_file is not None:
            fn = uploaded_file.name.lower()
            if fn.endswith(".xlsx") or fn.endswith(".xlsm"):
                cp_parsed, h_parsed, cr_parsed, kp_parsed, preview_issues = parse_ownership_workbook(
                    uploaded_file.getvalue(),
                    filename=uploaded_file.name,
                )
                if cp_parsed.name and cp_parsed.name != "Unknown Target":
                    st.session_state["ubo_counterparty"] = cp_parsed
                if h_parsed:
                    st.session_state["ubo_holdings"] = h_parsed
                if cr_parsed:
                    st.session_state["ubo_control"] = cr_parsed
                if kp_parsed:
                    st.session_state["ubo_key_persons"] = kp_parsed

                if preview_issues:
                    st.markdown("##### ⚠️ Import Preview: Validation Warnings & Fixes")
                    st.dataframe(preview_issues, use_container_width=True, hide_index=True)
                else:
                    st.success(f"Workbook successfully validated: {len(h_parsed)} holdings, {len(cr_parsed)} control relations, {len(kp_parsed)} key persons.")
            else:
                nodes, warnings = parse_ownership_table(uploaded_file.getvalue(), filename=uploaded_file.name)
                for w in warnings:
                    st.warning(w)
                if nodes:
                    h_list = [
                        Holding(
                            shareholder_name=n.name,
                            entity_name=n.parent_name or target_name,
                            share_pct=n.ownership_pct,
                            entity_type=n.entity_type,
                            country=n.country,
                            notes=n.notes,
                        )
                        for n in nodes
                    ]
                    st.session_state["ubo_holdings"] = h_list
                    st.success(f"Parsed {len(nodes)} records from CSV.")

    with in_tab_word:
        docx_file = st.file_uploader("Upload Word Document with Ownership Table (.docx)", type=["docx"], key="ubo_docx_uploader")
        if docx_file is not None:
            cp_d, h_d, cr_d, kp_d, docx_issues = parse_docx(docx_file.getvalue())
            if docx_issues:
                st.dataframe(docx_issues, use_container_width=True)
            if h_d:
                st.session_state["ubo_holdings"] = h_d
                st.success(f"Parsed {len(h_d)} ownership rows from Word document.")

    with in_tab_mappings:
        st.markdown("##### 📋 Configured Import Mappings")
        mappings = list_available_mappings()
        if mappings:
            m_display = []
            for m in mappings:
                m_display.append({
                    "Mapping Name": m["name"],
                    "Version": m["version"],
                    "Location": "Built-in" if m["is_builtin"] else "User Folder",
                    "SHA-256 Hash": m["hash"][:16] + "...",
                })
            st.dataframe(m_display, use_container_width=True, hide_index=True)
        st.caption(f"User mappings directory: `{get_user_mappings_dir()}`")

    # Review loaded data
    holdings_curr: List[Holding] = st.session_state.get("ubo_holdings", [])
    if holdings_curr:
        with st.expander(f"📋 Loaded Holdings & Control Hierarchy ({len(holdings_curr)} shareholdings)", expanded=False):
            disp_data = []
            for h in holdings_curr:
                disp_data.append({
                    "Shareholder": h.shareholder_name,
                    "Held In Entity": h.entity_name,
                    "Shareholding %": f"{h.share_pct:.1f}%",
                    "Type": h.holding_type.capitalize(),
                    "Verification Level": h.verification_level,
                    "Override": h.user_override or "Auto-Screen",
                })
            st.dataframe(disp_data, use_container_width=True, hide_index=True)

    st.markdown("<br>", unsafe_allow_html=True)
    btn_screen = st.button("🚀 Screen Corporate Structure & Evaluate Control", type="primary", use_container_width=True)

    if btn_screen:
        if not target_name.strip():
            st.error("Please enter a Target Counterparty Name.")
            return
        if not holdings_curr:
            st.error("Please provide at least one shareholding relationship.")
            return

        with st.spinner("Screening entities, checking cycles & evaluating multilateral rules..."):
            engine = UBOEngine()
            result = engine.evaluate_structure(
                counterparty=st.session_state["ubo_counterparty"],
                holdings=holdings_curr,
                control_relations=st.session_state.get("ubo_control", []),
                key_persons=st.session_state.get("ubo_key_persons", []),
                auto_screen=True,
            )
            st.session_state["ubo_last_result"] = result

    # Display results if available
    last_res: Optional[UBOResult] = st.session_state.get("ubo_last_result")
    if last_res:
        st.markdown("---")
        st.markdown(f"### 📊 Evaluation Findings: **{last_res.target_name}**")
        st.caption(f"Evaluation completed in {last_res.execution_time_ms:.1f}ms | Offline Lists")

        # Interactive Tree Visualization
        with st.expander("🌳 Interactive Ownership Hierarchy Tree", expanded=True):
            try:
                # Build graphviz dot string
                dot_lines = [
                    'digraph OwnershipTree {',
                    '  rankdir=TB;',
                    '  node [shape=box, style="rounded,filled", fontname="Segoe UI", fontsize=10];',
                    '  edge [fontname="Segoe UI", fontsize=9];',
                    f'  target [label="{last_res.target_name}\\n(Target Counterparty)", fillcolor="#E3F2FD", color="#1565C0", penwidth=2];',
                ]
                for h in last_res.holdings:
                    clean_sh = "".join(c if c.isalnum() else "_" for c in h.shareholder_name)
                    clean_ent = "target" if h.entity_name.lower() == last_res.target_name.lower() else "".join(c if c.isalnum() else "_" for c in h.entity_name)
                    eff = last_res.effective_holdings.get(h.shareholder_name, h.share_pct)
                    color = "#FFCDD2" if h.is_blocked else "#E8F5E9"
                    border = "#C62828" if h.is_blocked else "#2E7D32"
                    label = f"{h.shareholder_name}\\n(Direct: {h.share_pct:.1f}% | Look-Through: {eff:.1f}%)"
                    dot_lines.append(f'  {clean_sh} [label="{label}", fillcolor="{color}", color="{border}"];')
                    dot_lines.append(f'  {clean_sh} -> {clean_ent} [label="{h.share_pct:.1f}%"];')
                dot_lines.append('}')
                st.graphviz_chart("\n".join(dot_lines), use_container_width=True)
            except Exception:
                st.info("Interactive tree rendering available via graphviz.")

        # 4 Regime Verdict Cards
        v_col1, v_col2, v_col3, v_col4 = st.columns(4)

        with v_col1:
            st.markdown("#### 🇺🇸 US OFAC 50% Rule")
            if last_res.ofac_blocked:
                st.error(f"🔴 **CRITERIA MET**\n\nAggregate: **{last_res.ofac_aggregate_pct:.1f}%**")
                st.caption(last_res.ofac_verdict.get("verdict_text", ""))
            else:
                st.success(f"🟢 **CRITERIA NOT MET**\n\nAggregate: **{last_res.ofac_aggregate_pct:.1f}%**")
                st.caption(last_res.ofac_verdict.get("verdict_text", ""))

        with v_col2:
            st.markdown("#### 🇪🇺 EU Sanctions")
            if last_res.eu_blocked:
                st.error("🔴 **CRITERIA MET**")
                st.caption(last_res.eu_verdict.get("verdict_text", ""))
            else:
                st.success("🟢 **CRITERIA NOT MET**")
                st.caption(last_res.eu_verdict.get("verdict_text", ""))

        with v_col3:
            st.markdown("#### 🇬🇧 UK OFSI")
            if last_res.uk_blocked:
                st.error("🔴 **CRITERIA MET**")
                st.caption(last_res.uk_verdict.get("verdict_text", ""))
            else:
                st.success("🟢 **CRITERIA NOT MET**")
                st.caption(last_res.uk_verdict.get("verdict_text", ""))

        with v_col4:
            st.markdown("#### 🇺🇳 UN & 🇮🇳 MHA")
            if last_res.un_mha_flags:
                st.error(f"🔴 **ALERT: {len(last_res.un_mha_flags)} Listed Party**")
                for f in last_res.un_mha_flags:
                    st.caption(f["note"])
            else:
                st.success("🟢 **No Listed Parties**")
                st.caption("No owners or key persons listed on UN or India MHA registers.")

        # Traces & Calculation Notes
        with st.expander("🔍 Detailed Sanctions Traces & Boundary Notices", expanded=True):
            if last_res.ofac_path_traces:
                st.markdown("**OFAC Blocked Aggregation Traces:**")
                for tr in last_res.ofac_path_traces:
                    st.markdown(f"- `{tr}`")
            if last_res.eu_reasons:
                st.markdown("**EU Findings:**")
                for er in last_res.eu_reasons:
                    st.markdown(f"- {er}")
            if last_res.uk_verdict.get("notes"):
                st.markdown("**UK OFSI Boundary Notices:**")
                for un in last_res.uk_verdict.get("notes", []):
                    st.markdown(f"- ℹ️ *{un}*")
            if last_res.bis_affiliate_flags:
                st.markdown("**BIS Entity List 50%+ Affiliates:**")
                for bf in last_res.bis_affiliate_flags:
                    st.warning(f"⚠️ {bf['note']}")

        # Shortfall & Undisclosed Ownership Warning
        if last_res.undisclosed_ownership_pct > 0.0:
            st.warning(
                f"⚠️ **Undisclosed Ownership: {last_res.undisclosed_ownership_pct:.1f}% shortfall.** "
                + ("**CRITICAL: Result depends on undisclosed ownership.**" if last_res.depends_on_undisclosed else "")
            )

        # Adani 20% Diligence Triggers & Indian 10% BO Markers
        if last_res.diligence_triggers or last_res.india_bo_markers:
            st.markdown("#### 🔍 Compliance Triggers & Markers")
            c_tr1, c_tr2 = st.columns(2)
            with c_tr1:
                st.markdown("##### ✈️ Adani SOP 20% Diligence Triggers")
                if last_res.diligence_triggers:
                    for dt in last_res.diligence_triggers:
                        badge = "🔴 KYC Incomplete" if dt.get("kyc_incomplete") else "🟡 Diligence Required"
                        st.markdown(f"- **{dt['name']}**: Direct {dt['direct_pct']}%, Look-Through {dt['effective_pct']}% — *{badge}*")
                else:
                    st.caption("No parties meet or exceed the 20.0% diligence threshold.")
            with c_tr2:
                st.markdown("##### 🇮🇳 Indian Beneficial-Owner Markers (10%)")
                if last_res.india_bo_markers:
                    for bm in last_res.india_bo_markers:
                        st.markdown(f"- **{bm['name']}**: Effective {bm['effective_pct']}% — *Above the Indian beneficial-owner threshold (info only)*")
                else:
                    st.caption("No parties meet or exceed the 10.0% Indian BO marker.")

        # Side-by-side comparison table
        st.markdown("#### ⚖️ Side-by-Side: Sanctions Aggregation vs Economic Look-Through")
        summary_rows = []
        for s in last_res.look_through_summary:
            status_badge = "🔴 Blocked" if s["is_blocked"] else "🟢 Clear"
            summary_rows.append({
                "Entity / Shareholder": s["name"],
                "Type": s["type"].capitalize(),
                "Jurisdiction": s["country"] or "—",
                "Direct Stake": f"{s['direct_pct']:.1f}%",
                "Look-Through Stake": f"{s['effective_look_through_pct']:.2f}%",
                "Verification": s.get("verification_level", "self_declared"),
                "Sanctions Status": status_badge,
                "List Authority": s["blocked_source"] or "None",
            })
        st.dataframe(summary_rows, use_container_width=True, hide_index=True)

        # Four-Eyes Review Disposition
        st.markdown("#### ✍️ Four-Eyes Compliance Sign-Off")
        c_fe1, c_fe2, c_fe3 = st.columns([1, 1, 1])
        with c_fe1:
            preparer = st.text_input("Preparer Name", value=last_res.disposition.preparer or "Compliance Analyst")
        with c_fe2:
            reviewer = st.text_input("Reviewer Name", value=last_res.disposition.reviewer or "Compliance Officer")
        with c_fe3:
            status_list = ["Draft", "Submitted", "Reviewed", "Closed", "Escalated"]
            curr_st = last_res.disposition.status if last_res.disposition.status in status_list else "Draft"
            status = st.selectbox("Review Status", status_list, index=status_list.index(curr_st))

        st.caption(f"Review-Due Date: **{last_res.disposition.review_due_date}** (Version {last_res.disposition.version})")
        notes = st.text_area("Compliance Comments / Rationale", value=last_res.disposition.notes)

        c_act1, c_act2 = st.columns(2)
        with c_act1:
            if st.button("💾 Save Four-Eyes Sign-Off to Audit Trail", use_container_width=True):
                last_res.disposition.preparer = preparer
                last_res.disposition.reviewer = reviewer
                sep_ok, sep_msg = last_res.disposition.validate_user_separation()
                if not sep_ok:
                    st.error(sep_msg)
                else:
                    last_res.disposition.status = status
                    last_res.disposition.notes = notes
                    UBOEngine().save_ownership_check(last_res)
                    st.success(f"Audit record saved: status '{status}' (Review due {last_res.disposition.review_due_date}).")

        with c_act2:
            if st.button("📦 Generate UBO Evidence Pack (PDF + Excel)", use_container_width=True):
                p_pdf, p_xlsx = UBOEngine().generate_ubo_evidence_pack(last_res)
                st.success(f"Evidence pack generated!\n\n- PDF: `{p_pdf.name}`\n- Excel: `{p_xlsx.name}`")
