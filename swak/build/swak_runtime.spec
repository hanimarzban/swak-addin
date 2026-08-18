# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None

ROOT     = Path('.').resolve()
SERVER   = ROOT / 'server'
COMPILED = SERVER / 'compiled'

a = Analysis(
    [str(ROOT / 'swak_runtime.py')],
    pathex=[str(ROOT), str(SERVER)],
    binaries=[],
    datas=[
        (str(COMPILED / '*.pyd'), 'compiled'),
        (str(SERVER / '.env.template'), '.'),
    ],
    hiddenimports=[
        'flask', 'flask_cors', 'werkzeug', 'jinja2', 'click',
        'numpy', 'pandas', 'scipy',
        'sklearn', 'sklearn.utils._cython_blas',
        'sklearn.neighbors.typedefs',
        'sklearn.neighbors._partition_nodes',
        'sklearn.tree._utils',
        'openpyxl',
        'pystray', 'PIL', 'PIL.Image',
        'win32serviceutil', 'win32service', 'win32event',
        'servicemanager', 'socket',
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
    excludes=['tkinter', 'test', 'unittest'],
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
    console=False,
    uac_admin=True,
)
