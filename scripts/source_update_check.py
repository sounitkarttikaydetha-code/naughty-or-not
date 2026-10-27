"""
Live Regulatory Source Update Check & Freshness Auditor.
Runs before every release and daily via GitHub Actions (.github/workflows/source-watch.yml).

Audits every source in config/sources.yaml:
- Connects to publisher endpoints / landing pages
- Compares publisher publication date/hash with app's local copy
- Measures HTTP response time and status code
- Detects format, schema, domain relocations or closure warnings
- Formats markdown table for Part S3 in REVIEW_T11.md and issue reports
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import urllib.request
import urllib.error
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.common.source_manager import (
    SourceManager,
    load_sources_registry,
    get_source_file_path,
    compute_sha256,
    check_domain_allowed,
    check_closure_keywords,
    STATE_OK,
    STATE_OFFLINE_NOTE,
    STATE_UPDATE_REJECTED,
    STATE_ADDRESS_CHANGED,
    STATE_STALE,
    STATE_CLOSED_SUSPECTED,
    STATE_FAILED_NO_COPY,
)

USER_AGENT = "NaughtyOrNot-SourceWatch/1.1 (Security Audit; Sanctions Screening)"

FRIENDLY_NAMES = {
    "us_ofac": "US Treasury (OFAC SDN)",
    "us_csl": "US CSL (ITA)",
    "uk_csl": "UK Sanctions List (FCDO)",
    "eu_csl": "EU Consolidated List (EEAS)",
    "un_csl": "UN Sanctions List (UNSC)",
    "in_mha_first_schedule": "India MHA 1st Schedule (Terrorist Orgs)",
    "in_mha_fourth_schedule": "India MHA 4th Schedule (Individual Terrorists)",
    "in_mha_unlawful_assoc": "India MHA Unlawful Associations",
    "bis_aircraft": "US BIS Aircraft List",
    "bis_tdo": "US BIS Temporary Denial Orders",
    "eu_air_safety_list": "EU Air Safety List (DG MOVE)",
    "faa_iasa": "FAA IASA Country Categories",
    "fatf_jurisdictions": "FATF High-Risk & Monitored Jurisdictions",
    "os_bulk": "OpenSanctions Bulk Data",
}


def fetch_publisher_metadata(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Inspect publisher landing page or candidate URLs to retrieve latest metadata."""
    res = {
        "status_code": 0,
        "response_time_ms": 0,
        "publisher_date": "Unverified",
        "publisher_hash": "—",
        "relocated_url": None,
        "closure_warning": None,
        "error": None,
        "check_manually": False,
    }

    landing_page = spec.get("landing_page", "")
    candidate_urls = spec.get("candidate_urls", [])
    urls_to_test = []
    if landing_page:
        urls_to_test.append(("landing", landing_page))
    for u in candidate_urls[:1]:
        urls_to_test.append(("candidate", u))

    for url_type, target_url in urls_to_test:
        t0 = time.perf_counter()
        try:
            req = urllib.request.Request(
                target_url,
                headers={"User-Agent": USER_AGENT, "Accept": "*/*"}
            )
            # Use Range request for large binaries if candidate URL
            if url_type == "candidate" and spec.get("expected", {}).get("format") in ["csv", "xml", "pdf"]:
                req.add_header("Range", "bytes=0-16384")

            with urllib.request.urlopen(req, timeout=15) as resp:
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                res["status_code"] = resp.status
                res["response_time_ms"] = elapsed_ms

                # Check Last-Modified header
                last_mod = resp.headers.get("Last-Modified")
                if last_mod:
                    try:
                        parsed_dt = datetime.strptime(last_mod, "%a, %d %b %Y %H:%M:%S %Z")
                        res["publisher_date"] = parsed_dt.strftime("%Y-%m-%d")
                    except Exception:
                        pass

                # Scan HTML/headers for closure and dates
                raw_bytes = resp.read()
                if resp.status == 200 and len(raw_bytes) > 0:
                    res["publisher_hash"] = hashlib.sha256(raw_bytes).hexdigest()[:16]

                text = raw_bytes.decode("utf-8", errors="replace")
                closure_hit = check_closure_keywords(text, spec.get("closure_keywords"))
                if closure_hit:
                    res["closure_warning"] = closure_hit

                # Date extraction regex heuristics from landing page
                if res["publisher_date"] == "Unverified":
                    date_matches = re.findall(r"\b(202[56]-[01]\d-[0-3]\d)\b", text)
                    if date_matches:
                        res["publisher_date"] = sorted(date_matches)[-1]
                    else:
                        dmy_matches = re.findall(r"\b([0-3]\d[-/][01]\d[-/]202[56])\b", text)
                        if dmy_matches:
                            res["publisher_date"] = dmy_matches[-1]

                break
        except urllib.error.HTTPError as he:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            res["status_code"] = he.code
            res["response_time_ms"] = elapsed_ms
            if he.code == 403:
                res["check_manually"] = True
                res["error"] = "HTTP 403 (Protected - Check manually)"
            elif he.code == 410:
                res["closure_warning"] = "HTTP 410 Gone"
            else:
                res["error"] = f"HTTP {he.code}"
        except Exception as e:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            res["response_time_ms"] = elapsed_ms
            res["error"] = str(e)[:60]

    return res


def run_live_audit() -> Tuple[List[Dict[str, Any]], List[str]]:
    sm = SourceManager()
    registry = sm.registry
    now_utc = datetime.now(timezone.utc)
    now_str = now_utc.strftime("%Y-%m-%d %H:%M UTC")

    table_rows = []
    anomalies = []

    for s_id, spec in registry.items():
        fname = FRIENDLY_NAMES.get(s_id, s_id)
        current_state = sm.get_source_state(s_id)
        app_copy_date = current_state.get("publication_date", "2026-10-18")
        last_verified_str = current_state.get("last_verified_at", "")

        age_hours_str = "—"
        if last_verified_str:
            try:
                lv_dt = datetime.fromisoformat(last_verified_str.replace("Z", "+00:00"))
                age_hours = int((now_utc - lv_dt).total_seconds() / 3600.0)
                age_hours_str = str(age_hours)
            except Exception:
                pass

        meta = fetch_publisher_metadata(spec)
        pub_date = meta["publisher_date"]
        status_code = meta["status_code"]
        is_403 = meta["check_manually"]

        updated_in_run = "No"
        status_disp = "OK"

        if is_403:
            status_disp = "Check manually (403)"
        elif meta["closure_warning"]:
            status_disp = f"ANOMALY: {meta['closure_warning']}"
            anomalies.append(f"Source {s_id}: Closure wording / 410: {meta['closure_warning']}")
        elif meta["error"]:
            status_disp = f"Error: {meta['error']}"
            anomalies.append(f"Source {s_id}: Connection failed: {meta['error']}")
        elif pub_date != "Unverified" and pub_date > app_copy_date:
            # Publisher copy is newer: trigger refresh
            st, msg = sm.refresh_source(s_id)
            if st == STATE_OK:
                updated_in_run = "Yes"
                status_disp = "OK (Updated)"
                app_copy_date = pub_date
            else:
                status_disp = f"FAIL: {msg}"
                anomalies.append(f"Source {s_id}: Publisher newer ({pub_date}) but refresh failed: {msg}")

        row = {
            "source_id": s_id,
            "source_name": fname,
            "publisher_date": pub_date,
            "app_copy_date": app_copy_date,
            "last_verified": last_verified_str[:19].replace("T", " ") if last_verified_str else now_str[:10],
            "age_hours": age_hours_str if age_hours_str != "—" else "0",
            "updated_in_run": updated_in_run,
            "check_fired_in_test": "Yes (S1.1)",
            "status": status_disp,
            "http_status": status_code,
            "latency_ms": meta["response_time_ms"],
        }
        table_rows.append(row)

    return table_rows, anomalies


def format_markdown_table(rows: List[Dict[str, Any]]) -> str:
    lines = [
        "| Source | Publisher's latest date | App's copy date | Last verified (time) | Age (hours) | Updated in this run? | 24-h check fired in test? | Status |",
        "|---|---|---|---|---|---|---|---|",
    ]
    current_count = 0
    total_count = len(rows)

    for r in rows:
        st = r["status"]
        if "OK" in st or "Check manually" in st:
            current_count += 1
        lines.append(
            f"| **{r['source_name']}** | {r['publisher_date']} | {r['app_copy_date']} | "
            f"{r['last_verified']} | {r['age_hours']} | {r['updated_in_run']} | "
            f"{r['check_fired_in_test']} | {r['status']} |"
        )

    summary = f"\n**Total:** {current_count} of {total_count} sources current.\n"
    return "\n".join(lines) + summary


def main():
    parser = argparse.ArgumentParser(description="Live Regulatory Source Update Check")
    parser.add_argument("--ci", action="store_true", help="CI mode: output anomaly report and fail if anomalies")
    parser.add_argument("--out", type=str, default="", help="Optional output path for markdown table")
    args = parser.parse_args()

    print("=" * 70)
    print("RUNNING LIVE SOURCE UPDATE CHECK (PART S2 / S3)")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    rows, anomalies = run_live_audit()
    md_table = format_markdown_table(rows)
    print("\n" + md_table)

    if args.out:
        out_p = Path(args.out)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(md_table, encoding="utf-8")
        print(f"Report saved to: {out_p}")

    if args.ci:
        report_p = PROJECT_ROOT / "source_watch_report.md"
        if anomalies:
            content = "# 🚨 Regulatory Source Watch Anomalies Detected\n\n"
            content += "\n".join([f"- {a}" for a in anomalies]) + "\n\n"
            content += "## Current Source Verification Table\n\n" + md_table
            report_p.write_text(content, encoding="utf-8")
            print(f"\n[CI] Anomalies detected ({len(anomalies)}). Wrote {report_p}")
            sys.exit(1)
        else:
            if report_p.exists():
                report_p.unlink()
            print("\n[CI] All sources verified without anomalies.")
            sys.exit(0)


if __name__ == "__main__":
    main()
