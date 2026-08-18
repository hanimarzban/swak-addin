# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
"""
SWAK — Statistics Module (25 tools)
Pure Python + math — no external deps required
scipy used when available for advanced distributions
"""

import math
import statistics
from collections import Counter, defaultdict


def run(tool_id: str, params: dict, headers: list, rows: list) -> dict:
    fn_map = {
        'describe-stats':       describe_stats,
        'correlation':          correlation,
        'covariance':           covariance,
        'distribution-fit':     distribution_fit,
        'hypothesis-test':      hypothesis_test,
        'anova':                anova,
        'chi-square':           chi_square,
        'regression-simple':    regression_simple,
        'regression-multiple':  regression_multiple,
        'moving-average':       moving_average,
        'exponential-smooth':   exponential_smooth,
        'seasonality':          seasonality,
        'confidence-interval':  confidence_interval,
        'sample-size':          sample_size,
        'probability-dist':     probability_dist,
        'percentile-rank':      percentile_rank,
        'z-score':              z_score,
        'normality-test':       normality_test,
        'outlier-score':        outlier_score,
        'cross-tabulation':     cross_tabulation,
        'frequency-table':      frequency_table,
        'pareto-analysis':      pareto_analysis,
        'cohort-analysis':      cohort_analysis,
        'survival-analysis':    survival_analysis,
        'bootstrap':            bootstrap,
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

def _get_col_nums(headers, rows, col_name):
    ci   = _col_idx(headers, col_name)
    return [_to_number(r[ci] if ci < len(r) else None) for r in rows
            if _to_number(r[ci] if ci < len(r) else None) is not None]

def _mean(vals):
    return sum(vals) / len(vals) if vals else 0

def _variance(vals, sample=True):
    if len(vals) < 2: return 0
    m  = _mean(vals)
    ss = sum((v - m) ** 2 for v in vals)
    return ss / (len(vals) - 1 if sample else len(vals))

def _std(vals, sample=True):
    return math.sqrt(_variance(vals, sample))

def _median(vals):
    s = sorted(vals)
    n = len(s)
    return s[n//2] if n % 2 else (s[n//2-1] + s[n//2]) / 2

def _percentile(sorted_vals, p):
    if not sorted_vals: return 0
    idx = (p / 100) * (len(sorted_vals) - 1)
    lo, hi = int(idx), math.ceil(idx)
    if lo == hi: return sorted_vals[lo]
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (idx - lo)

def _mode(vals):
    if not vals: return None
    return Counter(vals).most_common(1)[0][0]

def _covariance(x, y):
    if len(x) != len(y) or len(x) < 2: return 0
    mx, my = _mean(x), _mean(y)
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (len(x) - 1)

def _pearson(x, y):
    cov = _covariance(x, y)
    sx, sy = _std(x), _std(y)
    return cov / (sx * sy) if sx and sy else 0

def _result(headers, rows, title, stats, note='', new_sheet=None):
    r = {'headers': headers, 'rows': rows,
         'summary': {'title': title, 'stats': stats, 'note': note}}
    if new_sheet:
        r['new_sheet'] = new_sheet
    return r


# ── 1. Describe Stats ─────────────────────────────────────────────────────

def describe_stats(params, headers, rows):
    cols = params.get('columns', headers)
    if isinstance(cols, str):
        cols = [c.strip() for c in cols.split(',')]

    out_headers = ['metric']
    out_rows_map = defaultdict(dict)
    metrics = ['count', 'mean', 'std', 'min', '25%', '50%', '75%', 'max',
               'sum', 'variance', 'skewness', 'kurtosis', 'missing', 'unique']

    for col in cols:
        out_headers.append(col)
        nums = _get_col_nums(headers, rows, col)
        ci   = _col_idx(headers, col)
        all_vals = [r[ci] if ci < len(r) else None for r in rows]
        missing  = sum(1 for v in all_vals if _is_empty(v))
        unique   = len(set(str(v) for v in all_vals if not _is_empty(v)))

        if not nums:
            for m in metrics:
                out_rows_map[m][col] = None
            continue

        s = sorted(nums)
        m = _mean(nums)
        v = _variance(nums)
        sd = math.sqrt(v) if v >= 0 else 0

        # Skewness (Fisher)
        n = len(nums)
        skew = (sum((x - m)**3 for x in nums) / n / (sd**3)) if sd else 0

        # Excess kurtosis
        kurt = (sum((x - m)**4 for x in nums) / n / (sd**4) - 3) if sd else 0

        out_rows_map['count'][col]    = n
        out_rows_map['mean'][col]     = round(m, 4)
        out_rows_map['std'][col]      = round(sd, 4)
        out_rows_map['min'][col]      = s[0]
        out_rows_map['25%'][col]      = round(_percentile(s, 25), 4)
        out_rows_map['50%'][col]      = round(_median(nums), 4)
        out_rows_map['75%'][col]      = round(_percentile(s, 75), 4)
        out_rows_map['max'][col]      = s[-1]
        out_rows_map['sum'][col]      = round(sum(nums), 4)
        out_rows_map['variance'][col] = round(v, 4)
        out_rows_map['skewness'][col] = round(skew, 4)
        out_rows_map['kurtosis'][col] = round(kurt, 4)
        out_rows_map['missing'][col]  = missing
        out_rows_map['unique'][col]   = unique

    out_rows = [[m] + [out_rows_map[m].get(c) for c in cols] for m in metrics]

    return _result(out_headers, out_rows,
                   'آمار توصیفی',
                   [['ستون‌های تحلیل', len(cols)], ['ردیف', len(rows)]])


# ── 2. Correlation Matrix ─────────────────────────────────────────────────

def correlation(params, headers, rows):
    cols   = params.get('columns', headers)
    if isinstance(cols, str):
        cols = [c.strip() for c in cols.split(',')]
    method = params.get('method', 'pearson')

    col_data = {}
    for col in cols:
        col_data[col] = _get_col_nums(headers, rows, col)

    out_headers = [''] + cols
    out_rows    = []
    for r_col in cols:
        row = [r_col]
        for c_col in cols:
            x = col_data[r_col]
            y = col_data[c_col]
            n = min(len(x), len(y))
            if n < 2:
                row.append(None)
                continue
            corr = _pearson(x[:n], y[:n])
            row.append(round(corr, 4))
        out_rows.append(row)

    return _result(out_headers, out_rows,
                   f'ماتریس همبستگی ({method})',
                   [['ستون‌ها', len(cols)], ['روش', method]])


# ── 3. Covariance Matrix ──────────────────────────────────────────────────

def covariance(params, headers, rows):
    cols = params.get('columns', headers)
    if isinstance(cols, str):
        cols = [c.strip() for c in cols.split(',')]

    col_data    = {col: _get_col_nums(headers, rows, col) for col in cols}
    out_headers = [''] + cols
    out_rows    = []

    for r_col in cols:
        row = [r_col]
        for c_col in cols:
            x = col_data[r_col]
            y = col_data[c_col]
            n = min(len(x), len(y))
            row.append(round(_covariance(x[:n], y[:n]), 4) if n >= 2 else None)
        out_rows.append(row)

    return _result(out_headers, out_rows,
                   'ماتریس کوواریانس',
                   [['ستون‌ها', len(cols)]])


# ── 4. Distribution Fit ───────────────────────────────────────────────────

def distribution_fit(params, headers, rows):
    nums = _get_col_nums(headers, rows, params['column'])
    if not nums:
        raise ValueError('مقدار عددی یافت نشد')

    m   = _mean(nums)
    s   = _std(nums)
    med = _median(nums)
    sk  = (sum((x - m)**3 for x in nums) / len(nums)) / (s**3) if s else 0

    # Simple heuristic fit
    fits = []
    if abs(sk) < 0.5:
        fits.append(('Normal', f'μ={m:.3f}, σ={s:.3f}', 'high'))
    if all(v >= 0 for v in nums):
        lam = 1 / m if m else 0
        fits.append(('Exponential', f'λ={lam:.4f}', 'medium'))
        fits.append(('Log-Normal', f'μ={math.log(m):.3f}', 'medium'))
    if abs(sk) > 1:
        fits.append(('Skewed', f'skew={sk:.3f}', 'low'))

    out_headers = ['distribution', 'parameters', 'fit_quality']
    out_rows    = [[f, p, q] for f, p, q in fits]

    return _result(out_headers, out_rows,
                   f'برازش توزیع — {params["column"]}',
                   [['میانگین', round(m, 4)],
                    ['انحراف معیار', round(s, 4)],
                    ['چولگی', round(sk, 4)]])


# ── 5. Hypothesis Test ────────────────────────────────────────────────────

def hypothesis_test(params, headers, rows):
    test  = params.get('test_type', 'one_sample_t')
    col1  = params.get('column1')
    col2  = params.get('column2', '')
    alpha = float(params.get('alpha', 0.05))
    mu0   = float(params.get('mu0', 0))

    x = _get_col_nums(headers, rows, col1)
    if not x:
        raise ValueError('داده عددی یافت نشد')

    n  = len(x)
    mx = _mean(x)
    sx = _std(x)

    if test == 'one_sample_t':
        t_stat = (mx - mu0) / (sx / math.sqrt(n)) if sx else 0
        # Approximate p-value using normal approx for large n
        p_val  = 2 * (1 - _norm_cdf(abs(t_stat)))
        result_rows = [
            ['آزمون', 'One-Sample T'],
            ['H₀', f'μ = {mu0}'],
            ['n', n],
            ['میانگین نمونه', round(mx, 4)],
            ['t-statistic', round(t_stat, 4)],
            ['p-value', round(p_val, 5)],
            ['alpha', alpha],
            ['نتیجه', 'رد H₀' if p_val < alpha else 'رد نشد H₀'],
        ]
    elif test == 'two_sample_t' and col2:
        y  = _get_col_nums(headers, rows, col2)
        my, sy, ny = _mean(y), _std(y), len(y)
        se     = math.sqrt(sx**2/n + sy**2/ny) if n and ny else 1
        t_stat = (mx - my) / se if se else 0
        p_val  = 2 * (1 - _norm_cdf(abs(t_stat)))
        result_rows = [
            ['آزمون', 'Two-Sample T'],
            ['میانگین ۱', round(mx, 4)],
            ['میانگین ۲', round(my, 4)],
            ['تفاوت', round(mx - my, 4)],
            ['t-statistic', round(t_stat, 4)],
            ['p-value', round(p_val, 5)],
            ['نتیجه', 'تفاوت معنادار' if p_val < alpha else 'تفاوت معنادار نیست'],
        ]
    else:
        result_rows = [['خطا', 'نوع آزمون پشتیبانی نمی‌شود']]

    out_headers = ['parameter', 'value']
    return _result(out_headers, result_rows, 'آزمون فرض', [['alpha', alpha]])


def _norm_cdf(z):
    """Approximation of normal CDF"""
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


# ── 6. ANOVA (One-Way) ────────────────────────────────────────────────────

def anova(params, headers, rows):
    group_ci = _col_idx(headers, params['group_column'])
    val_ci   = _col_idx(headers, params['value_column'])
    alpha    = float(params.get('alpha', 0.05))

    groups = defaultdict(list)
    for row in rows:
        g = str(row[group_ci] if group_ci < len(row) else '')
        v = _to_number(row[val_ci] if val_ci < len(row) else None)
        if v is not None:
            groups[g].append(v)

    if len(groups) < 2:
        raise ValueError('حداقل ۲ گروه لازم است')

    all_vals = [v for g in groups.values() for v in g]
    grand_m  = _mean(all_vals)
    N        = len(all_vals)
    k        = len(groups)

    # SS Between
    ss_between = sum(len(g) * (_mean(g) - grand_m)**2 for g in groups.values())
    # SS Within
    ss_within  = sum((v - _mean(g))**2 for g in groups.values() for v in g)

    df_between = k - 1
    df_within  = N - k
    ms_between = ss_between / df_between if df_between else 0
    ms_within  = ss_within  / df_within  if df_within  else 1

    f_stat = ms_between / ms_within if ms_within else 0

    out_headers = ['source', 'SS', 'df', 'MS', 'F']
    out_rows    = [
        ['Between Groups', round(ss_between, 4), df_between, round(ms_between, 4), round(f_stat, 4)],
        ['Within Groups',  round(ss_within,  4), df_within,  round(ms_within,  4), ''],
        ['Total',          round(ss_between + ss_within, 4), N - 1, '', ''],
    ]

    return _result(out_headers, out_rows, 'ANOVA یک‌طرفه',
                   [['گروه‌ها', k], ['F-statistic', round(f_stat, 4)],
                    ['نتیجه', f'F={f_stat:.4f} — تفسیر با جدول F']])


# ── 7. Chi-Square Test ────────────────────────────────────────────────────

def chi_square(params, headers, rows):
    col1  = _col_idx(headers, params['column1'])
    col2  = _col_idx(headers, params['column2'])
    alpha = float(params.get('alpha', 0.05))

    # Build contingency table
    cats1 = sorted(set(str(r[col1] if col1 < len(r) else '') for r in rows))
    cats2 = sorted(set(str(r[col2] if col2 < len(r) else '') for r in rows))

    observed = defaultdict(lambda: defaultdict(int))
    for row in rows:
        c1 = str(row[col1] if col1 < len(row) else '')
        c2 = str(row[col2] if col2 < len(row) else '')
        observed[c1][c2] += 1

    N = len(rows)
    chi2 = 0
    for c1 in cats1:
        row_total = sum(observed[c1][c2] for c2 in cats2)
        for c2 in cats2:
            col_total = sum(observed[c3][c2] for c3 in cats1)
            expected  = (row_total * col_total) / N if N else 0
            if expected > 0:
                chi2 += (observed[c1][c2] - expected)**2 / expected

    df = (len(cats1) - 1) * (len(cats2) - 1)

    out_headers = ['parameter', 'value']
    out_rows    = [
        ['آزمون', 'Chi-Square'],
        ['χ²', round(chi2, 4)],
        ['df', df],
        ['alpha', alpha],
        ['تفسیر', 'وابستگی معنادار احتمالی' if chi2 > df * 2 else 'احتمال استقلال'],
    ]

    return _result(out_headers, out_rows, 'آزمون کای‌دو',
                   [['χ²', round(chi2, 4)], ['df', df]])


# ── 8. Simple Linear Regression ──────────────────────────────────────────

def regression_simple(params, headers, rows):
    x = _get_col_nums(headers, rows, params['x_column'])
    y = _get_col_nums(headers, rows, params['y_column'])
    n = min(len(x), len(y))
    x, y = x[:n], y[:n]

    if n < 2:
        raise ValueError('حداقل ۲ داده لازم است')

    mx, my = _mean(x), _mean(y)
    cov_xy = _covariance(x, y)
    var_x  = _variance(x)
    slope  = cov_xy / var_x if var_x else 0
    intercept = my - slope * mx

    # R²
    y_pred = [slope * xi + intercept for xi in x]
    ss_res = sum((yi - yh)**2 for yi, yh in zip(y, y_pred))
    ss_tot = sum((yi - my)**2 for yi in y)
    r2     = 1 - ss_res / ss_tot if ss_tot else 0

    # RMSE
    rmse = math.sqrt(ss_res / n)

    # Add predictions to sheet
    pred_col  = f'{params["y_column"]}_predicted'
    resid_col = f'{params["y_column"]}_residual'
    x_ci = _col_idx(headers, params['x_column'])
    new_headers = headers + [pred_col, resid_col]
    xi_all = [_to_number(r[x_ci] if x_ci < len(r) else None) for r in rows]
    new_rows = []
    for i, row in enumerate(rows):
        xi = xi_all[i]
        yh = round(slope * xi + intercept, 4) if xi is not None else None
        yi = _to_number(row[_col_idx(headers, params['y_column'])] if _col_idx(headers, params['y_column']) < len(row) else None)
        resid = round(yi - yh, 4) if (yi is not None and yh is not None) else None
        new_rows.append(list(row) + [yh, resid])

    return _result(new_headers, new_rows,
                   'رگرسیون خطی ساده',
                   [['slope (β₁)', round(slope, 4)],
                    ['intercept (β₀)', round(intercept, 4)],
                    ['R²', round(r2, 4)],
                    ['RMSE', round(rmse, 4)],
                    ['معادله', f'y = {slope:.4f}x + {intercept:.4f}']])


# ── 9. Multiple Regression ────────────────────────────────────────────────

def regression_multiple(params, headers, rows):
    x_cols  = params.get('x_columns', [])
    y_col   = params.get('y_column')
    if isinstance(x_cols, str):
        x_cols = [c.strip() for c in x_cols.split(',')]

    # Build design matrix (with intercept)
    X, Y = [], []
    for row in rows:
        xs = [_to_number(row[_col_idx(headers, c)] if _col_idx(headers, c) < len(row) else None) for c in x_cols]
        y  = _to_number(row[_col_idx(headers, y_col)] if _col_idx(headers, y_col) < len(row) else None)
        if all(v is not None for v in xs) and y is not None:
            X.append([1.0] + xs)
            Y.append(y)

    n, p = len(X), len(X[0]) if X else 0
    if n < p:
        raise ValueError(f'داده کافی نیست (n={n}, p={p})')

    # OLS: β = (XᵀX)⁻¹ Xᵀy — manual implementation
    def mat_mult(A, B):
        rows_a, cols_a = len(A), len(A[0])
        cols_b = len(B[0])
        return [[sum(A[i][k] * B[k][j] for k in range(cols_a))
                 for j in range(cols_b)] for i in range(rows_a)]

    def mat_transpose(A):
        return [[A[j][i] for j in range(len(A))] for i in range(len(A[0]))]

    def mat_inv_2x2(A):
        det = A[0][0]*A[1][1] - A[0][1]*A[1][0]
        if abs(det) < 1e-12: return None
        return [[A[1][1]/det, -A[0][1]/det], [-A[1][0]/det, A[0][0]/det]]

    # Use simplified approach: only reliable for p ≤ 3
    XT    = mat_transpose(X)
    XTX   = mat_mult(XT, X)
    XTY   = [[sum(XT[i][k] * Y[k] for k in range(n))] for i in range(p)]

    # Gaussian elimination for β
    def solve_linear(A, b):
        n = len(A)
        M = [A[i][:] + [b[i][0]] for i in range(n)]
        for col in range(n):
            pivot = next((r for r in range(col, n) if abs(M[r][col]) > 1e-12), None)
            if pivot is None: return [0.0] * n
            M[col], M[pivot] = M[pivot], M[col]
            for r in range(n):
                if r != col and abs(M[col][col]) > 1e-12:
                    factor = M[r][col] / M[col][col]
                    M[r] = [M[r][c] - factor * M[col][c] for c in range(n + 1)]
        return [M[i][n] / M[i][i] if abs(M[i][i]) > 1e-12 else 0 for i in range(n)]

    beta = solve_linear(XTX, XTY)

    # R²
    my     = _mean(Y)
    y_pred = [sum(beta[j] * X[i][j] for j in range(p)) for i in range(n)]
    ss_res = sum((Y[i] - y_pred[i])**2 for i in range(n))
    ss_tot = sum((Y[i] - my)**2 for i in range(n))
    r2     = 1 - ss_res / ss_tot if ss_tot else 0

    coef_names = ['intercept'] + x_cols
    out_headers = ['variable', 'coefficient']
    out_rows    = [[coef_names[i], round(beta[i], 6)] for i in range(len(beta))]
    out_rows   += [['R²', round(r2, 4)], ['n', n]]

    return _result(out_headers, out_rows,
                   'رگرسیون چندگانه',
                   [['متغیر وابسته', y_col],
                    ['متغیرهای مستقل', len(x_cols)],
                    ['R²', round(r2, 4)], ['n', n]])


# ── 10. Moving Average ────────────────────────────────────────────────────

def moving_average(params, headers, rows):
    ci     = _col_idx(headers, params['column'])
    window = int(params.get('window', 3))
    mtype  = params.get('type', 'simple')  # simple | weighted | exponential

    vals = [_to_number(r[ci] if ci < len(r) else None) for r in rows]

    ma = []
    for i in range(len(vals)):
        if vals[i] is None:
            ma.append(None)
            continue
        win = [v for v in vals[max(0, i-window+1):i+1] if v is not None]
        if not win:
            ma.append(None)
        elif mtype == 'simple':
            ma.append(round(_mean(win), 4))
        elif mtype == 'weighted':
            weights = list(range(1, len(win)+1))
            wa = sum(v*w for v,w in zip(win, weights)) / sum(weights)
            ma.append(round(wa, 4))
        elif mtype == 'exponential':
            alpha = 2 / (window + 1)
            ema = win[0]
            for v in win[1:]:
                ema = alpha * v + (1 - alpha) * ema
            ma.append(round(ema, 4))

    col_name = f'{params["column"]}_MA{window}'
    new_headers = headers + [col_name]
    new_rows    = [list(r) + [ma[i]] for i, r in enumerate(rows)]

    return _result(new_headers, new_rows,
                   f'میانگین متحرک — {params["column"]}',
                   [['window', window], ['نوع', mtype], ['ستون جدید', col_name]])


# ── 11. Exponential Smoothing ─────────────────────────────────────────────

def exponential_smooth(params, headers, rows):
    ci    = _col_idx(headers, params['column'])
    alpha = float(params.get('alpha', 0.3))  # smoothing factor 0-1
    beta  = float(params.get('beta', 0.0))   # trend factor (Holt's)

    vals  = [_to_number(r[ci] if ci < len(r) else None) for r in rows]
    valid = [v for v in vals if v is not None]
    if not valid:
        raise ValueError('مقدار عددی یافت نشد')

    # Single exponential smoothing
    smoothed = [valid[0]]
    for v in valid[1:]:
        smoothed.append(alpha * v + (1 - alpha) * smoothed[-1])

    # Map back to original indices
    result = []
    vi = 0
    for v in vals:
        if v is None:
            result.append(None)
        else:
            result.append(round(smoothed[vi], 4))
            vi += 1

    col_name    = f'{params["column"]}_smoothed'
    new_headers = headers + [col_name]
    new_rows    = [list(r) + [result[i]] for i, r in enumerate(rows)]

    return _result(new_headers, new_rows,
                   'هموارسازی نمایی',
                   [['alpha', alpha], ['ستون جدید', col_name]])


# ── 12. Seasonality Detection ─────────────────────────────────────────────

def seasonality(params, headers, rows):
    ci     = _col_idx(headers, params['column'])
    period = int(params.get('period', 12))  # e.g. 12 for monthly

    vals = [_to_number(r[ci] if ci < len(r) else None) for r in rows]
    vals = [v for v in vals if v is not None]

    if len(vals) < period * 2:
        return _result(['parameter','value'], [['خطا', f'حداقل {period*2} داده لازم است']],
                       'تشخیص فصلی', [])

    # Compute seasonal indices (simple decomposition)
    seasonal = []
    for p in range(period):
        season_vals = [vals[i] for i in range(p, len(vals), period)]
        grand_mean  = _mean(vals)
        s_mean      = _mean(season_vals)
        seasonal.append(round(s_mean / grand_mean if grand_mean else 1, 4))

    out_headers = ['period', 'seasonal_index']
    out_rows    = [[i+1, s] for i, s in enumerate(seasonal)]

    return _result(out_headers, out_rows,
                   f'شاخص فصلی (period={period})',
                   [['دوره', period],
                    ['بالاترین', max(seasonal)],
                    ['پایین‌ترین', min(seasonal)]])


# ── 13. Confidence Interval ───────────────────────────────────────────────

def confidence_interval(params, headers, rows):
    nums  = _get_col_nums(headers, rows, params['column'])
    conf  = float(params.get('confidence', 95)) / 100
    n     = len(nums)

    if n < 2:
        raise ValueError('حداقل ۲ داده لازم است')

    m   = _mean(nums)
    se  = _std(nums) / math.sqrt(n)

    # z-score for common confidence levels
    z_map = {0.90: 1.645, 0.95: 1.960, 0.99: 2.576}
    z = z_map.get(conf, 1.960)

    lo = m - z * se
    hi = m + z * se

    out_headers = ['parameter', 'value']
    out_rows    = [
        ['n', n],
        ['میانگین', round(m, 4)],
        ['خطای استاندارد', round(se, 4)],
        ['سطح اطمینان', f'{conf*100:.0f}%'],
        ['z*', z],
        ['کران پایین', round(lo, 4)],
        ['کران بالا', round(hi, 4)],
        ['فاصله اطمینان', f'[{lo:.4f}, {hi:.4f}]'],
    ]

    return _result(out_headers, out_rows,
                   f'فاصله اطمینان — {params["column"]}',
                   [['فاصله', f'[{lo:.4f}, {hi:.4f}]'],
                    ['اطمینان', f'{conf*100:.0f}%']])


# ── 14. Sample Size ───────────────────────────────────────────────────────

def sample_size(params, headers, rows):
    method    = params.get('method', 'proportion')
    conf      = float(params.get('confidence', 95))
    margin    = float(params.get('margin_of_error', 5)) / 100
    z_map     = {90: 1.645, 95: 1.960, 99: 2.576}
    z         = z_map.get(int(conf), 1.960)

    if method == 'proportion':
        p = float(params.get('proportion', 0.5))
        n = math.ceil((z**2 * p * (1-p)) / margin**2)
    else:
        sigma = float(params.get('std_dev', 1))
        n = math.ceil((z * sigma / margin)**2)

    pop_size = int(params.get('population_size', 0))
    n_final  = n
    if pop_size > 0 and pop_size > n:
        n_final = math.ceil(n / (1 + (n - 1) / pop_size))

    out_headers = ['parameter', 'value']
    out_rows    = [
        ['روش', method],
        ['سطح اطمینان', f'{conf}%'],
        ['حاشیه خطا', f'{margin*100}%'],
        ['z*', z],
        ['حجم نمونه (نامحدود)', n],
        ['حجم نمونه (تصحیح شده)', n_final],
    ]

    return _result(out_headers, out_rows,
                   'حجم نمونه',
                   [['حجم نمونه', n_final]])


# ── 15. Probability Distribution ─────────────────────────────────────────

def probability_dist(params, headers, rows):
    dist  = params.get('distribution', 'normal')
    x_val = float(params.get('x_value', 0))
    mu    = float(params.get('mu', 0))
    sigma = float(params.get('sigma', 1))
    lam   = float(params.get('lambda', 1))

    if dist == 'normal':
        pdf = (1/(sigma*math.sqrt(2*math.pi))) * math.exp(-0.5*((x_val-mu)/sigma)**2)
        cdf = _norm_cdf((x_val - mu) / sigma)
        vals = [['توزیع', 'Normal'], ['x', x_val], ['μ', mu], ['σ', sigma],
                ['PDF', round(pdf, 6)], ['CDF', round(cdf, 6)]]
    elif dist == 'exponential':
        pdf = lam * math.exp(-lam * x_val) if x_val >= 0 else 0
        cdf = 1 - math.exp(-lam * x_val)  if x_val >= 0 else 0
        vals = [['توزیع', 'Exponential'], ['x', x_val], ['λ', lam],
                ['PDF', round(pdf, 6)], ['CDF', round(cdf, 6)]]
    elif dist == 'poisson':
        k   = int(x_val)
        pmf = (lam**k * math.exp(-lam)) / math.factorial(k)
        vals = [['توزیع', 'Poisson'], ['k', k], ['λ', lam], ['PMF', round(pmf, 6)]]
    else:
        vals = [['خطا', 'توزیع پشتیبانی نمی‌شود']]

    return _result(['parameter', 'value'], vals, f'توزیع {dist}',
                   [['توزیع', dist], ['x', x_val]])


# ── 16. Percentile Rank ───────────────────────────────────────────────────

def percentile_rank(params, headers, rows):
    ci   = _col_idx(headers, params['column'])
    nums = _get_col_nums(headers, rows, params['column'])
    s    = sorted(nums)
    n    = len(s)

    ranks = []
    for row in rows:
        v = _to_number(row[ci] if ci < len(row) else None)
        if v is None:
            ranks.append(None)
        else:
            pct = sum(1 for x in s if x <= v) / n * 100 if n else 0
            ranks.append(round(pct, 2))

    col_name    = f'{params["column"]}_percentile'
    new_headers = headers + [col_name]
    new_rows    = [list(r) + [ranks[i]] for i, r in enumerate(rows)]

    return _result(new_headers, new_rows,
                   f'رتبه درصدی — {params["column"]}',
                   [['n', n], ['ستون جدید', col_name]])


# ── 17. Z-Score ───────────────────────────────────────────────────────────

def z_score(params, headers, rows):
    ci    = _col_idx(headers, params['column'])
    nums  = _get_col_nums(headers, rows, params['column'])
    m     = _mean(nums)
    s     = _std(nums)

    col_name    = f'{params["column"]}_zscore'
    new_headers = headers + [col_name]
    new_rows    = []
    for row in rows:
        v = _to_number(row[ci] if ci < len(row) else None)
        z = round((v - m) / s, 4) if (v is not None and s) else None
        new_rows.append(list(row) + [z])

    return _result(new_headers, new_rows,
                   f'Z-Score — {params["column"]}',
                   [['میانگین', round(m, 4)], ['std', round(s, 4)]])


# ── 18. Normality Test ────────────────────────────────────────────────────

def normality_test(params, headers, rows):
    nums = _get_col_nums(headers, rows, params['column'])
    n    = len(nums)
    m    = _mean(nums)
    s    = _std(nums)

    # Jarque-Bera test
    sk   = (sum((x-m)**3 for x in nums)/n) / (s**3) if s else 0
    kurt = (sum((x-m)**4 for x in nums)/n) / (s**4) - 3 if s else 0
    jb   = n/6 * (sk**2 + kurt**2/4)

    # Simple heuristic: JB > 5.99 rejects normality at 5%
    is_normal = jb < 5.99

    out_headers = ['parameter', 'value']
    out_rows    = [
        ['n', n],
        ['میانگین', round(m, 4)],
        ['std', round(s, 4)],
        ['چولگی', round(sk, 4)],
        ['kurtosis اضافی', round(kurt, 4)],
        ['Jarque-Bera', round(jb, 4)],
        ['آستانه (5%)', 5.99],
        ['نتیجه', 'توزیع نرمال است' if is_normal else 'توزیع نرمال نیست'],
    ]

    return _result(out_headers, out_rows,
                   f'آزمون نرمالیتی — {params["column"]}',
                   [['JB', round(jb, 4)], ['نرمال', is_normal]])


# ── 19. Outlier Score ─────────────────────────────────────────────────────

def outlier_score(params, headers, rows):
    ci     = _col_idx(headers, params['column'])
    method = params.get('method', 'zscore')
    nums   = _get_col_nums(headers, rows, params['column'])
    m      = _mean(nums)
    s      = _std(nums)
    s_num  = sorted(nums)
    q1     = _percentile(s_num, 25)
    q3     = _percentile(s_num, 75)
    iqr    = q3 - q1

    scores    = []
    is_outlier= []
    for row in rows:
        v = _to_number(row[ci] if ci < len(row) else None)
        if v is None:
            scores.append(None)
            is_outlier.append(None)
        elif method == 'zscore':
            z = abs((v - m) / s) if s else 0
            scores.append(round(z, 4))
            is_outlier.append(1 if z > 3 else 0)
        else:  # IQR
            lo = q1 - 1.5 * iqr
            hi = q3 + 1.5 * iqr
            score = max(0, v - hi) if v > hi else max(0, lo - v) if v < lo else 0
            scores.append(round(score, 4))
            is_outlier.append(1 if v < lo or v > hi else 0)

    new_headers = headers + [f'{params["column"]}_score', f'{params["column"]}_outlier']
    new_rows    = [list(r) + [scores[i], is_outlier[i]] for i, r in enumerate(rows)]
    n_out       = sum(1 for x in is_outlier if x == 1)

    return _result(new_headers, new_rows,
                   f'امتیاز پرت — {params["column"]}',
                   [['روش', method], ['پرت یافت شده', n_out]])


# ── 20. Cross Tabulation ──────────────────────────────────────────────────

def cross_tabulation(params, headers, rows):
    ci1    = _col_idx(headers, params['row_column'])
    ci2    = _col_idx(headers, params['col_column'])
    normalize = params.get('normalize', 'none')

    row_cats = sorted(set(str(r[ci1] if ci1 < len(r) else '') for r in rows))
    col_cats = sorted(set(str(r[ci2] if ci2 < len(r) else '') for r in rows))

    counts   = defaultdict(lambda: defaultdict(int))
    for row in rows:
        r = str(row[ci1] if ci1 < len(row) else '')
        c = str(row[ci2] if ci2 < len(row) else '')
        counts[r][c] += 1

    total = len(rows)
    out_headers = [params['row_column']] + col_cats + ['Total']
    out_rows    = []
    for rc in row_cats:
        row_vals = [counts[rc][cc] for cc in col_cats]
        row_total = sum(row_vals)
        if normalize == 'row':
            row_vals = [round(v/row_total*100, 1) if row_total else 0 for v in row_vals]
        elif normalize == 'col':
            row_vals = [round(counts[rc][cc] / sum(counts[r2][cc] for r2 in row_cats) * 100, 1) for cc in col_cats]
        elif normalize == 'total':
            row_vals = [round(v/total*100, 1) if total else 0 for v in row_vals]
        out_rows.append([rc] + row_vals + [sum(counts[rc][cc] for cc in col_cats)])

    out_rows.append(['Total'] + [sum(counts[rc][cc] for rc in row_cats) for cc in col_cats] + [total])

    return _result(out_headers, out_rows, 'جدول متقاطع',
                   [['ردیف', len(row_cats)], ['ستون', len(col_cats)], ['نرمال‌سازی', normalize]])


# ── 21. Frequency Table ───────────────────────────────────────────────────

def frequency_table(params, headers, rows):
    ci      = _col_idx(headers, params['column'])
    top_n   = int(params.get('top_n', 0))
    sort_by = params.get('sort_by', 'frequency')

    vals    = [str(r[ci] if ci < len(r) else '') for r in rows if not _is_empty(r[ci] if ci < len(r) else None)]
    counts  = Counter(vals)
    total   = sum(counts.values())

    if sort_by == 'value':
        items = sorted(counts.items(), key=lambda x: x[0])
    else:
        items = sorted(counts.items(), key=lambda x: x[1], reverse=True)

    if top_n:
        items = items[:top_n]

    out_headers = ['value', 'frequency', 'percent', 'cumulative_pct']
    out_rows    = []
    cumulative  = 0
    for val, cnt in items:
        pct = cnt / total * 100
        cumulative += pct
        out_rows.append([val, cnt, round(pct, 2), round(cumulative, 2)])

    return _result(out_headers, out_rows,
                   f'جدول فراوانی — {params["column"]}',
                   [['مقادیر یکتا', len(counts)], ['کل', total]])


# ── 22. Pareto Analysis ───────────────────────────────────────────────────

def pareto_analysis(params, headers, rows):
    cat_ci = _col_idx(headers, params['category_column'])
    val_ci = _col_idx(headers, params['value_column'])

    groups = defaultdict(float)
    for row in rows:
        cat = str(row[cat_ci] if cat_ci < len(row) else '')
        val = _to_number(row[val_ci] if val_ci < len(row) else None) or 0
        groups[cat] += val

    total   = sum(groups.values())
    items   = sorted(groups.items(), key=lambda x: x[1], reverse=True)

    out_headers = ['category', 'value', 'percent', 'cumulative_pct', 'is_vital_few']
    out_rows    = []
    cum = 0
    for cat, val in items:
        pct = val / total * 100 if total else 0
        cum += pct
        out_rows.append([cat, round(val, 2), round(pct, 2), round(cum, 2), 1 if cum <= 80 else 0])

    vital_few = sum(1 for r in out_rows if r[4] == 1)

    return _result(out_headers, out_rows, 'تحلیل پارتو',
                   [['دسته‌های حیاتی (80%)', vital_few],
                    ['کل دسته‌ها', len(items)],
                    ['قانون 80/20', f'{vital_few}/{len(items)}']])


# ── 23. Cohort Analysis ───────────────────────────────────────────────────

def cohort_analysis(params, headers, rows):
    user_ci   = _col_idx(headers, params['user_column'])
    date_ci   = _col_idx(headers, params['date_column'])
    event_ci  = _col_idx(headers, params.get('event_column', params['date_column']))

    # Find each user's first date (cohort)
    user_first = {}
    for row in rows:
        u = str(row[user_ci] if user_ci < len(row) else '')
        d = str(row[date_ci] if date_ci < len(row) else '')[:7]  # YYYY-MM
        if u not in user_first or d < user_first[u]:
            user_first[u] = d

    # Count users per cohort per period offset
    cohort_data = defaultdict(lambda: defaultdict(set))
    for row in rows:
        u      = str(row[user_ci] if user_ci < len(row) else '')
        d      = str(row[date_ci] if date_ci < len(row) else '')[:7]
        cohort = user_first.get(u, d)
        try:
            cy, cm = int(cohort[:4]), int(cohort[5:7])
            dy, dm = int(d[:4]),      int(d[5:7])
            offset = (dy - cy) * 12 + (dm - cm)
            cohort_data[cohort][offset].add(u)
        except Exception:
            pass

    cohorts   = sorted(cohort_data.keys())
    max_offset= max((max(offsets.keys()) for offsets in cohort_data.values()), default=0)

    out_headers = ['cohort'] + [f'month_{i}' for i in range(max_offset + 1)]
    out_rows    = []
    for cohort in cohorts:
        base = len(cohort_data[cohort].get(0, set()))
        row  = [cohort]
        for offset in range(max_offset + 1):
            cnt = len(cohort_data[cohort].get(offset, set()))
            pct = round(cnt / base * 100, 1) if base else 0
            row.append(pct)
        out_rows.append(row)

    return _result(out_headers, out_rows, 'تحلیل کوهورت',
                   [['کوهورت‌ها', len(cohorts)], ['بازه زمانی', f'{max_offset} ماه']])


# ── 24. Survival Analysis ─────────────────────────────────────────────────

def survival_analysis(params, headers, rows):
    time_ci  = _col_idx(headers, params['time_column'])
    event_ci = _col_idx(headers, params['event_column'])

    data = []
    for row in rows:
        t = _to_number(row[time_ci]  if time_ci  < len(row) else None)
        e_raw = row[event_ci] if event_ci < len(row) else None
        # Handle boolean values (True/False) as well as numbers
        if isinstance(e_raw, bool):
            e = 1 if e_raw else 0
        else:
            e = _to_number(e_raw)
        if t is not None and e is not None:
            data.append((t, int(e)))

    if not data:
        raise ValueError('داده‌های survival یافت نشد')

    # Kaplan-Meier estimator
    data.sort(key=lambda x: x[0])
    n = len(data)
    times_unique = sorted(set(t for t, e in data if e == 1))

    out_headers = ['time', 'n_at_risk', 'n_events', 'survival_prob']
    out_rows    = [['0', n, 0, 1.0]]
    S = 1.0
    remaining = n

    for t in times_unique:
        events = sum(1 for ti, ei in data if ti == t and ei == 1)
        if remaining > 0:
            S = S * (1 - events / remaining)
        censored_before = sum(1 for ti, ei in data if ti < t and ei == 0)
        remaining = sum(1 for ti, _ in data if ti >= t)
        out_rows.append([t, remaining, events, round(S, 4)])

    return _result(out_headers, out_rows, 'Kaplan-Meier',
                   [['n', n], ['رویداد', sum(1 for _, e in data if e == 1)],
                    ['سانسور', sum(1 for _, e in data if e == 0)]])


# ── 25. Bootstrap ─────────────────────────────────────────────────────────

def bootstrap(params, headers, rows):
    import random
    nums       = _get_col_nums(headers, rows, params['column'])
    n_iter     = int(params.get('n_iterations', 1000))
    stat       = params.get('statistic', 'mean')
    conf       = float(params.get('confidence', 95)) / 100

    if not nums:
        raise ValueError('مقدار عددی یافت نشد')

    random.seed(42)  # reproducible

    def compute_stat(sample):
        if stat == 'mean':   return _mean(sample)
        if stat == 'median': return _median(sample)
        if stat == 'std':    return _std(sample)
        if stat == 'min':    return min(sample)
        if stat == 'max':    return max(sample)
        return _mean(sample)

    boot_stats = []
    n = len(nums)
    for _ in range(n_iter):
        sample = [nums[random.randint(0, n-1)] for _ in range(n)]
        boot_stats.append(compute_stat(sample))

    boot_stats.sort()
    lo_idx = int((1 - conf) / 2 * n_iter)
    hi_idx = int((1 + conf) / 2 * n_iter)
    lo     = boot_stats[lo_idx]
    hi     = boot_stats[min(hi_idx, n_iter - 1)]
    obs    = compute_stat(nums)

    out_headers = ['parameter', 'value']
    out_rows    = [
        ['آماره', stat],
        ['مقدار مشاهده شده', round(obs, 4)],
        ['تکرار Bootstrap', n_iter],
        ['سطح اطمینان', f'{conf*100:.0f}%'],
        ['کران پایین', round(lo, 4)],
        ['کران بالا',  round(hi, 4)],
        ['فاصله', f'[{lo:.4f}, {hi:.4f}]'],
    ]

    return _result(out_headers, out_rows, 'Bootstrap',
                   [['آماره', stat], ['فاصله اطمینان', f'[{lo:.4f}, {hi:.4f}]']])
