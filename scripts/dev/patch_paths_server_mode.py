with open("modules/common/paths.py", "r", encoding="utf-8") as f:
    text = f.read()

target = """def get_app_data_dir() -> Path:
    \"\"\"
    Return the per-user data directory (%LOCALAPPDATA%\\NaughtyOrNot).
    Uses NAUGHTY_DATA_DIR environment variable if specified.
    \"\"\"
    override = os.environ.get("NAUGHTY_DATA_DIR")
    if override:
        p = Path(override)
        p.mkdir(parents=True, exist_ok=True)
        return p"""

replacement = """def get_app_data_dir() -> Path:
    \"\"\"
    Return the per-user data directory (%LOCALAPPDATA%\\NaughtyOrNot) in desktop mode,
    or the server data directory in server/container mode.
    Uses NAUGHTY_DATA_DIR environment variable if specified.
    \"\"\"
    mode = os.environ.get("DEPLOYMENT_MODE", "desktop").lower()
    if mode == "server":
        override = os.environ.get("NAUGHTY_DATA_DIR", "/app/data")
        p = Path(override)
        try:
            p.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return p

    override = os.environ.get("NAUGHTY_DATA_DIR")
    if override:
        p = Path(override)
        p.mkdir(parents=True, exist_ok=True)
        return p"""

# Also enhance get_logs_dir, get_reports_dir, get_cache_dir
logs_target = """def get_logs_dir() -> Path:
    \"\"\"Directory holding append-only audit database and logs.\"\"\"
    p = get_app_data_dir() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p"""

logs_replacement = """def get_logs_dir() -> Path:
    \"\"\"Directory holding append-only audit database and logs.\"\"\"
    override = os.environ.get("NAUGHTY_LOGS_DIR")
    if override:
        p = Path(override)
        try:
            p.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return p
    p = get_app_data_dir() / "logs"
    try:
        p.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return p"""

rep_target = """def get_reports_dir() -> Path:
    \"\"\"Directory holding generated PDF and Excel reports.\"\"\"
    p = get_app_data_dir() / "reports"
    p.mkdir(parents=True, exist_ok=True)
    return p"""

rep_replacement = """def get_reports_dir() -> Path:
    \"\"\"Directory holding generated PDF and Excel reports.\"\"\"
    override = os.environ.get("NAUGHTY_REPORTS_DIR")
    if override:
        p = Path(override)
        try:
            p.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return p
    p = get_app_data_dir() / "reports"
    try:
        p.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return p"""

cache_target = """def get_cache_dir() -> Path:
    \"\"\"Directory holding binary index caches.\"\"\"
    p = get_app_data_dir() / "cache"
    p.mkdir(parents=True, exist_ok=True)
    return p"""

cache_replacement = """def get_cache_dir() -> Path:
    \"\"\"Directory holding binary index caches.\"\"\"
    override = os.environ.get("NAUGHTY_CACHE_DIR")
    if override:
        p = Path(override)
        try:
            p.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return p
    p = get_app_data_dir() / "cache"
    try:
        p.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return p"""

text = text.replace(target, replacement)
text = text.replace(logs_target, logs_replacement)
text = text.replace(rep_target, rep_replacement)
text = text.replace(cache_target, cache_replacement)

with open("modules/common/paths.py", "w", encoding="utf-8") as f:
    f.write(text)

print("modules/common/paths.py patched successfully!")
