# Feasibility Report: Desktop Executable (Prompt T7 Step 0)

## 1. Running Watchman without Docker
Moov does not publish official Windows releases. Watchman (Go) compiles cleanly for Windows (`GOOS=windows go build`), provided `CGO_ENABLED=0` (disabling `libpostal` address parsing, preserving core name search). Cross-compilation via GitHub Actions produces a static `watchman.exe` (~45 MB).
- **Pro:** Exactly matches the Linux Docker screening API (`/v2/search`, `/v2/listinfo`).
- **Con:** Needs a background child process, port binding, and memory overhead (~350 MB RAM).

## 2. Fallback Engine (Native Python / SQLite FTS5)
A built-in native screening engine using our SQLite FTS5 index (`data/raw_index.db`) and `modules.screening.tiering` (token sort, edit distance, threshold filtering).
- **Feasibility:** High. 1-2 days effort. Eliminates port collisions, child process crashes, and daemon lag.
- **Recommendation:** Implement Native Python Fallback Engine as the primary desktop runner; package compiled `watchman.exe` as optional external daemon.

## 3. Window Technology Comparison
- **`pywebview` wrapping local Streamlit (Recommended):** Reuses 100% of tested Streamlit UI and session state. Uses native Windows Edge WebView2 (pre-installed on Win 10/11). Minimal footprint (~70 MB), zero rewrite risk.
- **PySide6 / Qt:** Requires complete UI rewrite (~2 weeks), high risk of UI parity bugs.
- **Tauri / Electron:** Requires frontend port to React/HTML; Electron bloats bundle by ~150 MB.

## 4. Packaging & Licences
- **Bundler:** PyInstaller (onedir mode) bundled into a single self-extracting **Inno Setup** installer.
- **Licences:** All 46 Python packages audited; 44 Permissive (MIT/BSD/Apache-2.0), 1 MPL-2.0 (`certifi`), 0 GPL/AGPL in runtime.
- **Asset Compliance:** Permissive DejaVu/Noto fonts replace GPL `DarkGarden`. All font and license assets are clean.

## 5. Corporate Laptop & User Account Constraints
- **Non-Admin Execution:** Installs strictly into `%LOCALAPPDATA%\Programs\NaughtyOrNot\`. Runtime data, logs, and reports write to `%LOCALAPPDATA%\NaughtyOrNot\`. Zero admin/UAC required.
- **Windows Defender SmartScreen:** Unsigned binaries will show "Unknown Publisher". Mitigation: Provide SHA-256 hashes in release notes and guide IT for InTune/SCCM deployment or cert signing.
- **Corporate Proxy & Root CA:** Natively supported via Python `truststore` (using Windows Schannel / CertStore) + `HTTP_PROXY` / `HTTPS_PROXY` in app settings.

## 6. Docker & Hardcoded `localhost:8084` Audit
- `modules/watchman/client.py`: Configurable via `WATCHMAN_URL` env var / config setting.
- `docker-compose.yml`, `run_app.bat`, `stop_app.bat`: Docker-specific launcher scripts to be supplemented with desktop launchers (`run_desktop.bat`, `NaughtyOrNot.exe`).
- All file paths in `modules/reporting` and `modules/aviation` already support `%LOCALAPPDATA%` redirection.
