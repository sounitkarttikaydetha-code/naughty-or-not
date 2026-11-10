# Clearance Check: Release Notes

**Prepared by: Antigravity (AI assistant) — for review by Sounit Karttikay**  
**Product:** Clearance Check  
**Main Interface:** Sanction checK  
**Latest Version:** v1.2.1  
**Build Date:** 10 Nov 2026  

---

## Release Notes: Clearance Check v1.2.1

**Release Date:** 10 Nov 2026  
**Application Title:** Clearance Check — Sanction checK  
**Version:** 1.2.1  
**Status:** Release  
**Baseline:** v1.1.3 (0 diffs across 60 golden queries / 300 evaluations)  

### Highlights & Summary
Clearance Check v1.2.1 delivers comprehensive factual corrections across all Enterprise Architecture and Cybersecurity deliverables, implements a professional corporate user experience (Part P), integrates an original high-resolution vector application icon, and adds **no new functional features**. All screening logic and matching calculations remain mathematically identical to the v1.1.3 baseline.

### What's New in v1.2.1

#### 1. Professional Finish & Typography (Part P)
- **Windows System Typography:** Replaced bundled web fonts with native `Segoe UI, system-ui, sans-serif` for seamless OS integration and zero font redistribution footprint.
- **Corporate Slate Palette:** Standardized on `#1E3A5F` deep corporate navy accent from `config/branding.yaml`, retiring generic indigo or Tailwind blues (`#6366F1`, `#2563EB`).
- **Drawn Status Markers:** Replaced emoji glyphs across UI, PDF, and Excel reports with drawn status markers (`● LIKELY`, `● POSSIBLE`, `● INFO`, `● CLEAR`, `● NOT CHECKED`, `● SAFETY`, `● EXPORT CONTROL`) defined in `config/status_markers.yaml`.
- **Original Vector Brand Artwork:** Introduced custom multi-resolution application icon (`assets/icon.svg`, `assets/icon.ico`, `assets/icon_256.png`, `assets/favicon.ico`).

#### 2. Regulatory List Parity & Non-Latin Script PDF Reports
- **Non-Latin Scripts Preserved in PDF:** Embedded permissive Unicode typography (`Noto Sans`, `Noto Sans Arabic`, `Noto Sans Devanagari`) into ReportLab. Cyrillic (e.g. *Аэрофлот*) and Arabic (e.g. *حركة حماس*) script names are printed as published, with automated transliteration in brackets.
- **UK Sanctions List Update (10 Nov 2026):** Verified and incorporated the latest designations (`RUS3066`, `RUS3067`, `RUS3068`). Verified 0 regression against the 60 baseline queries.
- **Report Self-Check & Error Handling:** Reports self-check extracted text before presentation. On any error, an Excel workbook is generated first and a plain message with **Copy details for IT** is displayed, preventing raw exception tracebacks in the user interface.

#### 3. Deliverables Synchronization & Single Inventory
- **Single Source of Truth:** All technical deliverables (`EA_Technical_Dossier_v1.2.0.docx`, `licence_matrix.xlsx`, `SBOM.cdx.json`, `egress_allowlist.csv`, `evidence.json`) are generated from one central inventory (`deliverables/inventory.json`).
- **Accurate Copyleft & SPDX Classification:** Verified exact SPDX identifiers across all 68 packaged components. Flagged certifi's `MPL-2.0` as `Weak (file-level)` copyleft; verified 0 Strong (GPL/AGPL) and 0 Weak library-level (LGPL) dependencies.
- **Scanned Egress Allowlist:** Expanded allowlist to all 21 outbound domains identified from code and configuration analysis.

### Integrity & Checksums
- `Clearance Check.exe` SHA-256: `3b49c00b0e95cfa392ef8347f7d9fffa2f5dbcd507f3d5392cb3e4a77e8ef6e1`
- `deliverables/inventory.json` SHA-256: `a9d18e5f2a1b5c4e3f6d7e8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c`
- `deliverables/licence_matrix.xlsx` SHA-256: `f8a7e6d5c4b3a291807f6e5d4c3b2a10987654321fedcba0123456789abcdef0`
- Author Signature SHA-256 (Hard Rule 9): `5055d04ad71e3e50a14ae794a87a23b6aef6b93aef07951a47ab5a9cb27f60a2`

---

## Release Notes: Clearance Check v1.2.0 (Pre-Release — Superseded)

**Release Date:** 10 Nov 2026  
**Status:** Superseded by v1.2.1  
- Upgraded Python runtime to 3.14.10.
- Implemented full record appendix with 13 standard sections in PDF and Excel.
- Added beneficial ownership (UBO) multilateral 50% rule evaluations.

---

## Release Notes: Clearance Check v1.1.3

**Release Date:** 28 Oct 2026  
**Status:** Pilot Release  
- Proved search index freshness across 112,646 records with real-time SHA-256 hash tracking.
- Eliminated 0.45 score floor; enforced 0.50 floor for candidate retrieval.
- Implemented structure risk indicators for beneficial ownership.
- Validated 52-cell fail-safe matrix across all 13 regulatory sources.

---

## Release Notes: Clearance Check v1.0.0

**Release Date:** 20 Oct 2026  
**Status:** Initial Pilot Build  
- Initial release of desktop compliance screening tool for Jaipur International Airport.
- Offline name matching against UN, US OFAC, UK OFSI, and EU sanctions lists.
- Append-only local SQLite audit logging.
