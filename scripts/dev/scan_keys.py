"""
Scan working tree, git log, logs/, reports/, reviews/ and screenshots
for any leaks of the OpenSanctions API key (excluding last 4 characters).
"""
import os
import subprocess
from pathlib import Path

def main():
    env_path = Path(".env")
    if not env_path.exists():
        print("No .env found!")
        return

    key = ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "OPENSANCTIONS" in line and "=" in line:
            key = line.split("=", 1)[1].strip().strip("'\"")

    if not key or len(key) < 12:
        print("No valid key found in .env")
        return

    secret_part = key[:-4]
    print(f"Scanning for secret fragment (length {len(secret_part)}, ending in ...{key[-4:]})...")

    # 1. Scan git history
    p = subprocess.run(["git", "log", "-p", "--all"], capture_output=True, text=True, errors="ignore")
    if secret_part in p.stdout:
        print("WARNING: Key found in git log!")
    else:
        print("Git history: CLEAN (zero leaks)")

    # 2. Scan working tree
    found = []
    for root, dirs, files in os.walk("."):
        if ".git" in dirs:
            dirs.remove(".git")
        if ".venv" in dirs:
            dirs.remove(".venv")
        for f in files:
            if f == ".env":
                continue
            fp = Path(root) / f
            try:
                content = fp.read_bytes()
                if secret_part.encode("utf-8") in content:
                    found.append(str(fp))
            except Exception:
                pass

    print(f"Working tree scan: {len(found)} leaks found: {found}")

    # 3. Check .env git status
    p_status = subprocess.run(["git", "status", "--ignored"], capture_output=True, text=True)
    if ".env" in p_status.stdout and "Ignored files:" in p_status.stdout:
        print(".env status: CONFIRMED GIT-IGNORED")
    elif ".env" not in p_status.stdout:
        print(".env status: NOT TRACKED")
    else:
        print(".env status: CHECK NEEDED")

    # 4. Check usage log
    usage_log = Path("logs/opensanctions_usage.csv")
    if usage_log.exists():
        lines = [l for l in usage_log.read_text(encoding="utf-8").splitlines() if l.strip()]
        print(f"Usage log exists: {len(lines)} lines (header + {max(0, len(lines)-1)} rows)")
    else:
        print("Usage log does not exist yet (0 credits used)")

if __name__ == "__main__":
    main()
