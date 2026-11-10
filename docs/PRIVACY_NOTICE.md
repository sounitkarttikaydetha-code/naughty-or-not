# Privacy Notice: Clearance Check

**Prepared by: Antigravity (AI assistant) — for review by Sounit Karttikay**  
**Document Version:** 1.2.1  
**Last Updated:** 10 Nov 2026  

This privacy notice describes how personal data is processed within Clearance Check. The application operates on a local-first architecture designed for employee use in regulatory compliance screening.

---

### 1. Personal Data Processed
Clearance Check processes identifying details of natural persons when entered by the operator for screening or imported as part of corporate shareholding hierarchies:
- **Identifying Names:** Full legal names, alternative spellings, aliases, and former names.
- **Biographical Attributes:** Dates of birth, places of birth, and nationalities.
- **Identity Numbers:** Passport numbers, national identity document numbers, tax identifiers, and corporate registration numbers.
- **Corporate Roles:** Designations as ultimate beneficial owners, shareholders, directors, or authorized signatories.

---

### 2. Purpose of Processing
Personal data is processed solely for regulatory compliance purposes:
- Verifying counterparties against official government sanctions lists (US OFAC, UK FCDO, EU DG FISMA, UN Security Council, and India MHA).
- Aggregating corporate beneficial ownership under international 50% rules and control guidelines.
- Preventing transactions involving denied parties, banned air carriers, and export-controlled aircraft.
- Maintaining an auditable compliance record of screening actions taken by authorized personnel.

---

### 3. Location of Processing and Storage
- **Local Storage:** All entered data, imported ownership files, screening results, and audit trails remain on this workstation.
- **File System:** Stored in the local user profile (`%LOCALAPPDATA%\NaughtyOrNot\` in desktop mode or the designated container storage volume).
- **Zero Inbound/Outbound Transmission:** Normal screening operates entirely in local memory and local SQLite databases. No counterparty personal data is transmitted across the local network or internet during standard searches.

---

### 4. Optional External Service (OpenSanctions)
If an operator explicitly enables the optional "Use OpenSanctions API" feature and provides an API token, the following fields are transmitted to `api.opensanctions.org` over encrypted HTTPS (TLS 1.3):
- Entity or person name entered in the search query.
- Entity schema type (Individual or Organization).
- Date of birth and nationality (only if entered in the query form).
This feature is disabled by default and requires explicit operator action to activate.

---

### 5. Data Retention
- **Audit Logs:** Screening history is retained in the local database (`screening.db`).
- **Retention Period:** To be confirmed by the owner in accordance with corporate records retention and data governance policies.
- **List Backups:** Previous regulatory list downloads are retained locally (previous 3 versions archived in `lists/archive/`) to verify historical screening integrity.

---

### 6. Access and Visibility
- **Workstation Level:** Accessible only to the logged-in operating system user and authorized local workstation administrators.
- **Central Infrastructure:** In the current standalone desktop version, records are not synchronized to a central cloud repository.
