# cython: language_level=3
"""
SWAK — Data Engineering Module (16 tools)
"""

import re
import json
import math
import hashlib
from collections import defaultdict
from datetime import datetime


def run(tool_id: str, params: dict, headers: list, rows: list) -> dict:
    fn_map = {
        'generate-ids':      generate_ids,
        'hash-column':       hash_column,
        'json-flatten':      json_flatten,
        'json-extract':      json_extract,
        'array-expand':      array_expand,
        'window-function':   window_function,
        'data-lineage':      data_lineage,
        'schema-validate':   schema_validate,
        'data-masking':      data_masking,
        'partition-data':    partition_data,
        'sample-data':       sample_data,
        'data-diff':         data_diff,
        'sql-transform':     sql_transform,
        'generate-sequence': generate_sequence,
        'lookup-table':      lookup_table,
        'conditional-logic': conditional_logic,
    }
    fn = fn_map.get(tool_id)
    if not fn:
        raise ValueError(f'ابزار ناشناخته: {tool_id}')
    return fn(params, headers, list(rows))


def _is_empty(v):
    return v is None or (isinstance(v, float) and math.isnan(v)) or (isinstance(v, str) and v.strip() == '')

def _to_number(v):
    if _is_empty(v): return None
    try: return float(str(v).replace(',',''))
    except: return None

def _result(headers, rows, title, stats, note=''):
    return {'headers': headers, 'rows': rows,
            'summary': {'title': title, 'stats': stats, 'note': note}}


def generate_ids(params, headers, rows):
    style  = params.get('style', 'uuid')
    prefix = params.get('prefix', '')
    start  = int(params.get('start', 1))
    col    = params.get('column_name', 'id')

    import random, time
    ids = []
    for i, row in enumerate(rows):
        if style == 'uuid':
            uid = '%08x-%04x-%04x-%04x-%012x' % (
                random.randint(0, 0xffffffff), random.randint(0, 0xffff),
                random.randint(0x4000, 0x4fff), random.randint(0x8000, 0xbfff),
                random.randint(0, 0xffffffffffff))
            ids.append(f'{prefix}{uid}')
        elif style == 'sequential':
            ids.append(f'{prefix}{start + i}')
        elif style == 'hash':
            h = hashlib.md5(str(row).encode()).hexdigest()[:12]
            ids.append(f'{prefix}{h}')
        elif style == 'timestamp':
            ts = int(time.time() * 1000) + i
            ids.append(f'{prefix}{ts}')

    new_headers = [col] + headers
    new_rows    = [[ids[i]] + list(row) for i, row in enumerate(rows)]
    return _result(new_headers, new_rows, f'تولید ID ({style})',
                   [['style', style], ['ID تولید شده', len(ids)]])


def hash_column(params, headers, rows):
    col      = params.get('column', headers[0])
    algo     = params.get('algorithm', 'md5')
    salt     = params.get('salt', '')
    ci       = headers.index(col)
    col_name = f'{col}_hash'

    algos = {'md5': hashlib.md5, 'sha256': hashlib.sha256,
             'sha512': hashlib.sha512, 'sha1': hashlib.sha1}
    fn = algos.get(algo, hashlib.md5)

    new_headers = headers + [col_name]
    new_rows    = []
    for row in rows:
        v   = str(row[ci] if ci < len(row) else '') + salt
        h   = fn(v.encode()).hexdigest()
        new_rows.append(list(row) + [h])

    return _result(new_headers, new_rows, f'Hash — {col} ({algo})',
                   [['الگوریتم', algo], ['ستون جدید', col_name]])


def json_flatten(params, headers, rows):
    col   = params.get('column', headers[0])
    ci    = headers.index(col)
    sep   = params.get('separator', '.')
    depth = int(params.get('max_depth', 2))

    def flatten(obj, prefix='', d=0):
        result = {}
        if isinstance(obj, dict) and d < depth:
            for k, v in obj.items():
                key = f'{prefix}{sep}{k}' if prefix else k
                result.update(flatten(v, key, d+1))
        else:
            result[prefix] = obj
        return result

    all_keys   = set()
    flat_data  = []
    for row in rows:
        v = row[ci] if ci < len(row) else None
        try:
            obj = json.loads(str(v)) if isinstance(v, str) else v
            fd  = flatten(obj) if isinstance(obj, dict) else {'value': obj}
        except: fd = {'value': str(v)}
        all_keys.update(fd.keys())
        flat_data.append(fd)

    new_cols    = sorted(all_keys)
    new_headers = [h for i,h in enumerate(headers) if i != ci] + new_cols
    new_rows    = [[row[i] if i < len(row) else None for i in range(len(headers)) if i != ci]
                   + [fd.get(k) for k in new_cols]
                   for row, fd in zip(rows, flat_data)]

    return _result(new_headers, new_rows, f'JSON Flatten — {col}',
                   [['ستون جدید', len(new_cols)]])


def json_extract(params, headers, rows):
    col      = params.get('column', headers[0])
    path     = params.get('json_path', '')
    col_name = params.get('output_column', f'{col}_extracted')
    ci       = headers.index(col)

    def extract(v):
        try:
            obj = json.loads(str(v))
            for key in path.split('.'):
                if isinstance(obj, dict): obj = obj.get(key)
                elif isinstance(obj, list) and key.isdigit(): obj = obj[int(key)]
                else: return None
            return obj
        except: return None

    new_headers = headers + [col_name]
    new_rows    = [list(row) + [extract(row[ci] if ci < len(row) else None)] for row in rows]
    extracted   = sum(1 for r in new_rows if r[-1] is not None)

    return _result(new_headers, new_rows, f'JSON Extract — {path}',
                   [['path', path], ['استخراج موفق', extracted]])


def array_expand(params, headers, rows):
    col    = params.get('column', headers[0])
    sep    = params.get('separator', ',')
    ci     = headers.index(col)

    new_rows = []
    for row in rows:
        v     = str(row[ci] if ci < len(row) else '')
        items = [x.strip() for x in v.split(sep)]
        for item in items:
            new_row = list(row)
            new_row[ci] = item
            new_rows.append(new_row)

    return _result(headers, new_rows, f'Array Expand — {col}',
                   [['ردیف اصلی', len(rows)], ['ردیف خروجی', len(new_rows)]])


def window_function(params, headers, rows):
    col       = params.get('column', headers[0])
    fn_name   = params.get('function', 'row_number')
    partition = params.get('partition_by', '')
    order_col = params.get('order_by', col)
    ci        = headers.index(col)
    pi        = headers.index(partition) if partition in headers else None
    oi        = headers.index(order_col) if order_col in headers else ci

    # Group by partition
    groups = defaultdict(list)
    for i, row in enumerate(rows):
        key = str(row[pi] if pi is not None and pi < len(row) else '_all_')
        groups[key].append(i)

    results = [None] * len(rows)
    for key, idxs in groups.items():
        sorted_idxs = sorted(idxs, key=lambda i: _to_number(rows[i][oi] if oi < len(rows[i]) else None) or 0)
        vals = [_to_number(rows[i][ci] if ci < len(rows[i]) else None) or 0 for i in sorted_idxs]
        cumsum = 0
        mean_v = sum(vals)/len(vals) if vals else 0
        for rank, (i, v) in enumerate(zip(sorted_idxs, vals)):
            cumsum += v
            if fn_name == 'row_number': results[i] = rank + 1
            elif fn_name == 'rank':     results[i] = rank + 1
            elif fn_name == 'cumsum':   results[i] = round(cumsum, 4)
            elif fn_name == 'lag':      results[i] = vals[rank-1] if rank > 0 else None
            elif fn_name == 'lead':     results[i] = vals[rank+1] if rank < len(vals)-1 else None
            elif fn_name == 'pct_rank': results[i] = round(rank/(len(vals)-1)*100,2) if len(vals)>1 else 0
            elif fn_name == 'mean':     results[i] = round(mean_v, 4)

    col_name    = f'{col}_{fn_name}'
    new_headers = headers + [col_name]
    new_rows    = [list(row) + [results[i]] for i, row in enumerate(rows)]

    return _result(new_headers, new_rows, f'Window: {fn_name}',
                   [['function', fn_name], ['partition', partition or 'none']])


def data_lineage(params, headers, rows):
    """Track data transformations applied"""
    transformations = params.get('transformations', [])
    out_rows = [
        ['منبع اصلی', f'{len(rows)} ردیف × {len(headers)} ستون'],
        ['تاریخ', datetime.now().strftime('%Y-%m-%d %H:%M')],
    ]
    for i, t in enumerate(transformations if isinstance(transformations, list) else []):
        out_rows.append([f'گام {i+1}', str(t)])
    out_rows.append(['وضعیت نهایی', f'{len(rows)} ردیف × {len(headers)} ستون'])

    return _result(['step','description'], out_rows, 'نسب‌شناسی داده',
                   [['گام‌های تبدیل', len(transformations)]])


def schema_validate(params, headers, rows):
    schema = params.get('schema', {})
    # schema: {col_name: {type, required, min, max, pattern}}
    violations = []
    for i, row in enumerate(rows):
        for col, rules in schema.items():
            if col not in headers: continue
            ci  = headers.index(col)
            v   = row[ci] if ci < len(row) else None
            if rules.get('required') and _is_empty(v):
                violations.append([i+1, col, 'required', 'مقدار الزامی است'])
                continue
            if not _is_empty(v):
                n = _to_number(v)
                if rules.get('type') == 'number' and n is None:
                    violations.append([i+1, col, 'type', f'عدد نیست: {v}'])
                if rules.get('min') is not None and n is not None and n < rules['min']:
                    violations.append([i+1, col, 'min', f'{v} < {rules["min"]}'])
                if rules.get('max') is not None and n is not None and n > rules['max']:
                    violations.append([i+1, col, 'max', f'{v} > {rules["max"]}'])
                if rules.get('pattern'):
                    if not re.match(rules['pattern'], str(v)):
                        violations.append([i+1, col, 'pattern', f'الگو نمی‌خورد: {v[:30]}'])

    return _result(['row','column','rule','message'],
                   violations[:500], 'اعتبارسنجی Schema',
                   [['نقض', len(violations)], ['وضعیت', '✅ معتبر' if not violations else '❌ نقض']])


def data_masking(params, headers, rows):
    col     = params.get('column', headers[0])
    method  = params.get('method', 'partial')  # full|partial|hash|fake
    ci      = headers.index(col)

    def mask(v):
        s = str(v or '')
        if method == 'full':    return '*' * len(s)
        if method == 'partial': return s[:2] + '*'*(len(s)-4) + s[-2:] if len(s) > 4 else '***'
        if method == 'hash':    return hashlib.md5(s.encode()).hexdigest()[:12]
        if method == 'fake':
            if '@' in s: return 'user@example.com'
            if s.isdigit(): return '0' * len(s)
            return 'REDACTED'
        return s

    new_rows = [list(r) for r in rows]
    for i, row in enumerate(new_rows):
        if ci < len(row) and not _is_empty(row[ci]):
            new_rows[i][ci] = mask(row[ci])

    return _result(headers, new_rows, f'Data Masking — {col}',
                   [['method', method], ['ستون', col]])


def partition_data(params, headers, rows):
    col      = params.get('column', headers[0])
    strategy = params.get('strategy', 'value')  # value|range|hash
    n_parts  = int(params.get('n_partitions', 4))
    ci       = headers.index(col)

    if strategy == 'value':
        parts = defaultdict(list)
        for row in rows:
            key = str(row[ci] if ci < len(row) else '')
            parts[key].append(row)
        result_rows = [[k, len(v)] for k, v in sorted(parts.items())]
        part_headers = ['partition_key', 'row_count']
    elif strategy == 'hash':
        parts = [[] for _ in range(n_parts)]
        for row in rows:
            h = int(hashlib.md5(str(row[ci] if ci < len(row) else '').encode()).hexdigest(), 16)
            parts[h % n_parts].append(row)
        result_rows = [[i, len(p)] for i, p in enumerate(parts)]
        part_headers = ['partition_id', 'row_count']
    else:  # range
        nums = sorted([_to_number(r[ci] if ci < len(r) else None) for r in rows if _to_number(r[ci] if ci < len(r) else None) is not None])
        if not nums:
            raise ValueError('مقدار عددی یافت نشد')
        mn, mx = nums[0], nums[-1]
        rng    = (mx - mn) / n_parts or 1
        result_rows = [[f'{mn+i*rng:.2f}–{mn+(i+1)*rng:.2f}', sum(1 for v in nums if mn+i*rng <= v < mn+(i+1)*rng)] for i in range(n_parts)]
        part_headers = ['range', 'row_count']

    return _result(part_headers, result_rows, f'تقسیم‌بندی ({strategy})',
                   [['استراتژی', strategy], ['پارتیشن‌ها', len(result_rows)]])


def sample_data(params, headers, rows):
    import random
    method = params.get('method', 'random')
    n      = int(params.get('n', min(100, len(rows))))
    seed   = int(params.get('seed', 42))
    random.seed(seed)

    if method == 'random':
        sample = random.sample(rows, min(n, len(rows)))
    elif method == 'first':
        sample = rows[:n]
    elif method == 'last':
        sample = rows[-n:]
    elif method == 'systematic':
        step   = max(1, len(rows)//n)
        sample = rows[::step][:n]
    else:
        sample = random.sample(rows, min(n, len(rows)))

    return _result(headers, sample, f'نمونه‌گیری ({method})',
                   [['روش', method], ['نمونه', len(sample)], ['کل', len(rows)]])


def data_diff(params, headers, rows):
    content2 = params.get('dataset2', '[]')
    key_col  = params.get('key_column', headers[0])
    try:
        rows2 = json.loads(content2)
        if isinstance(rows2, list) and rows2 and isinstance(rows2[0], dict):
            hdrs2 = list(rows2[0].keys())
            rows2 = [[r.get(h) for h in hdrs2] for r in rows2]
        else:
            hdrs2 = headers
    except: hdrs2, rows2 = headers, []

    ki   = headers.index(key_col)
    set1 = {str(r[ki] if ki < len(r) else '') for r in rows}
    ki2  = hdrs2.index(key_col) if key_col in hdrs2 else 0
    set2 = {str(r[ki2] if ki2 < len(r) else '') for r in rows2}

    added   = set2 - set1
    removed = set1 - set2
    common  = set1 & set2

    out_rows = [['در هر دو', len(common)],
                ['فقط در dataset 1', len(removed)],
                ['فقط در dataset 2', len(added)]]
    if removed: out_rows.append(['کلیدهای حذف شده', ', '.join(list(removed)[:10])])
    if added:   out_rows.append(['کلیدهای اضافه شده', ', '.join(list(added)[:10])])

    return _result(['status','count'], out_rows, 'مقایسه Data Diff',
                   [['تفاوت', len(added)+len(removed)]])


def sql_transform(params, headers, rows):
    """Apply SQL-like SELECT/WHERE/ORDER transformations using Python"""
    select_cols = params.get('select', '*')
    where_expr  = params.get('where', '')
    order_col   = params.get('order_by', '')
    limit       = int(params.get('limit', len(rows)))

    # SELECT
    if select_cols == '*':
        sel_headers, sel_idxs = headers, list(range(len(headers)))
    else:
        cols = [c.strip() for c in select_cols.split(',')]
        sel_idxs   = [headers.index(c) for c in cols if c in headers]
        sel_headers = [headers[i] for i in sel_idxs]

    # WHERE
    if where_expr:
        def match(row):
            ctx = {h.replace(' ','_'): row[i] if i < len(row) else None for i, h in enumerate(headers)}
            safe = where_expr.replace(' AND ',' and ').replace(' OR ',' or ').replace(' NOT ',' not ')
            try: return bool(eval(safe, {'__builtins__':{}}, ctx))
            except: return True
        result_rows = [r for r in rows if match(r)]
    else:
        result_rows = list(rows)

    # ORDER BY
    if order_col and order_col in headers:
        oi = headers.index(order_col)
        desc = order_col.endswith(' DESC') or params.get('order_dir','asc') == 'desc'
        result_rows.sort(key=lambda r: (_to_number(r[oi] if oi < len(r) else None) or 0), reverse=desc)

    # SELECT columns and LIMIT
    final = [[r[i] if i < len(r) else None for i in sel_idxs] for r in result_rows[:limit]]

    return _result(sel_headers, final, 'SQL Transform',
                   [['SELECT', select_cols[:30]], ['WHERE', where_expr[:30] if where_expr else 'none'],
                    ['ردیف خروجی', len(final)]])


def generate_sequence(params, headers, rows):
    col_name = params.get('column_name', 'sequence')
    start    = float(params.get('start', 1))
    step     = float(params.get('step', 1))
    repeat   = int(params.get('repeat', 1))

    seq = []
    val = start
    for i in range(len(rows)):
        seq.append(round(val, 8))
        if (i+1) % repeat == 0:
            val += step

    new_headers = [col_name] + headers
    new_rows    = [[seq[i]] + list(row) for i, row in enumerate(rows)]

    return _result(new_headers, new_rows, 'تولید دنباله',
                   [['شروع', start], ['گام', step], ['ردیف', len(rows)]])


def lookup_table(params, headers, rows):
    lookup_json = params.get('lookup_table', '{}')
    col         = params.get('column', headers[0])
    output_col  = params.get('output_column', f'{col}_lookup')
    default_val = params.get('default', None)
    ci          = headers.index(col)

    try:
        lookup = json.loads(lookup_json)
    except: raise ValueError('lookup_table باید JSON معتبر باشد')

    new_headers = headers + [output_col]
    new_rows    = [list(row) + [lookup.get(str(row[ci] if ci < len(row) else ''), default_val)]
                   for row in rows]
    matched = sum(1 for r in new_rows if r[-1] is not None)

    return _result(new_headers, new_rows, f'Lookup — {col}',
                   [['تطبیق یافته', matched], ['نتطبق', len(rows)-matched]])


def conditional_logic(params, headers, rows):
    col_name  = params.get('output_column', 'result')
    conditions= params.get('conditions', [])
    # conditions: [{expr, value}, ...], default
    default   = params.get('default', None)

    new_headers = headers + [col_name]
    new_rows    = []
    for row in rows:
        ctx = {h.replace(' ','_'): row[i] if i < len(row) else None for i, h in enumerate(headers)}
        result = default
        for cond in (conditions if isinstance(conditions, list) else []):
            expr = cond.get('expr','').replace(' AND ',' and ').replace(' OR ',' or ')
            try:
                if eval(expr, {'__builtins__':{}}, ctx):
                    result = cond.get('value', default)
                    break
            except: pass
        new_rows.append(list(row) + [result])

    return _result(new_headers, new_rows, 'منطق شرطی',
                   [['شرط‌ها', len(conditions)], ['ستون جدید', col_name]])
