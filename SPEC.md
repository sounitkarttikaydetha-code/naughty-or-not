# Clearance Check — Product & Technical Specification (v1.1.0)

**Application Name:** Clearance Check  
**Main Screen Title:** Sanction checK  
**Version:** 1.1.0  
**Owner & Author:** Sounit Karttikay / Compliance Engineering  
**Distribution:** Windows 10/11 x64 Standalone Desktop Application (Zero Admin Rights)  

---

## 1. Purpose & Scope

Clearance Check is a unified desktop sanctions screening and beneficial ownership analysis engine. It provides compliance officers with a single interface to evaluate individuals, corporate entities, aircraft, vessels, countries, and complex multi-tier ownership structures against official global sanctions lists, export controls, and regulatory registers.

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
- **Matching Tiers:**
  - 🔴 **POTENTIAL_MATCH (0.80 — 1.00):** High match requiring core-name equivalence, exact alias match, exact identifier match, or corroboration upgrade.
  - 🟠 **POSSIBLE_MATCH_REVIEW (0.70 — 0.79):** Moderate match recommended for review (including phonetic matches and person subset matches).
  - ℹ️ **BELOW_THRESHOLD (0.60 — 0.69):** Low score preserved for audit information.
  - ⚪ **NO_MATCH (< 0.60):** Discarded without alert.
- **Identifier Elevation & Corroboration:**
  - Exact match on passport, national ID, tax ID, or registration number triggers 🔴 `id_match`.
  - SOLAS 7-digit IMO validation via modulus 10 check digit.
  - DOB + Nationality full match upgrades 🟠 to 🔴 `name_dob_nat_match`.
  - Secondary identifier conflicts apply controlled single-tier downgrades.

### 2.2 Beneficial Ownership & Control (UBO Check)
- **US OFAC 50% Rule (FAQs 399, 401 Examples 1–3):**
  - Aggregation of all direct and indirect holdings owned by blocked persons.
  - Multi-tier subsidiary pass-through: Intermediate entities >=50% blocked are treated as 100% blocked downstream.
  - Non-blocked intermediate entities (<50% blocked) do not pass through blocked status.
- **EU Ownership & Control:**
  - Proprietary ownership >50.0%.
  - Control criterion: appointment power or majority board representation.
- **UK OFSI Ownership & Control:**
  - Condition 1: >50% shares or voting rights.
  - Condition 2: Right to appoint or remove majority of board members.
  - Condition 3: Dominant influence or conduct of affairs per wishes.
- **Side-by-Side Economic Look-Through:** Multiplicative pro-rata breakdown displayed alongside statutory sanctions aggregation.
- **Workflow & Audit:** Four-eyes review indicators (Preparer, Reviewer, Status) logged to local database under `mode = 'ownership'`.

### 2.3 Country Check
- **Territorial Sanctions Analysis:** Comprehensive embargoes (Cuba, Iran, North Korea, Syria, Russia) and selective regimes (Belarus, Myanmar, Venezuela, Zimbabwe, Sudan).
- **Integrated Risk Factors:** FATF Call for Action (Black) and Monitored (Grey) lists, EU Air Safety banned states, and EAR Country Groups.
- **Audit Logging:** Dedicated `mode = 'country'` records in local SQLite trail.

### 2.4 Text Search (Keyword Exploration)
- High-performance SQLite FTS5 full-text search across 40,400+ indexed sanctions records.
- Allows direct raw inspection across all 8 supported source databases without fuzzy match filtering.

### 2.5 Start-up Self-Test Framework
- **Layer 1 (Engine Canary):** 20 invariant test cases evaluated in-memory; hard-fails with `ENGINE_CANARY_FAILURE` banner if matching logic is inconsistent.
- **Layer 2 (Self-Sampled Probes):** Samples 5 live records from local database and verifies 3 nonsense strings return no false alarms.
- **Layer 3 (Named Probes):** Checks 10 benchmark designated entities for drift or list updates, reporting soft notes without blocking application startup.
- Execution budget: Entire self-test runs in <= 2.0s (measured ~166ms).

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

- **100% Offline Screening:** Zero outbound network socket connections during standard screening, UBO calculations, and report generation.
- **Local Datastore:** Stored in `%LOCALAPPDATA%\ClearanceCheck\`:
  - `logs/screening.db`: SQLite database with WAL journaling.
  - `reports/`: PDF and Excel compliance exports.
- **Optional OpenSanctions API:** Disabled by default; activated only by explicit user opt-in with local API key storage. Unlimited calls without testing cap.
