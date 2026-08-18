"""
SWAK — Local Python Backend Server
Flask HTTP server on 127.0.0.1:5000
Calls Cython-compiled modules for secure processing

Run: python server.py
     (or packaged as .exe via PyInstaller)
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import sys
import os

app = Flask(__name__)

# Only allow connections from localhost (Excel Add-in)
CORS(app, origins=['https://localhost', 'null', 'file://'])

# ── Import compiled modules ───────────────────────────────────────────────
# These are .pyd (Windows) or .so (Mac/Linux) files compiled from Cython
# If compiled version not found, fall back to .py source

def _import_module(name):
    try:
        import importlib
        return importlib.import_module(f'compiled.{name}_c')
    except ImportError:
        return importlib.import_module(f'modules.{name}')

try:
    clean_mod      = _import_module('clean')
    filter_mod     = _import_module('filter')
    transform_mod  = _import_module('transform')
    stats_mod      = _import_module('stats')
    ml_mod         = _import_module('ml')
    viz_mod        = _import_module('viz')
    ai_mod         = _import_module('ai')
    import_mod     = _import_module('import_tools')
    export_mod     = _import_module('export_tools')
    profiling_mod  = _import_module('profiling')
    dataeng_mod    = _import_module('dataeng')
    productivity_mod = _import_module('productivity')
    license_mod    = _import_module('license')
except Exception as e:
    print(f"[SWAK] Module import error: {e}")
    sys.exit(1)


# ── Health check ─────────────────────────────────────────────────────────

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'version': '2.0.0'})


# ── Generic tool runner ───────────────────────────────────────────────────

def run_tool(module, req):
    data = req.get_json(force=True)
    tool_id     = data.get('tool_id')
    params      = data.get('params', {})
    headers     = data.get('headers', [])
    rows        = data.get('rows', [])
    license_key = data.get('license_key')

    if not tool_id:
        return jsonify({'error': 'tool_id الزامی است'}), 400

    # Validate license for non-free tools
    # (license_mod.validate returns True/False)
    # Free tools bypass license check
    # TODO: wire up free tool list from manifest

    try:
        result = module.run(tool_id, params, headers, rows)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'خطای داخلی: {str(e)}'}), 500


# ── Routes ────────────────────────────────────────────────────────────────

@app.route('/api/clean',        methods=['POST'])
def route_clean():        return run_tool(clean_mod, request)

@app.route('/api/filter',       methods=['POST'])
def route_filter():       return run_tool(filter_mod, request)

@app.route('/api/transform',    methods=['POST'])
def route_transform():    return run_tool(transform_mod, request)

@app.route('/api/stats',        methods=['POST'])
def route_stats():        return run_tool(stats_mod, request)

@app.route('/api/ml',           methods=['POST'])
def route_ml():           return run_tool(ml_mod, request)

@app.route('/api/viz',          methods=['POST'])
def route_viz():          return run_tool(viz_mod, request)

@app.route('/api/ai',           methods=['POST'])
def route_ai():           return run_tool(ai_mod, request)

@app.route('/api/import',       methods=['POST'])
def route_import():       return run_tool(import_mod, request)

@app.route('/api/export',       methods=['POST'])
def route_export():       return run_tool(export_mod, request)

@app.route('/api/profiling',    methods=['POST'])
def route_profiling():    return run_tool(profiling_mod, request)

@app.route('/api/dataeng',      methods=['POST'])
def route_dataeng():      return run_tool(dataeng_mod, request)

@app.route('/api/productivity', methods=['POST'])
def route_productivity(): return run_tool(productivity_mod, request)


# ── License endpoints ─────────────────────────────────────────────────────

@app.route('/api/license/validate', methods=['POST'])
def validate_license():
    data = request.get_json(force=True)
    key  = data.get('license_key', '')
    dev  = data.get('device_id', '')
    ok   = license_mod.validate(key, dev)
    return jsonify({'valid': ok})


# ── Start ─────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("=" * 50)
    print("  SWAK Backend Server v2.0.0")
    print("  Listening on http://127.0.0.1:5000")
    print("  Press Ctrl+C to stop")
    print("=" * 50)
    app.run(
        host='127.0.0.1',
        port=5000,
        debug=False,          # Never True in production
        threaded=True,
    )
