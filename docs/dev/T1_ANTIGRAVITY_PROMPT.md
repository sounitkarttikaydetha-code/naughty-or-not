# T1 — Antigravity prompt: Watchman setup + project skeleton

Paste the prompt below into Antigravity, with an empty folder named `naughty-or-not` open as the workspace. Copy SPEC.md into that folder first.

---

Read SPEC.md in this workspace. It is the functional spec for a sanctions screening tool. The project name is "Naughty or not". The main UI screen title is "Sanction checK", written exactly like that. Do only task T1 now. Do not build the UI or any other module.

**T1 scope**

1. **Check the prerequisites.** Check whether Docker Desktop and Python 3.10 or later are installed. If either is missing, stop and give me step-by-step installation instructions for Windows. Do not install anything without asking me.

2. **Run Moov Watchman locally.** Read the official docs at https://moov-io.github.io/watchman/ first, and use only options documented there.
   - Create `docker-compose.yml` to run the official `moov/watchman` image on port 8084.
   - Load these lists: `us_ofac, us_csl, eu_csl, uk_csl, un_csl`.
   - Set the list refresh interval to 24 hours, using the config option named in the docs.
   - Pin a specific release tag rather than `latest`, and write the tag in the README.
   - Support `HTTPS_PROXY` / `SSL_CERT_FILE` through `.env` for the corporate network.

3. **Verify.** Call `/v2/listinfo` and report the record count, hash and timestamp for each list. Any list with 0 records is a failure. Diagnose it and report back; do not work around it.

4. **Smoke tests.** Using `/v2/search` with `minMatch=0.80`, run: Sberbank, VTB Bank, S7 Airlines / Siberia Airlines, Aeroflot, and "Jaipur International Airport Limited" (the clean control). Give me a table with the query, the top 3 hits, the score, the source list and the source ID. Then run the same queries at `minMatch=0.70` and show the difference.

5. **Project skeleton.**
   ```
   naughty-or-not/
     SPEC.md
     README.md            (setup steps for company and personal laptops)
     docker-compose.yml
     .env.example         (OPENSANCTIONS_API_KEY=, HTTPS_PROXY=, SSL_CERT_FILE=, WATCHMAN_URL=http://localhost:8084)
     .gitignore           (.env, logs/, reports/, data/, __pycache__/, .venv/)
     requirements.txt     (empty placeholder for now)
     app/                 (empty, with __init__.py)
     modules/             (empty folders: watchman/, opensanctions/, aviation/, india/)
     data/  logs/  reports/   (git-ignored)
     tests/               (acceptance test list copied from SPEC section 8)
   ```

6. **Write a small Python client** at `modules/watchman/client.py` with:
   - `health()`
   - `list_info()`
   - `search(name, type=None, min_match=0.80, **fields)`

   It should return clean Python dicts, use a timeout, and return a clear "unavailable" result if Watchman is down. It must not crash in that case. Add one test for this.

**Rules**
- Do not send any screened name to any external service.
- Do not commit `.env`, logs, reports or data.
- Do not add features beyond T1.
- Finish with a short summary: what you did, files created, test results, and any open issues or decisions I need to take.
