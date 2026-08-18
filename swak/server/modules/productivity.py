# cython: language_level=3
"""
SWAK — Productivity Module (14 tools)
Excel-specific productivity tools via Office.js bridge
"""

import re
import math
import json
from datetime import datetime, timedelta
from collections import defaultdict


def run(tool_id: str, params: dict, headers: list, rows: list) -> dict:
    fn_map = {
        'auto-format':        auto_format,
        'conditional-format': conditional_format,
        'create-chart':       create_chart,
        'freeze-panes':       freeze_panes,
        'add-filter':         add_filter,
        'protect-sheet':      protect_sheet,
        'named-range':        named_range,
        'data-validation':    data_validation,
        'add-hyperlinks':     add_hyperlinks,
        'summarize-sheet':    summarize_sheet,
        'batch-formulas':     batch_formulas,
        'clean-formatting':   clean_formatting,
        'workbook-toc':       workbook_toc,
        'schedule-refresh':   schedule_refresh,
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
    try: return float(str(v).replace(',', ''))
    except: return None

def _result(headers, rows, title, stats, note='', office_commands=None):
    r = {'headers': headers, 'rows': rows,
         'summary': {'title': title, 'stats': stats, 'note': note}}
    if office_commands:
        r['office_commands'] = office_commands  # JS side executes these
    return r


# ── 1. Auto Format ────────────────────────────────────────────────────────

def auto_format(params, headers, rows):
    """
    Detect column types and return formatting instructions for Office.js.
    JS side applies the actual formatting via Excel.run.
    """
    style   = params.get('style', 'swak_dark')   # swak_dark | minimal | colorful
    formats = []

    PALETTES = {
        'swak_dark': {
            'header_bg': '#1a1a3e', 'header_fg': '#a0a0ff',
            'alt_bg': '#0a0a1a',    'border': '#2a2a5a',
            'number': '#7ab8f5',    'date': '#a0d9a0',
            'text': '#e0e0ff',
        },
        'minimal': {
            'header_bg': '#2563eb', 'header_fg': '#ffffff',
            'alt_bg': '#f8fafc',    'border': '#e2e8f0',
            'number': '#1e40af',    'date': '#059669',
            'text': '#111827',
        },
        'colorful': {
            'header_bg': '#7c3aed', 'header_fg': '#ffffff',
            'alt_bg': '#faf5ff',    'border': '#ddd6fe',
            'number': '#2563eb',    'date': '#059669',
            'text': '#111827',
        },
    }

    pal = PALETTES.get(style, PALETTES['swak_dark'])

    # Detect column types
    col_types = []
    for i, h in enumerate(headers):
        vals = [r[i] if i < len(r) else None for r in rows[:20]]
        nn   = [v for v in vals if not _is_empty(v)]
        nums = [_to_number(v) for v in nn if _to_number(v) is not None]
        dates= sum(1 for v in nn if re.search(r'\d{4}[-/]\d{2}', str(v)))

        if len(nums) > len(nn) * 0.8:
            all_int = all(float(v).is_integer() for v in nums)
            col_types.append('integer' if all_int else 'float')
        elif dates > len(nn) * 0.5:
            col_types.append('date')
        else:
            col_types.append('text')

    # Build format spec
    for i, (h, t) in enumerate(zip(headers, col_types)):
        fmt = {
            'col_index':  i,
            'col_name':   h,
            'type':       t,
            'number_fmt': '#,##0' if t == 'integer' else '#,##0.00' if t == 'float' else
                          'YYYY-MM-DD' if t == 'date' else '@',
            'alignment':  'right' if t in ('integer', 'float') else
                          'center' if t == 'date' else 'left',
            'font_color': pal['number'] if t in ('integer','float') else
                          pal['date'] if t == 'date' else pal['text'],
        }
        formats.append(fmt)

    # Return both instructions for JS and summary table
    out_rows = [[f['col_name'], f['type'], f['number_fmt'], f['alignment']] for f in formats]

    return _result(
        ['column', 'detected_type', 'number_format', 'alignment'],
        out_rows,
        f'فرمت‌بندی خودکار ({style})',
        [['style', style], ['ستون‌ها', len(headers)]],
        note=json.dumps({'palette': pal, 'column_formats': formats}),
        office_commands=[{'action': 'apply_format', 'palette': pal, 'formats': formats}]
    )


# ── 2. Conditional Formatting ─────────────────────────────────────────────

def conditional_format(params, headers, rows):
    col      = params.get('column', headers[0])
    rule     = params.get('rule', 'color_scale')
    ci       = headers.index(col) if col in headers else 0
    nums     = [_to_number(r[ci] if ci < len(r) else None) for r in rows]
    nums_val = [v for v in nums if v is not None]

    instructions = []
    if rule == 'color_scale' and nums_val:
        mn, mx = min(nums_val), max(nums_val)
        for i, v in enumerate(nums):
            if v is None: continue
            ratio = (v - mn) / (mx - mn) if mx != mn else 0
            r_c   = int(255 * (1 - ratio))
            g_c   = int(255 * ratio)
            color = f'#{r_c:02X}{g_c:02X}40'
            instructions.append({'row': i + 1, 'col': ci, 'bg_color': color})

    elif rule == 'data_bar' and nums_val:
        mn, mx = min(nums_val), max(nums_val)
        for i, v in enumerate(nums):
            if v is None: continue
            pct = int((v - mn) / (mx - mn) * 100) if mx != mn else 0
            instructions.append({'row': i + 1, 'col': ci, 'bar_pct': pct, 'bar_color': '#4c6ef5'})

    elif rule == 'top_n':
        n        = int(params.get('n', 10))
        top_vals = set(sorted(nums_val, reverse=True)[:n])
        for i, v in enumerate(nums):
            if v in top_vals:
                instructions.append({'row': i + 1, 'col': ci, 'bg_color': '#1a3e1a'})

    elif rule == 'above_avg' and nums_val:
        avg = sum(nums_val) / len(nums_val)
        for i, v in enumerate(nums):
            if v is not None and v > avg:
                instructions.append({'row': i + 1, 'col': ci, 'bg_color': '#1a3e1a'})
            elif v is not None and v < avg:
                instructions.append({'row': i + 1, 'col': ci, 'bg_color': '#3e1a1a'})

    out_rows = [[ins.get('row', ''), ins.get('col', ''),
                 ins.get('bg_color', ''), ins.get('bar_pct', '')] for ins in instructions[:100]]

    return _result(
        ['row', 'col', 'bg_color', 'bar_pct'],
        out_rows,
        f'قالب‌بندی شرطی — {col} ({rule})',
        [['قانون', rule], ['دستورالعمل', len(instructions)]],
        office_commands=[{'action': 'conditional_format', 'instructions': instructions}]
    )


# ── 3. Create Chart ───────────────────────────────────────────────────────

def create_chart(params, headers, rows):
    chart_type = params.get('chart_type', 'bar')
    x_col      = params.get('x_column', headers[0])
    y_cols     = params.get('y_columns', headers[1:3])
    if isinstance(y_cols, str): y_cols = [c.strip() for c in y_cols.split(',')]
    title      = params.get('title', f'SWAK Chart — {chart_type}')

    xi = headers.index(x_col) if x_col in headers else 0
    yis= [headers.index(c) for c in y_cols if c in headers]

    # Prepare chart data
    x_vals  = [str(r[xi] if xi < len(r) else '') for r in rows]
    y_data  = [[_to_number(r[yi] if yi < len(r) else None) for r in rows] for yi in yis]

    chart_spec = {
        'type':   chart_type,
        'title':  title,
        'x':      x_vals[:50],
        'series': [{'name': headers[yi], 'data': y_data[i][:50]} for i, yi in enumerate(yis)],
        'colors': ['#4c6ef5', '#f03e3e', '#12b886', '#fab005', '#be4bdb'],
    }

    out_rows = [[headers[yi], len([v for v in y_data[i] if v is not None])]
                for i, yi in enumerate(yis)]

    return _result(
        ['series', 'data_points'],
        out_rows,
        f'ایجاد نمودار — {chart_type}',
        [['نوع', chart_type], ['محور X', x_col], ['سری‌ها', len(yis)]],
        note=json.dumps(chart_spec),
        office_commands=[{'action': 'create_chart', 'spec': chart_spec}]
    )


# ── 4. Freeze Panes ───────────────────────────────────────────────────────

def freeze_panes(params, headers, rows):
    freeze_row = int(params.get('freeze_row', 1))
    freeze_col = int(params.get('freeze_col', 0))

    return _result(
        ['action', 'value'],
        [['freeze_row', freeze_row], ['freeze_col', freeze_col]],
        'ثابت کردن ردیف/ستون',
        [['ردیف', freeze_row], ['ستون', freeze_col]],
        office_commands=[{'action': 'freeze_panes', 'row': freeze_row, 'col': freeze_col}]
    )


# ── 5. Add AutoFilter ─────────────────────────────────────────────────────

def add_filter(params, headers, rows):
    col    = params.get('column', '')
    values = params.get('filter_values', '')

    return _result(
        ['action', 'column', 'values'],
        [['add_filter', col, values]],
        'افزودن فیلتر',
        [['ستون', col or 'همه']],
        office_commands=[{'action': 'add_autofilter', 'column': col, 'values': values}]
    )


# ── 6. Protect Sheet ──────────────────────────────────────────────────────

def protect_sheet(params, headers, rows):
    password  = params.get('password', '')
    allow_sel = params.get('allow_select', 'true') == 'true'
    allow_fmt = params.get('allow_format', 'false') == 'true'

    return _result(
        ['setting', 'value'],
        [['password_set', 'بله' if password else 'خیر'],
         ['allow_select', allow_sel],
         ['allow_format', allow_fmt]],
        'محافظت از شیت',
        [['پسورد', 'تنظیم شد' if password else 'بدون پسورد']],
        office_commands=[{'action': 'protect_sheet',
                         'password': password,
                         'allow_select': allow_sel,
                         'allow_format': allow_fmt}]
    )


# ── 7. Named Range ────────────────────────────────────────────────────────

def named_range(params, headers, rows):
    name      = params.get('range_name', 'MyRange')
    start_row = int(params.get('start_row', 1))
    end_row   = int(params.get('end_row', len(rows) + 1))
    start_col = int(params.get('start_col', 0))
    end_col   = int(params.get('end_col', len(headers) - 1))

    col_letter = lambda n: chr(ord('A') + n) if n < 26 else chr(ord('A') + n//26 - 1) + chr(ord('A') + n%26)
    address    = f'${col_letter(start_col)}${start_row}:${col_letter(end_col)}${end_row}'

    return _result(
        ['name', 'address'],
        [[name, address]],
        'محدوده نام‌گذاری شده',
        [['نام', name], ['آدرس', address]],
        office_commands=[{'action': 'add_named_range', 'name': name, 'address': address}]
    )


# ── 8. Data Validation ────────────────────────────────────────────────────

def data_validation(params, headers, rows):
    col      = params.get('column', headers[0])
    rule     = params.get('rule', 'list')        # list|range|date|custom
    values   = params.get('values', '')
    min_val  = params.get('min_val', '')
    max_val  = params.get('max_val', '')
    message  = params.get('error_message', 'مقدار نامعتبر')
    ci       = headers.index(col) if col in headers else 0

    validation_spec = {
        'col_index':   ci,
        'col_name':    col,
        'rule':        rule,
        'values':      values.split(',') if values else [],
        'min':         min_val,
        'max':         max_val,
        'error_msg':   message,
        'rows':        len(rows) + 1,
    }

    return _result(
        ['column', 'rule', 'values', 'message'],
        [[col, rule, values[:50], message]],
        f'اعتبارسنجی ورودی — {col}',
        [['قانون', rule], ['ستون', col]],
        office_commands=[{'action': 'data_validation', 'spec': validation_spec}]
    )


# ── 9. Add Hyperlinks ─────────────────────────────────────────────────────

def add_hyperlinks(params, headers, rows):
    col      = params.get('column', headers[0])
    url_col  = params.get('url_column', col)
    label_col= params.get('label_column', col)
    ci_url   = headers.index(url_col)   if url_col   in headers else 0
    ci_label = headers.index(label_col) if label_col in headers else 0

    links = []
    valid = 0
    for i, row in enumerate(rows):
        url   = str(row[ci_url]   if ci_url   < len(row) else '')
        label = str(row[ci_label] if ci_label < len(row) else '')
        if url.startswith('http'):
            links.append({'row': i+1, 'col': ci_url, 'url': url, 'label': label})
            valid += 1

    return _result(
        ['row', 'url', 'label'],
        [[l['row'], l['url'][:50], l['label'][:30]] for l in links[:50]],
        f'افزودن هایپرلینک — {col}',
        [['لینک معتبر', valid], ['نامعتبر', len(rows) - valid]],
        office_commands=[{'action': 'add_hyperlinks', 'links': links}]
    )


# ── 10. Summarize Sheet ───────────────────────────────────────────────────

def summarize_sheet(params, headers, rows):
    n = len(rows)

    # Basic stats per column
    summary_rows = []
    for i, h in enumerate(headers):
        vals = [r[i] if i < len(r) else None for r in rows]
        nn   = [v for v in vals if not _is_empty(v)]
        nums = [_to_number(v) for v in nn if _to_number(v) is not None]

        if nums:
            summary_rows.append([
                h, 'numeric', len(nn), len(vals)-len(nn),
                round(sum(nums)/len(nums), 2),
                round(min(nums), 2), round(max(nums), 2)
            ])
        else:
            from collections import Counter
            top = Counter(str(v) for v in nn).most_common(1)
            summary_rows.append([
                h, 'text', len(nn), len(vals)-len(nn),
                top[0][0][:20] if top else '',
                len(set(str(v) for v in nn)), ''
            ])

    out_headers = ['column', 'type', 'count', 'missing', 'mean/top', 'min/unique', 'max']

    return _result(
        out_headers,
        summary_rows,
        'خلاصه شیت',
        [['ردیف', n], ['ستون', len(headers)],
         ['عددی', sum(1 for r in summary_rows if r[1]=='numeric')],
         ['متنی', sum(1 for r in summary_rows if r[1]=='text')]]
    )


# ── 11. Batch Formulas ────────────────────────────────────────────────────

def batch_formulas(params, headers, rows):
    formulas     = params.get('formulas', [])
    # formulas: [{col_name, excel_formula}, ...]
    if isinstance(formulas, str):
        try: formulas = json.loads(formulas)
        except: formulas = []

    results = []
    for f in formulas:
        col_name = f.get('col_name', 'new_col')
        formula  = f.get('excel_formula', '=A1')
        results.append([col_name, formula])

    return _result(
        ['column_name', 'formula'],
        results,
        'فرمول‌های دسته‌جمعی',
        [['فرمول', len(results)]],
        office_commands=[{'action': 'batch_formulas',
                         'formulas': formulas,
                         'total_rows': len(rows)}]
    )


# ── 12. Clean Formatting ──────────────────────────────────────────────────

def clean_formatting(params, headers, rows):
    scope = params.get('scope', 'all')
    # all | colors | fonts | borders | number_format

    return _result(
        ['action', 'scope'],
        [['clean_format', scope]],
        'پاکسازی قالب‌بندی',
        [['محدوده', scope]],
        note='تمام قالب‌بندی‌های اضافی حذف شدند',
        office_commands=[{'action': 'clear_formatting', 'scope': scope,
                         'rows': len(rows), 'cols': len(headers)}]
    )


# ── 13. Workbook Table of Contents ────────────────────────────────────────

def workbook_toc(params, headers, rows):
    sheet_names = params.get('sheet_names', [])
    toc_title   = params.get('title', 'فهرست مطالب')

    if not sheet_names:
        return _result(
            ['info'],
            [['نام شیت‌ها از Office.js باید ارسال شود']],
            'فهرست مطالب Workbook',
            [['توضیح', 'sheet_names از JS ارسال می‌شود']],
            office_commands=[{'action': 'create_toc', 'title': toc_title}]
        )

    toc_rows = [[i+1, name, f'=HYPERLINK("#\'{name}\'!A1","رفتن")']
                for i, name in enumerate(sheet_names)]

    return _result(
        ['#', 'sheet_name', 'link'],
        toc_rows,
        'فهرست مطالب Workbook',
        [['شیت‌ها', len(sheet_names)]],
        office_commands=[{'action': 'create_toc', 'title': toc_title,
                         'sheets': sheet_names}]
    )


# ── 14. Schedule Refresh ──────────────────────────────────────────────────

def schedule_refresh(params, headers, rows):
    interval_min = int(params.get('interval_minutes', 60))
    tool_id      = params.get('tool_to_run', '')
    enabled      = params.get('enabled', 'true') == 'true'
    next_run     = (datetime.now() + timedelta(minutes=interval_min)).strftime('%Y-%m-%d %H:%M')

    schedule_spec = {
        'enabled':      enabled,
        'interval_ms':  interval_min * 60 * 1000,
        'tool_id':      tool_id,
        'next_run':     next_run,
    }

    return _result(
        ['setting', 'value'],
        [['وضعیت', 'فعال' if enabled else 'غیرفعال'],
         ['بازه', f'{interval_min} دقیقه'],
         ['ابزار', tool_id],
         ['اجرای بعدی', next_run]],
        'زمان‌بندی تازه‌سازی',
        [['بازه', f'{interval_min} دقیقه'], ['فعال', enabled]],
        office_commands=[{'action': 'schedule_refresh', 'spec': schedule_spec}]
    )
