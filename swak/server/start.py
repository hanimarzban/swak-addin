"""
SWAK — Server Startup Script
Run this to start the backend:
    python start.py

Or as .exe (PyInstaller):
    swak_server.exe
"""

import os
import sys
from pathlib import Path

def load_env():
    """Load .env file if present"""
    env_path = Path(__file__).parent / '.env'
    if not env_path.exists():
        tmpl = Path(__file__).parent / '.env.template'
        print(f"[SWAK] .env not found. Copy .env.template → .env and fill in your keys.")
        if tmpl.exists():
            print(f"[SWAK] Template: {tmpl}")
        return

    with open(env_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, val = line.partition('=')
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)

    print("[SWAK] .env loaded")

def check_deps():
    """Check required packages are installed"""
    required = ['flask', 'flask_cors']
    missing  = []
    for pkg in required:
        try:
            __import__(pkg.replace('-', '_'))
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"[SWAK] Missing packages: {', '.join(missing)}")
        print(f"[SWAK] Run: pip install -r requirements.txt")
        sys.exit(1)

def main():
    load_env()
    check_deps()

    host = os.environ.get('SWAK_HOST', '127.0.0.1')
    port = int(os.environ.get('SWAK_PORT', '5000'))

    print("=" * 52)
    print("  SWAK Backend Server v2.0.0")
    print(f"  Running on http://{host}:{port}")
    print("  Press Ctrl+C to stop")
    print("=" * 52)

    # Import and run Flask app
    from server import app
    app.run(host=host, port=port, debug=False, threaded=True)

if __name__ == '__main__':
    main()
