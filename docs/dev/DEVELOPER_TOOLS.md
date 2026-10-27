# Developer Tools & Build Infrastructure — Clearance Check v1.1.0

The following tools and libraries are utilized during the engineering, test automation, and release build lifecycle of Clearance Check.

> [!NOTE]
> None of the developer tools listed in this document are bundled, distributed, or executed in end-user installation packages. They are strictly confined to developer workstations and CI/CD pipelines.

---

## 1. Test Automation Frameworks

### pytest
- **Version:** >= 8.0
- **License:** MIT License
- **Purpose:** Primary unit, regression, and mutation test suite execution (`pytest tests/`).

### anyio
- **Version:** >= 4.0
- **License:** MIT License
- **Purpose:** Asynchronous runtime test fixture support.

### Playwright
- **Version:** >= 1.40
- **License:** Apache License 2.0
- **Purpose:** Headless browser automation for end-to-end visual UI regression tests and screen layout validation (`reviews/screens/`).

---

## 2. Code Quality & Formatting

### black
- **License:** MIT License
- **Purpose:** Deterministic Python code formatting.

### flake8
- **License:** MIT License
- **Purpose:** PEP 8 compliance and static syntax linting.

---

## 3. Packaging & Distribution Infrastructure

### Inno Setup
- **Version:** 6.x
- **License:** Inno Setup License (Jordan Russell)
- **Purpose:** Compiles Windows per-user standalone desktop installer (`installer/setup.iss`).

### PyInstaller
- **Version:** 6.x
- **License:** GPLv2 with PyInstaller Bootloader Exception
- **Purpose:** Bundles Python runtime and dependencies into a self-contained executable folder (`build.spec`).

---

## 4. Test Fixtures & Validation Sets

- **Golden Regression Suite:** `tests/golden_set.json` (70 verified historical screening expectations).
- **Phonetic Evaluation Set:** `reviews/phonetic_validation_results.json` (500 leave-one-out and 300 noise controls).
- **Engine Canary Set:** `tests/fixtures/canary/canary_records.yaml` (20 matching engine invariant test cases).
