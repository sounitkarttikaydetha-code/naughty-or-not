# Naughty or not — Deployment & Installation Guide

## Staff Deployment (Company Laptop)

### Prerequisites & Approval
- **Corporate Policy Notice:** Install only after IT Compliance and Information Security have approved software deployment on your corporate workstation.
- **Operating System:** Windows 10 or Windows 11 (64-bit).
- **Permissions:** Standard User account. **No local administrator rights are required.**

### Installation Steps
1. Navigate to the private GitHub repository Releases page:
   `https://github.com/<org>/naughty-or-not/releases/tag/v1.0.1`
2. Download both files to your Downloads folder:
   - `NaughtyOrNot_Setup_v1.0.1.exe`
   - `SHA256.txt`
3. Verify the cryptographic SHA-256 integrity hash:
   - Open PowerShell and run:
     ```powershell
     Get-FileHash .\NaughtyOrNot_Setup_v1.0.1.exe -Algorithm SHA256
     ```
   - Compare the output hash against the hash listed in `SHA256.txt`. The hashes must match identically.
4. Run `NaughtyOrNot_Setup_v1.0.1.exe`:
   - The installer automatically installs per-user to:
     `%LOCALAPPDATA%\Programs\NaughtyOrNot`
   - No UAC administrator prompt will appear.
5. On completion, launch "Naughty or not" from the Desktop shortcut or Start Menu.
6. The first-run initialization will prepare the bundled lists and text search index.

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
