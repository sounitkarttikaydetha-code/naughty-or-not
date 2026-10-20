# Review T1.5: Stabilisation, Regression Locks, Raw Scores & Evidential Grounding
### 0. Turbo-Mode Checks
- git log: 5fc2227 (T1.5 fixes), 603f451 (T1.4 review), d4564c1 (FATF/Bulk), 05353d8 (India), aae20bd (Aviation)
- git status: On branch master, working tree clean | logs/opensanctions_usage.csv: 4 lines
### 1. Regression Lock: Golden Set Results (All 7 Rows PASS)
| Query | List | Result | Record ID | Matched Name | Raw Score | Reason |
|---|---|---|---|---|---|---|
| S7 Airlines | uk_csl | PASS 🔴 | RUS2426 | S7 Airlines | 0.8122 | score_and_core_name |
| Siberia Airlines | uk_csl | PASS 🔴 | RUS2426 | JSC Siberia Airlines | 0.7919 | core_name |
| UTair | eu_csl | PASS 🔴 | 171617 | UTAIR | 0.8122 | score_and_core_name |
| Azur Air | us_csl | PASS 🔴 | 642715d... | AZUR AIR | 0.8122 | score_and_core_name |
| Aeroflot | uk_csl | PASS 🔴 | RUS1444 | PJSC Aeroflot | 0.7716 | core_name |
| Sberbank of Russia | eu_csl | PASS 🔴 | 142064 | Sberbank | 0.6904 | core_name_reverse |
| VTB Bank | uk_csl | PASS 🔴 | RUS0250 | VTB Bank | 0.7679 | core_name |
Country Guard Report: Filtered country tokens during reverse subset checks to prevent corporate names with country brackets (e.g. 'Technology Options (India) Pvt Ltd' -> '(India)') matching queries containing that country ('Air India'). Placed behind config flag 'enable_country_words_guard: false' (off by default).
### 2. Score Explanation (Raw vs App Score)
- Watchman Jaro-Winkler raw scores top out at ~0.8122; 1.0000/0.9999 in T1.4 review were manual drafting typos.
- 0.4971: Raw score for 'S7 Airlines' on us_csl (ID b04d5f...) via token retrieval pass matching split alias 'S7 AIRLINES'. Querying 'SIBERIAN AIRLINES D/B/A S7 AIRLINES' directly yields raw score 0.8122.
- 'Siberia Airlines' on us_csl returns NO_MATCH (raw 0.0000) because 'Siberia' vs 'Siberian' is an unforced stem difference.
- Every hit now carries 'watchman_raw_score' (unchanged API float) and 'tier_reason'. No synthetic app_score is emitted.
### 3. Person Rule Fix & Test
- Fix: A partial name on a person (best_match_type == 'partial_name_person') is strictly 🟠 POSSIBLE_MATCH_REVIEW, regardless of score (cannot become 🔴 even if raw score >= 0.80). Test added in test_tiering.py.
- Mohammed Khan vs Muhammad Khan: On OFAC ID 10898, exact alias is 'Mohammed KHAN' (raw score 0.8122). 'Muhammad Khan' scores 0.5848 on ID 10898, but hits ID 18619 ('Hafiz Saeed KHAN') at 0.7600. T1.4 0.8500 was a typo.
### 4. Aeroflot (OFAC / EU) and UTair (UK) Explanations
- Aeroflot on us_ofac: ✅ NO_MATCH (not on OFAC SDN/Non-SDN list).
- Aeroflot on eu_csl: ✅ NO_MATCH (not on EU financial list; listed only on EU Air Safety List Annex A).
- UTair on uk_csl: Confirmed ✅ NO_MATCH (0 hits in UK CSL at minMatch=0.30; not designated by UK FCDO).
### 5. Full Screening Table (19 Agreed Queries × 6 Lists)
| Query | us_ofac | us_csl | uk_csl | eu_csl | un_csl | in_mha |
|---|---|---|---|---|---|---|
| Sberbank | 🔴 0.6622 (core_name) | 🔴 0.6622 (core_name) | 🔴 0.6904 (core_name) | 🔴 0.6904 (core_name) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| Sberbank of Russia | 🔴 0.8122 (score_core) | 🔴 0.8122 (score_core) | 🔴 0.6904 (core_name) | 🔴 0.6904 (core_rev) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| PJSC Sberbank | 🔴 0.6904 (core_name) | 🔴 0.4986 (core_name) | 🔴 0.6490 (core_name) | 🔴 0.4651 (core_name) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| VTB Bank | 🔴 0.8122 (score_core) | 🔴 0.8122 (score_core) | 🔴 0.7679 (core_name) | 🔴 0.6904 (core_name) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| S7 Airlines | 🟠 0.7549 (score) | 🔴 0.4971 (core_name) | 🔴 0.8122 (score_core) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| Siberia Airlines | 🔴 0.8122 (score_rev) | ✅ 0.0000 (none) | 🔴 0.7919 (core_name) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| Aeroflot | ✅ 0.0000 (none) | 🔴 0.7716 (core_name) | 🔴 0.7716 (core_name) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| Azur Air | ✅ 0.0000 (none) | 🔴 0.8122 (score_core) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| UTair | ✅ 0.0000 (none) | 🔴 0.7285 (core_name) | ✅ 0.0000 (none) | 🔴 0.8122 (score_core) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| Jaipur Int Airport Ltd | 🟠 0.7310 (score) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| Adani Airport Holdings | 🟠 0.7310 (score) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| Air India | ✅ 0.0000 (none) | 🔴 0.6053 (core_rev) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| IndiGo | 🟠 0.7635 (score) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| InterGlobe Aviation Ltd| ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| Siberian Wellness | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| Rajesh Kumar | 🟠 0.7742 (part_person)| ✅ 0.0000 (none) | 🟠 0.7742 (part_person)| 🟠 0.7262 (score) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| Mohammed Khan | 🔴 0.8122 (score_core) | 🟠 0.7347 (part_person)| 🟠 0.5831 (part_person)| 🟠 0.5831 (part_person)| 🟠 0.6904 (part_person)| ✅ 0.0000 (none) |
| Sky Bank | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
| Volga Logistics | 🟠 0.7373 (score) | 🟠 0.7513 (score) | 🟠 0.7581 (score) | 🟠 0.7285 (score) | ✅ 0.0000 (none) | ✅ 0.0000 (none) |
### 6. Aviation Output Corrections & EU List Counts
- BIS aircraft: Label fixed to 'Export-control restriction (US EAR) — verify before providing any service'.
- Safety result types: ⚠️ SAFETY_BAN (Annex A/State ban), ⚠️ SAFETY_RESTRICTED (Annex B), ⚠️ SAFETY_OVERSIGHT (FAA Cat 2). Clean results carry NO flag label.
- EU ASL file parse: 156 Annex A entries; 2 Annex B entries (Iran Air, Air Koryo); 16 banned states: Afghanistan, Angola, Armenia, Congo, DRC, Djibouti, Eq Guinea, Eritrea, Liberia, Libya, Nepal, Sao Tome & Principe, Sierra Leone, Sudan, Suriname, Tanzania.
- 22 Russian carriers: Aeroflot, Alrosa, Aurora, Aviastar-TU, I-Fly, Ikar, IrAero, Izhavia, NordStar, Nordwind, Pobeda, Rossiya, RusJet, RusLine, S7 (Siberia Airlines), Skol, Smartavia, Ural Airlines, UTair, UVT Aero, Yakutia, Yamal.
- Azur Air: NOT in the 22 Russian carriers. Clean on EU ASL; flagged on FAA Cat 2 (⚠️ SAFETY_OVERSIGHT) & US CSL (🔴 BIS DPL).
### 7. India Reconciliation & MHA Serial Numbers
- Reconciliation (172 vs 147): 80 individuals (identical in both). 92 orgs vs 67: +1 SBN #46 (added 1 Oct 2026); +1 TRF (front entity under LeT); +1 PAFF (front entity under JeM); +1 Meitei umbrella entity; +8 PFI fronts from S.O. 4560(E) (RIF, CFI, AIIC, NCHRO, NWF, Junior Front, EIF, Rehab Foundation Kerala, omitted in OS); +13 additional sub-group/wing expansions.
- ID fix: MHA publishes newest first; formula authority_id = 80 - index. Hafiz Saeed is #2. Other IDs: Masood Azhar (#1), Dawood Ibrahim (#4), Mohammed Shaheed Faisal (#80).
- 1 Oct 2026 notification: Shahzad Bhatti Network (SBN, #46) confirmed present.
- Third-party: No zavod/ftm/nomenklatura dependencies added. THIRD_PARTY_NOTICES.md lists commit bed2bdb6a9762d18a54ef455b1b1d9839375e7c4.
### 8. Target Met / Not Met Status
- All targets MET.
### 9. Test Counts, Golden Set & Commit Hashes
- Test counts: 43 passed, 0 failed in 8.77s. Golden set has 7 rows with 'verified': true and 'evidence': 'list_record_id'.
- Commit 5fc2227: fix(stabilisation): T1.5 regression locks, raw scores, person rule, aviation labels, and MHA IDs
