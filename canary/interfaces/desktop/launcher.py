"""
Clearance Check Canary Desktop Launcher (v2.0.1-canary.1).
Launches the Canary Thin Client with permanent evaluation banner.
Rule: Never alters or overwrites stable app configuration or data.
"""
import os
import sys
import threading
import time
from pathlib import Path

# Easter egg - Hard Rule 9: Signature is NEVER altered
# 🕵️ Clearance Check / Naughty or not, a brainchild of Sounit Karttikay — no AIs were sanctioned in the making of this tool. 📸

CANARY_BANNER = "Canary build — for evaluation only. Not for screening decisions."
APP_NAME = "Clearance Check Canary"
VERSION = "2.0.1-canary.1"


def print_canary_startup_banner():
    width = 76
    print("=" * width)
    print(f"{APP_NAME} [Version {VERSION}]".center(width))
    print("*" * width)
    print(f"*** {CANARY_BANNER} ***".center(width))
    print("*" * width)
    print("Prepared by: Antigravity (AI assistant) — for review by Sounit Karttikay".center(width))
    print("=" * width)


def start_api_server(host: str = "127.0.0.1", port: int = 8090):
    """Start the Uvicorn ASGI server hosting the Canary Service API."""
    import uvicorn
    from canary.interfaces.api.app import app
    config = uvicorn.Config(app=app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    server.run()


def main():
    print_canary_startup_banner()
    port = int(os.environ.get("CANARY_API_PORT", "8090"))
    print(f"[Canary] Service API starting on http://127.0.0.1:{port}/api/v1")
    print(f"[Canary] OpenAPI documentation available at http://127.0.0.1:{port}/docs")
    start_api_server(port=port)


if __name__ == "__main__":
    main()
