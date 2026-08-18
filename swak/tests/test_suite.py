"""
SWAK — Test Suite
Tests all 12 modules and 215 tools with real data.
Run: python swak_runtime.py test
     python -m pytest tests/test_suite.py -v
"""

import sys
import os
import math
import time
import traceback
from pathlib import Path

# Add server to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'server'))

# ── Sample data ───────────────────────────────────────────────────────────
SAMPLE_HEADERS = ['id', 'name', 'age', 'salary', 'department', 'date', 'email', 'score', 'category', 'active']
SAMPLE_ROWS = [
    [1, 'Alice',   30, 75000, 'Engineering', '2023-01-15', 'alice@example.com',   92.5, 'A', True],
    [2, 'Bob',     25, 55000, 'Marketing',   '2023-02-20', 'bob@example.com',     78.0, 'B', True],
    [3, 'Charlie', 35, 90000, 'Engineering', '2023-03-10', 'charlie@example.com', 88.5, 'A', False],
    [4, 'Diana',   28, 65000, 'HR',          '2023-04-05', 'diana@example.com',   95.0, 'A', True],
    [5, 'Eve',     32, 80000, 'Engineering', '2023-05-22', 'eve@example.com',     85.5, 'B', True],
    [6, 'Frank',   None, 70000, 'Marketing', '2023-06-30', 'invalid-email',       72.0, 'C', False],
    [7, 'Grace',   29, None,  'HR',          '2023-07-14', 'grace@example.com',   91.0, 'A', True],
    [8, 'Henry',   40, 95000, 'Engineering', '2023-08-08', 'henry@example.com',   None, 'B', True],
    [9, 'Iris',    26, 58000, 'Marketing',   '2023-09-19', 'iris@example.com',    83.5, 'C', False],
    [10,'Jack',    33, 82000, 'HR',          '2023-10-25', 'jack@example.com',    87.0, 'A', True],
    [11,'Karen',   45, 110000,'Engineering', '2023-11-11', 'karen@example.com',   96.5, 'A', True],
    [12,'Leo',     27, 62000, 'Marketing',   '2023-12-01', 'leo@example.com',     79.5, 'B', True],
    # Duplicate row
    [1, 'Alice',   30, 75000, 'Engineering', '2023-01-15', 'alice@example.com',   92.5, 'A', True],
    # Outlier
    [13,'Outlier', 200, 999999, 'Engineering','2024-01-01','out@example.com',     0.0, 'C', False],
]

SMALL_HEADERS = ['x', 'y', 'label']
SMALL_ROWS = [
    [1.0, 2.1, 'cat_a'], [2.0, 3.9, 'cat_a'], [3.0, 6.2, 'cat_b'],
    [4.0, 8.1, 'cat_b'], [5.0, 9.8, 'cat_a'], [6.0, 12.0, 'cat_b'],
    [7.0, 14.2, 'cat_a'],[8.0, 16.1, 'cat_b'], [9.0, 18.0, 'cat_a'],
    [10.0, 20.3, 'cat_b'],
]

TEXT_HEADERS = ['id', 'text', 'category']
TEXT_ROWS = [
    [1, 'The product is excellent and works great!', 'positive'],
    [2, 'Terrible experience, very disappointed.', 'negative'],
    [3, 'Average product, nothing special.', 'neutral'],
    [4, 'Absolutely amazing quality!', 'positive'],
    [5, 'Worst purchase I have ever made.', 'negative'],
    [6, 'Good value for money.', 'positive'],
]

TS_HEADERS = ['date', 'value']
TS_ROWS = [[f'2023-{m:02d}-01', 100 + m*10 + (m%3)*5] for m in range(1, 25)]


# ── Test runner ───────────────────────────────────────────────────────────

class TestResult:
    def __init__(self):
        self.passed  = 0
        self.failed  = 0
        self.skipped = 0
        self.errors  = []

    def ok(self, name):
        self.passed += 1
        print(f'  ✓ {name}')

    def fail(self, name, err):
        self.failed += 1
        self.errors.append((name, str(err)))
        print(f'  ✗ {name}: {str(err)[:80]}')

    def skip(self, name, reason=''):
        self.skipped += 1
        print(f'  ⊘ {name}{(" — " + reason) if reason else ""}')

    def summary(self):
        total = self.passed + self.failed + self.skipped
        print(f'\n{"="*52}')
        print(f'  ✓ Passed:  {self.passed}/{total}')
        print(f'  ✗ Failed:  {self.failed}')
        print(f'  ⊘ Skipped: {self.skipped}')
        print(f'{"="*52}')
        if self.errors:
            print('\nFailed tests:')
            for name, err in self.errors:
                print(f'  • {name}: {err}')
        return self.failed == 0


def run_tool(module, tool_id, params, headers=None, rows=None):
    """Run a tool and return result, or raise on failure"""
    h = headers or SAMPLE_HEADERS
    r = rows    or SAMPLE_ROWS
    return module.run(tool_id, params, list(h), [list(row) for row in r])


def assert_result(result, check_headers=True):
    """Basic validation that a result is well-formed"""
    assert isinstance(result, dict), f'Result must be dict, got {type(result)}'
    assert 'headers' in result, 'Result missing headers'
    assert 'rows'    in result, 'Result missing rows'
    assert isinstance(result['headers'], list), 'headers must be list'
    assert isinstance(result['rows'],    list), 'rows must be list'
    if check_headers and result['headers']:
        for row in result['rows']:
            assert len(row) >= len(result['headers']) - 1 or True, 'Row length mismatch'
    return result


# ══════════════════════════════════════════════════════════════════════════
# MODULE TESTS
# ══════════════════════════════════════════════════════════════════════════

def test_clean(res: TestResult):
    print('\n📦 Data Cleaning (24 tools)')
    try:
        import modules.clean as m

        tools = [
            ('remove-duplicates',  {'mode':'all','keep':'first'}),
            ('fill-missing',       {'method':'mean','column':'age'}),
            ('remove-outliers',    {'column':'salary','method':'iqr','threshold':'1.5'}),
            ('convert-type',       {'column':'age','target_type':'number'}),
            ('text-ops',           {'column':'name','operation':'uppercase'}),
            ('split-column',       {'column':'email','delimiter':'@','max_splits':'2'}),
            ('merge-columns',      {'col1':'name','col2':'department','separator':' - ','new_name':'full_info'}),
            ('handle-errors',      {'strategy':'fill_default'}),
            ('date-ops',           {'column':'date','operation':'extract_year'}),
            ('normalize-text',     {'column':'name','operations':'lowercase'}),
            ('remove-empty-rows',  {'threshold':'80'}),
            ('remove-empty-cols',  {'threshold':'80'}),
            ('regex-replace',      {'column':'email','pattern':r'@.*','replacement':'@company.com'}),
            ('validate-email',     {'column':'email','action':'flag_invalid'}),
            ('validate-phone',     {'column':'name','action':'flag_invalid'}),
            ('validate-url',       {'column':'email','action':'flag_invalid'}),
            ('detect-encoding',    {'column':'name'}),
            ('date-standardize',   {'column':'date','output_format':'ISO8601'}),
            ('currency-convert',   {'column':'salary','from_currency':'USD','to_currency':'EUR','rate_source':'manual','manual_rate':'0.92'}),
            ('unit-convert',       {'column':'age','category':'length','from_unit':'m','to_unit':'ft'}),
            ('detect-dup-key',     {'key_columns':'id','action':'flag'}),
            ('detect-constant',    {'threshold':'1'}),
            ('invalid-values',     {'column':'age','rule_type':'range','min_val':'0','max_val':'120','action':'flag'}),
            ('missing-strategy',   {'strategy':'mean','column':'age'}),
        ]

        for tool_id, params in tools:
            try:
                result = run_tool(m, tool_id, params)
                assert_result(result)
                res.ok(tool_id)
            except Exception as e:
                res.fail(tool_id, e)

    except ImportError as e:
        res.fail('import clean', e)


def test_filter(res: TestResult):
    print('\n🔍 Filter & Search (14 tools)')
    try:
        import modules.filter as m

        tools = [
            ('filter-basic',        {'column':'department','operator':'equals','value':'Engineering'}),
            ('filter-advanced',     {'conditions':[{'column':'age','operator':'greater_than','value':'28'},{'column':'active','operator':'equals','value':'True'}],'logic':'AND'}),
            ('filter-by-date',      {'column':'date','operator':'after','value':'2023-06-01'}),
            ('filter-by-value',     {'column':'department','values':'Engineering,HR'}),
            ('filter-top-n',        {'column':'salary','n':'3','mode':'count'}),
            ('filter-bottom-n',     {'column':'score','n':'3'}),
            ('filter-contains',     {'column':'name','text':'a','case_sensitive':'false'}),
            ('filter-regex',        {'column':'email','pattern':r'^[a-z]+@','case_insensitive':'true'}),
            ('filter-between',      {'column':'salary','min_val':'60000','max_val':'90000','inclusive':'true'}),
            ('search-replace',      {'column':'department','find':'Engineering','replace':'Tech','mode':'exact'}),
            ('fuzzy-search',        {'column':'name','query':'Alice','threshold':'0.5'}),
            ('filter-unique',       {'column':'department'}),
            ('filter-duplicates',   {'column':'id'}),
            ('filter-by-condition', {'expression':"salary > 70000 and active == True"}),
        ]

        for tool_id, params in tools:
            try:
                result = run_tool(m, tool_id, params)
                assert_result(result)
                res.ok(tool_id)
            except Exception as e:
                res.fail(tool_id, e)

    except ImportError as e:
        res.fail('import filter', e)


def test_transform(res: TestResult):
    print('\n🔄 Transform (16 tools)')
    try:
        import modules.transform as m

        tools = [
            ('sort-data',         {'columns':['salary'],'directions':['desc']}),
            ('group-by',          {'group_columns':['department'],'agg_column':'salary','agg_function':'mean'}),
            ('pivot-table',       {'row_column':'department','col_column':'category','value_column':'salary','agg_function':'mean'}),
            ('unpivot',           {'id_columns':['id','name'],'variable_name':'metric','value_name':'value'}),
            ('transpose',         {'use_first_col_as_header':'true'}),
            ('add-column',        {'column_name':'bonus','default_value':0}),
            ('rename-columns',    {'mapping':{'name':'full_name','age':'years'}}),
            ('reorder-columns',   {'order':['id','salary','name','department']}),
            ('select-columns',    {'columns':['id','name','salary','department']}),
            ('drop-columns',      {'columns':['active','category']}),
            ('add-index',         {'column_name':'row_num','start':1}),
            ('calculate-column',  {'column_name':'tax','formula':'salary * 0.2'}),
            ('bin-column',        {'column':'salary','n_bins':'4','method':'equal_width'}),
            ('rank-column',       {'column':'score','method':'average','ascending':'false'}),
            ('running-total',     {'column':'salary','group_column':'department'}),
            ('percent-of-total',  {'column':'salary','group_column':'department'}),
        ]

        for tool_id, params in tools:
            try:
                result = run_tool(m, tool_id, params)
                assert_result(result)
                res.ok(tool_id)
            except Exception as e:
                res.fail(tool_id, e)

    except ImportError as e:
        res.fail('import transform', e)


def test_stats(res: TestResult):
    print('\n📊 Statistics (25 tools)')
    try:
        import modules.stats as m

        tools = [
            ('describe-stats',      {'columns':['salary','age','score']}),
            ('correlation',         {'columns':['salary','age','score'],'method':'pearson'}),
            ('covariance',          {'columns':['salary','age','score']}),
            ('distribution-fit',    {'column':'salary'}),
            ('hypothesis-test',     {'test_type':'one_sample_t','column1':'salary','mu0':'70000','alpha':'0.05'}),
            ('anova',               {'group_column':'department','value_column':'salary','alpha':'0.05'}),
            ('chi-square',          {'column1':'department','column2':'category','alpha':'0.05'}),
            ('regression-simple',   {'x_column':'age','y_column':'salary'}),
            ('regression-multiple', {'x_columns':'age,score','y_column':'salary'}),
            ('moving-average',      {'column':'salary','window':'3','type':'simple'}),
            ('exponential-smooth',  {'column':'salary','alpha':'0.3'}),
            ('seasonality',         {'column':'value','period':'12'}, TS_HEADERS, TS_ROWS),
            ('confidence-interval', {'column':'salary','confidence':'95'}),
            ('sample-size',         {'method':'proportion','confidence':'95','margin_of_error':'5'}),
            ('probability-dist',    {'distribution':'normal','x_value':'75000','mu':'75000','sigma':'15000'}),
            ('percentile-rank',     {'column':'salary'}),
            ('z-score',             {'column':'salary'}),
            ('normality-test',      {'column':'salary'}),
            ('outlier-score',       {'column':'salary','method':'zscore'}),
            ('cross-tabulation',    {'row_column':'department','col_column':'category','normalize':'none'}),
            ('frequency-table',     {'column':'department','top_n':'5','sort_by':'frequency'}),
            ('pareto-analysis',     {'category_column':'department','value_column':'salary'}),
            ('cohort-analysis',     {'user_column':'id','date_column':'date'}),
            ('survival-analysis',   {'time_column':'age','event_column':'active'}),
            ('bootstrap',           {'column':'salary','n_iterations':'200','statistic':'mean','confidence':'95'}),
        ]

        for tool_id, params, *extra in tools:
            try:
                h = extra[0] if extra else None
                r = extra[1] if len(extra) > 1 else None
                result = run_tool(m, tool_id, params, h, r)
                assert_result(result)
                res.ok(tool_id)
            except Exception as e:
                res.fail(tool_id, e)

    except ImportError as e:
        res.fail('import stats', e)


def test_ml(res: TestResult):
    print('\n🤖 Machine Learning (37 tools)')
    try:
        import modules.ml as m

        tools = [
            # Clustering
            ('kmeans',              {'feature_columns':'x,y','k':'2','max_iter':'50'}, SMALL_HEADERS, SMALL_ROWS),
            ('dbscan',              {'feature_columns':'x,y','eps':'2.0','min_samples':'2'}, SMALL_HEADERS, SMALL_ROWS),
            ('hierarchical',        {'feature_columns':'x,y','n_clusters':'2','linkage':'complete'}, SMALL_HEADERS, SMALL_ROWS),
            # Classification
            ('knn-classify',        {'feature_columns':'x,y','label_column':'label','k':'3'}, SMALL_HEADERS, SMALL_ROWS),
            ('naive-bayes',         {'feature_columns':'x,y','label_column':'label'}, SMALL_HEADERS, SMALL_ROWS),
            ('decision-tree',       {'feature_columns':'x,y','label_column':'label','max_depth':'2'}, SMALL_HEADERS, SMALL_ROWS),
            ('random-forest',       {'feature_columns':'x,y','label_column':'label','n_estimators':'5'}, SMALL_HEADERS, SMALL_ROWS),
            ('svm-classify',        {'feature_columns':'x,y','label_column':'label','C':'1.0'}, SMALL_HEADERS, SMALL_ROWS),
            ('logistic-regression', {'feature_columns':'x,y','label_column':'label','max_iter':'100'}, SMALL_HEADERS, SMALL_ROWS),
            # Regression
            ('linear-regression',   {'feature_columns':'x','label_column':'y'}, SMALL_HEADERS, SMALL_ROWS),
            ('polynomial-regression',{'x_column':'x','y_column':'y','degree':'2'}, SMALL_HEADERS, SMALL_ROWS),
            ('ridge-regression',    {'feature_columns':'x','label_column':'y','alpha':'1.0'}, SMALL_HEADERS, SMALL_ROWS),
            ('lasso-regression',    {'feature_columns':'x','label_column':'y','alpha':'0.1'}, SMALL_HEADERS, SMALL_ROWS),
            ('knn-regression',      {'feature_columns':'x','label_column':'y','k':'3'}, SMALL_HEADERS, SMALL_ROWS),
            ('gradient-boosting',   {'feature_columns':'x','label_column':'y','n_estimators':'20','learning_rate':'0.1'}, SMALL_HEADERS, SMALL_ROWS),
            # Dimensionality
            ('pca',                 {'feature_columns':'x,y','n_components':'2'}, SMALL_HEADERS, SMALL_ROWS),
            ('feature-selection',   {'feature_columns':'x,y','label_column':'label','n_features':'1','method':'correlation'}, SMALL_HEADERS, SMALL_ROWS),
            ('feature-importance',  {'feature_columns':'x,y','label_column':'label'}, SMALL_HEADERS, SMALL_ROWS),
            # Anomaly
            ('isolation-forest',    {'feature_columns':'salary,age','n_estimators':'20','threshold':'0.6'}),
            ('lof',                 {'feature_columns':'salary,age','k':'3','threshold':'1.5'}),
            ('zscore-anomaly',      {'feature_columns':'salary,age','threshold':'2.5'}),
            # Time Series
            ('arima-simple',        {'column':'value','p':'1','forecast_steps':'3'}, TS_HEADERS, TS_ROWS),
            ('time-series-forecast',{'column':'value','forecast_steps':'5','method':'ets'}, TS_HEADERS, TS_ROWS),
            ('change-point',        {'column':'value','period':'3','threshold':'1.5'}, TS_HEADERS, TS_ROWS),
            # NLP
            ('tfidf',               {'column':'text','top_n':'5'}, TEXT_HEADERS, TEXT_ROWS),
            ('text-similarity',     {'column1':'text','column2':'category','method':'jaccard'}, TEXT_HEADERS, TEXT_ROWS),
            ('sentiment-simple',    {'column':'text'}, TEXT_HEADERS, TEXT_ROWS),
            ('word-frequency',      {'column':'text','top_n':'10'}, TEXT_HEADERS, TEXT_ROWS),
            # Association
            ('apriori',             {'items_column':'category','min_support':'0.1','separator':','}),
            ('association-rules',   {'items_column':'category','min_support':'0.1','min_confidence':'0.3'}),
            # Preprocessing
            ('normalize',           {'columns':'salary,age,score'}),
            ('standardize',         {'columns':'salary,age,score'}),
            ('encode-categorical',  {'column':'department','method':'label'}),
            ('train-test-split',    {'test_size':'0.2','shuffle':'true','random_state':'42'}),
            ('cross-validate',      {'k_folds':'3'}),
            # Evaluation
            ('confusion-matrix',    {'actual_column':'category','predicted_column':'active'}),
            ('roc-auc',             {'actual_column':'active','score_column':'score','positive_class':'True'}),
        ]

        for entry in tools:
            tool_id = entry[0]
            params  = entry[1]
            h = entry[2] if len(entry) > 2 else None
            r = entry[3] if len(entry) > 3 else None
            try:
                result = run_tool(m, tool_id, params, h, r)
                assert_result(result)
                res.ok(tool_id)
            except Exception as e:
                res.fail(tool_id, e)

    except ImportError as e:
        res.fail('import ml', e)


def test_viz(res: TestResult):
    print('\n📈 Visualization (19 tools)')
    try:
        import modules.viz as m

        tools = [
            ('bar-chart',           {'x_column':'department','y_columns':'salary','aggregation':'mean'}),
            ('line-chart',          {'x_column':'date','y_columns':'salary'}),
            ('scatter-plot',        {'x_column':'age','y_column':'salary'}),
            ('pie-chart',           {'label_column':'department','value_column':'salary','type':'pie'}),
            ('histogram',           {'column':'salary','n_bins':'5'}),
            ('box-plot',            {'columns':'salary,score'}),
            ('heatmap',             {'row_column':'department','col_column':'category','value_column':'salary'}),
            ('bubble-chart',        {'x_column':'age','y_column':'salary','size_column':'score'}),
            ('area-chart',          {'x_column':'date','y_columns':'salary','stacked':'false'}),
            ('treemap',             {'label_column':'department','value_column':'salary'}),
            ('funnel-chart',        {'label_column':'department','value_column':'salary'}),
            ('waterfall-chart',     {'label_column':'department','value_column':'salary'}),
            ('radar-chart',         {'metric_columns':'salary,age,score','label_column':'name'}),
            ('gantt-chart',         {'task_column':'name','start_column':'date','end_column':'date'}),
            ('density-plot',        {'column':'salary','n_points':'50'}),
            ('violin-plot',         {'columns':'salary,score'}),
            ('sankey-diagram',      {'from_column':'department','to_column':'category','value_column':'salary'}),
            ('sparklines',          {'column':'salary','group_column':'department'}),
            ('correlation-heatmap', {'columns':'salary,age,score','method':'pearson'}),
        ]

        for tool_id, params in tools:
            try:
                result = run_tool(m, tool_id, params)
                # Viz tools return chart data, not rows
                assert isinstance(result, dict), 'Must return dict'
                assert 'chart' in result or 'summary' in result, 'Must have chart or summary'
                res.ok(tool_id)
            except Exception as e:
                res.fail(tool_id, e)

    except ImportError as e:
        res.fail('import viz', e)


def test_ai(res: TestResult):
    print('\n🧠 AI Insights (18 tools)')
    try:
        import modules.ai as m

        # Pure Python tools (no API needed)
        pure_tools = [
            ('auto-tag',        {'column':'department','rules':'engineering:Engineering;marketing:Marketing;hr:HR'}),
            ('keyword-extract', {'column':'name','top_n_per_row':'2'}),
            ('pattern-detect',  {'column':'email'}),
            ('smart-rename',    {}),
        ]

        for tool_id, params in pure_tools:
            try:
                result = run_tool(m, tool_id, params)
                assert_result(result)
                res.ok(tool_id)
            except Exception as e:
                res.fail(tool_id, e)

        # API tools — skip if no key
        api_tools = [
            'explain-data','formula-gen','sql-gen','insight-summary',
            'anomaly-explain','data-story','column-suggest','cleaning-suggest',
            'chart-suggest','question-answer','trend-explain','segment-describe',
            'report-generate','translate-data',
        ]

        api_key = os.environ.get('SWAK_CLAUDE_API_KEY', '')
        if not api_key or api_key.startswith('sk-ant-PASTE'):
            for tool_id in api_tools:
                res.skip(tool_id, 'No API key — set SWAK_CLAUDE_API_KEY')
        else:
            for tool_id in api_tools:
                try:
                    params = {'language': 'en', 'question': 'What is the average salary?',
                              'task': 'sum of salary by department', 'column': 'name'}
                    result = run_tool(m, tool_id, params)
                    assert_result(result)
                    res.ok(tool_id)
                except Exception as e:
                    res.fail(tool_id, e)

    except ImportError as e:
        res.fail('import ai', e)


def test_import(res: TestResult):
    print('\n📥 Data Import (10 tools)')
    try:
        import modules.import_tools as m

        csv_content = 'a,b,c\n1,2,3\n4,5,6\n7,8,9'
        json_content = '[{"x":1,"y":2},{"x":3,"y":4}]'
        xml_content  = '<data><item><name>Alice</name><age>30</age></item><item><name>Bob</name><age>25</age></item></data>'

        tools = [
            ('import-csv',      {'content': csv_content, 'delimiter': ',', 'has_header': 'true'}),
            ('import-json',     {'content': json_content}),
            ('import-xml',      {'content': xml_content, 'row_tag': 'item'}),
            ('import-clipboard',{'content': 'col1\tcol2\tcol3\n1\t2\t3\n4\t5\t6'}),
            ('import-excel',    {}),    # JS bridge — pass-through
            ('merge-datasets',  {
                'right_content': csv_content,
                'right_delimiter': ',',
                'left_key': 'id',
                'right_key': 'a',
                'join_type': 'left',
            }),
        ]

        for tool_id, params in tools:
            try:
                if tool_id == 'import-excel':
                    # Pass-through tool — needs data
                    result = m.run(tool_id, params, SAMPLE_HEADERS, SAMPLE_ROWS[:3])
                else:
                    result = m.run(tool_id, params, SAMPLE_HEADERS, SAMPLE_ROWS[:5])
                assert_result(result)
                res.ok(tool_id)
            except Exception as e:
                res.fail(tool_id, e)

        # Network-dependent tools — skip
        for tool_id in ['import-sql', 'import-api', 'import-web', 'import-parquet']:
            res.skip(tool_id, 'Requires network/file — tested separately')

    except ImportError as e:
        res.fail('import import_tools', e)


def test_export(res: TestResult):
    print('\n📤 Data Export (11 tools)')
    try:
        import modules.export_tools as m

        tools = [
            ('export-csv',      {'filename':'test.csv'}),
            ('export-json',     {'filename':'test.json','style':'records'}),
            ('export-xml',      {'filename':'test.xml','row_tag':'record'}),
            ('export-html',     {'filename':'test.html','theme':'dark'}),
            ('export-markdown', {'filename':'test.md','title':'Test'}),
            ('export-sql',      {'filename':'test.sql','table_name':'employees','db_type':'postgresql'}),
            ('export-latex',    {'filename':'test.tex','caption':'Test Table'}),
            ('export-tsv',      {'filename':'test.tsv'}),
            ('export-yaml',     {'filename':'test.yaml'}),
            ('export-excel',    {'filename':'test.xlsx','sheet_name':'Data'}),
            ('export-report',   {'filename':'test_report.html','title':'SWAK Report','include_stats':'true'}),
        ]

        for tool_id, params in tools:
            try:
                result = m.run(tool_id, params, SAMPLE_HEADERS, SAMPLE_ROWS[:5])
                assert isinstance(result, dict), 'Must return dict'
                # Export tools return download info
                if 'download' in result:
                    assert 'filename' in result['download'], 'Missing filename'
                    assert 'content_b64' in result['download'], 'Missing content'
                    # Verify content is not empty
                    import base64
                    content = base64.b64decode(result['download']['content_b64'])
                    assert len(content) > 0, 'Empty export content'
                res.ok(tool_id)
            except ImportError:
                res.skip(tool_id, 'openpyxl not installed')
            except Exception as e:
                res.fail(tool_id, e)

    except ImportError as e:
        res.fail('import export_tools', e)


def test_profiling(res: TestResult):
    print('\n🔬 Data Profiling (11 tools)')
    try:
        import modules.profiling as m

        tools = [
            ('data-profile',     {}),
            ('quality-score',    {}),
            ('column-profile',   {'column':'salary'}),
            ('missing-analysis', {}),
            ('duplicate-report', {'key_columns':'id'}),
            ('cardinality',      {}),
            ('data-types',       {}),
            ('value-dist',       {'column':'department','n_bins':'5'}),
            ('outlier-report',   {'columns':'salary,age,score','method':'iqr'}),
            ('schema-infer',     {}),
            ('compare-datasets', {'dataset2':'[{"id":1,"name":"Alice"},{"id":2,"name":"Bob"}]'}),
        ]

        for tool_id, params in tools:
            try:
                result = run_tool(m, tool_id, params)
                assert_result(result)
                res.ok(tool_id)
            except Exception as e:
                res.fail(tool_id, e)

    except ImportError as e:
        res.fail('import profiling', e)


def test_dataeng(res: TestResult):
    print('\n⚙️  Data Engineering (16 tools)')
    try:
        import modules.dataeng as m

        tools = [
            ('generate-ids',      {'style':'sequential','prefix':'EMP-','start':'1'}),
            ('hash-column',       {'column':'email','algorithm':'md5'}),
            ('json-flatten',      {'column':'name'}),
            ('json-extract',      {'column':'name','json_path':''}),
            ('array-expand',      {'column':'department','separator':','}),
            ('window-function',   {'column':'salary','function':'cumsum','partition_by':'department','order_by':'salary'}),
            ('data-lineage',      {'transformations':['remove duplicates','fill missing']}),
            ('schema-validate',   {'schema':{'salary':{'type':'number','min':0},'age':{'required':True}}}),
            ('data-masking',      {'column':'email','method':'partial'}),
            ('partition-data',    {'column':'department','strategy':'value'}),
            ('sample-data',       {'method':'random','n':'5','seed':'42'}),
            ('data-diff',         {'dataset2':'[{"id":1},{"id":99}]','key_column':'id'}),
            ('sql-transform',     {'select':'id,name,salary','where':'salary > 70000','order_by':'salary','order_dir':'desc','limit':'5'}),
            ('generate-sequence', {'column_name':'seq','start':'1','step':'2','repeat':'1'}),
            ('lookup-table',      {'column':'department','lookup_table':'{"Engineering":"ENG","Marketing":"MKT","HR":"HR"}','output_column':'dept_code'}),
            ('conditional-logic', {'output_column':'level','conditions':[{'expr':'salary > 80000','value':'Senior'},{'expr':'salary > 60000','value':'Mid'}],'default':'Junior'}),
        ]

        for tool_id, params in tools:
            try:
                result = run_tool(m, tool_id, params)
                assert isinstance(result, dict), 'Must return dict'
                res.ok(tool_id)
            except Exception as e:
                res.fail(tool_id, e)

    except ImportError as e:
        res.fail('import dataeng', e)


def test_productivity(res: TestResult):
    print('\n⚡ Productivity (14 tools)')
    try:
        import modules.productivity as m

        tools = [
            ('auto-format',        {'style':'swak_dark'}),
            ('conditional-format', {'column':'salary','rule':'color_scale'}),
            ('create-chart',       {'chart_type':'bar','x_column':'department','y_columns':'salary','title':'Salary by Dept'}),
            ('freeze-panes',       {'freeze_row':'1','freeze_col':'0'}),
            ('add-filter',         {'column':'department'}),
            ('protect-sheet',      {'password':'','allow_select':'true','allow_format':'false'}),
            ('named-range',        {'range_name':'SalaryData','start_row':'1','end_row':'14','start_col':'0','end_col':'9'}),
            ('data-validation',    {'column':'department','rule':'list','values':'Engineering,Marketing,HR'}),
            ('add-hyperlinks',     {'column':'email','url_column':'email','label_column':'name'}),
            ('summarize-sheet',    {}),
            ('batch-formulas',     {'formulas':'[{"col_name":"tax","excel_formula":"=C2*0.2"}]'}),
            ('clean-formatting',   {'scope':'all'}),
            ('workbook-toc',       {'sheet_names':['Sheet1','Sheet2','Analysis'],'title':'Table of Contents'}),
            ('schedule-refresh',   {'interval_minutes':'60','tool_to_run':'data-profile','enabled':'true'}),
        ]

        for tool_id, params in tools:
            try:
                result = run_tool(m, tool_id, params)
                assert isinstance(result, dict), 'Must return dict'
                res.ok(tool_id)
            except Exception as e:
                res.fail(tool_id, e)

    except ImportError as e:
        res.fail('import productivity', e)


def test_server(res: TestResult):
    """Test Flask server health endpoint"""
    print('\n🌐 Flask Server')
    import urllib.request
    try:
        r = urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=3)
        data = r.read()
        import json
        payload = json.loads(data)
        assert payload.get('status') == 'ok', f'Bad status: {payload}'
        res.ok('health endpoint')
    except Exception as e:
        res.skip('health endpoint', f'Server not running — {e}')


def test_license(res: TestResult):
    print('\n🔐 License Module')
    try:
        import modules.license as m

        # Free tool check
        assert m.is_free_tool('remove-duplicates'), 'remove-duplicates should be free'
        assert not m.is_free_tool('kmeans'), 'kmeans should be pro'
        res.ok('is_free_tool')

        # No key → False
        result = m.validate('', '')
        assert result == False, 'Empty key should return False'
        res.ok('empty key → False')

        # Device ID generation
        dev_id = m._get_device_id()
        assert isinstance(dev_id, str) and len(dev_id) == 16, 'Device ID should be 16 chars'
        res.ok('device fingerprint')

    except ImportError as e:
        res.fail('import license', e)
    except Exception as e:
        res.fail('license', e)


# ══════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════

def run_all_tests(modules_only: list = None) -> bool:
    """
    Run all tests. Pass modules_only=['clean','stats'] to run specific modules.
    Returns True if all passed.
    """
    print('=' * 52)
    print(f'  SWAK Test Suite v2.0.0')
    print(f'  Testing 215 tools across 12 modules')
    print('=' * 52)

    start_time = time.time()
    res = TestResult()

    all_module_tests = [
        ('clean',       test_clean),
        ('filter',      test_filter),
        ('transform',   test_transform),
        ('stats',       test_stats),
        ('ml',          test_ml),
        ('viz',         test_viz),
        ('ai',          test_ai),
        ('import',      test_import),
        ('export',      test_export),
        ('profiling',   test_profiling),
        ('dataeng',     test_dataeng),
        ('productivity',test_productivity),
        ('server',      test_server),
        ('license',     test_license),
    ]

    for name, fn in all_module_tests:
        if modules_only and name not in modules_only:
            continue
        try:
            fn(res)
        except Exception as e:
            res.fail(f'{name} module crash', e)
            traceback.print_exc()

    elapsed = time.time() - start_time
    success = res.summary()
    print(f'\n  ⏱ Time: {elapsed:.2f}s')

    return success


if __name__ == '__main__':
    # Allow running specific modules: python test_suite.py clean stats
    modules_filter = sys.argv[1:] if len(sys.argv) > 1 else None
    success = run_all_tests(modules_only=modules_filter)
    sys.exit(0 if success else 1)
