"""
Capture baseline before/after screenshots for T9-1 Display Fit verification.
Uses Playwright to capture UI at required viewports (1024x640, 1280x720, 1366x768, 1600x900, 1920x1080)
and device scalings (1.0, 1.25, 1.5).
"""

import os
import sys
import time
import socket
import threading
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright

def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def start_streamlit_server(port: int):
    cmd = [
        sys.executable, "-m", "streamlit", "run", "app.py",
        "--server.port", str(port),
        "--server.address", "127.0.0.1",
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
        "--global.developmentMode", "false",
    ]
    env = os.environ.copy()
    env["ENGINE"] = "python"
    env["NAUGHTY_DESKTOP_MODE"] = "1"
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return proc

def wait_for_server(port: int, timeout: float = 25.0) -> bool:
    import urllib.request
    url = f"http://127.0.0.1:{port}/_stcore/health"
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.4)
    return False

def capture_screens(stage: str = "before"):
    out_dir = Path("reviews/screens") / stage
    out_dir.mkdir(parents=True, exist_ok=True)
    
    port = find_free_port()
    print(f"Starting Streamlit server on port {port}...")
    proc = start_streamlit_server(port)
    
    try:
        if not wait_for_server(port):
            raise RuntimeError("Streamlit server failed to start within timeout.")
        print(f"Server ready at http://127.0.0.1:{port}")
        
        viewports = [
            (1024, 640),
            (1280, 720),
            (1366, 768),
            (1600, 900),
            (1920, 1080),
        ]
        scalings = [1.0, 1.25, 1.5]
        
        scenarios = [
            ("name_check_mixed", f"http://127.0.0.1:{port}/?autorun=true&search_type=Organisation&q=Siberian+Airlines&expand_info=true"),
            ("airline_sections_abc", f"http://127.0.0.1:{port}/?autorun=true&search_type=Airline&q=Aeroflot&country=Russia"),
            ("text_search", f"http://127.0.0.1:{port}/?tab=raw&raw_query=Aeroflot&raw_autorun=true"),
            ("manual_check", f"http://127.0.0.1:{port}/?tab=manual"),
        ]
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            
            # Representative matrix of sizes and scalings
            for w, h in viewports:
                for scale in scalings:
                    # Capture full scenarios on representative combinations
                    scale_str = f"scale_{int(scale*100)}"
                    ctx = browser.new_context(
                        viewport={"width": w, "height": h},
                        device_scale_factor=scale,
                    )
                    page = ctx.new_page()
                    
                    for scen_name, url in scenarios:
                        try:
                            page.goto(url, wait_until="networkidle", timeout=20000)
                            # Wait for Streamlit rendering to settle
                            page.wait_for_timeout(2000)
                            
                            # Check horizontal overflow
                            overflow_info = page.evaluate("""() => {
                                const doc = document.documentElement;
                                return {
                                    scrollWidth: doc.scrollWidth,
                                    clientWidth: doc.clientWidth,
                                    hasHorizontalOverflow: doc.scrollWidth > doc.clientWidth + 1
                                };
                            }""")
                            
                            fname = f"{scen_name}_{w}x{h}_{scale_str}.png"
                            page.screenshot(path=str(out_dir / fname), full_page=False)
                            print(f"Captured {fname} | overflow={overflow_info['hasHorizontalOverflow']} ({overflow_info['scrollWidth']} vs {overflow_info['clientWidth']})")
                        except Exception as e:
                            print(f"Error capturing {scen_name} at {w}x{h}@{scale}: {e}")
                    
                    ctx.close()
            
            browser.close()
            
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        print("Streamlit server stopped.")

if __name__ == "__main__":
    stage_arg = sys.argv[1] if len(sys.argv) > 1 else "before"
    capture_screens(stage_arg)
