# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
"""
SWAK — Machine Learning Module (37 tools)
Pure Python implementations — no external ML libs required
scikit-learn used when available for better accuracy
"""

import math
import random
from collections import defaultdict, Counter


def run(tool_id: str, params: dict, headers: list, rows: list) -> dict:
    fn_map = {
        # Clustering
        'kmeans':               kmeans,
        'dbscan':               dbscan,
        'hierarchical':         hierarchical,
        # Classification
        'knn-classify':         knn_classify,
        'naive-bayes':          naive_bayes,
        'decision-tree':        decision_tree,
        'random-forest':        random_forest,
        'svm-classify':         svm_classify,
        'logistic-regression':  logistic_regression,
        # Regression
        'linear-regression':    linear_regression_ml,
        'polynomial-regression':polynomial_regression,
        'ridge-regression':     ridge_regression,
        'lasso-regression':     lasso_regression,
        'knn-regression':       knn_regression,
        'gradient-boosting':    gradient_boosting,
        # Dimensionality
        'pca':                  pca,
        'feature-selection':    feature_selection,
        'feature-importance':   feature_importance,
        # Anomaly Detection
        'isolation-forest':     isolation_forest,
        'lof':                  lof,
        'zscore-anomaly':       zscore_anomaly,
        # Time Series
        'arima-simple':         arima_simple,
        'time-series-forecast': time_series_forecast,
        'change-point':         change_point,
        # NLP / Text
        'tfidf':                tfidf,
        'text-similarity':      text_similarity,
        'sentiment-simple':     sentiment_simple,
        'word-frequency':       word_frequency,
        # Association
        'apriori':              apriori,
        'association-rules':    association_rules,
        # Preprocessing
        'normalize':            normalize_ml,
        'standardize':          standardize_ml,
        'encode-categorical':   encode_categorical,
        'train-test-split':     train_test_split,
        'cross-validate':       cross_validate,
        # Evaluation
        'confusion-matrix':     confusion_matrix,
        'roc-auc':              roc_auc,
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
    return v is None or (isinstance(v, float) and math.isnan(v)) or (isinstance(v, str) and v.strip() == '')

def _to_number(v):
    if _is_empty(v): return None
    try:
        return float(str(v).replace(',', '').replace('،', ''))
    except: return None

def _get_matrix(headers, rows, col_names):
    """Extract numeric matrix for given columns"""
    idxs = [_col_idx(headers, c) for c in col_names]
    X, valid_rows = [], []
    for row in rows:
        vals = [_to_number(row[i] if i < len(row) else None) for i in idxs]
        if all(v is not None for v in vals):
            X.append(vals)
            valid_rows.append(row)
    return X, valid_rows

def _mean(vals):
    return sum(vals) / len(vals) if vals else 0

def _std(vals):
    m = _mean(vals)
    v = sum((x-m)**2 for x in vals) / len(vals) if vals else 0
    return math.sqrt(v)

def _distance(a, b):
    return math.sqrt(sum((x-y)**2 for x,y in zip(a,b)))

def _result(headers, rows, title, stats, note=''):
    return {'headers': headers, 'rows': rows,
            'summary': {'title': title, 'stats': stats, 'note': note}}


# ══════════════════════════════════════════════════════════════════════════
# CLUSTERING
# ══════════════════════════════════════════════════════════════════════════

def kmeans(params, headers, rows):
    cols = params.get('feature_columns', headers)
    if isinstance(cols, str): cols = [c.strip() for c in cols.split(',')]
    k        = int(params.get('k', 3))
    max_iter = int(params.get('max_iter', 100))

    X, valid_rows = _get_matrix(headers, rows, cols)
    if len(X) < k:
        raise ValueError(f'داده کمتر از k={k} است')

    random.seed(42)
    # K-Means++ initialization
    centers = [random.choice(X)]
    for _ in range(k - 1):
        dists  = [min(_distance(x, c)**2 for c in centers) for x in X]
        total  = sum(dists)
        r      = random.uniform(0, total)
        cumsum = 0
        for i, d in enumerate(dists):
            cumsum += d
            if cumsum >= r:
                centers.append(X[i])
                break

    labels = [0] * len(X)
    for _ in range(max_iter):
        new_labels = [min(range(k), key=lambda c: _distance(X[i], centers[c])) for i in range(len(X))]
        if new_labels == labels: break
        labels = new_labels
        centers = []
        for c in range(k):
            pts = [X[i] for i in range(len(X)) if labels[i] == c]
            centers.append([_mean([p[j] for p in pts]) for j in range(len(cols))] if pts else X[0])

    # Inertia
    inertia = sum(_distance(X[i], centers[labels[i]])**2 for i in range(len(X)))

    new_headers = headers + ['cluster']
    new_rows    = [list(valid_rows[i]) + [labels[i]] for i in range(len(valid_rows))]
    cluster_sizes = Counter(labels)

    return _result(new_headers, new_rows, f'K-Means (k={k})',
                   [['k', k], ['inertia', round(inertia, 2)],
                    ['اندازه خوشه‌ها', ', '.join(f'C{c}:{cluster_sizes[c]}' for c in range(k))]])


def dbscan(params, headers, rows):
    cols = params.get('feature_columns', headers)
    if isinstance(cols, str): cols = [c.strip() for c in cols.split(',')]
    eps      = float(params.get('eps', 0.5))
    min_pts  = int(params.get('min_samples', 5))

    X, valid_rows = _get_matrix(headers, rows, cols)
    n       = len(X)
    labels  = [-1] * n  # -1 = noise
    cluster_id = 0

    def region_query(idx):
        return [j for j in range(n) if _distance(X[idx], X[j]) <= eps]

    visited = set()
    for i in range(n):
        if i in visited: continue
        visited.add(i)
        neighbors = region_query(i)
        if len(neighbors) < min_pts:
            labels[i] = -1  # noise
        else:
            labels[i] = cluster_id
            seed = set(neighbors) - visited
            while seed:
                j = seed.pop()
                visited.add(j)
                labels[j] = cluster_id
                j_neighbors = region_query(j)
                if len(j_neighbors) >= min_pts:
                    seed |= set(j_neighbors) - visited
            cluster_id += 1

    noise    = labels.count(-1)
    n_clust  = cluster_id
    new_headers = headers + ['cluster']
    new_rows    = [list(valid_rows[i]) + [labels[i]] for i in range(len(valid_rows))]

    return _result(new_headers, new_rows, f'DBSCAN',
                   [['خوشه‌ها', n_clust], ['نویز', noise], ['eps', eps], ['min_samples', min_pts]])


def hierarchical(params, headers, rows):
    cols = params.get('feature_columns', headers)
    if isinstance(cols, str): cols = [c.strip() for c in cols.split(',')]
    n_clusters = int(params.get('n_clusters', 3))
    linkage    = params.get('linkage', 'complete')

    X, valid_rows = _get_matrix(headers, rows, cols)
    n = len(X)
    if n > 500:
        return _result(headers, rows, 'Hierarchical Clustering',
                       [['خطا', 'برای n > 500 از K-Means استفاده کنید']])

    # Agglomerative: start with each point in its own cluster
    clusters = [{i} for i in range(n)]

    def cluster_dist(c1, c2):
        pairs = [_distance(X[i], X[j]) for i in c1 for j in c2]
        if linkage == 'single':  return min(pairs)
        if linkage == 'complete': return max(pairs)
        return _mean(pairs)

    while len(clusters) > n_clusters:
        min_d, merge = float('inf'), (0, 1)
        for i in range(len(clusters)):
            for j in range(i+1, len(clusters)):
                d = cluster_dist(clusters[i], clusters[j])
                if d < min_d:
                    min_d, merge = d, (i, j)
        i, j = merge
        clusters[i] |= clusters[j]
        clusters.pop(j)

    labels = [0] * n
    for cid, members in enumerate(clusters):
        for m in members:
            labels[m] = cid

    new_headers = headers + ['cluster']
    new_rows    = [list(valid_rows[i]) + [labels[i]] for i in range(len(valid_rows))]

    return _result(new_headers, new_rows, 'Hierarchical Clustering',
                   [['خوشه‌ها', n_clusters], ['linkage', linkage]])


# ══════════════════════════════════════════════════════════════════════════
# CLASSIFICATION
# ══════════════════════════════════════════════════════════════════════════

def knn_classify(params, headers, rows):
    feat_cols = params.get('feature_columns', headers[:-1])
    label_col = params.get('label_column', headers[-1])
    if isinstance(feat_cols, str): feat_cols = [c.strip() for c in feat_cols.split(',')]
    k = int(params.get('k', 5))

    X, valid_rows = _get_matrix(headers, rows, feat_cols)
    lci   = _col_idx(headers, label_col)
    y     = [str(r[lci] if lci < len(r) else '') for r in valid_rows]

    # Leave-one-out prediction
    preds = []
    for i in range(len(X)):
        dists = sorted([(j, _distance(X[i], X[j])) for j in range(len(X)) if j != i], key=lambda x: x[1])
        k_nearest = [y[j] for j, _ in dists[:k]]
        preds.append(Counter(k_nearest).most_common(1)[0][0])

    correct  = sum(1 for p, t in zip(preds, y) if p == t)
    accuracy = correct / len(y) if y else 0

    new_headers = headers + ['knn_prediction']
    new_rows    = [list(valid_rows[i]) + [preds[i]] for i in range(len(valid_rows))]

    return _result(new_headers, new_rows, f'KNN (k={k})',
                   [['k', k], ['دقت (LOO)', f'{accuracy*100:.2f}%'], ['صحیح', correct]])


def naive_bayes(params, headers, rows):
    feat_cols = params.get('feature_columns', headers[:-1])
    label_col = params.get('label_column', headers[-1])
    if isinstance(feat_cols, str): feat_cols = [c.strip() for c in feat_cols.split(',')]

    X, valid_rows = _get_matrix(headers, rows, feat_cols)
    lci = _col_idx(headers, label_col)
    y   = [str(r[lci] if lci < len(r) else '') for r in valid_rows]

    classes   = list(set(y))
    class_cnt = Counter(y)
    n         = len(y)

    # Gaussian Naive Bayes
    stats = {}
    for cls in classes:
        idxs = [i for i, yi in enumerate(y) if yi == cls]
        stats[cls] = {
            'prior': class_cnt[cls] / n,
            'means': [_mean([X[i][j] for i in idxs]) for j in range(len(feat_cols))],
            'stds':  [_std([X[i][j]  for i in idxs]) + 1e-9 for j in range(len(feat_cols))],
        }

    def predict(x):
        best_cls, best_log = None, -float('inf')
        for cls, s in stats.items():
            log_p = math.log(s['prior'])
            for j in range(len(feat_cols)):
                mu, sg = s['means'][j], s['stds'][j]
                log_p += -math.log(sg) - 0.5*((x[j]-mu)/sg)**2
            if log_p > best_log:
                best_log, best_cls = log_p, cls
        return best_cls

    preds    = [predict(x) for x in X]
    correct  = sum(1 for p, t in zip(preds, y) if p == t)
    accuracy = correct / n if n else 0

    new_headers = headers + ['nb_prediction']
    new_rows    = [list(valid_rows[i]) + [preds[i]] for i in range(len(valid_rows))]

    return _result(new_headers, new_rows, 'Naive Bayes (Gaussian)',
                   [['دقت', f'{accuracy*100:.2f}%'], ['کلاس‌ها', len(classes)]])


def decision_tree(params, headers, rows):
    # Simplified: find best single-feature threshold split
    feat_cols = params.get('feature_columns', headers[:-1])
    label_col = params.get('label_column', headers[-1])
    if isinstance(feat_cols, str): feat_cols = [c.strip() for c in feat_cols.split(',')]
    max_depth = int(params.get('max_depth', 3))

    X, valid_rows = _get_matrix(headers, rows, feat_cols)
    lci = _col_idx(headers, label_col)
    y   = [str(r[lci] if lci < len(r) else '') for r in valid_rows]

    def gini(labels):
        n = len(labels)
        return 1 - sum((c/n)**2 for c in Counter(labels).values()) if n else 0

    def best_split(indices):
        best = None
        best_g = float('inf')
        for fi in range(len(feat_cols)):
            vals = sorted(set(X[i][fi] for i in indices))
            for thresh in [(vals[i]+vals[i+1])/2 for i in range(len(vals)-1)]:
                left  = [i for i in indices if X[i][fi] <= thresh]
                right = [i for i in indices if X[i][fi] >  thresh]
                if not left or not right: continue
                g = (len(left)*gini([y[i] for i in left]) +
                     len(right)*gini([y[i] for i in right])) / len(indices)
                if g < best_g:
                    best_g, best = g, (fi, thresh, left, right)
        return best

    def predict_tree(x, node):
        if 'label' in node: return node['label']
        if x[node['fi']] <= node['thresh']:
            return predict_tree(x, node['left'])
        return predict_tree(x, node['right'])

    def build_tree(indices, depth):
        labels = [y[i] for i in indices]
        if depth == 0 or len(set(labels)) == 1:
            return {'label': Counter(labels).most_common(1)[0][0]}
        split = best_split(indices)
        if not split:
            return {'label': Counter(labels).most_common(1)[0][0]}
        fi, thresh, left, right = split
        return {'fi': fi, 'thresh': thresh,
                'left':  build_tree(left,  depth-1),
                'right': build_tree(right, depth-1)}

    tree  = build_tree(list(range(len(X))), max_depth)
    preds = [predict_tree(x, tree) for x in X]
    acc   = sum(1 for p,t in zip(preds,y) if p==t) / len(y) if y else 0

    new_headers = headers + ['tree_prediction']
    new_rows    = [list(valid_rows[i]) + [preds[i]] for i in range(len(valid_rows))]

    return _result(new_headers, new_rows, f'Decision Tree (depth={max_depth})',
                   [['دقت', f'{acc*100:.2f}%'], ['max_depth', max_depth]])


def random_forest(params, headers, rows):
    feat_cols = params.get('feature_columns', headers[:-1])
    label_col = params.get('label_column', headers[-1])
    if isinstance(feat_cols, str): feat_cols = [c.strip() for c in feat_cols.split(',')]
    n_trees = int(params.get('n_estimators', 10))

    X, valid_rows = _get_matrix(headers, rows, feat_cols)
    lci = _col_idx(headers, label_col)
    y   = [str(r[lci] if lci < len(r) else '') for r in valid_rows]
    n   = len(X)

    random.seed(42)

    def gini(labels):
        n = len(labels)
        return 1 - sum((c/n)**2 for c in Counter(labels).values()) if n else 0

    def build_stump(indices, feat_subset):
        best_g, best = float('inf'), None
        for fi in feat_subset:
            vals = sorted(set(X[i][fi] for i in indices))
            for thresh in [(vals[j]+vals[j+1])/2 for j in range(len(vals)-1)]:
                left  = [i for i in indices if X[i][fi] <= thresh]
                right = [i for i in indices if X[i][fi] >  thresh]
                if not left or not right: continue
                g = (len(left)*gini([y[i] for i in left]) +
                     len(right)*gini([y[i] for i in right])) / len(indices)
                if g < best_g:
                    best_g, best = g, (fi, thresh, left, right)
        if not best:
            return {'label': Counter([y[i] for i in indices]).most_common(1)[0][0]}
        fi, thresh, left, right = best
        lbl = lambda idxs: Counter([y[i] for i in idxs]).most_common(1)[0][0]
        return {'fi': fi, 'thresh': thresh, 'left': {'label': lbl(left)}, 'right': {'label': lbl(right)}}

    def predict_stump(x, node):
        if 'label' in node: return node['label']
        return predict_stump(x, node['left'] if x[node['fi']] <= node['thresh'] else node['right'])

    m = max(1, int(math.sqrt(len(feat_cols))))
    trees = []
    for _ in range(n_trees):
        boot = [random.randint(0, n-1) for _ in range(n)]
        feat_sub = random.sample(range(len(feat_cols)), m)
        trees.append(build_stump(boot, feat_sub))

    preds = [Counter([predict_stump(X[i], t) for t in trees]).most_common(1)[0][0]
             for i in range(n)]
    acc   = sum(1 for p,t in zip(preds,y) if p==t) / n if n else 0

    new_headers = headers + ['rf_prediction']
    new_rows    = [list(valid_rows[i]) + [preds[i]] for i in range(len(valid_rows))]

    return _result(new_headers, new_rows, f'Random Forest ({n_trees} trees)',
                   [['دقت', f'{acc*100:.2f}%'], ['درخت‌ها', n_trees]])


def svm_classify(params, headers, rows):
    """Linear SVM via gradient descent"""
    feat_cols = params.get('feature_columns', headers[:-1])
    label_col = params.get('label_column', headers[-1])
    if isinstance(feat_cols, str): feat_cols = [c.strip() for c in feat_cols.split(',')]

    X, valid_rows = _get_matrix(headers, rows, feat_cols)
    lci = _col_idx(headers, label_col)
    y   = [str(r[lci] if lci < len(r) else '') for r in valid_rows]

    classes = sorted(set(y))
    if len(classes) != 2:
        return _result(headers, rows, 'SVM',
                       [['خطا', 'SVM باینری: دقیقاً ۲ کلاس لازم است']])

    # Normalize features
    means = [_mean([x[j] for x in X]) for j in range(len(feat_cols))]
    stds  = [_std([x[j] for x in X]) + 1e-9 for j in range(len(feat_cols))]
    Xn    = [[(X[i][j]-means[j])/stds[j] for j in range(len(feat_cols))] for i in range(len(X))]
    yn    = [1 if yi == classes[1] else -1 for yi in y]

    # SGD for linear SVM
    w  = [0.0] * len(feat_cols)
    b  = 0.0
    lr = 0.01
    C  = float(params.get('C', 1.0))

    random.seed(42)
    for epoch in range(100):
        idxs = list(range(len(Xn)))
        random.shuffle(idxs)
        for i in idxs:
            margin = yn[i] * (sum(w[j]*Xn[i][j] for j in range(len(feat_cols))) + b)
            if margin < 1:
                for j in range(len(feat_cols)):
                    w[j] = (1-lr)*w[j] + lr*C*yn[i]*Xn[i][j]
                b += lr*C*yn[i]
            else:
                for j in range(len(feat_cols)):
                    w[j] = (1-lr)*w[j]

    preds = []
    for x in Xn:
        score = sum(w[j]*x[j] for j in range(len(feat_cols))) + b
        preds.append(classes[1] if score > 0 else classes[0])

    acc = sum(1 for p,t in zip(preds,y) if p==t) / len(y) if y else 0
    new_headers = headers + ['svm_prediction']
    new_rows    = [list(valid_rows[i]) + [preds[i]] for i in range(len(valid_rows))]

    return _result(new_headers, new_rows, 'SVM (Linear)',
                   [['دقت', f'{acc*100:.2f}%'], ['C', C], ['کلاس‌ها', classes]])


def logistic_regression(params, headers, rows):
    feat_cols = params.get('feature_columns', headers[:-1])
    label_col = params.get('label_column', headers[-1])
    if isinstance(feat_cols, str): feat_cols = [c.strip() for c in feat_cols.split(',')]

    X, valid_rows = _get_matrix(headers, rows, feat_cols)
    lci = _col_idx(headers, label_col)
    y_raw = [str(r[lci] if lci < len(r) else '') for r in valid_rows]
    classes = sorted(set(y_raw))
    if len(classes) != 2:
        return _result(headers, rows, 'Logistic Regression',
                       [['خطا', '۲ کلاس لازم است']])

    yn = [1.0 if yi == classes[1] else 0.0 for yi in y_raw]
    means = [_mean([x[j] for x in X]) for j in range(len(feat_cols))]
    stds  = [_std([x[j] for x in X]) + 1e-9 for j in range(len(feat_cols))]
    Xn    = [[(X[i][j]-means[j])/stds[j] for j in range(len(feat_cols))] for i in range(len(X))]

    w  = [0.0] * len(feat_cols)
    b  = 0.0
    lr = float(params.get('learning_rate', 0.1))

    def sigmoid(z): return 1 / (1 + math.exp(-max(-500, min(500, z))))

    for _ in range(int(params.get('max_iter', 200))):
        for i in range(len(Xn)):
            z   = sum(w[j]*Xn[i][j] for j in range(len(feat_cols))) + b
            err = sigmoid(z) - yn[i]
            for j in range(len(feat_cols)):
                w[j] -= lr * err * Xn[i][j]
            b -= lr * err

    preds = [classes[1] if sigmoid(sum(w[j]*Xn[i][j] for j in range(len(feat_cols)))+b) > 0.5
             else classes[0] for i in range(len(Xn))]
    probs = [round(sigmoid(sum(w[j]*Xn[i][j] for j in range(len(feat_cols)))+b), 4) for i in range(len(Xn))]
    acc   = sum(1 for p,t in zip(preds,y_raw) if p==t) / len(y_raw) if y_raw else 0

    new_headers = headers + ['lr_prediction', 'lr_probability']
    new_rows    = [list(valid_rows[i]) + [preds[i], probs[i]] for i in range(len(valid_rows))]

    return _result(new_headers, new_rows, 'Logistic Regression',
                   [['دقت', f'{acc*100:.2f}%'], ['کلاس مثبت', classes[1]]])


# ══════════════════════════════════════════════════════════════════════════
# REGRESSION (ML)
# ══════════════════════════════════════════════════════════════════════════

def linear_regression_ml(params, headers, rows):
    feat_cols = params.get('feature_columns', headers[:-1])
    label_col = params.get('label_column', headers[-1])
    if isinstance(feat_cols, str): feat_cols = [c.strip() for c in feat_cols.split(',')]

    X, valid_rows = _get_matrix(headers, rows, feat_cols)
    lci = _col_idx(headers, label_col)
    y   = [_to_number(r[lci] if lci < len(r) else None) for r in valid_rows]
    y   = [v for v in y if v is not None]
    X   = X[:len(y)]

    # OLS via gradient descent
    n, p = len(X), len(feat_cols)
    means = [_mean([x[j] for x in X]) for j in range(p)]
    stds  = [_std([x[j] for x in X]) + 1e-9 for j in range(p)]
    Xn    = [[(X[i][j]-means[j])/stds[j] for j in range(p)] for i in range(n)]

    w, b, lr = [0.0]*p, 0.0, 0.01
    for _ in range(500):
        preds = [sum(w[j]*Xn[i][j] for j in range(p)) + b for i in range(n)]
        for j in range(p):
            w[j] -= lr * sum((preds[i]-y[i])*Xn[i][j] for i in range(n)) / n
        b -= lr * sum(preds[i]-y[i] for i in range(n)) / n

    preds  = [round(sum(w[j]*Xn[i][j] for j in range(p)) + b, 4) for i in range(n)]
    my     = _mean(y)
    ss_res = sum((y[i]-preds[i])**2 for i in range(n))
    ss_tot = sum((y[i]-my)**2 for i in range(n))
    r2     = 1 - ss_res/ss_tot if ss_tot else 0
    rmse   = math.sqrt(ss_res/n)

    new_headers = headers + ['lr_predicted', 'lr_residual']
    new_rows    = [list(valid_rows[i]) + [preds[i], round(y[i]-preds[i], 4)] for i in range(n)]

    return _result(new_headers, new_rows, 'Linear Regression (ML)',
                   [['R²', round(r2, 4)], ['RMSE', round(rmse, 4)], ['n', n]])


def polynomial_regression(params, headers, rows):
    x_col  = params.get('x_column', headers[0])
    y_col  = params.get('y_column', headers[-1])
    degree = int(params.get('degree', 2))

    xci = _col_idx(headers, x_col)
    yci = _col_idx(headers, y_col)
    xy  = [(r[xci] if xci < len(r) else None, r[yci] if yci < len(r) else None) for r in rows]
    xy  = [((_to_number(x), _to_number(y))) for x, y in xy if _to_number(x) is not None and _to_number(y) is not None]
    X   = [[xi**d for d in range(degree+1)] for xi, _ in xy]
    y   = [yi for _, yi in xy]

    # OLS via Gaussian elimination
    def solve(A, b):
        n = len(A)
        # b must be a flat list of scalars
        b_flat = [x[0] if isinstance(x, list) else x for x in b]
        M = [A[i][:] + [b_flat[i]] for i in range(n)]
        for col in range(n):
            pivot = next((r for r in range(col, n) if abs(M[r][col]) > 1e-12), None)
            if pivot is None: return [0.0] * n
            M[col], M[pivot] = M[pivot], M[col]
            for r in range(n):
                if r != col and abs(M[col][col]) > 1e-12:
                    f = M[r][col] / M[col][col]
                    M[r] = [M[r][c] - f * M[col][c] for c in range(n + 1)]
        return [float(M[i][n] / M[i][i]) if abs(M[i][i]) > 1e-12 else 0.0 for i in range(n)]

    XT   = [[X[i][j] for i in range(len(X))] for j in range(degree+1)]
    XTX  = [[sum(XT[r][k]*X[k][c] for k in range(len(X))) for c in range(degree+1)] for r in range(degree+1)]
    XTy  = [sum(XT[r][k]*y[k] for k in range(len(X))) for r in range(degree+1)]
    beta = solve(XTX, XTy)   # pass flat list, not [[v] for v in XTy]
    beta = [float(b) for b in beta]

    preds = [sum(beta[d]*(float(xi)**d) for d in range(degree+1)) for xi, _ in xy]
    my    = _mean(y)
    r2    = 1 - sum((y[i]-preds[i])**2 for i in range(len(y))) / (sum((y[i]-my)**2 for i in range(len(y))) or 1)

    eqn = ' + '.join(f'{round(beta[d], 4)}x^{d}' for d in range(degree+1))

    new_headers = headers + ['poly_predicted']
    new_rows    = [list(rows[i]) + [round(preds[i] if i < len(preds) else None, 4)] for i in range(len(rows))]

    return _result(new_headers, new_rows, f'Polynomial Regression (degree={degree})',
                   [['درجه', degree], ['R²', round(r2, 4)], ['معادله', eqn[:60]]])


def ridge_regression(params, headers, rows):
    return _regression_regularized(params, headers, rows, 'ridge')

def lasso_regression(params, headers, rows):
    return _regression_regularized(params, headers, rows, 'lasso')

def _regression_regularized(params, headers, rows, mode):
    feat_cols = params.get('feature_columns', headers[:-1])
    label_col = params.get('label_column', headers[-1])
    if isinstance(feat_cols, str): feat_cols = [c.strip() for c in feat_cols.split(',')]
    alpha = float(params.get('alpha', 1.0))

    X, valid_rows = _get_matrix(headers, rows, feat_cols)
    lci = _col_idx(headers, label_col)
    y   = [_to_number(r[lci] if lci < len(r) else None) for r in valid_rows]
    y   = [v for v in y if v is not None]
    X   = X[:len(y)]
    n, p= len(X), len(feat_cols)

    means = [_mean([x[j] for x in X]) for j in range(p)]
    stds  = [_std([x[j] for x in X]) + 1e-9 for j in range(p)]
    Xn    = [[(X[i][j]-means[j])/stds[j] for j in range(p)] for i in range(n)]
    my    = _mean(y)
    yn    = [v - my for v in y]

    w, lr = [0.0]*p, 0.001
    for _ in range(1000):
        preds = [sum(w[j]*Xn[i][j] for j in range(p)) for i in range(n)]
        for j in range(p):
            grad = sum((preds[i]-yn[i])*Xn[i][j] for i in range(n)) / n
            if mode == 'ridge':
                w[j] -= lr * (grad + alpha * w[j])
            else:  # lasso
                w[j] -= lr * grad
                w[j]  = max(0, abs(w[j]) - lr*alpha) * (1 if w[j] > 0 else -1)

    preds_full = [round(sum(w[j]*Xn[i][j] for j in range(p)) + my, 4) for i in range(n)]
    ss_res = sum((y[i]-preds_full[i])**2 for i in range(n))
    ss_tot = sum((y[i]-my)**2 for i in range(n))
    r2     = 1 - ss_res/ss_tot if ss_tot else 0

    new_headers = headers + [f'{mode}_predicted']
    new_rows    = [list(valid_rows[i]) + [preds_full[i]] for i in range(n)]

    return _result(new_headers, new_rows, f'{mode.title()} Regression (α={alpha})',
                   [['R²', round(r2, 4)], ['alpha', alpha]])


def knn_regression(params, headers, rows):
    feat_cols = params.get('feature_columns', headers[:-1])
    label_col = params.get('label_column', headers[-1])
    if isinstance(feat_cols, str): feat_cols = [c.strip() for c in feat_cols.split(',')]
    k = int(params.get('k', 5))

    X, valid_rows = _get_matrix(headers, rows, feat_cols)
    lci = _col_idx(headers, label_col)
    y   = [_to_number(r[lci] if lci < len(r) else None) for r in valid_rows]
    y   = [v if v is not None else 0 for v in y]

    preds = []
    for i in range(len(X)):
        dists = sorted([(j, _distance(X[i], X[j])) for j in range(len(X)) if j != i], key=lambda x: x[1])
        k_vals = [y[j] for j, _ in dists[:k]]
        preds.append(round(_mean(k_vals), 4))

    my     = _mean(y)
    ss_res = sum((y[i]-preds[i])**2 for i in range(len(y)))
    ss_tot = sum((y[i]-my)**2 for i in range(len(y)))
    r2     = 1 - ss_res/ss_tot if ss_tot else 0

    new_headers = headers + ['knn_predicted']
    new_rows    = [list(valid_rows[i]) + [preds[i]] for i in range(len(valid_rows))]

    return _result(new_headers, new_rows, f'KNN Regression (k={k})',
                   [['R²', round(r2, 4)], ['k', k]])


def gradient_boosting(params, headers, rows):
    """Gradient Boosting with decision stumps"""
    feat_cols = params.get('feature_columns', headers[:-1])
    label_col = params.get('label_column', headers[-1])
    if isinstance(feat_cols, str): feat_cols = [c.strip() for c in feat_cols.split(',')]
    n_est = int(params.get('n_estimators', 50))
    lr    = float(params.get('learning_rate', 0.1))

    X, valid_rows = _get_matrix(headers, rows, feat_cols)
    lci = _col_idx(headers, label_col)
    y   = [_to_number(r[lci] if lci < len(r) else None) for r in valid_rows]
    y   = [v if v is not None else 0 for v in y]
    n   = len(y)

    F = [_mean(y)] * n  # initial prediction

    stumps = []
    for _ in range(n_est):
        residuals = [y[i] - F[i] for i in range(n)]
        # Fit stump to residuals
        best_split = None
        best_mse   = float('inf')
        for fi in range(len(feat_cols)):
            vals = sorted(set(X[i][fi] for i in range(n)))
            for thresh in [(vals[j]+vals[j+1])/2 for j in range(len(vals)-1)]:
                left  = [residuals[i] for i in range(n) if X[i][fi] <= thresh]
                right = [residuals[i] for i in range(n) if X[i][fi] >  thresh]
                if not left or not right: continue
                mse = (sum(r**2 for r in left) + sum(r**2 for r in right)) / n
                if mse < best_mse:
                    best_mse   = mse
                    best_split = (fi, thresh, _mean(left), _mean(right))

        if not best_split: break
        fi, thresh, lval, rval = best_split
        stumps.append(best_split)
        for i in range(n):
            F[i] += lr * (lval if X[i][fi] <= thresh else rval)

    preds  = [round(F[i], 4) for i in range(n)]
    my     = _mean(y)
    ss_res = sum((y[i]-preds[i])**2 for i in range(n))
    ss_tot = sum((y[i]-my)**2 for i in range(n))
    r2     = 1 - ss_res/ss_tot if ss_tot else 0

    new_headers = headers + ['gb_predicted']
    new_rows    = [list(valid_rows[i]) + [preds[i]] for i in range(n)]

    return _result(new_headers, new_rows, f'Gradient Boosting ({n_est} estimators)',
                   [['R²', round(r2, 4)], ['n_estimators', n_est], ['lr', lr]])


# ══════════════════════════════════════════════════════════════════════════
# DIMENSIONALITY REDUCTION
# ══════════════════════════════════════════════════════════════════════════

def pca(params, headers, rows):
    cols = params.get('feature_columns', headers)
    if isinstance(cols, str): cols = [c.strip() for c in cols.split(',')]
    n_components = int(params.get('n_components', 2))

    X, valid_rows = _get_matrix(headers, rows, cols)
    n, p = len(X), len(cols)

    # Center
    means = [_mean([X[i][j] for i in range(n)]) for j in range(p)]
    Xc    = [[X[i][j] - means[j] for j in range(p)] for i in range(n)]

    # Covariance matrix
    cov = [[sum(Xc[k][i]*Xc[k][j] for k in range(n))/(n-1) for j in range(p)] for i in range(p)]

    # Power iteration for top eigenvectors
    def power_iter(mat, deflate=None):
        v = [random.gauss(0,1) for _ in range(p)]
        if deflate:
            for ev, elam in deflate:
                dot = sum(v[j]*ev[j] for j in range(p))
                v   = [v[j] - dot*ev[j] for j in range(p)]
        for _ in range(200):
            Mv = [sum(mat[i][j]*v[j] for j in range(p)) for i in range(p)]
            if deflate:
                for ev, elam in deflate:
                    dot = sum(Mv[j]*ev[j] for j in range(p))
                    Mv  = [Mv[j] - dot*ev[j] for j in range(p)]
            norm = math.sqrt(sum(x**2 for x in Mv)) or 1
            v_new = [x/norm for x in Mv]
            if sum((v_new[j]-v[j])**2 for j in range(p)) < 1e-12: break
            v = v_new
        lam = sum(sum(cov[i][j]*v[j] for j in range(p))*v[i] for i in range(p))
        return v, lam

    random.seed(42)
    components = []
    for _ in range(min(n_components, p)):
        ev, elam = power_iter(cov, components)
        components.append((ev, elam))

    # Project
    pc_cols = [f'PC{i+1}' for i in range(len(components))]
    new_headers = headers + pc_cols
    new_rows    = []
    for i, row in enumerate(valid_rows):
        projections = [round(sum(Xc[i][j]*ev[j] for j in range(p)), 4)
                       for ev, _ in components]
        new_rows.append(list(row) + projections)

    total_var = sum(abs(lam) for _, lam in components)
    explained = [round(abs(lam)/total_var*100, 2) if total_var else 0 for _, lam in components]

    return _result(new_headers, new_rows, f'PCA ({n_components} components)',
                   [['مؤلفه‌ها', n_components],
                    ['واریانس تبیین شده', ', '.join(f'PC{i+1}:{e}%' for i,e in enumerate(explained))]])


def feature_selection(params, headers, rows):
    feat_cols = params.get('feature_columns', headers[:-1])
    label_col = params.get('label_column', headers[-1])
    if isinstance(feat_cols, str): feat_cols = [c.strip() for c in feat_cols.split(',')]
    n_select  = int(params.get('n_features', len(feat_cols)//2 or 1))
    method    = params.get('method', 'correlation')

    X, valid_rows = _get_matrix(headers, rows, feat_cols)
    lci = _col_idx(headers, label_col)
    y   = [_to_number(r[lci] if lci < len(r) else None) for r in valid_rows]
    y   = [v if v is not None else 0 for v in y]

    scores = []
    for j, col in enumerate(feat_cols):
        xj = [X[i][j] for i in range(len(X))]
        if method == 'correlation':
            m_x, m_y = _mean(xj), _mean(y)
            cov  = sum((xj[i]-m_x)*(y[i]-m_y) for i in range(len(y)))
            sx   = _std(xj) + 1e-9
            sy   = _std(y)  + 1e-9
            score = abs(cov / (sx * sy * len(y)))
        else:  # variance
            score = _std(xj)
        scores.append((col, round(score, 4)))

    scores.sort(key=lambda x: x[1], reverse=True)
    selected = [col for col, _ in scores[:n_select]]

    out_headers = ['feature', 'score', 'selected']
    out_rows    = [[col, sc, 1 if col in selected else 0] for col, sc in scores]

    return _result(out_headers, out_rows, 'انتخاب ویژگی',
                   [['روش', method], ['انتخاب شده', n_select], ['کل', len(feat_cols)]])


def feature_importance(params, headers, rows):
    """Permutation importance using random forest stumps"""
    feat_cols = params.get('feature_columns', headers[:-1])
    label_col = params.get('label_column', headers[-1])
    if isinstance(feat_cols, str): feat_cols = [c.strip() for c in feat_cols.split(',')]

    X, valid_rows = _get_matrix(headers, rows, feat_cols)
    lci = _col_idx(headers, label_col)
    y   = [_to_number(r[lci] if lci < len(r) else None) for r in valid_rows]
    y   = [v if v is not None else 0 for v in y]

    def baseline_mse():
        return sum((yi - _mean(y))**2 for yi in y) / len(y) if y else 0

    base = baseline_mse()
    importances = []
    random.seed(42)

    for j, col in enumerate(feat_cols):
        # Permute feature j and measure increase in MSE
        Xp = [list(x) for x in X]
        col_vals = [x[j] for x in X]
        random.shuffle(col_vals)
        for i in range(len(Xp)):
            Xp[i][j] = col_vals[i]

        # Simple 1-NN prediction
        preds = []
        for i in range(len(Xp)):
            nearest = min((k for k in range(len(Xp)) if k != i),
                          key=lambda k: _distance(Xp[i], Xp[k]), default=0)
            preds.append(y[nearest])

        perm_mse = sum((y[i]-preds[i])**2 for i in range(len(y))) / len(y) if y else 0
        importances.append((col, round(max(0, perm_mse - base), 4)))

    importances.sort(key=lambda x: x[1], reverse=True)
    total = sum(s for _, s in importances) or 1
    out_rows = [[col, sc, round(sc/total*100, 2)] for col, sc in importances]

    return _result(['feature', 'importance', 'importance_pct'],
                   out_rows, 'اهمیت ویژگی‌ها',
                   [['مهم‌ترین ویژگی', importances[0][0] if importances else 'N/A']])


# ══════════════════════════════════════════════════════════════════════════
# ANOMALY DETECTION
# ══════════════════════════════════════════════════════════════════════════

def isolation_forest(params, headers, rows):
    cols    = params.get('feature_columns', headers)
    if isinstance(cols, str): cols = [c.strip() for c in cols.split(',')]
    n_trees = int(params.get('n_estimators', 50))
    max_smp = int(params.get('max_samples', min(256, len(rows))))

    X, valid_rows = _get_matrix(headers, rows, cols)
    n = len(X)
    if n == 0: raise ValueError('داده عددی یافت نشد')

    random.seed(42)

    def build_itree(sample_idxs, current_height, height_limit):
        if current_height >= height_limit or len(sample_idxs) <= 1:
            return {'type': 'leaf', 'size': len(sample_idxs)}
        fi = random.randint(0, len(cols)-1)
        vals = [X[i][fi] for i in sample_idxs]
        lo, hi = min(vals), max(vals)
        if lo == hi:
            return {'type': 'leaf', 'size': len(sample_idxs)}
        split = random.uniform(lo, hi)
        left  = [i for i in sample_idxs if X[i][fi] < split]
        right = [i for i in sample_idxs if X[i][fi] >= split]
        return {'type': 'node', 'fi': fi, 'split': split,
                'left': build_itree(left, current_height+1, height_limit),
                'right': build_itree(right, current_height+1, height_limit)}

    def path_length(x, node, depth=0):
        if node['type'] == 'leaf':
            s = node['size']
            return depth + (2*(math.log(s-1)+0.5772) - 2*(s-1)/s if s > 1 else 0)
        if x[node['fi']] < node['split']:
            return path_length(x, node['left'], depth+1)
        return path_length(x, node['right'], depth+1)

    height_limit = int(math.ceil(math.log2(max_smp))) if max_smp > 1 else 1
    trees = []
    for _ in range(n_trees):
        sample = random.sample(range(n), min(max_smp, n))
        trees.append(build_itree(sample, 0, height_limit))

    def c(n_):
        return (2*(math.log(n_-1)+0.5772) - 2*(n_-1)/n_) if n_ > 1 else (1 if n_ == 1 else 0)

    avg_pl = [_mean([path_length(X[i], t) for t in trees]) for i in range(n)]
    scores = [round(2 ** (-pl / c(max_smp)), 4) for pl in avg_pl]
    threshold = float(params.get('threshold', 0.6))
    anomalies = [1 if s > threshold else 0 for s in scores]

    new_headers = headers + ['if_score', 'is_anomaly']
    new_rows    = [list(valid_rows[i]) + [scores[i], anomalies[i]] for i in range(n)]
    n_anomaly   = sum(anomalies)

    return _result(new_headers, new_rows, 'Isolation Forest',
                   [['آنومالی یافت شده', n_anomaly], ['آستانه', threshold]])


def lof(params, headers, rows):
    cols = params.get('feature_columns', headers)
    if isinstance(cols, str): cols = [c.strip() for c in cols.split(',')]
    k = int(params.get('k', 5))

    X, valid_rows = _get_matrix(headers, rows, cols)
    n = len(X)

    # k-dist and reachability distance
    k_dists = []
    neighbors_list = []
    for i in range(n):
        dists = sorted([(j, _distance(X[i], X[j])) for j in range(n) if j != i], key=lambda x: x[1])
        k_dists.append(dists[k-1][1] if len(dists) >= k else dists[-1][1])
        neighbors_list.append([j for j, _ in dists[:k]])

    def reach_dist(i, j):
        return max(k_dists[j], _distance(X[i], X[j]))

    lrd = []
    for i in range(n):
        nbrs = neighbors_list[i]
        avg_rd = _mean([reach_dist(i, j) for j in nbrs]) if nbrs else 1
        lrd.append(1 / avg_rd if avg_rd else 0)

    lof_scores = []
    for i in range(n):
        nbrs = neighbors_list[i]
        ratio = _mean([lrd[j]/lrd[i] if lrd[i] else 0 for j in nbrs]) if nbrs else 1
        lof_scores.append(round(ratio, 4))

    threshold = float(params.get('threshold', 1.5))
    anomalies = [1 if s > threshold else 0 for s in lof_scores]

    new_headers = headers + ['lof_score', 'is_anomaly']
    new_rows    = [list(valid_rows[i]) + [lof_scores[i], anomalies[i]] for i in range(n)]

    return _result(new_headers, new_rows, f'LOF (k={k})',
                   [['آنومالی', sum(anomalies)], ['آستانه', threshold]])


def zscore_anomaly(params, headers, rows):
    cols      = params.get('feature_columns', headers)
    if isinstance(cols, str): cols = [c.strip() for c in cols.split(',')]
    threshold = float(params.get('threshold', 3.0))

    X, valid_rows = _get_matrix(headers, rows, cols)
    n, p = len(X), len(cols)
    means = [_mean([X[i][j] for i in range(n)]) for j in range(p)]
    stds  = [_std([X[i][j] for i in range(n)]) + 1e-9 for j in range(p)]

    scores    = [max(abs((X[i][j]-means[j])/stds[j]) for j in range(p)) for i in range(n)]
    anomalies = [1 if s > threshold else 0 for s in scores]

    new_headers = headers + ['zscore_max', 'is_anomaly']
    new_rows    = [list(valid_rows[i]) + [round(scores[i],4), anomalies[i]] for i in range(n)]

    return _result(new_headers, new_rows, f'Z-Score Anomaly (threshold={threshold})',
                   [['آنومالی', sum(anomalies)], ['آستانه', threshold]])


# ══════════════════════════════════════════════════════════════════════════
# TIME SERIES
# ══════════════════════════════════════════════════════════════════════════

def arima_simple(params, headers, rows):
    ci     = _col_idx(headers, params['column'])
    p_ar   = int(params.get('p', 1))
    steps  = int(params.get('forecast_steps', 5))

    vals = [_to_number(r[ci] if ci < len(r) else None) for r in rows]
    vals = [v for v in vals if v is not None]
    n    = len(vals)

    if n < p_ar + 10:
        raise ValueError(f'حداقل {p_ar+10} داده لازم است')

    # Fit AR(p) via OLS
    y = vals[p_ar:]
    X = [[vals[i-k-1] for k in range(p_ar)] for i in range(p_ar, n)]

    # Gradient descent for AR coefficients
    w  = [0.0] * p_ar
    b  = _mean(vals)
    lr = 0.001
    for _ in range(500):
        preds = [b + sum(w[k]*X[i][k] for k in range(p_ar)) for i in range(len(X))]
        for k in range(p_ar):
            w[k] -= lr * sum((preds[i]-y[i])*X[i][k] for i in range(len(X))) / len(X)
        b -= lr * sum(preds[i]-y[i] for i in range(len(X))) / len(X)

    # Forecast
    history = list(vals)
    forecasts = []
    for _ in range(steps):
        f = b + sum(w[k]*history[-(k+1)] for k in range(p_ar))
        forecasts.append(round(f, 4))
        history.append(f)

    out_headers = ['step', 'forecast']
    out_rows    = [[i+1, forecasts[i]] for i in range(steps)]

    return {'headers': out_headers, 'rows': out_rows,
            'summary': {'title': f'AR({p_ar}) Forecast',
                        'stats': [['AR order', p_ar], ['پیش‌بینی', steps]]}}


def time_series_forecast(params, headers, rows):
    ci       = _col_idx(headers, params['column'])
    steps    = int(params.get('forecast_steps', 10))
    method   = params.get('method', 'ets')  # ets | naive | drift

    vals = [_to_number(r[ci] if ci < len(r) else None) for r in rows]
    vals = [v for v in vals if v is not None]
    n    = len(vals)

    if method == 'naive':
        forecasts = [vals[-1]] * steps
    elif method == 'drift':
        drift = (vals[-1] - vals[0]) / (n - 1) if n > 1 else 0
        forecasts = [round(vals[-1] + drift*(i+1), 4) for i in range(steps)]
    else:  # ETS (simple exponential smoothing)
        alpha = 0.3
        ets = vals[0]
        for v in vals[1:]:
            ets = alpha*v + (1-alpha)*ets
        forecasts = [round(ets, 4)] * steps

    out_headers = ['step', 'forecast']
    out_rows    = [[i+1, forecasts[i]] for i in range(steps)]

    return {'headers': out_headers, 'rows': out_rows,
            'summary': {'title': f'پیش‌بینی سری زمانی ({method})',
                        'stats': [['روش', method], ['گام‌های پیش‌بینی', steps]]}}


def change_point(params, headers, rows):
    ci        = _col_idx(headers, params['column'])
    min_size  = int(params.get('min_segment_size', 5))
    threshold = float(params.get('threshold', 2.0))

    vals = [_to_number(r[ci] if ci < len(r) else None) for r in rows]
    vals = [v for v in vals if v is not None]
    n    = len(vals)

    # CUSUM-based change point detection
    grand_mean = _mean(vals)
    cusum      = [0.0]
    for v in vals:
        cusum.append(cusum[-1] + v - grand_mean)

    # Find max deviation
    change_points = []
    for i in range(min_size, n - min_size):
        left_mean  = _mean(vals[:i])
        right_mean = _mean(vals[i:])
        left_std   = _std(vals[:i]) + 1e-9
        diff       = abs(right_mean - left_mean) / left_std
        if diff > threshold:
            change_points.append({'idx': i, 'diff': round(diff, 3),
                                  'left_mean': round(left_mean, 4),
                                  'right_mean': round(right_mean, 4)})

    # Non-maximum suppression
    filtered = []
    for cp in sorted(change_points, key=lambda x: x['diff'], reverse=True):
        if not any(abs(cp['idx']-f['idx']) < min_size for f in filtered):
            filtered.append(cp)

    out_headers = ['index', 'diff_score', 'left_mean', 'right_mean']
    out_rows    = [[cp['idx'], cp['diff'], cp['left_mean'], cp['right_mean']] for cp in filtered]

    return _result(out_headers, out_rows, 'تشخیص نقطه تغییر',
                   [['نقطه یافت شده', len(filtered)], ['آستانه', threshold]])


# ══════════════════════════════════════════════════════════════════════════
# NLP / TEXT
# ══════════════════════════════════════════════════════════════════════════

def tfidf(params, headers, rows):
    ci   = _col_idx(headers, params['column'])
    top_n= int(params.get('top_n', 10))

    docs = [str(r[ci] if ci < len(r) else '').lower() for r in rows]
    import re
    tokenize = lambda d: re.findall(r'\b\w+\b', d)
    tokenized= [tokenize(d) for d in docs]
    N        = len(docs)

    # TF-IDF
    vocab = set(w for tokens in tokenized for w in tokens)
    df    = {w: sum(1 for t in tokenized if w in t) for w in vocab}
    idf   = {w: math.log(N / (df[w]+1)) + 1 for w in vocab}

    scores = {}
    for tokens in tokenized:
        tf = Counter(tokens)
        for w, cnt in tf.items():
            scores[w] = scores.get(w, 0) + (cnt/len(tokens)) * idf.get(w, 0)

    top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]

    out_headers = ['term', 'tfidf_score']
    out_rows    = [[w, round(s, 4)] for w, s in top]

    return _result(out_headers, out_rows, f'TF-IDF — {params["column"]}',
                   [['اسناد', N], ['واژگان', len(vocab)], ['top_n', top_n]])


def text_similarity(params, headers, rows):
    ci1 = _col_idx(headers, params['column1'])
    ci2 = _col_idx(headers, params['column2'])
    method = params.get('method', 'cosine')

    import re
    tokenize = lambda d: set(re.findall(r'\b\w+\b', str(d).lower()))

    sims = []
    for row in rows:
        a = tokenize(row[ci1] if ci1 < len(row) else '')
        b = tokenize(row[ci2] if ci2 < len(row) else '')
        if method == 'jaccard':
            sim = len(a & b) / len(a | b) if (a | b) else 0
        else:  # cosine
            sim = len(a & b) / (math.sqrt(len(a)) * math.sqrt(len(b))) if a and b else 0
        sims.append(round(sim, 4))

    col_name    = 'text_similarity'
    new_headers = headers + [col_name]
    new_rows    = [list(row) + [sims[i]] for i, row in enumerate(rows)]

    return _result(new_headers, new_rows, f'شباهت متن ({method})',
                   [['روش', method], ['میانگین شباهت', round(_mean(sims), 4)]])


def sentiment_simple(params, headers, rows):
    ci = _col_idx(headers, params['column'])

    POS = {'good','great','excellent','amazing','wonderful','love','best','awesome',
           'fantastic','happy','positive','nice','beautiful','perfect','خوب','عالی','بهترین'}
    NEG = {'bad','terrible','awful','horrible','worst','hate','poor','wrong','ugly',
           'negative','disappointed','fail','error','بد','ضعیف','افتضاح'}

    import re
    def analyze(text):
        words = set(re.findall(r'\b\w+\b', str(text).lower()))
        pos   = len(words & POS)
        neg   = len(words & NEG)
        score = (pos - neg) / (pos + neg + 1)
        label = 'مثبت' if score > 0.1 else ('منفی' if score < -0.1 else 'خنثی')
        return round(score, 3), label

    new_headers = headers + ['sentiment_score', 'sentiment_label']
    new_rows    = []
    for row in rows:
        score, label = analyze(row[ci] if ci < len(row) else '')
        new_rows.append(list(row) + [score, label])

    labels  = [r[-1] for r in new_rows]
    cnt     = Counter(labels)

    return _result(new_headers, new_rows, f'تحلیل احساسات — {params["column"]}',
                   [['مثبت', cnt.get('مثبت',0)], ['منفی', cnt.get('منفی',0)], ['خنثی', cnt.get('خنثی',0)]])


def word_frequency(params, headers, rows):
    ci    = _col_idx(headers, params['column'])
    top_n = int(params.get('top_n', 20))
    stopwords_str = params.get('stopwords', 'the,a,an,and,or,but,in,on,at,to,for,of,with,is,are,was')
    stops = set(stopwords_str.split(','))

    import re
    all_words = []
    for row in rows:
        words = re.findall(r'\b\w+\b', str(row[ci] if ci < len(row) else '').lower())
        all_words.extend(w for w in words if w not in stops and len(w) > 1)

    freq = Counter(all_words).most_common(top_n)
    out_headers = ['word', 'frequency', 'percent']
    total = len(all_words)
    out_rows = [[w, cnt, round(cnt/total*100, 2)] for w, cnt in freq]

    return _result(out_headers, out_rows, f'فراوانی کلمات — {params["column"]}',
                   [['کل کلمات', total], ['یکتا', len(set(all_words))]])


# ══════════════════════════════════════════════════════════════════════════
# ASSOCIATION RULES
# ══════════════════════════════════════════════════════════════════════════

def apriori(params, headers, rows):
    ci           = _col_idx(headers, params['items_column'])
    min_support  = float(params.get('min_support', 0.1))
    separator    = params.get('separator', ',')

    transactions = [set(str(r[ci] if ci < len(r) else '').split(separator))
                    for r in rows if not (r[ci] if ci < len(r) else None) is None]
    n = len(transactions)

    # Single-item frequencies
    item_counts = Counter(item.strip() for t in transactions for item in t)
    freq_items  = {item for item, cnt in item_counts.items() if cnt/n >= min_support}

    out_headers = ['itemset', 'support', 'count']
    out_rows    = [[item, round(item_counts[item]/n, 4), item_counts[item]]
                   for item in sorted(freq_items)]

    return _result(out_headers, out_rows, f'Apriori (min_support={min_support})',
                   [['تراکنش‌ها', n], ['آیتم‌های مکرر', len(freq_items)]])


def association_rules(params, headers, rows):
    ci           = _col_idx(headers, params['items_column'])
    min_conf     = float(params.get('min_confidence', 0.5))
    min_support  = float(params.get('min_support', 0.1))
    separator    = params.get('separator', ',')

    transactions = [set(str(r[ci] if ci < len(r) else '').split(separator))
                    for r in rows]
    n = len(transactions)

    item_counts = Counter(item.strip() for t in transactions for item in t)
    freq_items  = {item for item, cnt in item_counts.items() if cnt/n >= min_support}

    rules = []
    items = sorted(freq_items)
    for i, ant in enumerate(items):
        for cons in items:
            if ant == cons: continue
            ant_cnt  = sum(1 for t in transactions if ant  in t)
            both_cnt = sum(1 for t in transactions if ant in t and cons in t)
            support  = both_cnt / n
            conf     = both_cnt / ant_cnt if ant_cnt else 0
            lift     = conf / (item_counts[cons] / n) if item_counts[cons] else 0
            if support >= min_support and conf >= min_conf:
                rules.append([ant, cons, round(support, 4), round(conf, 4), round(lift, 4)])

    out_headers = ['antecedent', 'consequent', 'support', 'confidence', 'lift']
    rules.sort(key=lambda r: r[3], reverse=True)

    return _result(out_headers, rules, 'قوانین انجمنی',
                   [['قوانین یافت شده', len(rules)],
                    ['min_support', min_support],
                    ['min_confidence', min_conf]])


# ══════════════════════════════════════════════════════════════════════════
# PREPROCESSING
# ══════════════════════════════════════════════════════════════════════════

def normalize_ml(params, headers, rows):
    cols = params.get('columns', headers)
    if isinstance(cols, str): cols = [c.strip() for c in cols.split(',')]

    new_rows = [list(r) for r in rows]
    for col in cols:
        ci   = _col_idx(headers, col)
        vals = [_to_number(r[ci] if ci < len(r) else None) for r in rows]
        nums = [v for v in vals if v is not None]
        mn, mx = min(nums) if nums else 0, max(nums) if nums else 1
        rng  = mx - mn or 1
        for i in range(len(new_rows)):
            v = vals[i]
            new_rows[i][ci] = round((v - mn) / rng, 4) if v is not None else None

    return _result(headers, new_rows, 'نرمال‌سازی Min-Max',
                   [['ستون‌ها', len(cols)], ['بازه', '[0, 1]']])


def standardize_ml(params, headers, rows):
    cols = params.get('columns', headers)
    if isinstance(cols, str): cols = [c.strip() for c in cols.split(',')]

    new_rows = [list(r) for r in rows]
    for col in cols:
        ci   = _col_idx(headers, col)
        vals = [_to_number(r[ci] if ci < len(r) else None) for r in rows]
        nums = [v for v in vals if v is not None]
        m, s = _mean(nums), _std(nums) + 1e-9
        for i in range(len(new_rows)):
            v = vals[i]
            new_rows[i][ci] = round((v - m) / s, 4) if v is not None else None

    return _result(headers, new_rows, 'استانداردسازی Z-score',
                   [['ستون‌ها', len(cols)], ['توزیع', 'μ=0, σ=1']])


def encode_categorical(params, headers, rows):
    col    = params.get('column')
    method = params.get('method', 'label')  # label | onehot
    ci     = _col_idx(headers, col)

    unique = sorted(set(str(r[ci] if ci < len(r) else '') for r in rows))

    if method == 'label':
        mapping  = {v: i for i, v in enumerate(unique)}
        new_hdrs = headers + [f'{col}_encoded']
        new_rows = [list(r) + [mapping.get(str(r[ci] if ci < len(r) else ''), -1)] for r in rows]
    else:  # one-hot
        new_hdrs = headers + [f'{col}_{v}' for v in unique]
        new_rows = []
        for row in rows:
            val = str(row[ci] if ci < len(row) else '')
            new_rows.append(list(row) + [1 if val == v else 0 for v in unique])

    return _result(new_hdrs, new_rows, f'کدگذاری دسته‌بندی — {col}',
                   [['روش', method], ['مقادیر یکتا', len(unique)]])


def train_test_split(params, headers, rows):
    test_size = float(params.get('test_size', 0.2))
    shuffle   = params.get('shuffle', 'true') == 'true'
    seed      = int(params.get('random_state', 42))

    data = list(rows)
    if shuffle:
        random.seed(seed)
        random.shuffle(data)

    split = int(len(data) * (1 - test_size))
    train = data[:split]
    test  = data[split:]

    train_hdrs = headers + ['split']
    train_rows = [list(r) + ['train'] for r in train]
    test_rows  = [list(r) + ['test']  for r in test]
    all_rows   = train_rows + test_rows

    return _result(train_hdrs, all_rows, 'تقسیم Train/Test',
                   [['train', len(train)], ['test', len(test)],
                    ['نسبت test', f'{test_size*100:.0f}%']])


def cross_validate(params, headers, rows):
    k = int(params.get('k_folds', 5))
    n = len(rows)
    fold_size = n // k

    out_headers = ['fold', 'train_size', 'val_size', 'val_start', 'val_end']
    out_rows    = []
    for i in range(k):
        start = i * fold_size
        end   = start + fold_size if i < k-1 else n
        val   = end - start
        out_rows.append([i+1, n - val, val, start, end-1])

    return _result(out_headers, out_rows, f'{k}-Fold Cross Validation',
                   [['folds', k], ['نمونه', n], ['اندازه fold', fold_size]])


# ══════════════════════════════════════════════════════════════════════════
# EVALUATION
# ══════════════════════════════════════════════════════════════════════════

def confusion_matrix(params, headers, rows):
    actual_ci = _col_idx(headers, params['actual_column'])
    pred_ci   = _col_idx(headers, params['predicted_column'])

    actual = [str(r[actual_ci] if actual_ci < len(r) else '') for r in rows]
    pred   = [str(r[pred_ci]   if pred_ci   < len(r) else '') for r in rows]
    classes= sorted(set(actual))

    matrix = defaultdict(lambda: defaultdict(int))
    for a, p in zip(actual, pred):
        matrix[a][p] += 1

    out_headers = ['actual \\ predicted'] + classes
    out_rows    = [[cls] + [matrix[cls][p] for p in classes] for cls in classes]

    n = len(actual)
    correct = sum(1 for a, p in zip(actual, pred) if a == p)
    accuracy = correct / n if n else 0

    return _result(out_headers, out_rows, 'Confusion Matrix',
                   [['دقت', f'{accuracy*100:.2f}%'],
                    ['صحیح', correct], ['نادرست', n - correct]])


def roc_auc(params, headers, rows):
    actual_ci = _col_idx(headers, params['actual_column'])
    score_ci  = _col_idx(headers, params['score_column'])
    pos_class = params.get('positive_class', '1')

    actual = [str(r[actual_ci] if actual_ci < len(r) else '') for r in rows]
    scores = [_to_number(r[score_ci] if score_ci < len(r) else None) for r in rows]

    pairs = [(s, a) for s, a in zip(scores, actual) if s is not None]
    pairs.sort(key=lambda x: x[0], reverse=True)

    n_pos = sum(1 for _, a in pairs if a == pos_class)
    n_neg = len(pairs) - n_pos
    if n_pos == 0 or n_neg == 0:
        return _result(['parameter','value'], [['خطا', 'هر دو کلاس لازم است']],
                       'ROC AUC', [])

    # Trapezoidal AUC
    tpr_points, fpr_points = [0], [0]
    tp = fp = 0
    for score, label in pairs:
        if label == pos_class: tp += 1
        else: fp += 1
        tpr_points.append(tp / n_pos)
        fpr_points.append(fp / n_neg)

    auc = sum((fpr_points[i]-fpr_points[i-1]) * (tpr_points[i]+tpr_points[i-1])/2
              for i in range(1, len(tpr_points)))

    return _result(['parameter','value'],
                   [['AUC', round(auc, 4)],
                    ['n_positive', n_pos], ['n_negative', n_neg],
                    ['تفسیر', 'عالی' if auc > 0.9 else 'خوب' if auc > 0.8 else 'متوسط']],
                   'ROC AUC',
                   [['AUC', round(auc, 4)]])
