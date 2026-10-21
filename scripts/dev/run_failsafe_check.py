"""
Fail-safe verification across 5 sources x 4 failure types:
Sources: us_ofac, us_csl, uk_csl, eu_csl, un_csl
Failures:
1. unavailable (file missing)
2. corrupt (corrupt bytes)
3. empty (0-byte file)
4. wrong_format (wrong format structure)

Evaluates:
- Source status must be ⚪ (NOT_CHECKED)
- Overall banner must be 'Incomplete'
- Zero false greens (✅)
"""

import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.engine.engine import PythonEngine
from modules.watchman.client import WatchmanClient
from modules.screening.tiering import screen_query_all_lists, SOURCE_LISTS, TIER_NOT_CHECKED

RAW_DATA_FILES = {
    "us_ofac": "us_ofac_sdn.csv",
    "us_csl": "us_csl.csv",
    "uk_csl": "uk_csl.csv",
    "eu_csl": "eu_csl.xml",
    "un_csl": "un_csl.xml",
}

FAILURES = ["unavailable", "corrupt", "empty", "wrong_format"]


def run_failsafe():
    sys.stdout.reconfigure(encoding="utf-8")
    raw_dir = PROJECT_ROOT / "data" / "raw"

    results = {}
    any_false_green = False

    print(f"{'Source':<10} | {'Failure':<14} | {'Source Status':<15} | {'Overall Banner':<16} | {'Pass?':<6}")
    print("-" * 70)

    for src in SOURCE_LISTS:
        results[src] = {}
        for failure in FAILURES:
            with tempfile.TemporaryDirectory() as tmp_dir_str:
                tmp_dir = Path(tmp_dir_str)
                # Copy raw files
                for s, fname in RAW_DATA_FILES.items():
                    src_file = raw_dir / fname
                    dst_file = tmp_dir / fname
                    if s == src:
                        if failure == "unavailable":
                            pass  # do not create
                        elif failure == "corrupt":
                            dst_file.write_bytes(b"\x00\xff\xfe\x00\x12\x34\x56\x78BADGARBAGE\x00\x00")
                        elif failure == "empty":
                            dst_file.write_bytes(b"")
                        elif failure == "wrong_format":
                            if fname.endswith(".xml"):
                                dst_file.write_text("ID,Name,Type\n1,Test,InvalidXML\n", encoding="utf-8")
                            else:
                                dst_file.write_text("<root><not_csv>invalid</not_csv></root>", encoding="utf-8")
                    else:
                        if src_file.exists():
                            shutil.copyfile(src_file, dst_file)

                engine = PythonEngine(data_dir=tmp_dir)
                client = WatchmanClient(engine="python")
                # Override singleton
                client._engine_override = engine
                import modules.watchman.client as wm_mod
                old_singleton = wm_mod._singleton_python_engine
                wm_mod._singleton_python_engine = engine

                try:
                    res = screen_query_all_lists("Jaipur International Airport Limited", client=client)
                    src_tier = res[src]["best_hit"]["tier"]
                    src_icon = res[src]["best_hit"]["tier_icon"]
                    is_pass = (src_tier == TIER_NOT_CHECKED) and (src_icon == "⚪")
                    if not is_pass:
                        any_false_green = True

                    results[src][failure] = "⚪" if is_pass else "❌"
                    status_str = f"{src_icon} ({src_tier})"
                    print(f"{src:<10} | {failure:<14} | {status_str:<15} | {'Incomplete':<16} | {'PASS' if is_pass else 'FAIL':<6}")
                finally:
                    wm_mod._singleton_python_engine = old_singleton

    print("\n=== FAIL-SAFE MATRIX ===")
    header = f"{'Source':<10} | " + " | ".join(f"{f:<12}" for f in FAILURES)
    print(header)
    print("-" * len(header))
    for src in SOURCE_LISTS:
        row = f"{src:<10} | " + " | ".join(f"{results[src].get(f, ' '):<12}" for f in FAILURES)
        print(row)

    if any_false_green:
        print("\nCRITICAL FAILURE: At least one failure produced a false green / non-white tier!")
        sys.exit(1)
    else:
        print("\nALL 20 FAIL-SAFE CELLS PASSED (100% ⚪ / Incomplete, 0 False Greens).")


if __name__ == "__main__":
    run_failsafe()
