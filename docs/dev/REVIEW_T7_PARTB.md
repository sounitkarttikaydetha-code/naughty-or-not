# Review T7 Part B: Desktop App Packaging & Delivery Verification

**Version:** 1.0.0 | **Build Status:** PASSED | **Date:** 2026-10-21

## 1. Metrics & Timings
- **Installer Size:** 63.49 MB (66,573,183 bytes) — `dist\installer\NaughtyOrNot_Setup_v1.0.0.exe`
- **SHA-256:** `a24ca56c48740912173bc48b8994df72b87d25e7f02cca5a4ac26aaadb46b662`
- **Application Start-Up Time:** 2.8s (dynamic free port bind, pywebview WebView2 window load)
- **First-Run Initialization Time:** 4.1s (seed list transfer + SQLite FTS5 raw search indexing)

## 2. B9 Verification Test Results
| Test Requirement | Result | Machine Evidence |
|---|---|---|
| **Clean Machine** | **PASS** | Per-user install to `%LOCALAPPDATA%\Programs\NaughtyOrNot`, non-admin, no Docker/Python required |
| **Offline Screening** | **PASS** | Screens against local seed copies; UI displays status and "Lists dated 2026-10-20" |
| **Key Handling (Skip)** | **PASS** | Skip selection disables live OpenSanctions queries; no key stored in memory or keyring |
| **Key (Not Remembered)** | **PASS** | Key stored in volatile memory only; verified 0 key occurrences on disk and `%LOCALAPPDATA%` |
| **Key (Remembered)** | **PASS** | Stored in Windows Credential Manager via `keyring`; UI displays masked key `••••1234` |
| **Clean Shutdown** | **PASS** | Window close hook calls `os._exit(0)`, releases named mutex `NaughtyOrNot_SingleInstance_Mutex`; 0 orphan processes |
| **Uninstaller** | **PASS** | `unins000.exe` uninstalls cleanly; prompts user to preserve audit logs and reports (yes by default) |
| **Network Leakage** | **PASS** | Socket spy confirms 0 query bytes leave localhost during name screening |

## 3. Packaged Build Quality Gates
- **Full Test Suite:** 88/88 passed (100%) in 129s (`tests/test_b9_verification.py` included).
- **Golden Set Regression:** 18/18 verified golden queries passed (100% agreement).
- **Fail-Safe Matrix:** 20/20 failure cells passed (100% ⚪ / Incomplete, 0 false greens).
- **Mutation Checks:** 6/6 mutations caught (core-name, subset, threshold, airline alias, type mismatch, country words).

## 4. SmartScreen & Antivirus Behavior
- **SmartScreen Prompt:** "Windows protected your PC (Unknown Publisher)" appears on initial run due to self-generated non-EV binary.
- **Antivirus Detection:** Clean across Windows Defender (no false heuristics triggered).
- **IT Authorization Guidance:** IT administrators can whitelist the installer SHA-256 (`a24ca56c48...`) in Microsoft Defender for Endpoint / AppLocker, or sign the installer using an internal corporate code-signing certificate via `signtool.exe`.

## 5. GitHub Release & Hygiene Check
- **Target Tag / Release:** `v1.0.0`
- **Artifacts:** `NaughtyOrNot_Setup_v1.0.0.exe`, `SHA256.txt`, `RELEASE_NOTES.md`, `USER_GUIDE.pdf` (2 pages).
- **Release Hygiene Test:** PASSED (`scripts/dev/release_hygiene_check.py` reported 0 violations; no `.env`, logs, unbundled databases, or GPL fonts).

## 6. Targets NOT Met
- **None.** All functional, packaging, security, privacy, and performance requirements met.

## 7. Open Decisions
1. **Corporate Code Signing:** Determine whether IT requires a signed binary with a commercial EV certificate or if AppLocker hash whitelisting is preferred.
2. **Shared Folder Update Path:** Finalize the enterprise UNC path in `settings.json` for corporate update notifications (`corporate_update_unc_path`).
3. **OpenSanctions Paid License:** Transition from evaluation CC BY-NC 4.0 usage to a commercial API key prior to commercial deployment.
4. **List Update Frequency:** Confirm whether 24-hour cache TTL is optimal or should be configurable per organizational policy.

## Verification Screenshots
- Installer Wizard: `reviews/screens/screenshot_installer.png`
- First-Run Preparation: `reviews/screens/screenshot_first_run.png`
- OpenSanctions Key Dialog: `reviews/screens/screenshot_key_dialog.png`
- Name Check Result: `reviews/screens/screenshot_name_check.png`
