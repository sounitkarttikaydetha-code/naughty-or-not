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
