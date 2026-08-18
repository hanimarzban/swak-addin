"""
SWAK Runtime — System Tray Application
Shows SWAK status in Windows/Mac system tray.
Users can start/stop/restart the service from here.

Requires: pip install pystray pillow
"""

import os
import sys
import time
import threading
import subprocess
import webbrowser
import urllib.request
from pathlib import Path

try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False


# ── Config ────────────────────────────────────────────────────────────────
HEALTH_URL   = 'http://127.0.0.1:5000/health'
CHECK_EVERY  = 5   # seconds
APP_NAME     = 'SWAK Data Tools Runtime'
VERSION      = '2.0.0'
WEBSITE_URL  = 'https://swaksoft.com'


# ── Status ────────────────────────────────────────────────────────────────
class RuntimeStatus:
    def __init__(self):
        self.running  = False
        self.pid      = None
        self.lock     = threading.Lock()

status = RuntimeStatus()


# ── Health check ──────────────────────────────────────────────────────────
def check_health():
    try:
        r = urllib.request.urlopen(HEALTH_URL, timeout=2)
        return r.status == 200
    except Exception:
        return False


# ── Icon builder ──────────────────────────────────────────────────────────
def make_icon(running: bool) -> Image.Image:
    """Generate tray icon — green S (running) or red S (stopped)"""
    size   = 64
    img    = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw   = ImageDraw.Draw(img)
    color  = (74, 222, 128, 255) if running else (248, 113, 113, 255)

    # Circle background
    draw.ellipse([2, 2, size-2, size-2], fill=color)

    # "S" letter
    try:
        font = ImageFont.truetype('arial.ttf', 36)
    except Exception:
        font = ImageFont.load_default()

    draw.text((size//2, size//2), 'S', fill=(13, 17, 23, 255),
              font=font, anchor='mm')
    return img


# ── Flask process manager ─────────────────────────────────────────────────
_flask_proc = None

def start_server():
    global _flask_proc
    if _flask_proc and _flask_proc.poll() is None:
        return  # already running

    server_py = Path(__file__).parent / 'start.py'
    _flask_proc = subprocess.Popen(
        [sys.executable, str(server_py)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(Path(__file__).parent),
    )

def stop_server():
    global _flask_proc
    if _flask_proc:
        _flask_proc.terminate()
        try:
            _flask_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _flask_proc.kill()
        _flask_proc = None


# ── Tray application ──────────────────────────────────────────────────────
def build_menu(icon):
    """Build context menu based on current status"""
    is_running = status.running

    def on_start(icon, item):
        start_server()

    def on_stop(icon, item):
        stop_server()

    def on_restart(icon, item):
        stop_server()
        time.sleep(1)
        start_server()

    def on_website(icon, item):
        webbrowser.open(WEBSITE_URL)

    def on_quit(icon, item):
        stop_server()
        icon.stop()

    status_text = f'● Running (port 5000)' if is_running else '○ Stopped'

    return pystray.Menu(
        pystray.MenuItem(f'{APP_NAME} v{VERSION}', None, enabled=False),
        pystray.MenuItem(status_text, None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            'Start Runtime',
            on_start,
            enabled=not is_running
        ),
        pystray.MenuItem(
            'Stop Runtime',
            on_stop,
            enabled=is_running
        ),
        pystray.MenuItem(
            'Restart Runtime',
            on_restart,
            enabled=is_running
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Open Website', on_website),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Quit SWAK Runtime', on_quit),
    )


def monitor_loop(icon):
    """Background thread — check health every N seconds, update icon"""
    start_server()  # auto-start on launch

    while True:
        alive = check_health()
        with status.lock:
            status.running = alive

        # Update icon and tooltip
        icon.icon   = make_icon(alive)
        icon.title  = (
            f'{APP_NAME} — Running'
            if alive
            else f'{APP_NAME} — Stopped'
        )
        icon.menu = build_menu(icon)

        # Notify on state change (optional — can be removed)
        # icon.notify('...') # pystray notification

        time.sleep(CHECK_EVERY)


def run_tray():
    if not HAS_TRAY:
        print('[SWAK Tray] pystray/Pillow not installed.')
        print('            Run: pip install pystray pillow')
        print('            Falling back to headless mode...')
        # Headless: just run Flask directly
        from start import main as run_main
        run_main()
        return

    icon = pystray.Icon(
        name   = 'swak_runtime',
        icon   = make_icon(False),
        title  = f'{APP_NAME} — Starting...',
        menu   = pystray.Menu(),
    )

    # Start monitor in background
    t = threading.Thread(target=monitor_loop, args=(icon,), daemon=True)
    t.start()

    # Run tray (blocking)
    icon.run()


if __name__ == '__main__':
    run_tray()
