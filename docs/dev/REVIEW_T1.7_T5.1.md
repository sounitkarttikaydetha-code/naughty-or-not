# Naughty or not — Review T1.7, T5.1 (Raw Search), T5.2, and Launch

### 0. Turbo-Mode Checks
- `git log --oneline`: `ca888a5` HEAD, clean history.
- `git status`: working tree clean.
- `logs/opensanctions_usage.csv`: exactly 4 lines (0 API credits consumed this round).

### 1. T1.7 Status & Evidence (Items 1–6) — ALL MET
- **Item 1 (SIBERIA on `us_ofac`):** MET. OFAC ID `37078`, Name `SIBERIA`, Type `vessel` (IMO 9239458, Prog: `RUSSIA-EO14024`). Downgraded to 🟠 `0.8122 (type_mismatch)` on Airline/Org queries; reverse single-word core match never yields 🔴.
- **Item 2 (Low scores & Fuzzy 0.90):** MET. Fuzzy setting restored to 0.90 in `tiering_config.json`. S7 `uk_csl` (0.5990) and `us_csl` (0.4971) correctly flag token pass and core-name match.
- **Item 3 (UTair candidates):** MET. `us_ofac` 🟠 0.7285 is `JINSONG JOINT BANK` (ID 23003); `uk_csl` 🟠 0.7209 is `JOINT DEVELOPMENT BANK` (ID RUS3647). Both are banks, not the airline.
- **Item 4 (Show every candidate):** MET. `DISPLAY_MIN_MATCH=0.50`, `DISPLAY_LIMIT=25`. Below-threshold candidates mapped to ℹ️ `BELOW_THRESHOLD`. Overall banner and list status stay ✅ clean.
- **Item 5 (Streamlit privacy & Deploy button):** MET. Configured in `.streamlit/config.toml` (`client.toolbarMode = "minimal"`, `server.address = "127.0.0.1"`, `browser.gatherUsageStats = false`). Deploy button is completely removed.
- **Item 6 (Refresh):** MET. Freshness check runs on start and manual "Refresh All Sources" button kept; no cron.

### 2. Full Per-List Tier Table: 19 Agreed Queries × 6 Lists (From `_generated_tables.md`)
| Query | us_ofac | us_csl | uk_csl | eu_csl | un_csl | in_mha |
|---|---|---|---|---|---|---|
| Sberbank | 🔴 0.6622 (core_name) +12ℹ️ | 🔴 0.6622 (core_name) +9ℹ️ | 🔴 0.6904 (core_name) | 🔴 0.6904 (core_name) | ✅ 0.0000 (none) +10ℹ️ | ✅ 0.0000 (none) |
| Sberbank of Russia | 🔴 0.8122 (score_and_core_name) +12ℹ️ | 🔴 0.8122 (score_and_core_name) +8ℹ️ | 🔴 0.6904 (core_name) | 🔴 0.6904 (core_name_reverse) | ✅ 0.0000 (none) +10ℹ️ | ✅ 0.0000 (none) |
| PJSC Sberbank | 🔴 0.6904 (core_name) +17ℹ️ | 🔴 0.4986 (core_name) +12ℹ️ | 🔴 0.6490 (core_name) | 🔴 0.4651 (core_name) | ✅ 0.0000 (none) +10ℹ️ | ✅ 0.0000 (none) |
| VTB Bank | 🔴 0.8122 (score_and_core_name) +5ℹ️ | 🔴 0.8122 (score_and_core_name) +4ℹ️ | 🔴 0.7679 (core_name) | 🔴 0.6904 (core_name) | ✅ 0.0000 (none) +2ℹ️ | ✅ 0.0000 (none) |
| S7 Airlines | 🟠 0.7549 (score) +82ℹ️ | 🔴 0.4971 (core_name) +80ℹ️ | 🔴 0.8122 (score_and_core_name) +21ℹ️ | ✅ 0.0000 (none) +60ℹ️ | ✅ 0.0000 (none) +53ℹ️ | ✅ 0.0000 (none) |
| Siberia Airlines | 🟠 0.8122 (type_mismatch) +82ℹ️ | 🔴 0.6482 (core_name) +80ℹ️ | 🔴 0.7919 (core_name) +21ℹ️ | ✅ 0.0000 (none) +60ℹ️ | ✅ 0.0000 (none) +53ℹ️ | ✅ 0.0000 (none) |
| Aeroflot | ✅ 0.0000 (none) +25ℹ️ | 🔴 0.7716 (core_name) +8ℹ️ | 🔴 0.7716 (core_name) +3ℹ️ | ✅ 0.0000 (none) +26ℹ️ | ✅ 0.0000 (none) +5ℹ️ | ✅ 0.0000 (none) |
| Azur Air | ✅ 0.0000 (none) +73ℹ️ | 🔴 0.8122 (score_and_core_name) +49ℹ️ | ✅ 0.0000 (none) +69ℹ️ | ✅ 0.0000 (none) +71ℹ️ | ✅ 0.0000 (none) +61ℹ️ | ✅ 0.0000 (none) |
| UTair | 🟠 0.7285 (score) +53ℹ️ | 🔴 0.7285 (core_name) +24ℹ️ | 🟠 0.7209 (score) +50ℹ️ | 🔴 0.8122 (score_and_core_name) +33ℹ️ | ✅ 0.0000 (none) +30ℹ️ | ✅ 0.0000 (none) |
| Jaipur International Airport Limited | ✅ 0.0000 (none) +25ℹ️ | ✅ 0.0000 (none) +25ℹ️ | ✅ 0.0000 (none) +25ℹ️ | ✅ 0.0000 (none) +25ℹ️ | ✅ 0.0000 (none) +25ℹ️ | ✅ 0.0000 (none) |
| Adani Airport Holdings Limited | ✅ 0.0000 (none) +2ℹ️ | ✅ 0.0000 (none) +25ℹ️ | ✅ 0.0000 (none) +25ℹ️ | ✅ 0.0000 (none) +25ℹ️ | ✅ 0.0000 (none) +25ℹ️ | ✅ 0.0000 (none) |
| Air India | ✅ 0.0000 (none) +5ℹ️ | ✅ 0.0000 (none) +3ℹ️ | ✅ 0.0000 (none) | ✅ 0.0000 (none) +1ℹ️ | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| IndiGo | 🟠 0.7635 (score) | ✅ 0.0000 (none) +25ℹ️ | ✅ 0.0000 (none) +25ℹ️ | ✅ 0.0000 (none) +25ℹ️ | ✅ 0.0000 (none) +13ℹ️ | ✅ 0.0000 (none) |
| InterGlobe Aviation Limited | ✅ 0.0000 (none) +25ℹ️ | ✅ 0.0000 (none) +25ℹ️ | ✅ 0.0000 (none) +25ℹ️ | ✅ 0.0000 (none) +25ℹ️ | ✅ 0.0000 (none) +11ℹ️ | ✅ 0.0000 (none) |
| Siberian Wellness | ✅ 0.0000 (none) +16ℹ️ | ✅ 0.0000 (none) +25ℹ️ | ✅ 0.0000 (none) +4ℹ️ | ✅ 0.0000 (none) +6ℹ️ | ✅ 0.0000 (none) +25ℹ️ | ✅ 0.0000 (none) |
| Rajesh Kumar | 🟠 0.7742 (partial_name_person) | ✅ 0.0000 (none) | 🟠 0.7742 (partial_name_person) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| Mohammed Khan | 🔴 0.8122 (score_and_core_name) +3ℹ️ | 🟠 0.7347 (partial_name_person) +2ℹ️ | ✅ 0.0000 (none) +5ℹ️ | ✅ 0.0000 (none) +5ℹ️ | ✅ 0.0000 (none) +5ℹ️ | ✅ 0.0000 (none) |
| Sky Bank | ✅ 0.0000 (none) +6ℹ️ | ✅ 0.0000 (none) +24ℹ️ | ✅ 0.0000 (none) +1ℹ️ | ✅ 0.0000 (none) | ✅ 0.0000 (none) +4ℹ️ | ✅ 0.0000 (none) |
| Volga Logistics | 🟠 0.7373 (score) +5ℹ️ | 🟠 0.7513 (score) | 🟠 0.7581 (score) +1ℹ️ | 🟠 0.7285 (score) +4ℹ️ | ✅ 0.0000 (none) +1ℹ️ | ✅ 0.0000 (none) |

### 3. Expanded Airline Table (From `_generated_tables.md`)
| Query | List | Tier | Best Hit / Listed Name | Score | Reason | Matched Name | Expanded From |
|---|---|---|---|---|---|---|---|
| Siberia Airlines | us_ofac | 🟠 POSSIBLE_MATCH_REVIEW | SIBERIA | 0.8122 | type_mismatch | SIBERIA | — |
| Siberia Airlines | us_csl | 🔴 POTENTIAL_MATCH | SIBERIAN AIRLINES D/B/A S7 AIRLINES | 0.6482 | core_name | SIBERIAN AIRLINES | Siberian Airlines |
| Siberia Airlines | uk_csl | 🔴 POTENTIAL_MATCH | JSC Siberia Airlines | 0.7919 | core_name | JSC Siberia Airlines | — |
| Siberia Airlines | eu_csl | ✅ NO_MATCH | — | 0.0000 | none | — | — |
| Siberia Airlines | un_csl | ✅ NO_MATCH | — | 0.0000 | none | — | — |
| S7 | us_ofac | 🟠 POSSIBLE_MATCH_REVIEW | SIBERIA | 0.8122 | type_mismatch | SIBERIA | Siberia Airlines |
| S7 | us_csl | 🔴 POTENTIAL_MATCH | SIBERIAN AIRLINES D/B/A S7 AIRLINES | 0.6482 | core_name | SIBERIAN AIRLINES | Siberian Airlines |
| S7 | uk_csl | 🔴 POTENTIAL_MATCH | JSC Siberia Airlines | 0.5990 | core_name | S7 Airlines | — |
| S7 | eu_csl | ✅ NO_MATCH | — | 0.0000 | none | — | — |
| S7 | un_csl | ✅ NO_MATCH | — | 0.0000 | none | — | — |
| Aeroflot Russian Airlines | us_ofac | ✅ NO_MATCH | — | 0.0000 | none | — | — |
| Aeroflot Russian Airlines | us_csl | 🔴 POTENTIAL_MATCH | PJSC AEROFLOT | 0.7716 | core_name_reverse | PJSC AEROFLOT | — |
| Aeroflot Russian Airlines | uk_csl | 🔴 POTENTIAL_MATCH | PJSC Aeroflot | 0.7716 | core_name_reverse | PJSC Aeroflot | — |
| Aeroflot Russian Airlines | eu_csl | ✅ NO_MATCH | — | 0.0000 | none | — | — |
| Aeroflot Russian Airlines | un_csl | ✅ NO_MATCH | — | 0.0000 | none | — | — |

### 4. Raw Search (T5.1)
- **Index Record Counts (112,605 total in `data/raw_index.db`):** `us_ofac`: 19,944 | `us_csl`: 26,159 | `uk_csl`: 58,609 | `eu_csl`: 6,234 | `un_csl`: 1,010 | `bis_aircraft`: 305 | `eu_air_safety`: 156 | `faa_iasa`: 9 | `in_mha_first_schedule`: 48 | `in_mha_fourth_schedule`: 80 | `in_mha_unlawful_assoc`: 20 | `fatf_jurisdictions`: 31.
- **Test Results Table:** `RUS2426` -> 3 UK hits (12ms) | `VP-BCD` -> 1 BIS hit (11ms) | `41215` -> 1 BIS hit (10ms) | `Sberbank` -> hits on OFAC, US CSL, UK, EU (28ms) | `Resistance Front` -> 4 hits inc. MHA First Schedule (12ms) | `"ab"` -> rejected: minimum 3 chars. Missing raw files render ⚪ in status registry.

### 4a. Verification Links & Manual Check Tab (T5.2)
- **Verification Links:** Record-level links operational for OFAC (`Details.aspx?id={id}`), OpenSanctions (`entities/{id}/`), BIS aircraft doc, and MHA portal. Search-page fallback + "Copy name" & "Copy ID" operational for UK, EU, UN, and US CSL.
- **HTTP 200 Checks:** All official landing/search URLs return HTTP 200 (including updated EC DG MOVE `/transport-themes/` and FATF topics endpoints).
- **Manual Check Tab:** 13 official source verification rows with direct link buttons, copy buttons, status selectors, and comment boxes. Saves audit log with `mode = manual` and embeds findings into PDF/Excel reports.

### 5. Launch & App Status
- `run_app.bat` tested: launches Docker, verifies Watchman ping, runs Streamlit, and opens browser.
- Desktop shortcut `%USERPROFILE%\Desktop\Naughty or not.lnk` successfully created pointing to `run_app.bat`.
- Streamlit Deploy button removed via `client.toolbarMode = "minimal"`.
- App is **running and left open** at `http://127.0.0.1:8501`.

### 6. Every Target NOT Met
None, with evidence in sections 1–5.

### 7. Test Counts & Commit Hashes
- **Test Suite:** 67 tests passed, 0 failed (100% pass rate in 49.37s).
- **Commit Hashes:**
  - `a7f860f`: T1.7 engine fixes, non-discarding candidate below-threshold tier, type mismatch, streamlit privacy
  - `7dab901`: T5.1 Raw search mode and T5.2 verification links with Manual check tab
  - `eac4ab6`: Launch scripts (`run_app.bat`, `stop_app.bat`), desktop shortcut, and updated README
  - `ca888a5`: Review table regeneration with `+nℹ️` counts and 3 review screenshots

### 8. Open Decisions
1. **Raw Index Auto-Sync:** Current index builds on refresh button; confirm if raw list files should re-download automatically on app startup.
2. **FTS5 Trigram Expansion:** Confirm if substring search inside tokens should use FTS5 trigram indexes for sub-millisecond full-text queries.
3. **Manual Check Export Consolidation:** Confirm whether manual check records should persist across multiple client sessions or remain session-scoped.

### Screenshots
- Raw search for "RUS2426": `reviews/screens/05_raw_search_rus2426.png`
- Volga Logistics with ℹ️ candidates: `reviews/screens/06_volga_logistics_info_expanded.png`
- S7 Airline search: `reviews/screens/07_s7_airline_search.png`
