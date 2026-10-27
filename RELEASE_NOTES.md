# Release Notes — Naughty or not (Sanction checK)

---

## Release v1.0.4 (Latest Release)

### Overview
Naughty or not v1.0.4 is a production-hardened, high-performance release delivering end-to-end display fit improvements, validated Double Metaphone phonetic matching, comprehensive application stress testing, and structured OpenSanctions bulk and API integration with strict credit limits.

### Highlights & Key Improvements

1. **Display & Visual Ergonomics (T9-1)**
   - **Per-Monitor High-DPI Scaling:** Dynamic work area dimension calculation respecting Windows taskbars and display scaling factors (100%, 125%, 150%, 200%).
   - **Persistent Geometry:** Window dimensions and positions are saved across sessions in `settings.json`.
   - **WCAG 2.1 AA Accessible Status Chips:** Replaced plain emoji markers with distinct, high-contrast accessible chips (`LIKELY`, `POSSIBLE`, `INFO`, `CLEAR`, `NOT CHECKED`, `SAFETY`, `EXPORT CONTROL`, `SOUNDS LIKE`).
   - **Responsive 3-Line Cards:** Fluid card layouts with relative CSS units (`rem`/`em`) eliminating horizontal scrolling across common laptop displays (1366x768 to 4K).

2. **Sound-Alike Phonetic Matching Validation (T9-2)**
   - **Double Metaphone Validation:** Rigorously benchmarked across a 500-pair leave-one-out test achieving **100.0% recall** with phonetic matching enabled.
   - **Clean Noise Guard:** Evaluated against 260 clean international corporate entities resulting in **0 false reds** and zero degradation.
   - **Governance & Transparency:** Dedicated report banner clearly indicates whether phonetic matching was active during screening.

3. **Engine Hardening & Gap Closures (T9-3)**
   - **Sub-Second Screening Latency:** Optimized token similarity caching yielding clean organization screening times well under the 1.0s target (Jaipur International Airport: 786ms; Tata Steel: 176ms; InterGlobe Aviation: 859ms).
   - **FATF Plenary Logic:** Updated statements ensuring current plenary mandates remain active through October 31, 2026.
   - **Ambiguous Airline Alias Safety:** Strictly isolated genuine listings (e.g., Ural Airlines) while capping ambiguous partial matches below red thresholds.
   - **Manual Verification Workflow:** Expanded to 14 structured cards with pre-populated "Not checked" defaults and direct verification URLs.
   - **Extended Mutation Test Suite:** 14/14 automated mutation tests verifying score floor guards, weak-word filters, and alias splitting logic.

4. **Easter Egg Restoration (T9-4)**
   - Restored the vertical scroll easter egg beneath the formal Compliance & Governance section in `README.md` and in `app/about.py`.

5. **OpenSanctions Bulk Data Governance & Synthetic Loader (T10-1 & T10-2)**
   - **Three-Condition Bulk Gate:** Loader strictly refuses to execute unless `OPENSANCTIONS_BULK_ENABLED=true`, a non-empty `OPENSANCTIONS_BULK_PERMISSION_REF` is set, and the user completes the in-app acknowledgement.
   - **Key Independence:** Presence or absence of the API key never enables or affects bulk ingestion.
   - **Synthetic Fixture Benchmarking:** Validated against 1,000 and 50,000 synthetic FollowTheMoney entities with zero memory leakage and sub-second ingestion rates.
   - **Packaged Build Guard:** Rejection of test fixtures in compiled desktop releases.

6. **OpenSanctions API Client & Hard Credit Cap (T10-3)**
   - **Hard Credit Cap:** Enforced `OPENSANCTIONS_TEST_CREDIT_CAP = 15` in configuration; aborts calls before exceeding the limit.
   - **Multi-Query Batching:** Added `match_batch` to screen multiple entities in a single HTTP request with accurate per-query credit accounting.
   - **Persistent Usage Log:** Every API query is logged to `logs/opensanctions_usage.csv` and persists across application restarts.
   - **Mocked Failure Suite:** 13/13 automated mocked tests verifying 401, 403, 429 backoff, network timeouts, corrupt JSON, and budget cap refusal.

7. **Application Stress & Endurance Testing (T10-4)**
   - **500 Sequential Name Checks:** Completed 500 checks in 205.85s with a median latency of 263.38ms, memory growth of only 33.85MB, and a slowdown ratio of 0.961x (zero performance degradation).
   - **Soak Test:** 12 iterations at 5-second intervals with 0 errors, 202 handles (0 handle leak), and 0.02MB memory growth.
   - **100 Report Generations:** Generated 100 PDF and Excel report pairs in 20.77s (median 200.75ms per report pair).
   - **2,000 Malformed Inputs:** Tested empty, whitespace, 500-character, non-Latin, emoji, and SQL/XSS injection probes with **0 crashes, 0 hangs, and 0 false reds without warning**.
   - **Concurrent List Refresh:** In-memory index reloaded in 1,334ms while 180 concurrent searches ran without a single failure.
   - **Force-Close Crash Resilience:** Hard process termination during active SQLite writes recovered seamlessly via WAL mode (`PRAGMA integrity_check: ok`).
   - **Failure Modes:** Single-instance mutex prevented duplicate windows, while low-disk and locked-database scenarios displayed graceful, actionable error messages.

8. **Key Hygiene & Implementation Guides (T10-5 & T10-6)**
   - **Key Hygiene Scan:** Zero leaks across the entire Git commit history, working tree, logs, and reports.
   - **Enable Guide:** Comprehensive step-by-step documentation in `docs/OPENSANCTIONS_ENABLE.md`.

---

## Release v1.0.3

- Introduced master source management in `config/sources.yaml` with automatic list refresh and SHA-256 change detection.
- Added FATF High-Risk and Increased Monitoring regulatory data with 45-day staleness tracking.
- Implemented sub-second engine startup (<0.8s) via hash-keyed disk caching.
- Ported core screening engine to native in-process Python, eliminating all external container dependencies.
- Added 14 automated mutation tests and Docker-native parity verification.

---

## Release v1.0.2

- Implemented standalone Windows packaging via PyInstaller and pywebview (Microsoft Edge WebView2).
- Zero-admin per-user installer (`.exe`) and portable standalone `.zip` distribution.
- Added Windows Single-Instance Mutex and clean child process tree termination.
- Offline data packaging containing pre-indexed sanctions and aviation safety lists.

---

## Release v1.0.1

- Initial release featuring unified screening across US OFAC, US CSL, UK OFSI, EU CSL, and UN Sanctions.
- Core name check, alias splitting, and weak-word filtering logic.
- PDF and Excel export engine.
