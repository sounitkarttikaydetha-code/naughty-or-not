# Naughty or not — User Guide

## Overview
**Naughty or not** is a desktop sanctions and compliance screening tool designed for non-technical compliance officers and analysts. It runs completely offline on standard Windows laptops without administrative rights, Docker, or external services.

---

## 1. Quick Start

### Installation
1. Download `NaughtyOrNot_Setup_v1.0.1.exe` and `SHA256.txt` from the private GitHub Releases page.
2. Verify the installer's checksum against `SHA256.txt`.
3. Double-click `NaughtyOrNot_Setup_v1.0.1.exe` to install. The installer installs per-user to `%LOCALAPPDATA%\Programs\NaughtyOrNot`. No administrator password is required.
4. Launch "Naughty or not" from your Start Menu or Desktop.

### First Run
On the first run, the app initializes bundled official sanctions lists and builds the local full-text search index (`raw_index.db`). A progress bar is displayed:
> **"Preparing lists / text search… this happens once"**
Once completed, the main screening interface appears immediately.

---

## 2. Screening Modes

### A. Screen Entity (Fuzzy & Name Matching)
- **Entity Types:** Person, Organisation, Airline, Vessel, Aircraft.
- **Search Query:** Primary legal name, alias, registration number, or identifier.
- **Optional Attributes:** DOB (for persons), Nationality, Registration/Tail (for aircraft), IMO (for vessels).
- **Match Tiers:**
  - 🔴 **POTENTIAL MATCH (Red):** Score $\ge 0.80$. Strong match requiring escalation.
  - 🟠 **POSSIBLE MATCH (Amber):** Score $\ge 0.70$. Plausible similarity requiring analyst review.
  - ⚪ **NO MATCH (Green / Clean):** No candidates reached review thresholds.
  - ℹ️ **Sub-threshold / Grey list:** Scores $\ge 0.50$ shown for transparency under "Candidates below threshold".

### B. Raw Search (Full-Text)
- Search across all raw source text, records, notes, and addresses using SQLite FTS5.
- Enter exact tokens, tail numbers (e.g. `RUS2426`, `VP-BCD`), MSN, or person names.

### C. Manual Check & Verification
- Record manual clearing decisions with analyst notes.
- Log is persisted locally to `%LOCALAPPDATA%\NaughtyOrNot\logs\screening.db`.
- Click "Verify on official source" to cross-check records directly on regulatory portals.

---

## 3. Data Privacy & Compliance
- **100% Offline Default:** All name queries are screened locally in-process. No candidate or screening input ever leaves your machine.
- **OpenSanctions:** Opt-in only. Requires explicitly entering an API key. Uses session credits with masked key display (`...XXXX`).
- **Reports & Audit Trail:** Every search automatically writes an immutable log row and generates an audit-ready PDF/Excel report in `%LOCALAPPDATA%\NaughtyOrNot\reports\`.


---

## 4. Deployment Modes: Installer vs. Portable Mode
- **Production Compliance Screening (Installer):** For regulatory compliance and audit readiness, deploy using the per-user Windows Installer (`NaughtyOrNot_Setup_v1.0.4.exe`). It installs to `%LOCALAPPDATA%\Programs\NaughtyOrNot` and retains audit logs in `%LOCALAPPDATA%\NaughtyOrNot\logs\screening.db` to satisfy long-term compliance record retention mandates.
- **Personal Evaluation (Portable Mode):** The zero-install portable `.zip` (`NaughtyOrNot_v1.0.4_Portable.zip`) is provided strictly for personal evaluation, temporary testing, and offline trials. It can be unpacked into any user folder without installation. Placing a `.portable` marker file inside the application directory directs logs and cache to a local `data/` folder instead of `%LOCALAPPDATA%`.


---

## 5. Comprehensive Record Exposure & 13 Standard Sections (v1.2.0)

When an entity matches a regulatory list, Sanction checK presents complete source record details organized across 13 standard sections:
1. **Header / Identity:** Source authority, primary name, entity type, list publication date, status badge.
2. **Aliases & Alternative Names:** Direct and alternative spellings, transliterations, weak aliases.
3. **Identifiers:** Passports, National IDs, Tax Registration numbers, SOLAS IMO numbers.
4. **Addresses & Locations:** Registered and physical street addresses, cities, countries.
5. **Dates & Places of Birth / Incorporation:** DOBs, POBs, entity incorporation details.
6. **Nationalities & Citizenships:** Current and prior citizenships, jurisdictions of incorporation.
7. **Sanctions Programs & Designations:** Program tags (e.g. `RUSSIA-EO14024`, `UK-SAMLA-2018`).
8. **Legal Basis & Authority References:** Statutory instruments, gazette citations, council regulations.
9. **Positions, Titles & Affiliations:** Board roles, military ranks, public offices.
10. **Vessel & Aircraft Details:** IMO number, MMSI, call sign, gross tonnage, flag, manufacturer serial number (MSN).
11. **Remarks, Reasons & Regulatory Statements:** Full narrative explanation published by regulator.
12. **Other fields (as published):** Dynamic catch-all for any additional raw publisher attributes.
13. **Verification & Audit:** Official regulator verification URL, record cryptographic hash.

### Appendices in Generated Reports
- **PDF Report Appendix F:** Detailed multi-column appendix ("Full records for matches above threshold") containing all populated fields across the 13 standard sections.
- **Excel Report "Full records" Sheet:** A dedicated workbook sheet providing a structured column view of all match details for enterprise data ingestion.

---

## 6. Accessible Functional Status Markers

Sanction checK employs an unambiguous status marker taxonomy meeting WCAG 2.1 Level AA contrast guidelines (minimum 4.68:1 contrast ratio). Symbols are strictly paired with explicit text words:
- `🔴 LIKELY` (Score >= 0.80): High match requiring formal escalation.
- `🟠 POSSIBLE` (Score 0.70 — 0.79): Moderate match requiring analyst review.
- `ℹ️ INFO` (Score 0.50 — 0.69): Sub-threshold candidate shown for complete transparency.
- `✅ CLEAR`: No matching entries identified on screened registers.
- `⚪ NOT CHECKED`: Source list unavailable or offline during screening run.
- `✈️ SAFETY`: Aviation safety restriction identified (EU ASL, FAA IASA, BIS Aircraft).
- `📦 EXPORT CONTROL`: Export control restriction identified (US CSL, BIS TDO).
