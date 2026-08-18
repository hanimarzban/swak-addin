# cython: language_level=3
# cython: boundscheck=False
"""
SWAK — Transform Module (16 tools)
Reshape, pivot, sort, and restructure data
"""

import math
import re
from collections import defaultdict


def run(tool_id: str, params: dict, headers: list, rows: list) -> dict:
    fn_map = {
        'sort-data':          sort_data,
        'group-by':           group_by,
        'pivot-table':        pivot_table,
        'unpivot':            unpivot,
        'transpose':          transpose,
        'add-column':         add_column,
        'rename-columns':     rename_columns,
        'reorder-columns':    reorder_columns,
        'select-columns':     select_columns,
        'drop-columns':       drop_columns,
        'add-index':          add_index,
        'calculate-column':   calculate_column,
        'bin-column':         bin_column,
        'rank-column':        rank_column,
        'running-total':      running_total,
        'percent-of-total':   percent_of_total,
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

def _result(headers, rows, title, stats, note=''):
    return {'headers': headers, 'rows': rows,
            'summary': {'title': title, 'stats': stats, 'note': note}}


# ── 1. Sort Data ──────────────────────────────────────────────────────────

def sort_data(params, headers, rows):
    """Sort by one or more columns"""
    sort_cols = params.get('columns', [headers[0]])
    if isinstance(sort_cols, str):
        sort_cols = [sort_cols]
    directions = params.get('directions', ['asc'] * len(sort_cols))
    if isinstance(directions, str):
        directions = [directions]

    col_idxs = [_col_idx(headers, c) for c in sort_cols]

    def sort_key(row):
        parts = []
        for i, ci in enumerate(col_idxs):
            v   = row[ci] if ci < len(row) else None
            n   = _to_number(v)
            key = n if n is not None else (str(v) if not _is_empty(v) else '')
            parts.append(key)
        return parts

    reverse_flags = [d.lower() == 'desc' for d in directions]

    # Multi-key sort: Python's sort is stable
    result = list(rows)
    for ci_pos in reversed(range(len(col_idxs))):
        ci  = col_idxs[ci_pos]
        rev = reverse_flags[ci_pos]
        result.sort(key=lambda r: (
            (0, _to_number(r[ci])) if _to_number(r[ci]) is not None
            else (1, str(r[ci] if ci < len(r) else ''))
        ), reverse=rev)

    return _result(headers, result, 'مرتب‌سازی',
                   [['ستون', ', '.join(sort_cols)],
                    ['جهت', ', '.join(directions)],
                    ['ردیف', len(result)]])


# ── 2. Group By ───────────────────────────────────────────────────────────

def group_by(params, headers, rows):
    """Aggregate rows by group column(s)"""
    group_cols  = params.get('group_columns', [headers[0]])
    if isinstance(group_cols, str):
        group_cols = [group_cols]
    agg_col     = params.get('agg_column', '')
    agg_fn      = params.get('agg_function', 'count')  # count|sum|mean|min|max|list

    group_idxs  = [_col_idx(headers, c) for c in group_cols]
    agg_ci      = _col_idx(headers, agg_col) if agg_col else None

    groups = defaultdict(list)
    for row in rows:
        key = tuple(str(row[ci] if ci < len(row) else '') for ci in group_idxs)
        val = row[agg_ci] if (agg_ci is not None and agg_ci < len(row)) else None
        groups[key].append(val)

    new_headers = group_cols + ([f'{agg_col}_{agg_fn}' if agg_col else 'count'])
    new_rows    = []

    for key, vals in sorted(groups.items()):
        nums = [_to_number(v) for v in vals if _to_number(v) is not None]
        if agg_fn == 'count':  agg_val = len(vals)
        elif agg_fn == 'sum':  agg_val = sum(nums) if nums else 0
        elif agg_fn == 'mean': agg_val = round(sum(nums)/len(nums), 4) if nums else None
        elif agg_fn == 'min':  agg_val = min(nums) if nums else None
        elif agg_fn == 'max':  agg_val = max(nums) if nums else None
        elif agg_fn == 'list': agg_val = ', '.join(str(v) for v in vals if not _is_empty(v))
        else: agg_val = len(vals)
        new_rows.append(list(key) + [agg_val])

    return _result(new_headers, new_rows, 'گروه‌بندی',
                   [['گروه', ', '.join(group_cols)], ['تابع', agg_fn], ['گروه‌ها', len(new_rows)]])


# ── 3. Pivot Table ────────────────────────────────────────────────────────

def pivot_table(params, headers, rows):
    row_col  = params.get('row_column')
    col_col  = params.get('col_column')
    val_col  = params.get('value_column')
    agg_fn   = params.get('agg_function', 'sum')

    if not row_col or not col_col or not val_col:
        raise ValueError('row_column، col_column، value_column الزامی است')

    ri = _col_idx(headers, row_col)
    ci = _col_idx(headers, col_col)
    vi = _col_idx(headers, val_col)

    # Collect unique col values (for pivot columns)
    col_vals = sorted(set(str(r[ci] if ci < len(r) else '') for r in rows))
    row_keys = sorted(set(str(r[ri] if ri < len(r) else '') for r in rows))

    # Build aggregation dict
    data = defaultdict(lambda: defaultdict(list))
    for row in rows:
        rk = str(row[ri] if ri < len(row) else '')
        ck = str(row[ci] if ci < len(row) else '')
        vv = _to_number(row[vi] if vi < len(row) else None)
        if vv is not None:
            data[rk][ck].append(vv)

    def agg(vals):
        if not vals: return None
        if agg_fn == 'sum':   return sum(vals)
        if agg_fn == 'mean':  return round(sum(vals)/len(vals), 4)
        if agg_fn == 'count': return len(vals)
        if agg_fn == 'min':   return min(vals)
        if agg_fn == 'max':   return max(vals)
        return sum(vals)

    new_headers = [row_col] + col_vals
    new_rows    = [[rk] + [agg(data[rk].get(ck, [])) for ck in col_vals]
                   for rk in row_keys]

    return _result(new_headers, new_rows, 'Pivot Table',
                   [['ردیف', row_col], ['ستون', col_col], ['مقدار', val_col],
                    ['تابع', agg_fn], ['ستون‌های pivot', len(col_vals)]])


# ── 4. Unpivot (melt) ─────────────────────────────────────────────────────

def unpivot(params, headers, rows):
    id_cols   = params.get('id_columns', [headers[0]])
    if isinstance(id_cols, str):
        id_cols = [id_cols]
    var_name  = params.get('variable_name', 'variable')
    val_name  = params.get('value_name', 'value')

    id_idxs   = [_col_idx(headers, c) for c in id_cols]
    val_idxs  = [i for i in range(len(headers)) if i not in id_idxs]
    val_names = [headers[i] for i in val_idxs]

    new_headers = id_cols + [var_name, val_name]
    new_rows    = []
    for row in rows:
        id_vals = [row[i] if i < len(row) else None for i in id_idxs]
        for vi, vn in zip(val_idxs, val_names):
            new_rows.append(id_vals + [vn, row[vi] if vi < len(row) else None])

    return _result(new_headers, new_rows, 'Unpivot',
                   [['ID ستون‌ها', len(id_cols)], ['مقدار ستون‌ها', len(val_idxs)],
                    ['ردیف خروجی', len(new_rows)]])


# ── 5. Transpose ──────────────────────────────────────────────────────────

def transpose(params, headers, rows):
    use_header = params.get('use_first_col_as_header', 'true') == 'true'
    all_rows   = [headers] + [list(r) for r in rows]
    transposed = list(map(list, zip(*all_rows)))

    if use_header:
        new_headers = [str(transposed[0][0])] + [str(v) for v in transposed[0][1:]]
        new_rows    = [r[1:] for r in transposed[1:]]  # skip original header col
    else:
        new_headers = [f'col_{i}' for i in range(len(transposed[0]))]
        new_rows    = transposed

    # Actually transpose properly
    matrix = [headers] + [list(r) for r in rows]
    t      = [list(col) for col in zip(*matrix)]
    if use_header:
        new_headers = [str(t[i][0]) for i in range(len(t))]
        new_rows    = [[t[i][j] for i in range(len(t))] for j in range(1, len(t[0]))]
    else:
        new_headers = [f'col_{i+1}' for i in range(len(t))]
        new_rows    = [[t[i][j] for i in range(len(t))] for j in range(len(t[0]))]

    return _result(new_headers, new_rows, 'جابجایی (Transpose)',
                   [['ردیف اصلی', len(rows)], ['ستون اصلی', len(headers)],
                    ['ردیف جدید', len(new_rows)], ['ستون جدید', len(new_headers)]])


# ── 6. Add Calculated Column ──────────────────────────────────────────────

def add_column(params, headers, rows):
    name  = params.get('column_name', 'new_column')
    value = params.get('default_value', '')

    new_headers = headers + [name]
    new_rows    = [list(r) + [value] for r in rows]

    return _result(new_headers, new_rows, f'افزودن ستون — {name}',
                   [['ستون جدید', name], ['مقدار پیش‌فرض', value]])


# ── 7. Rename Columns ─────────────────────────────────────────────────────

def rename_columns(params, headers, rows):
    """params.mapping: {'old_name': 'new_name', ...}"""
    mapping     = params.get('mapping', {})
    new_headers = [mapping.get(h, h) for h in headers]
    renamed     = sum(1 for h in headers if h in mapping)

    return _result(new_headers, rows, 'تغییر نام ستون',
                   [['تغییر یافته', renamed], ['بدون تغییر', len(headers) - renamed]])


# ── 8. Reorder Columns ────────────────────────────────────────────────────

def reorder_columns(params, headers, rows):
    """params.order: list of column names in desired order"""
    order       = params.get('order', headers)
    col_idxs    = []
    new_headers = []
    for col in order:
        if col in headers:
            idx = headers.index(col)
            col_idxs.append(idx)
            new_headers.append(col)

    # Add any remaining columns not specified
    for i, h in enumerate(headers):
        if h not in order:
            col_idxs.append(i)
            new_headers.append(h)

    new_rows = [[row[i] if i < len(row) else None for i in col_idxs] for row in rows]

    return _result(new_headers, new_rows, 'ترتیب ستون‌ها',
                   [['ستون‌ها', len(new_headers)]])


# ── 9. Select Columns ─────────────────────────────────────────────────────

def select_columns(params, headers, rows):
    cols     = params.get('columns', headers)
    if isinstance(cols, str):
        cols = [c.strip() for c in cols.split(',')]
    idxs     = [_col_idx(headers, c) for c in cols]
    new_rows = [[row[i] if i < len(row) else None for i in idxs] for row in rows]

    return _result(cols, new_rows, 'انتخاب ستون',
                   [['ستون انتخابی', len(cols)], ['ستون حذف شده', len(headers) - len(cols)]])


# ── 10. Drop Columns ──────────────────────────────────────────────────────

def drop_columns(params, headers, rows):
    drop     = params.get('columns', [])
    if isinstance(drop, str):
        drop = [c.strip() for c in drop.split(',')]
    drop_set = set(drop)
    keep_idx = [i for i, h in enumerate(headers) if h not in drop_set]
    new_hdrs = [headers[i] for i in keep_idx]
    new_rows = [[row[i] if i < len(row) else None for i in keep_idx] for row in rows]

    return _result(new_hdrs, new_rows, 'حذف ستون',
                   [['حذف شده', len(drop)], ['باقیمانده', len(new_hdrs)]])


# ── 11. Add Index ─────────────────────────────────────────────────────────

def add_index(params, headers, rows):
    name    = params.get('column_name', 'index')
    start   = int(params.get('start', 1))
    new_hdrs = [name] + headers
    new_rows = [[start + i] + list(row) for i, row in enumerate(rows)]

    return _result(new_hdrs, new_rows, 'افزودن ایندکس',
                   [['شروع', start], ['ردیف', len(new_rows)]])


# ── 12. Calculate Column (formula) ───────────────────────────────────────

def calculate_column(params, headers, rows):
    name    = params.get('column_name', 'calculated')
    formula = params.get('formula', '')

    if not formula:
        raise ValueError('فرمول الزامی است')

    errors  = 0
    new_hdrs = headers + [name]
    new_rows = [list(r) for r in rows]

    for i, row in enumerate(new_rows):
        ctx = {h.replace(' ', '_'): _to_number(row[j] if j < len(row) else None) or 0
               for j, h in enumerate(headers)}
        ctx['math'] = math
        safe_formula = formula
        for h in headers:
            safe_formula = safe_formula.replace(h, h.replace(' ', '_'))
        try:
            result = eval(safe_formula, {'__builtins__': {'abs': abs, 'round': round, 'max': max, 'min': min}}, ctx)
            new_rows[i].append(result)
        except Exception:
            new_rows[i].append(None)
            errors += 1

    return _result(new_hdrs, new_rows, f'محاسبه ستون — {name}',
                   [['فرمول', formula[:50]], ['خطا', errors]])


# ── 13. Bin Column ────────────────────────────────────────────────────────

def bin_column(params, headers, rows):
    ci      = _col_idx(headers, params['column'])
    n_bins  = int(params.get('n_bins', 5))
    method  = params.get('method', 'equal_width')  # equal_width | equal_freq | custom
    labels  = params.get('labels', [])

    nums = [(_to_number(r[ci] if ci < len(r) else None), i) for i, r in enumerate(rows)]
    valid_nums = [(n, i) for n, i in nums if n is not None]

    if not valid_nums:
        return _result(headers + [f'{params["column"]}_bin'], rows,
                       'بیننینگ', [['خطا', 'مقدار عددی یافت نشد']])

    vals_sorted = sorted(v for v, _ in valid_nums)
    mn, mx = vals_sorted[0], vals_sorted[-1]

    if method == 'equal_width':
        edges = [mn + i * (mx - mn) / n_bins for i in range(n_bins + 1)]
    elif method == 'equal_freq':
        step  = max(1, len(vals_sorted) // n_bins)
        edges = [vals_sorted[0]] + [vals_sorted[min(i*step, len(vals_sorted)-1)] for i in range(1, n_bins)] + [vals_sorted[-1]]
    else:
        edges = [float(e) for e in params.get('custom_edges', [])]

    def find_bin(v):
        if v is None: return None
        for b in range(len(edges) - 1):
            lo = edges[b]
            hi = edges[b + 1]
            if b == len(edges) - 2:
                if lo <= v <= hi:
                    return labels[b] if b < len(labels) else f'bin_{b+1}'
            else:
                if lo <= v < hi:
                    return labels[b] if b < len(labels) else f'bin_{b+1}'
        return None

    new_hdrs = headers + [f'{params["column"]}_bin']
    new_rows = [list(r) + [find_bin(_to_number(r[ci] if ci < len(r) else None))] for r in rows]

    return _result(new_hdrs, new_rows, f'بیننینگ — {params["column"]}',
                   [['روش', method], ['تعداد bin', n_bins]])


# ── 14. Rank Column ───────────────────────────────────────────────────────

def rank_column(params, headers, rows):
    ci      = _col_idx(headers, params['column'])
    method  = params.get('method', 'average')  # average | min | max | dense | ordinal
    asc     = params.get('ascending', 'true') == 'true'

    nums    = [(_to_number(r[ci] if ci < len(r) else None), i) for i, r in enumerate(rows)]
    valid   = [(v, i) for v, i in nums if v is not None]
    sorted_ = sorted(valid, key=lambda x: x[0], reverse=not asc)

    ranks   = [None] * len(rows)
    for rank_pos, (v, orig_i) in enumerate(sorted_, 1):
        ranks[orig_i] = rank_pos

    new_hdrs = headers + [f'{params["column"]}_rank']
    new_rows = [list(r) + [ranks[i]] for i, r in enumerate(rows)]

    return _result(new_hdrs, new_rows, f'رتبه‌بندی — {params["column"]}',
                   [['روش', method], ['صعودی', asc]])


# ── 15. Running Total ─────────────────────────────────────────────────────

def running_total(params, headers, rows):
    ci       = _col_idx(headers, params['column'])
    group_ci = _col_idx(headers, params['group_column']) if params.get('group_column') else None

    new_hdrs  = headers + [f'{params["column"]}_cumsum']
    new_rows  = [list(r) for r in rows]
    group_sum = defaultdict(float)

    for i, row in enumerate(new_rows):
        v    = _to_number(row[ci] if ci < len(row) else None) or 0
        gkey = str(row[group_ci] if group_ci is not None and group_ci < len(row) else '_all_')
        group_sum[gkey] += v
        new_rows[i].append(round(group_sum[gkey], 4))

    return _result(new_hdrs, new_rows, f'مجموع تجمعی — {params["column"]}',
                   [['گروه', params.get('group_column', 'بدون گروه')]])


# ── 16. Percent of Total ──────────────────────────────────────────────────

def percent_of_total(params, headers, rows):
    ci        = _col_idx(headers, params['column'])
    group_ci  = _col_idx(headers, params['group_column']) if params.get('group_column') else None
    precision = int(params.get('precision', 2))

    # Calculate totals per group
    group_totals = defaultdict(float)
    for row in rows:
        v    = _to_number(row[ci] if ci < len(row) else None) or 0
        gkey = str(row[group_ci] if group_ci is not None and group_ci < len(row) else '_all_')
        group_totals[gkey] += abs(v)

    new_hdrs = headers + [f'{params["column"]}_pct']
    new_rows = []
    for row in rows:
        v     = _to_number(row[ci] if ci < len(row) else None) or 0
        gkey  = str(row[group_ci] if group_ci is not None and group_ci < len(row) else '_all_')
        total = group_totals[gkey]
        pct   = round((v / total * 100) if total else 0, precision)
        new_rows.append(list(row) + [pct])

    return _result(new_hdrs, new_rows, f'درصد از کل — {params["column"]}',
                   [['گروه', params.get('group_column', 'کل')]])
