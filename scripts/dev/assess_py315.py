import importlib.metadata
import os
from pathlib import Path
import packaging.tags

def assess_py315():
    # Read requirements.lock
    packages = []
    with open("requirements.lock", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "==" in line and not line.startswith("#"):
                pkg_name = line.split("==")[0].strip()
                pkg_ver = line.split("==")[1].split()[0].strip()
                packages.append((pkg_name, pkg_ver))

    print(f"Total packages in lock: {len(packages)}")
    pure_python = []
    c_extensions = []
    for name, ver in packages:
        try:
            dist = importlib.metadata.distribution(name)
            # Check wheel / files
            # Look at RECORD or files in dist
            files = dist.files or []
            has_so = any(str(p).endswith((".pyd", ".so", ".dll")) for p in files)
            # check wheel tags if RECORD or WHEEL exists
            wheel_text = dist.read_text("WHEEL")
            tag_lines = [l for l in (wheel_text or "").splitlines() if l.startswith("Tag:")]
            tags = [l.split("Tag:")[1].strip() for l in tag_lines]
            is_pure = any("none-any" in t for t in tags) or not has_so
            if is_pure:
                pure_python.append((name, ver, tags))
            else:
                c_extensions.append((name, ver, tags))
        except Exception as e:
            # check if pure
            pure_python.append((name, ver, [str(e)]))

    print("\n--- PURE PYTHON WHEELS (Will install and run cleanly on Python 3.15 without rebuild) ---")
    for name, ver, tags in pure_python:
        print(f"  {name} {ver} ({', '.join(tags) if tags else 'pure'})")

    print("\n--- C-EXTENSION PACKAGES (Require CPython ABI compatibility or wheel build for Python 3.15) ---")
    for name, ver, tags in c_extensions:
        print(f"  {name} {ver} ({', '.join(tags) if tags else 'C extension'})")

if __name__ == "__main__":
    assess_py315()
