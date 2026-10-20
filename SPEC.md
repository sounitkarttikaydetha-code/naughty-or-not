# Naughty or not — Functional Specification (v0.1, draft)

**Project / app name:** Naughty or not
**Main screen title (shown in UI):** Sanction checK
**Owner:** Sounit Karttikay, Legal, JIAL
**Status:** Test version, single user. May later be rolled out across the airport.

---

## 1. Purpose

A single screen where the user enters a name (or an aircraft or vessel identifier) and gets one result for each source. It covers sanctions lists (US, UK, EU, UN, India) and aviation-specific checks. It replaces separate manual searches on each regulator's website, as required by the Sanctions Compliance Policy.

The tool **flags** potential matches only. Verifying a match and escalating it stay with the user, as set out in the Policy.

## 2. Environments

| Item | Company laptop | Personal laptop |
|---|---|---|
| Purpose | Real screening | Development and testing |
| Data | Real counterparty names | Publicly known test names only |
| Code | Same repository | Same repository |
| Config | `.env` file kept on the machine (never committed) | `.env` file kept on the machine (never committed) |
| Logs and reports | Stored only on that machine (`/logs`, `/reports`) | Stored only on that machine |

- Both machines need Docker Desktop and Python 3.10 or later. The company laptop needs IT approval for Docker.
- No screened names, logs or reports are committed to Git. `.gitignore` must exclude `.env`, `/logs`, `/reports` and `/data`.
- The company laptop may need proxy or SSL settings (`HTTPS_PROXY`, `SSL_CERT_FILE`) set in `.env`.

## 3. Architecture

```
[ Sanction checK UI (Streamlit, Python) ]
        |                |                    |                     |
        v                v                    v                     v
 Moov Watchman     OpenSanctions API     Aviation module       India module
 (Docker, local)   (optional, uses       (local tables:        (local tables:
 OFAC SDN/Non-SDN,  credits)              BIS aircraft list,    MHA / UAPA lists)
 US CSL, EU, UK, UN                       EU Air Safety List,
                                          FAA IASA)
        \_______________ results + list versions _______________/
                                 |
                      Log (append-only) + Report (PDF/Excel)
```

- **Watchman** is the main engine. It runs locally on `localhost:8084` and loads `us_ofac, us_csl, eu_csl, uk_csl, un_csl`.
- **OpenSanctions** is a second-opinion check through the hosted API. It is called only when the user ticks the checkbox. The API key goes in `.env` as `OPENSANCTIONS_API_KEY`.
- **Aviation and India modules** read local tables built from official publications. Some of these are published only as PDFs and need to be parsed.

## 4. Main screen: "Sanction checK"

### 4.1 Inputs

**Search type** (selector): Person / Organisation / Airline / Aircraft / Vessel

| Search type | Fields (only the name is mandatory, except Aircraft and Vessel) |
|---|---|
| Person | Full name\*, date of birth or year of birth, nationality, passport / ID number |
| Organisation | Legal name\*, country, registration / tax number |
| Airline | Airline name\*, ICAO / IATA code, country of AOC |
| Aircraft | Registration (tail no.)\* **or** MSN\*, operator, aircraft type |
| Vessel | Vessel name or IMO number\*, flag |

**Source options:**
- ☑ US / UK / EU / UN sanctions lists (Watchman). Always on.
- ☑ India: MHA / UAPA lists. On by default.
- ☑ Aviation checks. On by default for Airline and Aircraft searches; hidden for other types.
- ☐ **OpenSanctions (uses credits)**. **Off by default.** This label must be shown exactly.
- Match threshold slider. Default 0.80, range 0.60–1.00, with the help text: "Lower = more spelling variants caught, more false positives".

### 4.2 Results

**Overall banner** (one of):
- 🔴 **Potential sanctions match**: verify on the official source and escalate under the Sanctions Compliance Policy before proceeding.
- ⚠️ **No sanctions match, but aviation safety flag**: see the Aviation safety section.
- ✅ **No match** on any source checked at the selected threshold.
- ⚪ **Incomplete**: one or more sources could not be checked. Do not rely on this result alone.

**Section A — Sanctions** (one row per source):

| Source | Result | Top match | Score | List version / date | Verify link |
|---|---|---|---|---|---|
| OFAC SDN / Non-SDN | ✅ / 🔴 / ⚪ | | | | |
| US CSL (incl. BIS denial orders) | | | | | |
| UK Sanctions List | | | | | |
| EU Consolidated List | | | | | |
| UN SC Consolidated List | | | | | |
| India (MHA / UAPA) | | | | | |
| OpenSanctions | shows "Not run" when unticked | | | | |

Each row can be expanded to show all matches: listed name, matched alias, type, programme or regime, countries, date of birth, listing date, reference ID and remarks.

**Section B — Aviation** (Airline and Aircraft searches only). This section is **always shown separately from sanctions**:

| Check | Result |
|---|---|
| BIS aircraft list (potential EAR violation): matched on current registration, **previous** registration and MSN | 🔴 / ✅ |
| EU Air Safety List: Annex A (banned) / Annex B (restricted) | ⚠️ / ✅ |
| FAA IASA: country of the AOC is in Category 2 | ⚠️ / ✅ |

The BIS aircraft list is shown as 🔴 because it is an export-control restriction. EU and FAA hits are shown as ⚠️ **safety flags, not sanctions**, with that wording visible on screen.

**Footer disclaimer** (always shown): "Screening aid only. A result here is not a legal determination. Potential matches must be verified against the official source and escalated under the Sanctions Compliance Policy. Ownership/control (e.g. the US 50% rule) is not assessed."

### 4.3 Outputs

- **Download report:** PDF and Excel, one per search. The report includes the inputs, the timestamp, the user, the sources checked, the version or date of each list, all results, the threshold, whether OpenSanctions was used, and the disclaimer.
- **Log:** an append-only local log (SQLite or CSV) with one row per source per search. Columns: timestamp, Windows user, machine name, search type, inputs, threshold, source, result, top match, score, list version, OpenSanctions used (Y/N), report file name. The log is retained for 10 years under the Policy.

## 5. Data refresh (automatic, daily)

| Source | Refresh method |
|---|---|
| Watchman lists | Watchman's built-in refresh interval, set to 24 hours. Show the version and date of each list from `/v2/listinfo` |
| OpenSanctions | Live API, no refresh needed |
| BIS aircraft list | Daily check of the BIS page. If the publication changes, download it, parse it and keep the previous version |
| EU Air Safety List | Daily check. If it changes, re-parse it |
| FAA IASA | Daily check. If it changes, re-parse it |
| India (MHA) | Daily check. If it changes, re-parse it |

**Failure rule:** if any refresh or parse fails, the app still runs on the last good version but shows ⚪ with the date of that version and the error message. A source must never fail silently.

## 6. OpenSanctions credits

- The API is called only when the checkbox is ticked. One search counts as one call.
- The screen shows a "Credits used (this session / total logged)" counter, calculated from the log.
- If no API key is set, the checkbox is disabled with the tooltip "Add OPENSANCTIONS_API_KEY to .env".
- **Bulk data licensing notice**: If bulk data loading is ever enabled (via `OPENSANCTIONS_BULK_ENABLED=true`), the UI must show: `"OpenSanctions data is licensed under CC BY-NC 4.0; commercial use requires a licence from opensanctions.org"` on the screen where bulk data is configured or used. By default, bulk data loading is strictly disabled in code.

## 7. Out of scope (phase 1)

- Batch screening (phase 2)
- A review workflow for false positives or escalations (the tool only flags)
- Ownership / 50% rule analysis
- Passenger-list screening
- Multi-user hosting / server deployment

## 8. Acceptance tests (initial)

| # | Input | Expected |
|---|---|---|
| 1 | Organisation: Sberbank | 🔴 on OFAC, EU, UK |
| 2 | Organisation: VTB Bank | 🔴 on OFAC, EU, UK |
| 3 | Airline: S7 / Siberia Airlines | 🔴 (UK designation, US CSL denial order); ⚠️ EU Air Safety List |
| 4 | Airline: Aeroflot | 🔴 US CSL denial order; ⚠️ EU Air Safety List |
| 5 | Aircraft: a registration taken from the current BIS list, searched by its **previous** registration | 🔴 BIS aircraft list |
| 6 | Organisation: Jaipur International Airport Limited | ✅ on all sources |
| 7 | Any search with Docker stopped | ⚪ Incomplete banner; app does not crash |
| 8 | OpenSanctions unticked | "Not run"; no API call made (check the log) |

## 9. Build tasks

| # | Task | Who |
|---|---|---|
| T1 | Set up Docker and Watchman, plus the project skeleton | Antigravity |
| T2 | Connect the OpenSanctions API | Antigravity |
| T3 | Aviation module: parse the BIS and EU Air Safety List PDFs, add the FAA IASA table | Antigravity |
| T4 | India module (MHA / UAPA) | Antigravity |
| T5 | "Sanction checK" UI, report and log | Antigravity |
| T6 | Run the acceptance tests and agree the threshold | Antigravity runs; Sounit reviews |
| T7 | Compliance note and one-page SOP | Copilot |
