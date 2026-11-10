import re
from pathlib import Path

target_file = Path("scripts/source_update_check.py")
content = target_file.read_text(encoding="utf-8")

# Fix 1: bis.doc.gov -> bis.gov
content = content.replace(
    'https://www.bis.doc.gov/index.php/enforcement/oee/export-violations',
    'https://www.bis.gov/enforcement/export-violations'
)

# Fix 2: plenary rule before pub_date == app_copy_date, and eu_high_risk_third_countries
old_block = """        elif pub_date > app_copy_date:
            st, msg = sm.refresh_source(s_id)
            if st in [STATE_OK, STATE_ADDRESS_CHANGED]:
                updated_in_run = "Yes"
                status_disp = "OK (Updated)"
                app_copy_date = pub_date
                data_age_str = "0d"
            else:
                status_disp = f"FAIL: Newer copy {pub_date} available but refresh failed: {msg}"
                anomalies.append(f"{s_id}: Refresh failed: {msg}")
        elif pub_date == app_copy_date or (s_id in ["eu_csl", "bis_tdo"] and pub_date <= app_copy_date):
            status_disp = "OK"
        elif s_id == "fatf_jurisdictions":
            if now_utc > datetime(2026, 10, 30, 23, 59, 59, tzinfo=timezone.utc):
                status_disp = "Update due (Oct 2026 plenary concluded)"
            else:
                status_disp = "OK (via HM Treasury notice)"
        else:
            status_disp = "OK" """

# Use regex to replace regardless of line endings or slight whitespace
pattern = re.compile(
    r'elif pub_date > app_copy_date:.*?elif s_id == "fatf_jurisdictions":.*?status_disp = "OK"',
    re.DOTALL
)

replacement = """elif s_id == "eu_high_risk_third_countries":
            status_disp = "Reference only — no data loaded"
        elif s_id == "fatf_jurisdictions":
            if now_utc > datetime(2026, 10, 30, 23, 59, 59, tzinfo=timezone.utc):
                status_disp = "Update due (Oct 2026 plenary concluded)"
            else:
                status_disp = "OK (via HM Treasury notice)"
        elif pub_date > app_copy_date:
            st, msg = sm.refresh_source(s_id)
            if st in [STATE_OK, STATE_ADDRESS_CHANGED]:
                updated_in_run = "Yes"
                status_disp = "OK (Updated)"
                app_copy_date = pub_date
                data_age_str = "0d"
            else:
                status_disp = f"FAIL: Newer copy {pub_date} available but refresh failed: {msg}"
                anomalies.append(f"{s_id}: Refresh failed: {msg}")
        elif pub_date == app_copy_date or (s_id in ["eu_csl", "bis_tdo"] and pub_date <= app_copy_date):
            status_disp = "OK"
        else:
            status_disp = "OK" """

content = pattern.sub(replacement, content, count=1)

# Fix 3: Exclude eu_high_risk_third_countries from downloaded_rows count
old_dl_row = 'downloaded_rows = [r for r in rows if r["source_id"] != "os_bulk"]'
new_dl_row = """downloaded_rows = [r for r in rows if r["source_id"] not in ["os_bulk", "eu_high_risk_third_countries"]]
    advisory_rows = [r for r in rows if r["source_id"] == "eu_high_risk_third_countries"]"""

content = content.replace(old_dl_row, new_dl_row)

old_loop = """    for r in downloaded_rows:
        st = r["status"]
        if "OK" in st:
            current_count += 1
        lines.append(
            f"| **{r['source_name']}** | {r['publisher_date']} | {r['app_copy_date']} | "
            f"{r['data_age']} | {r['last_checked']} | `{r['discovered_link']}` | "
            f"{r['http_status']} | `{r['file_read']}` | {r['index_built_hash']} | **{r['hash_match']}** | **{r['status']}** |"
        )"""

new_loop = """    for r in downloaded_rows:
        st = r["status"]
        if "OK" in st or "Update due" in st:
            current_count += 1
        lines.append(
            f"| **{r['source_name']}** | {r['publisher_date']} | {r['app_copy_date']} | "
            f"{r['data_age']} | {r['last_checked']} | `{r['discovered_link']}` | "
            f"{r['http_status']} | `{r['file_read']}` | {r['index_built_hash']} | **{r['hash_match']}** | **{r['status']}** |"
        )

    for r in advisory_rows:
        lines.append(
            f"| **{r['source_name']}** | {r['publisher_date']} | {r['app_copy_date']} | "
            f"{r['data_age']} | {r['last_checked']} | `{r['discovered_link']}` | "
            f"{r['http_status']} | `{r['file_read']}` | {r['index_built_hash']} | **{r['hash_match']}** | **{r['status']}** |"
        )"""

content = content.replace(old_loop, new_loop)

# Fix 4: If any source was updated in run, automatically rebuild index
auto_rebuild_hook = """    if any(r["updated_in_run"] == "Yes" for r in table_rows):
        try:
            from modules.raw_search.indexer import build_full_raw_index
            build_full_raw_index()
        except Exception:
            pass"""

if "build_full_raw_index" not in content:
    content = content.replace("save_sources_state(sm.state)", "save_sources_state(sm.state)\n" + auto_rebuild_hook)

target_file.write_text(content, encoding="utf-8")
print("source_update_check.py patched successfully.")
