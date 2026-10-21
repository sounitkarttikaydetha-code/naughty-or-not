# Release Notes — Naughty or not v1.0.2

## Overview & Highlights
Naughty or not v1.0.2 resolves dynamic submodule import handling for PDF report generation and introduces official zero-install portable deployment alongside the Windows installer.

## Key Changes in v1.0.2
- **PDF Report Generator Fix:** Added recursive packaging of all `reportlab` submodules (including `reportlab.lib.colors`, `reportlab.platypus`, and styling modules), resolving runtime import errors when generating screening reports.
- **Standalone Portable `.zip` Release:** Provided zero-install `NaughtyOrNot_v1.0.2_Portable.zip` containing the complete application bundle and pre-seeded sanction lists. Users can unzip anywhere and run `Naughty or not.exe` directly without setup.
- **Zero-Trace "True Portable" Mode:** Placing a `.portable` marker file inside the application directory directs all audit logs, databases, and cached lists to an internal `data/` directory instead of `%LOCALAPPDATA%`, leaving zero footprint on host systems when running from USB drives.

---

# Release Notes — Naughty or not v1.0.1

## Overview & Highlights
Naughty or not v1.0.0 is the official self-contained Windows desktop release for non-technical users. It operates as a native standalone application running in its own window without requiring Docker, Python installations, administrative privileges, or terminal execution.

## Key Changes in v1.0.0
- **In-Process Python Screening Engine:** Replaced external Docker Watchman with an in-process Python screening engine ported directly from Moov Watchman's scoring algorithms, achieving exact parity:
  - 100% of 🔴 and 🟠 candidates match within 0.05
  - Zero missed 🔴 or 🟠 hits across the full test suite
  - 100% of candidates scoring $\ge 0.60$ preserved in top-25 candidate overlap
- **Native pywebview Desktop Window:** App runs in a standalone Microsoft Edge WebView2 window with clean single-instance enforcement and immediate process termination upon window closure (zero orphan processes).
- **Per-User Installer (No Admin Rights):** Inno Setup per-user installer targeting `%LOCALAPPDATA%\Programs\NaughtyOrNot` with Start Menu and Desktop shortcuts.
- **Plain-Language Interface:** Mode tabs renamed to **Name check**, **Text search**, and **Manual check**. Removed all technical jargon ("Watchman", "API", "token", "index", "tier", "core-name") from main screen, translating match reasons into plain English while retaining raw diagnostics in a collapsible Details panel.
- **Secure Key Management:** Optional OpenSanctions API key stored in Windows Credential Manager via `keyring` only when explicitly remembered; otherwise maintained in session memory and never written to disk, logs, reports, or environment files.
- **Fail-Safe Reliability:** All 20/20 list failure combinations (service unavailable, corrupt file, empty file, wrong file format) strictly yield ⚪ (NOT_CHECKED) with an overall **Incomplete** banner — never a false green.
- **User Guide Included:** Multi-page quick-start guide (`USER_GUIDE.pdf`) directly accessible from the app.

## Engine & Architecture
- **Screening Engine:** Local In-Process Python Screening Engine (RapidFuzz 3.14.6 + Jaro-Winkler / Levenshtein scoring)
- **GUI Host:** pywebview 6.2.1 wrapping Streamlit 1.66.0 via Microsoft Edge WebView2 Evergreen Runtime
- **Port Allocation:** Dynamic free port on `127.0.0.1` chosen at start-up
- **SSL / Proxy:** System proxy and corporate certificate store integration via `truststore`

## Verification & Test Results
- **Full Test Suite:** 82/82 tests passing (100%)
- **Golden Regression Set:** 100% passing across all verified queries
- **Fail-Safe Matrix:** 20/20 cells verified ⚪ / Incomplete
- **Mutation Testing:** 6/6 mutation checks passed
- **Release Hygiene:** 100% verified clean (zero secrets, zero logs, zero unbundled databases, zero GPL fonts)

## Bundled Sanction & Regulatory Lists
The installer bundles official seed copies dated **2026-10-18**:
1. **US OFAC SDN & Consolidated** (`us_ofac_sdn.csv`, `us_ofac_alt.csv`) — 2026-10-18
2. **US Consolidated Screening List** (`us_csl.csv`) — 2026-10-18
3. **UK Sanctions List** (`uk_csl.csv`) — 2026-10-18
4. **EU Consolidated Financial Sanctions List** (`eu_csl.xml`) — 2026-10-18
5. **UN Security Council Consolidated List** (`un_csl.xml`) — 2026-10-18
6. **India MHA UAPA First & Fourth Schedules** — 2026-10-01 / 2026-07-04
7. **US BIS Aircraft Potential Violation of EAR** — 2025-10-10
8. **EU Air Safety List (Banned Carriers)** — 2026-06-05
9. **US FAA IASA Category 2 Assessments** — 2026-04-15
10. **FATF High-Risk & Monitored Jurisdictions** — 2026-06-28

## Known Limitations
- **Name-Only Matching:** Screening algorithms evaluate primary and alternate names, known aliases, distinctive words, and secondary identifiers (DOB, nationality, registration IDs). Ownership and control structures (such as the US OFAC 50% rule) are not assessed and must be evaluated under corporate compliance policy.
- **Evaluation Notice:** Test version for internal evaluation. OpenSanctions data is licensed CC BY-NC 4.0; commercial use requires a licence from OpenSanctions.
