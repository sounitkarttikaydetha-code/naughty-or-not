"""
Script to capture pixel-perfect UI screenshots for T5 review using Chrome CDP.
"""

import asyncio
import base64
import json
import subprocess
import time
import urllib.request
import urllib.parse
from pathlib import Path
import websockets

ROOT = Path(__file__).resolve().parent.parent
SCREENS_DIR = ROOT / "reviews" / "screens"
SCREENS_DIR.mkdir(parents=True, exist_ok=True)

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
STREAMLIT_PORT = 8503
CDP_PORT = 9222


def wait_for_http(url, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


async def capture_cdp_screenshot(url: str, out_path: Path, wait_seconds: float = 6.0):
    # Open new tab via CDP HTTP endpoint with fully escaped destination URL
    encoded_url = urllib.parse.quote(url, safe="")
    new_tab_url = f"http://localhost:{CDP_PORT}/json/new?{encoded_url}"
    req = urllib.request.Request(new_tab_url, method="PUT")
    with urllib.request.urlopen(req) as resp:
        tab_data = json.loads(resp.read().decode())

    target_id = tab_data["id"]
    ws_url = tab_data["webSocketDebuggerUrl"]

    try:
        async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as ws:
            # Wait for Streamlit execution and DOM rendering to finish
            await asyncio.sleep(wait_seconds)

            # Capture screenshot
            msg = {
                "id": 1,
                "method": "Page.captureScreenshot",
                "params": {"format": "png", "captureBeyondViewport": False},
            }
            await ws.send(json.dumps(msg))

            while True:
                resp = await ws.recv()
                data = json.loads(resp)
                if data.get("id") == 1:
                    img_data = base64.b64decode(data["result"]["data"])
                    with open(out_path, "wb") as f:
                        f.write(img_data)
                    break
    finally:
        # Close the tab
        try:
            close_url = f"http://localhost:{CDP_PORT}/json/close/{target_id}"
            urllib.request.urlopen(close_url)
        except Exception:
            pass


async def main():
    print("Starting Streamlit server on port", STREAMLIT_PORT)
    st_cmd = [
        str(ROOT / ".venv" / "Scripts" / "python.exe"),
        "-m",
        "streamlit",
        "run",
        "app.py",
        f"--server.port={STREAMLIT_PORT}",
        "--server.headless=true",
    ]
    st_proc = subprocess.Popen(st_cmd, cwd=str(ROOT))

    print("Starting headless Chrome on port", CDP_PORT)
    chrome_cmd = [
        CHROME_PATH,
        "--headless=new",
        f"--remote-debugging-port={CDP_PORT}",
        "--window-size=1280,1200",
        "--disable-gpu",
        "--hide-scrollbars",
        "about:blank",
    ]
    chrome_proc = subprocess.Popen(chrome_cmd)

    try:
        if not wait_for_http(f"http://localhost:{STREAMLIT_PORT}/_stcore/health", timeout=30):
            print("Streamlit server failed to start")
            return
        if not wait_for_http(f"http://localhost:{CDP_PORT}/json/version", timeout=15):
            print("Chrome CDP failed to start")
            return

        print("Both Streamlit and Chrome CDP are ready!")

        searches = [
            (
                "01_airline_aeroflot.png",
                f"http://localhost:{STREAMLIT_PORT}/?search_type=Airline&query=Aeroflot&autorun=true",
                9.0,
            ),
            (
                "02_aircraft_ra73093.png",
                f"http://localhost:{STREAMLIT_PORT}/?search_type=Aircraft&query=RA-73093&autorun=true",
                5.0,
            ),
            (
                "03_organisation_jaipur_airport.png",
                f"http://localhost:{STREAMLIT_PORT}/?search_type=Organisation&query=Jaipur%20International%20Airport%20Limited&autorun=true",
                6.0,
            ),
            (
                "04_person_mohammed_khan.png",
                f"http://localhost:{STREAMLIT_PORT}/?search_type=Person&query=Mohammed%20Khan&dob=1980&autorun=true",
                6.0,
            ),
        ]

        for filename, url, wait_time in searches:
            out_file = SCREENS_DIR / filename
            print(f"Capturing {filename} (waiting {wait_time}s)...")
            await capture_cdp_screenshot(url, out_file, wait_seconds=wait_time)
            print(f"Captured {filename}: {out_file.stat().st_size} bytes")

    finally:
        print("Cleaning up processes...")
        chrome_proc.terminate()
        st_proc.terminate()
        try:
            chrome_proc.wait(timeout=5)
            st_proc.wait(timeout=5)
        except Exception:
            pass
        print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
