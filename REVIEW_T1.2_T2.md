# Review T1.2 & T2: Screening Tiering and OpenSanctions

## 1. Final Per-List Tier Table
| Query | us_ofac | us_csl | uk_csl | eu_csl | un_csl |
|---|---|---|---|---|---|
| Sberbank | 🔴 0.6622 (core_name) | 🔴 0.6622 (core_name) | 🔴 0.6904 (core_name) | 🔴 0.6904 (core_name) | ✅ — |
| Sberbank of Russia | 🔴 0.8122 (score+core) | 🔴 0.8122 (score+core) | 🔴 0.6904 (core_name) | ✅ — | ✅ — |
| VTB Bank | 🔴 0.8122 (score+core) | 🔴 0.8122 (score+core) | 🔴 0.7679 (core_name) | 🔴 0.6904 (core_name) | ✅ — |
| S7 Airlines | 🟠 0.7549 (score) | 🟠 0.7645 (score) | 🔴 0.8122 (score+core) | ✅ — | ✅ — |
| Siberia Airlines | ✅ — | ✅ — | 🔴 0.7919 (core_name) | ✅ — | ✅ — |
| Aeroflot | ✅ — | 🔴 0.7716 (core_name) | 🔴 0.7716 (core_name) | ✅ — | ✅ — |
| Azur Air | ✅ — | 🔴 0.8122 (score+core) | ✅ — | ✅ — | ✅ — |
| UTair | ✅ — | 🔴 0.7285 (core_name) | ✅ — | 🔴 0.8122 (score+core) | ✅ — |
| Jaipur Int Airport | ✅ — | ✅ — | ✅ — | ✅ — | ✅ — |
| Adani Airport Hold | ✅ — | ✅ — | ✅ — | ✅ — | ✅ — |
| Air India | ✅ — | ✅ — | ✅ — | ✅ — | ✅ — |
| IndiGo | 🟠 0.7635 (score) | ✅ — | ✅ — | ✅ — | ✅ — |
| InterGlobe Aviation | ✅ — | ✅ — | ✅ — | ✅ — | ✅ — |
| Siberian Wellness | ✅ — | ✅ — | ✅ — | ✅ — | ✅ — |
| Rajesh Kumar | 🟠 0.7742 (partial_person) | ✅ — | 🟠 0.7742 (partial_person) | ✅ — | ✅ — |
| Mohammed Khan | 🔴 0.8122 (score+core) | 🟠 0.7347 (partial_person) | ✅ — | ✅ — | ✅ — |
| Sky Bank | ✅ — | ✅ — | ✅ — | ✅ — | ✅ — |
| Volga Logistics | ✅ — | ✅ — | ✅ — | ✅ — | ✅ — |

## 2. Changes vs T1.1
- UTair on us_csl: promoted 🟠 (0.7285, score) -> 🔴 (0.7285, core_name) as "aviation" is now a weak word.
- Rajesh Kumar on uk_csl: reason updated from score -> partial_name_person via alias splitting and person rule.
- Rajesh Kumar on us_ofac: reason updated from score -> partial_name_person on Gupta alias.
- S7 Airlines on uk_csl: matched alias refined directly to "S7 Airlines" via bracket/delimiter splitting.

## 3. Matches on Clean and Near-Miss Controls
- Mohammed Khan on us_ofac: 🔴 (0.8122) — True positive on listed SDN alias (ID 10898); secondary DOB/country resolves counterparty.
- Mohammed Khan on us_csl: 🟠 (0.7347) — False positive review flag from partial token overlap with Mohammad Jan Khan Mangal.
- IndiGo on us_ofac: 🟠 (0.7635) — False positive review flag on Russian LLC INDIGO 3D (distinctive token "3D" blocks 🔴).
- Rajesh Kumar on us_ofac & uk_csl: 🟠 (0.7742) — Near-miss review flag on Gupta brothers' alias (Rajesh Kumar GUPTA).

## 4. OpenSanctions Live Results vs Watchman & Credits
| Query | Watchman Top Hit | OpenSanctions Top Hit | Score | OS Tier |
|---|---|---|---|---|
| Aeroflot | 🔴 us_csl/uk_csl (0.7716, PJSC Aeroflot) | 🔴 PJSC Aeroflot (NK-LVyjEWp4GKdvHCQBysu8tQ) | 0.8772 | 🔴 POTENTIAL_MATCH |
| VTB Bank | 🔴 us_ofac/csl/uk/eu (0.8122, VTB Bank) | 🔴 VTB Bank PJSC (NK-mvzx7uNDj9jZf8EAxaHH2h) | 1.0000 | 🔴 POTENTIAL_MATCH |
| Jaipur Int Airport | ✅ NO_MATCH across all lists | ✅ NO_MATCH (0 candidates) | 0.0000 | ✅ NO_MATCH |

- Credits consumed: 3 credits | Total API calls: 3 | Rate: 1 credit per query | Audit log: logs/opensanctions_usage.csv

## 5. Test Pass/Fail Counts & Commit Hashes
- Test results: 12 passed, 0 failed across test_tiering, test_opensanctions, test_golden, and test_watchman_client.
- Commit cf4dcdc: feat(opensanctions): add OpenSanctions client with credit guard, usage logging, and tests
- Commit 554c267: fix(tiering): two-way core-name check, alias splitting, weak words, person rules, and golden set
- Commit e861ff8: feat(screening): add match tiering layer and core-name normalization
- Commit a73e5b7: Initial commit: project skeleton for Sanction checK

## 6. Open Decisions for You
1. Golden set verification: Toggle verified flags from false to true in tests/golden_set.json as you audit official gazettes.
2. Siberia Airlines stem: Keep stem distinct (gives 🟠/✅ on US CSL, 🔴 on UK CSL) or add custom mapping for Siberia/Siberian.
3. OpenSanctions UI details: Decide whether to display OpenSanctions match explanation features in expandable UI rows.
4. Secondary ID workflow: Confirm whether counterparty DOB and nationality should be mandatory or optional inputs in UI.
