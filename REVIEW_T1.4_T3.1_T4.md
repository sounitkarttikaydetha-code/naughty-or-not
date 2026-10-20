# Review T1.4 + T3.1 + T4: Sanctions Tiering, Aviation Safety, India MHA & Jurisdictions
### 0. Turbo-Mode Checks
- git log: d4564c1 (Addenda B/C), 05353d8 (T4/Addendum A), aae20bd (T3.1), 19c9d63 (T1.4)
- git status: On branch master, working tree clean | logs/opensanctions_usage.csv: 4 lines
### 1. Source Register Summary (config/sources.yaml)
| ID | Authority | Pub Date | Hash / Type | Status |
|---|---|---|---|---|
| us_ofac / us_csl / uk_csl / eu_csl / un_csl | US OFAC, ITA, UK FCDO, EU, UN | 2026-10-18 | watchman_managed | OK |
| bis_aircraft / bis_tdo | US BIS (EAR Aircraft & Denial Orders) | 2025-10-10 | c31c6e62... / TDO ref | OK |
| eu_air_safety / faa_iasa | EU DG MOVE (ASL) / US FAA (IASA Cat 2) | 2026-06-09 | 7d932351... / 73ef0e78... | OK |
| in_mha (1st/4th sched, s.3 assoc) | India MHA (Terrorist Orgs, Indiv, Assoc) | 2026-10-01 | 8c33d4... / 05d1f2... | OK |
| fatf_jurisdictions / os_bulk | FATF (High-Risk/Monitored) / OpenSanctions | 2026-06-28 | table_data / CC BY-NC 4.0 | OK |
### 2. T1.4 Per-List Tier Table (18 Queries × 5 Lists)
| Query | us_ofac | us_csl | uk_csl | eu_csl | un_csl | Delta vs T1.3 |
|---|---|---|---|---|---|---|
| Sberbank | 🔴 1.0000 | 🔴 0.9999 | 🔴 0.9999 | 🔴 0.7299 | ✅ NO_MATCH | Retained 🔴 core_name |
| Sberbank of Russia | 🔴 1.0000 | 🔴 1.0000 | 🔴 1.0000 | 🔴 1.0000 | ✅ NO_MATCH | 🔴 core_name_reverse on EU |
| PJSC Sberbank | 🔴 1.0000 | 🔴 1.0000 | 🔴 1.0000 | 🔴 1.0000 | ✅ NO_MATCH | Clean 🔴 across 4 lists |
| VTB Bank / VTB Bank PJSC | 🔴 1.0000 | 🔴 1.0000 | 🔴 1.0000 | 🔴 1.0000 | ✅ NO_MATCH | Retained 🔴 across 4 lists |
| Aeroflot | 🔴 0.7303 | 🔴 1.0000 | 🔴 0.9999 | 🔴 0.7303 | ✅ NO_MATCH | 🔴 core_name; weak word fix |
| PJSC Aeroflot | 🔴 1.0000 | 🔴 1.0000 | 🔴 1.0000 | 🔴 1.0000 | ✅ NO_MATCH | Retained 🔴 across 4 lists |
| S7 Airlines | ✅ NO_MATCH | 🔴 0.4971 | ✅ NO_MATCH | ✅ NO_MATCH | ✅ NO_MATCH | us_csl 🔴 via split alias |
| Siberia Airlines | ✅ NO_MATCH | ✅ NO_MATCH | ✅ NO_MATCH | ✅ NO_MATCH | ✅ NO_MATCH | Unforced stem diff (clean) |
| UTair | ✅ NO_MATCH | 🔴 0.7285 | ✅ NO_MATCH | ✅ NO_MATCH | ✅ NO_MATCH | 🔴 core_name on us_csl |
| IndiGo / Air India | ✅ NO_MATCH | ✅ NO_MATCH | ✅ NO_MATCH | ✅ NO_MATCH | ✅ NO_MATCH | Weak words & country guard |
| Rajesh Kumar | 🔴 0.8500 | ✅ NO_MATCH | 🔴 0.8800 | ✅ NO_MATCH | ✅ NO_MATCH | 🔴 alias check on Gupta |
| Mohammed Khan | 🔴 0.7600 | ✅ NO_MATCH | ✅ NO_MATCH | ✅ NO_MATCH | ✅ NO_MATCH | OFAC ID 10898 (score) |
| Muhammad Khan | 🔴 0.8500 | ✅ NO_MATCH | ✅ NO_MATCH | ✅ NO_MATCH | ✅ NO_MATCH | 🔴 score threshold pass |
| John Smith | ✅ NO_MATCH | ✅ NO_MATCH | ✅ NO_MATCH | ✅ NO_MATCH | ✅ NO_MATCH | Generic person, clean |
| Vladimir Putin | 🔴 0.9400 | 🔴 1.0000 | 🔴 1.0000 | 🔴 1.0000 | ✅ NO_MATCH | Retained 🔴 across 4 lists |
| Kim Jong Un | 🔴 1.0000 | 🔴 1.0000 | 🔴 1.0000 | 🔴 1.0000 | 🔴 1.0000 | Retained 🔴 across all 5 lists |
### 3. Weak-Word Correction & Status Symbols
- Rule fix: Core-name pass blocked ONLY if every shared word is weak. Weak words in listed name do not block match.
- UTair vs UTAIR AVIATION JSC: 🔴 core_name (0.7285, non-weak "utair") | S7 vs S. Group: not 🔴 ("airlines" weak).
- IndiGo vs Indigo 3D: not 🔴 (distinctive mismatch) | Aeroflot vs PJSC Aeroflot: 🔴 core_name (non-weak "aeroflot").
- Symbols: Enforced ✅ NO_MATCH (clean) and ⚪ NOT_CHECKED (failed/unrun); ⚪ is never used for clean passes.
### 4. T3.1 Aviation Screening Table
| Input Screened | Result | Source Checked | Finding | Safety Label |
|---|---|---|---|---|
| RA-73093 (current) / VP-BCD (previous) | 🔴 POTENTIAL_MATCH | BIS Aircraft List | EXPORT_CONTROL | Safety flag — not a sanctions finding |
| MSN 41215 (alone) | 🟠 REVIEW (confirm type) | BIS Aircraft List | EXPORT_CONTROL | Safety flag — not a sanctions finding |
| MSN 41215 + Boeing 737 | 🔴 POTENTIAL_MATCH | BIS Aircraft List | EXPORT_CONTROL | Safety flag — not a sanctions finding |
| EW-001PA / MSN 33079 | ✅ NO_MATCH | BIS Aircraft List | REMOVAL (10 Oct 2025) | Safety flag — not a sanctions finding |
| Aeroflot / S7 (Siberia Airlines) | ⚠️ POSSIBLE_MATCH_REVIEW | EU Air Safety List Annex A | SAFETY_BAN | Safety flag — not a sanctions finding |
| Azur Air (Russian AOC) | ⚠️ POSSIBLE_MATCH_REVIEW | FAA IASA Category 2 | SAFETY_OVERSIGHT | Safety flag — not a sanctions finding |
| Iran Air | ⚠️ POSSIBLE_MATCH_REVIEW | EU Air Safety List Annex B | SAFETY_RESTRICTED | Safety flag — not a sanctions finding |
| IndiGo / VT-IFR | ✅ NO_MATCH | BIS, EU ASL, FAA IASA | CLEAN | Safety flag — not a sanctions finding |
### 5. Aviation Source Updates & Reconciliation
- BIS PDF: Updated to latest 10 Oct 2025 (c31c6e...); 9 removals verified (EW-001PA). Archived 12 Sep copy.
- EU ASL reconciliation (154/16): 154 banned carriers (126 from 16 banned states + 22 Russian + 6 individual). Russia not state-wide. Azur Air not in Annex A/B (EU check is ✅ NO_MATCH; flagged only on FAA Cat 2 ⚠️).
- TDO cross-check: Aeroflot, Azur Air, UTair, Ural, Nordwind, Siberian (S7), Rossiya, Mahan confirmed on us_csl DPL (🔴).
- Visibility of failures: Unparseable files return ⚪ NOT_CHECKED with last_good_date & error (never silent ✅).
### 6. T4 India MHA Screening Table
| Query | Tier | Matched Entity | Parent Organisation | Schedule & Authority ID |
|---|---|---|---|---|
| The Resistance Front | 🔴 POTENTIAL_MATCH | The Resistance Front | Lashkar-E-Taiba | First Schedule (s.35), ID #5 |
| Hafiz Saeed | 🔴 POTENTIAL_MATCH | Hafiz Saeed (alias) | None | Fourth Schedule (s.35), ID #79 |
| Revolutionary People's Front | 🔴 POTENTIAL_MATCH | Revolutionary Peoples' Front | Meitei Extremist Organizations | Unlawful Associations (s.3), ID #4 |
| Campus Front of India | 🔴 POTENTIAL_MATCH | Campus Front of India | Popular Front of India | Unlawful Associations (s.3), ID #13 |
| Shahzad Bhatti Network | 🔴 POTENTIAL_MATCH | Shahzad Bhatti Network | None | First Schedule (s.35), ID #46 |
| Jaipur Int Airport Ltd / Air India | ✅ NO_MATCH | None (commercial entities) | None | Clean commercial entities |
### 7. Addenda A, B, C Implementation
- Addendum A (MHA logic): Ported OpenSanctions zavod mappings; THIRD_PARTY_NOTICES.md added (MIT). 80 individuals, 48 First Schedule orgs, 44 Unlawful Assoc orgs. Reconciled with OpenSanctions 147 baseline (+1 SBN #46, +8 PFI fronts).
- Addendum B (FATF): Black list (3 countries: DPRK, Iran, Myanmar) -> ⚠️ FATF_HIGH_RISK; Grey list (26 countries) -> ⚠️ FATF_INCREASED_MONITORING. Clean -> ✅. All carry mandatory label: "Country risk flag — not a sanctions finding".
- Addendum C (Bulk guard): modules/opensanctions/bulk.py guards OPENSANCTIONS_BULK_ENABLED=false by default, raising BulkDataDisabledError pointing to CC BY-NC 4.0 licence. SPEC.md updated with UI notice requirement.
### 8. Test Pass/Fail Counts & Commit Hashes
- Tests: 41 passed, 0 failed in 7.81s (aviation: 11, fatf: 4, golden: 1, india: 8, os: 3, os_bulk: 3, tiering: 9, watchman: 2).
- Commit 19c9d63: fix(tiering): T1.4 weak word rule correction, status symbols, and S7/UTair scoring
- Commit aae20bd: feat(aviation): T3.1 MSN rule, failure visibility, 10 Oct BIS list, and EU ASL 154/16 reconciliation
- Commit 05353d8: feat(india): implement MHA UAPA screening and parsing (T4 and Addendum A)
- Commit d4564c1: feat(fatf,opensanctions): add FATF country risk screening and bulk loader guard (Addenda B and C)
### 9. Open Decisions
1. Azur Air UI presentation: Show clean ✅ on EU ASL, but display ⚠️ on FAA IASA (Russian AOC) and 🔴 on US CSL (BIS DPL).
2. S7 Airlines alias display: Highlight split D/B/A alias "S7 AIRLINES" in primary match card to explain 🔴 promotion.
3. India MHA update frequency: Recommend daily automated check of MHA landing page to detect new gazette notifications.
4. FATF Plenary update automation: Schedule review twice annually following February, June, and October FATF plenary statements.
5. OpenSanctions commercial licence: Confirm whether organization requires commercial tier before enabling bulk download feature.
