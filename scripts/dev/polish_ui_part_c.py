"""
Script to apply Part C UI polish:
Removes decorative emojis from app.py and modules/ownership/ui.py.
Preserves functional markers (🔴, 🟠, ℹ️, ✅, ⚪, ✈️, 📦, 🔍) paired with words.
Preserves Rule 9 author signature character-for-character.
"""
import re

# 1. Polish app.py
with open("app.py", "r", encoding="utf-8") as f:
    app_text = f.read()

replacements_app = [
    ('page_icon="🛡️"', 'page_icon="🔍"'),
    ('"⚠️ **TEST VERSION**', '"**TEST VERSION**'),
    ('badge_lbl = f"🟡 TIER 3: WEAK_SIMILARITY', 'badge_lbl = f"ℹ️ TIER 3: WEAK_SIMILARITY'),
    ('st.error("🚨 **Engine Self-Test FAILED**', 'st.error("**Engine Self-Test Failed**'),
    ('st.caption(f"🛡️ Self-test: Passed', 'st.caption(f"Self-test: Passed'),
    ('with st.expander("ℹ️ Self-test notes"', 'with st.expander("Self-test notes"'),
    ('if st.button("🔑 Change / clear key"):', 'if st.button("Change / clear key"):'),
    ('badge = "🟢" if status == "OK"', 'badge = "✅" if status == "OK"'),
    ('st.link_button("🌐 Open official page"', 'st.link_button("Open official page"'),
    ('f"📥 Import downloaded file ({fname})"', 'f"Import downloaded file ({fname})"'),
    ('if st.button("🔄 Update lists"):', 'if st.button("Update lists"):'),
    ('if st.button("📁 Reports"):', 'if st.button("Reports"):'),
    ('if st.button("📁 Logs"):', 'if st.button("Logs"):'),
    ('if st.button("📖 User Guide (PDF)"):', 'if st.button("User Guide (PDF)"):'),
    ('with st.expander("⚙️ Settings"', 'with st.expander("Settings"'),
    ('st.error("🚨 **ENGINE_CANARY_FAILURE:', 'st.error("**ENGINE_CANARY_FAILURE:'),
    ('st.warning("⚠️ **TEST VERSION — NOT FOR OFFICIAL REGULATORY REPORTING.**', 'st.warning("**TEST VERSION — NOT FOR OFFICIAL REGULATORY REPORTING.**'),
    ('["📄 Text search", "🔍 Name check", "🏢 Ownership check", "📋 Manual check"]', '["Text search", "🔍 Name check", "Ownership check", "Manual check"]'),
    ('["📋 Manual check", "🔍 Name check", "🏢 Ownership check", "📄 Text search"]', '["Manual check", "🔍 Name check", "Ownership check", "Text search"]'),
    ('["🏢 Ownership check", "🔍 Name check", "📄 Text search", "📋 Manual check"]', '["Ownership check", "🔍 Name check", "Text search", "Manual check"]'),
    ('["🔍 Name check", "🏢 Ownership check", "📄 Text search", "📋 Manual check"]', '["🔍 Name check", "Ownership check", "Text search", "Manual check"]'),
    ('banner_text = "⚠️ POSSIBLE MATCH / RISK FLAG — Review and verification required"', 'banner_text = "🟠 POSSIBLE MATCH / RISK FLAG — Review and verification required"'),
    ('banner_text = "⚠️ NO MATCH — This name contains non-Latin characters.', 'banner_text = "ℹ️ INFO — Non-Latin characters detected.'),
    ('st.warning("⚠️ **Sound-alike matching OFF**', 'st.warning("**Sound-alike matching OFF**'),
    ('st.info("💡 **Add DOB / nationality to refine**', 'st.info("**Add DOB / nationality to refine**'),
    ('st.warning(f"⚠️ **Non-Latin Input:**', 'st.warning(f"**Non-Latin Input:**'),
    ('st.info(f"ℹ️ **Transliteration:**', 'st.info(f"**Transliteration:**'),
    ('st.error("⚠️ PDF report generation failed.', 'st.error("PDF report generation failed.'),
    ('"📥 Download PDF Report"', '"Download PDF Report"'),
    ('"📥 Download Excel Report"', '"Download Excel Report"'),
    ("CONFLICT ⚠️", "CONFLICT [ALERT]"),
    ('st.link_button(f"🔗 Verify on {auth_name}"', 'st.link_button(f"Verify on {auth_name}"'),
    ('with st.expander("📋 Show full record"', 'with st.expander("Show full record"'),
    ('with st.expander(f"🔊 Sound-alike matches', 'with st.expander(f"Sound-alike matches'),
    ('f"ℹ️ Show candidates below threshold ({len(below_cands)}) — [{list_id}]"', 'f"Show candidates below threshold ({len(below_cands)}) — [{list_id}]"'),
    ('st.link_button("🔗 Verify on official BIS document"', 'st.link_button("Verify on official BIS document"'),
    ('st.link_button("🔗 Verify on official Aviation authority"', 'st.link_button("Verify on official Aviation authority"'),
    ('st.link_button("🔗 Verify on official FATF website"', 'st.link_button("Verify on official FATF website"'),
    ('with st.expander(f"📋 Prior Manual Verification History', 'with st.expander(f"Prior Manual Verification History'),
    ('st.info("📌 **Text search — results are keyword occurrences', 'st.info("**Text search** — results are keyword occurrences'),
    ('with st.popover("📂 Regulatory Sources to Search ▾"', 'with st.popover("Regulatory Sources to Search ▾"'),
    ('st.form_submit_button("🔎 Search Records"', 'st.form_submit_button("🔍 Search Records"'),
    ('st.warning("⚠️ **Showing top 200 — more may exist; refine the search.**")', 'st.warning("**Showing top 200** — more may exist; refine the search.")'),
    ('"📥 Download Text Search PDF"', '"Download Text Search PDF"'),
    ('"📥 Download Text Search Excel"', '"Download Text Search Excel"'),
    ('st.link_button("🔗 Verify on official source"', 'st.link_button("Verify on official source"'),
    ('with st.expander(f"🕒 Recent manual checks for', 'with st.expander(f"Recent manual checks for'),
    ('with st.expander(f"🏛️ {pub[\'name\']}', 'with st.expander(f"{pub[\'name\']}'),
    ('st.link_button("🌐 Open official search portal"', 'st.link_button("Open official search portal"'),
    ('if st.button(f"💾 Save {pub[\'name\']} Check"', 'if st.button(f"Save {pub[\'name\']} Check"'),
    ('if st.button("💾 Save All Completed Checks"', 'if st.button("Save All Completed Checks"'),
]

for old, new in replacements_app:
    if old in app_text:
        app_text = app_text.replace(old, new)
    else:
        print(f"Warning: pattern not found in app.py: {old[:40]}")

with open("app.py", "w", encoding="utf-8") as f:
    f.write(app_text)
print("app.py polished successfully!")

# 2. Polish modules/ownership/ui.py
with open("modules/ownership/ui.py", "r", encoding="utf-8") as f:
    own_text = f.read()

replacements_own = [
    ('st.markdown("### 🏢 Beneficial Ownership & Control (UBO) Screening")', 'st.markdown("### Beneficial Ownership & Control (UBO) Screening")'),
    ('"📥 Download 7-Sheet Excel Template"', '"Download 7-Sheet Excel Template"'),
    ('if st.button("📋 Load Example: Alpha Ground Services (Worked Example 4)"', 'if st.button("Load Example: Alpha Ground Services (Worked Example 4)"'),
    ('in_tab_upload, in_tab_word, in_tab_mappings = st.tabs(["📁 Excel Upload & Preview", "📄 Word (.docx) Import", "⚙️ Custom Column Mappings"])', 'in_tab_upload, in_tab_word, in_tab_mappings = st.tabs(["Excel Upload & Preview", "Word (.docx) Import", "Custom Column Mappings"])'),
    ('st.markdown("##### ⚠️ Import Preview: Validation Warnings & Fixes")', 'st.markdown("##### Import Preview: Validation Warnings & Fixes")'),
    ('st.markdown("##### 📋 Configured Import Mappings")', 'st.markdown("##### Configured Import Mappings")'),
    ('with st.expander(f"📋 Loaded Holdings & Control Hierarchy', 'with st.expander(f"Loaded Holdings & Control Hierarchy'),
    ('btn_screen = st.button("🚀 Screen Corporate Structure & Evaluate Control"', 'btn_screen = st.button("Screen Corporate Structure & Evaluate Control"'),
    ('st.markdown(f"### 📊 Evaluation Findings:', 'st.markdown(f"### Evaluation Findings:'),
    ('with st.expander("🌳 Interactive Ownership Hierarchy Tree"', 'with st.expander("Interactive Ownership Hierarchy Tree"'),
    ('st.success(f"🟢 **CRITERIA NOT MET**', 'st.success(f"✅ **CLEAR: CRITERIA NOT MET**'),
    ('st.success("🟢 **CRITERIA NOT MET**")', 'st.success("✅ **CLEAR: CRITERIA NOT MET**")'),
    ('st.success("🟢 **No Listed Parties**")', 'st.success("✅ **CLEAR: No Listed Parties**")'),
    ('with st.expander("🔍 Detailed Sanctions Traces & Boundary Notices"', 'with st.expander("Detailed Sanctions Traces & Boundary Notices"'),
    ('st.markdown(f"- ℹ️ *{un}*")', 'st.markdown(f"- ℹ️ INFO: *{un}*")'),
    ('st.warning(f"⚠️ {bf[\'note\']}', 'st.warning(f"{bf[\'note\']}'),
    ('f"⚠️ **Undisclosed Ownership:', 'f"**Undisclosed Ownership:'),
    ('st.markdown("#### 🔍 Compliance Triggers & Markers")', 'st.markdown("#### Compliance Triggers & Markers")'),
    ('st.markdown("##### ✈️ Adani SOP 20% Diligence Triggers")', 'st.markdown("##### ✈️ SAFETY: 20% Diligence Triggers")'),
    ('badge = "🔴 KYC Incomplete" if dt.get("kyc_incomplete") else "🟡 Diligence Required"', 'badge = "🔴 KYC Incomplete" if dt.get("kyc_incomplete") else "ℹ️ INFO: Diligence Required"'),
    ('st.markdown("#### ⚖️ Side-by-Side: Sanctions Aggregation vs Economic Look-Through")', 'st.markdown("#### Side-by-Side: Sanctions Aggregation vs Economic Look-Through")'),
    ('status_badge = "🔴 Blocked" if s["is_blocked"] else "🟢 Clear"', 'status_badge = "🔴 Blocked" if s["is_blocked"] else "✅ CLEAR"'),
    ('st.markdown("#### ✍️ Four-Eyes Compliance Sign-Off")', 'st.markdown("#### Four-Eyes Compliance Sign-Off")'),
    ('if st.button("💾 Save Four-Eyes Sign-Off to Audit Trail"', 'if st.button("Save Four-Eyes Sign-Off to Audit Trail"'),
    ('if st.button("📦 Generate UBO Evidence Pack (PDF + Excel)"', 'if st.button("Generate UBO Evidence Pack (PDF + Excel)"'),
]

for old, new in replacements_own:
    if old in own_text:
        own_text = own_text.replace(old, new)
    else:
        print(f"Warning: pattern not found in modules/ownership/ui.py: {old[:40]}")

with open("modules/ownership/ui.py", "w", encoding="utf-8") as f:
    f.write(own_text)
print("modules/ownership/ui.py polished successfully!")
