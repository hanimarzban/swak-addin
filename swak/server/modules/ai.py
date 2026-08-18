# cython: language_level=3
"""
SWAK — AI Insights Module (18 tools)
14 tools use Claude API — key placeholder ready
4 tools use pure Python (no API needed)

CLAUDE_API_KEY: set in .env file when ready
"""

import json
import math
import re
import urllib.request
from collections import Counter

# ── API Config (placeholder) ──────────────────────────────────────────────
import os
CLAUDE_API_KEY = os.environ.get('SWAK_CLAUDE_API_KEY', '')   # ← جای‌گذاری کلید اینجا
CLAUDE_MODEL   = 'claude-sonnet-4-6'
CLAUDE_URL     = 'https://api.anthropic.com/v1/messages'
API_AVAILABLE  = bool(CLAUDE_API_KEY)


def run(tool_id: str, params: dict, headers: list, rows: list) -> dict:
    fn_map = {
        # Claude API tools
        'explain-data':       explain_data,
        'formula-gen':        formula_gen,
        'sql-gen':            sql_gen,
        'insight-summary':    insight_summary,
        'anomaly-explain':    anomaly_explain,
        'data-story':         data_story,
        'column-suggest':     column_suggest,
        'cleaning-suggest':   cleaning_suggest,
        'chart-suggest':      chart_suggest,
        'question-answer':    question_answer,
        'trend-explain':      trend_explain,
        'segment-describe':   segment_describe,
        'report-generate':    report_generate,
        'translate-data':     translate_data,
        # Pure Python tools (no API)
        'auto-tag':           auto_tag,
        'keyword-extract':    keyword_extract,
        'pattern-detect':     pattern_detect,
        'smart-rename':       smart_rename,
    }
    fn = fn_map.get(tool_id)
    if not fn:
        raise ValueError(f'ابزار ناشناخته: {tool_id}')
    return fn(params, headers, list(rows))


# ── Claude API caller ─────────────────────────────────────────────────────

def _call_claude(system_prompt: str, user_message: str, max_tokens: int = 1000) -> str:
    """
    Call Claude API.
    Returns response text or raises RuntimeError if API key not set.
    """
    if not API_AVAILABLE:
        raise RuntimeError(
            'Claude API key not configured.\n'
            'Set SWAK_CLAUDE_API_KEY in your .env file.\n'
            'Get your key from: https://console.anthropic.com'
        )

    payload = json.dumps({
        'model':      CLAUDE_MODEL,
        'max_tokens': max_tokens,
        'system':     system_prompt,
        'messages':   [{'role': 'user', 'content': user_message}],
    }).encode('utf-8')

    req = urllib.request.Request(
        CLAUDE_URL,
        data=payload,
        headers={
            'Content-Type':      'application/json',
            'x-api-key':         CLAUDE_API_KEY,
            'anthropic-version': '2023-06-01',
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            data = json.loads(res.read())
            return data['content'][0]['text']
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'Claude API error {e.code}: {body[:200]}')
    except Exception as e:
        raise RuntimeError(f'Claude API call failed: {e}')


def _data_summary(headers, rows, max_rows=20):
    """Build a compact text summary of the dataset for API prompts"""
    n      = len(rows)
    sample = rows[:max_rows]
    lines  = [f'Dataset: {n} rows × {len(headers)} columns']
    lines.append(f'Columns: {", ".join(headers)}')
    lines.append(f'Sample ({min(max_rows, n)} rows):')
    lines.append('\t'.join(headers))
    for r in sample:
        lines.append('\t'.join(str(v) if v is not None else '' for v in r))
    return '\n'.join(lines)


def _no_api_fallback(tool_name):
    """Standard fallback when API key not configured"""
    return {
        'headers': ['status', 'message'],
        'rows': [
            ['⚠️ API Key لازم است', f'ابزار {tool_name} به Claude API نیاز دارد'],
            ['راهنما', 'در فایل .env مقدار SWAK_CLAUDE_API_KEY را تنظیم کنید'],
            ['لینک', 'https://console.anthropic.com'],
        ],
        'summary': {
            'title': f'{tool_name} — API Key لازم است',
            'stats': [['وضعیت', 'API key تنظیم نشده']],
            'note': 'پس از تنظیم کلید، سرور را ریستارت کنید',
        }
    }


# ══════════════════════════════════════════════════════════════════════════
# CLAUDE API TOOLS (14 tools)
# ══════════════════════════════════════════════════════════════════════════

def explain_data(params, headers, rows):
    """Explain what the dataset contains in plain language"""
    if not API_AVAILABLE:
        return _no_api_fallback('Explain Data')

    lang    = params.get('language', 'fa')
    detail  = params.get('detail_level', 'summary')
    summary = _data_summary(headers, rows)

    system = (
        'You are a data analyst. Explain datasets clearly and concisely. '
        f'Respond in {"Persian/Farsi" if lang == "fa" else "English"}.'
    )
    prompt = (
        f'Explain this dataset in {detail} level:\n\n{summary}\n\n'
        'Cover: what the data represents, key columns, data quality observations, '
        'and 2-3 interesting patterns you notice.'
    )

    explanation = _call_claude(system, prompt, max_tokens=800)

    return {
        'headers': ['explanation'],
        'rows': [[explanation]],
        'summary': {
            'title': 'توضیح داده‌ها',
            'stats': [['ردیف', len(rows)], ['ستون', len(headers)]],
            'note': explanation[:200],
        }
    }


def formula_gen(params, headers, rows):
    """Generate Excel/Python formula for a given task"""
    if not API_AVAILABLE:
        return _no_api_fallback('Formula Generator')

    task      = params.get('task', '')
    formula_type = params.get('formula_type', 'excel')

    system = 'You are an Excel and Python formula expert. Generate precise, working formulas.'
    prompt = (
        f'Generate a {formula_type} formula/code for this task:\n"{task}"\n\n'
        f'Available columns: {", ".join(headers)}\n'
        f'Data sample (first 3 rows):\n'
        + '\n'.join('\t'.join(str(v) for v in r) for r in rows[:3]) +
        '\n\nProvide:\n1. The formula/code\n2. Brief explanation\n3. Example output'
    )

    result = _call_claude(system, prompt, max_tokens=600)

    return {
        'headers': ['formula_result'],
        'rows': [[result]],
        'summary': {
            'title': f'فرمول {formula_type}',
            'stats': [['وظیفه', task[:50]]],
            'note': result[:150],
        }
    }


def sql_gen(params, headers, rows):
    """Generate SQL query from natural language"""
    if not API_AVAILABLE:
        return _no_api_fallback('SQL Generator')

    question  = params.get('question', '')
    db_type   = params.get('db_type', 'postgresql')
    table_name= params.get('table_name', 'data')

    system = f'You are a {db_type} SQL expert. Write clean, optimized SQL queries.'
    prompt = (
        f'Write a {db_type} SQL query to answer:\n"{question}"\n\n'
        f'Table: {table_name}\n'
        f'Columns: {", ".join(headers)}\n'
        f'Sample data:\n'
        + '\t'.join(headers) + '\n'
        + '\n'.join('\t'.join(str(v) for v in r) for r in rows[:3]) +
        '\n\nProvide:\n1. The SQL query\n2. Brief explanation'
    )

    result = _call_claude(system, prompt, max_tokens=500)

    return {
        'headers': ['sql_query'],
        'rows': [[result]],
        'summary': {
            'title': f'SQL Query ({db_type})',
            'stats': [['سوال', question[:50]]],
            'note': result[:150],
        }
    }


def insight_summary(params, headers, rows):
    """Generate key insights from data"""
    if not API_AVAILABLE:
        return _no_api_fallback('Insight Summary')

    n_insights = int(params.get('n_insights', 5))
    focus_col  = params.get('focus_column', '')
    summary    = _data_summary(headers, rows)
    lang       = params.get('language', 'fa')

    system = (
        'You are a senior data analyst. Extract actionable insights from data. '
        f'Respond in {"Persian/Farsi" if lang == "fa" else "English"}.'
    )
    prompt = (
        f'Extract the top {n_insights} data insights from:\n\n{summary}\n\n'
        + (f'Focus especially on column: {focus_col}\n' if focus_col else '') +
        'Format each insight as:\n'
        '1. [Category] Brief title: Detailed explanation with specific numbers'
    )

    result = _call_claude(system, prompt, max_tokens=800)
    insights = [line.strip() for line in result.split('\n') if line.strip() and line[0].isdigit()]

    out_rows = [[i+1, ins] for i, ins in enumerate(insights)] if insights else [[1, result]]

    return {
        'headers': ['#', 'insight'],
        'rows': out_rows,
        'summary': {
            'title': 'خلاصه بینش‌ها',
            'stats': [['بینش یافت شده', len(out_rows)]],
        }
    }


def anomaly_explain(params, headers, rows):
    """Explain detected anomalies in natural language"""
    if not API_AVAILABLE:
        return _no_api_fallback('Anomaly Explainer')

    anomaly_col = params.get('anomaly_column', '')
    lang        = params.get('language', 'fa')

    # Find anomalous rows
    if anomaly_col and anomaly_col in headers:
        ci = headers.index(anomaly_col)
        anomaly_rows = [r for r in rows if str(r[ci] if ci < len(r) else '') in ('1', 'True', 'true')]
    else:
        anomaly_rows = rows[:5]

    summary = _data_summary(headers, anomaly_rows, max_rows=10)
    system  = (
        'You are a data scientist specializing in anomaly detection. '
        f'Explain anomalies clearly. Respond in {"Persian/Farsi" if lang == "fa" else "English"}.'
    )
    prompt  = (
        f'These are anomalous data points detected in a dataset:\n\n{summary}\n\n'
        'Explain:\n1. What makes these points anomalous\n'
        '2. Possible causes\n3. Recommended actions'
    )

    result = _call_claude(system, prompt, max_tokens=600)

    return {
        'headers': ['anomaly_explanation'],
        'rows': [[result]],
        'summary': {
            'title': 'توضیح آنومالی‌ها',
            'stats': [['آنومالی', len(anomaly_rows)]],
            'note': result[:150],
        }
    }


def data_story(params, headers, rows):
    """Generate a narrative data story"""
    if not API_AVAILABLE:
        return _no_api_fallback('Data Story')

    audience = params.get('audience', 'business')
    tone     = params.get('tone', 'professional')
    lang     = params.get('language', 'fa')
    summary  = _data_summary(headers, rows)

    system = (
        f'You are a data storyteller. Write engaging {tone} narratives for {audience} audiences. '
        f'Respond in {"Persian/Farsi" if lang == "fa" else "English"}.'
    )
    prompt = (
        f'Write a data story about this dataset:\n\n{summary}\n\n'
        'Structure: Hook → Key Finding → Supporting Evidence → Implication → Call to Action\n'
        'Keep it concise (200-300 words).'
    )

    result = _call_claude(system, prompt, max_tokens=600)

    return {
        'headers': ['data_story'],
        'rows': [[result]],
        'summary': {
            'title': 'داستان داده',
            'stats': [['مخاطب', audience], ['لحن', tone]],
        }
    }


def column_suggest(params, headers, rows):
    """Suggest new useful columns to add"""
    if not API_AVAILABLE:
        return _no_api_fallback('Column Suggestions')

    summary = _data_summary(headers, rows)
    lang    = params.get('language', 'fa')

    system = (
        'You are a data engineering expert. Suggest useful derived columns. '
        f'Respond in {"Persian/Farsi" if lang == "fa" else "English"}.'
    )
    prompt = (
        f'Based on this dataset:\n\n{summary}\n\n'
        'Suggest 5 useful new columns to add. For each:\n'
        '- Column name\n- Formula or logic\n- Why it would be useful'
    )

    result   = _call_claude(system, prompt, max_tokens=600)
    lines    = [l.strip() for l in result.split('\n') if l.strip()]

    return {
        'headers': ['suggestion'],
        'rows': [[l] for l in lines],
        'summary': {
            'title': 'پیشنهاد ستون جدید',
            'stats': [['پیشنهادها', len(lines)]],
        }
    }


def cleaning_suggest(params, headers, rows):
    """Suggest data cleaning steps"""
    if not API_AVAILABLE:
        return _no_api_fallback('Cleaning Suggestions')

    summary = _data_summary(headers, rows)
    lang    = params.get('language', 'fa')

    # Also compute basic stats
    missing_info = []
    for i, h in enumerate(headers):
        missing = sum(1 for r in rows if (r[i] if i < len(r) else None) in (None, '', 'NULL', 'null'))
        if missing > 0:
            missing_info.append(f'{h}: {missing} missing ({missing/len(rows)*100:.1f}%)')

    system = (
        'You are a data quality expert. Provide specific, actionable cleaning recommendations. '
        f'Respond in {"Persian/Farsi" if lang == "fa" else "English"}.'
    )
    prompt = (
        f'Analyze this dataset and suggest cleaning steps:\n\n{summary}\n\n'
        + (f'Missing values:\n' + '\n'.join(missing_info) if missing_info else '') +
        '\n\nProvide specific cleaning steps in priority order with expected impact.'
    )

    result = _call_claude(system, prompt, max_tokens=600)
    steps  = [l.strip() for l in result.split('\n') if l.strip()]

    return {
        'headers': ['cleaning_step'],
        'rows': [[s] for s in steps],
        'summary': {
            'title': 'پیشنهادات پاکسازی داده',
            'stats': [['مراحل پیشنهادی', len(steps)]],
        }
    }


def chart_suggest(params, headers, rows):
    """Suggest best chart types for the data"""
    if not API_AVAILABLE:
        return _no_api_fallback('Chart Suggestions')

    summary = _data_summary(headers, rows)
    lang    = params.get('language', 'fa')

    system = (
        'You are a data visualization expert. Recommend the most effective chart types. '
        f'Respond in {"Persian/Farsi" if lang == "fa" else "English"}.'
    )
    prompt = (
        f'Recommend 3-5 chart types for this dataset:\n\n{summary}\n\n'
        'For each chart:\n'
        '- Chart type\n- X-axis and Y-axis columns\n- Why it works well\n- Key insight it would reveal'
    )

    result = _call_claude(system, prompt, max_tokens=600)
    lines  = [l.strip() for l in result.split('\n') if l.strip()]

    return {
        'headers': ['chart_suggestion'],
        'rows': [[l] for l in lines],
        'summary': {'title': 'پیشنهاد نمودار', 'stats': []},
    }


def question_answer(params, headers, rows):
    """Answer a natural language question about the data"""
    if not API_AVAILABLE:
        return _no_api_fallback('Q&A')

    question = params.get('question', '')
    if not question:
        raise ValueError('سوال الزامی است')

    summary = _data_summary(headers, rows)
    lang    = params.get('language', 'fa')

    system = (
        'You are a data analyst. Answer questions about datasets accurately using the data provided. '
        f'Respond in {"Persian/Farsi" if lang == "fa" else "English"}. '
        'If you cannot answer from the data alone, say so clearly.'
    )
    prompt = f'Dataset:\n{summary}\n\nQuestion: {question}\n\nProvide a specific, data-backed answer.'

    answer = _call_claude(system, prompt, max_tokens=500)

    return {
        'headers': ['question', 'answer'],
        'rows': [[question, answer]],
        'summary': {
            'title': 'پاسخ به سوال',
            'stats': [['سوال', question[:50]]],
            'note': answer[:150],
        }
    }


def trend_explain(params, headers, rows):
    """Explain trends in a time series column"""
    if not API_AVAILABLE:
        return _no_api_fallback('Trend Explanation')

    value_col = params.get('value_column', headers[-1])
    date_col  = params.get('date_column', headers[0])
    lang      = params.get('language', 'fa')

    summary   = _data_summary(headers, rows)
    system    = (
        'You are a time series analyst. Explain trends clearly with specific observations. '
        f'Respond in {"Persian/Farsi" if lang == "fa" else "English"}.'
    )
    prompt = (
        f'Analyze the trend in column "{value_col}" over time (column "{date_col}"):\n\n'
        f'{summary}\n\n'
        'Describe: overall trend, seasonal patterns, notable spikes/dips, forecast direction'
    )

    result = _call_claude(system, prompt, max_tokens=500)

    return {
        'headers': ['trend_analysis'],
        'rows': [[result]],
        'summary': {'title': f'تحلیل روند — {value_col}', 'stats': [], 'note': result[:150]},
    }


def segment_describe(params, headers, rows):
    """Describe characteristics of each segment/cluster"""
    if not API_AVAILABLE:
        return _no_api_fallback('Segment Description')

    segment_col = params.get('segment_column', headers[-1])
    lang        = params.get('language', 'fa')
    summary     = _data_summary(headers, rows)

    system = (
        'You are a market analyst. Describe customer/data segments with actionable insights. '
        f'Respond in {"Persian/Farsi" if lang == "fa" else "English"}.'
    )
    prompt = (
        f'Describe each segment in column "{segment_col}" based on this data:\n\n{summary}\n\n'
        'For each segment: key characteristics, distinguishing features, recommended strategy'
    )

    result = _call_claude(system, prompt, max_tokens=700)

    return {
        'headers': ['segment_description'],
        'rows': [[result]],
        'summary': {'title': f'توصیف بخش‌ها — {segment_col}', 'stats': []},
    }


def report_generate(params, headers, rows):
    """Generate a complete data analysis report"""
    if not API_AVAILABLE:
        return _no_api_fallback('Report Generator')

    title   = params.get('title', 'Data Analysis Report')
    lang    = params.get('language', 'fa')
    summary = _data_summary(headers, rows)

    system = (
        'You are a senior data analyst. Generate comprehensive, professional reports. '
        f'Respond in {"Persian/Farsi" if lang == "fa" else "English"}.'
    )
    prompt = (
        f'Generate a professional data analysis report titled "{title}":\n\n{summary}\n\n'
        'Structure:\n'
        '## Executive Summary\n## Dataset Overview\n## Key Findings\n'
        '## Recommendations\n## Next Steps\n\n'
        'Be specific, use numbers, and keep it under 400 words.'
    )

    result = _call_claude(system, prompt, max_tokens=1000)

    return {
        'headers': ['report'],
        'rows': [[result]],
        'summary': {'title': title, 'stats': [['ردیف', len(rows)], ['ستون', len(headers)]]},
    }


def translate_data(params, headers, rows):
    """Translate text values in a column"""
    if not API_AVAILABLE:
        return _no_api_fallback('Data Translator')

    ci      = headers.index(params['column']) if params.get('column') in headers else 0
    from_lang = params.get('from_language', 'auto')
    to_lang   = params.get('to_language', 'fa')
    batch_size= int(params.get('batch_size', 20))

    # Collect unique values to translate (batched)
    unique_vals = list(set(
        str(r[ci] if ci < len(r) else '')
        for r in rows
        if not (r[ci] if ci < len(r) else '') == ''
    ))
    translations = {}

    system = f'You are a professional translator. Translate accurately. Output ONLY JSON.'
    for i in range(0, len(unique_vals), batch_size):
        batch = unique_vals[i:i+batch_size]
        prompt = (
            f'Translate from {from_lang} to {to_lang}. Return ONLY a JSON object:\n'
            + json.dumps({v: '' for v in batch}) +
            '\nFill in the values with translations.'
        )
        try:
            result = _call_claude(system, prompt, max_tokens=500)
            parsed = json.loads(result)
            translations.update(parsed)
        except Exception:
            for v in batch:
                translations[v] = v  # fallback: keep original

    col_name    = f'{params.get("column","")}_translated'
    new_headers = headers + [col_name]
    new_rows    = [list(r) + [translations.get(str(r[ci] if ci < len(r) else ''), '')] for r in rows]

    return {
        'headers': new_headers,
        'rows': new_rows,
        'summary': {
            'title': f'ترجمه — {params.get("column","")}',
            'stats': [['زبان مقصد', to_lang], ['مقادیر ترجمه شده', len(translations)]],
        }
    }


# ══════════════════════════════════════════════════════════════════════════
# PURE PYTHON TOOLS (no API needed)
# ══════════════════════════════════════════════════════════════════════════

def auto_tag(params, headers, rows):
    """Auto-tag rows based on keyword rules"""
    ci        = headers.index(params['column']) if params.get('column') in headers else 0
    rules_str = params.get('rules', '')
    # rules format: "tag1:keyword1,keyword2;tag2:keyword3"
    rules = {}
    for rule in rules_str.split(';'):
        if ':' in rule:
            tag, kws = rule.split(':', 1)
            rules[tag.strip()] = [k.strip().lower() for k in kws.split(',')]

    if not rules:
        # Auto-generate rules from most common words
        all_text = ' '.join(str(r[ci] if ci < len(r) else '') for r in rows).lower()
        words    = re.findall(r'\b\w{4,}\b', all_text)
        top_words= [w for w, _ in Counter(words).most_common(10)]
        rules    = {w: [w] for w in top_words[:5]}

    col_name    = f'{headers[ci]}_tags'
    new_headers = headers + [col_name]
    new_rows    = []

    for row in rows:
        text = str(row[ci] if ci < len(row) else '').lower()
        tags = [tag for tag, kws in rules.items() if any(kw in text for kw in kws)]
        new_rows.append(list(row) + [', '.join(tags) if tags else 'other'])

    tagged = sum(1 for r in new_rows if r[-1] != 'other')
    return {
        'headers': new_headers,
        'rows': new_rows,
        'summary': {
            'title': f'برچسب‌گذاری خودکار — {headers[ci]}',
            'stats': [['برچسب‌زده', tagged], ['بدون برچسب', len(rows)-tagged],
                      ['قوانین', len(rules)]],
        }
    }


def keyword_extract(params, headers, rows):
    """Extract keywords from text column using TF-IDF heuristic"""
    ci    = headers.index(params['column']) if params.get('column') in headers else 0
    top_n = int(params.get('top_n_per_row', 3))
    stops = {'the','a','an','and','or','but','in','on','at','to','for','of','with',
             'is','are','was','were','be','been','this','that','it','he','she','they',
             'در','و','به','از','با','که','این','آن','را','هم','تا','یا'}

    # IDF
    docs  = [re.findall(r'\b\w{3,}\b', str(r[ci] if ci < len(r) else '').lower()) for r in rows]
    vocab = set(w for d in docs for w in d if w not in stops)
    N     = len(docs)
    idf   = {w: math.log(N / (sum(1 for d in docs if w in d) + 1)) for w in vocab}

    col_name    = f'{headers[ci]}_keywords'
    new_headers = headers + [col_name]
    new_rows    = []

    for doc in docs:
        tf   = Counter(doc)
        kws  = sorted((w for w in tf if w not in stops),
                      key=lambda w: tf[w] * idf.get(w, 0), reverse=True)[:top_n]
        new_rows.append(None)  # placeholder

    for i, (row, doc) in enumerate(zip(rows, docs)):
        tf   = Counter(doc)
        kws  = sorted((w for w in tf if w not in stops),
                      key=lambda w: tf[w] * idf.get(w, 0), reverse=True)[:top_n]
        new_rows[i] = list(row) + [', '.join(kws)]

    return {
        'headers': new_headers,
        'rows': new_rows,
        'summary': {
            'title': f'استخراج کلمات کلیدی — {headers[ci]}',
            'stats': [['top_n', top_n], ['واژگان', len(vocab)]],
        }
    }


def pattern_detect(params, headers, rows):
    """Detect common patterns in a column (email, phone, date, number, etc.)"""
    ci = headers.index(params['column']) if params.get('column') in headers else 0

    PATTERNS = {
        'email':   re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]{2,}$'),
        'phone':   re.compile(r'^[\+\d\s\-\(\)]{7,20}$'),
        'date':    re.compile(r'\d{4}[-/]\d{2}[-/]\d{2}'),
        'url':     re.compile(r'https?://\S+'),
        'integer': re.compile(r'^-?\d+$'),
        'float':   re.compile(r'^-?\d+\.\d+$'),
        'persian': re.compile(r'[\u0600-\u06FF]'),
        'arabic':  re.compile(r'[\u0600-\u06FF]'),
        'latin':   re.compile(r'^[A-Za-z\s]+$'),
    }

    col_name    = f'{headers[ci]}_pattern'
    new_headers = headers + [col_name]
    new_rows    = []
    pattern_cnt = Counter()

    for row in rows:
        v       = str(row[ci] if ci < len(row) else '').strip()
        matched = next((name for name, pat in PATTERNS.items() if pat.search(v)), 'other')
        pattern_cnt[matched] += 1
        new_rows.append(list(row) + [matched])

    return {
        'headers': new_headers,
        'rows': new_rows,
        'summary': {
            'title': f'تشخیص الگو — {headers[ci]}',
            'stats': [[pat, cnt] for pat, cnt in pattern_cnt.most_common()],
        }
    }


def smart_rename(params, headers, rows):
    """Suggest better column names based on content analysis"""
    suggestions = []
    for i, h in enumerate(headers):
        vals    = [str(r[i] if i < len(r) else '') for r in rows[:20] if not (r[i] if i < len(r) else '') == '']
        nums    = sum(1 for v in vals if re.match(r'^-?\d+\.?\d*$', v))
        emails  = sum(1 for v in vals if '@' in v)
        dates   = sum(1 for v in vals if re.search(r'\d{4}[-/]\d{2}', v))
        urls    = sum(1 for v in vals if v.startswith('http'))

        hint = h  # default
        if emails > len(vals)//2:  hint = h if 'email' in h.lower() else h + '_email'
        elif dates > len(vals)//2: hint = h if 'date' in h.lower() else h + '_date'
        elif urls > len(vals)//2:  hint = h if 'url' in h.lower() else h + '_url'
        elif nums > len(vals)*0.8: hint = h if any(x in h.lower() for x in ['id','count','num','amount','price']) else h

        # snake_case
        clean = re.sub(r'[^a-zA-Z0-9_\u0600-\u06FF]', '_', h).strip('_').lower()
        suggestions.append([h, clean, hint, 'بله' if clean != h.lower() else 'خیر'])

    out_headers = ['original', 'snake_case', 'suggested', 'needs_rename']
    return {
        'headers': out_headers,
        'rows': suggestions,
        'summary': {
            'title': 'پیشنهاد تغییر نام ستون',
            'stats': [['نیاز به تغییر', sum(1 for r in suggestions if r[3] == 'بله')],
                      ['بدون تغییر', sum(1 for r in suggestions if r[3] == 'خیر')]],
        }
    }
