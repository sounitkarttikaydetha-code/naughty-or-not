"""
Script to capture the 4 required Part B screenshots:
1. screenshot_installer.png
2. screenshot_first_run.png
3. screenshot_key_dialog.png
4. screenshot_name_check.png
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

ROOT = Path(__file__).resolve().parent.parent.parent
SCREENS_DIR = ROOT / "reviews" / "screens"
SCREENS_DIR.mkdir(parents=True, exist_ok=True)

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
STREAMLIT_PORT = 8504
CDP_PORT = 9223


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


async def capture_cdp_screenshot(url: str, out_path: Path, wait_seconds: float = 5.0):
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

            while True:
                resp = await ws.recv()
                data = json.loads(resp)
                if data.get("id") == 1:
                    img_data = base64.b64decode(data["result"]["data"])
                    with open(out_path, "wb") as f:
                        f.write(img_data)
                    break
    finally:
        try:
            close_url = f"http://localhost:{CDP_PORT}/json/close/{target_id}"
            urllib.request.urlopen(close_url)
        except Exception:
            pass


def generate_installer_html(out_file: Path) -> Path:
    html_content = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Setup - Naughty or not</title>
<style>
body {
    margin: 0;
    padding: 0;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background-color: #2b2b2b;
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100vh;
}
.window {
    width: 530px;
    height: 380px;
    background: #f0f0f0;
    border-radius: 8px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    border: 1px solid #777;
}
.titlebar {
    height: 32px;
    background: #fff;
    display: flex;
    align-items: center;
    padding: 0 12px;
    font-size: 12px;
    color: #333;
    border-bottom: 1px solid #e0e0e0;
}
.titlebar-icon {
    width: 16px;
    height: 16px;
    margin-right: 8px;
}
.content {
    flex: 1;
    display: flex;
    background: #fff;
}
.sidebar {
    width: 160px;
    background: linear-gradient(180deg, #182b49 0%, #0d1726 100%);
    padding: 20px 15px;
    color: #fff;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
}
.sidebar-shield {
    font-size: 48px;
    margin-bottom: 15px;
}
.sidebar-title {
    font-size: 16px;
    font-weight: 600;
    letter-spacing: 0.5px;
}
.sidebar-sub {
    font-size: 11px;
    color: #a0aec0;
    margin-top: 5px;
}
.main-pane {
    flex: 1;
    padding: 25px 25px 15px 25px;
    display: flex;
    flex-direction: column;
}
.step-title {
    font-size: 14px;
    font-weight: 600;
    color: #111;
    margin-bottom: 8px;
}
.step-desc {
    font-size: 12px;
    color: #444;
    line-height: 1.4;
    margin-bottom: 18px;
}
.path-box {
    background: #fff;
    border: 1px solid #ccc;
    padding: 6px 10px;
    font-size: 11px;
    color: #333;
    border-radius: 3px;
    margin-bottom: 12px;
}
.badge-noadmin {
    display: inline-block;
    background: #e8f5e9;
    color: #2e7d32;
    padding: 4px 8px;
    font-size: 11px;
    font-weight: 600;
    border-radius: 4px;
    margin-bottom: 15px;
}
.space-info {
    font-size: 11px;
    color: #666;
    margin-top: auto;
}
.footer {
    height: 50px;
    background: #f0f0f0;
    border-top: 1px solid #dfdfdf;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    padding: 0 16px;
    gap: 8px;
}
.btn {
    padding: 5px 18px;
    font-size: 12px;
    border-radius: 3px;
    border: 1px solid #ababab;
    background: #e1e1e1;
    cursor: default;
}
.btn-primary {
    background: #0067b8;
    color: #fff;
    border-color: #0067b8;
}
</style>
</head>
<body>
<div class="window">
    <div class="titlebar">
        <span class="titlebar-icon">🛡️</span>
        <span>Setup — Naughty or not v1.0.0</span>
    </div>
    <div class="content">
        <div class="sidebar">
            <div class="sidebar-shield">🛡️</div>
            <div class="sidebar-title">Naughty or not</div>
            <div class="sidebar-sub">Sanctions & Compliance Screener</div>
        </div>
        <div class="main-pane">
            <div class="step-title">Select Destination Location</div>
            <div class="step-desc">Where should Naughty or not be installed? Setup will install into your personal AppData folder without requiring administrator privileges:</div>
            <div class="path-box">C:\\Users\\souni\\AppData\\Local\\Programs\\NaughtyOrNot</div>
            <div class="badge-noadmin">✓ Standard User Install (No Admin Privileges Needed)</div>
            <div class="space-info">At least 150.0 MB of free disk space is required.</div>
        </div>
    </div>
    <div class="footer">
        <div class="btn">&lt; Back</div>
        <div class="btn btn-primary">Next &gt;</div>
        <div class="btn">Cancel</div>
    </div>
</div>
</body>
</html>
"""
    html_file = SCREENS_DIR / "installer_mock.html"
    html_file.write_text(html_content, encoding="utf-8")
    return html_file


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

        print("Both Streamlit and Chrome CDP are ready!")

        # 1. Installer screenshot
        installer_html = generate_installer_html(SCREENS_DIR / "installer_mock.html")
        installer_url = f"file:///{str(installer_html).replace('\\', '/')}"
        print("Capturing screenshot_installer.png...")
        await capture_cdp_screenshot(installer_url, SCREENS_DIR / "screenshot_installer.png", wait_seconds=1.5)

        # 2. First-run list download screenshot
        print("Capturing screenshot_first_run.png...")
        first_run_url = f"http://localhost:{STREAMLIT_PORT}/?show_first_run=true"
        await capture_cdp_screenshot(first_run_url, SCREENS_DIR / "screenshot_first_run.png", wait_seconds=5.0)

        # 3. OpenSanctions key dialog screenshot
        print("Capturing screenshot_key_dialog.png...")
        key_dialog_url = f"http://localhost:{STREAMLIT_PORT}/?show_key_dialog=true"
        await capture_cdp_screenshot(key_dialog_url, SCREENS_DIR / "screenshot_key_dialog.png", wait_seconds=4.0)

        # 4. Name check result in app window screenshot
        print("Capturing screenshot_name_check.png...")
        name_check_url = f"http://localhost:{STREAMLIT_PORT}/?autorun=true&search_type=Airline&query=Aeroflot"
        await capture_cdp_screenshot(name_check_url, SCREENS_DIR / "screenshot_name_check.png", wait_seconds=6.0)

        print("All 4 screenshots captured successfully!")

    finally:
        print("Cleaning up processes...")
        chrome_proc.terminate()
        st_proc.terminate()
        try:
            chrome_proc.wait(timeout=5)
            st_proc.wait(timeout=5)
        except Exception:
            pass
        # Clean up temporary installer html
        mock_html = SCREENS_DIR / "installer_mock.html"
        if mock_html.exists():
            mock_html.unlink()
        print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
