import yaml
import re
from pathlib import Path

domains = {}
with open("config/sources.yaml", "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

for s in cfg.get("sources", []):
    url = s.get("url", "")
    m = re.search(r"https?://([^/]+)", url)
    if m:
        domains[m.group(1)] = f"config url: {s.get('name')}"
    cand = s.get("candidate_url", "")
    m2 = re.search(r"https?://([^/]+)", cand)
    if m2:
        domains[m2.group(1)] = f"config candidate: {s.get('name')}"
    fallback = s.get("fallback_url", "")
    m3 = re.search(r"https?://([^/]+)", fallback)
    if m3:
        domains[m3.group(1)] = f"config fallback: {s.get('name')}"

for p in list(Path("modules").glob("**/*.py")) + list(Path("app").glob("**/*.py")) + [Path("app.py"), Path("desktop_launcher.py"), Path("scripts/source_update_check.py"), Path("scripts/init_data.py")]:
    try:
        content = p.read_text(encoding="utf-8", errors="ignore")
        matches = re.findall(r"https?://([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", content)
        for d in matches:
            d_lower = d.lower()
            if not any(x in d_lower for x in ["localhost", "127.0.0.1", "schemas.", "cyclonedx.", "w3.org", "openxmlformats", "example.com", "pypi.org", "python.org"]):
                if d not in domains:
                    domains[d] = f"code: {p}"
    except Exception as e:
        pass

for d in sorted(domains):
    print(f"{d:45} | {domains[d]}")
print("Total domains:", len(domains))
