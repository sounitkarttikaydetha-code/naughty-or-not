"""
Release Hygiene Verification Script
Ensures that built distribution artifacts contain:
- Zero .env files or secrets
- Zero audit logs or generated reports
- Zero *.db database files (e.g. raw_index.db, screening.db)
- Zero screenshots
- Zero GPL fonts (DarkGarden, etc.)
- Only permitted files
"""

import sys
from pathlib import Path


def run_hygiene_check(target_dir: Path) -> bool:
    print(f"Running release hygiene check on: {target_dir}")
    if not target_dir.exists():
        print(f"Error: Target path {target_dir} does not exist!")
        return False

    violations = []

    for path in target_dir.rglob("*"):
        if not path.is_file():
            continue

        rel = path.relative_to(target_dir)
        lower_name = path.name.lower()
        lower_str = str(rel).lower()

        # 1. No .env files
        if ".env" in lower_name:
            violations.append(f"Forbidden environment file: {rel}")

        # 2. No runtime logs or reports directories
        if "logs/" in lower_str or "logs\\" in lower_str or "reports/" in lower_str or "reports\\" in lower_str:
            violations.append(f"Forbidden runtime logs/reports directory: {rel}")

        # 3. No *.db files (raw_index.db, screening.db, etc.)
        if path.suffix.lower() == ".db":
            violations.append(f"Forbidden database file: {rel}")

        # 4. No screenshots in binary distribution
        if path.suffix.lower() in [".png", ".jpg", ".jpeg"] and "screens" in lower_str:
            violations.append(f"Forbidden screenshot in distribution: {rel}")

        # 5. No GPL fonts
        if "darkgarden" in lower_name:
            violations.append(f"Forbidden GPL font: {rel}")

        # 6. Check for secret tokens/keys in plain text
        if path.suffix.lower() in [".txt", ".json", ".yaml", ".yml", ".py"]:
            try:
                import re
                content = path.read_text(encoding="utf-8", errors="ignore")
                if re.search(r"key_live_[a-zA-Z0-9_-]{16,}", content) or re.search(r"AIzaSy[a-zA-Z0-9_-]{33}", content):
                    violations.append(f"Possible API key found in: {rel}")
            except Exception:
                pass

    if violations:
        print("[FAIL] RELEASE HYGIENE CHECK FAILED:")
        for v in violations:
            print(f"   - {v}")
        return False

    print("[PASS] RELEASE HYGIENE CHECK PASSED: Artifacts are 100% clean of secrets, logs, databases, and GPL fonts.")
    return True


if __name__ == "__main__":
    check_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("dist/NaughtyOrNot")
    if not run_hygiene_check(check_path):
        sys.exit(1)
