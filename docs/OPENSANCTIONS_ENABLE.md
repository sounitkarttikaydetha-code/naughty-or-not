# Enabling OpenSanctions Bulk Ingestion

This guide outlines the mandatory governance and operational steps required to activate OpenSanctions bulk data in **Naughty or not (Sanction checK)** once formal written authorization or a commercial license has been obtained from OpenSanctions.

---

## 1. Permission Recording & Governance Prerequisites

Before modifying any configuration or attempting to ingest data:
1. **Record Written Permission:**
   - **Permission Reference:** Note the official license identifier or authorization email reference (e.g., `OS-LIC-2026-XXXX`).
   - **Effective Date:** Record the start date and termination/expiry date of the evaluation or licensing term.
   - **Scope of Coverage:** Confirm whether the permission covers internal evaluation, number of authorized seats/users, and restrictions against redistribution.
2. **Licensing Compliance Notice:**
   - OpenSanctions data is licensed under CC BY-NC 4.0 for non-commercial use. Commercial deployment strictly requires a commercial license from OpenSanctions.

---

## 2. Setting the Three Bulk Gate Conditions (T10-1)

To protect against inadvertent or unauthorized bulk usage, the bulk ingestion module enforces a strict **three-part gate**. Ingestion **refuses to run** unless ALL THREE conditions are met:

### Gate 1: Environment Variable Activation
In your local `.env` file (or secure execution environment):
```bash
OPENSANCTIONS_BULK_ENABLED=true
```

### Gate 2: Official Permission Reference
In your `.env` file, configure the non-empty permission reference:
```bash
OPENSANCTIONS_BULK_PERMISSION_REF=OS-LIC-2026-XXXX
```
*(The system will display only the last 4 characters in public reports, preserving confidentiality).*

### Gate 3: In-App User Acknowledgement
- Open the application.
- Navigate to the **Settings** tab.
- Read and accept the formal acknowledgement:
  > *"We hold written permission or a licence from OpenSanctions for this use."*
- Click **Save Acknowledgement**. This creates an audit log entry in SQLite (`bulk_acknowledgement_logs`) recording your Windows username, application version, and UTC timestamp.
- Note: This acknowledgement must be re-confirmed after every major application version update.

> **CRITICAL RULE:** The API key (`OPENSANCTIONS_API_KEY`) **never** enables bulk data loading by itself.

---

## 3. Ingestion & File Layout Verification (T10-2)

1. Place the official OpenSanctions FollowTheMoney (FtM) newline-delimited JSON export at:
   ```
   data/opensanctions/entities.ftm.json
   ```
2. Run the loader once to index the entities:
   ```powershell
   .venv\Scripts\python.exe -m modules.opensanctions.bulk
   ```
3. Verify file layout and record integrity:
   - Check entity counts, schema validation, and ensure malformed rows are quarantined into error logs rather than failing silently.
   - Run benchmark script to confirm memory and load-time metrics:
     ```powershell
     .venv\Scripts\python.exe scripts/dev/benchmark_synthetic_os.py
     ```

---

## 4. Verification & Baseline Validation

With bulk ingestion active:
1. **Re-run Baseline Regression:**
   Confirm that existing verified golden records continue to return expected ratings:
   ```powershell
   .venv\Scripts\python.exe scripts/dev/diff_baseline.py
   ```
2. **Screening Validation:**
   Verify that bulk-sourced matches display the clear provenance tag:
   `OpenSanctions (evaluation)` or `OpenSanctions (licensed)`.
3. **Report Header Audit:**
   Generate a sample PDF/Excel report to confirm that the report header displays:
   - Bulk status: `Enabled`
   - Permission reference: `***XXXX` (masked last 4 characters).

---

## 5. End of Evaluation / Decommissioning Procedure

When the trial period expires or if authorization is revoked:
1. **Disable Gates:**
   Set in `.env`:
   ```bash
   OPENSANCTIONS_BULK_ENABLED=false
   OPENSANCTIONS_BULK_PERMISSION_REF=
   ```
2. **Purge Data & Indices:**
   Delete downloaded FtM JSON files and cached indexes:
   ```powershell
   Remove-Item -Recurse -Force "data/opensanctions"
   Remove-Item -Recurse -Force "cache/opensanctions*"
   ```
3. **Audit Trail Logging:**
   Record the decommissioning date, administrator ID, and reason in the compliance audit register.
