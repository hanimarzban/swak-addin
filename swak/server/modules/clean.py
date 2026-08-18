# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
"""
SWAK — Data Cleaning Module (Python → Cython)
This file is compiled to clean_c.pyd / clean_c.so via build.py
Source code becomes binary — not readable after compilation

24 tools: all pure Python/NumPy for speed + Cython safety
"""

import re
import math
from datetime import datetime, timezone
from collections import Counter

# ── NumPy / Pandas (available in compiled binary) ──
import numpy as np
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


def run(tool_id: str, params: dict, headers: list, rows: list) -> dict:
    """Main entry point called by server.py"""
    fn_map = {
        'remove-duplicates':  remove_duplicates,
        'fill-missing':       fill_missing,
        'remove-outliers':    remove_outliers,
        'convert-type':       convert_type,
        'text-ops':           text_ops,
        'split-column':       split_column,
        'merge-columns':      merge_columns,
        'handle-errors':      handle_errors,
        'date-ops':           date_ops,
        'normalize-text':     normalize_text,
        'remove-empty-rows':  remove_empty_rows,
        'remove-empty-cols':  remove_empty_cols,
        'regex-replace':      regex_replace,
        'validate-email':     validate_email,
        'validate-phone':     validate_phone,
        'validate-url':       validate_url,
        'detect-encoding':    detect_encoding,
        'date-standardize':   date_standardize,
        'currency-convert':   currency_convert,
        'unit-convert':       unit_convert,
        'detect-dup-key':     detect_dup_key,
        'detect-constant':    detect_constant,
        'invalid-values':     invalid_values,
        'missing-strategy':   missing_strategy,
    }
    fn = fn_map.get(tool_id)
    if not fn:
        raise ValueError(f'ابزار ناشناخته: {tool_id}')
    return fn(params, headers, list(rows))


# ── Helpers ───────────────────────────────────────────────────────────────

def _col_idx(headers, col_name):
    try:
        return headers.index(col_name)
    except ValueError:
        raise ValueError(f'ستون "{col_name}" یافت نشد')

def _is_empty(v):
    if v is None: return True
    if isinstance(v, float) and math.isnan(v): return True
    if isinstance(v, str) and v.strip() == '': return True
    return False

def _to_number(v):
    if _is_empty(v): return None
    try:
        return float(str(v).replace(',', '').replace('،', ''))
    except (ValueError, TypeError):
        return None

def _median(vals):
    s = sorted(v for v in vals if v is not None)
    if not s: return 0
    n = len(s)
    return s[n//2] if n % 2 else (s[n//2-1] + s[n//2]) / 2

def _percentile(sorted_vals, p):
    if not sorted_vals: return 0
    idx = (p / 100) * (len(sorted_vals) - 1)
    lo, hi = int(idx), math.ceil(idx)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (idx - lo) if lo != hi else sorted_vals[lo]

def _mode(vals):
    non_empty = [v for v in vals if not _is_empty(v)]
    if not non_empty: return None
    return Counter(non_empty).most_common(1)[0][0]


# ── 1. Remove Duplicates ──────────────────────────────────────────────────

def remove_duplicates(params, headers, rows):
    mode  = params.get('mode', 'all')
    keep  = params.get('keep', 'first')

    key_cols = list(range(len(headers))) if mode == 'all' else [_col_idx(headers, params.get('column', headers[0]))]

    seen = {}
    result = []
    dup_count = 0

    source = reversed(rows) if keep == 'last' else rows
    for i, row in enumerate(source):
        key = '\x00'.join(str(row[ci] if ci < len(row) else '') for ci in key_cols)
        if key not in seen:
            seen[key] = True
            result.append(row)
        else:
            dup_count += 1

    if keep == 'last':
        result = list(reversed(result))

    return {
        'headers': headers,
        'rows': result,
        'summary': {
            'title': 'حذف تکراری‌ها',
            'stats': [
                ['ردیف اصلی', len(rows)],
                ['تکراری حذف شده', dup_count],
                ['ردیف باقیمانده', len(result)],
                ['% حذف شده', f'{dup_count/len(rows)*100:.1f}%' if rows else '0%'],
            ],
        }
    }


# ── 2. Fill Missing Values ────────────────────────────────────────────────

def fill_missing(params, headers, rows):
    method    = params.get('method', 'mean')
    col_name  = params.get('column', '')
    col_idxs  = [_col_idx(headers, col_name)] if col_name else list(range(len(headers)))

    new_rows = [list(r) for r in rows]
    filled   = 0

    for ci in col_idxs:
        vals    = [r[ci] if ci < len(r) else None for r in rows]
        numeric = [_to_number(v) for v in vals if _to_number(v) is not None]

        if method == 'mean':
            fill_val = sum(numeric) / len(numeric) if numeric else 0
        elif method == 'median':
            fill_val = _median(numeric)
        elif method == 'zero':
            fill_val = 0
        elif method == 'value':
            fill_val = params.get('fill_value', 0)
        else:
            fill_val = None

        if method == 'ffill':
            last = None
            for i, row in enumerate(new_rows):
                if _is_empty(row[ci] if ci < len(row) else None):
                    if last is not None:
                        new_rows[i][ci] = last
                        filled += 1
                else:
                    last = row[ci]
            continue

        if method == 'bfill':
            nxt = None
            for i in range(len(new_rows) - 1, -1, -1):
                if _is_empty(new_rows[i][ci] if ci < len(new_rows[i]) else None):
                    if nxt is not None:
                        new_rows[i][ci] = nxt
                        filled += 1
                else:
                    nxt = new_rows[i][ci]
            continue

        for i, row in enumerate(new_rows):
            if _is_empty(row[ci] if ci < len(row) else None):
                new_rows[i][ci] = fill_val
                filled += 1

    return {
        'headers': headers,
        'rows': new_rows,
        'summary': {
            'title': 'پر کردن مقادیر خالی',
            'stats': [['سلول پر شده', filled], ['روش', method]],
        }
    }


# ── 3. Remove Outliers ────────────────────────────────────────────────────

def remove_outliers(params, headers, rows):
    ci        = _col_idx(headers, params['column'])
    method    = params.get('method', 'iqr')
    threshold = float(params.get('threshold', 1.5))

    nums = [(i, _to_number(r[ci])) for i, r in enumerate(rows) if _to_number(r[ci]) is not None]
    vals = sorted(n for _, n in nums)

    if method == 'iqr':
        q1    = _percentile(vals, 25)
        q3    = _percentile(vals, 75)
        iqr   = q3 - q1
        lower = q1 - threshold * iqr
        upper = q3 + threshold * iqr
    else:
        mean  = sum(vals) / len(vals)
        std   = math.sqrt(sum((v - mean)**2 for v in vals) / len(vals))
        lower = mean - threshold * std
        upper = mean + threshold * std

    outlier_idx = {i for i, n in nums if n < lower or n > upper}
    new_rows    = [r for i, r in enumerate(rows) if i not in outlier_idx]

    return {
        'headers': headers,
        'rows': new_rows,
        'summary': {
            'title': f'حذف مقادیر پرت — {params["column"]}',
            'stats': [
                ['روش', method],
                ['کران پایین', f'{lower:.2f}'],
                ['کران بالا',  f'{upper:.2f}'],
                ['پرت حذف شده', len(outlier_idx)],
                ['ردیف باقیمانده', len(new_rows)],
            ],
        }
    }


# ── 4. Convert Type ───────────────────────────────────────────────────────

def convert_type(params, headers, rows):
    ci         = _col_idx(headers, params['column'])
    target     = params.get('target_type', 'number')
    converted  = 0
    failed     = 0
    new_rows   = [list(r) for r in rows]

    for i, row in enumerate(new_rows):
        val = row[ci] if ci < len(row) else None
        try:
            if target == 'number':
                n = _to_number(val)
                new_rows[i][ci] = n
                (converted if n is not None else failed).__class__  # dummy
                if n is not None: converted += 1
                else: failed += 1
            elif target == 'text':
                new_rows[i][ci] = '' if _is_empty(val) else str(val)
                converted += 1
            elif target == 'date':
                d = datetime.fromisoformat(str(val))
                new_rows[i][ci] = d.strftime('%Y-%m-%d')
                converted += 1
            elif target == 'boolean':
                s = str(val).lower().strip()
                new_rows[i][ci] = s in ('true', '1', 'yes', 'بله', 'صحیح')
                converted += 1
            elif target == 'currency':
                n = _to_number(re.sub(r'[^\d.\-]', '', str(val)))
                new_rows[i][ci] = n
                if n is not None: converted += 1
                else: failed += 1
        except Exception:
            new_rows[i][ci] = None
            failed += 1

    return {
        'headers': headers,
        'rows': new_rows,
        'summary': {
            'title': f'تبدیل نوع — {params["column"]}',
            'stats': [['نوع هدف', target], ['موفق', converted], ['ناموفق', failed]],
        }
    }


# ── 5. Text Operations ────────────────────────────────────────────────────

def text_ops(params, headers, rows):
    ci       = _col_idx(headers, params['column'])
    op       = params.get('operation', 'trim')
    changed  = 0
    new_rows = [list(r) for r in rows]

    def apply_op(v):
        s = str(v)
        if op == 'trim':            return s.strip()
        if op == 'uppercase':       return s.upper()
        if op == 'lowercase':       return s.lower()
        if op == 'title_case':      return s.title()
        if op == 'remove_special':  return re.sub(r'[^\w\s\u0600-\u06FF]', '', s)
        if op == 'remove_numbers':  return re.sub(r'[\d\u06F0-\u06F9\u0660-\u0669]', '', s)
        if op == 'remove_spaces':   return re.sub(r'\s+', '', s)
        if op == 'extract_numbers': return ' '.join(re.findall(r'[\d\u06F0-\u06F9.,\-]+', s))
        return s

    for i, row in enumerate(new_rows):
        if not _is_empty(row[ci] if ci < len(row) else None):
            orig = str(row[ci])
            new_rows[i][ci] = apply_op(row[ci])
            if new_rows[i][ci] != orig:
                changed += 1

    return {
        'headers': headers,
        'rows': new_rows,
        'summary': {
            'title': f'عملیات متنی — {params["column"]}',
            'stats': [['عملیات', op], ['تغییر یافته', changed]],
        }
    }


# ── 6. Split Column ───────────────────────────────────────────────────────

def split_column(params, headers, rows):
    ci        = _col_idx(headers, params['column'])
    delim     = params.get('delimiter', ',')
    max_split = int(params.get('max_splits', 2))

    new_headers = headers + [f'{params["column"]}_{i+1}' for i in range(max_split)]
    new_rows    = []
    for row in rows:
        r     = list(row)
        parts = str(r[ci] if ci < len(r) else '').split(delim)
        for i in range(max_split):
            r.append(parts[i].strip() if i < len(parts) else '')
        new_rows.append(r)

    return {
        'headers': new_headers,
        'rows': new_rows,
        'summary': {
            'title': f'جدا کردن ستون — {params["column"]}',
            'stats': [['جداکننده', delim], ['ستون جدید', max_split]],
        }
    }


# ── 7. Merge Columns ──────────────────────────────────────────────────────

def merge_columns(params, headers, rows):
    ci1  = _col_idx(headers, params['col1'])
    ci2  = _col_idx(headers, params['col2'])
    sep  = params.get('separator', ' ')
    name = params.get('new_name', 'merged')

    new_headers = headers + [name]
    new_rows    = [list(r) + [f'{r[ci1] or ""}{sep}{r[ci2] or ""}'] for r in rows]

    return {
        'headers': new_headers,
        'rows': new_rows,
        'summary': {
            'title': 'ادغام ستون‌ها',
            'stats': [['ستون ۱', params['col1']], ['ستون ۲', params['col2']], ['ستون جدید', name]],
        }
    }


# ── 8. Handle Errors ──────────────────────────────────────────────────────

EXCEL_ERRORS = {'#div/0!','#n/a','#name?','#null!','#num!','#ref!','#value!','#error!'}

def handle_errors(params, headers, rows):
    strategy = params.get('strategy', 'fill_default')
    col_name = params.get('column', '')
    col_idxs = [_col_idx(headers, col_name)] if col_name else list(range(len(headers)))

    is_err   = lambda v: str(v or '').lower().strip() in EXCEL_ERRORS
    fixed    = 0
    new_rows = [list(r) for r in rows]
    new_hdrs = list(headers)

    if strategy == 'flag_column':
        new_hdrs.append('_has_error')

    for i, row in enumerate(new_rows):
        has_err = any(is_err(row[ci] if ci < len(row) else None) for ci in col_idxs)
        for ci in col_idxs:
            if ci < len(row) and is_err(row[ci]):
                fixed += 1
                row[ci] = 0 if strategy == 'fill_default' else None
        if strategy == 'flag_column':
            new_rows[i].append(1 if has_err else 0)

    if strategy == 'drop_rows':
        new_rows = [r for r in new_rows if not any(is_err(r[ci] if ci < len(r) else None) for ci in col_idxs)]

    return {
        'headers': new_hdrs,
        'rows': new_rows,
        'summary': {
            'title': 'مدیریت خطا',
            'stats': [['استراتژی', strategy], ['خطا یافت شده', fixed]],
        }
    }


# ── 9. Date Operations ────────────────────────────────────────────────────

def date_ops(params, headers, rows):
    ci       = _col_idx(headers, params['column'])
    op       = params.get('operation', 'extract_year')
    col_name = op.replace('extract_', '').replace('_', ' ')

    new_headers = headers + [col_name]
    new_rows    = []

    for row in rows:
        r = list(row)
        v = r[ci] if ci < len(r) else None
        extracted = ''
        try:
            d = datetime.fromisoformat(str(v).replace('/', '-'))
            if op == 'extract_year':    extracted = d.year
            elif op == 'extract_month': extracted = d.month
            elif op == 'extract_day':   extracted = d.day
            elif op == 'extract_weekday': extracted = d.strftime('%a')
            elif op == 'add_days':
                from datetime import timedelta
                extracted = (d + timedelta(days=int(params.get('days', 0)))).strftime('%Y-%m-%d')
            elif op == 'format':        extracted = d.strftime(params.get('format','%Y-%m-%d'))
        except Exception:
            pass
        new_rows.append(r + [extracted])

    return {
        'headers': new_headers,
        'rows': new_rows,
        'summary': {'title': f'عملیات تاریخ — {params["column"]}', 'stats': [['عملیات', op]]},
    }


# ── 10. Normalize Text ────────────────────────────────────────────────────

def normalize_text(params, headers, rows):
    import unicodedata
    ci      = _col_idx(headers, params['column'])
    ops     = params.get('operations', 'nfkc')
    changed = 0
    new_rows = [list(r) for r in rows]

    for i, row in enumerate(new_rows):
        v = str(row[ci] if ci < len(row) else '')
        orig = v
        if ops in ('nfkc','all'): v = unicodedata.normalize('NFKC', v)
        elif ops == 'nfc':        v = unicodedata.normalize('NFC', v)
        elif ops == 'nfd':        v = unicodedata.normalize('NFD', v)
        if ops in ('remove_accents','all'):
            v = ''.join(c for c in unicodedata.normalize('NFD', v) if unicodedata.category(c) != 'Mn')
        if ops in ('lowercase','all'): v = v.lower()
        if v != orig: changed += 1
        new_rows[i][ci] = v

    return {
        'headers': headers,
        'rows': new_rows,
        'summary': {'title': f'یکنواخت‌سازی متن — {params["column"]}', 'stats': [['تغییر یافته', changed]]},
    }


# ── 11. Remove Empty Rows ─────────────────────────────────────────────────

def remove_empty_rows(params, headers, rows):
    threshold = float(params.get('threshold', 100))
    ws_empty  = params.get('consider_whitespace', 'true') != 'false'

    def is_empty(v):
        return _is_empty(v) or (ws_empty and isinstance(v, str) and v.strip() == '')

    new_rows = []
    removed  = 0
    for row in rows:
        empty_pct = sum(1 for v in row if is_empty(v)) / len(row) * 100 if row else 100
        if empty_pct < threshold:
            new_rows.append(row)
        else:
            removed += 1

    return {
        'headers': headers,
        'rows': new_rows,
        'summary': {'title': 'حذف ردیف‌های خالی', 'stats': [['حذف شده', removed], ['باقیمانده', len(new_rows)]]},
    }


# ── 12. Remove Empty Cols ─────────────────────────────────────────────────

def remove_empty_cols(params, headers, rows):
    threshold = float(params.get('threshold', 100))
    ws_empty  = params.get('consider_whitespace', 'true') != 'false'

    def is_empty(v):
        return _is_empty(v) or (ws_empty and isinstance(v, str) and v.strip() == '')

    keep_cols = []
    for ci, h in enumerate(headers):
        empty_pct = sum(1 for r in rows if is_empty(r[ci] if ci < len(r) else None)) / len(rows) * 100 if rows else 100
        keep_cols.append(empty_pct < threshold)

    new_headers = [h for h, k in zip(headers, keep_cols) if k]
    new_rows    = [[v for v, k in zip(r, keep_cols) if k] for r in rows]

    return {
        'headers': new_headers,
        'rows': new_rows,
        'summary': {'title': 'حذف ستون‌های خالی', 'stats': [['حذف شده', keep_cols.count(False)], ['باقیمانده', len(new_headers)]]},
    }


# ── 13-24: Remaining tools (regex_replace → missing_strategy) ────────────
# Same logic as JS version, translated to Python
# Omitted here for brevity — see full implementation in clean_full.py

def regex_replace(params, headers, rows):
    ci      = _col_idx(headers, params['column'])
    pattern = params.get('pattern','')
    repl    = params.get('replacement','')
    flags   = re.IGNORECASE if params.get('flags') == 'case_insensitive' else 0
    regex   = re.compile(pattern, flags)
    changed = 0
    new_rows = [list(r) for r in rows]
    for i, row in enumerate(new_rows):
        orig = str(row[ci] if ci < len(row) else '')
        new_rows[i][ci] = regex.sub(repl, orig)
        if new_rows[i][ci] != orig: changed += 1
    return {'headers': headers, 'rows': new_rows,
            'summary': {'title': f'Regex Replace — {params["column"]}', 'stats': [['تغییر یافته', changed]]}}

def validate_email(params, headers, rows):
    ci     = _col_idx(headers, params['column'])
    action = params.get('action', 'flag_invalid')
    RE     = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]{2,}$')
    new_hdrs = list(headers) + (['email_valid'] if action == 'flag_invalid' else [])
    new_rows = [list(r) for r in rows]
    invalid  = 0
    for i, row in enumerate(new_rows):
        v     = str(row[ci] if ci < len(row) else '').strip()
        valid = bool(RE.match(v))
        if not valid: invalid += 1
        if action == 'flag_invalid': new_rows[i].append(1 if valid else 0)
        elif action == 'remove_invalid' and not valid: new_rows[i][ci] = None
    if action == 'extract_valid':
        orig_rows = rows
        new_rows  = [r for i,r in enumerate(new_rows) if bool(RE.match(str(orig_rows[i][ci] or '').strip()))]
    return {'headers': new_hdrs, 'rows': new_rows,
            'summary': {'title': f'اعتبارسنجی ایمیل — {params["column"]}',
                        'stats': [['کل', len(rows)], ['معتبر', len(rows)-invalid], ['نامعتبر', invalid]]}}

def validate_phone(params, headers, rows):
    ci      = _col_idx(headers, params['column'])
    action  = params.get('action', 'flag_invalid')
    region  = params.get('region', 'auto')
    PATS    = {'IR': r'^(\+98|0098|0)?9\d{9}$', 'US': r'^(\+1)?[2-9]\d{9}$',
               'auto': r'^[\+\d\s\-\(\)]{7,20}$'}
    RE      = re.compile(PATS.get(region, PATS['auto']))
    new_hdrs= list(headers) + (['phone_valid'] if action == 'flag_invalid' else [])
    new_rows= [list(r) for r in rows]
    invalid = 0
    for i, row in enumerate(new_rows):
        raw   = re.sub(r'\s','', str(row[ci] if ci < len(row) else ''))
        valid = bool(RE.match(raw))
        if not valid: invalid += 1
        if action == 'flag_invalid': new_rows[i].append(1 if valid else 0)
        elif action == 'remove_invalid' and not valid: new_rows[i][ci] = None
        elif action == 'normalize' and valid: new_rows[i][ci] = re.sub(r'[^\d+]','',raw)
    return {'headers': new_hdrs, 'rows': new_rows,
            'summary': {'title': f'اعتبارسنجی تلفن — {params["column"]}',
                        'stats': [['معتبر', len(rows)-invalid], ['نامعتبر', invalid]]}}

def validate_url(params, headers, rows):
    from urllib.parse import urlparse
    ci           = _col_idx(headers, params['column'])
    action       = params.get('action', 'flag_invalid')
    check_scheme = params.get('check_scheme', 'true') != 'false'
    def is_valid(v):
        try:
            p = urlparse(str(v).strip())
            return bool(p.netloc) and (not check_scheme or p.scheme in ('http','https'))
        except: return False
    new_hdrs = list(headers) + (['url_valid'] if action == 'flag_invalid' else [])
    new_rows = [list(r) for r in rows]
    invalid  = 0
    for i, row in enumerate(new_rows):
        valid = is_valid(row[ci] if ci < len(row) else '')
        if not valid: invalid += 1
        if action == 'flag_invalid': new_rows[i].append(1 if valid else 0)
        elif action == 'remove_invalid' and not valid: new_rows[i][ci] = None
    return {'headers': new_hdrs, 'rows': new_rows,
            'summary': {'title': f'اعتبارسنجی URL — {params["column"]}',
                        'stats': [['معتبر', len(rows)-invalid], ['نامعتبر', invalid]]}}

def detect_encoding(params, headers, rows):
    return {'headers': headers, 'rows': rows,
            'summary': {'title': 'تشخیص کدگذاری', 'stats': [['وضعیت', 'UTF-8 (Python internal)']]}}

def date_standardize(params, headers, rows):
    ci      = _col_idx(headers, params['column'])
    fmt_map = {'ISO8601':'%Y-%m-%d','%Y-%m-%d':'%Y-%m-%d','%d/%m/%Y':'%d/%m/%Y',
               '%m/%d/%Y':'%m/%d/%Y','%Y/%m/%d':'%Y/%m/%d'}
    out_fmt = fmt_map.get(params.get('output_format','ISO8601'), '%Y-%m-%d')
    on_err  = params.get('handle_errors','null')
    converted, errors = 0, 0
    new_rows = [list(r) for r in rows]
    for i, row in enumerate(new_rows):
        try:
            d = datetime.fromisoformat(str(row[ci] if ci<len(row) else '').replace('/','-'))
            if params.get('output_format') == 'unix':
                new_rows[i][ci] = int(d.timestamp())
            else:
                new_rows[i][ci] = d.strftime(out_fmt)
            converted += 1
        except:
            errors += 1
            if on_err == 'null':    new_rows[i][ci] = None
            elif on_err == 'error': new_rows[i][ci] = '#DATE_ERROR'
    return {'headers': headers, 'rows': new_rows,
            'summary': {'title': f'استانداردسازی تاریخ — {params["column"]}',
                        'stats': [['موفق', converted], ['خطا', errors]]}}

def currency_convert(params, headers, rows):
    ci   = _col_idx(headers, params['column'])
    frm  = params.get('from_currency','USD')
    to   = params.get('to_currency','EUR')
    rate = float(params.get('manual_rate', 1.0))
    if params.get('rate_source','live') == 'live':
        try:
            import urllib.request, json
            with urllib.request.urlopen(f'https://api.exchangerate-api.com/v4/latest/{frm}', timeout=5) as r:
                data = json.loads(r.read())
                rate = data['rates'].get(to, rate)
        except: pass
    new_hdrs = headers + [f'{params["column"]}_{to}']
    new_rows = [list(r) + [round(_to_number(r[ci])*rate, 4) if _to_number(r[ci]) is not None else None] for r in rows]
    return {'headers': new_hdrs, 'rows': new_rows,
            'summary': {'title': f'تبدیل ارز {frm}→{to}', 'stats': [['نرخ', f'{rate:.6f}']]}}

def unit_convert(params, headers, rows):
    UNITS = {
        'length':  {'m':1,'km':1000,'cm':0.01,'mm':0.001,'ft':0.3048,'in':0.0254,'mi':1609.344},
        'mass':    {'kg':1,'g':0.001,'lb':0.453592,'oz':0.028349,'t':1000},
        'area':    {'m2':1,'km2':1e6,'ft2':0.092903,'acre':4046.86,'ha':10000},
        'volume':  {'m3':1,'l':0.001,'ml':0.000001,'gal':0.003785},
        'speed':   {'ms':1,'kmh':0.27778,'mph':0.44704},
        'pressure':{'pa':1,'kpa':1000,'bar':100000,'psi':6894.76,'atm':101325},
    }
    ci   = _col_idx(headers, params['column'])
    cat  = params.get('category','length')
    frm  = params.get('from_unit','m')
    to   = params.get('to_unit','ft')
    tbl  = UNITS.get(cat,{})
    rate = (tbl.get(frm,1) / tbl.get(to,1)) if to in tbl else 1
    new_hdrs = headers + [f'{params["column"]}_{to}']
    new_rows = [list(r) + [round(_to_number(r[ci])*rate, 6) if _to_number(r[ci]) is not None else None] for r in rows]
    return {'headers': new_hdrs, 'rows': new_rows,
            'summary': {'title': f'تبدیل واحد {frm}→{to}', 'stats': [['دسته', cat]]}}

def detect_dup_key(params, headers, rows):
    ci     = _col_idx(headers, params['key_columns'])
    action = params.get('action','report')
    seen   = {}
    dups   = []
    for i, row in enumerate(rows):
        key = str(row[ci] if ci < len(row) else '')
        if key in seen: dups.append(i)
        else: seen[key] = i
    new_rows = list(rows)
    if action == 'keep_first':
        dup_set  = set(dups)
        new_rows = [r for i,r in enumerate(rows) if i not in dup_set]
    return {'headers': headers, 'rows': new_rows,
            'summary': {'title': f'تشخیص کلید تکراری — {params["key_columns"]}',
                        'stats': [['تکراری', len(dups)], ['یکتا', len(seen)]]}}

def detect_constant(params, headers, rows):
    threshold = int(params.get('threshold', 1))
    const_cols = [h for i,h in enumerate(headers)
                  if len(set(str(r[i] if i<len(r) else '') for r in rows)) <= threshold]
    return {'headers': headers, 'rows': rows,
            'summary': {'title': 'تشخیص ستون ثابت',
                        'stats': [['ستون ثابت', len(const_cols)]],
                        'note': 'ستون‌های ثابت: ' + ', '.join(const_cols) if const_cols else 'هیچ ستون ثابتی یافت نشد'}}

def invalid_values(params, headers, rows):
    ci        = _col_idx(headers, params['column'])
    rule_type = params.get('rule_type','range')
    action    = params.get('action','flag')
    violations = 0
    new_hdrs  = list(headers) + (['is_invalid'] if action == 'flag' else [])
    new_rows  = [list(r) for r in rows]
    for i, row in enumerate(new_rows):
        v   = row[ci] if ci < len(row) else None
        bad = False
        if rule_type == 'not_null': bad = _is_empty(v)
        elif rule_type == 'range':
            n   = _to_number(v)
            bad = n is None or (params.get('min_val') and n < float(params['min_val'])) or \
                               (params.get('max_val') and n > float(params['max_val']))
        elif rule_type == 'allowed_list':
            lst = [s.strip() for s in params.get('allowed_list','').split(',')]
            bad = str(v or '').strip() not in lst
        elif rule_type == 'regex':
            bad = not bool(re.match(params.get('regex_pattern',''), str(v or '')))
        if bad: violations += 1
        if action == 'flag': new_rows[i].append(1 if bad else 0)
        elif bad: new_rows[i][ci] = None
    if action == 'remove': new_rows = [r for r in new_rows if r[ci] is not None]
    return {'headers': new_hdrs, 'rows': new_rows,
            'summary': {'title': f'مقادیر نامعتبر — {params["column"]}',
                        'stats': [['نقض', violations], ['معتبر', len(rows)-violations]]}}

def missing_strategy(params, headers, rows):
    strategy  = params.get('strategy','mean')
    col_name  = params.get('column','')
    threshold = float(params.get('threshold', 50))
    col_idxs  = [_col_idx(headers, col_name)] if col_name else list(range(len(headers)))
    new_rows  = [list(r) for r in rows]
    new_hdrs  = list(headers)

    if strategy == 'drop_rows':
        new_rows = [r for r in new_rows if all(not _is_empty(r[ci] if ci < len(r) else None) for ci in col_idxs)]
    elif strategy == 'drop_cols':
        keep = [sum(1 for r in rows if _is_empty(r[ci] if ci<len(r) else None))/len(rows)*100 < threshold
                for ci in range(len(headers))]
        new_hdrs = [h for h,k in zip(headers,keep) if k]
        new_rows = [[v for v,k in zip(r,keep) if k] for r in new_rows]
    else:
        for ci in col_idxs:
            vals    = [r[ci] if ci<len(r) else None for r in new_rows]
            numeric = [_to_number(v) for v in vals if _to_number(v) is not None]
            if strategy == 'mean':     fv = sum(numeric)/len(numeric) if numeric else 0
            elif strategy == 'median': fv = _median(numeric)
            elif strategy == 'mode':   fv = _mode(vals)
            elif strategy == 'constant': fv = params.get('constant_value', 0)
            else: fv = None
            for i in range(len(new_rows)):
                if _is_empty(new_rows[i][ci] if ci<len(new_rows[i]) else None):
                    if strategy == 'forward_fill':
                        new_rows[i][ci] = new_rows[i-1][ci] if i>0 else None
                    elif strategy == 'backward_fill':
                        pass  # second pass below
                    else:
                        new_rows[i][ci] = fv
            if strategy == 'backward_fill':
                for i in range(len(new_rows)-2,-1,-1):
                    if _is_empty(new_rows[i][ci] if ci<len(new_rows[i]) else None):
                        new_rows[i][ci] = new_rows[i+1][ci] if i+1<len(new_rows) else None

    return {'headers': new_hdrs, 'rows': new_rows,
            'summary': {'title': 'استراتژی مقادیر خالی',
                        'stats': [['استراتژی', strategy], ['ردیف نهایی', len(new_rows)]]}}
