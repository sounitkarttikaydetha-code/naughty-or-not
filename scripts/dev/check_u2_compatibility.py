"""
Audit compatibility and wheel existence for Python 3.14 (cp314) and 3.15 (cp315) on Windows (win_amd64).
Uses packaging.tags to identify all compatible tags (including abi3, py3-none-any, and py3-none-win_amd64).
Distinguishes pure-Python source distributions from compiled packages.
"""

import json
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import packaging.tags
import packaging.utils

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def get_compatible_tags(py_ver: Tuple[int, int], interpreter: str) -> Set[packaging.tags.Tag]:
    c_tags = set(packaging.tags.cpython_tags(py_ver, platforms=["win_amd64"]))
    comp_tags = set(packaging.tags.compatible_tags(py_ver, interpreter=interpreter, platforms=["win_amd64"]))
    return c_tags | comp_tags


TAGS_314 = get_compatible_tags((3, 14), "cp314")
TAGS_315 = get_compatible_tags((3, 15), "cp315")


def parse_reqs(path: Path) -> Dict[str, Tuple[str, str]]:
    reqs = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r"^([a-zA-Z0-9_\-\.]+)\s*([=><~!]=?)\s*([0-9a-zA-Z_\-\.]+)", line)
            if m:
                reqs[m.group(1)] = (m.group(2), m.group(3))
            else:
                reqs[line.split()[0]] = ("", "")
    return reqs


def check_distribution(files: List[Dict[str, Any]], target_tags: Set[packaging.tags.Tag]) -> Tuple[str, str, str]:
    """
    Returns (status, filename, classification).
    status: 'wheel' | 'pure_python_sdist' | 'compiled_sdist' | 'none'
    """
    best_wheel = None
    best_class = None
    sdist = None

    for f in files:
        fn = f.get("filename", "")
        if fn.endswith(".whl"):
            try:
                name, ver, bld, w_tags = packaging.utils.parse_wheel_filename(fn)
                matching = w_tags & target_tags
                if matching:
                    # Classify wheel
                    for t in matching:
                        if t.abi == "abi3":
                            cls = "abi3"
                            break
                        elif t.platform == "any":
                            cls = "py3-none-any"
                            break
                        elif "win_amd64" in t.platform and t.abi.startswith("cp"):
                            cls = "cp-binary"
                            break
                        elif "win_amd64" in t.platform and t.abi == "none":
                            cls = "py3-none-win_amd64"
                            break
                        else:
                            cls = "compatible-wheel"
                    best_wheel = fn
                    best_class = cls
                    break
            except Exception:
                pass
        elif fn.endswith(".tar.gz") or fn.endswith(".zip"):
            sdist = fn

    if best_wheel:
        return "wheel", best_wheel, best_class

    if sdist:
        return "sdist", sdist, "source-dist"

    return "none", "", "no-distribution"


def check_package_pypi(pkg_name: str) -> Dict[str, Any]:
    url = f"https://pypi.org/pypi/{pkg_name}/json"
    headers = {"User-Agent": "ClearanceCheck-Audit/1.2.0"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}

    info = data.get("info", {})
    latest_version = info.get("version", "")
    license_str = info.get("license") or "Unknown"

    releases = data.get("releases", {})
    latest_files = releases.get(latest_version, [])

    # Check 3.14 on latest
    st_314, fn_314, cls_314 = check_distribution(latest_files, TAGS_314)
    # Check 3.15 on latest
    st_315, fn_315, cls_315 = check_distribution(latest_files, TAGS_315)

    # If wheel not found on latest, search recent 5 releases
    if st_314 != "wheel" or st_315 != "wheel":
        recent_files = []
        for rel_v, f_list in list(releases.items())[-5:]:
            recent_files.extend(f_list)
        if st_314 != "wheel":
            st_314_r, fn_314_r, cls_314_r = check_distribution(recent_files, TAGS_314)
            if st_314_r == "wheel":
                st_314, fn_314, cls_314 = st_314_r, fn_314_r, cls_314_r
        if st_315 != "wheel":
            st_315_r, fn_315_r, cls_315_r = check_distribution(recent_files, TAGS_315)
            if st_315_r == "wheel":
                st_315, fn_315, cls_315 = st_315_r, fn_315_r, cls_315_r

    return {
        "latest_version": latest_version,
        "license": license_str,
        "status_314": st_314,
        "file_314": fn_314,
        "class_314": cls_314,
        "status_315": st_315,
        "file_315": fn_315,
        "class_315": cls_315,
    }


def main():
    print("=" * 80)
    print("PYTHON 3.14 & 3.15 COMPATIBILITY MATRIX AUDIT (packaging.tags)")
    print("=" * 80)

    runtime_reqs = parse_reqs(PROJECT_ROOT / "requirements.txt")
    dev_reqs = parse_reqs(PROJECT_ROOT / "requirements-dev.txt")

    results = {"runtime": {}, "dev": {}}

    print(f"\n--- RUNTIME PACKAGES ({len(runtime_reqs)}) ---")
    print(f"{'Package':<24} | {'Current':<10} | {'Target':<10} | {'Python 3.14':<20} | {'Python 3.15':<20} | {'Licence':<15}")
    print("-" * 115)

    for pkg, (op, cur_v) in runtime_reqs.items():
        res = check_package_pypi(pkg)
        res["current_version"] = cur_v
        results["runtime"][pkg] = res

        s314 = f"{res['status_314']} ({res['class_314']})"
        s315 = f"{res['status_315']} ({res['class_315']})"
        lic = (res.get("license") or "Unknown")[:15].replace("\n", " ")
        print(f"{pkg:<24} | {cur_v:<10} | {res.get('latest_version',''):<10} | {s314:<20} | {s315:<20} | {lic:<15}")

    print(f"\n--- BUILD / DEV PACKAGES ({len(dev_reqs)}) ---")
    print(f"{'Package':<24} | {'Current':<10} | {'Target':<10} | {'Python 3.14':<20} | {'Python 3.15':<20} | {'Licence':<15}")
    print("-" * 115)

    for pkg, (op, cur_v) in dev_reqs.items():
        res = check_package_pypi(pkg)
        res["current_version"] = cur_v
        results["dev"][pkg] = res

        s314 = f"{res['status_314']} ({res['class_314']})"
        s315 = f"{res['status_315']} ({res['class_315']})"
        lic = (res.get("license") or "Unknown")[:15].replace("\n", " ")
        print(f"{pkg:<24} | {cur_v:<10} | {res.get('latest_version',''):<10} | {s314:<20} | {s315:<20} | {lic:<15}")

    out_file = PROJECT_ROOT / "reviews" / "u2_compatibility_audit_fixed.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved updated audit to {out_file}")


if __name__ == "__main__":
    main()
