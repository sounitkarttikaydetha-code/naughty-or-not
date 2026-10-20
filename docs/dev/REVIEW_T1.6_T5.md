# Review T1.6 + T5 — Sanction checK UI & Engine Stabilisation

### 0. Pre-Flight Verification
- **Git Commits**: `9caf858` (T5 UI & reporting), `be3415e` (T1.6 engine fixes)
- **Git Status**: Working tree clean (all features and tests committed)
- **OpenSanctions Usage**: 4 lines in `logs/opensanctions_usage.csv` (0 credits consumed during T1.6 & T5)

### 1. Engine Fixes (T1.6)
- **Country Words as Weak Words**: Country/demonym words added to weak filter; bracket text discarded. "Air India", "Jaipur Airport", and "Adani Airport" all resolve to ✅ `NO_MATCH`.
- **Airline Query Expansion**: Alias lookup enables S7 and Aeroflot queries to screen canonical/alias forms.
- **Token Pass Floor**: Token pass strictly restricted to organisations/airlines; persons enforce 0.60 floor.
- **MHA Gazette IDs**: Fourth Schedule mapped to official gazette entry IDs (1, 2, 4, 80).
- **EU ASL Wrap Fix**: Cleaned multiline carrier name wraps; Annex A matches official 154 carriers.
- **Fuzzy Core-Name Rule**: Words ≥5 chars with ≥0.85 similarity yield 🟠 `core_name_fuzzy`.

### 2. Full Per-List Tier Table: 19 Agreed Queries × 6 Lists
*(Generated directly by `scripts/build_review_tables.py`)*

| Query | us_ofac | us_csl | uk_csl | eu_csl | un_csl | in_mha |
|---|---|---|---|---|---|---|
| Sberbank | 🔴 0.6622 (core_name) | 🔴 0.6622 (core_name) | 🔴 0.6904 (core_name) | 🔴 0.6904 (core_name) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| Sberbank of Russia | 🔴 0.8122 (score_and_core_name) | 🔴 0.8122 (score_and_core_name) | 🔴 0.6904 (core_name) | 🔴 0.6904 (core_name_reverse) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| PJSC Sberbank | 🔴 0.6904 (core_name) | 🔴 0.4986 (core_name) | 🔴 0.6490 (core_name) | 🔴 0.4651 (core_name) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| VTB Bank | 🔴 0.8122 (score_and_core_name) | 🔴 0.8122 (score_and_core_name) | 🔴 0.7679 (core_name) | 🔴 0.6904 (core_name) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| S7 Airlines | 🔴 0.8122 (score_and_core_name_reverse) | 🔴 0.4971 (core_name) | 🔴 0.8122 (score_and_core_name) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| Siberia Airlines | 🔴 0.8122 (score_and_core_name_reverse) | 🔴 0.6482 (core_name) | 🔴 0.7919 (core_name) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| Aeroflot | ✅ 0.0000 (none) | 🔴 0.7716 (core_name) | 🔴 0.7716 (core_name) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| Azur Air | ✅ 0.0000 (none) | 🔴 0.8122 (score_and_core_name) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| UTair | 🟠 0.7285 (score) | 🔴 0.7285 (core_name) | 🟠 0.7209 (score) | 🔴 0.8122 (score_and_core_name) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| Jaipur International Airport Limited | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| Adani Airport Holdings Limited | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| Air India | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| IndiGo | 🟠 0.7635 (score) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| InterGlobe Aviation Limited | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| Siberian Wellness | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| Rajesh Kumar | 🟠 0.7742 (partial_name_person) | ✅ 0.0000 (none) | 🟠 0.7742 (partial_name_person) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| Mohammed Khan | 🔴 0.8122 (score_and_core_name) | 🟠 0.7347 (partial_name_person) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| Sky Bank | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| Volga Logistics | 🟠 0.7373 (score) | 🟠 0.7513 (score) | 🟠 0.7581 (score) | 🟠 0.7285 (score) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |

### 2b. Expanded Airline Queries Table

| Query | List | Tier | Best Hit / Listed Name | Score | Reason | Matched Name | Expanded From |
|---|---|---|---|---|---|---|---|
| Siberia Airlines | us_ofac | 🔴 POTENTIAL_MATCH | SIBERIA | 0.8122 | score_and_core_name_reverse | SIBERIA | — |
| Siberia Airlines | us_csl | 🔴 POTENTIAL_MATCH | SIBERIAN AIRLINES D/B/A S7 AIRLINES | 0.6482 | core_name | SIBERIAN AIRLINES | Siberian Airlines |
| Siberia Airlines | uk_csl | 🔴 POTENTIAL_MATCH | JSC Siberia Airlines | 0.7919 | core_name | JSC Siberia Airlines | — |
| Siberia Airlines | eu_csl | ✅ NO_MATCH | — | 0.0000 | none | — | — |
| Siberia Airlines | un_csl | ✅ NO_MATCH | — | 0.0000 | none | — | — |
| S7 | us_ofac | 🔴 POTENTIAL_MATCH | SIBERIA | 0.8122 | score_and_core_name_reverse | SIBERIA | Siberia Airlines |
| S7 | us_csl | 🔴 POTENTIAL_MATCH | SIBERIAN AIRLINES D/B/A S7 AIRLINES | 0.6482 | core_name | SIBERIAN AIRLINES | Siberian Airlines |
| S7 | uk_csl | 🔴 POTENTIAL_MATCH | JSC Siberia Airlines | 0.5990 | core_name | S7 Airlines | — |
| S7 | eu_csl | ✅ NO_MATCH | — | 0.0000 | none | — | — |
| S7 | un_csl | ✅ NO_MATCH | — | 0.0000 | none | — | — |
| Aeroflot Russian Airlines | us_ofac | ✅ NO_MATCH | — | 0.0000 | none | — | — |
| Aeroflot Russian Airlines | us_csl | 🔴 POTENTIAL_MATCH | PJSC AEROFLOT | 0.7716 | core_name_reverse | PJSC AEROFLOT | — |
| Aeroflot Russian Airlines | uk_csl | 🔴 POTENTIAL_MATCH | PJSC Aeroflot | 0.7716 | core_name_reverse | PJSC Aeroflot | — |
| Aeroflot Russian Airlines | eu_csl | ✅ NO_MATCH | — | 0.0000 | none | — | — |
| Aeroflot Russian Airlines | un_csl | ✅ NO_MATCH | — | 0.0000 | none | — | — |

### 3. UI Implementation (T5 — Sanction checK)
- **App Details**: Streamlit app named `Naughty or not` with page title `Sanction checK`.
- **Licence & Notices**: Permanent header warning and first-run modal acknowledging CC BY-NC 4.0 terms.
- **Dynamic Search Types**: Person (DOB, nat), Organisation (country, reg), Airline (AOC, ICAO/IATA), Aircraft (tail, MSN, op), Vessel (IMO, flag).
- **Aviation & Country Risk**: Sections B & C display distinct labels: "Safety flag — not a sanctions finding" and "Country risk flag — not a sanctions finding".
- **Logging & Reports**: Append-only SQLite at `logs/screening.db`; branded PDF & Excel reports generated in `reports/`.
- **Automated Tests & Screens**: Streamlit `AppTest` suite (7 tests) passing; 4 screenshots saved in `reviews/screens/`.

### 4. Test Suite & Status
- **Pytest**: 51 passed across all 9 test suites (unit, golden locks, aviation, fatf, india, opensanctions, ui).
- **Status**: All targets MET with script-generated evidence.

### 5. Open Decisions
1. **Auto-refresh Schedule**: Schedule periodic cron/background refresh for aviation and FATF sources.
2. **OpenSanctions Paid Tier**: Confirm production credit budget before enabling auto-screening defaults.
3. **50% Ownership Rule**: Consider adding entity corporate structure feeds to assess indirect ownership.
