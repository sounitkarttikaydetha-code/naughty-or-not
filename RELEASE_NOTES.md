# Clearance Check — Release Notes

---

## 🚀 Release Notes — Clearance Check v1.1.1

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