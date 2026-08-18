# cython: language_level=3
# cython: boundscheck=False
"""
SWAK — Filter & Search Module (14 tools)
"""

import re
import math
from datetime import datetime


def run(tool_id: str, params: dict, headers: list, rows: list) -> dict:
    fn_map = {
        'filter-basic':        filter_basic,
        'filter-advanced':     filter_advanced,
        'filter-by-date':      filter_by_date,
        'filter-by-value':     filter_by_value,
        'filter-top-n':        filter_top_n,
        'filter-bottom-n':     filter_bottom_n,
        'filter-contains':     filter_contains,
        'filter-regex':        filter_regex,
        'filter-between':      filter_between,
        'search-replace':      search_replace,
        'fuzzy-search':        fuzzy_search,
        'filter-unique':       filter_unique,
        'filter-duplicates':   filter_duplicates,
        'filter-by-condition': filter_by_condition,
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
    return {
        'headers': headers,
        'rows': rows,
        'summary': {'title': title, 'stats': stats, 'note': note}
    }


# ── 1. Basic Filter ───────────────────────────────────────────────────────

def filter_basic(params, headers, rows):
    """Filter rows by a single condition on one column"""
    ci   = _col_idx(headers, params['column'])
    op   = params.get('operator', 'equals')
    val  = params.get('value', '')

    def matches(v):
        if op == 'equals':          return str(v) == str(val)
        if op == 'not_equals':      return str(v) != str(val)
        if op == 'contains':        return str(val).lower() in str(v).lower()
        if op == 'not_contains':    return str(val).lower() not in str(v).lower()
        if op == 'starts_with':     return str(v).lower().startswith(str(val).lower())
        if op == 'ends_with':       return str(v).lower().endswith(str(val).lower())
        if op == 'is_empty':        return _is_empty(v)
        if op == 'is_not_empty':    return not _is_empty(v)
        n = _to_number(v)
        nv = _to_number(val)
        if n is None or nv is None: return False
        if op == 'greater_than':    return n > nv
        if op == 'less_than':       return n < nv
        if op == 'gte':             return n >= nv
        if op == 'lte':             return n <= nv
        return False

    filtered = [r for r in rows if matches(r[ci] if ci < len(r) else None)]
    return _result(headers, filtered, f'فیلتر — {params["column"]}',
                   [['شرط', f'{params["column"]} {op} {val}'],
                    ['یافت شد', len(filtered)],
                    ['حذف شد', len(rows) - len(filtered)]])


# ── 2. Advanced Filter (multi-condition) ──────────────────────────────────

def filter_advanced(params, headers, rows):
    """Multiple conditions with AND/OR logic"""
    conditions = params.get('conditions', [])
    logic      = params.get('logic', 'AND')  # AND | OR

    def row_matches(row):
        results = []
        for cond in conditions:
            try:
                ci  = _col_idx(headers, cond['column'])
                v   = row[ci] if ci < len(row) else None
                op  = cond.get('operator', 'equals')
                val = cond.get('value', '')
                results.append(_apply_op(v, op, val))
            except Exception:
                results.append(False)
        if not results:
            return True
        return all(results) if logic == 'AND' else any(results)

    filtered = [r for r in rows if row_matches(r)]
    return _result(headers, filtered,
                   f'فیلتر پیشرفته ({logic})',
                   [['شرط‌ها', len(conditions)],
                    ['منطق', logic],
                    ['یافت شد', len(filtered)]])


def _apply_op(v, op, val):
    if op == 'equals':       return str(v) == str(val)
    if op == 'not_equals':   return str(v) != str(val)
    if op == 'contains':     return str(val).lower() in str(v).lower()
    if op == 'not_contains': return str(val).lower() not in str(v).lower()
    if op == 'starts_with':  return str(v).lower().startswith(str(val).lower())
    if op == 'ends_with':    return str(v).lower().endswith(str(val).lower())
    if op == 'is_empty':     return _is_empty(v)
    if op == 'is_not_empty': return not _is_empty(v)
    if op == 'regex':
        try: return bool(re.search(str(val), str(v), re.IGNORECASE))
        except: return False
    n, nv = _to_number(v), _to_number(val)
    if n is None or nv is None: return False
    if op == 'greater_than': return n > nv
    if op == 'less_than':    return n < nv
    if op == 'gte':          return n >= nv
    if op == 'lte':          return n <= nv
    return False


# ── 3. Filter By Date ─────────────────────────────────────────────────────

def filter_by_date(params, headers, rows):
    ci       = _col_idx(headers, params['column'])
    op       = params.get('operator', 'after')
    date_val = params.get('value', '')
    date2    = params.get('value2', '')  # for 'between'

    def parse_date(v):
        if not v: return None
        try:
            return datetime.fromisoformat(str(v).replace('/', '-').strip())
        except Exception:
            return None

    ref  = parse_date(date_val)
    ref2 = parse_date(date2)

    def matches(v):
        d = parse_date(v)
        if not d: return False
        if op == 'after':   return d > ref
        if op == 'before':  return d < ref
        if op == 'on':      return d.date() == ref.date()
        if op == 'between': return ref and ref2 and ref <= d <= ref2
        if op == 'year':    return d.year == int(date_val)
        if op == 'month':   return d.month == int(date_val)
        return False

    filtered = [r for r in rows if matches(r[ci] if ci < len(r) else None)]
    return _result(headers, filtered, f'فیلتر تاریخ — {params["column"]}',
                   [['شرط', f'{op} {date_val}'], ['یافت شد', len(filtered)]])


# ── 4. Filter By Value List ───────────────────────────────────────────────

def filter_by_value(params, headers, rows):
    ci     = _col_idx(headers, params['column'])
    values = [v.strip() for v in params.get('values', '').split(',')]
    negate = params.get('negate', 'false') == 'true'

    value_set = set(values)
    def matches(v):
        hit = str(v).strip() in value_set
        return not hit if negate else hit

    filtered = [r for r in rows if matches(r[ci] if ci < len(r) else None)]
    return _result(headers, filtered, f'فیلتر مقدار — {params["column"]}',
                   [['مقادیر', ', '.join(values[:5])], ['یافت شد', len(filtered)]])


# ── 5. Filter Top N ───────────────────────────────────────────────────────

def filter_top_n(params, headers, rows):
    ci  = _col_idx(headers, params['column'])
    n   = int(params.get('n', 10))
    pct = params.get('mode', 'count') == 'percent'

    scored = [(r, _to_number(r[ci] if ci < len(r) else None)) for r in rows]
    scored = [(r, v) for r, v in scored if v is not None]
    scored.sort(key=lambda x: x[1], reverse=True)

    if pct:
        count = max(1, int(len(scored) * n / 100))
    else:
        count = min(n, len(scored))

    result = [r for r, _ in scored[:count]]
    return _result(headers, result, f'Top {n} — {params["column"]}',
                   [['N', count], ['یافت شد', len(result)]])


# ── 6. Filter Bottom N ────────────────────────────────────────────────────

def filter_bottom_n(params, headers, rows):
    ci  = _col_idx(headers, params['column'])
    n   = int(params.get('n', 10))

    scored = [(r, _to_number(r[ci] if ci < len(r) else None)) for r in rows]
    scored = [(r, v) for r, v in scored if v is not None]
    scored.sort(key=lambda x: x[1])

    count  = min(n, len(scored))
    result = [r for r, _ in scored[:count]]
    return _result(headers, result, f'Bottom {n} — {params["column"]}',
                   [['N', count], ['یافت شد', len(result)]])


# ── 7. Filter Contains ────────────────────────────────────────────────────

def filter_contains(params, headers, rows):
    ci             = _col_idx(headers, params['column'])
    search_text    = params.get('text', '')
    case_sensitive = params.get('case_sensitive', 'false') == 'true'
    negate         = params.get('negate', 'false') == 'true'

    def matches(v):
        a = str(v)
        b = search_text
        if not case_sensitive:
            a, b = a.lower(), b.lower()
        hit = b in a
        return not hit if negate else hit

    filtered = [r for r in rows if matches(r[ci] if ci < len(r) else None)]
    return _result(headers, filtered, f'جستجوی متن — {params["column"]}',
                   [['متن', search_text], ['یافت شد', len(filtered)]])


# ── 8. Filter Regex ───────────────────────────────────────────────────────

def filter_regex(params, headers, rows):
    ci      = _col_idx(headers, params['column'])
    pattern = params.get('pattern', '')
    negate  = params.get('negate', 'false') == 'true'
    flags   = re.IGNORECASE if params.get('case_insensitive', 'true') == 'true' else 0

    try:
        regex = re.compile(pattern, flags)
    except re.error as e:
        raise ValueError(f'الگوی Regex نامعتبر: {e}')

    def matches(v):
        hit = bool(regex.search(str(v)))
        return not hit if negate else hit

    filtered = [r for r in rows if matches(r[ci] if ci < len(r) else None)]
    return _result(headers, filtered, f'فیلتر Regex — {params["column"]}',
                   [['الگو', pattern], ['یافت شد', len(filtered)]])


# ── 9. Filter Between ─────────────────────────────────────────────────────

def filter_between(params, headers, rows):
    ci  = _col_idx(headers, params['column'])
    lo  = _to_number(params.get('min_val', ''))
    hi  = _to_number(params.get('max_val', ''))
    inc = params.get('inclusive', 'true') == 'true'

    def matches(v):
        n = _to_number(v)
        if n is None: return False
        lo_ok = (n >= lo) if (lo is not None and inc) else (n > lo) if lo is not None else True
        hi_ok = (n <= hi) if (hi is not None and inc) else (n < hi) if hi is not None else True
        return lo_ok and hi_ok

    filtered = [r for r in rows if matches(r[ci] if ci < len(r) else None)]
    return _result(headers, filtered, f'فیلتر بازه — {params["column"]}',
                   [['min', lo], ['max', hi], ['یافت شد', len(filtered)]])


# ── 10. Search & Replace ──────────────────────────────────────────────────

def search_replace(params, headers, rows):
    ci    = _col_idx(headers, params['column']) if params.get('column') else None
    find  = params.get('find', '')
    repl  = params.get('replace', '')
    case  = params.get('case_sensitive', 'false') == 'true'
    mode  = params.get('mode', 'exact')  # exact | contains | regex

    def apply(v):
        s = str(v)
        if mode == 'regex':
            flags = 0 if case else re.IGNORECASE
            return re.sub(find, repl, s, flags=flags)
        if mode == 'contains':
            if case: return s.replace(find, repl)
            return re.sub(re.escape(find), repl, s, flags=re.IGNORECASE)
        # exact
        if (s == find) or (not case and s.lower() == find.lower()):
            return repl
        return s

    changed  = 0
    new_rows = [list(r) for r in rows]
    cols     = [ci] if ci is not None else list(range(len(headers)))

    for i, row in enumerate(new_rows):
        for c in cols:
            if c < len(row) and not _is_empty(row[c]):
                orig = str(row[c])
                new_rows[i][c] = apply(row[c])
                if new_rows[i][c] != orig:
                    changed += 1

    return _result(headers, new_rows, 'جستجو و جایگزینی',
                   [['جستجو', find], ['جایگزین', repl], ['تغییر', changed]])


# ── 11. Fuzzy Search ──────────────────────────────────────────────────────

def fuzzy_search(params, headers, rows):
    """Simple Levenshtein-based fuzzy matching (no external lib needed)"""
    ci        = _col_idx(headers, params['column'])
    query     = params.get('query', '').lower()
    threshold = float(params.get('threshold', 0.6))  # similarity 0-1

    def levenshtein(a, b):
        if len(a) < len(b): a, b = b, a
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a):
            curr = [i + 1]
            for j, cb in enumerate(b):
                curr.append(min(prev[j+1]+1, curr[j]+1, prev[j]+(ca!=cb)))
            prev = curr
        return prev[-1]

    def similarity(a, b):
        dist = levenshtein(a, b)
        return 1 - dist / max(len(a), len(b), 1)

    results = []
    for row in rows:
        v    = str(row[ci] if ci < len(row) else '').lower()
        sim  = similarity(v, query)
        if sim >= threshold:
            results.append((row, sim))

    results.sort(key=lambda x: x[1], reverse=True)
    filtered    = [r for r, _ in results]
    new_headers = headers + ['_fuzzy_score']
    new_rows    = [list(r) + [round(s, 3)] for r, s in results]

    return _result(new_headers, new_rows, f'جستجوی تقریبی — {params["column"]}',
                   [['جستجو', query], ['آستانه', threshold], ['یافت شد', len(filtered)]])


# ── 12. Filter Unique Values ──────────────────────────────────────────────

def filter_unique(params, headers, rows):
    ci   = _col_idx(headers, params['column'])
    seen = set()
    result = []
    for row in rows:
        v = str(row[ci] if ci < len(row) else '')
        if v not in seen:
            seen.add(v)
            result.append(row)

    return _result(headers, result, f'مقادیر یکتا — {params["column"]}',
                   [['یکتا', len(result)], ['تکراری حذف شده', len(rows) - len(result)]])


# ── 13. Filter Duplicates ─────────────────────────────────────────────────

def filter_duplicates(params, headers, rows):
    """Return ONLY the duplicate rows (inverse of filter_unique)"""
    ci   = _col_idx(headers, params['column'])
    seen = {}
    for i, row in enumerate(rows):
        k = str(row[ci] if ci < len(row) else '')
        seen.setdefault(k, []).append(i)

    dup_idxs = {i for idxs in seen.values() if len(idxs) > 1 for i in idxs}
    result   = [r for i, r in enumerate(rows) if i in dup_idxs]

    return _result(headers, result, f'ردیف‌های تکراری — {params["column"]}',
                   [['تکراری', len(result)], ['گروه یکتا', sum(1 for v in seen.values() if len(v) > 1)]])


# ── 14. Filter By Condition (formula-style) ───────────────────────────────

def filter_by_condition(params, headers, rows):
    """
    Evaluate a simple expression string against each row.
    Example: "Sales > 1000 AND Region == 'West'"
    """
    expr = params.get('expression', '')
    if not expr:
        raise ValueError('عبارت شرطی الزامی است')

    # Build a safe eval context per row
    def eval_expr(row):
        context = {h.replace(' ', '_'): row[i] if i < len(row) else None
                   for i, h in enumerate(headers)}
        # Replace AND/OR/NOT with Python equivalents
        safe_expr = expr.replace(' AND ', ' and ').replace(' OR ', ' or ').replace(' NOT ', ' not ')
        try:
            return bool(eval(safe_expr, {'__builtins__': {}}, context))
        except Exception:
            return False

    filtered = [r for r in rows if eval_expr(r)]
    return _result(headers, filtered, 'فیلتر شرطی',
                   [['عبارت', expr[:50]], ['یافت شد', len(filtered)]])
