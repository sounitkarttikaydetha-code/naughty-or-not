# Clearance Check v1.1.0 — System Architecture Dossier

**Product Name:** Clearance Check  
**Main UI Title:** Sanction checK  
**Version:** 1.1.0  
**Build Target:** Windows 10/11 x64 Standalone Desktop Application  
**Runtime:** Embedded Python 3.12, Streamlit UI, pywebview / Edge WebView2 Shell  
**Author:** Sounit Karttikay / Compliance Engineering  

---

## 1. System Overview & Offline Architecture

Clearance Check is a desktop compliance screening and beneficial ownership analysis application. It operates in a 100% offline, privacy-first mode where all entity matching, phonetic expansion, corporate hierarchy traversal, and report generation execute locally on the analyst's machine.

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
|  - Corroboration |     |   - UK OFSI      |    | - Aviation   |  | - 8 Sources    |
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
|      * `manual_checks` (Analyst disposition history)                              |
+-----------------------------------------------------------------------------------+
```

---

## 2. Supported Sanctions Regimes & Source Catalog

| Source Identifier | Official Authority / Register | Format | Entity Coverage |
|---|---|---|---|
| `us_ofac` | US Treasury Office of Foreign Assets Control (SDN & SSI) | XML / JSON | Global individuals, banks, corporates, vessels, aircraft |
| `us_csl` | US International Trade Administration (CSL: BIS, DTC, State) | CSV | Global export violations, Entity List, UVL, MEU |
| `uk_csl` | UK Foreign, Commonwealth & Development Office (FCDO) | XML / CSV | UK Sanctions List post-28 Jan 2026 designations |
| `eu_csl` | European External Action Service (EEAS) | XML / CSV | EU Financial Sanctions & Common Foreign Policy |
| `un_csl` | United Nations Security Council Consolidated List | XML | UN Sanctions Committees (ISIL/Al-Qaida, 1718, etc.) |
| `in_mha` | India Ministry of Home Affairs (UAPA Schedules 1st, 4th, UA) | PDF / HTML | Banned organizations, terrorist individuals, unlawful groups |
| `bis_aircraft` | US Bureau of Industry and Security | Web / CSV | Export-restricted Russian/Belarusian/Iranian tail numbers |
| `eu_air_safety` | European Commission DG MOVE | Regulation PDF | Air carriers banned or restricted from European airspace |
| `fatf` | Financial Action Task Force | Plenary Decs | Black-list (High-Risk) & Grey-list (Monitored) jurisdictions |

---

## 3. Matching & Tiering Rules Engine

Core matching operates deterministically with standardized threshold boundaries:
- **0.80 — 1.00:** High match / Potential Match (🔴). Requires core-name equivalence, exact alias match, exact identifier match, or corroboration upgrade.
- **0.70 — 0.79:** Moderate match / Possible Match (🟠). Review recommended. Includes sound-alike phonetic matches and partial person name subsets.
- **0.60 — 0.69:** Low match / Below Threshold (ℹ️). Retained for information only.
- **< 0.60:** Discarded / No Match (⚪).

### Special Matching Capabilities (v1.1.0)
1. **Identifier Elevation:** Matching a tax ID, national ID, passport, or registration number immediately forces Tier 1 (🔴) with reason `id_match`.
2. **SOLAS IMO Check Digit:** Maritime IMO numbers validated via modulus 10 weighted sum.
3. **Corroboration Upgrades:** If Date of Birth AND Nationality match a candidate, a Tier 2 candidate elevates to Tier 1 (`name_dob_nat_match`).
4. **Controlled Conflict Downgrades:** Conflicting secondary identifiers downgrade candidates by one tier per conflict while preserving audit visibility.

---

## 4. Beneficial Ownership & Control (UBO) Engine

Implements multilateral statutory aggregation rules:
- **US OFAC 50% Rule (FAQs 399, 401 Examples 1–3):**
  - Direct 50%+ ownership by blocked persons blocks the target entity.
  - Multi-tier indirect pass-through: Intermediate subsidiaries >=50% owned by blocked persons are treated as 100% blocked in subsequent tiers.
  - Non-blocked intermediate subsidiaries (<50% blocked) do NOT pass through blocked status.
  - Distinct blocked persons are aggregated together at each tier.
- **EU Ownership & Control:**
  - Proprietary ownership >50.0%.
  - Control criteria: Right to appoint/remove majority of board; power to exercise decisive influence.
- **UK OFSI Ownership & Control:**
  - Condition 1: Holds >50% shares or voting rights.
  - Condition 2: Right to appoint or remove majority of board members.
  - Condition 3: Significant control or conduct of affairs per wishes.
- **Economic Look-Through:** Multiplicative pro-rata percentage across all tiers displayed side-by-side with statutory sanctions aggregation.

---

## 5. Security, Privacy & Performance Specifications

| Metric / Boundary | Specification | Observed Performance |
|---|---|---|
| Outbound Network Requests | Strictly 0 during standard screening | Verified (0 socket calls) |
| Startup Self-Test Duration | <= 2.00 seconds | 166 milliseconds |
| Single Entity Screening Duration | <= 50 milliseconds (cached) | 15–25 milliseconds |
| Complete Test Suite | 240 tests across 28 modules | 100% passing (16 skipped visual) |
| Mutation Security Checks | 17/17 caught | 17/17 passed |
| CSS Size Budget | <= 30 KB | 3.5 KB |
| Contrast Accessibility | WCAG AA >= 4.5:1 | Compliant (6.37:1 to 17.85:1) |
| Storage Audit Trail | SQLite WAL Mode with graceful flush | Verified (no DB lock / leak) |
