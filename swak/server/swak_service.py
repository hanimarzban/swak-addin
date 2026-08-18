"""
SWAK Runtime — Windows Service
Runs Flask backend as a Windows Service that auto-starts with Windows.

Install:   python swak_service.py install
Start:     python swak_service.py start
Stop:      python swak_service.py stop
Remove:    python swak_service.py remove
Debug:     python swak_service.py debug
"""

import sys
import os
import time
import threading
import subprocess
from pathlib import Path

# ── Windows Service (pywin32) ─────────────────────────────────────────────
try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

# ── Load .env ─────────────────────────────────────────────────────────────
def load_env():
    env_path = Path(__file__).parent / '.env'
    if not env_path.exists():
        return
    with open(env_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# ── Flask runner (thread) ─────────────────────────────────────────────────
def run_flask():
    load_env()
    # Import here so env is loaded first
    from server import app
    host = os.environ.get('SWAK_HOST', '127.0.0.1')
    port = int(os.environ.get('SWAK_PORT', '5000'))
    app.run(host=host, port=port, debug=False, threaded=True, use_reloader=False)


if HAS_WIN32:
    class SWAKService(win32serviceutil.ServiceFramework):
        _svc_name_         = 'SWAKRuntime'
        _svc_display_name_ = 'SWAK Data Tools Runtime'
        _svc_description_  = (
            'SWAK Data Tools local processing engine. '
            'Required for SWAK Excel Add-in to function. '
            'Runs on 127.0.0.1:5000 — no external network access.'
        )

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self._stop_event  = win32event.CreateEvent(None, 0, 0, None)
            self._flask_thread = None

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self._stop_event)
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STOPPED,
                (self._svc_name_, '')
            )

        def SvcDoRun(self):
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, '')
            )
            # Start Flask in background thread
            self._flask_thread = threading.Thread(
                target=run_flask, daemon=True
            )
            self._flask_thread.start()

            # Wait for stop signal
            win32event.WaitForSingleObject(
                self._stop_event, win32event.INFINITE
            )


def main():
    if not HAS_WIN32:
        print('[SWAK] pywin32 not installed.')
        print('       Run: pip install pywin32')
        print('       Then: python swak_service.py install')
        sys.exit(1)

    if len(sys.argv) == 1:
        # No args — run as service
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(SWAKService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(SWAKService)


if __name__ == '__main__':
    main()
