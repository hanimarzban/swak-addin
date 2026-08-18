# build.py — Compile Python modules to Cython binaries
"""
SWAK — Cython Build Script
Compiles all server/modules/*.py files to native C extensions
Output: server/compiled/*.pyd (Windows) or *.so (Mac/Linux)

Usage:
  python build.py           — compile all modules
  python build.py clean     — compile clean.py only
  python build.py --clean   — remove compiled files
"""

import sys
import os
import shutil
import subprocess
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────

MODULES_DIR  = Path('server/modules')
COMPILED_DIR = Path('server/compiled')
BUILD_TEMP   = Path('build_temp')

# Modules to compile (order matters for dependencies)
MODULES = [
    'clean',
    'filter',
    'transform',
    'stats',
    'ml',
    'viz',
    'ai',
    'import_tools',
    'export_tools',
    'profiling',
    'dataeng',
    'productivity',
    'license',
]

# ── Helpers ───────────────────────────────────────────────────────────────

def check_cython():
    try:
        import Cython
        print(f'[OK] Cython {Cython.__version__} found')
        return True
    except ImportError:
        print('[ERROR] Cython not installed. Run: pip install cython')
        return False

def check_compiler():
    """Check if C compiler is available"""
    import distutils.core
    try:
        if sys.platform == 'win32':
            # Check for MSVC or MinGW
            result = subprocess.run(['cl'], capture_output=True)
            print('[OK] MSVC compiler found')
        else:
            result = subprocess.run(['gcc', '--version'], capture_output=True)
            print('[OK] GCC compiler found')
        return True
    except FileNotFoundError:
        print('[WARN] No C compiler found — install Visual Studio Build Tools (Windows) or GCC (Mac/Linux)')
        return False

def write_setup_py(module_name, source_path):
    """Generate a setup.py for a single module"""
    setup_content = f"""
from setuptools import setup
from Cython.Build import cythonize
import numpy

setup(
    ext_modules=cythonize(
        '{source_path}',
        compiler_directives={{
            'language_level': '3',
            'boundscheck': False,
            'wraparound': False,
            'cdivision': True,
            'nonecheck': False,
        }},
        annotate=False,   # don't produce .html annotation files
    ),
    include_dirs=[numpy.get_include()],
)
"""
    setup_file = BUILD_TEMP / f'setup_{module_name}.py'
    setup_file.write_text(setup_content)
    return setup_file

def compile_module(module_name):
    """Compile a single module to .pyd/.so"""
    src = MODULES_DIR / f'{module_name}.py'
    if not src.exists():
        print(f'[SKIP] {module_name}.py not found')
        return False

    print(f'[BUILD] Compiling {module_name}...')

    # Copy source to temp
    tmp_src = BUILD_TEMP / f'{module_name}_c.py'
    shutil.copy(src, tmp_src)

    # Add Cython header comment
    content = tmp_src.read_text(encoding='utf-8')
    if not content.startswith('# cython:'):
        content = '# cython: language_level=3\n# cython: boundscheck=False\n# cython: wraparound=False\n' + content
        tmp_src.write_text(content, encoding='utf-8')

    # Write setup.py
    setup_file = write_setup_py(module_name, str(tmp_src))

    # Run build
    result = subprocess.run(
        [sys.executable, str(setup_file), 'build_ext', '--inplace'],
        capture_output=True,
        text=True,
        cwd=str(BUILD_TEMP)
    )

    if result.returncode != 0:
        print(f'[ERROR] {module_name}: {result.stderr[-500:]}')
        return False

    # Find output .pyd/.so and move to compiled/
    ext = '.pyd' if sys.platform == 'win32' else '.so'
    built = list(BUILD_TEMP.glob(f'*{module_name}_c*{ext}'))
    if not built:
        print(f'[ERROR] {module_name}: compiled file not found')
        return False

    dest = COMPILED_DIR / built[0].name
    shutil.move(str(built[0]), str(dest))
    print(f'[OK] {module_name} → {dest.name}')
    return True

def clean_compiled():
    """Remove all compiled files"""
    if COMPILED_DIR.exists():
        for f in COMPILED_DIR.iterdir():
            if f.suffix in ('.pyd', '.so', '.c'):
                f.unlink()
                print(f'[DEL] {f.name}')
    if BUILD_TEMP.exists():
        shutil.rmtree(BUILD_TEMP)
        print('[DEL] build_temp/')
    print('[DONE] Cleaned')

def write_compiled_init():
    """Write __init__.py for compiled package"""
    init = COMPILED_DIR / '__init__.py'
    init.write_text('# SWAK compiled modules — auto-generated\n')

# ── Main ──────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if '--clean' in args:
        clean_compiled()
        return

    # Determine which modules to build
    target_modules = [a for a in args if not a.startswith('-')] or MODULES

    print('=' * 50)
    print('  SWAK — Cython Build')
    print(f'  Platform: {sys.platform}')
    print(f'  Python: {sys.version.split()[0]}')
    print('=' * 50)

    if not check_cython():
        sys.exit(1)

    has_compiler = check_compiler()
    if not has_compiler:
        print('\n[WARN] Proceeding without compiler check...')

    # Create dirs
    COMPILED_DIR.mkdir(parents=True, exist_ok=True)
    BUILD_TEMP.mkdir(parents=True, exist_ok=True)
    write_compiled_init()

    # Compile
    ok, fail = 0, 0
    for mod in target_modules:
        if compile_module(mod):
            ok += 1
        else:
            fail += 1

    # Cleanup temp
    if BUILD_TEMP.exists():
        shutil.rmtree(BUILD_TEMP)

    print('=' * 50)
    print(f'  Done: {ok} compiled, {fail} failed')
    print('=' * 50)

    if fail > 0:
        sys.exit(1)

if __name__ == '__main__':
    main()
