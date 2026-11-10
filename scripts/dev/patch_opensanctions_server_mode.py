with open("modules/opensanctions/client.py", "r", encoding="utf-8") as f:
    text = f.read()

target = """def get_api_key() -> Optional[str]:
    \"\"\"Retrieve OPENSANCTIONS_API_KEY from session key manager, environment or .env file.\"\"\"
    try:
        from modules.opensanctions.key_manager import get_session_key
        sk = get_session_key()
        if sk and sk.strip():
            return sk.strip()
    except Exception:
        pass"""

replacement = """def get_api_key() -> Optional[str]:
    \"\"\"
    Retrieve OPENSANCTIONS_API_KEY.
    In server mode (DEPLOYMENT_MODE=server):
    - OpenSanctions is OFF unless explicitly enabled via ENABLE_OPENSANCTIONS=true
    - Key comes strictly from OPENSANCTIONS_API_KEY environment variable (no credential manager/no .env)
    \"\"\"
    mode = os.environ.get("DEPLOYMENT_MODE", "desktop").lower()
    if mode == "server":
        enabled = os.environ.get("ENABLE_OPENSANCTIONS", "false").lower() in ("true", "1", "yes")
        if not enabled:
            return None
        key = os.getenv("OPENSANCTIONS_API_KEY")
        return key.strip() if key and key.strip() else None

    try:
        from modules.opensanctions.key_manager import get_session_key
        sk = get_session_key()
        if sk and sk.strip():
            return sk.strip()
    except Exception:
        pass"""

text = text.replace(target, replacement)

with open("modules/opensanctions/client.py", "w", encoding="utf-8") as f:
    f.write(text)

print("modules/opensanctions/client.py patched successfully!")
