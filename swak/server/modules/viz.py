# cython: language_level=3
"""
SWAK — Visualization Module (19 tools)
Prepares chart data + specs for JS rendering (Chart.js / D3)
Python side: data aggregation and transformation
JS side: actual rendering in Excel task pane
"""

import math
import re
from collections import Counter, defaultdict


def run(tool_id: str, params: dict, headers: list, rows: list) -> dict:
    fn_map = {
        'bar-chart':        bar_chart,
        'line-chart':       line_chart,
        'scatter-plot':     scatter_plot,
        'pie-chart':        pie_chart,
        'histogram':        histogram,
        'box-plot':         box_plot,
        'heatmap':          heatmap,
        'bubble-chart':     bubble_chart,
        'area-chart':       area_chart,
        'treemap':          treemap,
        'funnel-chart':     funnel_chart,
        'waterfall-chart':  waterfall_chart,
        'radar-chart':      radar_chart,
        'gantt-chart':      gantt_chart,
        'density-plot':     density_plot,
        'violin-plot':      violin_plot,
        'sankey-diagram':   sankey_diagram,
        'sparklines':       sparklines,
        'correlation-heatmap': correlation_heatmap,
    }
    fn = fn_map.get(tool_id)
    if not fn:
        raise ValueError(f'ابزار ناشناخته: {tool_id}')
    return fn(params, headers, list(rows))


def _is_empty(v):
    return v is None or (isinstance(v, float) and math.isnan(v)) or \
           (isinstance(v, str) and v.strip() == '')

def _to_number(v):
    if _is_empty(v): return None
    try: return float(str(v).replace(',', '').replace('،', ''))
    except: return None

def _mean(vals): return sum(vals)/len(vals) if vals else 0
def _std(vals):
    m = _mean(vals)
    return math.sqrt(sum((x-m)**2 for x in vals)/len(vals)) if vals else 0

def _col_idx(headers, col):
    try: return headers.index(col)
    except: raise ValueError(f'ستون "{col}" یافت نشد')

def _percentile(s, p):
    if not s: return 0
    i = (p/100)*(len(s)-1)
    lo, hi = int(i), math.ceil(i)
    return s[lo] + (s[hi]-s[lo])*(i-lo) if lo != hi else s[lo]

def _chart_result(chart_type, chart_data, title, stats):
    """Standard return format: chart_data goes to JS renderer"""
    import json
    return {
        'headers': ['chart_type', 'title', 'data_points'],
        'rows':    [[chart_type, title, str(len(chart_data.get('labels', chart_data.get('x', []))))]],
        'summary': {'title': title, 'stats': stats},
        'chart':   chart_data,       # JS picks this up and renders
    }


# ── 1. Bar Chart ──────────────────────────────────────────────────────────

def bar_chart(params, headers, rows):
    x_col     = params.get('x_column', headers[0])
    y_cols    = params.get('y_columns', headers[1:3])
    if isinstance(y_cols, str): y_cols = [c.strip() for c in y_cols.split(',')]
    agg_fn    = params.get('aggregation', 'sum')
    orientation = params.get('orientation', 'vertical')

    xi   = _col_idx(headers, x_col)
    yis  = [_col_idx(headers, c) for c in y_cols]

    # Aggregate by X
    groups = defaultdict(lambda: defaultdict(list))
    for row in rows:
        k = str(row[xi] if xi < len(row) else '')
        for yi, yc in zip(yis, y_cols):
            v = _to_number(row[yi] if yi < len(row) else None)
            if v is not None:
                groups[k][yc].append(v)

    labels = sorted(groups.keys())

    def agg(vals):
        if not vals: return 0
        if agg_fn == 'sum':   return round(sum(vals), 4)
        if agg_fn == 'mean':  return round(_mean(vals), 4)
        if agg_fn == 'count': return len(vals)
        if agg_fn == 'max':   return round(max(vals), 4)
        if agg_fn == 'min':   return round(min(vals), 4)
        return round(sum(vals), 4)

    datasets = [{'label': yc, 'data': [agg(groups[l][yc]) for l in labels]}
                for yc in y_cols]
    title = params.get('title', f'Bar Chart — {x_col}')

    chart_data = {
        'type': 'bar', 'orientation': orientation,
        'labels': labels[:50], 'datasets': datasets,
        'options': {'title': title, 'x_label': x_col,
                    'y_label': ', '.join(y_cols), 'aggregation': agg_fn}
    }

    return _chart_result('bar', chart_data, title,
                         [['X', x_col], ['Y', ', '.join(y_cols)],
                          ['گروه‌ها', len(labels)], ['تجمیع', agg_fn]])


# ── 2. Line Chart ─────────────────────────────────────────────────────────

def line_chart(params, headers, rows):
    x_col  = params.get('x_column', headers[0])
    y_cols = params.get('y_columns', headers[1:3])
    if isinstance(y_cols, str): y_cols = [c.strip() for c in y_cols.split(',')]
    smooth = params.get('smooth', 'false') == 'true'

    xi   = _col_idx(headers, x_col)
    yis  = [_col_idx(headers, c) for c in y_cols]

    x_vals    = [str(row[xi] if xi < len(row) else '') for row in rows]
    datasets  = [{'label': yc, 'data': [_to_number(row[yi] if yi < len(row) else None) for row in rows],
                  'tension': 0.4 if smooth else 0}
                 for yi, yc in zip(yis, y_cols)]

    title = params.get('title', f'Line Chart — {x_col}')
    chart_data = {
        'type': 'line', 'labels': x_vals[:500], 'datasets': datasets,
        'options': {'title': title, 'smooth': smooth}
    }

    return _chart_result('line', chart_data, title,
                         [['نقاط داده', len(rows)], ['سری‌ها', len(y_cols)]])


# ── 3. Scatter Plot ───────────────────────────────────────────────────────

def scatter_plot(params, headers, rows):
    x_col  = params.get('x_column', headers[0])
    y_col  = params.get('y_column', headers[1] if len(headers) > 1 else headers[0])
    color_col = params.get('color_column', '')

    xi  = _col_idx(headers, x_col)
    yi  = _col_idx(headers, y_col)
    ci  = _col_idx(headers, color_col) if color_col in headers else None

    points = []
    for row in rows:
        x = _to_number(row[xi] if xi < len(row) else None)
        y = _to_number(row[yi] if yi < len(row) else None)
        if x is not None and y is not None:
            p = {'x': x, 'y': y}
            if ci is not None:
                p['category'] = str(row[ci] if ci < len(row) else '')
            points.append(p)

    # Compute trend line
    xs    = [p['x'] for p in points]
    ys    = [p['y'] for p in points]
    mx, my= _mean(xs), _mean(ys)
    cov   = sum((x-mx)*(y-my) for x,y in zip(xs,ys))/(len(xs)-1) if len(xs)>1 else 0
    vx    = sum((x-mx)**2 for x in xs)/(len(xs)-1) if len(xs)>1 else 1
    slope = cov/vx if vx else 0
    intercept = my - slope*mx
    corr  = slope*(_std(xs)/(_std(ys) or 1)) if xs and ys else 0

    title = params.get('title', f'Scatter — {x_col} vs {y_col}')
    chart_data = {
        'type': 'scatter', 'data': points[:1000],
        'trend': {'slope': round(slope,4), 'intercept': round(intercept,4),
                  'r': round(corr,4)},
        'options': {'title': title, 'x_label': x_col, 'y_label': y_col}
    }

    return _chart_result('scatter', chart_data, title,
                         [['نقاط', len(points)], ['همبستگی', round(corr, 4)]])


# ── 4. Pie / Donut Chart ──────────────────────────────────────────────────

def pie_chart(params, headers, rows):
    label_col = params.get('label_column', headers[0])
    value_col = params.get('value_column', headers[1] if len(headers) > 1 else headers[0])
    chart_type= params.get('type', 'pie')  # pie | donut
    top_n     = int(params.get('top_n', 10))

    li  = _col_idx(headers, label_col)
    vi  = _col_idx(headers, value_col)

    groups = defaultdict(float)
    for row in rows:
        k = str(row[li] if li < len(row) else '')
        v = _to_number(row[vi] if vi < len(row) else None) or 0
        groups[k] += v

    items  = sorted(groups.items(), key=lambda x: x[1], reverse=True)
    top    = items[:top_n]
    other  = sum(v for _, v in items[top_n:])
    if other > 0:
        top.append(('سایر', other))

    total  = sum(v for _, v in top)
    labels = [k for k,_ in top]
    values = [round(v, 4) for _,v in top]
    pcts   = [round(v/total*100, 2) if total else 0 for v in values]

    title = params.get('title', f'{chart_type.title()} — {label_col}')
    chart_data = {
        'type': chart_type, 'labels': labels, 'data': values,
        'percentages': pcts,
        'options': {'title': title, 'cutout': '50%' if chart_type == 'donut' else '0%'}
    }

    return _chart_result(chart_type, chart_data, title,
                         [['دسته‌ها', len(labels)], ['کل', round(total, 2)]])


# ── 5. Histogram ──────────────────────────────────────────────────────────

def histogram(params, headers, rows):
    col    = params.get('column', headers[0])
    n_bins = int(params.get('n_bins', 20))
    ci     = _col_idx(headers, col)

    nums   = sorted([_to_number(r[ci] if ci < len(r) else None) for r in rows
                     if _to_number(r[ci] if ci < len(r) else None) is not None])
    if not nums:
        raise ValueError('مقدار عددی یافت نشد')

    mn, mx = nums[0], nums[-1]
    rng    = mx - mn or 1
    width  = rng / n_bins

    bins   = [(mn + i*width, mn + (i+1)*width) for i in range(n_bins)]
    counts = [sum(1 for v in nums if lo <= v < hi) + (1 if i==n_bins-1 and nums[-1] <= hi else 0)
              for i, (lo,hi) in enumerate(bins)]

    labels = [f'{lo:.2f}' for lo,_ in bins]
    title  = params.get('title', f'Histogram — {col}')

    chart_data = {
        'type': 'bar', 'labels': labels, 'datasets': [{'label': col, 'data': counts}],
        'options': {'title': title, 'x_label': col, 'y_label': 'Frequency',
                    'bar_padding': 0}
    }

    return _chart_result('histogram', chart_data, title,
                         [['bins', n_bins], ['n', len(nums)],
                          ['mean', round(_mean(nums), 2)], ['std', round(_std(nums), 2)]])


# ── 6. Box Plot ───────────────────────────────────────────────────────────

def box_plot(params, headers, rows):
    cols     = params.get('columns', headers[:5])
    if isinstance(cols, str): cols = [c.strip() for c in cols.split(',')]
    group_col= params.get('group_column', '')

    box_data = []
    for col in cols:
        ci   = _col_idx(headers, col)
        nums = sorted([_to_number(r[ci] if ci < len(r) else None) for r in rows
                       if _to_number(r[ci] if ci < len(r) else None) is not None])
        if not nums: continue
        q1   = _percentile(nums, 25)
        q2   = _percentile(nums, 50)
        q3   = _percentile(nums, 75)
        iqr  = q3 - q1
        wlo  = max(nums[0], q1 - 1.5*iqr)
        whi  = min(nums[-1], q3 + 1.5*iqr)
        outs = [v for v in nums if v < wlo or v > whi]

        box_data.append({
            'label': col,
            'q1': round(q1, 4), 'q2': round(q2, 4), 'q3': round(q3, 4),
            'whisker_low': round(wlo, 4), 'whisker_high': round(whi, 4),
            'outliers': outs[:20], 'n': len(nums),
        })

    title = params.get('title', 'Box Plot')
    chart_data = {'type': 'boxplot', 'datasets': box_data,
                  'options': {'title': title}}

    return _chart_result('boxplot', chart_data, title,
                         [['ستون‌ها', len(box_data)]])


# ── 7. Heatmap ────────────────────────────────────────────────────────────

def heatmap(params, headers, rows):
    row_col = params.get('row_column', headers[0])
    col_col = params.get('col_column', headers[1] if len(headers) > 1 else headers[0])
    val_col = params.get('value_column', headers[2] if len(headers) > 2 else headers[0])

    ri  = _col_idx(headers, row_col)
    ci  = _col_idx(headers, col_col)
    vi  = _col_idx(headers, val_col)

    row_cats = sorted(set(str(r[ri] if ri < len(r) else '') for r in rows))
    col_cats = sorted(set(str(r[ci] if ci < len(r) else '') for r in rows))

    matrix   = defaultdict(lambda: defaultdict(list))
    for row in rows:
        rk = str(row[ri] if ri < len(row) else '')
        ck = str(row[ci] if ci < len(row) else '')
        v  = _to_number(row[vi] if vi < len(row) else None)
        if v is not None:
            matrix[rk][ck].append(v)

    data = [[round(_mean(matrix[rk][ck]), 4) if matrix[rk][ck] else None
             for ck in col_cats] for rk in row_cats]

    title = params.get('title', f'Heatmap — {val_col}')
    chart_data = {
        'type': 'heatmap', 'x_labels': col_cats, 'y_labels': row_cats,
        'data': data, 'options': {'title': title, 'color_scale': 'blues'}
    }

    return _chart_result('heatmap', chart_data, title,
                         [['ردیف', len(row_cats)], ['ستون', len(col_cats)]])


# ── 8. Bubble Chart ───────────────────────────────────────────────────────

def bubble_chart(params, headers, rows):
    x_col = params.get('x_column', headers[0])
    y_col = params.get('y_column', headers[1] if len(headers) > 1 else headers[0])
    r_col = params.get('size_column', headers[2] if len(headers) > 2 else headers[0])
    l_col = params.get('label_column', '')

    xi, yi, ri = _col_idx(headers, x_col), _col_idx(headers, y_col), _col_idx(headers, r_col)
    li = _col_idx(headers, l_col) if l_col in headers else None

    r_vals = [_to_number(row[ri] if ri < len(row) else None) for row in rows]
    r_max  = max((v for v in r_vals if v), default=1)

    bubbles = []
    for i, row in enumerate(rows):
        x = _to_number(row[xi] if xi < len(row) else None)
        y = _to_number(row[yi] if yi < len(row) else None)
        r = _to_number(row[ri] if ri < len(row) else None)
        if x is not None and y is not None and r is not None:
            b = {'x': x, 'y': y, 'r': round(r/r_max*30 + 3, 2)}
            if li: b['label'] = str(row[li] if li < len(row) else '')
            bubbles.append(b)

    title = params.get('title', f'Bubble — {x_col} × {y_col}')
    chart_data = {'type': 'bubble', 'data': bubbles[:200],
                  'options': {'title': title, 'x_label': x_col,
                              'y_label': y_col, 'size_label': r_col}}

    return _chart_result('bubble', chart_data, title,
                         [['حباب‌ها', len(bubbles)]])


# ── 9. Area Chart ─────────────────────────────────────────────────────────

def area_chart(params, headers, rows):
    x_col  = params.get('x_column', headers[0])
    y_cols = params.get('y_columns', headers[1:3])
    if isinstance(y_cols, str): y_cols = [c.strip() for c in y_cols.split(',')]
    stacked= params.get('stacked', 'false') == 'true'

    xi   = _col_idx(headers, x_col)
    yis  = [_col_idx(headers, c) for c in y_cols]
    x_vals  = [str(row[xi] if xi < len(row) else '') for row in rows]
    datasets= [{'label': yc, 'data': [_to_number(row[yi] if yi < len(row) else None) for row in rows],
                'fill': True, 'stack': 'stack' if stacked else ''}
               for yi, yc in zip(yis, y_cols)]

    title = params.get('title', f'Area Chart — {x_col}')
    chart_data = {'type': 'line', 'fill': True, 'labels': x_vals[:500],
                  'datasets': datasets, 'options': {'title': title, 'stacked': stacked}}

    return _chart_result('area', chart_data, title,
                         [['نقاط', len(rows)], ['سری‌ها', len(y_cols)], ['stacked', stacked]])


# ── 10. Treemap ───────────────────────────────────────────────────────────

def treemap(params, headers, rows):
    label_col = params.get('label_column', headers[0])
    value_col = params.get('value_column', headers[1] if len(headers) > 1 else headers[0])
    parent_col= params.get('parent_column', '')

    li = _col_idx(headers, label_col)
    vi = _col_idx(headers, value_col)
    pi = _col_idx(headers, parent_col) if parent_col in headers else None

    nodes = []
    for row in rows:
        label = str(row[li] if li < len(row) else '')
        value = _to_number(row[vi] if vi < len(row) else None) or 0
        node  = {'label': label, 'value': round(value, 4)}
        if pi: node['parent'] = str(row[pi] if pi < len(row) else '')
        nodes.append(node)

    total = sum(n['value'] for n in nodes)
    title = params.get('title', f'Treemap — {label_col}')
    chart_data = {'type': 'treemap', 'data': nodes[:100],
                  'options': {'title': title, 'total': total}}

    return _chart_result('treemap', chart_data, title,
                         [['گره‌ها', len(nodes)], ['کل', round(total, 2)]])


# ── 11. Funnel Chart ──────────────────────────────────────────────────────

def funnel_chart(params, headers, rows):
    label_col = params.get('label_column', headers[0])
    value_col = params.get('value_column', headers[1] if len(headers) > 1 else headers[0])

    li   = _col_idx(headers, label_col)
    vi   = _col_idx(headers, value_col)

    stages= [(str(r[li] if li < len(r) else ''), _to_number(r[vi] if vi < len(r) else None) or 0)
             for r in rows]
    stages= [(l, v) for l, v in stages if v > 0]
    stages.sort(key=lambda x: x[1], reverse=True)

    first = stages[0][1] if stages else 1
    data  = [{'label': l, 'value': round(v,4), 'pct': round(v/first*100,1)}
             for l, v in stages]

    title = params.get('title', 'Funnel Chart')
    chart_data = {'type': 'funnel', 'data': data,
                  'options': {'title': title}}

    return _chart_result('funnel', chart_data, title,
                         [['مراحل', len(data)],
                          ['نرخ تبدیل', f'{data[-1]["pct"]}%' if data else '0%']])


# ── 12. Waterfall Chart ───────────────────────────────────────────────────

def waterfall_chart(params, headers, rows):
    label_col = params.get('label_column', headers[0])
    value_col = params.get('value_column', headers[1] if len(headers) > 1 else headers[0])

    li = _col_idx(headers, label_col)
    vi = _col_idx(headers, value_col)

    items    = [(str(r[li] if li < len(r) else ''), _to_number(r[vi] if vi < len(r) else None) or 0)
                for r in rows]
    cumulative = 0
    bars       = []
    for label, val in items:
        bars.append({'label': label, 'value': round(val,4),
                     'start': round(cumulative,4),
                     'end':   round(cumulative+val,4),
                     'type':  'positive' if val >= 0 else 'negative'})
        cumulative += val

    total_bar = {'label': 'مجموع', 'value': round(cumulative,4),
                 'start': 0, 'end': round(cumulative,4), 'type': 'total'}
    bars.append(total_bar)

    title = params.get('title', 'Waterfall Chart')
    chart_data = {'type': 'waterfall', 'data': bars,
                  'options': {'title': title}}

    return _chart_result('waterfall', chart_data, title,
                         [['مراحل', len(bars)-1], ['مجموع', round(cumulative,2)]])


# ── 13. Radar Chart ───────────────────────────────────────────────────────

def radar_chart(params, headers, rows):
    metrics   = params.get('metric_columns', headers[1:])
    if isinstance(metrics, str): metrics = [c.strip() for c in metrics.split(',')]
    label_col = params.get('label_column', headers[0])
    max_rows  = int(params.get('max_series', 5))

    li = _col_idx(headers, label_col)

    datasets = []
    for row in rows[:max_rows]:
        label = str(row[li] if li < len(row) else '')
        vals  = [_to_number(row[_col_idx(headers, m)] if _col_idx(headers, m) < len(row) else None) or 0
                 for m in metrics if m in headers]
        datasets.append({'label': label, 'data': vals})

    title = params.get('title', 'Radar Chart')
    chart_data = {'type': 'radar', 'labels': metrics, 'datasets': datasets,
                  'options': {'title': title}}

    return _chart_result('radar', chart_data, title,
                         [['محور', len(metrics)], ['سری‌ها', len(datasets)]])


# ── 14. Gantt Chart ───────────────────────────────────────────────────────

def gantt_chart(params, headers, rows):
    task_col  = params.get('task_column',  headers[0])
    start_col = params.get('start_column', headers[1] if len(headers) > 1 else headers[0])
    end_col   = params.get('end_column',   headers[2] if len(headers) > 2 else headers[0])
    cat_col   = params.get('category_column', '')

    ti = _col_idx(headers, task_col)
    si = _col_idx(headers, start_col)
    ei = _col_idx(headers, end_col)
    ci = _col_idx(headers, cat_col) if cat_col in headers else None

    tasks = []
    for row in rows:
        task  = str(row[ti] if ti < len(row) else '')
        start = str(row[si] if si < len(row) else '')
        end   = str(row[ei] if ei < len(row) else '')
        cat   = str(row[ci] if ci and ci < len(row) else 'default')
        tasks.append({'task': task, 'start': start, 'end': end, 'category': cat})

    title = params.get('title', 'Gantt Chart')
    chart_data = {'type': 'gantt', 'tasks': tasks,
                  'options': {'title': title}}

    return _chart_result('gantt', chart_data, title,
                         [['وظایف', len(tasks)]])


# ── 15. Density Plot ──────────────────────────────────────────────────────

def density_plot(params, headers, rows):
    col    = params.get('column', headers[0])
    n_pts  = int(params.get('n_points', 100))
    ci     = _col_idx(headers, col)
    nums   = [_to_number(r[ci] if ci < len(r) else None) for r in rows
              if _to_number(r[ci] if ci < len(r) else None) is not None]

    if not nums: raise ValueError('مقدار عددی یافت نشد')

    mn, mx = min(nums), max(nums)
    m, s   = _mean(nums), _std(nums) or 1
    bw     = 1.06 * s * len(nums)**(-0.2)  # Silverman's rule

    xs = [mn + (mx-mn)*i/(n_pts-1) for i in range(n_pts)]
    ys = []
    for x in xs:
        density = _mean([math.exp(-0.5*((x-xi)/bw)**2)/(bw*math.sqrt(2*math.pi))
                         for xi in nums])
        ys.append(round(density, 6))

    title = params.get('title', f'Density — {col}')
    chart_data = {'type': 'line', 'fill': True, 'labels': [round(x,3) for x in xs],
                  'datasets': [{'label': f'KDE {col}', 'data': ys}],
                  'options': {'title': title, 'x_label': col, 'y_label': 'Density'}}

    return _chart_result('density', chart_data, title,
                         [['n', len(nums)], ['bandwidth', round(bw,4)]])


# ── 16. Violin Plot ───────────────────────────────────────────────────────

def violin_plot(params, headers, rows):
    cols = params.get('columns', headers[:5])
    if isinstance(cols, str): cols = [c.strip() for c in cols.split(',')]

    violins = []
    for col in cols:
        ci   = _col_idx(headers, col) if col in headers else 0
        nums = sorted([_to_number(r[ci] if ci < len(r) else None) for r in rows
                       if _to_number(r[ci] if ci < len(r) else None) is not None])
        if not nums: continue
        q1, q2, q3 = _percentile(nums,25), _percentile(nums,50), _percentile(nums,75)
        # KDE points for violin shape
        m, s, n = _mean(nums), _std(nums) or 1, len(nums)
        bw = 1.06*s*n**(-0.2)
        y_pts= [nums[0] + (nums[-1]-nums[0])*i/20 for i in range(21)]
        kde  = [round(_mean([math.exp(-0.5*((y-xi)/bw)**2) for xi in nums]), 4) for y in y_pts]
        violins.append({'label': col, 'kde_x': kde, 'kde_y': [round(y,4) for y in y_pts],
                        'q1':round(q1,4), 'q2':round(q2,4), 'q3':round(q3,4),
                        'min':nums[0], 'max':nums[-1]})

    title = params.get('title', 'Violin Plot')
    chart_data = {'type': 'violin', 'datasets': violins,
                  'options': {'title': title}}

    return _chart_result('violin', chart_data, title,
                         [['ستون‌ها', len(violins)]])


# ── 17. Sankey Diagram ────────────────────────────────────────────────────

def sankey_diagram(params, headers, rows):
    from_col = params.get('from_column', headers[0])
    to_col   = params.get('to_column', headers[1] if len(headers) > 1 else headers[0])
    val_col  = params.get('value_column', headers[2] if len(headers) > 2 else headers[0])

    fi = _col_idx(headers, from_col)
    ti = _col_idx(headers, to_col)
    vi = _col_idx(headers, val_col)

    flows = defaultdict(float)
    for row in rows:
        src = str(row[fi] if fi < len(row) else '')
        tgt = str(row[ti] if ti < len(row) else '')
        val = _to_number(row[vi] if vi < len(row) else None) or 0
        flows[(src, tgt)] += val

    nodes = list(set(k for pair in flows for k in pair))
    links = [{'source': src, 'target': tgt, 'value': round(val, 4)}
             for (src, tgt), val in sorted(flows.items(), key=lambda x: -x[1])[:50]]

    title = params.get('title', f'Sankey — {from_col} → {to_col}')
    chart_data = {'type': 'sankey', 'nodes': nodes, 'links': links,
                  'options': {'title': title}}

    return _chart_result('sankey', chart_data, title,
                         [['گره‌ها', len(nodes)], ['لینک‌ها', len(links)]])


# ── 18. Sparklines ────────────────────────────────────────────────────────

def sparklines(params, headers, rows):
    col    = params.get('column', headers[0])
    group_col = params.get('group_column', '')
    ci     = _col_idx(headers, col)
    gi     = _col_idx(headers, group_col) if group_col in headers else None

    if gi:
        groups = defaultdict(list)
        for row in rows:
            k = str(row[gi] if gi < len(row) else '')
            v = _to_number(row[ci] if ci < len(row) else None)
            if v is not None: groups[k].append(v)
        sparkline_data = [{'label': k, 'data': v[:50], 'min': round(min(v),2),
                           'max': round(max(v),2), 'last': round(v[-1],2)}
                          for k, v in groups.items()]
    else:
        vals = [_to_number(r[ci] if ci < len(r) else None) for r in rows if _to_number(r[ci] if ci < len(r) else None) is not None]
        sparkline_data = [{'label': col, 'data': vals[:200]}]

    title = params.get('title', f'Sparklines — {col}')
    chart_data = {'type': 'sparklines', 'series': sparkline_data,
                  'options': {'title': title}}

    return _chart_result('sparklines', chart_data, title,
                         [['سری‌ها', len(sparkline_data)]])


# ── 19. Correlation Heatmap ───────────────────────────────────────────────

def correlation_heatmap(params, headers, rows):
    cols = params.get('columns', headers)
    if isinstance(cols, str): cols = [c.strip() for c in cols.split(',')]
    method = params.get('method', 'pearson')

    col_data = {}
    for col in cols:
        if col not in headers: continue
        ci = headers.index(col)
        col_data[col] = [_to_number(r[ci] if ci < len(r) else None) for r in rows
                         if _to_number(r[ci] if ci < len(r) else None) is not None]

    valid_cols = [c for c in cols if c in col_data and col_data[c]]

    matrix = []
    for rc in valid_cols:
        row_vals = []
        for cc in valid_cols:
            x = col_data[rc]
            y = col_data[cc]
            n = min(len(x), len(y))
            if n < 2: row_vals.append(0); continue
            mx, my = _mean(x[:n]), _mean(y[:n])
            cov    = sum((x[i]-mx)*(y[i]-my) for i in range(n))/(n-1)
            sx, sy = _std(x[:n])+1e-9, _std(y[:n])+1e-9
            row_vals.append(round(cov/(sx*sy), 4))
        matrix.append(row_vals)

    title = params.get('title', 'Correlation Heatmap')
    chart_data = {
        'type': 'heatmap', 'x_labels': valid_cols, 'y_labels': valid_cols,
        'data': matrix, 'options': {'title': title, 'color_scale': 'rdbu',
                                    'min': -1, 'max': 1}
    }

    return _chart_result('correlation_heatmap', chart_data, title,
                         [['ستون‌ها', len(valid_cols)], ['روش', method]])
