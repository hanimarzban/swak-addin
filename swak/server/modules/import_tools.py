# cython: language_level=3
"""
SWAK — Data Import Module (10 tools)
Parse and import various file formats into Excel
"""

import csv
import json
import re
import io
import math
import urllib.request
import urllib.parse
from collections import defaultdict


def run(tool_id: str, params: dict, headers: list, rows: list) -> dict:
    fn_map = {
        'import-csv':       import_csv,
        'import-json':      import_json,
        'import-xml':       import_xml,
        'import-sql':       import_sql_query,
        'import-api':       import_api,
        'import-clipboard': import_clipboard,
        'import-web':       import_web_table,
        'import-excel':     import_excel_sheet,
        'import-parquet':   import_parquet,
        'merge-datasets':   merge_datasets,
    }
    fn = fn_map.get(tool_id)
    if not fn:
        raise ValueError(f'ابزار ناشناخته: {tool_id}')
    return fn(params, headers, list(rows))


# ── Helpers ───────────────────────────────────────────────────────────────

def _is_empty(v):
    return v is None or (isinstance(v, float) and math.isnan(v)) or (isinstance(v, str) and v.strip() == '')

def _to_number(v):
    if _is_empty(v): return None
    try: return float(str(v).replace(',', ''))
    except: return None

def _result(headers, rows, title, stats, note=''):
    return {'headers': headers, 'rows': rows,
            'summary': {'title': title, 'stats': stats, 'note': note}}

def _infer_types(headers, rows):
    """Try to infer and convert numeric columns"""
    new_rows = [list(r) for r in rows]
    for ci in range(len(headers)):
        vals = [r[ci] if ci < len(r) else None for r in rows]
        non_empty = [v for v in vals if not _is_empty(v)]
        nums = [_to_number(v) for v in non_empty]
        if non_empty and all(n is not None for n in nums):
            for i in range(len(new_rows)):
                v = new_rows[i][ci] if ci < len(new_rows[i]) else None
                if not _is_empty(v):
                    n = _to_number(v)
                    if n is not None:
                        new_rows[i][ci] = n
    return new_rows


# ── 1. Import CSV ─────────────────────────────────────────────────────────

def import_csv(params, headers, rows):
    """
    Parse CSV text content passed in params.content
    or read from params.file_path (server-side)
    """
    content    = params.get('content', '')
    delimiter  = params.get('delimiter', ',')
    encoding   = params.get('encoding', 'utf-8')
    skip_rows  = int(params.get('skip_rows', 0))
    has_header = params.get('has_header', 'true') == 'true'
    file_path  = params.get('file_path', '')

    if not content and file_path:
        try:
            with open(file_path, encoding=encoding, errors='replace') as f:
                content = f.read()
        except Exception as e:
            raise ValueError(f'خواندن فایل ناموفق: {e}')

    if not content:
        raise ValueError('محتوای CSV الزامی است (content یا file_path)')

    reader = csv.reader(io.StringIO(content), delimiter=delimiter)
    all_rows = list(reader)
    all_rows = all_rows[skip_rows:]

    if not all_rows:
        raise ValueError('فایل CSV خالی است')

    if has_header:
        new_headers = [str(h).strip() for h in all_rows[0]]
        new_rows    = [[c.strip() for c in r] for r in all_rows[1:] if r]
    else:
        new_headers = [f'col_{i+1}' for i in range(len(all_rows[0]))]
        new_rows    = [[c.strip() for c in r] for r in all_rows if r]

    # Auto-infer numeric types
    if params.get('infer_types', 'true') == 'true':
        new_rows = _infer_types(new_headers, new_rows)

    return _result(new_headers, new_rows,
                   'Import CSV',
                   [['ردیف وارد شده', len(new_rows)],
                    ['ستون', len(new_headers)],
                    ['جداکننده', repr(delimiter)]])


# ── 2. Import JSON ────────────────────────────────────────────────────────

def import_json(params, headers, rows):
    content   = params.get('content', '')
    file_path = params.get('file_path', '')
    path_expr = params.get('json_path', '')  # e.g. "data.items"

    if not content and file_path:
        with open(file_path, encoding='utf-8') as f:
            content = f.read()

    if not content:
        raise ValueError('محتوای JSON الزامی است')

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f'JSON نامعتبر: {e}')

    # Navigate json path if specified
    if path_expr:
        for key in path_expr.split('.'):
            if isinstance(data, dict):
                data = data.get(key, data)
            elif isinstance(data, list) and key.isdigit():
                data = data[int(key)]

    # Normalize to list of dicts
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError('JSON باید آرایه‌ای از اشیاء باشد')

    if not data:
        return _result([], [], 'Import JSON', [['وضعیت', 'خالی']])

    # Flatten one level deep
    def flatten(obj, prefix=''):
        items = {}
        for k, v in obj.items():
            key = f'{prefix}{k}' if not prefix else f'{prefix}.{k}'
            if isinstance(v, dict) and params.get('flatten', 'true') == 'true':
                items.update(flatten(v, key))
            else:
                items[key] = v
        return items

    flat   = [flatten(r) if isinstance(r, dict) else {'value': r} for r in data]
    hdrs   = list(dict.fromkeys(k for r in flat for k in r.keys()))
    nrows  = [[r.get(h) for h in hdrs] for r in flat]

    return _result(hdrs, nrows,
                   'Import JSON',
                   [['ردیف', len(nrows)], ['ستون', len(hdrs)]])


# ── 3. Import XML ─────────────────────────────────────────────────────────

def import_xml(params, headers, rows):
    content     = params.get('content', '')
    file_path   = params.get('file_path', '')
    row_tag     = params.get('row_tag', '')  # e.g. "item", "record"

    if not content and file_path:
        with open(file_path, encoding='utf-8') as f:
            content = f.read()

    if not content:
        raise ValueError('محتوای XML الزامی است')

    # Simple regex-based XML parser (no external lib needed)
    if not row_tag:
        # Auto-detect repeating tags
        tags = re.findall(r'<(\w+)[^/]', content)
        tag_cnt = defaultdict(int)
        for t in tags:
            tag_cnt[t] += 1
        row_tag = max(tag_cnt, key=lambda t: tag_cnt[t]) if tag_cnt else 'item'

    # Extract all instances of row_tag
    pattern = re.compile(rf'<{row_tag}[^>]*>(.*?)</{row_tag}>', re.DOTALL | re.IGNORECASE)
    records_raw = pattern.findall(content)

    if not records_raw:
        raise ValueError(f'تگ <{row_tag}> یافت نشد')

    def parse_children(xml_str):
        result = {}
        child_pattern = re.compile(r'<(\w+)[^>]*>(.*?)</\1>', re.DOTALL)
        for m in child_pattern.finditer(xml_str):
            tag_name  = m.group(1)
            tag_value = re.sub(r'<[^>]+>', '', m.group(2)).strip()  # strip nested tags
            result[tag_name] = tag_value
        return result

    records = [parse_children(r) for r in records_raw]
    hdrs    = list(dict.fromkeys(k for r in records for k in r.keys()))
    nrows   = [[r.get(h, '') for h in hdrs] for r in records]

    return _result(hdrs, nrows,
                   'Import XML',
                   [['تگ ردیف', row_tag], ['ردیف', len(nrows)], ['ستون', len(hdrs)]])


# ── 4. Import SQL Query Result ────────────────────────────────────────────

def import_sql_query(params, headers, rows):
    """
    Execute SQL against local SQLite db or parse SQL result pasted as text
    For security: only SQLite local files, no remote connections
    """
    mode      = params.get('mode', 'paste')  # paste | sqlite
    content   = params.get('content', '')
    db_path   = params.get('db_path', '')
    query     = params.get('query', '')

    if mode == 'sqlite' and db_path and query:
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cur  = conn.cursor()
            cur.execute(query)
            col_names = [d[0] for d in cur.description] if cur.description else []
            data      = cur.fetchall()
            conn.close()
            nrows = [list(r) for r in data]
            return _result(col_names, nrows,
                           'Import SQL (SQLite)',
                           [['ردیف', len(nrows)], ['query', query[:50]]])
        except Exception as e:
            raise ValueError(f'SQLite error: {e}')

    # Parse pasted SQL result (tab or pipe separated)
    if content:
        lines = [l.strip() for l in content.strip().split('\n') if l.strip()]
        # Remove separator lines (---+---) common in psql/mysql output
        lines = [l for l in lines if not re.match(r'^[\-\+\|]+$', l)]

        if not lines:
            raise ValueError('محتوا خالی است')

        delimiter = '|' if '|' in lines[0] else '\t'
        parsed    = [[c.strip().strip('|') for c in l.split(delimiter)] for l in lines]
        hdrs      = parsed[0]
        nrows     = parsed[1:]

        return _result(hdrs, nrows,
                       'Import SQL Result',
                       [['ردیف', len(nrows)], ['ستون', len(hdrs)]])

    raise ValueError('db_path+query یا content الزامی است')


# ── 5. Import from API ────────────────────────────────────────────────────

def import_api(params, headers, rows):
    """
    Fetch JSON data from a public API endpoint
    For security: only GET requests, no auth headers stored
    """
    url       = params.get('url', '')
    json_path = params.get('json_path', '')
    timeout   = int(params.get('timeout', 10))

    if not url:
        raise ValueError('URL الزامی است')

    # Validate URL
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        raise ValueError('فقط HTTP/HTTPS مجاز است')

    try:
        req  = urllib.request.Request(url, headers={'User-Agent': 'SWAK/2.0'})
        with urllib.request.urlopen(req, timeout=timeout) as res:
            raw = res.read().decode('utf-8', errors='replace')
    except Exception as e:
        raise ValueError(f'دریافت API ناموفق: {e}')

    # Parse (reuse JSON logic)
    new_params = {'content': raw, 'json_path': json_path}
    return import_json(new_params, headers, rows)


# ── 6. Import from Clipboard ──────────────────────────────────────────────

def import_clipboard(params, headers, rows):
    """Parse text content (passed from clipboard via JS)"""
    content   = params.get('content', '')
    delimiter = params.get('delimiter', 'auto')

    if not content:
        raise ValueError('محتوای clipboard الزامی است')

    # Auto-detect delimiter
    if delimiter == 'auto':
        sample = content[:500]
        counts = {d: sample.count(d) for d in ['\t', ',', ';', '|']}
        delimiter = max(counts, key=counts.get)

    reader    = csv.reader(io.StringIO(content), delimiter=delimiter)
    all_rows  = list(reader)
    if not all_rows:
        raise ValueError('محتوا خالی است')

    hdrs  = [str(h).strip() for h in all_rows[0]]
    nrows = [[c.strip() for c in r] for r in all_rows[1:] if r]

    return _result(hdrs, nrows,
                   'Import Clipboard',
                   [['ردیف', len(nrows)], ['جداکننده', repr(delimiter)]])


# ── 7. Import Web Table ───────────────────────────────────────────────────

def import_web_table(params, headers, rows):
    """Scrape an HTML table from a URL"""
    url        = params.get('url', '')
    table_idx  = int(params.get('table_index', 0))
    timeout    = int(params.get('timeout', 10))

    if not url:
        raise ValueError('URL الزامی است')

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 SWAK/2.0'})
        with urllib.request.urlopen(req, timeout=timeout) as res:
            html = res.read().decode('utf-8', errors='replace')
    except Exception as e:
        raise ValueError(f'دریافت صفحه ناموفق: {e}')

    # Extract tables with regex
    tables = re.findall(r'<table[^>]*>(.*?)</table>', html, re.DOTALL | re.IGNORECASE)
    if not tables:
        raise ValueError('جدول HTML یافت نشد')

    if table_idx >= len(tables):
        table_idx = 0

    table = tables[table_idx]
    rows_raw = re.findall(r'<tr[^>]*>(.*?)</tr>', table, re.DOTALL | re.IGNORECASE)

    def parse_cells(row_html):
        cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row_html, re.DOTALL | re.IGNORECASE)
        return [re.sub(r'<[^>]+>', '', c).strip() for c in cells]

    parsed = [parse_cells(r) for r in rows_raw]
    parsed = [r for r in parsed if r]

    if not parsed:
        raise ValueError('ردیف جدول یافت نشد')

    hdrs  = parsed[0]
    nrows = parsed[1:]

    return _result(hdrs, nrows,
                   f'Import Web Table (index={table_idx})',
                   [['URL', url[:50]], ['ردیف', len(nrows)], ['ستون', len(hdrs)]])


# ── 8. Import from Another Excel Sheet ────────────────────────────────────

def import_excel_sheet(params, headers, rows):
    """
    This tool tells the JS side to read another sheet.
    The actual read is done by excel.js — here we just pass through.
    """
    sheet_name = params.get('sheet_name', '')
    # In practice, JS calls excel.readSheet(sheet_name) and passes data
    # Here we just validate and return what was passed
    if not rows:
        raise ValueError('داده‌ای دریافت نشد — شیت را در JS بخوانید')

    return _result(headers, rows,
                   f'Import Sheet: {sheet_name}',
                   [['ردیف', len(rows)], ['ستون', len(headers)]])


# ── 9. Import Parquet (via Arrow/pandas) ──────────────────────────────────

def import_parquet(params, headers, rows):
    file_path = params.get('file_path', '')
    if not file_path:
        raise ValueError('file_path الزامی است')

    try:
        import pandas as pd
        df    = pd.read_parquet(file_path)
        hdrs  = list(df.columns)
        nrows = df.fillna('').values.tolist()
        return _result(hdrs, nrows,
                       'Import Parquet',
                       [['ردیف', len(nrows)], ['ستون', len(hdrs)]])
    except ImportError:
        raise ValueError('pandas لازم است: pip install pandas pyarrow')
    except Exception as e:
        raise ValueError(f'خواندن Parquet ناموفق: {e}')


# ── 10. Merge Datasets ────────────────────────────────────────────────────

def merge_datasets(params, headers, rows):
    """
    Merge current sheet with another dataset (passed as content)
    Supports: inner, left, right, outer joins
    """
    content      = params.get('right_content', '')
    delimiter    = params.get('right_delimiter', ',')
    left_key     = params.get('left_key', headers[0] if headers else '')
    right_key    = params.get('right_key', '')
    join_type    = params.get('join_type', 'left')  # inner|left|right|outer

    if not content:
        raise ValueError('right_content الزامی است')

    # Parse right dataset
    reader     = csv.reader(io.StringIO(content), delimiter=delimiter)
    right_all  = list(reader)
    if not right_all:
        raise ValueError('داده راست خالی است')

    r_headers  = [h.strip() for h in right_all[0]]
    r_rows     = [[c.strip() for c in r] for r in right_all[1:]]
    right_key  = right_key or r_headers[0]

    lki = next((i for i, h in enumerate(headers) if h == left_key), None)
    rki = next((i for i, h in enumerate(r_headers) if h == right_key), None)

    if lki is None:
        raise ValueError(f'کلید چپ "{left_key}" یافت نشد')
    if rki is None:
        raise ValueError(f'کلید راست "{right_key}" یافت نشد')

    # Build right lookup
    right_lookup = defaultdict(list)
    for r in r_rows:
        key = str(r[rki] if rki < len(r) else '')
        right_lookup[key].append(r)

    # Suffix for duplicate columns
    r_only_hdrs = [h for i, h in enumerate(r_headers) if i != rki]
    r_suffixed  = [f'{h}_right' if h in headers else h for h in r_only_hdrs]
    merged_hdrs = headers + r_suffixed

    empty_right = [None] * len(r_only_hdrs)
    merged_rows = []
    matched_right_keys = set()

    # Left side
    for left_row in rows:
        key = str(left_row[lki] if lki < len(left_row) else '')
        matches = right_lookup.get(key, [])
        if matches:
            matched_right_keys.add(key)
            for r_row in matches:
                r_vals = [r_row[i] if i < len(r_row) else None
                          for i in range(len(r_headers)) if i != rki]
                merged_rows.append(list(left_row) + r_vals)
        elif join_type in ('left', 'outer'):
            merged_rows.append(list(left_row) + empty_right)

    # Right-only rows
    if join_type in ('right', 'outer'):
        for key, r_row_list in right_lookup.items():
            if key not in matched_right_keys:
                for r_row in r_row_list:
                    r_vals = [r_row[i] if i < len(r_row) else None
                              for i in range(len(r_headers)) if i != rki]
                    merged_rows.append([None]*len(headers) + r_vals)

    return _result(merged_hdrs, merged_rows,
                   f'Merge ({join_type} join)',
                   [['کلید چپ', left_key],
                    ['کلید راست', right_key],
                    ['join type', join_type],
                    ['ردیف خروجی', len(merged_rows)]])
