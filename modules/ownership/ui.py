"""
Streamlit UI Component for Beneficial Ownership & Control (T11 Part E).
Renders the 'Ownership check' tab:
  - Target entity input and template download
  - File upload (Excel/CSV) & manual node editor
  - Multilateral sanctions evaluation cards (OFAC 50%, EU, UK)
  - Economic look-through vs legal aggregation comparison
  - Four-eyes workflow disposition
"""

import io
from pathlib import Path
from typing import List, Optional
import streamlit as st

from modules.ownership.engine import UBOEngine
from modules.ownership.importer import parse_ownership_table
from modules.ownership.models import FourEyesReview, OwnershipNode, UBOResult

TEMPLATE_PATH = Path(__file__).resolve().parent.parent.parent / "templates" / "ownership_template.xlsx"


def render_ownership_tab():
    """Render the Ownership Check tab."""
    st.markdown("### 🏢 Beneficial Ownership & Control (UBO) Screening")
    st.caption(
        "Multilateral 50% Rule and Control analysis covering US OFAC (FAQs 399, 401), "
        "EU Council Regulations, and UK OFSI Sanctions Regulations. 100% offline; zero data egress."
    )

    # Top action bar: Template download and sample loader
    c_top1, c_top2 = st.columns([1, 1])
    with c_top1:
        if TEMPLATE_PATH.exists():
            with open(TEMPLATE_PATH, "rb") as tf:
                st.download_button(
                    "📥 Download Excel Template",
                    data=tf.read(),
                    file_name="clearance_check_ownership_template.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
    with c_top2:
        if st.button("📋 Load Example: OFAC FAQ 401 Multi-Tier Structure", use_container_width=True):
            st.session_state["ubo_target_name"] = "Petrochemical Supply Corp"
            st.session_state["ubo_nodes"] = [
                OwnershipNode(name="Alpha Holdings Ltd", ownership_pct=50.0, entity_type="company", notes="Direct 50% owner"),
                OwnershipNode(name="Independent Co", ownership_pct=50.0, entity_type="company", user_override="CLEAR", notes="Co-investor"),
                OwnershipNode(name="Sberbank", ownership_pct=60.0, parent_name="Alpha Holdings Ltd", entity_type="company", notes="UBO holding 60% of Alpha Holdings"),
                OwnershipNode(name="Private Equity Fund", ownership_pct=40.0, parent_name="Alpha Holdings Ltd", entity_type="company", user_override="CLEAR"),
            ]
            st.rerun()

    st.divider()

    # Target entity input
    target_name = st.text_input(
        "Target Counterparty Name (Entity Being Evaluated)",
        value=st.session_state.get("ubo_target_name", ""),
        placeholder="e.g. Petrochemical Supply Corp",
    )
    st.session_state["ubo_target_name"] = target_name

    # Input method tabs
    in_tab_upload, in_tab_table = st.tabs(["📁 Upload File (Excel / CSV)", "✍️ Quick Table Builder"])

    with in_tab_upload:
        uploaded_file = st.file_uploader(
            "Upload Ownership Table (.xlsx, .csv)",
            type=["xlsx", "csv"],
            key="ubo_file_uploader",
        )
        if uploaded_file is not None:
            nodes, warnings = parse_ownership_table(
                uploaded_file.getvalue(),
                filename=uploaded_file.name,
            )
            for w in warnings:
                st.warning(w)
            if nodes:
                st.session_state["ubo_nodes"] = nodes
                st.success(f"Parsed {len(nodes)} ownership relationships successfully.")

    with in_tab_table:
        st.caption("Review or edit currently loaded ownership entities:")
        current_nodes: List[OwnershipNode] = st.session_state.get("ubo_nodes", [])
        if not current_nodes:
            st.info("No ownership nodes loaded yet. Upload a file above or click 'Load Example'.")
        else:
            table_data = []
            for n in current_nodes:
                table_data.append({
                    "Owner Name": n.name,
                    "Entity Type": n.entity_type,
                    "Direct Ownership %": n.ownership_pct,
                    "Immediate Parent": n.parent_name or "(Target Entity)",
                    "Board Member": "Yes" if n.is_board_member else "No",
                    "Appointment Power": "Yes" if n.has_appointment_power else "No",
                    "Override": n.user_override or "Auto-Screen",
                })
            st.dataframe(table_data, use_container_width=True, hide_index=True)

    st.markdown("<br>", unsafe_allow_html=True)
    btn_screen = st.button("🚀 Screen Corporate Structure & Evaluate Control", type="primary", use_container_width=True)

    if btn_screen:
        nodes_to_screen = st.session_state.get("ubo_nodes", [])
        if not target_name.strip():
            st.error("Please enter a Target Counterparty Name.")
            return
        if not nodes_to_screen:
            st.error("Please provide at least one shareholder or ownership relationship.")
            return

        with st.spinner("Screening every party and calculating multilateral aggregation..."):
            engine = UBOEngine()
            result = engine.evaluate_ownership(
                target_name=target_name,
                nodes=nodes_to_screen,
                auto_screen=True,
            )
            st.session_state["ubo_last_result"] = result

    # Display results if available
    last_res: Optional[UBOResult] = st.session_state.get("ubo_last_result")
    if last_res:
        st.markdown("---")
        st.markdown(f"### 📊 Evaluation Findings: **{last_res.target_name}**")
        st.caption(f"Evaluation completed in {last_res.execution_time_ms:.1f}ms (Local Screening Database)")

        # 3 Verdict Cards
        v_col1, v_col2, v_col3 = st.columns(3)

        with v_col1:
            st.markdown("#### 🇺🇸 US OFAC 50% Rule")
            if last_res.ofac_blocked:
                st.error(f"🔴 **BLOCKED**\n\nAggregate: **{last_res.ofac_aggregate_pct:.1f}%**")
                st.caption("Owned 50% or more in the aggregate by blocked persons (OFAC FAQs 399, 401).")
            else:
                st.success(f"🟢 **NOT BLOCKED**\n\nAggregate: **{last_res.ofac_aggregate_pct:.1f}%**")
                st.caption("Below 50.0% OFAC aggregation threshold.")

        with v_col2:
            st.markdown("#### 🇪🇺 EU Ownership & Control")
            if last_res.eu_blocked:
                st.error("🔴 **BLOCKED / CONTROLLED**")
                if last_res.eu_ownership_blocked:
                    st.caption("• Proprietary ownership >50%")
                if last_res.eu_control_blocked:
                    st.caption("• Control / appointment power criterion triggered")
            else:
                st.success("🟢 **CLEAR**")
                st.caption("Neither ownership (>50%) nor control criterion triggered.")

        with v_col3:
            st.markdown("#### 🇬🇧 UK Ownership & Control")
            if last_res.uk_blocked:
                st.error("🔴 **OWNED / CONTROLLED**")
                if last_res.uk_condition_1_shares:
                    st.caption("• Condition 1: >50% shares/voting rights")
                if last_res.uk_condition_2_board:
                    st.caption("• Condition 2: Board appointment or majority control")
            else:
                st.success("🟢 **CLEAR**")
                st.caption("Neither shareholding nor board control conditions met.")

        # Path traces and reasons
        if last_res.ofac_path_traces or last_res.eu_reasons or last_res.uk_reasons:
            with st.expander("🔍 Detailed Sanctions Traces & Authority Citations", expanded=True):
                if last_res.ofac_path_traces:
                    st.markdown("**OFAC Blocked Aggregation Traces:**")
                    for tr in last_res.ofac_path_traces:
                        st.markdown(f"- `{tr}`")
                if last_res.eu_reasons:
                    st.markdown("**EU Findings:**")
                    for er in last_res.eu_reasons:
                        st.markdown(f"- {er}")
                if last_res.uk_reasons:
                    st.markdown("**UK OFSI Findings:**")
                    for ur in last_res.uk_reasons:
                        st.markdown(f"- {ur}")

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
                "Designation Status": status_badge,
                "List Authority": s["blocked_source"] or "None",
            })
        st.dataframe(summary_rows, use_container_width=True, hide_index=True)

        # Four-Eyes Review Disposition
        st.markdown("#### ✍️ Four-Eyes Compliance Sign-Off")
        c_fe1, c_fe2, c_fe3 = st.columns([1, 1, 1])
        with c_fe1:
            preparer = st.text_input("Preparer Name", value=last_res.disposition.preparer or "Analyst")
        with c_fe2:
            reviewer = st.text_input("Reviewer Name", value=last_res.disposition.reviewer or "Compliance Manager")
        with c_fe3:
            status = st.selectbox(
                "Review Disposition",
                ["PENDING", "APPROVED", "ESCALATED", "REJECTED"],
                index=["PENDING", "APPROVED", "ESCALATED", "REJECTED"].index(last_res.disposition.status),
            )
        notes = st.text_area("Compliance Comments / Rationale", value=last_res.disposition.notes)

        if st.button("💾 Save Four-Eyes Sign-Off to Audit Trail"):
            last_res.disposition.preparer = preparer
            last_res.disposition.reviewer = reviewer
            last_res.disposition.status = status
            last_res.disposition.notes = notes
            UBOEngine().log_ubo_check(last_res)
            st.success(f"Audit record saved with status '{status}' by {reviewer}.")
