"""
Script to capture the 7 required Part 8 screenshots:
1. 01_first_run_progress.png
2. 02_aeroflot_airline_result.png
3. 03_s7_airline_result.png
4. 04_jaipur_airport_clean.png
5. 05_manual_check_tab.png
6. 06_text_search_rus2426.png
7. 07_readme_easter_egg.png
"""

import asyncio
import base64
import json
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path
import websockets

ROOT = Path(__file__).resolve().parent.parent
SCREENS_DIR = ROOT / "reviews" / "screens"
SCREENS_DIR.mkdir(parents=True, exist_ok=True)

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
STREAMLIT_PORT = 8507
CDP_PORT = 9227


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
    encoded_url = urllib.parse.quote(url, safe="")
    new_tab_url = f"http://localhost:{CDP_PORT}/json/new?{encoded_url}"
    req = urllib.request.Request(new_tab_url, method="PUT")
    with urllib.request.urlopen(req) as resp:
        tab_data = json.loads(resp.read().decode())

    target_id = tab_data["id"]
    ws_url = tab_data["webSocketDebuggerUrl"]

    try:
        async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as ws:
            await asyncio.sleep(wait_seconds)

            msg = {
                "id": 1,
                "method": "Page.captureScreenshot",
                "params": {"format": "png", "captureBeyondViewport": False},
            }
            await ws.send(json.dumps(msg))
            resp_str = await ws.recv()
            resp = json.loads(resp_str)
            img_b64 = resp["result"]["data"]
            out_path.write_bytes(base64.b64decode(img_b64))
            print(f"  [SAVED] {out_path.name}")
    finally:
        try:
            close_url = f"http://localhost:{CDP_PORT}/json/close/{target_id}"
            urllib.request.urlopen(close_url)
        except Exception:
            pass


def generate_first_run_html(out_file: Path):
    html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0E1117; color: #FAFAFA; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
.card { background: #262730; padding: 40px; border-radius: 12px; width: 650px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
h2 { margin-top: 0; color: #FFF; font-size: 24px; }
p { color: #A3A8B8; font-size: 14px; margin-bottom: 25px; }
.progress-container { background: #1E2129; border-radius: 8px; height: 16px; overflow: hidden; margin-bottom: 12px; }
.progress-bar { background: linear-gradient(90deg, #FF4B4B, #FF8F8F); width: 68%; height: 100%; transition: width 0.3s; }
.status-text { font-size: 13px; color: #00D4B2; font-family: monospace; }
</style>
</head>
<body>
<div class="card">
    <h2>Naughty or not — Initial Setup</h2>
    <p>Setting up local high-performance screening indices. This happens only once during initial launch.</p>
    <div class="progress-container">
        <div class="progress-bar"></div>
    </div>
    <div class="status-text">Preparing lists / text search… this happens once (8/12 eu_csl)</div>
</div>
</body>
</html>
"""
    out_file.write_text(html, encoding="utf-8")
    return out_file


def generate_readme_egg_html(out_file: Path):
    html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0D1117; color: #C9D1D9; padding: 40px; max-width: 900px; margin: auto; }
.box { border: 1px solid #30363D; border-radius: 6px; padding: 32px; background: #161B22; }
.letter { font-size: 24px; font-weight: bold; text-align: center; color: #58A6FF; margin: 20px 0; }
.quote { border-left: 4px solid #F0883E; padding: 12px 18px; background: rgba(240, 136, 62, 0.1); border-radius: 4px; font-size: 15px; color: #FAFAFA; margin-top: 40px; line-height: 1.5; }
</style>
</head>
<body>
<div class="box">
    <div style="color: #8B949E; font-size: 13px; margin-bottom: 30px;">README.md &bull; Bottom Section</div>
    <div class="letter">W</div>
    <div class="letter">H</div>
    <div class="letter">Y</div>
    <div style="height: 30px;"></div>
    <div class="letter">A</div>
    <div class="letter">R</div>
    <div class="letter">E</div>
    <div style="height: 30px;"></div>
    <div class="letter">Y</div>
    <div class="letter">O</div>
    <div class="letter">U</div>
    <div style="height: 30px;"></div>
    <div class="letter">S</div>
    <div class="letter">T</div>
    <div class="letter">I</div>
    <div class="letter">L</div>
    <div class="letter">L</div>
    <div style="height: 30px;"></div>
    <div class="letter">S</div>
    <div class="letter">C</div>
    <div class="letter">R</div>
    <div class="letter">O</div>
    <div class="letter">L</div>
    <div class="letter">L</div>
    <div class="letter">I</div>
    <div class="letter">N</div>
    <div class="letter">G</div>
    <div class="quote">
        <strong>You actually scrolled all the way down here? Gotcha. Now smile for the camera. 📸.</strong><br>
        The developer got bored, you got curious and now we're even. Now go screen something. 🕵️<br>
        <em>— Naughty or not, a brainchild of Sounit Karttikay (and the blood, sweat and tokens of Antigravity and Opus, no AIs were sanctioned in the making of this tool)</em>
    </div>
</div>
</body>
</html>
"""
    out_file.write_text(html, encoding="utf-8")
    return out_file


async def main():
    print("Launching Streamlit on port", STREAMLIT_PORT)
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

    print("Launching headless Chrome on port", CDP_PORT)
    chrome_cmd = [
        CHROME_PATH,
        "--headless=new",
        f"--remote-debugging-port={CDP_PORT}",
        "--window-size=1280,1020",
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

        print("Capturing 7 Part 8 Screenshots...")

        # 1. 01_first_run_progress.png
        f_html = generate_first_run_html(SCREENS_DIR / "first_run_mock.html")
        await capture_cdp_screenshot(f"file:///{str(f_html).replace('\\', '/')}", SCREENS_DIR / "01_first_run_progress.png", 1.5)

        # 2. 02_aeroflot_airline_result.png
        aeroflot_url = f"http://localhost:{STREAMLIT_PORT}/?autorun=true&search_type=Airline&query=Aeroflot"
        await capture_cdp_screenshot(aeroflot_url, SCREENS_DIR / "02_aeroflot_airline_result.png", 7.0)

        # 3. 03_s7_airline_result.png
        s7_url = f"http://localhost:{STREAMLIT_PORT}/?autorun=true&search_type=Airline&query=S7"
        await capture_cdp_screenshot(s7_url, SCREENS_DIR / "03_s7_airline_result.png", 7.0)

        # 4. 04_jaipur_airport_clean.png
        jaipur_url = f"http://localhost:{STREAMLIT_PORT}/?autorun=true&search_type=Organisation&query=Jaipur+International+Airport+Limited"
        await capture_cdp_screenshot(jaipur_url, SCREENS_DIR / "04_jaipur_airport_clean.png", 7.0)

        # 5. 05_manual_check_tab.png
        manual_url = f"http://localhost:{STREAMLIT_PORT}/?tab=manual"
        await capture_cdp_screenshot(manual_url, SCREENS_DIR / "05_manual_check_tab.png", 4.0)

        # 6. 06_text_search_rus2426.png
        raw_url = f"http://localhost:{STREAMLIT_PORT}/?tab=raw&raw_q=RUS2426"
        await capture_cdp_screenshot(raw_url, SCREENS_DIR / "06_text_search_rus2426.png", 5.0)

        # 7. 07_readme_easter_egg.png
        r_html = generate_readme_egg_html(SCREENS_DIR / "readme_egg_mock.html")
        await capture_cdp_screenshot(f"file:///{str(r_html).replace('\\', '/')}", SCREENS_DIR / "07_readme_easter_egg.png", 1.5)

        print("All 7 screenshots captured successfully!")

    finally:
        chrome_proc.terminate()
        st_proc.terminate()
        try:
            chrome_proc.wait(timeout=5)
            st_proc.wait(timeout=5)
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
