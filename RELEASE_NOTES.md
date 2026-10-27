# Release Notes — Clearance Check v1.1.0

**Release Date:** October 28, 2026  
**Application Title:** Sanction checK  
**Version:** 1.1.0  
**Baseline:** v1.0.4  

---

## 🌟 Highlights & What's New

### 🏢 Beneficial Ownership & Control (UBO) Screening
- **Multilateral 50% Rule Engine:** Automated analysis under US OFAC FAQs 399 & 401 (Examples 1, 2, and 3), European Union proprietary ownership & control criteria, and UK OFSI Sanctions Regulations (Conditions 1, 2, and 3).
- **Parallel Economic Look-Through:** View direct and indirect pro-rata economic look-through percentages side-by-side with statutory sanctions aggregation.
- **Excel & CSV Import:** Pre-formatted downloadable templates (`ownership_template.xlsx`) and support for standard compliance schedules (including KYC Annexure 1).
- **Four-Eyes Sign-Off Workflow:** Preparer and reviewer disposition panels with audit trails logged directly to local encrypted SQLite storage (`mode = 'ownership'`).

### 🌍 Comprehensive Country Check
- **Territorial Sanctions Analysis:** Screen high-risk and embargoed jurisdictions (Cuba, Iran, North Korea, Syria, Russia) as well as elevated-risk selective sanctions regimes (Belarus, Myanmar, Venezuela, Zimbabwe, Sudan).
- **Integrated Risk Factors:** Instant visibility into FATF call-for-action (black) and increased monitoring (grey) jurisdictions, EU Air Safety bans, FAA IASA Category 2 restrictions, and EAR Country Groups (D:1, D:3, D:5, E:1, E:2).
- **Audit Compliance:** Dedicated `mode = 'country'` logging in the local compliance audit trail.

### 🛡️ Three-Layer Start-up Self-Test
- **Engine Canary Layer:** 20 invariant algorithmic test cases verified on startup to guarantee internal consistency.
- **Self-Sampled Live Probes:** Samples live loaded database entities and rejects nonsense strings.
- **Named Drift Monitoring:** Evaluates 10 benchmark designated entities to notify compliance officers of list updates or delistings without blocking startup.
- **Blazing Fast:** Complete 3-layer self-test runs in under 200 milliseconds.

### 🔍 Advanced Matching & Identifier Corroboration
- **Exact Identifier Match (🔴):** Immediate elevation to Tier 1 when a tax ID, national ID, passport, or registration number matches.
- **SOLAS IMO Validation:** Algorithmic 7-digit check-digit verification for maritime vessel identification numbers.
- **Corroboration Upgrades:** When both full Date of Birth and Nationality corroborate a sound-alike or high candidate hit, it upgrades automatically to a Tier 1 match.
- **Controlled Conflict Downgrades:** Conflicting secondary identifiers (e.g. mismatched year of birth) safely adjust candidate tiers while preserving full audit visibility.

### 🎨 Modernized User Interface & Accessibility
- **Local Inter Typeface:** Bundled offline WOFF2 fonts with zero external web requests.
- **Refined Contrast & Styling:** Enhanced palette complying strictly with WCAG AA accessibility standards (all text contrast >= 4.5:1).
- **Compact Results & Full Record Inspector:** Streamlined summary row and single-click expanders providing complete official records from our 40,400+ indexed dataset.
- **Wrap-Protected PDF & Excel Reports:** Formatted cell rendering and soft hyphenation preventing word clipping in portrait A4 PDFs.

---

## 🛠️ Security, Performance & Upgrades

- **Unlimited OpenSanctions API:** Removed the temporary 15-call test credit cap. Key usage is tracked in local session memory with zero cloud telemetry.
- **100% Offline Privacy Guarantee:** Verified with zero external network socket calls during screening, UBO calculations, and report generation.
- **Audit Database Integrity:** Immediate Write-Ahead Logging (WAL) flush and atomic transaction safety upon desktop application shutdown.
- **Clean Deployment & Licensing:** Proprietary enterprise license, updated installer Terms of Use, and clean attribution notices across all bundled open-source modules.

---

## 📦 Upgrading from v1.0.4

1. Close existing application instances.
2. Run `ClearanceCheck_Setup_v1.1.0.exe`.
3. Historical screening logs and generated PDF/Excel reports in `%LOCALAPPDATA%\ClearanceCheck` are automatically preserved and migrated.
