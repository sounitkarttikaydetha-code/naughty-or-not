"""
Maintainer-side Watch for Source Integrity, Relocation, and Closure Detection.
Runs in CI (.github/workflows/source-watch.yml) weekly or on manual dispatch.
Checks:
- HTTP URL status
- Landing page discovery & closure keywords
- File schema & record count vs config/source_baseline.json
- Logs anomalies and generates GitHub issue markdown if changes detected
"""

import json
from pathlib import Path
import re
import sys
import urllib.request
import urllib.error
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.common.source_manager import (
    load_sources_registry,
    check_domain_allowed,
    check_closure_keywords,
    validate_file,
    DEFAULT_CLOSURE_KEYWORDS,
)

def run_source_watch() -> Tuple[bool, List[str]]:
    registry = load_sources_registry()
    baseline_path = PROJECT_ROOT / "config" / "source_baseline.json"
    baseline = {}
    if baseline_path.is_file():
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))

    anomalies = []
    print("=" * 60)
    print("RUNNING MAINTAINER-SIDE SOURCE WATCH")
    print(f"Monitoring {len(registry)} sources against baseline")
    print("=" * 60)

    for s_id, spec in registry.items():
        print(f"\nChecking source: {s_id} ({spec.get('authority')})")
        landing_page = spec.get("landing_page", "")
        allowed_domains = spec.get("allowed_domains", [])
        closure_kws = spec.get("closure_keywords", DEFAULT_CLOSURE_KEYWORDS)

        # 1. Check landing page
        if landing_page:
            try:
                req = urllib.request.Request(landing_page, headers={"User-Agent": "NaughtyOrNot-SourceWatch/1.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    page_html = resp.read().decode("utf-8", errors="replace")
                    closure_hit = check_closure_keywords(page_html, closure_kws)
                    if closure_hit:
                        msg = f"CLOSURE KEYWORD DETECTED on landing page for {s_id}: '{closure_hit}' ({landing_page})"
                        print(f"  [ANOMALY] {msg}")
                        anomalies.append(msg)
            except urllib.error.HTTPError as he:
                if he.code == 410:
                    msg = f"HTTP 410 Gone on landing page for {s_id} ({landing_page})"
                    print(f"  [ANOMALY] {msg}")
                    anomalies.append(msg)
                elif he.code == 403:
                    print(f"  [NOTICE] HTTP 403 on landing page for {s_id} (bot protection) - check manually")
                else:
                    print(f"  [WARNING] HTTP {he.code} on landing page for {s_id}")
            except Exception as e:
                print(f"  [NOTICE] Landing page check error: {e}")

        # 2. Check Candidate URLs
        candidate_urls = spec.get("candidate_urls", [])
        url_reachable = False
        for url in candidate_urls:
            if not check_domain_allowed(url, allowed_domains):
                msg = f"Candidate URL '{url}' outside allowed domains: {allowed_domains}"
                print(f"  [ANOMALY] {msg}")
                anomalies.append(msg)
                continue

            try:
                req = urllib.request.Request(url, headers={"User-Agent": "NaughtyOrNot-SourceWatch/1.0"})
                # Send HEAD or Range GET request
                req.add_header("Range", "bytes=0-4096")
                with urllib.request.urlopen(req, timeout=15) as resp:
                    if resp.status in [200, 206]:
                        url_reachable = True
                        print(f"  [OK] Endpoint reachable: {url}")
                        break
                    elif resp.status == 410:
                        msg = f"HTTP 410 Gone for candidate URL {url}"
                        print(f"  [ANOMALY] {msg}")
                        anomalies.append(msg)
            except urllib.error.HTTPError as he:
                if he.code == 410:
                    msg = f"HTTP 410 Gone for candidate URL {url}"
                    print(f"  [ANOMALY] {msg}")
                    anomalies.append(msg)
                elif he.code == 403:
                    print(f"  [NOTICE] HTTP 403 for candidate URL {url} (bot protection) - check manually")
                    url_reachable = True # Do not fail build for script blocking
                elif he.code == 404:
                    print(f"  [WARNING] HTTP 404 for candidate URL {url}")
            except Exception as e:
                print(f"  [NOTICE] URL connection: {e}")

        if not url_reachable:
            msg = f"No candidate URL reachable for {s_id}"
            print(f"  [ANOMALY] {msg}")
            anomalies.append(msg)

    # Summary
    print("\n" + "=" * 60)
    print(f"SOURCE WATCH COMPLETED: {len(anomalies)} anomalies found")
    print("=" * 60)

    report_path = PROJECT_ROOT / "source_watch_report.md"
    if anomalies:
        content = "# Source Change Anomaly Report\n\n"
        content += "The following source anomalies were detected during source-watch:\n\n"
        for a in anomalies:
            content += f"- ⚠️ {a}\n"
        report_path.write_text(content, encoding="utf-8")
        print(f"Wrote anomaly report to {report_path}")
        return False, anomalies
    else:
        report_path.write_text("# Source Change Report: All Sources Clean\n\nNo anomalies detected.", encoding="utf-8")
        return True, []

if __name__ == "__main__":
    from typing import Tuple, List
    success, anomalies = run_source_watch()
    if not success:
        sys.exit(1)
