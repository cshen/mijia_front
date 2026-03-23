"""
macOS app entry point.

Starts the uvicorn server in a background thread, waits until it is
accepting connections, then opens the dashboard in the default browser.
The main thread blocks so the process stays alive until the user quits
the app (Cmd+Q or via the menu-bar icon if rumps is present).
"""
from __future__ import annotations

import os
import sys
import socket
import threading
import time
import webbrowser

# ── Resolve bundle / dev paths ─────────────────────────────────────────────────
# When frozen by PyInstaller, sys._MEIPASS points to the temp directory where
# bundled data files are extracted.  In development, just use the script dir.
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS  # type: ignore[attr-defined]
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

os.chdir(BASE_DIR)          # make relative paths in main.py resolve correctly

# ── Constants ──────────────────────────────────────────────────────────────────
HOST = "127.0.0.1"
PORT = 8765
URL  = f"http://{HOST}:{PORT}"


# ── Server thread ──────────────────────────────────────────────────────────────
def _run_server() -> None:
    import uvicorn
    from main import app  # direct import so PyInstaller bundles all of main's deps
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        reload=False,       # reload must be off inside a bundle
        log_level="warning",
    )


def _wait_for_server(timeout: float = 15.0) -> bool:
    """Return True once the server is accepting TCP connections."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((HOST, PORT), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    thread = threading.Thread(target=_run_server, daemon=True)
    thread.start()

    if _wait_for_server():
        webbrowser.open(URL)
    else:
        # Server didn't start in time — open anyway and let the browser retry
        webbrowser.open(URL)

    # Try to show a rumps menu-bar icon; fall back to blocking forever.
    try:
        import rumps  # type: ignore
        app = rumps.App("Mijia IoT", quit_button="Quit Mijia IoT")
        app.run()
    except ImportError:
        # No rumps — just keep the process alive so the server keeps running.
        thread.join()


if __name__ == "__main__":
    main()
