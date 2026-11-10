"""
Generate pip lock files with SHA256 hashes using the PyPI JSON API.
Generates:
  - requirements.lock (runtime packages)
  - requirements-dev.lock (dev packages)
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

def fetch_hashes_for_package(pkg: str, version: str):
    url = f"https://pypi.org/pypi/{pkg}/{version}/json"
    req = urllib.request.Request(url, headers={"User-Agent": "NaughtyOrNot-Lockfile-Generator/1.2.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            hashes = []
            for u in data.get("urls", []):
                sha = u.get("digests", {}).get("sha256")
                if sha:
                    hashes.append(f"--hash=sha256:{sha}")
            return sorted(set(hashes))
    except Exception as e:
        print(f"Error fetching {pkg}=={version}: {e}")
        return []

def generate_lock_file(req_file: Path, lock_file: Path):
    print(f"Generating {lock_file.name} from {req_file.name}...")
    lines = req_file.read_text(encoding="utf-8").splitlines()
    out_lines = [
        f"# Lock file generated for {req_file.name} with exact SHA-256 hashes",
        "# Generated for Python 3.14.x on Windows amd64",
        "",
    ]
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Match pkg==version or pkg>=version
        m = re.match(r"^([A-Za-z0-9_.\-]+)(?:==|>=)([0-9A-Za-z_.\-]+)", line)
        if not m:
            continue
        pkg, ver = m.group(1), m.group(2)
        print(f"  Querying hashes for {pkg}=={ver}...")
        hashes = fetch_hashes_for_package(pkg, ver)
        if not hashes:
            out_lines.append(f"{pkg}=={ver}")
        else:
            first_hash = hashes[0]
            out_lines.append(f"{pkg}=={ver} \\")
            for h in hashes[:-1]:
                out_lines.append(f"    {h} \\")
            out_lines.append(f"    {hashes[-1]}")
    
    lock_file.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"Wrote {lock_file}")

if __name__ == "__main__":
    generate_lock_file(ROOT / "requirements.txt", ROOT / "requirements.lock")
    generate_lock_file(ROOT / "requirements-dev.txt", ROOT / "requirements-dev.lock")
