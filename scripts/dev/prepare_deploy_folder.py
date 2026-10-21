"""Prepare clean deployment folder at D:\\naughty-or-not-deploy."""

import shutil
from pathlib import Path

SRC = Path(r"D:\Naughty or not")
DST = Path(r"D:\naughty-or-not-deploy")

if DST.exists():
    shutil.rmtree(DST)
DST.mkdir(parents=True)

# 1. Directories to copy recursively (excluding caches)
def copy_clean_dir(src_dir: Path, dst_dir: Path):
    if not src_dir.exists():
        return
    for item in src_dir.rglob("*"):
        if item.is_file():
            parts = item.relative_to(src_dir).parts
            if any(p in ("__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache") for p in parts):
                continue
            if item.suffix in (".pyc", ".pyo"):
                continue
            rel = item.relative_to(src_dir)
            target = dst_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)

copy_clean_dir(SRC / "app", DST / "app")
copy_clean_dir(SRC / "modules", DST / "modules")
copy_clean_dir(SRC / "config", DST / "config")
copy_clean_dir(SRC / "installer", DST / "installer")
copy_clean_dir(SRC / "assets", DST / "assets")
copy_clean_dir(SRC / ".github", DST / ".github")
copy_clean_dir(SRC / ".streamlit", DST / ".streamlit")
copy_clean_dir(SRC / "tests", DST / "tests")

# 2. data/aviation/airline_aliases.csv
(DST / "data" / "aviation").mkdir(parents=True, exist_ok=True)
alias_src = SRC / "data" / "aviation" / "airline_aliases.csv"
if alias_src.exists():
    shutil.copy2(alias_src, DST / "data" / "aviation" / "airline_aliases.csv")

# 3. scripts
(DST / "scripts").mkdir(parents=True, exist_ok=True)
shutil.copy2(SRC / "scripts" / "init_data.py", DST / "scripts" / "init_data.py")
shutil.copy2(SRC / "scripts" / "check_deploy_folder.py", DST / "scripts" / "check_deploy_folder.py")
copy_clean_dir(SRC / "scripts" / "dev", DST / "scripts" / "dev")

# 4. Root files
ROOT_FILES = [
    "app.py",
    "desktop_launcher.py",
    "build.spec",
    "requirements.txt",
    "requirements-dev.txt",
    "pytest.ini",
    "README.md",
    "SPEC.md",
    "USER_GUIDE.md",
    "USER_GUIDE.pdf",
    "RELEASE_NOTES.md",
    "THIRD_PARTY_NOTICES.md",
    "NOTICE.md",
    "LICENSE",
    "DEPLOY.md",
    ".gitignore",
    ".env.example",
]

for fname in ROOT_FILES:
    fsrc = SRC / fname
    if fsrc.exists():
        shutil.copy2(fsrc, DST / fname)

print("Created clean deploy folder at:", DST)
