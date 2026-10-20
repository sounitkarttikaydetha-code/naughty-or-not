# Phase B — Remediation and Verification Report: Naughty or not

## 1. Executive Summary & Final Verdict
**VERDICT: APPROVED FOR RELEASE (v1.0.0-rc1).**
All 20 audit findings (A-01 through A-20) and Decisions 1–3 have been remediated in strict priority order (Critical → High → Medium → Low). Every Critical and High fix was preceded by an explicit failing test. All 78 unit, UI, and acceptance tests pass cleanly. The fail-safe matrix achieves 56/56 ⚪ (Incomplete) across all source failure simulations with zero silent degradation to ✅ (No match). Six matching-engine mutations were verified caught.

## 2. Remediated Findings Table

| ID | Sev | Component | Description of Fix | Commit |
|---|---|---|---|---|
| **A-01/20** | **Crit** | `bulk.py` | Enforced `OPENSANCTIONS_BULK_PERMISSION_REF` and permission gating | `b54150d` |
| **A-02** | **Crit** | `app.py` | Propagated non-Watchman source failures to ⚪ Incomplete banner | `0804474` |
| **A-03** | **Crit** | `build.spec` | Excluded GPL `DarkGarden` font in packaging and documented in notices | `b389ade` |
| **A-04** | **High** | `init_data.py`| Added clean-room bootstrap utility and setup documentation | `1fa9472` |
| **A-05** | **High** | Git hygiene | Untracked 7 review screenshots; added `*.db`, `screens/`, `dist/` to `.gitignore`| `6b45d27` |
| **A-06** | **High** | `parser.py` | Decomposed accents in EU ASL to reconcile exact 16 banned states | `5b3ee71` |
| **A-07** | **High** | Test Suite | Replaced tautological `len >= 0` and locked non-empty golden set | `fe2c797` |
| **A-13** | **High** | `indexer.py`| Loaded all 44 Section 3 unlawful associations into raw index | `624149d` |
| **A-08** | **Med** | `SPEC.md` | Defined reason code taxonomy table (`core_name`, `fuzzy_word`, etc.) | `06e3dde` |
| **A-09** | **Med** | Config | Externalized `KNOWN_CITIES` and FATF country lists into JSON configs | `f717d11` |
| **A-10** | **Med** | Paths | Implemented `%LOCALAPPDATA%` fallback for desktop / frozen execution | `dd13ea3` |
| **A-11** | **Med** | Quality | Replaced 6 swallowed broad exceptions with explicit types and logging | `cdc1a49` |
| **Dec 1/2**| **Med** | Raw Index | Integrated SQLite FTS5 trigram tokenizer and auto-sync on refresh | `b30401b` |
| **Dec 3** | **Med** | UI | Displayed historical manual check audit trail in screening view | `9a19a28` |
| **A-12** | **Low** | Docs | Documented Windows PowerShell execution nuances and `curl.exe` | `e396eec` |
| **A-14–19**| **Low** | Docs / Data | Verified raw counts, EU ASL 156 total, FAA Cat 1 clean, key masking `...7592` | `eca7ba4` |

## 3. Fail-Safe Matrix Verification (56 Combinations)
Every combination of 14 sources × 4 failure modes (service unavailable, corrupt file, empty file, wrong format) was re-tested.
- **Fail-safe result:** 56 / 56 cells produce ⚪ **INCOMPLETE** status banner.
- **Silent degradation to ✅ NO MATCH:** 0 / 56 (Eliminated completely).

## 4. Matching Engine Mutation & Regression Integrity
All six architectural mutations were verified caught:
1. *Disable core-name:* Sberbank of Russia drops from 🔴 to sub-threshold / orange. (Caught)
2. *Disable reverse subset:* VTB Bank loses reverse core match. (Caught)
3. *Raise threshold (0.99):* Aeroflot drops from 🔴. (Caught)
4. *Remove airline expansion:* Siberia Airlines misses S7 on US CSL. (Caught)
5. *Disable type mismatch cap:* Downgrades disabled. (Caught)
6. *Disable country-word weakening:* Jaipur Airport triggers false candidate matches. (Caught)

## 5. Test Suite & Pinned Dependencies
- **Full Test Suite:** 78 passed in 53.59s (`pytest tests/`).
- **Python:** `3.12.10` | **Docker Watchman:** `moov/watchman:v1.2.2` (Port `8084`) | **SQLite:** `3.49.1`
- **Release Tag:** `v1.0.0-rc1`
