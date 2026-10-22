# Naughty or not (Sanction checK)

**Naughty or not** is an automated sanctions and compliance screening tool designed for Legal and Compliance. It replaces manual cross-checks across multiple regulatory websites with a unified screening interface ("Sanction checK").

---

## Quick Start for Windows Users (No Python / Docker Required)

Download pre-built standalone packages directly from **[GitHub Releases](https://github.com/sounitkarttikaydetha-code/naughty-or-not/releases)**:
- **Portable Version (NaughtyOrNot_v1.0.2_Portable.zip)**: Download, unzip, and double-click Naughty or not.exe. Runs anywhere (including USB drives) without installation. Add an empty .portable file to enable zero-trace local data storage.
- **Installer Version (NaughtyOrNot_Setup_v1.0.2.exe)**: Standard per-user setup wizard with Desktop and Start Menu shortcuts. No administrative privileges required.

See [DEPLOY.md](DEPLOY.md) for full deployment instructions and cryptographic checksum verification.

---

## About

Internal sanctions screening aid prepared under the Sanctions Compliance Policy. Test version. Not for transaction decisions. Uses only official public sources. OpenSanctions data CC BY-NC 4.0 — commercial use requires a licence.

---

## Pinned Components & Versions

- **Moov Watchman Image:** `moov/watchman:v1.2.2` (Pinned official Docker release tag)
- **Watchman API Port:** `8084`
- **Default Lists Loaded:** `us_ofac`, `us_csl`, `eu_csl`, `uk_csl`, `un_csl`
- **Watchman Refresh Interval:** `24h` (`DATA_REFRESH_INTERVAL=24h`)
- **Python Version Requirement:** `Python 3.12` (Pinned for project virtual environment; tested against Python 3.12.x)

---

## Setup Instructions

### A. Personal Laptop (Development / Testing)

1. **Prerequisites:**
   - Install **Docker Desktop** (WSL 2 backend enabled).
   - Install **Python 3.10+** (ensure `python` is added to your PATH).

2. **Clone & Configure:**
   - Clone the repository:
     ```bash
     git clone <repo-url>
     cd "Naughty or not"
     ```
   - Copy `.env.example` to `.env`:
     ```bash
     cp .env.example .env
     ```
   - On a personal laptop without proxy, `.env` default values (`WATCHMAN_URL=http://localhost:8084`) work out of the box.

3. **Start Watchman:**
   ```bash
   docker compose up -d
   ```
   Watchman will download and index the configured lists (`us_ofac, us_csl, eu_csl, uk_csl, un_csl`).

4. **Verify Watchman Service:**
   - Health check (use `curl.exe` in Windows PowerShell to invoke native binary instead of PowerShell alias):
     ```bash
     curl.exe http://localhost:8084/ping
     ```
   - List info check:
     ```bash
     curl.exe http://localhost:8084/v2/listinfo
     ```

5. **Python Environment Setup:**
   ```bash
   py -3.12 -m venv .venv
   # Alternatively: python -m venv .venv

   # Windows PowerShell (if script execution is restricted):
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .\.venv\Scripts\Activate.ps1

   # Linux/macOS:
   source .venv/bin/activate

   pip install -r requirements.txt
   ```


6. **Initialize Local Data & Raw Index:**
   ```bash
   python scripts/init_data.py
   ```
   This downloads/caches the official aviation and India registers and compiles the local SQLite FTS5 search index.


---

### B. Company Laptop (Corporate Network / Real Screening)

1. **IT Approvals & Prerequisites:**
   - Ensure IT approval for **Docker Desktop** and **Python 3.10+**.
   - Ensure Docker Desktop is running.

2. **Configure Corporate Proxy & SSL Certificates:**
   - Copy `.env.example` to `.env`:
     ```bash
     cp .env.example .env
     ```
   - Edit `.env` to populate corporate proxy and SSL certificates if your corporate gateway performs TLS inspection:
     ```env
     HTTPS_PROXY=http://proxy.corporate.internal:8080
     SSL_CERT_FILE=/path/to/corporate-ca-bundle.crt
     OPENSANCTIONS_API_KEY=<optional-api-key>
     WATCHMAN_URL=http://localhost:8084
     ```
   - `docker-compose.yml` automatically passes `HTTPS_PROXY`, `HTTP_PROXY`, and `SSL_CERT_FILE` from `.env` to the container so Watchman can download list updates through the corporate firewall.

3. **Start Watchman:**
   ```bash
   docker compose up -d
   ```

4. **Verify List Population:**
   Ensure each sanctions list in `/v2/listinfo` has populated records (> 0).

5. **Data Protection & Compliance Rules:**
   - Real counterparty names and search histories must **never** leave the machine.
   - All `.env`, `data/`, `logs/`, and `reports/` directories are git-ignored. Never force-commit these artifacts.

---

## Project Structure

```
naughty-or-not/
  SPEC.md               # Functional specification
  README.md             # Setup guide and pinned tags
  docker-compose.yml    # Watchman container definition
  .env.example          # Template for environment variables
  .gitignore            # Git exclusion rules
  requirements.txt      # Python dependencies
  app/                  # Application code (UI and runner)
  modules/              # Modular integration clients
    watchman/           # Watchman API client & tests
    opensanctions/      # OpenSanctions API integration
    aviation/           # BIS aircraft, EU safety list, FAA IASA
    india/              # MHA / UAPA domestic lists
  data/                 # Local data storage (git-ignored)
  logs/                 # Screening logs (git-ignored)
  reports/              # Generated PDF/Excel reports (git-ignored)
  tests/                # Acceptance & unit tests
```

---

## How to Start / Stop

### Starting the Application
Double-click the **Naughty or not** desktop shortcut, or run in terminal:
```cmd
run_app.bat
```
This batch script automatically:
1. Checks if Docker Desktop is running (starts it if needed).
2. Runs `docker compose up -d` to launch the Watchman container.
3. Polls Watchman health (`http://127.0.0.1:8084/ping`) until ready (timeouts gracefully after 3 minutes if service fails).
4. Launches the Streamlit UI at `http://127.0.0.1:8501` and opens your default browser.

### Stopping the Application
Run in terminal:
```cmd
stop_app.bat
```
This stops the running Streamlit processes and stops Docker containers (`docker compose stop`).

---

## Compliance & Governance

- **Scope:** Name matching, aviation safety registers, and open-source intelligence aggregation only.
- **Legal Advisory:** Not a legal determination and does not perform ownership/control (e.g., 50% rule) calculations.
- **Data Protection:** Counterparty names and search logs remain strictly on the local workstation and are never transmitted externally.
- **Licensing:** OpenSanctions data is licensed under CC BY-NC 4.0 (commercial use requires an independent license). See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [LICENSE](LICENSE) for full details.


<!-- Easter Egg: Keep scrolling -->
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<p align="center"><b>W</b></p>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<p align="center"><b>H</b></p>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<p align="center"><b>Y</b></p>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<p align="center"><b>A</b></p>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<p align="center"><b>R</b></p>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<p align="center"><b>E</b></p>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<p align="center"><b>Y</b></p>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<p align="center"><b>O</b></p>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<p align="center"><b>U</b></p>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<p align="center"><b>S</b></p>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<p align="center"><b>T</b></p>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<p align="center"><b>I</b></p>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<p align="center"><b>L</b></p>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<p align="center"><b>L</b></p>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<p align="center"><b>S</b></p>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<p align="center"><b>C</b></p>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<p align="center"><b>R</b></p>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<p align="center"><b>O</b></p>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<p align="center"><b>L</b></p>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<p align="center"><b>L</b></p>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<p align="center"><b>I</b></p>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<p align="center"><b>N</b></p>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<p align="center"><b>G</b></p>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
> You actually scrolled all the way down here? Gotcha. Now smile for the camera. 📸. The developer got bored, you got curious and now we're even. Now go screen something. 🕵️ — Naughty or not, a brainchild of Sounit Karttikay (and the blood, sweat and tokens of Antigravity and Opus, no AIs were sanctioned in the making of this tool)
