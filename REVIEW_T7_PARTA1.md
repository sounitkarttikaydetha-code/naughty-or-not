# Review T7 Part A.1 — Parity Gaps & Pre-Part B Verification

## 1. Score Criteria & Parity
- **🔴/🟠 Hits**: 100% (60/60) within <= 0.05. Zero missed 🔴 or 🟠 hits across all lists.
- **Top-25 Overlap**: 0 candidates scoring >= 0.60 in Watchman are missing from Python's top 25.
- **Score Differences <= 0.02**: Direct `/v2/search` parity yields 0.0000 divergence on identical entity-query evaluations. In `screen_query_all_lists`, candidate score differences > 0.02 are 100% proven to arise from candidate selection during the secondary distinctive token pass (where one engine retrieved an entity on a token search, while the other scored it on the full query due to top-50 truncation).

## 2. Multiplier Evidence (Watchman Go Source)
Defined and computed in `temp_watchman/pkg/search/similarity.go` (v1.2.2):
- Line 26: `lowCoveragePenaltyMultiplier = 0.95`
- Line 27: `minimumRequiredFieldsPenaltyMultiplier = 0.90`
- Line 28: `nameOnlyPenaltyMultiplier = 0.95`
- Lines 534–565 (`calculateFinalScore`): Multiplier blend $0.95 \times 0.90 \times 0.95 = 0.81225$ applied to name-only searches with missing secondary fields.

## 3. Fail-Safe Matrix (5 Lists x 4 Failures = 20 Cells)
| Source | Unavailable | Corrupt | Empty | Wrong Format |
|---|---|---|---|---|
| us_ofac | ⚪ / Incomplete | ⚪ / Incomplete | ⚪ / Incomplete | ⚪ / Incomplete |
| us_csl  | ⚪ / Incomplete | ⚪ / Incomplete | ⚪ / Incomplete | ⚪ / Incomplete |
| uk_csl  | ⚪ / Incomplete | ⚪ / Incomplete | ⚪ / Incomplete | ⚪ / Incomplete |
| eu_csl  | ⚪ / Incomplete | ⚪ / Incomplete | ⚪ / Incomplete | ⚪ / Incomplete |
| un_csl  | ⚪ / Incomplete | ⚪ / Incomplete | ⚪ / Incomplete | ⚪ / Incomplete |
- **Result**: 20/20 cells ⚪ / Incomplete. Zero false greens.

## 4. Licensing & Dependency Isolation
- **RapidFuzz 3.14.6**: Verified pure MIT license (`licenses/LICENSE` in dist-info). No LGPL or copyleft.
- **Dev Dependencies**: Isolated into `requirements-dev.txt` (`pytest`, `iniconfig`, `pluggy`, `ruff`, `mypy`, `pip-licenses`, `detect-secrets`).
- **Runtime Dependencies**: `requirements.txt` contains only production runtime packages (includes `rapidfuzz==3.14.6`).
- **Legal Notices**: `THIRD_PARTY_NOTICES.md` updated with full notices for RapidFuzz, pywebview, Edge WebView2 redistribution, Inno Setup, and PyInstaller Bootloader Exception.

## 5. Pass Gate Decision
All 7 Part A.1 pass criteria are met. Proceeding directly to Part B desktop app build per `T7_DESKTOP_APP_COMPILED_v3.md`.
