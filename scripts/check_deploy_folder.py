"""
Verify clean deployment folder hygiene.
Fails if any forbidden file or pattern is present, or if the deploy folder is over 20 MB (excluding installer).
"""

import sys
from pathlib import Path

FORBIDDEN_NAMES = {
    ".env",
    "raw_index.db",
    "screening.db",
    "PREPUSH_CHECK.md",
}

FORBIDDEN_EXTENSIONS = {
    ".pyc",
    ".db",
    ".log",
}

FORBIDDEN_DIRS = {
    ".venv",
    "venv",
    "logs",
    "reports",
    "reviews",
    "scratch",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
}

FORBIDDEN_PREFIXES = (
    "investigate_",
    "check_",
    "run_step",
    "temp_",
)


def check_deploy_folder(deploy_dir: Path) -> bool:
    if not deploy_dir.is_dir():
        print(f"ERROR: Deploy directory not found: {deploy_dir}")
        return False

    errors = []
    total_size = 0

    for p in deploy_dir.rglob("*"):
        rel = p.relative_to(deploy_dir)
        rel_str = str(rel).replace("\\", "/")
        parts = rel.parts

        # Check forbidden dirs
        for part in parts:
            if part in FORBIDDEN_DIRS:
                errors.append(f"Forbidden directory component: {rel_str}")
                break

        if p.is_file():
            # Check forbidden names
            if p.name in FORBIDDEN_NAMES:
                errors.append(f"Forbidden file: {rel_str}")

            # Check forbidden extensions
            if p.suffix.lower() in FORBIDDEN_EXTENSIONS:
                errors.append(f"Forbidden extension: {rel_str}")

            # Check forbidden scripts
            if any(p.name.startswith(pre) for pre in ("investigate_", "run_step", "temp_")):
                errors.append(f"Forbidden temporary script: {rel_str}")
            if p.parent == deploy_dir and p.name.startswith("check_"):
                errors.append(f"Forbidden ad-hoc script in root: {rel_str}")

            # Disallow prompt/review/audit md files at root or outside docs/dev
            if p.name.endswith(".md"):
                upper = p.name.upper()
                if any(k in upper for k in ["AUDIT", "REVIEW", "PROMPT", "STEP0", "PARTA"]):
                    errors.append(f"Forbidden dev markdown file: {rel_str}")

            # Disallow data files outside aviation and india fixtures
            if "data" in parts:
                if any(k in parts for k in ("raw", "raw_search", "fatf", "seed")):
                    errors.append(f"Forbidden data file: {rel_str}")

            # Calculate size excluding installer/ directory
            if "installer" not in parts:
                total_size += p.stat().st_size

    total_mb = total_size / (1024 * 1024)
    print(f"Deploy folder size (excluding installer/): {total_mb:.2f} MB")

    if total_mb > 20.0:
        errors.append(f"Deploy folder size ({total_mb:.2f} MB) exceeds 20.0 MB limit")

    if errors:
        print("Deploy Hygiene Violations Found:")
        for e in errors:
            print(f"  - {e}")
        return False

    print("Deploy folder hygiene verification PASSED! Clean and compliant.")
    return True


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"D:\naughty-or-not-deploy")
    ok = check_deploy_folder(target)
    sys.exit(0 if ok else 1)
