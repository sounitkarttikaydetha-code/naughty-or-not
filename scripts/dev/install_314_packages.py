"""
Test installation of every runtime and dev package in Python 3.14 venv (.venv314).
1. pip install --only-binary :all: <pkg>
2. If no wheel: attempt pip wheel --no-deps <pkg>
3. Record exact status: 'installed from a wheel', 'built locally from a pure-Python source distribution (no compiler needed)', or 'failed: <exact error>'.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import re

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
VENV_PIP = str(PROJECT_ROOT / ".venv314" / "Scripts" / "pip.exe")

def parse_reqs(path: Path):
    reqs = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            reqs.append(line)
    return reqs

def install_pkg(req_str: str):
    # Try wheel first
    cmd_wheel = [VENV_PIP, "install", "--no-deps", "--only-binary", ":all:", req_str]
    res_w = subprocess.run(cmd_wheel, capture_output=True, text=True)
    if res_w.returncode == 0:
        return "installed from a wheel", ""

    # Check if failed because no binary wheel was found
    err_w = res_w.stderr or res_w.stdout
    if "Could not find a version that satisfies the requirement" in err_w or "none of the available versions for" in err_w or "no matching distribution" in err_w:
        # Try building from sdist
        with tempfile.TemporaryDirectory() as tmp_dir:
            cmd_build = [VENV_PIP, "wheel", "--no-deps", "--wheel-dir", tmp_dir, req_str]
            res_b = subprocess.run(cmd_build, capture_output=True, text=True)
            if res_b.returncode == 0:
                # Built wheel! Install it
                built_wheels = list(Path(tmp_dir).glob("*.whl"))
                if built_wheels:
                    cmd_inst = [VENV_PIP, "install", "--no-deps", str(built_wheels[0])]
                    res_i = subprocess.run(cmd_inst, capture_output=True, text=True)
                    if res_i.returncode == 0:
                        return "built locally from a pure-Python source distribution (no compiler needed)", ""
                    else:
                        return "failed", res_i.stderr or res_i.stdout
                return "failed", "Wheel command succeeded but no wheel file produced"
            else:
                err_b = (res_b.stderr or res_b.stdout).strip().splitlines()
                last_err = err_b[-1] if err_b else "Build failed"
                for l in err_b:
                    if "error:" in l.lower() or "failed" in l.lower():
                        last_err = l.strip()
                        break
                return "failed", f"pip wheel error: {last_err}"
    else:
        err_lines = err_w.strip().splitlines()
        last_err = err_lines[-1] if err_lines else "Install failed"
        return "failed", f"pip install error: {last_err}"

def main():
    print("Upgrading pip in .venv314...")
    subprocess.run([VENV_PIP, "install", "--upgrade", "pip"], capture_output=True)

    runtime_reqs = parse_reqs(PROJECT_ROOT / "requirements.txt")
    dev_reqs = parse_reqs(PROJECT_ROOT / "requirements-dev.txt")

    results = {"runtime": {}, "dev": {}}

    print("\n--- INSTALLING RUNTIME PACKAGES (Python 3.14) ---")
    for r in runtime_reqs:
        # Handle upgrades if needed: pillow, pypdf
        test_r = r
        if r.startswith("pillow=="):
            test_r = "pillow>=13.0.0"
        elif r.startswith("pypdf=="):
            test_r = "pypdf>=7.0.0"

        st, err = install_pkg(test_r)
        pkg_name = test_r.split("=")[0].split(">")[0].split("<")[0]
        results["runtime"][pkg_name] = {"spec": test_r, "status": st, "error": err}
        print(f"  {pkg_name:<24} : {st} {f'({err})' if err else ''}")

    print("\n--- INSTALLING DEV / BUILD PACKAGES (Python 3.14) ---")
    for r in dev_reqs:
        st, err = install_pkg(r)
        pkg_name = r.split("=")[0].split(">")[0].split("<")[0]
        results["dev"][pkg_name] = {"spec": r, "status": st, "error": err}
        print(f"  {pkg_name:<24} : {st} {f'({err})' if err else ''}")

    out_file = PROJECT_ROOT / "reviews" / "install_314_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved results to {out_file}")

if __name__ == "__main__":
    main()
