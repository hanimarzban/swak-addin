# cython: language_level=3
"""
SWAK — License Validation Module
Validates license keys against Supabase
Runs locally — key stored encrypted on disk
"""

import hashlib
import json
import os
import time
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────

SUPABASE_URL = os.environ.get('SWAK_SUPABASE_URL', '')  # Set in .env
SUPABASE_KEY = os.environ.get('SWAK_SUPABASE_ANON_KEY', '')  # Set in .env

CACHE_FILE   = Path(os.path.expanduser('~')) / '.swak' / 'license_cache.json'
CACHE_TTL    = 86400  # 24 hours — revalidate daily

# Free tools that never need license
FREE_TOOL_IDS = {
    'remove-duplicates', 'fill-missing', 'remove-empty-rows',
    'remove-empty-cols', 'text-ops', 'convert-type',
    'validate-email', 'validate-phone', 'validate-url',
    'remove-outliers', 'filter-basic', 'sort-data',
    'describe-stats', 'correlation',
}


def validate(license_key: str, device_id: str = '') -> bool:
    """
    Returns True if license is valid.
    Checks local cache first, then Supabase.
    """
    if not license_key:
        return False

    # Check cache
    cached = _read_cache(license_key)
    if cached is not None:
        return cached

    # Validate against Supabase
    result = _validate_remote(license_key, device_id)
    _write_cache(license_key, result)
    return result


def is_free_tool(tool_id: str) -> bool:
    return tool_id in FREE_TOOL_IDS


def _validate_remote(key: str, device_id: str) -> bool:
    if not SUPABASE_URL or not SUPABASE_KEY:
        # No Supabase configured — allow all (dev mode)
        return True

    try:
        import urllib.request
        import urllib.parse

        payload = json.dumps({
            'license_key': key,
            'device_id':   device_id or _get_device_id(),
        }).encode()

        req = urllib.request.Request(
            f'{SUPABASE_URL}/rest/v1/rpc/validate_license',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'apikey':       SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}',
            }
        )

        with urllib.request.urlopen(req, timeout=10) as res:
            data = json.loads(res.read())
            return bool(data.get('valid', False))

    except Exception as e:
        print(f'[License] Remote validation failed: {e}')
        # If server unreachable, use cached result or deny
        return False


def _get_device_id() -> str:
    """Generate a stable device fingerprint"""
    import platform
    parts = [
        platform.node(),
        platform.machine(),
        platform.processor(),
    ]
    return hashlib.sha256('|'.join(parts).encode()).hexdigest()[:16]


def _cache_key(license_key: str) -> str:
    return hashlib.sha256(license_key.encode()).hexdigest()[:16]


def _read_cache(license_key: str):
    try:
        if not CACHE_FILE.exists():
            return None
        data = json.loads(CACHE_FILE.read_text())
        entry = data.get(_cache_key(license_key))
        if not entry:
            return None
        if time.time() - entry['ts'] > CACHE_TTL:
            return None  # expired
        return entry['valid']
    except Exception:
        return None


def _write_cache(license_key: str, valid: bool):
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if CACHE_FILE.exists():
            data = json.loads(CACHE_FILE.read_text())
        data[_cache_key(license_key)] = {'valid': valid, 'ts': int(time.time())}
        CACHE_FILE.write_text(json.dumps(data))
    except Exception:
        pass
