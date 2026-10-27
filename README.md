# Naughty or not (Sanction checK)

**Naughty or not** is a standalone automated sanctions, export controls, and regulatory compliance screening tool designed for Legal and Compliance teams. It replaces manual cross-checks across multiple regulatory websites with a unified, high-performance screening interface ("Sanction checK").

Runs 100% locally and offline on Windows with an embedded in-process screening engine. **Zero background services, no Docker containers, and no administrative privileges required.**

---

## Quick Start for Windows Users (No Installation Required)

Download pre-built standalone packages directly from **[GitHub Releases](https://github.com/sounitkarttikaydetha-code/naughty-or-not/releases)**:

### Option A: Portable Version (Recommended for USB & Quick Use)
**File:** `NaughtyOrNot_v1.0.4_Portable.zip`

1. **Download:** Download `NaughtyOrNot_v1.0.4_Portable.zip` from the latest release.
2. **Extract:** Right-click the downloaded `.zip` file, select **Extract All...**, and choose any destination folder (e.g., your Desktop, Documents, or a USB flash drive).
3. **Launch:** Open the extracted `NaughtyOrNot` folder and double-click:
   ```text
   Naughty or not.exe
   ```
4. **Done:** The application opens in a dedicated, high-DPI desktop window. All audit logs and reports remain isolated within your local environment.

> **Tip (Zero-Trace / True Portable Mode):** To keep all screening logs and reports strictly inside the extracted folder (e.g., on a thumb drive without writing to your PC profile), create an empty text file named `.portable` inside the application folder.

### Option B: Windows Installer Setup
**File:** `NaughtyOrNot_Setup_v1.0.4.exe`

1. Download and run `NaughtyOrNot_Setup_v1.0.4.exe`.
2. Follow the setup wizard (installs to your user profile directory without requiring administrator rights).
3. Launch anytime via your Start Menu or Desktop shortcut.

See [DEPLOY.md](DEPLOY.md) for full deployment instructions and cryptographic SHA-256 verification.

---

## What It Screens

- **Official Sanctions Lists:**
  - **US OFAC:** Specially Designated Nationals (SDN) and Consolidated Non-SDN lists.
  - **US CSL:** Consolidated Screening List (BIS Entity List, Unverified List, MEU List).
  - **UK OFSI / CSL:** Consolidated Sanctions List.
  - **EU CSL:** European Union Financial Sanctions Database.
  - **UN Security Council:** Consolidated Sanctions List.
- **Aviation Safety & Export Restrictions:**
  - **US BIS Aeroflot & Russian/Belarusian Aircraft:** Grounded tail numbers and serial numbers (MSN).
  - **EU Air Safety List:** Annex A (full operating ban) and Annex B (operational restrictions).
  - **FAA IASA:** International Aviation Safety Assessment Category 2 non-compliant jurisdictions.
- **National Security & Domestic Designations:**
  - **India MHA UAPA:** First Schedule (Terrorist Organisations), Fourth Schedule (Individuals), and Unlawful Associations.
- **Jurisdictional Anti-Money Laundering (AML) Risk:**
  - **FATF Jurisdictions:** High-Risk Jurisdictions subject to a Call for Action (Black List) and Jurisdictions under Increased Monitoring (Grey List).
- **Optional Enhanced Screening:**
  - **OpenSanctions Hosted API:** Optional commercial API integration with a strict, verifiable credit-usage limit.

---

## Key Features

- **Embedded Python Screening Engine:** Drop-in, in-process scoring engine with sub-second retrieval (<0.8s) powered by tokenized candidate filtering, Double Metaphone phonetic expansion, and Jaro-Winkler fuzzy matching.
- **Offline & Private:** All screening calculations happen on your CPU. Counterparty names, queries, and results never leave your computer.
- **Dual Export Formats:** Generate formal audit-ready PDF reports and structured Excel (.xlsx) workbooks with a single click.
- **Integrated Audit Trail:** Tamper-evident SQLite database logging timestamps, search types, overall status tiers, candidate counts, and user metadata.
- **Dedicated Manual Check Workflow:** 14 structured regulatory cards with direct links to official publisher databases.
- **Per-Monitor High-DPI Display:** High-contrast WCAG 2.1 AA accessible status chips and adaptive multi-resolution window scaling.

---

## Running from Source (Developers)

If you wish to run or develop from the Python source code:

1. **Prerequisites:**
   - Python 3.12 (64-bit) installed and on your PATH.
   - Microsoft Edge WebView2 Runtime (pre-installed on Windows 10/11).

2. **Clone & Virtual Environment:**
   ```powershell
   git clone https://github.com/sounitkarttikaydetha-code/naughty-or-not.git
   cd "naughty-or-not"

   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

3. **Initialize Offline Data & Full-Text Index:**
   ```powershell
   python scripts/init_data.py
   ```

4. **Run Application:**
   ```powershell
   python desktop_launcher.py
   ```

5. **Run Test Suite:**
   ```powershell
   pytest -q
   ```

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
