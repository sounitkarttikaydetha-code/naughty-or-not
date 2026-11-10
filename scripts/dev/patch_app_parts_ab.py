import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Imports
if "build_13_sections," not in content:
    content = content.replace(
        "    populate_records_cache,\n)",
        "    populate_records_cache,\n    build_13_sections,\n)"
    )

if "ReportGenerationError" not in content:
    content = content.replace(
        "from modules.reporting.generator import generate_reports, generate_raw_reports",
        "from modules.reporting.generator import generate_reports, generate_raw_reports, ReportGenerationError"
    )

# 2. render_full_record_details
old_render_fn = """def render_full_record_details(
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
    p_name = html.escape(str(rec.get("primary_name") or hit.get("primary_name") or hit.get("matched_name") or "—"))
    
    aliases_list = rec.get("aliases") or hit.get("aliases") or []
    if isinstance(aliases_list, list):
        aliases_str = html.escape("; ".join(str(a) for a in aliases_list if a and str(a).strip() not in ["", "-0-"])) or "None recorded"
    else:
        aliases_str = html.escape(str(aliases_list)) or "None recorded"
        
    etype = html.escape(str(rec.get("entity_type") or hit.get("entity_type") or "Organisation"))
    tax_id = rec.get("tax_id") or rec.get("reg_number") or rec.get("id_number") or ""
    type_reg = f"{etype} (Tax ID / Reg: {html.escape(str(tax_id))})" if tax_id else etype
    
    prog = html.escape(str(hit.get("program") or rec.get("program") or rec.get("regime") or "Sanctions List"))
    source_prog = f"{auth_name or src_id} (Program: {prog})"
    
    addrs = rec.get("addresses") or hit.get("addresses") or []
    if isinstance(addrs, list):
        addr_str = html.escape("; ".join(str(a) for a in addrs if a and str(a).strip() not in ["", "-0-"])) or "None recorded"
    else:
        addr_str = html.escape(str(addrs)) or "None recorded"
        
    verif_date = hit.get("publication_date") or rec.get("publication_date") or "2026-10-27"
    
    if tier == "POTENTIAL_MATCH":
        badge_cls = "badge-red"
        badge_lbl = f"🔴 TIER 1: POTENTIAL_MATCH (Score: {score_val:.2f})"
    elif tier == "POSSIBLE_MATCH_REVIEW":
        badge_cls = "badge-orange"
        badge_lbl = f"🟠 TIER 2: POSSIBLE_MATCH_REVIEW (Score: {score_val:.2f})"
    elif tier == "WEAK_SIMILARITY":
        badge_cls = "badge-yellow"
        badge_lbl = f"🟡 TIER 3: WEAK_SIMILARITY (Score: {score_val:.2f})"
    else:
        badge_cls = "badge-blue"
        badge_lbl = f"ℹ️ TIER 4: SHOWN_FOR_INFORMATION (Score: {score_val:.2f})"
        
    card_html = f\"\"\"
    <div class="full-record-modal-card">
        <div class="full-record-header">
            <span>Full Sanctions Record Details — Official Verification</span>
            <span style="font-size:14px; opacity:0.85;">🔒 Verified Local Record</span>
        </div>
        <div class="full-record-body">
            <div style="margin-bottom:16px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                <span class="{badge_cls}">{badge_lbl}</span>
                <span style="font-size:12px; color:#64748B;">Verification Date: <b>{verif_date}</b></span>
            </div>
            <div class="detail-row"><div class="detail-label">Primary Listed Name:</div><div class="detail-val"><b>{p_name}</b></div></div>
            <div class="detail-row"><div class="detail-label">Source & Program:</div><div class="detail-val">{source_prog}</div></div>
            <div class="detail-row"><div class="detail-label">Record Identifier:</div><div class="detail-val"><code style="background:#F1F5F9; padding:2px 6px; border-radius:3px; color:#0F52BA; font-weight:600;">{html.escape(str(rec_id))}</code></div></div>
            <div class="detail-row"><div class="detail-label">Known Aliases:</div><div class="detail-val">{aliases_str}</div></div>
            <div class="detail-row"><div class="detail-label">Entity Type & Reg:</div><div class="detail-val">{type_reg}</div></div>
            <div class="detail-row"><div class="detail-label">Addresses on Record:</div><div class="detail-val">{addr_str}</div></div>
            <div class="detail-row"><div class="detail-label">Official Publisher URL:</div><div class="detail-val"><a href="{direct_verify_url or '#'}" target="_blank" style="color:#0F52BA; font-weight:600; text-decoration:none;">{direct_verify_url or 'Official Registry'} ↗</a></div></div>
        </div>
    </div>
    \"\"\"
    st.markdown(card_html, unsafe_allow_html=True)
    
    txt_record = format_record_as_text(src_id, str(rec_id), rec)
    json_bytes = json.dumps(rec, indent=2, ensure_ascii=False)
    
    c_btn_l, c_btn_r = st.columns([1, 1])
    with c_btn_l:
        key_tag = f"{key_prefix}_{src_id}_{rec_id}" if key_prefix else f"{src_id}_{rec_id}"
        st.download_button(
            "📥 Copy / Download JSON Record",
            data=json_bytes,
            file_name=f"record_{src_id}_{rec_id}.json",
            mime="application/json",
            key=f"dl_rec_json_{key_tag}",
            use_container_width=True,
        )
    with c_btn_r:
        with st.popover("📋 View Structured Details", use_container_width=True):
            st.code(txt_record, language="")"""

new_render_fn = """def render_full_record_details(
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
        badge_lbl = f"🟡 TIER 3: WEAK_SIMILARITY (Score: {score_val:.2f})"
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
            st.code(txt_record, language="")"""

content = content.replace(old_render_fn, new_render_fn)

# 3. Screening Report Generation & Error Handling
old_gen_rep = """        # Generate Reports & Log
        session_manual_checks = st.session_state.manual_checks_saved.get(primary_query, [])
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

        log_search(
            search_type=search_type,
            inputs=inputs_dict,
            source_results=source_statuses,
            report_file_name=pdf_path.name,
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
            "pdf_path": str(pdf_path),
            "excel_path": str(excel_path),
        }"""

new_gen_rep = """        # Generate Reports & Log
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
        }"""

content = content.replace(old_gen_rep, new_gen_rep)

# 4. Screening Download Row & Error Banner
old_dl_row = """        # Download Reports Row
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
                    )"""

new_dl_row = """        # PDF Error Fallback Banner & Traceback (Part A6)
        if res.get("pdf_error"):
            st.error("⚠️ PDF report generation failed. An Excel report is available below. Copy the technical details below and send them to IT.")
            with st.expander("Technical details for IT (click to copy)", expanded=False):
                err_data = res["pdf_error"]
                tb_txt = f"Inputs:\\n{json.dumps(err_data.get('inputs', {}), indent=2)}\\n\\nError:\\n{err_data.get('message', '')}\\n\\nTraceback:\\n{err_data.get('traceback', '')}"
                st.code(tb_txt, language="")

        # Download Reports Row
        col_d1, col_d2, _ = st.columns([1, 1, 3])
        with col_d1:
            if res.get("pdf_path") and os.path.isfile(res["pdf_path"]):
                with open(res["pdf_path"], "rb") as f:
                    st.download_button(
                        "📥 Download PDF Report",
                        data=f.read(),
                        file_name=Path(res["pdf_path"]).name,
                        mime="application/pdf",
                    )
        with col_d2:
            if res.get("excel_path") and os.path.isfile(res["excel_path"]):
                with open(res["excel_path"], "rb") as f:
                    st.download_button(
                        "📥 Download Excel Report",
                        data=f.read(),
                        file_name=Path(res["excel_path"]).name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )"""

content = content.replace(old_dl_row, new_dl_row)

# 5. Raw Search Reports & Error Handling
old_raw_gen = """                    raw_pdf, raw_excel = generate_raw_reports(
                        query=raw_q.strip(),
                        options={
                            "match_option": match_opt,
                            "search_field": search_fields,
                            "fold_accents": fold_accents,
                            "sources": selected_raw_sources,
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
                    st.session_state.raw_search_results = raw_res"""

new_raw_gen = """                    raw_pdf = None
                    raw_excel = None
                    raw_pdf_error = None
                    try:
                        raw_pdf, raw_excel = generate_raw_reports(
                            query=raw_q.strip(),
                            options={
                                "match_option": match_opt,
                                "search_field": search_fields,
                                "fold_accents": fold_accents,
                                "sources": selected_raw_sources,
                            },
                            results=raw_res.get("results", []),
                        )
                    except ReportGenerationError as rge:
                        raw_excel = rge.excel_path
                        raw_pdf_error = {
                            "message": rge.message,
                            "traceback": rge.details,
                            "query": raw_q.strip(),
                        }
                        logger.error("Raw search PDF generation failed: %s", rge.message)

                    rep_name = raw_pdf.name if raw_pdf else (raw_excel.name if raw_excel else "FAILED")
                    log_raw_search(
                        query=raw_q.strip(),
                        options={
                            "match_option": match_opt,
                            "search_field": search_fields,
                            "fold_accents": fold_accents,
                            "sources": selected_raw_sources,
                        },
                        result_count=raw_res.get("total_matches", 0),
                        report_file_name=rep_name,
                    )
                    raw_res["pdf_path"] = str(raw_pdf) if raw_pdf else None
                    raw_res["excel_path"] = str(raw_excel) if raw_excel else None
                    raw_res["pdf_error"] = raw_pdf_error
                    st.session_state.raw_search_results = raw_res"""

content = content.replace(old_raw_gen, new_raw_gen)

# 6. Raw Search Download Row & Error Banner
old_raw_dl = """        # Download Report Buttons
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
                    )"""

new_raw_dl = """        # PDF Error Fallback Banner & Traceback (Part A6)
        if rr.get("pdf_error"):
            st.error("⚠️ PDF report generation failed. An Excel report is available below. Copy the technical details below and send them to IT.")
            with st.expander("Technical details for IT (click to copy)", expanded=False):
                err_data = rr["pdf_error"]
                tb_txt = f"Query:\\n{err_data.get('query', '')}\\n\\nError:\\n{err_data.get('message', '')}\\n\\nTraceback:\\n{err_data.get('traceback', '')}"
                st.code(tb_txt, language="")

        # Download Report Buttons
        r_d1, r_d2, _ = st.columns([1, 1, 3])
        with r_d1:
            if rr.get("pdf_path") and os.path.isfile(rr["pdf_path"]):
                with open(rr["pdf_path"], "rb") as f:
                    st.download_button(
                        "📥 Download Text Search PDF",
                        data=f.read(),
                        file_name=Path(rr["pdf_path"]).name,
                        mime="application/pdf",
                        key="raw_pdf_dl",
                    )
        with r_d2:
            if rr.get("excel_path") and os.path.isfile(rr["excel_path"]):
                with open(rr["excel_path"], "rb") as f:
                    st.download_button(
                        "📥 Download Text Search Excel",
                        data=f.read(),
                        file_name=Path(rr["excel_path"]).name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="raw_excel_dl",
                    )"""

content = content.replace(old_raw_dl, new_raw_dl)

# 7. Manual Check Save Regeneration
old_man_regen = """            if st.session_state.last_results and st.session_state.last_results.get("primary_query") == clean_subj:
                res = st.session_state.last_results
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
                res["excel_path"] = str(excel_p)"""

new_man_regen = """            if st.session_state.last_results and st.session_state.last_results.get("primary_query") == clean_subj:
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
                        "message": rge.message,
                        "traceback": rge.details,
                        "inputs": {"name": clean_subj},
                    }"""

content = content.replace(old_man_regen, new_man_regen)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)

print("app.py patched successfully!")
