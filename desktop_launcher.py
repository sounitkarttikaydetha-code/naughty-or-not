from modules.common.branding import APP_NAME, VERSION_LABEL, MAIN_TITLE
"""
Naughty or not — Single Desktop Launcher
Runs local Python screening engine in-process and opens native WebView2 window.
Fully self-contained, zero background services, dynamic port allocation, clean process lifecycle.
"""

import ctypes
import os
import signal
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

# Corporate SSL verification via Windows Certificate Store
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

MUTEX_NAME = "NaughtyOrNot_SingleInstance_Mutex"
APP_TITLE = f"{APP_NAME} {VERSION_LABEL} — {MAIN_TITLE}"


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def get_work_area_dimensions() -> tuple[int, int]:
    """Calculate 90% of screen work area, clamped between 1000x640 and 1500x950."""
    target_w, target_h = 1280, 850
    if sys.platform == "win32":
        try:
            rect = RECT()
            # SPI_GETWORKAREA = 0x0030
            if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
                work_w = rect.right - rect.left
                work_h = rect.bottom - rect.top
                target_w = max(1000, min(1500, int(work_w * 0.90)))
                target_h = max(640, min(950, int(work_h * 0.90)))
        except Exception:
            pass
    return target_w, target_h


def check_single_instance() -> bool:
    """Enforce single running instance. Brings existing window to front if duplicate."""
    if sys.platform != "win32":
        return True

    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32

    # Create named mutex
    mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    last_err = kernel32.GetLastError()
    if last_err == 183:  # ERROR_ALREADY_EXISTS
        # Find existing window by title and bring to foreground
        def enum_windows_cb(hwnd, _):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if APP_TITLE in buf.value or "Clearance Check" in buf.value or "Naughty or not" in buf.value:
                    user32.ShowWindowAsync(hwnd, 9)  # SW_RESTORE
                    user32.SetForegroundWindow(hwnd)
                    return False
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        user32.EnumWindows(WNDENUMPROC(enum_windows_cb), 0)
        return False
    return True


def check_webview2_installed() -> bool:
    """Verify that Microsoft Edge WebView2 runtime is present."""
    if sys.platform != "win32":
        return True

    import winreg
    subkeys = [
        r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
        r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
        r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-9447-4EC8-857B-9E3E00E4630B}",
        r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-9447-4EC8-857B-9E3E00E4630B}",
    ]
    for key_path in subkeys:
        for root in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
            try:
                with winreg.OpenKey(root, key_path) as k:
                    val, _ = winreg.QueryValueEx(k, "pv")
                    if val and str(val).strip():
                        return True
            except Exception:
                pass

    # Also check if Edge executable directory exists
    edge_paths = [
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft" / "EdgeWebView" / "Application",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft" / "Edge" / "Application",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft" / "Edge" / "Application",
    ]
    for ep in edge_paths:
        if ep.is_dir():
            return True

    return False


def show_webview2_missing_dialog() -> None:
    """Display plain error message with WebView2 download link."""
    msg = (
        f"Microsoft Edge WebView2 Runtime is required to run {APP_NAME}.\n\n"
        "Please download and install Evergreen WebView2 Runtime from:\n"
        "https://developer.microsoft.com/en-us/microsoft-edge/webview2/\n\n"
        "Contact IT support if you do not have permission to install it."
    )
    if sys.platform == "win32":
        ctypes.windll.user32.MessageBoxW(0, msg, f"{APP_NAME} — WebView2 Required", 0x10)
    else:
        print(msg)


def find_free_port() -> int:
    """Find dynamic free port on 127.0.0.1."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get_project_root() -> Path:
    """Get project base directory whether running from script or PyInstaller."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent


def shutdown_cleanly():
    """Flush and close SQLite log, raw index, and stop Streamlit cleanly before exit."""
    try:
        from modules.reporting.logger import DB_PATH
        if DB_PATH.exists():
            import sqlite3
            with sqlite3.connect(str(DB_PATH)) as con:
                con.execute("PRAGMA wal_checkpoint(FULL);")
    except Exception:
        pass

    try:
        from modules.common.paths import INDEX_DB_PATH
        if INDEX_DB_PATH.exists():
            import sqlite3
            with sqlite3.connect(str(INDEX_DB_PATH)) as con:
                con.execute("PRAGMA wal_checkpoint(FULL);")
    except Exception:
        pass

    try:
        from streamlit.web.server.server import Server
        server = Server.get_current()
        if server:
            server.stop()
    except Exception:
        pass


def main():
    # 0. Set per-monitor DPI awareness (Windows)
    if sys.platform == "win32":
        try:
            # 2 = PROCESS_PER_MONITOR_DPI_AWARE
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    # 1. Single instance check
    if not check_single_instance():
        sys.exit(0)

    # 2. Check WebView2
    if not check_webview2_installed():
        show_webview2_missing_dialog()
        sys.exit(1)

    # 3. Environment configuration
    root = get_project_root()
    os.environ["ENGINE"] = "python"
    os.environ["NAUGHTY_DESKTOP_MODE"] = "1"

    # Portable mode check: if .portable or portable.dat exists in application directory
    if (root / ".portable").exists() or (root / "portable.dat").exists():
        app_data = root / "data"
    else:
        local_app = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        app_data = Path(local_app) / "NaughtyOrNot"
    app_data.mkdir(parents=True, exist_ok=True)
    os.environ["NAUGHTY_DATA_DIR"] = str(app_data)

    # Populate seed lists on first run if needed
    try:
        from modules.common.list_updater import init_lists_from_seed
        init_lists_from_seed()
    except Exception as e:
        print(f"Notice: Seed init: {e}")

    # Warm up screening engine in background daemon thread (T8-3)
    try:
        from modules.watchman.client import get_python_engine
        import threading
        threading.Thread(target=get_python_engine, daemon=True, name="EngineWarmupThread").start()
    except Exception as e:
        print(f"Notice: Background engine warm-up: {e}")

    # 4. Patch signal.signal for in-process daemon thread
    orig_signal = signal.signal
    def safe_signal(sig, handler):
        try:
            return orig_signal(sig, handler)
        except ValueError:
            return None
    signal.signal = safe_signal

    # 5. Dynamic port allocation & Streamlit configuration
    port = find_free_port()
    import streamlit.config as st_config
    import streamlit.web.bootstrap as bootstrap

    st_config.set_option("server.port", port)
    st_config.set_option("server.address", "127.0.0.1")
    st_config.set_option("server.headless", True)
    st_config.set_option("global.developmentMode", False)
    st_config.set_option("browser.gatherUsageStats", False)
    st_config.set_option("server.enableCORS", False)
    st_config.set_option("server.enableXsrfProtection", False)
    st_config.set_option("client.toolbarMode", "viewer")
    try:
        st_config.set_option("client.showDeployButton", False)
    except Exception:
        pass
    try:
        st_config.set_option("theme.base", "light")
        st_config.set_option("theme.primaryColor", "#0F52BA")
        st_config.set_option("theme.backgroundColor", "#F8FAFC")
        st_config.set_option("theme.secondaryBackgroundColor", "#FFFFFF")
        st_config.set_option("theme.textColor", "#0F172A")
    except Exception:
        pass

    app_py_path = str(root / "app.py")
    server_thread = threading.Thread(
        target=lambda: bootstrap.run(app_py_path, is_hello=False, args=[], flag_options={}),
        daemon=True,
    )
    server_thread.start()

    # 6. Wait for server to be responsive
    health_url = f"http://127.0.0.1:{port}/_stcore/health"
    ready = False
    for _ in range(30):
        time.sleep(0.3)
        try:
            with urllib.request.urlopen(health_url, timeout=1) as resp:
                if resp.status == 200:
                    ready = True
                    break
        except Exception:
            pass

    if not ready:
        print("Error: In-process server failed to start within timeout.")
        sys.exit(1)

    # 7. Open pywebview Window
    import webview

    icon_path = root / "assets" / "icon.ico"
    icon_str = str(icon_path) if icon_path.is_file() else None

    from modules.common.settings import get_setting, set_setting

    saved_win = get_setting("window") or {}
    def_w, def_h = get_work_area_dimensions()
    init_w = saved_win.get("width") or def_w
    init_h = saved_win.get("height") or def_h
    init_w = max(1000, min(1920, int(init_w)))
    init_h = max(640, min(1200, int(init_h)))
    init_x = saved_win.get("x")
    init_y = saved_win.get("y")

    window = webview.create_window(
        title=APP_TITLE,
        url=f"http://127.0.0.1:{port}",
        width=init_w,
        height=init_h,
        x=init_x,
        y=init_y,
        min_size=(1000, 640),
        text_select=True,
        zoomable=True,
    )

    def on_closed():
        # Remember window size and position in settings.json
        try:
            set_setting("window", {
                "width": window.width,
                "height": window.height,
                "x": window.x,
                "y": window.y,
            })
        except Exception:
            pass

        # Clean process shutdown — flush databases and stop server
        shutdown_cleanly()

        # Stop periodic source refresh worker
        try:
            from modules.common.source_manager import stop_periodic_source_refresh_worker
            stop_periodic_source_refresh_worker()
        except Exception:
            pass

        # Watchdog: wait up to 5s before force-killing if process remains hung
        def watchdog_force_kill():
            time.sleep(5.0)
            if sys.platform == "win32":
                try:
                    import subprocess
                    subprocess.run(
                        f"taskkill /F /T /PID {os.getpid()}",
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except Exception:
                    pass
            os._exit(0)

        threading.Thread(target=watchdog_force_kill, daemon=True, name="ShutdownWatchdog").start()
        sys.exit(0)

    window.events.closed += on_closed
    webview.start(gui="edgechromium", icon=icon_str)

    # Guarantee clean exit on window close
    shutdown_cleanly()
    os._exit(0)


if __name__ == "__main__":
    main()
