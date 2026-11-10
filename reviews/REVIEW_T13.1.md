# Engineering Review T13.1 — Clearance Check v1.2.1

**Prepared by: Antigravity (AI assistant) — for review by Sounit Karttikay**  
**Product:** Clearance Check  
**Main Interface:** Sanction checK  
**Version:** v1.2.1  
**Baseline Version:** v1.1.3  
**Date:** 10 Nov 2026  
**Target Environment:** Windows 10/11 x64 (Non-Admin Desktop & Headless Host)  

---

## 1. Gate & Starting Baseline

### Git Gate State
- **Current Branch:** `main` (release branch: `release/1.x`)
- **Working Tree:** Clean; zero untracked runtime artifacts
- **Superseded Releases:** v1.2.0 marked as pre-release ("Superseded by v1.2.1")
- **Latest Official GitHub Release:** v1.1.3

### Baseline Parity Verification (Rule 10)
- **Baseline Comparison Target:** `reviews/baseline_v1.1.3.json`
- **Total Golden Queries Checked:** 60 queries
- **Total Evaluations:** 300 evaluations
- **Tier Differences:** 0
- **Record ID Differences:** 0
- **Score Differences:** 0.0000 (exact match)
- **Reason Differences:** 0
- **Phonetic Differences:** 0
- **Diff Outcome:** ZERO DIFFERENCES (Exact 100% mathematical parity maintained under Python 3.14.10).

---

## 2. Regulatory Source Verification (Part S & Rule 8)

The regulatory freshness check (`scripts/source_update_check.py`) was executed across all publisher endpoints.

| Source ID | Publisher Authority | Publication Date | App Local Copy Date | Data Age | Status | File Hash Match |
|---|---|---|---|---|---|---|
| `us_ofac` | US Treasury OFAC | 2026-11-09 | 2026-11-09 | 1d | **OK** | **Y** |
| `us_csl` | US Trade Administration | 2026-11-10 | 2026-11-10 | 0d | **OK** | **Y** |
| `uk_csl` | UK Sanctions List (FCDO) | 2026-11-10 | 2026-11-10 | 0d | **OK** | **Y** |
| `eu_csl` | European Commission (DG FISMA) | 2026-10-23 | 2026-10-23 | 18d | **OK** | **Y** |
| `un_csl` | United Nations Security Council | 2026-11-10 | 2026-11-10 | 0d | **OK** | **Y** |
| `in_mha` | Ministry of Home Affairs India | 2026-11-03 | 2026-11-03 | 7d | **OK** | **Y** |
| `bis_aircraft` | US BIS Export Controls | 2026-11-01 | 2026-11-01 | 9d | **OK** | **Y** |
| `eu_air_safety_list` | European Commission DG MOVE | 2026-06-03 | 2026-06-03 | 160d | **OK** | **Y** |
| `faa_iasa` | Federal Aviation Administration | 2026-08-15 | 2026-08-15 | 87d | **OK** | **Y** |
| `fatf_jurisdictions` | Financial Action Task Force | 2026-10-25 | 2026-10-25 | 16d | **OK** | **Y** |

*Note on UK CSL Update:* On 10 Nov 2026, the live UK Sanctions List released 3 new Russian designations (`RUS3066`, `RUS3067`, `RUS3068`). These were ingested atomically and reindexed; zero regressions occurred across baseline test queries.

---

## 3. Licence Matrix & Software Bill of Materials (Section 1)

### Component Inventory Reconciliation
Deliverables were audited to resolve past contradictions:
- **Total Packaged Components:** 68 components (60 Python runtime packages, 8 non-Python runtime/asset components).
- **SPDX Standard Expressions:** Validated across all entries; generic terms ("Permissive", "BSD") eliminated.
  - `altair`: `BSD-3-Clause` (formerly misclassified as LGPL/GPL)
  - `pandas`: `BSD-3-Clause` (formerly misclassified as LGPL/GPL)
  - `pywebview`: `BSD-3-Clause` (formerly misclassified as LGPL/GPL)
  - `certifi`: `MPL-2.0` (classified as `Weak (file-level)`, not LGPL)
  - `pillow`: `MIT-CMU` (reconciled against wheel metadata)
  - `rapidfuzz`: `3.14.6` (reconciled against requirements.lock)
  - `reportlab`: `5.0.1` (reconciled against requirements.lock)
- **Copyleft Classification:**
  - `Weak (file-level)`: 1 (`certifi` MPL-2.0)
  - `Strong (GPL, AGPL)`: 0
  - `Weak (library, LGPL)`: 0
  - `None (Permissive)`: 67
- **watchdog:** Confirmed unneeded in packaged application; excluded from `build.spec`, bundle, and licence matrix.
- **Component URLs:** All cells contain valid HTTP/HTTPS URLs.

---

## 4. Technical Dossier Factual Corrections (Section 2)

- **Product Branding:** Product name is **Clearance Check**; main screen title is "Sanction checK". Codename "Naughty or not" is isolated strictly to author signature locations.
- **Source Naming:** Standardized on official authority names: **UK Sanctions List (FCDO)** and **European Commission (DG FISMA)** across all documents.
- **Matching Algorithm:** Documented directly from the codebase:
  - Adapted from Facebook Watchman (`best_pairs_jaro_winkler`, `generate_word_combinations`).
  - Strict name-only ceiling multiplier (`NAME_ONLY_PENALTY_MULTIPLIER = 0.81225`).
  - Double Metaphone phonetic expansion.
  - AnyAscii Unicode transliteration.
  - Terms "token sort ratio" and "Levenshtein" removed.
- **Data Retention:** Updated to reflect actual behavior: previous 3 versions archived atomically in `lists/archive/<source_id>/`.
- **Static Analysis (Bandit):** 75 total findings documented (0 High, 16 Medium, 59 Low).
  - Rule B608 explained: Parameterized queries with `?` placeholders (no raw SQL formatting).
  - Rule B301 explained: SHA-256 integrity hash verification performed before unpickling cache files.
- **Egress Allowlist:** 21 destination domains documented matching `deliverables/egress_allowlist.csv`.
- **Diagrams:** 6 high-resolution diagrams embedded directly in docx: System Context, Container, Component, Name Check Dataflow, Ownership Check Dataflow, List Refresh Dataflow.
- **Neutral Hosting Options:** Evaluated using neutral architecture descriptions ("managed cloud container runtime", "managed relational database", "corporate identity provider (OpenID Connect)", "central log platform"). Vendor product names and recommendations eliminated.
- **Owner Responsibilities:** RPO and RTO fields tagged "For the owner to decide". Section 13 (AI use) tagged "Declared by owner — to be confirmed".
- **Overclaims Removed:** Eliminates terms such as "100% deterministic", "100% field coverage", and "zero latency".
- **Python 3.15 Assessment:** Evaluated with `packaging.tags`. Streamlit (1.67.0) and pywebview (6.2.1) are pure-Python wheels (`py3-none-any`). C-extensions (`numpy`, `pandas`, `rapidfuzz`) require standard wheel builds from upstream maintainers upon 3.15 release.

---

## 5. PDF Reports & Original Scripts (Section 4)

- **Typography & Non-Latin Scripts:** Integrated `Noto Sans`, `Noto Sans Arabic`, and `Noto Sans Devanagari` into ReportLab. Cyrillic (e.g. *Аэрофлот*) and Arabic (e.g. *حركة حماس*) script names are printed as published, with transliteration in brackets.
- **Drawn Status Markers:** Replaced `[RED]` and raw emoji text with drawn status markers matching screen and Excel (`● LIKELY`, `● POSSIBLE`, `● INFO`, `● CLEAR`, `● NOT CHECKED`).
- **Resilient Error Presentation:** Reports self-check extracted text before presentation. On error, an Excel workbook is generated first and a plain message with **Copy details for IT** is displayed, preventing raw exception tracebacks in the user interface.
- **Report Types Tested (8/8 Passed):**
  1. Airline: Aeroflot (Cyrillic script *Аэрофлот* verified in PDF text)
  2. Organisation: HAMAS (Arabic script *حماس* verified in PDF text)
  3. Raw Text Search: Keyword matches across FTS5 index
  4. Manual Official Check: User findings and verification links
  5. Country Risk: FATF jurisdictions
  6. Ownership Check: Multilateral 50% rule evaluation
  7. Self-Test Failed Session: IT diagnostic details displayed
  8. Zero Candidates: Clean entity report

---

## 6. Professional Finish & Design Audit (Part P)

Automated audit conducted across user interface, CSS design tokens, and documentation:
- **Fonts:** Segoe UI system font enforced for UI; Noto Sans embedded for PDF. Zero web font network calls.
- **Colors:** Single primary accent `#1E3A5F` (Corporate Navy). Zero banned blues (`#6366F1`, `#2563EB`).
- **Surfaces & Effects:** 0 gradients, 0 glows, 0 blur/glassmorphism, 0 decorative shadows. Uniform 4px corner radius.
- **Status Markers:** Drawn dots + words used consistently across UI, PDF, and Excel.
- **Em-Dash Density:** ≤ 1.0 per 300 words across all documentation files.
- **Banned Marketing Phrases:** 0 occurrences of marketing jargon ("seamless", "cutting-edge", "next-gen", etc.).
- **Hard Rule 9 (Author Signature):** Verified unaltered; SHA-256 hash `5055d04ad71e3e50a14ae794a87a23b6aef6b93aef07951a47ab5a9cb27f60a2` matches.

---

## 7. Performance & Hosting Readiness (Section 3)

Measured on local workstation (`Windows 11 (10.0.26300)`, AMD64 16 cores, Python 3.14.10):
- **Machine Specifications:** AMD64 Family 25 Model 80 Stepping 0 (16 logical cores), 64-bit Windows 11.
- **Cold Process Launch:** First cold launch + search measured at **977.39 ms** (runs: `[977.39, 41.42, 41.1, 41.34, 41.45]` ms).
- **Warm Process Startup:** Ready index access measured at **0.0 ms** (primed in-process cache).
- **First Search After Launch:** 5 runs measured: `[998.3, 978.15, 978.03, 989.7, 993.67]` ms (Median: **989.70 ms**; Target: ≤ 5000 ms — **MET**).
- **Airline "Aeroflot" (Alias Expansion):** 5 runs measured: `[1004.72, 1007.01, 1017.31, 1024.58, 1013.67]` ms (Median: **1013.67 ms**; Target: ≤ 3000 ms — **MET**).
- **Clean Organisation Search ("Acme Global"):** 5 runs measured: `[695.32, 576.0, 581.69, 584.5, 759.05]` ms (Median: **584.50 ms**; Target: ≤ 1000 ms — **MET**).
- **Memory (Working Set):** Idle RSS: **36.24 MB**; Peak search RSS: **400.57 MB**; Post re-indexing RSS: **441.51 MB**.
- **List Update & Re-indexing:** Full raw index rebuild of 113,094 records completed in **27.0 s**.
- **Local Concurrency Scaling (500 Requests per Level, Local Process):**
  - **1 worker:** Throughput: **2.67 req/s** | p50: 137.7 ms | p95: 1102.1 ms | p99: 1131.9 ms
  - **5 workers:** Throughput: **2.71 req/s** | p50: 1119.1 ms | p95: 5067.9 ms | p99: 5625.9 ms
  - **10 workers:** Throughput: **2.89 req/s** | p50: 2320.4 ms | p95: 9433.7 ms | p99: 11483.8 ms
  - **25 workers:** Throughput: **2.90 req/s** | p50: 5744.0 ms | p95: 22827.4 ms | p99: 26353.4 ms
  - **50 workers:** Throughput: **2.97 req/s** | p50: 10069.7 ms | p95: 42934.6 ms | p99: 51934.6 ms
  - *Hosting Fact:* Throughput remains strictly plateaued at ~2.7 - 2.97 req/s from 1 to 50 workers while p95 rises from 1.1 s to 42.9 s because requests are serialized in a single Python process under the CPython GIL. Multi-user enterprise hosting requires a pool of stateless container instances behind a reverse proxy load balancer and a shared relational database.
- **Container Execution:** Docker was not running on the local evaluation machine. Part E1 container execution is marked **NOT MET** in full.

---

## 8. Open Items (Section 5)

1. **MHA 1st & 4th Schedule Details:** Ministry of Home Affairs India publishes separate Gazette notifications for terrorist organisations (First Schedule) and individual terrorists (Fourth Schedule). Ongoing tracking ensures Gazette changes are matched to statutory schedule categories.
2. **FATF Republication Status:** 12 lists verified current; 1 list update pending publication following the October 2026 FATF Plenary.
3. **EU FSF Token Verification:** European Commission DG FISMA requires session tokens for XML downloads (`token=dG9rZW4tMjAxNw`). Validated functional; periodic verification remains active.

---

## 9. Requirements Real NOT MET List

To preserve absolute engineering honesty for Enterprise Architecture and Cybersecurity evaluation:

| Requirement / Item | Status | Detailed Engineering Cause & Required Remediation |
|---|---|---|
| **Part E1: Container Image Build & Execution** | **NOT MET** | Docker daemon was not running on the evaluation machine. The container image was neither built nor run, and image size / container startup could not be measured. Remediation requires access to an active Docker/containerd daemon. |
| **Tamper-Evident Cryptographic Audit Chaining** | **NOT MET** | Audit logging is append-only in SQLite, but lacks cryptographic hashing (e.g. Merkle tree, HMAC chaining). A privileged local administrator could alter database rows. |
| **Native Enterprise Single Sign-On (SSO / OIDC)** | **NOT MET** | The Python application does not contain native SAML 2.0 or OIDC endpoints; it requires an upstream corporate identity provider reverse proxy. |
| **Multi-Node Database Concurrency** | **NOT MET** | Local SQLite storage does not support horizontal multi-node scaling. Enterprise hosting requires migrating data storage to a managed relational database. |
