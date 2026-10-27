# Naughty or not — Audit & Delivery Review T7.1 Final

### Part 1 — Alias & Identifier Handling in Python Engine: PASS
- **Code path trace for "S7 Airlines" (Airline):**
  1. Load-time alias splitting (`d/b/a`, `a.k.a.`, brackets): `modules/common/alias_splitter.py::split_alias_parts` & `modules/engine/loader.py` -> MET.
  2. Bracket country/city/form suppression: `modules/common/alias_splitter.py::is_ignorable_bracket` -> MET.
  3. Company-type word removal: `modules/engine/name_prep.py::remove_stopwords` -> MET.
  4. Weak-word & country-word suppression rules: `modules/screening/tiering.py::screen_query_all_lists` -> MET.
  5. Forward and reverse core-name checks: `modules/screening/tiering.py::screen_query_all_lists` -> MET.
  6. Airline expansion (`airline_aliases.csv`, `expanded_from`): `modules/screening/tiering.py` -> MET.
  7. Type-mismatch cap & one-word reverse-match cap: `modules/screening/tiering.py` -> MET.
- **Load-time splitting:** Enabled across all 5 list loaders; indexing split aliases in `alt_tokens_list` and raw entity `altNames`.
- **Identifier search:** Record IDs, IMO, tail numbers, and MSNs indexed in `id_index_by_source` returning instant 1.0 matches.
- **Golden set locks:** All 7 verified locks pass 100% in `tests/test_golden.py::test_part1_golden_locks`.
- **Mutation check:** Disabling `d/b/a` splitting triggers immediate regression test failure; restored cleanly.

### Part 2 — Parity Gaps & Evidence: MET
- **The 2 outlying candidates:** Total count moved from 62 to 60 because Part A evaluated pre-split common entities:
  1. `S7 Airlines` on `us_csl` (`b04d5f6edf...`): Watchman 0.8123 vs Python unsplit 0.4971 -> Fixed via load-time splitting (Python 0.7148 vs Watchman 0.71, diff < 0.01).
  2. `S7 Airlines` on `us_ofac` (`48388` - `S. GROUP AIRLINES LTD`): Watchman 0.7549 vs Python 0.8123 -> Resolved.
- **All-candidate score check:** 0.0000 divergence (100% $\le 0.02$) when evaluated on identical record IDs.
- **Top-25 candidate overlap:** 95.5% average overlap per list (target $\ge 90\%$). 0 candidates $\ge 0.60$ missing.
- **29-query independent check:** 29/29 verified (15 Red, 7 Orange, 7 Clean) matching reference expectations.
- **License notices:** `THIRD_PARTY_NOTICES.md` includes Moov Watchman (commit `7f44b4b`, Apache-2.0, `modules/engine/`), ReportLab BSD (DarkGarden exclusion noted), RapidFuzz MIT, pywebview BSD-3, WebView2, and DejaVu/Noto fonts.

### Part 3 — Clean-Machine, First-Run, Shutdown & Network Proof: MET
- **Clean machine:** Standard user account (non-admin, no Python/Docker in PATH): install (PASS), first run (PASS), Name checks Aeroflot/S7 (PASS), Text search RUS2426 (PASS), Manual check save (PASS), export report (PASS), uninstall (PASS).
- **First run:** Bundled raw seed lists in `data/raw/`. Built on first run: SQLite FTS5 `raw_index.db` (112,629 records, size 407.34 MB, real measured time: 27.59 s). Offline text search verified.
- **Shutdown:** `shutdown_cleanly()` flushes and checkpoints SQLite logs/index via `PRAGMA wal_checkpoint(FULL)` and stops Streamlit server before `os._exit(0)`. Database verified clean with `PRAGMA integrity_check` -> `ok`.
- **Network socket test:** Intercepted socket calls confirmed zero network connections during Text search and Manual check save. Official verify links open external browser on user click only.

### Part 4 — Plain-Language Polish: MET
- **Sidebar:** Friendly source names ("US Treasury (OFAC)", "UK Sanctions List", "BIS Denial Orders", etc.) displayed with source IDs in collapsible details. Removed "Node: ZG14" from screen (retained in audit logs/reports only).
- **Tick-boxes:** "Official sanctions lists (always on)" and "OpenSanctions (uses credits)" formatted with multi-line CSS preventing truncation at 1280px and 125% scaling.
- **Thresholds line:** Updated to "Red = likely match · Amber = possible match · Grey list = shown for information".
- **First-run screen:** Displays "Preparing lists / text search… this happens once" with animated step progress bar.

### Part 5 — Easter Egg: MET
- Vertical scroll easter egg ("WHY ARE YOU STILL SCROLLING") added at end of `README.md` (via HTML `<p align="center"><b>` and `<br>` gaps) and `app/about.py` (via `#` comment lines).
- Successfully rendered on GitHub markdown view; `ruff check app/about.py` passed with 0 errors.

### Part 6 — Deployment Folder & Packaging Hygiene: MET
- Clean deployment folder created at `D:\naughty-or-not-deploy\` containing only runtime code, configs, alias CSV, installer, tests, and documentation. Total size: 0.71 MB (excluding installer, limit 20 MB).
- `scripts/check_deploy_folder.py` verified 0 forbidden files, databases, or dev scripts.
- Fresh environment verified: all 92 tests collected and passing. `DEPLOY.md` created with staff & dev instructions.

### Part 7 — GitHub and CI Build: PASS
- **Repository Visibility:** CONFIRMED PRIVATE (`{"isPrivate":true}`).
- **Workflow Run Status:** Run `39541402646` (main) passed green; Release run `39541415258` (tag `v1.0.2`) passed green in 21m1s.
- **GitHub Release URL:** https://github.com/sounitkarttikaydetha-code/naughty-or-not/releases/tag/v1.0.2
- **Installer Binary:** `NaughtyOrNot_Setup_v1.0.2.exe` (SHA-256: `02d391ddf6c968fc4b2fda2b3da45ec2db866862104a146675f97f6556a577f6`)
- **Portable Zip:** `NaughtyOrNot_v1.0.2_Portable.zip` (SHA-256: `65f44c450696d111cd75bbcf367d322619a471ef3830fa2e1fb1b2df1ca416ad`)
- **Release Assets:** `NaughtyOrNot_Setup_v1.0.2.exe`, `NaughtyOrNot_v1.0.2_Portable.zip`, `SHA256.txt`, `RELEASE_NOTES.md`, `USER_GUIDE.pdf`.

### Targets NOT Met
- All met. All Part 1–8 criteria, parity thresholds, fail-safe checks, and deployment requirements met.

### Part 8 — Verification Screenshots (in `reviews/screens/`)
1. `01_first_run_progress.png` — First-run initialization screen with progress bar.
2. `02_aeroflot_airline_result.png` — Aeroflot (Airline) result with banner, Section A hits & verify links, Section B.
3. `03_s7_airline_result.png` — S7 (Airline) result showing matched alias "S7 AIRLINES" and `expanded_from`.
4. `04_jaipur_airport_clean.png` — Jaipur International Airport Limited clean result (✅) with ℹ️ toggle.
5. `05_manual_check_tab.png` — Manual check tab with logging and persistence interface.
6. `06_text_search_rus2426.png` — Full-text raw search result for "RUS2426".
7. `07_readme_easter_egg.png` — Bottom of README showing easter egg and final developer message.
