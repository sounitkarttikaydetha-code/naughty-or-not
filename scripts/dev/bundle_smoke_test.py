"""
Desktop Bundle Smoke Test
Verifies the structural integrity and import viability of the PyInstaller build output.
"""

import sys
from pathlib import Path


def smoke_test_bundle(bundle_dir: Path) -> bool:
    print(f"Running bundle smoke test on: {bundle_dir}")
    if not bundle_dir.is_dir():
        print(f"[FAIL] Bundle directory does not exist: {bundle_dir}")
        return False

    exe_path = bundle_dir / "Naughty or not.exe"
    if not exe_path.is_file():
        print(f"[FAIL] Main executable not found: {exe_path}")
        return False

    internal_dir = bundle_dir / "_internal"
    if not internal_dir.is_dir():
        print(f"[FAIL] _internal directory not found: {internal_dir}")
        return False

    # Check data files
    seed_raw = internal_dir / "data" / "raw"
    if not seed_raw.is_dir() or not any(seed_raw.iterdir()):
        print(f"[FAIL] Bundled seed data missing in: {seed_raw}")
        return False

    # Check app and modules
    app_py = internal_dir / "app.py"
    if not app_py.is_file():
        print(f"[FAIL] app.py missing from _internal: {app_py}")
        return False

    # Test that Python runtime in the environment can import all modules
    # by adding _internal to sys.path
    sys.path.insert(0, str(internal_dir))
    try:
        import modules
        from modules.common.paths import get_app_data_dir
        from modules.reporting.generator import generate_reports
        from modules.reporting.logger import log_search, log_raw_search, log_manual_check
        from modules.screening.tiering import screen_query_all_lists
        print("  - Core modules imported successfully.")
    except Exception as e:
        print(f"[FAIL] Error importing core modules: {e}")
        return False

    try:
        import reportlab
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate
        import openpyxl
        import pypdf
        import rapidfuzz
        print("  - Third-party report/engine dependencies imported successfully.")
    except Exception as e:
        print(f"[FAIL] Error importing third-party dependencies: {e}")
        return False

    print("[PASS] BUNDLE SMOKE TEST PASSED: Executable, seed data, and modules verified.")
    return True


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("dist/NaughtyOrNot")
    if not smoke_test_bundle(target):
        sys.exit(1)
