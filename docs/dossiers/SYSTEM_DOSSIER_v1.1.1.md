# Clearance Check v1.1.1 — System Architecture Dossier

**Product Name:** Clearance Check  
**Main UI Title:** Sanction checK  
**Version:** 1.1.1  
**Build Target:** Windows 10/11 x64 Standalone Desktop Application  
**Runtime:** Embedded Python 3.12, Streamlit UI, pywebview / Edge WebView2 Shell  
**Status:** Pilot — test version  

---

## 1. System Overview & Privacy-First Architecture

Clearance Check is a desktop compliance screening and beneficial ownership analysis application (Status: Pilot — test version). It operates in a privacy-first, local-execution mode where all entity matching, phonetic expansion, corporate hierarchy traversal, and compliance dossier generation execute entirely on the analyst's machine.

Screening operations perform strictly zero outbound network requests. External network interactions are restricted exclusively to user-initiated list updates, background source freshness checking (with identifying User-Agent `ClearanceCheck/1.1.1 (+compliance contact)` and conditional HTTP headers), user-assisted manual imports, and optional user-opt-in OpenSanctions API enrichment.

```
+-----------------------------------------------------------------------------------+
|                           Streamlit User Interface (Localhost)                    |
|       [Name check]       [Ownership check]       [Country]       [Text search]    |
+-----------------------------------------------------------------------------------+
         |                        |                     |                 |
         v                        v                     v                 v
+------------------+     +------------------+    +--------------+  +----------------+
|  Tiering Engine  |     |   UBO & Control  |    | Country Risk |  | Raw Search Eng |
|  - Token Pass    |     |   - OFAC 50% Rule|    | - Embargoes  |  | - SQLite FTS5  |
|  - Sound-Alike   |     |   - EU Control   |    | - FATF Lists |  | - Disk Index   |
|  - Corroboration |     |   - UK OFSI      |    | - Aviation   |  | - 12 Sources   |
|  - Conflicts     |     |   - India PMLA   |    | - Export Ctl |  |                |
+------------------+     +------------------+    +--------------+  +----------------+
         |                        |                     |                 |
         +------------------------+---------------------+-----------------+
                                  |
                                  v
+-----------------------------------------------------------------------------------+
|                        Embedded Engine & Local Datastores                         |
|  - Python Watchman Engine (Ported Scoring & In-Memory Fuzzy Token Inverted Index)  |
|  - SQLite Database (`%LOCALAPPDATA%\ClearanceCheck\logs\screening.db`):            |
|      * `records` cache (40,400+ indexed sanctions entities)                       |
|      * `screening_logs` (Audit trails with modes: screened, country, ownership)   |
|      * `ownership_checks` & `ownership_parties` (Four-eyes UBO audit history)     |
|      * `manual_checks` (Analyst disposition history)                              |
|      * `source_events` (Provenance and refresh event ledger)                      |
+-----------------------------------------------------------------------------------+
```

---

## 2. Supported Sanctions Regimes & Source Catalog

| Source Identifier | Official Authority / Register | Format | Entity Coverage |
|---|---|---|---|
| `us_ofac` | US Treasury Office of Foreign Assets Control (SDN & SSI) | XML / CSV | Global individuals, banks, corporates, vessels, aircraft |
| `us_csl` | US International Trade Administration (CSL: BIS, DTC, State) | CSV | Global export violations, Entity List, UVL, MEU |
| `uk_csl` | UK Foreign, Commonwealth & Development Office (FCDO) | XML / CSV | UK Sanctions List post-28 Jan 2026 designations |
| `eu_csl` | European External Action Service (EEAS) | XML / CSV | EU Financial Sanctions & Common Foreign Policy |
| `un_csl` | United Nations Security Council Consolidated List | XML | UN Sanctions Committees (ISIL/Al-Qaida, 1718, etc.) |
| `in_mha_first_schedule` | India Ministry of Home Affairs (UAPA 1st Schedule) | PDF | Banned terrorist organizations |
| `in_mha_fourth_schedule` | India Ministry of Home Affairs (UAPA 4th Schedule) | JSON / HTML | Terrorist individuals |
| `in_mha_unlawful_assoc` | India Ministry of Home Affairs (Unlawful Associations) | HTML | Banned unlawful associations and organizations |
| `bis_aircraft` | US Bureau of Industry and Security | PDF / CSV | Export-restricted Russian/Belarusian/Iranian tail numbers |
| `eu_air_safety` | European Commission DG MOVE | PDF | Air carriers banned or restricted from European airspace |
| `faa_iasa` | US Federal Aviation Administration | PDF | International Aviation Safety Assessment Country Categories |
| `fatf_jurisdictions` | Financial Action Task Force | Plenary / Web | Black-list (High-Risk) & Grey-list (Monitored) jurisdictions |

---

## 3. Matching & Tiering Rules Engine

Core matching operates deterministically with standardized threshold boundaries:
- **Display Floor (0.50):** Candidates scoring below 0.50 are discarded and not displayed.
- **0.80 — 1.00:** High match / Potential Match (🔴). Requires core-name equivalence, exact alias match, exact identifier match, or corroboration upgrade.
- **0.70 — 0.79:** Moderate match / Possible Match (🟠). Review recommended. Includes sound-alike phonetic matches and partial person name subsets.
- **0.50 — 0.69:** Low match / Below Threshold (ℹ️). Retained for analyst information (`Shown for information — below match threshold`).
- **< 0.50 / Unavailable:** Discarded / Not Checked (⚪). ⚪ designates an unavailable source or unverified state; it is never used for "no match".

### Special Matching Capabilities & Conflict Rules (v1.1.1)
1. **Identifier Elevation:** Matching a tax ID, national ID, passport, or registration number immediately forces Tier 1 (🔴) with reason `id_match`.
2. **SOLAS IMO Check Digit:** Maritime IMO numbers validated via modulus 10 weighted sum.
3. **Corroboration Upgrades:** If Date of Birth AND Nationality match a candidate, a Tier 2 candidate elevates to Tier 1 (`name_dob_nat_match`).
4. **Controlled Conflict Downgrades:**
   - 1 clear secondary conflict (DOB or Nationality): candidate downgraded from 🔴 to 🟠 (`conflict_downgrade_1`).
   - 2 clear secondary conflicts (DOB and Nationality): candidate downgraded from 🟠 to ℹ️, and 🔴 to 🟠 (`conflict_downgrade_2`).
   - Candidates are never hidden or marked ✅ when a conflict occurs.

---

## 4. Beneficial Ownership & Control (UBO) Engine

Implements multilateral statutory aggregation rules and SOP guidelines (45/45 Requirements Verified):
- **US OFAC 50% Rule (FAQs 399, 401 Examples 1–3):**
  - Direct 50%+ ownership by blocked persons blocks the target entity.
  - Multi-tier indirect pass-through: Intermediate subsidiaries >=50% owned by blocked persons are treated as 100% blocked in subsequent tiers.
  - Non-blocked intermediate subsidiaries (<50% blocked) do NOT pass through blocked status.
  - Distinct blocked persons are aggregated together at each tier.
- **EU Ownership & Control:**
  - Proprietary ownership 50% or more (Council Regulation (EU) 267/2012 / EU Guidance).
  - Aggregation configurable (default ON), with calculation assumption explicitly stated in reports.
  - Control criteria: Right to appoint/remove majority of board; power to exercise decisive influence.
- **UK OFSI Ownership & Control:**
  - Condition 1: Holds >50% shares or voting rights (strictly >50%).
  - Condition 2: Right to appoint or remove majority of board members.
  - Condition 3: Significant control or conduct of affairs per wishes.
  - Individual statutory rule evaluated alongside aggregated (conservative) result.
- **India PMLA & Companies Act SBO (10% Marker):**
  - Identifies all holders exceeding 10% beneficial ownership threshold (`Above the Indian beneficial-owner threshold`).
- **Adani Airports Sanctions Compliance SOP 20% Diligence Trigger:**
  - Direct or effective holders >=20% flagged for enhanced due diligence (`ubo.diligence_trigger_pct = 20`).
  - Holders at >=20% with incomplete KYC flagged `KYC incomplete`.
- **Structural Integrity & Gold-Standard Features:**
  - Cycle detection (Tarjan / DFS) preventing infinite loops.
  - Shortfall detection: Shortfall below 100% displayed as `Undisclosed ownership: X%`.
  - Dependence warning: Triggers `Result depends on undisclosed X%` when undisclosed equity could alter statutory block determinations.
  - Nominee look-through & natural person resolution: Intermediate corporate wrappers traversed to ultimate beneficial individuals, flagging `Ultimate owner not identified` when chains do not terminate in natural persons.
  - Senior managing official fallback: Identified when no natural person exceeds ownership thresholds.
  - Trusts: Evaluates settlors, trustees, protectors, and beneficiaries.
- **Workflow & Evidence Pack:**
  - Standardized 7-sheet Excel template (`ownership_template.xlsx`) with openpyxl data validation dropdowns.
  - Round-trip workbook export (`Results` and `Regime_Verdicts` sheets).
  - Word (`.docx`) table parser.
  - User mapping discovery (`~/.clearance_check/import_mappings/`) with SHA-256 fingerprinting.
  - Four-eyes review: Status progression (Draft → Submitted → Reviewed → Closed / Escalated) enforcing user separation.
  - Review due date tracking (12 months standard, 6 months if risk flags present).
  - Combined Evidence Pack: Bundles complete JSON audit trace, XLSX ownership hierarchy with Results/Regime_Verdicts sheets, and signed PDF compliance dossier.

---

## 5. Country Sanctions & Regulatory Regimes

Multi-regime country screening verified against official government registries as of 2026-10-27:
- **Cuba (CU), Iran (IR), North Korea (KP):** Comprehensive multilateral embargoes.
- **Syria (SY):** US comprehensive trade embargo revoked effective 1 July 2025 (E.O. 14312); targeted authority continues under Providing Assistance and Aid to Regional Security in Syria (PAARSS) and 31 CFR Part 542. UK, EU, and UN sanctions remain active.
- **Russia (RU):** US sanctions are selective (extensive), not a countrywide blanket embargo; comprehensive territorial embargoes apply to Crimea, Donetsk, Luhansk, Kherson, Zaporizhzhia regions of Ukraine. Extensive sectoral, financial, and price-cap sanctions.
- **Selective Regimes:** Belarus (BY), Myanmar (MM), Venezuela (VE), Zimbabwe (ZW), Sudan (SD).
- Every regime entry contains official publisher `source_url` and `verification_date: "2026-10-27"` across US, UK, EU, and UN authorities.

---

## 6. Source Updating Engine (v1.1.1 Overhaul)

- **Background Refresh Worker:** Periodic daemon checks for expired lists past 24 hours, with initial 5-second warmup delay.
- **User-Assisted Import:** When automated access is blocked (HTTP 403 / Cloudflare bot protection), Sources panel offers "Open official page" and "Import downloaded file". Validates schema, format, record counts, and publication date; creates atomic 3-version archives; and logs provenance in `source_events`.
- **FATF Plenary Calendar Rule:** Recognizes that FATF lists change only post-plenary (February, June, October). Lists remain current between plenaries, triggering update alerts only post-plenary.
- **Windows System Truststore:** Injects `truststore` into SSL context for corporate certificate store compatibility, while strictly maintaining verification.
- **Honest User-Agent:** Identifying User-Agent `ClearanceCheck/1.1.1 (+compliance contact)` with conditional HTTP headers (`If-Modified-Since`, `If-None-Match`).

---

## 7. Security, Privacy & Performance Specifications

| Metric / Boundary | Specification | Observed Performance |
|---|---|---|
| Outbound Network Requests | Strictly 0 during standard screening | Verified (0 socket calls) |
| Cold Engine Startup | <= 2.5 seconds | ~1.4 seconds |
| Start-up Self-Test Budget | <= 2.0 seconds | ~166 ms |
| Name Screening Latency | <= 500 ms for multi-word query | 45–120 ms |
| Local Audit Trail | Append-only SQLite WAL | Verified |