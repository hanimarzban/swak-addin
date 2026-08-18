# -*- mode: python ; coding: utf-8 -*-
"""
SWAK — PyInstaller spec file
Entry: swak_runtime.py (tray + service + server)
Build: pyinstaller build/swak_runtime.spec  (از پوشه swak/)
Output: dist/swak_runtime/swak_runtime.exe
"""

import sys
from pathlib import Path

block_cipher = None

# ── Paths ──────────────────────────────────────────────────────────────────
# این spec از پوشه swak/ اجرا میشه
ROOT = Path('.').resolve()        # swak/
SERVER = ROOT / 'server'
COMPILED = SERVER / 'compiled'

# ── Analysis ───────────────────────────────────────────────────────────────
a = Analysis(
    [str(ROOT / 'swak_runtime.py')],
    pathex=[str(ROOT), str(SERVER)],
    binaries=[],
    datas=[
        # Compiled Cython modules
        (str(COMPILED / '*.pyd'), 'compiled'),    # Windows
        (str(COMPILED / '*.so'),  'compiled'),    # Linux/Mac (fallback)
        # .env template
        (str(SERVER / '.env.template'), '.'),
    ],
    hiddenimports=[
        # Flask
        'flask', 'flask_cors', 'werkzeug', 'jinja2', 'click',
        # Data
        'numpy', 'pandas', 'scipy',
        'sklearn', 'sklearn.utils._cython_blas',
        'sklearn.neighbors.typedefs',
        'sklearn.neighbors._partition_nodes',
        'sklearn.tree._utils',
        'openpyxl',
        # Tray
        'pystray', 'PIL', 'PIL.Image',
        # Windows Service
        'win32serviceutil', 'win32service', 'win32event',
        'servicemanager', 'socket',
        # SWAK modules (compiled)
        'compiled.clean_c',
        'compiled.filter_c',
        'compiled.transform_c',
        'compiled.stats_c',
        'compiled.ml_c',
        'compiled.viz_c',
        'compiled.ai_c',
        'compiled.import_tools_c',
        'compiled.export_tools_c',
        'compiled.profiling_c',
        'compiled.dataeng_c',
        'compiled.productivity_c',
        'compiled.license_c',
        # SWAK server modules (Python fallback if compiled not found)
        'server.server',
        'server.modules.clean',
        'server.modules.filter',
        'server.modules.transform',
        'server.modules.stats',
        'server.modules.ml',
        'server.modules.viz',
        'server.modules.ai',
        'server.modules.import_tools',
        'server.modules.export_tools',
        'server.modules.profiling',
        'server.modules.dataeng',
        'server.modules.productivity',
        'server.modules.license',
        'swak_service',
        'tray_app',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'test', 'unittest', 'email', 'http.server'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='swak_runtime',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=['vcruntime140.dll', 'ucrtbase.dll'],
    runtime_tmpdir=None,
    console=False,   # بدون پنجره cmd (tray app)
    icon=None,       # اگر swak_icon.ico داری، اینجا بذار: 'assets/swak_icon.ico'
    version=None,
    uac_admin=True,  # درخواست admin برای نصب service
)
