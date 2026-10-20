# Review T1.3 and T3: Screening Targets & Aviation Safety Integration

## 1. T1.3 Target Verification & Findings
| Item | Target Query & List | Status | Matched Hit (ID, Score, Reason) |
| --- | --- | --- | --- |
| 1 | "Sberbank of Russia" on `eu_csl` | MET | Сбербанк (ID: 142064, Score: 0.6904, 🔴 `core_name_reverse` via alias "Sberbank") |
| 2 | "S7 Airlines" on `us_csl` | MET | SIBERIAN AIRLINES D/B/A S7 AIRLINES (ID: b04d5f..., Score: 0.6000, 🔴 `core_name`) |
| 3 | "Mohammed Khan" on `us_ofac` | MET | Primary: Haji Asad Khan Zarkari MOHAMMADHASNI; Alias: "Mohammed KHAN" (ID: 10898, Score: 0.8122, 🔴 `score_and_core_name`) |
| 4 | "UTair" on `us_csl` | MET | UTAIR AVIATION JSC (ID: dc7f34..., Score: 0.7285, 🟠 `score`); weak words never promote to 🔴 |

- **Mohammed Khan OFAC IDs:** ID 10898 (*Haji Asad Khan Zarkari MOHAMMADHASNI*) carries exact listed alias `"Mohammed KHAN"` (`0.8122` -> 🔴). ID 12588 (*Haji Mohammad KHAN*) has no aliases and scores `0.7557` (subset match only -> 🟠 `partial_name_person`).
- **UTair weak word rule:** `UTAIR AVIATION JSC` previously triggered false subset promotion due to `AVIATION JSC`. Restricting promotion to non-weak distinctive words retains proper 🟠 tier.

## 2. Per-List Screening Tier Summary (Selected T1.3 Targets)
| Query | List | Tier | Best Hit Name | Score | Reason |
| --- | --- | --- | --- | --- | --- |
| Sberbank of Russia | eu_csl | 🔴 | Сбербанк (alias Sberbank) | 0.6904 | core_name_reverse |
| S7 Airlines | us_csl | 🔴 | SIBERIAN AIRLINES D/B/A S7 AIRLINES | 0.6000 | core_name |
| UTair | us_csl | 🟠 | UTAIR AVIATION JSC, | 0.7285 | score |
| Mohammed Khan | us_ofac | 🔴 | Haji Asad Khan Zarkari MOHAMMADHASNI | 0.8122 | score_and_core_name |

## 3. T3 Aviation Data Sources & Counts
| Source | Official URL | Pub Date | Records / Coverage |
| --- | --- | --- | --- |
| BIS Aircraft | https://www.bis.gov/media/documents/gp-10-list-091225-current-bis-list-commercial-private-aircraft-potential-violation-export | 2025-09-12 | 306 active aircraft, 8 removals (Belavia) |
| EU Air Safety List | https://transport.ec.europa.eu/document/download/7414988e-6e85-455b-8c8d-aece8e932aa9_en?filename=air-safety-list.pdf | 2026-06-09 | 136 Annex A airlines, 2 Annex B, 18 state bans |
| FAA IASA | https://www.faa.gov/sites/faa.gov/files/IASAWSR119r.pdf | 2025-04-18 | 9 Category 2 jurisdictions (incl. Russia, Venezuela) |
| Airline Aliases | `data/aviation/airline_aliases.csv` | Initial seed | 11 canonical carriers (verified ICAO/IATA) |

## 4. T3 Aviation Test Verification
- **BIS Tail Numbers & MSN:** `RA-73093` (Aeroflot B737), `VP-BCD` (previous tail), and MSN `41215` each return 🔴 `EXPORT_CONTROL` individually.
- **Removals Guard:** Belavia `EW-254PA` / MSN `26294` in removals returns ⚪ `NO_MATCH` (never matched).
- **EU ASL:** Aeroflot and S7 return ⚠️ `SAFETY_BAN` (Annex A); Azur Air returns ⚠️ `SAFETY_BAN` (State ban / Russia).
- **EU ASL Annex B:** Iran Air returns ⚠️ `SAFETY_RESTRICTED` with permitted types (all fleet except Fokker F100 and Boeing B747).
- **FAA IASA:** States `Russia` and `Venezuela` return ⚠️ `SAFETY_OVERSIGHT` (Category 2).
- **Safety Label:** All EU and FAA safety findings carry exact label: `"Safety flag — not a sanctions finding"`.
- **Clean Tests:** IndiGo and tail `VT-IFR` return ⚪ `NO_MATCH` (0 findings).
- **Resiliency:** Corrupt and missing PDF inputs return empty results cleanly without exceptions.

## 5. Test Pass Counts and Commits
- **T1.3 Commit:** `ccff536` (`fix(screening): T1.3 distinctive token recall, S7 D/B/A matching, and UTair weak word fix`)
- **T3 Commit:** `7ec35f4` (`feat(aviation): implement BIS aircraft, EU air safety list, and FAA IASA screening`)
- **Total Unit Tests:** 25 passed, 0 failed (`tests/test_aviation.py`: 11, `tests/test_tiering.py`: 8, `tests/test_golden.py`: 1, `tests/test_opensanctions.py`: 3, `tests/test_watchman_client.py`: 2).

## 6. Open Decisions for You
1. **Auto-refresh frequency:** Parser defaults to 24-hour cache TTL; confirm if background cron or on-demand fetch is preferred.
2. **Multi-source consolidation:** Should airline safety findings (⚠️) be returned as supplementary tabs alongside Watchman sanction tiers?
3. **Aircraft MSN format:** Should MSN search require accompanying operator/type to avoid false collisions on short serials (< 4 digits)?
4. **Carrier alias maintenance:** Confirm process for adding non-Russian/non-Iranian regional carriers to `airline_aliases.csv`.
