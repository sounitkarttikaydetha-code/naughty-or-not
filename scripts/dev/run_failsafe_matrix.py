"""
Fail-Safe Matrix Runner (T8-11 Step 3):
Tests all 4 failure types (missing file, empty file, corrupt file, schema mismatch)
across all 5 sanctions lists (us_ofac, us_csl, uk_csl, eu_csl, un_csl) = 20 cases.
Confirms engine fails safely without crashes and reports source error.
"""

import sys
import tempfile
from pathlib import Path
sys.path.insert(0, ".")

from modules.engine.engine import PythonEngine
from modules.engine.loader import (
    load_ofac_sdn,
    load_us_csl,
    load_uk_csl,
    load_eu_csl,
    load_un_csl,
)

LISTS = ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]
FAILURES = ["missing_file", "empty_file", "corrupt_file", "schema_mismatch"]

LOADERS = {
    "us_ofac": load_ofac_sdn,
    "us_csl": load_us_csl,
    "uk_csl": load_uk_csl,
    "eu_csl": load_eu_csl,
    "un_csl": load_un_csl,
}

EXTENSIONS = {
    "us_ofac": "csv",
    "us_csl": "csv",
    "uk_csl": "csv",
    "eu_csl": "xml",
    "un_csl": "xml",
}

def run_failsafe_matrix():
    print(f"Running Fail-Safe Matrix: {len(LISTS)} lists x {len(FAILURES)} failure types = 20 cases...")
    passed = 0
    total = len(LISTS) * len(FAILURES)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        for src in LISTS:
            loader = LOADERS[src]
            ext = EXTENSIONS[src]

            for fail_type in FAILURES:
                test_file = tmp / f"{src}_{fail_type}.{ext}"

                if fail_type == "missing_file":
                    # File does not exist
                    if test_file.exists():
                        test_file.unlink()
                elif fail_type == "empty_file":
                    test_file.write_text("", encoding="utf-8")
                elif fail_type == "corrupt_file":
                    test_file.write_bytes(b"\x00\xff\xfe\x01\x02\x03\x04GARBAGE_BYTES_CORRUPT")
                elif fail_type == "schema_mismatch":
                    if ext == "csv":
                        test_file.write_text("wrong_col_1,wrong_col_2,wrong_col_3\nval1,val2,val3\n", encoding="utf-8")
                    else:
                        test_file.write_text("<wrong_root><wrong_element>data</wrong_element></wrong_root>", encoding="utf-8")

                # Test loader directly
                recs, err = loader(test_file)
                # Success criteria: recs is empty, err is non-empty, no unhandled exception
                if len(recs) == 0 and err is not None:
                    passed += 1
                    print(f"  [PASS] {src:8s} | {fail_type:15s} -> Handled safely: {err[:50]}")
                else:
                    print(f"  [FAIL] {src:8s} | {fail_type:15s} -> Unexpected result: recs={len(recs)}, err={err}")

    print(f"\nFail-Safe Matrix Results: {passed}/{total} passed (100% target)")
    return passed == total

if __name__ == "__main__":
    success = run_failsafe_matrix()
    if not success:
        sys.exit(1)
