# cython: language_level=3
"""
SWAK — Data Profiling Module (11 tools)
Comprehensive data quality and profile analysis
"""

import math
import re
from collections import Counter, defaultdict
from datetime import datetime


def run(tool_id: str, params: dict, headers: list, rows: list) -> dict:
    fn_map = {
        'data-profile':     data_profile,
        'quality-score':    quality_score,
        'column-profile':   column_profile,
        'missing-analysis': missing_analysis,
        'duplicate-report': duplicate_report,
        'cardinality':      cardinality,
        'data-types':       data_types,
        'value-dist':       value_dist,
        'outlier-report':   outlier_report,
        'schema-infer':     schema_infer,
        'compare-datasets': compare_datasets,
    }
    fn = fn_map.get(tool_id)
    if not fn:
        raise ValueError(f'ابزار ناشناخته: {tool_id}')
    return fn(params, headers, list(rows))


def _is_empty(v):
    return v is None or (isinstance(v, float) and math.isnan(v)) or (isinstance(v, str) and v.strip() == '')

def _to_number(v):
    if _is_empty(v): return None
    try: return float(str(v).replace(',', ''))
    except: return None

def _mean(vals): return sum(vals)/len(vals) if vals else 0
def _std(vals):
    m = _mean(vals)
    return math.sqrt(sum((x-m)**2 for x in vals)/len(vals)) if vals else 0

def _result(headers, rows, title, stats, note=''):
    return {'headers': headers, 'rows': rows,
            'summary': {'title': title, 'stats': stats, 'note': note}}


def data_profile(params, headers, rows):
    n = len(rows)
    out_headers = ['column','type','count','missing','missing%','unique','min','max','mean','std','top_value']
    out_rows    = []

    for i, h in enumerate(headers):
        vals     = [r[i] if i < len(r) else None for r in rows]
        non_null = [v for v in vals if not _is_empty(v)]
        missing  = n - len(non_null)
        unique   = len(set(str(v) for v in non_null))
        nums     = [_to_number(v) for v in non_null if _to_number(v) is not None]
        top_val  = Counter(str(v) for v in non_null).most_common(1)

        col_type = 'numeric'   if len(nums) > len(non_null)*0.8 else \
                   'date'      if sum(1 for v in non_null if re.search(r'\d{4}[-/]\d{2}',str(v))) > len(non_null)*0.5 else \
                   'text'

        out_rows.append([
            h, col_type, len(non_null), missing,
            f'{missing/n*100:.1f}%', unique,
            round(min(nums),2) if nums else None,
            round(max(nums),2) if nums else None,
            round(_mean(nums),2) if nums else None,
            round(_std(nums),2) if nums else None,
            top_val[0][0][:30] if top_val else None,
        ])

    return _result(out_headers, out_rows, 'Data Profile',
                   [['ردیف', n], ['ستون', len(headers)],
                    ['کامل', sum(1 for r in out_rows if r[3] == 0)]])


def quality_score(params, headers, rows):
    n    = len(rows)
    dims = {}

    # Completeness
    total_cells = n * len(headers)
    missing = sum(1 for r in rows for v in r if _is_empty(v))
    dims['completeness'] = round((1 - missing/total_cells)*100, 1) if total_cells else 0

    # Uniqueness (no full-row duplicates)
    unique_rows = len(set(tuple(str(v) for v in r) for r in rows))
    dims['uniqueness'] = round(unique_rows/n*100, 1) if n else 0

    # Validity (no Excel error values)
    errors = sum(1 for r in rows for v in r if str(v or '').upper().strip() in
                 ('#DIV/0!','#N/A','#NAME?','#REF!','#VALUE!','#NUM!'))
    dims['validity'] = round((1-errors/total_cells)*100, 1) if total_cells else 0

    # Consistency (numeric cols have consistent types)
    consistent = 0
    for i in range(len(headers)):
        vals = [r[i] if i < len(r) else None for r in rows]
        nn   = [v for v in vals if not _is_empty(v)]
        if not nn: consistent += 1; continue
        nums = sum(1 for v in nn if _to_number(v) is not None)
        consistent += 1 if nums/len(nn) > 0.9 or nums/len(nn) < 0.1 else 0
    dims['consistency'] = round(consistent/len(headers)*100, 1) if headers else 0

    overall = round(_mean(list(dims.values())), 1)
    grade   = 'A' if overall >= 90 else 'B' if overall >= 80 else 'C' if overall >= 70 else 'D'

    out_rows = [[k, v, '✅' if v >= 90 else '⚠️' if v >= 70 else '❌'] for k, v in dims.items()]
    out_rows.append(['OVERALL', overall, grade])

    return _result(['dimension','score','status'], out_rows,
                   'امتیاز کیفیت داده',
                   [['امتیاز کلی', overall], ['رتبه', grade]])


def column_profile(params, headers, rows):
    col  = params.get('column', headers[0])
    ci   = headers.index(col)
    vals = [r[ci] if ci < len(r) else None for r in rows]
    nn   = [v for v in vals if not _is_empty(v)]
    nums = sorted([_to_number(v) for v in nn if _to_number(v) is not None])

    def pct(p):
        if not nums: return None
        i = (p/100)*(len(nums)-1)
        lo, hi = int(i), math.ceil(i)
        return round(nums[lo] + (nums[hi]-nums[lo])*(i-lo), 4) if lo != hi else nums[lo]

    out_rows = [
        ['count', len(nn)], ['missing', len(vals)-len(nn)],
        ['missing%', f'{(len(vals)-len(nn))/len(vals)*100:.1f}%'],
        ['unique', len(set(str(v) for v in nn))],
        ['type', 'numeric' if nums else 'text'],
    ]
    if nums:
        out_rows += [
            ['min', nums[0]], ['max', nums[-1]],
            ['mean', round(_mean(nums),4)], ['median', pct(50)],
            ['std', round(_std(nums),4)],
            ['p25', pct(25)], ['p75', pct(75)],
            ['IQR', round((pct(75) or 0)-(pct(25) or 0),4)],
            ['skewness', round((sum((x-_mean(nums))**3 for x in nums)/len(nums))/_std(nums)**3,3) if _std(nums) else 0],
        ]

    top5 = Counter(str(v) for v in nn).most_common(5)
    for val, cnt in top5:
        out_rows.append([f'top: {val[:20]}', f'{cnt} ({cnt/len(nn)*100:.1f}%)'])

    return _result(['metric','value'], out_rows, f'پروفایل ستون — {col}',
                   [['ستون', col], ['نوع', 'numeric' if nums else 'text']])


def missing_analysis(params, headers, rows):
    n = len(rows)
    out_rows = []
    for i, h in enumerate(headers):
        vals    = [r[i] if i < len(r) else None for r in rows]
        missing = sum(1 for v in vals if _is_empty(v))
        pct     = missing/n*100 if n else 0
        status  = '❌ بحرانی' if pct > 50 else '⚠️ زیاد' if pct > 20 else '✅ قابل قبول' if pct > 0 else '✅ کامل'
        out_rows.append([h, missing, round(pct,2), status])

    out_rows.sort(key=lambda r: r[1], reverse=True)
    total_missing = sum(r[1] for r in out_rows)

    return _result(['column','missing_count','missing_pct','status'],
                   out_rows, 'تحلیل مقادیر خالی',
                   [['کل خالی', total_missing],
                    ['ستون بحرانی', sum(1 for r in out_rows if '❌' in r[3])]])


def duplicate_report(params, headers, rows):
    key_cols = params.get('key_columns', '')
    if key_cols:
        idxs = [headers.index(c.strip()) for c in key_cols.split(',') if c.strip() in headers]
    else:
        idxs = list(range(len(headers)))

    seen = defaultdict(list)
    for i, row in enumerate(rows):
        key = tuple(str(row[j] if j < len(row) else '') for j in idxs)
        seen[key].append(i)

    dup_groups = {k: v for k, v in seen.items() if len(v) > 1}
    dup_rows   = sum(len(v) for v in dup_groups.values())
    dup_sets   = len(dup_groups)

    out_rows = [[', '.join(k), len(v), str(v)] for k, v in sorted(dup_groups.items(), key=lambda x: -len(x[1]))[:50]]

    return _result(['key_value','occurrences','row_indices'],
                   out_rows, 'گزارش تکراری‌ها',
                   [['گروه تکراری', dup_sets], ['ردیف تکراری', dup_rows],
                    ['% تکراری', f'{dup_rows/len(rows)*100:.1f}%' if rows else '0%']])


def cardinality(params, headers, rows):
    n = len(rows)
    out_rows = []
    for i, h in enumerate(headers):
        vals   = [str(r[i] if i < len(r) else '') for r in rows if not _is_empty(r[i] if i < len(r) else None)]
        unique = len(set(vals))
        ratio  = unique/n*100 if n else 0
        kind   = 'ID/Key' if ratio > 95 else 'High' if ratio > 50 else 'Medium' if ratio > 10 else 'Low' if unique > 1 else 'Constant'
        out_rows.append([h, unique, round(ratio,1), kind])

    out_rows.sort(key=lambda r: r[1], reverse=True)
    return _result(['column','unique_count','unique%','cardinality'],
                   out_rows, 'تحلیل Cardinality',
                   [['ستون‌ها', len(headers)],
                    ['ستون ID/Key', sum(1 for r in out_rows if r[3] == 'ID/Key')]])


def data_types(params, headers, rows):
    out_rows = []
    for i, h in enumerate(headers):
        vals = [r[i] if i < len(r) else None for r in rows if not _is_empty(r[i] if i < len(r) else None)]
        if not vals:
            out_rows.append([h, 'empty', 0, 0, 0, 0]); continue

        n_num  = sum(1 for v in vals if _to_number(v) is not None)
        n_int  = sum(1 for v in vals if _to_number(v) is not None and float(_to_number(v)).is_integer())
        n_date = sum(1 for v in vals if re.search(r'\d{4}[-/]\d{2}[-/]\d{2}', str(v)))
        n_bool = sum(1 for v in vals if str(v).lower() in ('true','false','yes','no','0','1','بله','خیر'))

        inferred = 'integer' if n_int/len(vals) > 0.9 else \
                   'float'   if n_num/len(vals) > 0.8 else \
                   'date'    if n_date/len(vals) > 0.7 else \
                   'boolean' if n_bool/len(vals) > 0.8 else 'text'

        out_rows.append([h, inferred, n_num, n_int, n_date, n_bool])

    return _result(['column','inferred_type','numeric%','integer%','date%','boolean%'],
                   [[r[0], r[1],
                     f'{r[2]/len(rows)*100:.0f}%' if rows else '0%',
                     f'{r[3]/len(rows)*100:.0f}%' if rows else '0%',
                     f'{r[4]/len(rows)*100:.0f}%' if rows else '0%',
                     f'{r[5]/len(rows)*100:.0f}%' if rows else '0%'] for r in out_rows],
                   'تشخیص نوع داده',
                   [['ستون‌ها', len(headers)]])


def value_dist(params, headers, rows):
    col   = params.get('column', headers[0])
    ci    = headers.index(col)
    n_bins= int(params.get('n_bins', 10))
    vals  = [r[ci] if ci < len(r) else None for r in rows]
    nums  = sorted([_to_number(v) for v in vals if _to_number(v) is not None])

    if nums:
        mn, mx = nums[0], nums[-1]
        rng    = mx - mn or 1
        bins   = [(mn + i*rng/n_bins, mn + (i+1)*rng/n_bins) for i in range(n_bins)]
        counts = [sum(1 for v in nums if lo <= v < hi) + (1 if i == n_bins-1 and mx <= hi else 0)
                  for i, (lo, hi) in enumerate(bins)]
        out_rows = [[f'{lo:.2f}–{hi:.2f}', cnt, round(cnt/len(nums)*100,1)]
                    for (lo,hi), cnt in zip(bins, counts)]
        return _result(['bin','count','percent'], out_rows,
                       f'توزیع مقادیر — {col}',
                       [['bins', n_bins], ['min', mn], ['max', mx]])
    else:
        top = Counter(str(v) for v in vals if not _is_empty(v)).most_common(n_bins)
        out_rows = [[v, cnt, round(cnt/len(vals)*100,1)] for v, cnt in top]
        return _result(['value','count','percent'], out_rows,
                       f'توزیع مقادیر — {col}', [['نوع', 'categorical']])


def outlier_report(params, headers, rows):
    cols = params.get('columns', headers)
    if isinstance(cols, str): cols = [c.strip() for c in cols.split(',')]
    method = params.get('method', 'iqr')

    out_rows = []
    for col in cols:
        if col not in headers: continue
        ci   = headers.index(col)
        nums = sorted([_to_number(r[ci] if ci < len(r) else None) for r in rows
                       if _to_number(r[ci] if ci < len(r) else None) is not None])
        if len(nums) < 4: continue

        if method == 'iqr':
            q1 = nums[int(len(nums)*0.25)]
            q3 = nums[int(len(nums)*0.75)]
            iqr = q3 - q1
            lo, hi = q1 - 1.5*iqr, q3 + 1.5*iqr
        else:
            m  = _mean(nums)
            s  = _std(nums)
            lo, hi = m - 3*s, m + 3*s

        outliers = [v for v in nums if v < lo or v > hi]
        out_rows.append([col, len(outliers), round(len(outliers)/len(nums)*100,1),
                         round(lo,2), round(hi,2),
                         round(min(outliers),2) if outliers else None,
                         round(max(outliers),2) if outliers else None])

    return _result(['column','outlier_count','outlier%','lower_bound','upper_bound','min_outlier','max_outlier'],
                   out_rows, f'گزارش پرت ({method})',
                   [['ستون تحلیل شده', len(out_rows)],
                    ['پرت‌دارترین', out_rows[0][0] if out_rows else 'N/A']])


def schema_infer(params, headers, rows):
    out_rows = []
    for i, h in enumerate(headers):
        vals = [r[i] if i < len(r) else None for r in rows]
        nn   = [v for v in vals if not _is_empty(v)]
        nums = [_to_number(v) for v in nn if _to_number(v) is not None]
        nullable = any(_is_empty(v) for v in vals)

        if len(nums) > len(nn)*0.8:
            all_int = all(float(v).is_integer() for v in nums)
            max_val = max(nums) if nums else 0
            sql_type = 'INTEGER' if all_int and max_val < 2**31 else 'BIGINT' if all_int else 'FLOAT'
        elif sum(1 for v in nn if re.search(r'\d{4}-\d{2}-\d{2}', str(v))) > len(nn)*0.7:
            sql_type = 'DATE'
        elif sum(1 for v in nn if '@' in str(v)) > len(nn)*0.7:
            sql_type = 'VARCHAR(255)'
        else:
            max_len  = max((len(str(v)) for v in nn), default=50)
            sql_type = f'VARCHAR({min(max_len*2+10, 255)})' if max_len <= 100 else 'TEXT'

        col_name = re.sub(r'[^a-zA-Z0-9_]','_', h).lower().strip('_')
        out_rows.append([h, col_name, sql_type, 'YES' if nullable else 'NO'])

    schema = 'CREATE TABLE data (\n' + ',\n'.join(
        f'  {r[1]} {r[2]}{"" if r[3]=="NO" else " NULL"}' for r in out_rows
    ) + '\n);'

    return _result(['original','sql_column','sql_type','nullable'],
                   out_rows, 'استنتاج Schema',
                   [['ستون‌ها', len(headers)], ['SQL DDL', schema[:100]]])


def compare_datasets(params, headers, rows):
    """Compare current data with a second dataset passed as JSON"""
    content2 = params.get('dataset2', '[]')
    try:
        import json
        other = json.loads(content2)
        if isinstance(other, list) and other:
            hdrs2  = list(other[0].keys())
            rows2  = [[r.get(h) for h in hdrs2] for r in other]
        else:
            return _result(['error'], [['dataset2 نامعتبر است']], 'مقایسه', [])
    except Exception as e:
        raise ValueError(f'dataset2 JSON نامعتبر: {e}')

    common_cols = [h for h in headers if h in hdrs2]
    only_left   = [h for h in headers if h not in hdrs2]
    only_right  = [h for h in hdrs2   if h not in headers]

    out_rows = [
        ['ردیف‌های چپ', len(rows)],
        ['ردیف‌های راست', len(rows2)],
        ['ستون‌های مشترک', len(common_cols)],
        ['فقط چپ', len(only_left)],
        ['فقط راست', len(only_right)],
    ]
    if only_left:  out_rows.append(['ستون‌های چپ', ', '.join(only_left[:10])])
    if only_right: out_rows.append(['ستون‌های راست', ', '.join(only_right[:10])])

    return _result(['metric','value'], out_rows, 'مقایسه Dataset',
                   [['مشترک', len(common_cols)]])
