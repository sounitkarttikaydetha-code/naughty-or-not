# Clearance Check — Product & Technical Specification (v1.1.1)

**Application Name:** Clearance Check  
**Main Screen Title:** Sanction checK  
**Version:** 1.1.1  
**Status:** Pilot — test version  
**Distribution:** Windows 10/11 x64 Standalone Desktop Application (Zero Admin Rights)  

---

## 1. Purpose & Scope

Clearance Check is a unified desktop sanctions screening and beneficial ownership analysis engine (Status: Pilot — test version). It provides compliance officers with a single interface to evaluate individuals, corporate entities, aircraft, vessels, countries, and complex multi-tier ownership structures against official global sanctions lists, export controls, and regulatory registers.

All entity matching, phonetic expansion, corporate hierarchy traversal, and report generation execute locally on the analyst's machine with zero outbound network calls during screening. Network interactions are strictly restricted to user-initiated list updates, background source freshness checking (with identifying User-Agent `ClearanceCheck/1.1.1 (+compliance contact)` and conditional HTTP requests), user-assisted manual imports, and optional user-opt-in OpenSanctions API enrichment.

The application operates as a computational compliance screening aid. It flags potential matches and computes statutory ownership thresholds; statutory determinations and regulatory escalations remain the responsibility of the compliance analyst.

---

## 2. Core Functional Modules

### 2.1 Name Check (Screened Search)
- **Entity Types:** Person, Organisation, Airline, Aircraft, Vessel, Country.
- **Lists Screened:**
  - US Treasury OFAC (SDN and SSI lists)
  - US Consolidated Screening List (ITA: BIS, DTC, State)
  - UK Sanctions List (FCDO)
  - European Union Consolidated Sanctions List (EEAS)
  - United Nations Security Council Consolidated List
  - India Ministry of Home Affairs (UAPA Schedules 1, 4, and Unlawful Associations)
  - Aviation restrictions (US BIS Export Restrict Aircraft, EU Air Safety Banned Carriers, FAA IASA Category 2)
- **Matching Tiers & Display Floor:**
  - **Display Floor:** 0.50 (candidates below 0.50 are discarded and not displayed).
  - 🔴 **POTENTIAL_MATCH (0.80 — 1.00):** High match requiring core-name equivalence, exact alias match, exact identifier match, or corroboration upgrade.
  - 🟠 **POSSIBLE_MATCH_REVIEW (0.70 — 0.79):** Moderate match recommended for review (including phonetic matches and person subset matches).
  - ℹ️ **BELOW_THRESHOLD (0.50 — 0.69):** Retained above display floor for analyst information (`Shown for information — below match threshold`).
  - ⚪ **NOT_CHECKED / DISCARDED (< 0.50 / source unavailable):** ⚪ designates an unavailable source or unverified state; it is never used for "no match".
- **Identifier Elevation & Corroboration:**
  - Exact match on passport, national ID, tax ID, or registration number triggers 🔴 `id_match`.
  - SOLAS 7-digit IMO validation via modulus 10 check digit.
  - DOB + Nationality full match upgrades 🟠 to 🔴 `name_dob_nat_match`.
- **Controlled Conflict Downgrades:**
  - 1 clear secondary conflict (DOB or Nationality): candidate downgraded from 🔴 to 🟠 (`conflict_downgrade_1`).
  - 2 clear secondary conflicts (DOB and Nationality): candidate downgraded from 🟠 to ℹ️, and 🔴 to 🟠 (`conflict_downgrade_2`).
  - Records are never hidden and never marked ✅ when a conflict occurs.

### 2.2 Beneficial Ownership & Control (UBO Check)
- **Multi-Regime Statutory Aggregation:**
  - **US OFAC 50% Rule (FAQs 399, 401 Examples 1–3):**
    - Aggregation of direct and indirect holdings owned by blocked persons.
    - Multi-tier subsidiary pass-through: Intermediate entities >=50% blocked are treated as 100% blocked downstream.
    - Non-blocked intermediate entities (<50% blocked) do not pass through blocked status.
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
  - Every holder whose direct or effective holding is >=20% is flagged for enhanced due diligence (`ubo.diligence_trigger_pct = 20`).
  - Any holder at >=20% with incomplete KYC (missing DOB or identification) is flagged `KYC incomplete`.
- **Structural Integrity & Traceability:**
  - Cycle detection (Tarjan / DFS) preventing infinite loops.
  - Shortfall detection: Shortfall below 100% displayed as `Undisclosed ownership: X%`.
  - Dependence warning: Triggers `Result depends on undisclosed X%` when undisclosed equity could alter statutory block determinations.
  - Nominee look-through & natural person resolution: Intermediate corporate wrappers traversed to ultimate beneficial individuals, flagging `Ultimate owner not identified` when chains do not terminate in natural persons.
  - Senior managing official fallback: Identified when no natural person exceeds ownership thresholds.
  - Trusts: Evaluates settlors, trustees, protectors, and beneficiaries.
- **Workflow, Import/Export & Audit:**
  - Standardized 7-sheet Excel workbook (`ownership_template.xlsx`) with openpyxl data validation dropdowns (`Instructions`, `Counterparty`, `Parties`, `Holdings`, `Control`, `Key_Persons`, `Documents`).
  - Word (`.docx`) table parser.
  - User mapping discovery (`~/.clearance_check/import_mappings/`) with SHA-256 fingerprinting.
  - Four-eyes lifecycle: Status progression (Draft → Submitted → Reviewed → Closed / Escalated) enforcing user separation (reviewer must differ from preparer).
  - Review due date tracking (12 months standard, 6 months if risk flags present).
  - Evidence Pack generation: Bundles complete JSON audit trace, XLSX ownership hierarchy with Results/Regime_Verdicts sheets, and signed PDF compliance dossier.

### 2.3 Country Check
- **Territorial Sanctions Analysis:**
  - **Cuba (CU), Iran (IR), North Korea (KP):** Comprehensive multilateral embargoes.
  - **Syria (SY):** US comprehensive trade embargo revoked effective 1 July 2025 (E.O. 14312); targeted authority continues under Providing Assistance and Aid to Regional Security in Syria (PAARSS) and 31 CFR Part 542. UK, EU, and UN sanctions remain active.
  - **Russia (RU):** US sanctions are selective (extensive), not a countrywide blanket embargo; comprehensive territorial embargoes apply to Crimea, Donetsk, Luhansk, Kherson, Zaporizhzhia regions of Ukraine. Extensive sectoral, financial, and price-cap sanctions.
  - **Selective Regimes:** Belarus (BY), Myanmar (MM), Venezuela (VE), Zimbabwe (ZW), Sudan (SD).
- **Official Documentation:** Every regime entry includes official publisher `source_url` and `verification_date: "2026-10-27"` across US, UK, EU, and UN authorities.
- **Integrated Risk Factors:** FATF Call for Action (Black) and Monitored (Grey) lists, EU Air Safety banned states, and EAR Country Groups.
- **Audit Logging:** Dedicated `mode = 'country'` records in local SQLite trail.

### 2.4 Text Search (Keyword Exploration)
- High-performance SQLite FTS5 full-text search across 12 indexed sanctions sources (40,400+ indexed sanctions records and aviation registries):
  1. `us_ofac` (SDN & SSI)
  2. `us_csl` (Consolidated Screening List)
  3. `uk_csl` (UK Sanctions List - FCDO)
  4. `eu_csl` (EU Consolidated List - EEAS)
  5. `un_csl` (UNSC Consolidated List)
  6. `bis_aircraft` (US BIS Export Restrict Aircraft)
  7. `eu_air_safety` (EU Air Safety List)
  8. `faa_iasa` (FAA IASA Country Categories)
  9. `in_mha_first_schedule` (Banned Terrorist Organizations)
  10. `in_mha_fourth_schedule` (Terrorist Individuals)
  11. `in_mha_unlawful_assoc` (Unlawful Associations)
  12. `fatf_jurisdictions` (High-Risk & Monitored Jurisdictions)

### 2.5 Start-up Self-Test Framework
- **Layer 1 (Engine Canary):** 20 invariant test cases evaluated in-memory; hard-fails with `ENGINE_CANARY_FAILURE` banner if matching logic is inconsistent.
- **Layer 2 (Self-Sampled Probes):** Samples 5 live records from local database and verifies 3 nonsense strings return no false alarms.
- **Layer 3 (Named Probes):** Checks 10 benchmark designated entities for drift or list updates, reporting soft notes without blocking application startup.
- Execution budget: Entire self-test runs in <= 2.0s (measured ~166ms).

### 2.6 Source Updating Engine (v1.1.1 Overhaul)
- **Background Refresh Worker:** Periodic daemon checks for expired lists past 24 hours, with initial 5-second warmup delay.
- **User-Assisted Import:** When automated access is blocked (HTTP 403 / Cloudflare bot protection), Sources panel offers "Open official page" and "Import downloaded file". Validates schema, format, record counts, and publication date; creates atomic 3-version archives; and logs provenance in `source_events`.
- **FATF Plenary Calendar Rule:** Recognizes that FATF lists change only post-plenary (February, June, October). Lists remain current between plenaries, triggering update alerts only post-plenary.
- **Windows System Truststore:** Injects `truststore` into SSL context for corporate certificate store compatibility, while strictly maintaining verification.
- **Honest User-Agent:** Identifying User-Agent `ClearanceCheck/1.1.1 (+compliance contact)` with conditional HTTP headers (`If-Modified-Since`, `If-None-Match`).

---

## 3. Reporting & Text Formatting Standards

- **PDF Generation (ReportLab):**
  - Standard portrait A4 printable width: strictly 523pt (with 36pt margins).
  - Cell rendering uses `Paragraph` flowables with soft zero-width space wrapping on delimiter characters (`/ ; , - _`).
  - Table headers repeat on every page (`repeatRows=1`).
- **Excel Generation (openpyxl):**
  - All cells enabled with `wrap_text=True` and automatic row height adjustments.
- **Branding Uniformity:** Application titles read from `config/branding.yaml` (`Sanction checK`).
- **Signature Integrity (Rule 9):** Author easter egg signature preserved character-for-character across all 5 mandatory locations.

---

## 4. Security, Privacy & Local Storage

- **Privacy-First Local Execution:** Zero outbound network socket connections during standard screening, UBO calculations, and report generation.
- **Local Datastore:** Stored in `%LOCALAPPDATA%\ClearanceCheck\`:
  - `logs/screening.db`: SQLite database with WAL journaling (append-only audit trails).
  - `reports/`: PDF and Excel compliance exports.
- **Optional OpenSanctions API:** Disabled by default; activated only by explicit user opt-in with local API key storage.