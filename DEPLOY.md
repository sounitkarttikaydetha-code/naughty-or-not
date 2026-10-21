# Naughty or not — Deployment & Installation Guide

## Staff Deployment (Company Laptop)

### Prerequisites & Approval
- **Corporate Policy Notice:** Install only after IT Compliance and Information Security have approved software deployment on your corporate workstation.
- **Operating System:** Windows 10 or Windows 11 (64-bit).
- **Permissions:** Standard User account. **No local administrator rights are required.**

### Option A: Windows Installer (.exe)
1. Navigate to the GitHub repository Releases page:
   `https://github.com/sounitkarttikaydetha-code/naughty-or-not/releases`
2. Download:
   - `NaughtyOrNot_Setup_v1.0.2.exe`
   - `SHA256.txt`
3. Verify the cryptographic SHA-256 integrity hash:
   ```powershell
   Get-FileHash .\NaughtyOrNot_Setup_v1.0.2.exe -Algorithm SHA256
   ```
4. Run `NaughtyOrNot_Setup_v1.0.2.exe`:
   - Installs per-user to `%LOCALAPPDATA%\Programs\NaughtyOrNot` (no admin rights required).
5. Launch from the Desktop or Start Menu shortcut.

### Option B: Zero-Install Portable Version (.zip)
1. Download `NaughtyOrNot_v1.0.2_Portable.zip` from Releases.
2. Verify SHA-256 checksum against `SHA256.txt`:
   ```powershell
   Get-FileHash .\NaughtyOrNot_v1.0.2_Portable.zip -Algorithm SHA256
   ```
3. Extract the `.zip` archive to any location (Desktop, Downloads, or a USB drive).
4. Double-click `Naughty or not.exe` to run immediately.
5. **Zero-Trace USB Mode:** To keep all audit logs, databases, and lists contained on your USB stick without leaving any files on the host computer, create an empty file named `.portable` inside the unzipped folder alongside `Naughty or not.exe`.

### Uninstallation
- To uninstall, use Windows Settings > Apps > Installed apps > "Naughty or not" > Uninstall.
- The uninstaller will ask whether to keep your local screening audit logs and generated PDF reports in `%LOCALAPPDATA%\NaughtyOrNot`. Choosing "Yes" preserves audit compliance records.

---

## Developer Setup (Cross-Platform / Development)

*Note: The native Windows `.exe` installer is Windows-only, but the screening engine and Streamlit web interface run cross-platform on Windows, macOS, and Linux.*

### Steps
1. **Clone Repository:**
   ```bash
   git clone git@github.com:<org>/naughty-or-not.git
   cd naughty-or-not
   ```
2. **Create and Activate Virtual Environment:**
   ```bash
   python -m venv .venv
   # Windows (PowerShell):
   .venv\Scripts\Activate.ps1
   # Linux / macOS:
   source .venv/bin/activate
   ```
3. **Install Dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt -r requirements-dev.txt
   ```
4. **Initialize Bundled & Downloaded Sanctions Data:**
   ```bash
   python scripts/init_data.py
   ```
5. **Run Test Suite:**
   ```bash
   pytest
   ```
6. **Launch Application:**
   ```bash
   streamlit run app.py
   # Or via wrapper:
   python app/main.py
   ```
