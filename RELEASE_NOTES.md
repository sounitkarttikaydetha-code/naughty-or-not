# Clearance Check — Release Notes

---

## 🚀 Release Notes — Clearance Check v1.1.2

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
- **MHA Discovery & Official Mirror:** Automated discovery of UAPA First Schedule, Fourth Schedule, and Unlawful Associations lists from the CTCR landing page table, with official ia NIA (MHA) secondary mirror fallback and e-Gazette post-copy watcher.
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
- **Evidence Pack Terminology:** Replaced 'signed PDF' with 'cryptographically hashed Evidence Pack'.
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

### 🌟 What's New in v1.1.1

#### 1. Complete Beneficial Ownership & Control (UBO) Suite (45/45 Requirements)
- **7-Sheet Standardized Excel Workbook (`ownership_template.xlsx`):** Pre-formatted template with built-in data validation dropdowns across seven dedicated sheets (`Instructions`, `Counterparty`, `Parties`, `Holdings`, `Control`, `Key_Persons`, `Documents`).
- **Round-Trip Import & Export:** Full workbook export includes calculated `Results` and `Regime_Verdicts` sheets. Importing an exported workbook reproduces the identical ownership hierarchy.
- **Word (`.docx`) Table Import:** Direct import of corporate ownership structures from Microsoft Word documents via `python-docx`.
- **User Import Mapping Discovery:** Automatically discovers format mappings from both the application catalog and the analyst's local directory (`~/.clearance_check/import_mappings/`), tracking SHA-256 fingerprints in compliance reports.
- **Multi-Regime Statutory Verdicts:**
  - **US OFAC 50% Rule:** Strict aggregation across blocked entities and multi-tier subsidiary pass-through.
  - **EU Ownership & Control:** 50% or more proprietary ownership with configurable aggregation (default ON) and appointment/control criteria.
  - **UK OFSI Ownership & Control:** More than 50% shareholding, board majority appointment, and dominant influence; individual statutory results displayed alongside aggregated conservative results.
  - **India PMLA & SBO:** 10% beneficial ownership marker identifying significant beneficial owners under Indian regulatory frameworks.
- **Enhanced Due Diligence & Gold-Standard Compliance:**
  - **20% Diligence Trigger:** Flags any party whose direct or effective holding meets or exceeds 20% (Adani Airports Sanctions Compliance SOP), with automatic `KYC incomplete` warnings for missing identification.
  - **Nominee Look-Through & Natural Person Resolution:** Traverses nominee agreements and intermediate corporate wrappers to identify ultimate natural persons, flagging `Ultimate owner not identified` when chains do not terminate in natural persons.
  - **Circular Shareholding Detection:** Employs Tarjan's cycle detection algorithm to identify circular shareholding rings without infinite loops.
  - **Undisclosed Ownership Shortfalls:** Explicitly calculates equity shortfalls (`Undisclosed ownership: X%`) and alerts analysts with `Result depends on undisclosed X%` when undisclosed equity could alter statutory block determinations.
  - **Trusts & Senior Managing Officials:** Complete evaluation of trust structures (settlors, trustees, protectors, beneficiaries) and senior managing official fallbacks.
- **Four-Eyes Governance & Evidence Pack:**
  - Lifecycle state progression (`Draft` → `Submitted` → `Reviewed` → `Closed` / `Escalated`) enforcing strict user separation (reviewer must differ from preparer).
  - Review due date tracking (12 months standard, 6 months for flagged risk structures).
  - Single-click Evidence Pack generation exporting a bundled package containing the complete JSON audit trail, XLSX ownership hierarchy, and signed PDF compliance dossier.

#### 2. Source Updating Overhaul & User-Assisted Ingestion
- **Automated Background Refresh Worker:** Background thread continuously checks for expired sources past 24 hours, with an initial 5-second warmup check ensuring non-blocking startup.
- **User-Assisted Import for Protected Sources:** When automated publisher downloads are refused (HTTP 403 or Cloudflare bot protection, such as FATF), the Sources panel surfaces **"Update needs your help"** with one-click navigation to the official portal and verified file import. Imports validate schema, record counts, and dates, maintaining 3-version atomic rollback archives and logging provenance to `source_events`.
- **FATF Plenary Calendar Rule:** Embeds the FATF plenary cycle (February, June, October). Lists are recognized as current between plenaries, raising an update alert only immediately following a plenary session.
- **Windows System Truststore (`truststore`):** Injects native Windows certificate store validation for reliable enterprise SSL verification, maintaining strict certificate validation at all times.
- **Honest User-Agent:** Identifying requests sent via `ClearanceCheck/1.1.1 (+compliance contact)` with conditional HTTP headers (`If-Modified-Since`, `If-None-Match`).

#### 3. Country Engine Data Corrections
- **Syria (SY):** Corrected US sanctions profile to reflect the formal revocation of the comprehensive Syria sanctions programme effective July 1, 2025 (E.O. 14312). Targeted designations continue under the Providing Assistance and Aid to Regional Security in Syria (PAARSS) programme and 31 CFR Part 542.
- **Russia (RU):** Corrected US sanctions categorization to "Selective (extensive)", acknowledging that sectoral prohibitions and designations apply rather than a countrywide blanket embargo. Territorial comprehensive embargoes remain strictly enforced on Crimea, Donetsk, Luhansk, Kherson, and Zaporizhzhia.
- **Publisher Traceability:** Added official publisher `source_url` and `verification_date: "2026-10-27"` to every country regime entry across US, UK, EU, and UN authorities.

#### 4. Specification & Dossier Corrections
- **Display Floor:** Corrected documentation to reflect the actual display floor of 0.50. Candidates below 0.50 are discarded; candidates from 0.50 to 0.69 are retained as ℹ️ (`Shown for information — below match threshold`).
- **⚪ Symbol Meaning:** Clarified that ⚪ designates an unavailable source or unverified state; it is never used for "no match".
- **Conflict Downgrades:** Confirmed controlled single-tier downgrade rules (1 conflict: 🔴 → 🟠; 2 conflicts: 🟠 → ℹ️, 🔴 → 🟠).
- **Text Search Source Count:** Updated raw search index documentation to reflect all 12 indexed sources in SQLite FTS5.
- **Status & Network Claims:** Standardized product status to "Pilot — test version" with an accurate network statement reflecting local execution alongside user-initiated updates and opt-in OpenSanctions.

---

## 🌟 Release Notes — Clearance Check v1.1.0

**Release Date:** October 28, 2026  
**Application Title:** Sanction checK  
**Version:** 1.1.0  
**Status:** Pilot — test version  
**Baseline:** v1.0.4  

### Highlights & Key Capabilities

- **Beneficial Ownership & Control (UBO) Screening:** Initial implementation of US OFAC 50% Rule, EU Ownership & Control, and UK OFSI Sanctions Regulations, with parallel economic look-through percentages and four-eyes review logging.
- **Comprehensive Country Check:** Screening across comprehensive and selective sanctions regimes, FATF lists, EU Air Safety bans, FAA IASA Category 2 restrictions, and EAR Country Groups.
- **Three-Layer Start-up Self-Test:** Layer 1 Engine Canary (20 invariant tests), Layer 2 Self-Sampled Probes, and Layer 3 Named Probes ensuring operational integrity in under 200 ms.
- **Advanced Matching & Identifier Corroboration:** Exact identifier elevation to Tier 1 (🔴), SOLAS IMO check digit validation, DOB + Nationality corroboration upgrades, and conflict downgrades.
- **Modernized User Interface & Accessibility:** Local Inter typeface, WCAG AA compliant contrast palette, compact results view with full record inspection, and wrap-protected PDF/Excel reporting.