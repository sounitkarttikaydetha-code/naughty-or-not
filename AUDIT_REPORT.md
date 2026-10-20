# Phase A — Independent Audit Report: Naughty or not

## 1. Verdict
**NOT READY for T7 (READY WITH FIXES upon completion of Phase B).** The core screening logic, fuzzy word rules, and Watchman client are functionally capable, and zero offline counterparty queries leak externally. However, three Critical defects prevent immediate release: (1) failed India/Aviation sources fail silently into clean ✅ overall banners instead of ⚪ Incomplete; (2) OpenSanctions bulk loader lacks an enforced permission/license reference gate; and (3) ReportLab bundles a GNU GPL v2 font (`DarkGarden`), which poses copyleft licensing risks for standalone desktop `.exe` distribution. Phase B remediation is required before tagging `v1.0.0-rc1`.

## 2. Findings Table
| ID | Severity | Area | Finding | Evidence | Recommended Fix |
|---|---|---|---|---|---|
| **A-01** | **Critical** | Privacy / Licensing | Bulk loader runs without permission reference | `modules/opensanctions/bulk.py:30` checks only boolean flag | Require non-empty `OPENSANCTIONS_BULK_PERMISSION_REF` |
| **A-02** | **Critical** | Engine / Safety | India & Aviation failures silently show clean ✅ banner | `app.py:355` hardcodes `"OK"`; `is_incomplete` not set | Check `NOT_CHECKED`, set `"FAILED"`, flag `is_incomplete` |
| **A-03** | **Critical** | Licensing / Desktop | ReportLab bundles GNU GPL v2 font (`DarkGarden`) | `.venv/.../reportlab/fonts/DarkGarden-copying-gpl.txt` | Exclude `DarkGarden` font in PyInstaller `.spec` |
| **A-04** | **High** | Reproducibility | Fresh clone cannot run offline search; `data/` missing | `data/*` git-ignored; no bootstrap script in `README.md` | Provide `scripts/init_data.py` and document setup |
| **A-05** | **High** | Repo Hygiene | Binary review screenshots (1.2MB) committed; `*.db` unignored | `reviews/screens/*.png` in git; `.gitignore` lacks `*.db` | Untrack PNGs; add `*.db`, `reviews/screens/`, `dist/` to `.gitignore` |
| **A-06** | **High** | Aviation Data | EU ASL parsed banned states count is 17 instead of 16 | `modules/aviation/parser.py` duplicates São Tomé & Príncipe | Normalize accent decoding to yield official 16 states |
| **A-07** | **High** | Test Integrity | Tautological test assertion (`len >= 0`) in test suite | `tests/test_tiering.py:323`: `self.assertTrue(len(info_cands) >= 0)` | Change to `self.assertGreater(len(info_cands), 0)` |
| **A-08** | **Medium** | Specification | Tier reason codes used throughout app are undefined in spec | `SPEC.md` has 0 occurrences of reason codes (`core_name`, etc.) | Add reason code taxonomy to `SPEC.md` Section 4.2 |
| **A-09** | **Medium** | Maintainability | `KNOWN_CITIES` and FATF country lists hardcoded in code | `modules/screening/tiering.py:43`; `modules/fatf/client.py:15` | Move into `tiering_config.json` and `fatf_lists.json` |
| **A-10** | **Medium** | Desktop Build | Hardcoded relative directory writes fail in `Program Files` | `logger.py:15` and `generator.py:20` write to repo folder | Fallback to `%LOCALAPPDATA%\NaughtyOrNot\` when frozen |
| **A-11** | **Medium** | Code Quality | Six swallowed broad exceptions (`except Exception: pass`) | `app.py:105`, `aviation/parser.py:97`, `tiering.py:675`, etc. | Replace with explicit exceptions and log warnings |
| **A-12** | **Low** | Documentation | Setup instructions lack Windows PowerShell nuances | `README.md:46, 55` omits PowerShell execution policies | Document `python -m venv` and `curl.exe` on Windows |
| **A-13** | **High** | India MHA Data | Raw index holds only 20 s.3 unlawful associations vs 44 | `indexer.py:409` loads 1-page HTML instead of all pages | Pass full unl associations file to include all 44 entities |
| **A-14** | **Medium** | Raw Index Counts | Raw index counts inflated (UK 58,609 vs 6,408; US 26k vs 6.7k) | Official CSVs denormalized with multi-rows per alias/address | Retain for raw row search; document multi-hit record structure |
| **A-15** | **Medium** | Aviation Data | EU ASL count reconciliation: 154 Annex A + 2 Annex B = 156 total | Official EU ASL publication specifies 154 banned, 2 restricted | Document exact Annex A vs Annex B breakdown in docs |
| **A-16** | **Medium** | Aviation Data | FAA IASA: 9 Category 2 countries; Cat 1 returns clean | Non-Cat 2 jurisdictions are compliant (Cat 1) -> clean ✅ | Document Cat 1 clean behavior in user manual |
| **A-17** | **Medium** | Engine Tuning | 0.45 token retrieval floor used to catch S7 on us_csl | `tiering.py:702, 722` lowers retrieval for S7 (0.4971) | Document 0.45 backend retrieval vs 0.50 display floor |
| **A-18** | **Medium** | Privacy Audit | Extended network egress table with internal downloads & params | Documented in Section 9.6 | Update documentation register |
| **A-19** | **Low** | Privacy Hygiene | OpenSanctions API key masked to last 4 characters only (`...7592`) | Verified across entire repo; masked in all docs and UI | Standardize masking to `...7592` |
| **A-20** | **Low** | Configuration | Standardize bulk permission variable to `OPENSANCTIONS_BULK_PERMISSION_REF` | `bulk.py` checks single variable name | Enforce `OPENSANCTIONS_BULK_PERMISSION_REF` |

## 3. Risk-Point Checklist (Section 4, Items 1–14)
1. **No hidden country guard removing candidates:** **OK** (`ENABLE_COUNTRY_WORDS_GUARD` unused; candidates retained as ℹ️).
2. **Raw scores shown; <0.60 labelled token_pass:** **OK** (`watchman_raw_score` preserved; `<0.60` marked `token_pass`).
3. **Every reason code defined in SPEC.md:** **NOT OK** (`SPEC.md` lacks definitions for `core_name`, `score_rev`, etc. — Finding **A-08**).
4. **Fuzzy word 0.90, len >=5, gives 🟠 only:** **OK** (Verified in `tiering.py:489` and `tiering_config.json`).
5. **Person rule: partial match → 🟠; no token pass:** **OK** (`tiering.py:496` enforces 0.60 floor → ℹ️; partial → 🟠).
6. **One-word reverse or type mismatch never 🔴:** **OK** (Single-word reverse and Airline/Org vs Vessel/Person cap at 🟠).
7. **Country words weak; bracket aliases skipped:** **OK** (Country tokens weak; pure country/city brackets discarded).
8. **Airline expansion shows expanded_from:** **OK** (Stored in hit dict and rendered in UI match cards).
9. **✅ vs ⚪ used correctly; failed never ✅:** **NOT OK** (India/Aviation failures silently yield ✅ banner — Finding **A-02**).
10. **Every candidate displayed (ℹ️ does not alter banner):** **OK** (Display floor 0.50/0.45; ℹ️ leaves banner ✅).
11. **India IDs read from MHA page, not calculated:** **OK** (Mapped from official gazette S.No. 1–80 in registry).
12. **EU ASL reconciles with official totals:** **NOT OK** (22 Russian carriers and 2 Annex B OK; banned states parses 17 vs 16 — Finding **A-06**).
13. **BIS aircraft: removals never match; tail/MSN work:** **OK** (Removals guarded; MSN type corroboration verified).
14. **Thresholds/word lists live only in config:** **NOT OK** (`KNOWN_CITIES` and FATF lists hardcoded in `.py` — Finding **A-09**).

## 4. Mutation Check
All 4 target mutations were tested in an isolated scratch environment (`scratch/mutation_env`):
- **Mutation 1 (Disable core-name):** CAUGHT (9 tests failed in `test_tiering.py`).
- **Mutation 2 (Disable reverse check):** CAUGHT (2 tests failed: `test_1_two_way_core_name_check_reverse`, `test_7_sberbank_on_eu_csl`).
- **Mutation 3 (Raise thresholds by 0.1):** CAUGHT (1 test failed: `test_4_weak_generic_words`).
- **Mutation 4 (Remove airline alias expansion):** CAUGHT (1 test failed: `test_9_siberia_airlines_on_us_csl_stem_difference`).
- **Unprotected Rules / Test Gaps:** `len(info_cands) >= 0` tautology (`test_tiering.py:323`) and missing `self.assertGreater(verified_count, 0)` in `test_golden.py`.

## 5. Independent Result Check (Raw Files vs Tool)
Screened 19 agreed queries + 10 extra probes against official raw files (`data/raw/*.csv`, `*.xml`) and FTS5 raw index:
- **Zero false negatives:** Every designated target in official raw files appeared in the tool's candidate display.
- **Zero unsupported 🔴 matches:** All 🔴 hits match official records (`Rosneft` OFAC 17022, `Gazprombank` OFAC 20312, `Mahan Air` OFAC 12927, `Rossiya` OFAC 16681, `Ural Airlines` US CSL 25b989...).
- **Controls & Probes:** Clean Indian companies (`Jaipur Airport`, `Adani Airport`, `Larsen & Toubro`, `SpiceJet`, `Akasa Air`) scored clean ✅. `Tata Steel` and `Bharat Petroleum` scored review 🟠 on partial token overlap (`STEEL, Saw` person and `Oranto Petroleum`), never 🔴.

## 6. Network Egress Table
| Destination Host / URL | Protocol / Port | Purpose | Screened Name Sent? | Gate / Guard |
|---|---|---|---|---|
| `127.0.0.1` / `::1` | HTTP / 8084 | Local Watchman container | Yes (local IPC only) | Never leaves host |
| `127.0.0.1` | HTTP / 8501 | Streamlit UI server | No (browser UI) | Bound to 127.0.0.1 |
| `api.opensanctions.org` | HTTPS / 443 | Opt-in 2nd opinion check | Yes (when enabled) | Checkbox unticked by default; requires key |
| `bis.gov`, `europa.eu`, `faa.gov` | HTTPS / 443 | Source list PDF refresh | No (static list fetch) | Triggered manually via UI refresh |

Empirical socket monkeypatch confirmed zero bytes of counterparty data leave the machine during offline screening. API key `...7592` in `.env` is absent from git history, codebase files, and `%LOCALAPPDATA%`.

## 7. Clean-Room Reproducibility Notes
- **Versions Pinned:** Python `3.12.10`, Docker `29.9.1`, Watchman `moov/watchman:v1.2.2`, requirements (45 pip packages pinned with `==`).
- **Source Hashes Verified:** BIS PDF `c31c6e62...` (2025-10-10), EU ASL `7d932351...` (2026-06-09), FAA IASA `73ef0e78...` (2025-04-18), MHA First Schedule `8c33d417...` (2026-10-01), Watchman UK CSL hash `0d873299...`.
- **Reproducibility Failure:** On a fresh clone, `data/` is absent and `README.md` provides no bootstrap commands, causing initial domestic searches to fail.

## 8. Unconfirmed Claims from Earlier Review Files
1. `REVIEW_T1.5.md:53` claimed EU ASL parses **16** banned states. In reality, `parse_eu_air_safety_list()` returns **17** states due to duplicate accented/unaccented São Tomé entries.
2. `REVIEW_T1.5.md:58` claimed MHA Fourth Schedule IDs are calculated as `80 - index`. Code actually loads them from `fourth_schedule_registry.json`.
3. `REVIEW_T1.7_T5.1.md:73` claimed all targets met with zero defects. Audit revealed that India and Aviation source failures fail silently into clean ✅ overall banners.

---

## 9. Phase A Completion

### 9.1 Fail-Safe Matrix (Pre-Fix Baseline)
| Source | Service Unavailable | Corrupt File | Empty File | Wrong Format |
|---|---|---|---|---|
| `us_ofac` | ⚪ NOT_CHECKED / ⚪ INCOMPLETE | ⚪ NOT_CHECKED / ⚪ INCOMPLETE | ⚪ NOT_CHECKED / ⚪ INCOMPLETE | ⚪ NOT_CHECKED / ⚪ INCOMPLETE |
| `us_csl` | ⚪ NOT_CHECKED / ⚪ INCOMPLETE | ⚪ NOT_CHECKED / ⚪ INCOMPLETE | ⚪ NOT_CHECKED / ⚪ INCOMPLETE | ⚪ NOT_CHECKED / ⚪ INCOMPLETE |
| `uk_csl` | ⚪ NOT_CHECKED / ⚪ INCOMPLETE | ⚪ NOT_CHECKED / ⚪ INCOMPLETE | ⚪ NOT_CHECKED / ⚪ INCOMPLETE | ⚪ NOT_CHECKED / ⚪ INCOMPLETE |
| `eu_csl` | ⚪ NOT_CHECKED / ⚪ INCOMPLETE | ⚪ NOT_CHECKED / ⚪ INCOMPLETE | ⚪ NOT_CHECKED / ⚪ INCOMPLETE | ⚪ NOT_CHECKED / ⚪ INCOMPLETE |
| `un_csl` | ⚪ NOT_CHECKED / ⚪ INCOMPLETE | ⚪ NOT_CHECKED / ⚪ INCOMPLETE | ⚪ NOT_CHECKED / ⚪ INCOMPLETE | ⚪ NOT_CHECKED / ⚪ INCOMPLETE |
| `in_mha_first` | ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** | ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** | ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** | ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** |
| `in_mha_fourth`| ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** | ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** | ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** | ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** |
| `in_mha_s3` | ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** | ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** | ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** | ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** |
| `bis_aircraft` | ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** | ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** | ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** | ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** |
| `eu_air_safety`| ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** | ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** | ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** | ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** |
| `faa_iasa` | ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** | ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** | ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** | ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** |
| `fatf` | ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** | ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** | ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** | ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** |
| `opensanctions`| ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** | ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** | ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** | ⚪ NOT_CHECKED / **✅ NO MATCH (CRITICAL)** |
| `raw_index` | ⚪ DB_UNAVAILABLE / ⚪ INCOMPLETE | ⚪ DB_UNAVAILABLE / ⚪ INCOMPLETE | ⚪ DB_UNAVAILABLE / ⚪ INCOMPLETE | ⚪ DB_UNAVAILABLE / ⚪ INCOMPLETE |

### 9.2 Unusual Inputs Across Modes
| Input Description | Input Representation | Screened Mode Result | Raw Search Mode Result | Manual Check Mode Result |
|---|---|---|---|---|
| Empty string | `""` | Handled cleanly; 0 hits | INVALID_QUERY (min 3 chars) | Logged cleanly (SQLite) |
| 500 characters | `"A" * 500` | Handled cleanly; 0 hits | NO_RESULTS (0 hits) | Logged cleanly (SQLite) |
| Cyrillic text | `"Сбербанк"` | Handled cleanly; core match | OK (3 hits) | Logged cleanly (SQLite) |
| Arabic text | `"تنظيم القاعدة"` | Handled cleanly; 0 hits | NO_RESULTS (0 hits) | Logged cleanly (SQLite) |
| Apostrophe | `"O'Brien"` | Handled cleanly; 0 hits | OK (3 hits) | Logged cleanly (SQLite) |
| Quotes | `"\"Al-Qaida\""` | Handled cleanly; MHA hit 🔴 | NO_RESULTS (0 hits) | Logged cleanly (SQLite) |
| SQL Injection | `"'; DROP TABLE x;--"` | Handled cleanly; 0 hits | NO_RESULTS (0 hits) | Logged cleanly (parameterized) |
| FTS operator | `"NEAR("` | Handled cleanly; 0 hits | NO_RESULTS (0 hits) | Logged cleanly (SQLite) |
| Asterisk | `"*"` | Handled cleanly; 0 hits | INVALID_QUERY (min 3 chars) | Logged cleanly (SQLite) |
| Emoji | `"🔴 ✈️ 🚢"` | Handled cleanly; 0 hits | NO_RESULTS (0 hits) | Logged cleanly (SQLite) |

### 9.3 Dependency Licenses Summary
46 installed distributions audited via package metadata:
- **Permissive Open-Source (44 packages):** MIT (21), BSD-3/2-Clause (13), Apache-2.0 (8), PSF-2.0 (1), CC0/Zlib (1).
- **Weak Copyleft (1 package):** `certifi==2026.10.19` (MPL 2.0; file-scoped, safe for dynamic linking/packaging).
- **GPL Copyleft Flag (1 package):** `reportlab==5.0.1` bundles GNU GPL v2 font `DarkGarden` (`DarkGarden-copying-gpl.txt`). Must be excluded in PyInstaller build spec.
- **Zero other GPL, AGPL, LGPL or unknown licenses present.**

### 9.4 Code Quality
- **Static Analysis Errors:**
  - `ruff check`: 436 errors (341 fixable via `--fix`; primarily unused imports and import sorting).
  - `mypy`: 26 errors across 5 files (`watchman/client.py`, `screening/tiering.py`, `india/parser.py`, `aviation/parser.py`, `raw_search/indexer.py`).
- **Leftover Investigation Scripts in `scratch/`:**
  - Move to `scripts/dev/` (reusable utilities): `reconcile_eu_asl.py`, `save_mha_data.py`, `fetch_all_mha.py`, `download_eu_asl.py`, `download_binary_bis.py`, `download_iasa.py`.
  - Delete (one-off debug files): `check_s7_*.py`, `check_sno.py`, `check_t15_*.py`, `check_t16_*.py`, `check_tdo_csl.py`, `test_7_regression.py`, `test_t13_*.py`, `test_t14_*.py`, `test_override*.py`.
- **Duplicated Normalization Logic:**
  - Identical whitespace/punctuation/accent stripping duplicated across `screening/tiering.py:normalize_name()`, `india/client.py:normalize_text()`, `aviation/client.py:normalize_token()`, `fatf/client.py:normalize_country()`, and `raw_search/indexer.py:normalize_text_for_index()`. Will unify into `modules/screening/normalization.py`.

### 9.5 Specification vs. Code Delta
- **Implemented in Code but Missing from `SPEC.md`:** (1) Tier reasoning codes (`core_name`, `score_and_core_name`, `core_name_reverse`, `type_mismatch`, `partial_name_person`, `core_name_fuzzy`, `token_pass`, `secondary_identifier_conflict`); (2) Fuzzy word matching (0.90 threshold, length >= 5); (3) Airline query expansion via `airline_aliases.csv`; (4) Raw FTS5 search mode; (5) Manual check verification tab; (6) FATF country risk module.
- **In `SPEC.md` but Not in Code:** (1) Automatic daily background cron/daemon refresh (currently manual UI button / startup check); (2) OpenSanctions CC BY-NC 4.0 UI banner on bulk config screen; (3) Fail-safe incomplete banner on non-Watchman source outages.

### 9.6 Extended Network Egress & Environment Assumptions
- **Container List Downloads:** Watchman container downloads official lists over HTTPS on startup/refresh (`treasury.gov`, `data.trade.gov`, `fcdo.gov.uk`, `europa.eu`, `un.org`). Configured to refresh every 24h via `DATA_REFRESH_INTERVAL=24h`.
- **Startup Document Refresh:** App checks `sources_meta.json` on launch; if documents are >24h old, performs static GET requests to `bis.gov`, `transport.ec.europa.eu`, and `faa.gov`. Zero counterparty data is transmitted.
- **Verification Links Opened in Browser:**
  - OFAC: `https://sanctionssearch.ofac.treas.gov/Details.aspx?id={id}` (SDN ID only).
  - OpenSanctions: `https://www.opensanctions.org/entities/{id}/` (OS entity ID only).
  - Static portals: UK, EU, US CSL, UN, BIS, and MHA links transmit zero query parameters.
- **Docker & Port Assumptions:** Docker required in `run_app.bat` and `stop_app.bat`; port 8084 assumed for Watchman; port 8501 assumed for Streamlit UI.
- **Path Portability:** Zero hardcoded `D:\` paths in source code. Runtime relative writes to `logs/` and `reports/` must adapt to `%LOCALAPPDATA%` for installed `.exe` deployments.
