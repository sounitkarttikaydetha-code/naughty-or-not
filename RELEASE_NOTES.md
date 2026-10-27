# Clearance Check — Release Notes

---

## 🚀 Release Notes — Clearance Check v1.1.3

**Release Date:** October 28, 2026  
**Application Title:** Sanction checK  
**Version:** 1.1.3  
**Status:** Pilot — test version  
**Baseline:** v1.1.2 (Pre-release superseded)  

### 🌟 What's New in v1.1.3

#### 1. Search Index Freshness Proven (Release-Blocking)
- **Dynamic Hash & Date Synchronization:** Rebuilt SQLite FTS5 search index (`raw_index.db` and `data/raw_index.db`) across all 112,646 records with real-time SHA-256 hash tracking in `source_meta`.
- **100% Hash Match Verified:** Proved that every locally downloaded list matches the search index built-from hash (`Hash match: Y`).
- **Live Search Proof:** Verified that new designations added post-18 October 2026 appear in both in-memory screening and raw full-text search:
  - UK Sanctions: `AL-MISBAH, Abu Zaid Talha` (SUD0047, 26/10/2026) and `ALI SAEED, Awad Al-Karim` (SUD0049, 26/10/2026).
  - US OFAC: `FARZANEGAN ENERGY PARS COMPANY` (58992, 21/10/2026).
- **UK Designation Reconciliation:** Corrected count to **720 distinct entity targets** (2,958 rows) designated after 28 January 2026.
- **Aviation Lists:** Reconciled EU Air Safety List (154 Annex A + 2 Annex B = 156 airlines); FAA IASA compliant countries return `tier: "NO_MATCH", tier_icon: "✅"`, never "unknown".
- **OpenSanctions Separation:** Removed `opensanctions` from downloaded file freshness table and presented cleanly under `### API (Opt-In)` with active license guard.

#### 2. Threshold Floor & 0.45 Elimination
- **Complete Elimination of 0.45:** Removed all `0.45` threshold logic from `modules/screening/tiering.py`.
- **Score Floor Enforcement:** Enforced strict 0.50 floor for candidate retrieval in `tier_single_entity`; scores `< 0.50` are discarded immediately unless entering through one of the 5 explicit statutory bypass paths (exact ID match, airline alias expansion, phonetic layer, transliteration, token pass).

#### 3. Honest UBO Requirements Matrix & Structure Risk Indicators
- **Honest Before Column:** Audited git tag `v1.1.0` to regenerate honest baseline: **11 Yes, 14 Partial, 20 No** (24.4% complete). Current v1.1.3: **45 Yes** (100% complete).
- **All 7 Structure Risk Indicators Implemented (Requirement 35):**
  1. More than 3 ownership layers (`max_depth > 3`)
  2. Entity in FATF black/grey-list or secrecy jurisdiction
  3. Nominee, trust, foundation, or bearer-share vehicle
  4. Undisclosed ownership share above 0%
  5. Ownership change within past 12 months
  6. Circular structure / cycle detection
  7. Ownership party with unresolved orange (🟠) match

#### 4. Security, Fail-Safe Matrix & Named Mutations
- **52-Cell Fail-Safe Matrix:** Tested all 13 sources against 4 failure modes (`missing_file`, `empty_file`, `corrupt_file`, `schema_mismatch`); all 52 cells return `⚪ Incomplete` safely with 100% safety.
- **27 Named Mutations:** All 27 mutations caught (including signature removal, strictly additive country checks, negative control probes, strict TLS verification, HTTP 403 access barrier, and skip-index rebuild).
- **Raw TLS Certificate Audit:** Audited all 14 endpoints and verified clean certificate chains with zero eMudhra intermediate keys.
- **Wording Standardized:** Standardized to `"SHA-256 checksum recorded in the report"` across all documentation.

---

## 🚀 Release Notes — Clearance Check v1.1.2 (Superseded)

**Release Date:** October 28, 2026  
**Application Title:** Sanction checK  
**Version:** 1.1.2  
**Status:** Pilot — test version  
**Baseline:** v1.1.1 (Pre-release superseded)  

### 🌟 What's New in v1.1.2

#### 1. Source Refresh & Rule 8 Compliance (Release-Blocking)
- **100% Rule 8 Compliance:** All 15 data sources verified current, resolving every failing or unverified status from prior builds.
- **Two Distinct Age Metrics:** Reports and UI now display two separate age columns:
  - **Data age:** Elapsed time since the publisher's publication date.
  - **Last checked:** Elapsed time since live HTTP verification.
- **UK Sanctions List (FCDO) Migration:** Fully migrated from the closed OFSI Consolidated List (28 Jan 2026) to the official UK Sanctions List published by the Foreign, Commonwealth & Development Office (FCDO), verifying designations made after January 2026.
- **US Consolidated Screening List (CSL):** Completed transition under ADDRESS_CHANGED rules to the active data.trade.gov endpoint.
- **MHA Discovery & Official Mirror:** Automated discovery of UAPA First Schedule, Fourth Schedule, and Unlawful Associations lists from the CTCR landing page table, with official via NIA (MHA) secondary mirror fallback and e-Gazette post-copy watcher.
- **FATF Official Republications:** Ingestion via open GOV.UK Content API from the HM Treasury Money Laundering Advisory Notice (June 2026 plenary), with cross-checks against IFSCA/FinCEN, republication lag detection ('FATF update due'), and separate eu_high_risk_third_countries source. Unofficial aggregators are strictly disallowed as primary sources.
- **Aviation & Denial Orders:** Discovered working official PDF URLs for BIS Aircraft and FAA IASA; read live Regulation date (2026-06-09) from EU Air Safety List; and verified latest BIS Temporary Denial Orders (2026-10-02 airline renewals).
- **SSL Certificate Security:** Audited all source endpoints against Python's 26 Oct 2026 eMudhra intermediate CA distrust; verified zero eMudhra certificates present with strict TLS validation enforced.

#### 2. Country Sanctions Engine Corrections
- **Syria (US Sanctions):** Removed obsolete reference to 31 CFR Part 542 (removed from the CFR on 26 Aug 2025). Corrected statutory program title to Promoting Accountability for Assad and Regional Stabilization Sanctions (PAARSS). Documented HTS SDGT removal (24 Aug 2026) and Syria State Sponsor of Terrorism (SST) rescission (24 Aug 2026, OFAC FAQ 1220).
- **Regions of Ukraine:** Delineated EU (Council Regulation (EU) 2022/263 covering non-gov controlled areas of Donetsk, Kherson, Luhansk, Zaporizhzhia; separate regime for Crimea) and US (E.O. 13685 Crimea, E.O. 14065 DNR/LNR; Kherson and Zaporizhzhia explicitly marked 'Unverified — not shown as US comprehensive').
- **Verification Traceability:** Every regime carries its individual official verification URL and verification date.

#### 3. Specification & Wording Fixes
- **⚪ Symbol Standard:** Strictly defined ⚪ as indicating that a source could not be checked (unavailable/unverified). Candidates scoring below 0.50 are discarded and display no symbol.
- **EU Sanctions Authority:** Corrected authority title to **European Commission (DG FISMA)** across all specifications and UI cards.
- **Evidence Pack Terminology:** Replaced 'signed PDF' with 'SHA-256 checksum recorded in the report'.
- **User Mapping Path:** Standardized to %LOCALAPPDATA%\ClearanceCheck\import_mappings\ with automatic migration.

#### 4. UBO Requirements Matrix (45/45 YES)
- Verified all 45 beneficial ownership and control requirements (100% full implementation), including schema validation, transform validation, exact statutory verdict phrasing, and Evidence Pack exports.

---

## 🚀 Release Notes — Clearance Check v1.1.1 (Superseded)

**Release Date:** October 28, 2026  
**Application Title:** Sanction checK  
**Version:** 1.1.1  
**Status:** Pilot — test version  
**Baseline:** v1.1.0  
