# Acceptance Tests (Initial)

Copied from `SPEC.md` Section 8:

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
