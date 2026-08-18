"""
SWAK Runtime — Main Entry Point
Handles all run modes:
  python swak_runtime.py              → tray app (default)
  python swak_runtime.py tray         → tray app
  python swak_runtime.py server       → Flask only (no tray)
  python swak_runtime.py service install/start/stop/remove
  python swak_runtime.py test         → run test suite
"""

import sys
import os
from pathlib import Path

# Add server dir to path
BASE_DIR = Path(__file__).parent.resolve()
SERVER_DIR = BASE_DIR / 'server'
sys.path.insert(0, str(SERVER_DIR))
sys.path.insert(0, str(BASE_DIR))


def load_env():
    env_path = SERVER_DIR / '.env'
    if not env_path.exists():
        env_path = BASE_DIR / '.env'
    if not env_path.exists():
        return
    with open(env_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main():
    load_env()

    mode = sys.argv[1].lower() if len(sys.argv) > 1 else 'tray'

    # ── Service mode (Windows only) ───────────────────────────────────
    if mode == 'service':
        try:
            from swak_service import main as svc_main
            # Pass remaining args to service handler
            sys.argv = [sys.argv[0]] + sys.argv[2:]
            svc_main()
        except ImportError:
            print('[SWAK] pywin32 not installed. Run: pip install pywin32')
            sys.exit(1)

    # ── Tray mode (default) ───────────────────────────────────────────
    elif mode == 'tray':
        from tray_app import run_tray
        run_tray()

    # ── Server only (no tray) ─────────────────────────────────────────
    elif mode == 'server':
        from server import app
        host = os.environ.get('SWAK_HOST', '127.0.0.1')
        port = int(os.environ.get('SWAK_PORT', '5000'))
        print(f'[SWAK] Starting server on http://{host}:{port}')
        app.run(host=host, port=port, debug=False, threaded=True)

    # ── Test mode ─────────────────────────────────────────────────────
    elif mode == 'test':
        from tests.test_suite import run_all_tests
        success = run_all_tests()
        sys.exit(0 if success else 1)

    else:
        print(f'Unknown mode: {mode}')
        print('Usage: swak_runtime.py [tray|server|service|test]')
        sys.exit(1)


if __name__ == '__main__':
    main()
