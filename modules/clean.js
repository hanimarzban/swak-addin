/**
 * SWAK — Data Cleaning Module
 * 24 tools — pure JS, runs in browser via Office.js
 *
 * Pattern: each tool reads from Excel, processes, writes back
 * Entry point: CleanModule.run(toolId, params)
 */

const CleanModule = {

  async run(toolId, params) {
    switch (toolId) {
      case 'remove-duplicates':     return this.removeDuplicates(params);
      case 'fill-missing':          return this.fillMissing(params);
      case 'remove-outliers':       return this.removeOutliers(params);
      case 'convert-type':          return this.convertType(params);
      case 'text-ops':              return this.textOps(params);
      case 'split-column':          return this.splitColumn(params);
      case 'merge-columns':         return this.mergeColumns(params);
      case 'handle-errors':         return this.handleErrors(params);
      case 'date-ops':              return this.dateOps(params);
      case 'normalize-text':        return this.normalizeText(params);
      case 'remove-empty-rows':     return this.removeEmptyRows(params);
      case 'remove-empty-cols':     return this.removeEmptyCols(params);
      case 'regex-replace':         return this.regexReplace(params);
      case 'validate-email':        return this.validateEmail(params);
      case 'validate-phone':        return this.validatePhone(params);
      case 'validate-url':          return this.validateUrl(params);
      case 'detect-encoding':       return this.detectEncoding(params);
      case 'date-standardize':      return this.dateStandardize(params);
      case 'currency-convert':      return this.currencyConvert(params);
      case 'unit-convert':          return this.unitConvert(params);
      case 'detect-dup-key':        return this.detectDupKey(params);
      case 'detect-constant':       return this.detectConstant(params);
      case 'invalid-values':        return this.invalidValues(params);
      case 'missing-strategy':      return this.missingStrategy(params);
      default:
        throw new Error(`ابزار ناشناخته: ${toolId}`);
    }
  },

  // ── 1. Remove Duplicates ───────────────────────────────────────────

  async removeDuplicates(params) {
    const { headers, rows } = await excel.readActiveSheet();
    const mode  = params.mode || 'all';   // 'all' | 'selected'
    const keep  = params.keep || 'first'; // 'first' | 'last'

    const keyCols = mode === 'all'
      ? headers.map((_, i) => i)
      : [excel.getColIndex(headers, params.column)];

    const seen   = new Map();
    const result = [];
    let dupCount = 0;

    const rowsToProcess = keep === 'last' ? [...rows].reverse() : rows;

    for (const row of rowsToProcess) {
      const key = keyCols.map(i => String(row[i] ?? '')).join('\x00');
      if (!seen.has(key)) {
        seen.set(key, true);
        result.push(row);
      } else {
        dupCount++;
      }
    }

    const finalRows = keep === 'last' ? result.reverse() : result;
    await excel.writeToActiveSheet({ headers, rows: finalRows });

    return {
      title: 'حذف تکراری‌ها',
      stats: [
        ['ردیف اصلی', rows.length],
        ['تکراری حذف شده', dupCount],
        ['ردیف باقیمانده', finalRows.length],
        ['% حذف شده', ((dupCount / rows.length) * 100).toFixed(1) + '%'],
      ],
      note: `Mode: ${mode} • Keep: ${keep}`,
    };
  },

  // ── 2. Fill Missing Values ─────────────────────────────────────────

  async fillMissing(params) {
    const { headers, rows } = await excel.readActiveSheet();
    const method = params.method || 'mean'; // mean|median|ffill|bfill|value|zero
    const targetCol = params.column ? excel.getColIndex(headers, params.column) : null;

    const colIndices = targetCol !== null
      ? [targetCol]
      : headers.map((_, i) => i);

    let filled = 0;
    const newRows = rows.map(r => [...r]);

    for (const ci of colIndices) {
      const vals = rows.map(r => r[ci]);
      const numericVals = vals.map(v => excel.toNumber(v)).filter(v => v !== null);

      let fillVal;
      if (method === 'mean')   fillVal = numericVals.length ? numericVals.reduce((a,b)=>a+b,0)/numericVals.length : 0;
      if (method === 'median') fillVal = this._median(numericVals);
      if (method === 'zero')   fillVal = 0;
      if (method === 'value')  fillVal = params.fill_value ?? 0;

      if (method === 'ffill') {
        let last = null;
        for (let i = 0; i < newRows.length; i++) {
          if (excel.isEmpty(newRows[i][ci])) {
            if (last !== null) { newRows[i][ci] = last; filled++; }
          } else {
            last = newRows[i][ci];
          }
        }
        continue;
      }

      if (method === 'bfill') {
        let next = null;
        for (let i = newRows.length - 1; i >= 0; i--) {
          if (excel.isEmpty(newRows[i][ci])) {
            if (next !== null) { newRows[i][ci] = next; filled++; }
          } else {
            next = newRows[i][ci];
          }
        }
        continue;
      }

      for (let i = 0; i < newRows.length; i++) {
        if (excel.isEmpty(newRows[i][ci])) {
          newRows[i][ci] = fillVal;
          filled++;
        }
      }
    }

    await excel.writeToActiveSheet({ headers, rows: newRows });
    return {
      title: 'پر کردن مقادیر خالی',
      stats: [
        ['سلول‌های پر شده', filled],
        ['روش', method],
        ['ستون‌های پردازش شده', colIndices.length],
      ],
    };
  },

  // ── 3. Remove Outliers ────────────────────────────────────────────

  async removeOutliers(params) {
    const { headers, rows } = await excel.readActiveSheet();
    const ci        = excel.getColIndex(headers, params.column);
    const method    = params.method || 'iqr';
    const threshold = parseFloat(params.threshold) || 1.5;

    const nums = rows.map((r, i) => ({ val: excel.toNumber(r[ci]), idx: i }))
                     .filter(x => x.val !== null);

    let lower, upper;

    if (method === 'iqr') {
      const sorted = nums.map(x=>x.val).sort((a,b)=>a-b);
      const q1 = this._percentile(sorted, 25);
      const q3 = this._percentile(sorted, 75);
      const iqr = q3 - q1;
      lower = q1 - threshold * iqr;
      upper = q3 + threshold * iqr;
    } else if (method === 'zscore' || method === 'modified') {
      const vals = nums.map(x=>x.val);
      const mean = vals.reduce((a,b)=>a+b,0)/vals.length;
      const std  = Math.sqrt(vals.reduce((s,v)=>s+(v-mean)**2,0)/vals.length);
      lower = mean - threshold * std;
      upper = mean + threshold * std;
    }

    const outlierIndices = new Set(
      nums.filter(x => x.val < lower || x.val > upper).map(x => x.idx)
    );

    const newRows = rows.filter((_, i) => !outlierIndices.has(i));
    await excel.writeToActiveSheet({ headers, rows: newRows });

    return {
      title: `حذف مقادیر پرت — ${params.column}`,
      stats: [
        ['روش', method],
        ['کران پایین', lower.toFixed(2)],
        ['کران بالا',  upper.toFixed(2)],
        ['پرت حذف شده', outlierIndices.size],
        ['ردیف باقیمانده', newRows.length],
      ],
    };
  },

  // ── 4. Convert Data Types ─────────────────────────────────────────

  async convertType(params) {
    const { headers, rows } = await excel.readActiveSheet();
    const ci   = excel.getColIndex(headers, params.column);
    const type = params.target_type || 'number';

    let converted = 0, failed = 0;
    const newRows = rows.map(r => {
      const row = [...r];
      const val = row[ci];
      try {
        if (type === 'number') {
          const n = Number(String(val).replace(/[,،]/g, ''));
          row[ci] = isNaN(n) ? null : n;
          isNaN(n) ? failed++ : converted++;
        } else if (type === 'text') {
          row[ci] = val === null || val === undefined ? '' : String(val);
          converted++;
        } else if (type === 'date') {
          const d = new Date(val);
          row[ci] = isNaN(d.getTime()) ? null : d.toISOString().split('T')[0];
          isNaN(d.getTime()) ? failed++ : converted++;
        } else if (type === 'boolean') {
          const s = String(val).toLowerCase().trim();
          row[ci] = ['true','1','yes','بله','صحیح'].includes(s) ? true : false;
          converted++;
        } else if (type === 'currency') {
          const n = Number(String(val).replace(/[^0-9.-]/g, ''));
          row[ci] = isNaN(n) ? null : n;
          isNaN(n) ? failed++ : converted++;
        }
      } catch (_) { failed++; }
      return row;
    });

    await excel.writeToActiveSheet({ headers, rows: newRows });
    return {
      title: `تبدیل نوع — ${params.column}`,
      stats: [
        ['ستون', params.column],
        ['نوع هدف', type],
        ['موفق', converted],
        ['ناموفق (null)', failed],
      ],
    };
  },

  // ── 5. Text Operations ────────────────────────────────────────────

  async textOps(params) {
    const { headers, rows } = await excel.readActiveSheet();
    const ci  = excel.getColIndex(headers, params.column);
    const op  = params.operation || 'trim';

    const ops = {
      trim:           v => String(v).trim(),
      uppercase:      v => String(v).toUpperCase(),
      lowercase:      v => String(v).toLowerCase(),
      title_case:     v => String(v).replace(/\b\w/g, c => c.toUpperCase()),
      remove_special: v => String(v).replace(/[^a-zA-Z0-9\u0600-\u06FF\s]/g, ''),
      remove_numbers: v => String(v).replace(/[0-9۰-۹٠-٩]/g, ''),
      remove_spaces:  v => String(v).replace(/\s+/g, ''),
      extract_numbers:v => (String(v).match(/[0-9۰-۹٠-٩.,-]+/g) || []).join(' '),
    };

    const fn = ops[op];
    if (!fn) throw new Error(`عملیات ناشناخته: ${op}`);

    let changed = 0;
    const newRows = rows.map(r => {
      const row = [...r];
      if (!excel.isEmpty(row[ci])) {
        const orig = row[ci];
        row[ci] = fn(row[ci]);
        if (row[ci] !== String(orig)) changed++;
      }
      return row;
    });

    await excel.writeToActiveSheet({ headers, rows: newRows });
    return {
      title: `عملیات متنی — ${params.column}`,
      stats: [
        ['عملیات', op],
        ['ردیف پردازش شده', rows.length],
        ['تغییر یافته', changed],
        ['بدون تغییر', rows.length - changed],
      ],
    };
  },

  // ── 6. Split Column ───────────────────────────────────────────────

  async splitColumn(params) {
    const { headers, rows } = await excel.readActiveSheet();
    const ci        = excel.getColIndex(headers, params.column);
    const delimiter = params.delimiter || ',';
    const maxSplits = parseInt(params.max_splits) || 2;

    // Build new headers
    const newHeaders = [...headers];
    for (let i = 1; i <= maxSplits; i++) {
      newHeaders.push(`${params.column}_${i}`);
    }

    const newRows = rows.map(r => {
      const row = [...r];
      const parts = String(row[ci] ?? '').split(delimiter);
      for (let i = 0; i < maxSplits; i++) {
        row.push(parts[i]?.trim() ?? '');
      }
      return row;
    });

    await excel.writeToActiveSheet({ headers: newHeaders, rows: newRows });
    return {
      title: `جدا کردن ستون — ${params.column}`,
      stats: [
        ['جداکننده', delimiter],
        ['ستون جدید', maxSplits],
        ['ردیف پردازش شده', rows.length],
      ],
    };
  },

  // ── 7. Merge Columns ──────────────────────────────────────────────

  async mergeColumns(params) {
    const { headers, rows } = await excel.readActiveSheet();
    const ci1  = excel.getColIndex(headers, params.col1);
    const ci2  = excel.getColIndex(headers, params.col2);
    const sep  = params.separator ?? ' ';
    const name = params.new_name || 'merged';

    const newHeaders = [...headers, name];
    const newRows = rows.map(r => {
      const row = [...r];
      row.push(`${r[ci1] ?? ''}${sep}${r[ci2] ?? ''}`);
      return row;
    });

    await excel.writeToActiveSheet({ headers: newHeaders, rows: newRows });
    return {
      title: 'ادغام ستون‌ها',
      stats: [
        ['ستون ۱', params.col1],
        ['ستون ۲', params.col2],
        ['جداکننده', `"${sep}"`],
        ['ستون جدید', name],
        ['ردیف پردازش شده', rows.length],
      ],
    };
  },

  // ── 8. Handle Errors ──────────────────────────────────────────────

  async handleErrors(params) {
    const { headers, rows } = await excel.readActiveSheet();
    const strategy = params.strategy || 'fill_default';
    const targetCi = params.column ? excel.getColIndex(headers, params.column) : null;

    const ERROR_VALS = ['#DIV/0!','#N/A','#NAME?','#NULL!','#NUM!','#REF!','#VALUE!','#ERROR!'];
    const isError = v => ERROR_VALS.includes(String(v ?? '').toUpperCase().trim());

    let fixed = 0;
    let newHeaders = [...headers];
    let newRows    = rows.map(r => [...r]);

    if (strategy === 'flag_column') {
      newHeaders.push('_has_error');
    }

    for (let i = 0; i < newRows.length; i++) {
      const row     = newRows[i];
      const cols    = targetCi !== null ? [targetCi] : row.map((_, ci) => ci);
      const hasErr  = cols.some(ci => isError(row[ci]));

      for (const ci of cols) {
        if (!isError(row[ci])) continue;
        fixed++;
        if (strategy === 'fill_default')  row[ci] = 0;
        if (strategy === 'flag_column')   row[ci] = null;
        if (strategy === 'drop_rows')     row[ci] = null; // mark, delete below
        if (strategy === 'isolate')       row[ci] = null;
      }

      if (strategy === 'flag_column') row.push(hasErr ? 1 : 0);
    }

    if (strategy === 'drop_rows') {
      newRows = newRows.filter(r => {
        const cols = targetCi !== null ? [targetCi] : r.map((_, ci) => ci);
        return !cols.some(ci => r[ci] === null);
      });
    }

    await excel.writeToActiveSheet({ headers: newHeaders, rows: newRows });
    return {
      title: 'مدیریت خطا',
      stats: [
        ['استراتژی', strategy],
        ['خطا یافت شده', fixed],
        ['ردیف نهایی', newRows.length],
      ],
    };
  },

  // ── 9. Date Operations ────────────────────────────────────────────

  async dateOps(params) {
    const { headers, rows } = await excel.readActiveSheet();
    const ci  = excel.getColIndex(headers, params.column);
    const op  = params.operation || 'extract_year';

    const newColName = op.replace('extract_', '').replace('_', ' ');
    const newHeaders = [...headers, newColName];

    const newRows = rows.map(r => {
      const row  = [...r];
      const date = new Date(r[ci]);
      let extracted = '';
      if (!isNaN(date.getTime())) {
        if (op === 'extract_year')    extracted = date.getFullYear();
        if (op === 'extract_month')   extracted = date.getMonth() + 1;
        if (op === 'extract_day')     extracted = date.getDate();
        if (op === 'extract_weekday') extracted = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][date.getDay()];
        if (op === 'add_days') {
          const d2 = new Date(date);
          d2.setDate(d2.getDate() + (parseInt(params.days) || 0));
          extracted = d2.toISOString().split('T')[0];
        }
        if (op === 'format') extracted = date.toISOString().split('T')[0];
      }
      row.push(extracted);
      return row;
    });

    await excel.writeToActiveSheet({ headers: newHeaders, rows: newRows });
    return {
      title: `عملیات تاریخ — ${params.column}`,
      stats: [
        ['عملیات', op],
        ['ستون جدید', newColName],
        ['ردیف پردازش شده', rows.length],
      ],
    };
  },

  // ── 10. Normalize Text ────────────────────────────────────────────

  async normalizeText(params) {
    const { headers, rows } = await excel.readActiveSheet();
    const ci  = excel.getColIndex(headers, params.column);
    const ops = params.operations || 'nfkc';

    let changed = 0;
    const newRows = rows.map(r => {
      const row = [...r];
      if (excel.isEmpty(row[ci])) return row;
      let v = String(row[ci]);
      const orig = v;
      if (ops.includes('nfkc') || ops === 'all') v = v.normalize('NFKC');
      else if (ops === 'nfc')  v = v.normalize('NFC');
      else if (ops === 'nfd')  v = v.normalize('NFD');
      if (ops === 'remove_accents' || ops === 'all')
        v = v.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
      if (ops === 'lowercase' || ops === 'all') v = v.toLowerCase();
      if (v !== orig) changed++;
      row[ci] = v;
      return row;
    });

    await excel.writeToActiveSheet({ headers, rows: newRows });
    return {
      title: `یکنواخت‌سازی متن — ${params.column}`,
      stats: [['عملیات', ops], ['تغییر یافته', changed]],
    };
  },

  // ── 11. Remove Empty Rows ─────────────────────────────────────────

  async removeEmptyRows(params) {
    const { headers, rows } = await excel.readActiveSheet();
    const threshold  = parseFloat(params.threshold) || 100;
    const wsEmpty    = (params.consider_whitespace !== 'false');

    const isEmpty = v => wsEmpty
      ? (v === null || v === undefined || String(v).trim() === '')
      : excel.isEmpty(v);

    const newRows = rows.filter(r => {
      const empties = r.filter(v => isEmpty(v)).length;
      const pct = (empties / r.length) * 100;
      return pct < threshold;
    });

    await excel.writeToActiveSheet({ headers, rows: newRows });
    return {
      title: 'حذف ردیف‌های خالی',
      stats: [
        ['آستانه', threshold + '%'],
        ['ردیف حذف شده', rows.length - newRows.length],
        ['ردیف باقیمانده', newRows.length],
      ],
    };
  },

  // ── 12. Remove Empty Cols ─────────────────────────────────────────

  async removeEmptyCols(params) {
    const { headers, rows } = await excel.readActiveSheet();
    const threshold = parseFloat(params.threshold) || 100;
    const wsEmpty   = (params.consider_whitespace !== 'false');

    const isEmpty = v => wsEmpty
      ? (v === null || v === undefined || String(v).trim() === '')
      : excel.isEmpty(v);

    const keepCols = headers.map((_, ci) => {
      const empties = rows.filter(r => isEmpty(r[ci])).length;
      const pct = rows.length > 0 ? (empties / rows.length) * 100 : 100;
      return pct < threshold;
    });

    const newHeaders = headers.filter((_, i) => keepCols[i]);
    const newRows    = rows.map(r => r.filter((_, i) => keepCols[i]));

    await excel.writeToActiveSheet({ headers: newHeaders, rows: newRows });
    return {
      title: 'حذف ستون‌های خالی',
      stats: [
        ['آستانه', threshold + '%'],
        ['ستون حذف شده', headers.length - newHeaders.length],
        ['ستون باقیمانده', newHeaders.length],
      ],
    };
  },

  // ── 13. Regex Replace ─────────────────────────────────────────────

  async regexReplace(params) {
    const { headers, rows } = await excel.readActiveSheet();
    const ci          = excel.getColIndex(headers, params.column);
    const pattern     = params.pattern;
    const replacement = params.replacement ?? '';
    const flags       = params.flags === 'case_insensitive' ? 'gi'
                      : params.flags === 'multiline'        ? 'gm'
                      : params.flags === 'dotall'           ? 'gs'
                      : 'g';

    if (!pattern) throw new Error('الگوی Regex الزامی است');
    const re = new RegExp(pattern, flags);

    let changed = 0;
    const newRows = rows.map(r => {
      const row = [...r];
      if (!excel.isEmpty(row[ci])) {
        const orig = String(row[ci]);
        row[ci] = orig.replace(re, replacement);
        if (row[ci] !== orig) changed++;
      }
      return row;
    });

    await excel.writeToActiveSheet({ headers, rows: newRows });
    return {
      title: `Regex Replace — ${params.column}`,
      stats: [
        ['الگو', pattern],
        ['جایگزین', `"${replacement}"`],
        ['ردیف تغییر یافته', changed],
      ],
    };
  },

  // ── 14. Email Validation ──────────────────────────────────────────

  async validateEmail(params) {
    const { headers, rows } = await excel.readActiveSheet();
    const ci     = excel.getColIndex(headers, params.column);
    const action = params.action || 'flag_invalid';
    const RE     = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

    let invalid = 0;
    let newHeaders = [...headers];
    let newRows    = rows.map(r => [...r]);

    if (action === 'flag_invalid') newHeaders.push('email_valid');

    for (let i = 0; i < newRows.length; i++) {
      const val   = String(newRows[i][ci] ?? '');
      const valid = RE.test(val.trim());
      if (!valid) invalid++;

      if (action === 'flag_invalid')  newRows[i].push(valid ? 1 : 0);
      if (action === 'remove_invalid' && !valid) newRows[i][ci] = null;
    }

    if (action === 'extract_valid') {
      newRows = newRows.filter((r, i) => RE.test(String(rows[i][ci] ?? '').trim()));
    }

    await excel.writeToActiveSheet({ headers: newHeaders, rows: newRows });
    return {
      title: `اعتبارسنجی ایمیل — ${params.column}`,
      stats: [
        ['کل', rows.length],
        ['معتبر', rows.length - invalid],
        ['نامعتبر', invalid],
        ['عملیات', action],
      ],
    };
  },

  // ── 15. Phone Validation ──────────────────────────────────────────

  async validatePhone(params) {
    const { headers, rows } = await excel.readActiveSheet();
    const ci     = excel.getColIndex(headers, params.column);
    const action = params.action || 'flag_invalid';

    const PATTERNS = {
      IR: /^(\+98|0098|0)?9[0-9]{9}$/,
      US: /^(\+1)?[2-9]\d{2}[2-9]\d{6}$/,
      DE: /^(\+49)?[1-9]\d{9,11}$/,
      FR: /^(\+33|0)[1-9]\d{8}$/,
      GB: /^(\+44|0)[1-9]\d{9}$/,
      CN: /^(\+86)?1[3-9]\d{9}$/,
      auto: /^[\+\d\s\-\(\)]{7,20}$/,
    };

    const region = params.region || 'auto';
    const RE     = PATTERNS[region] || PATTERNS.auto;

    let invalid = 0;
    let newHeaders = [...headers];
    let newRows    = rows.map(r => [...r]);

    if (action === 'flag_invalid') newHeaders.push('phone_valid');

    for (let i = 0; i < newRows.length; i++) {
      const raw   = String(newRows[i][ci] ?? '').replace(/\s/g, '');
      const valid = RE.test(raw);
      if (!valid) invalid++;

      if (action === 'flag_invalid')  newRows[i].push(valid ? 1 : 0);
      if (action === 'remove_invalid' && !valid) newRows[i][ci] = null;
      if (action === 'normalize' && valid) {
        newRows[i][ci] = raw.replace(/[^\d+]/g, '');
      }
    }

    await excel.writeToActiveSheet({ headers: newHeaders, rows: newRows });
    return {
      title: `اعتبارسنجی تلفن — ${params.column}`,
      stats: [['کل', rows.length], ['معتبر', rows.length - invalid], ['نامعتبر', invalid]],
    };
  },

  // ── 16. URL Validation ────────────────────────────────────────────

  async validateUrl(params) {
    const { headers, rows } = await excel.readActiveSheet();
    const ci          = excel.getColIndex(headers, params.column);
    const action      = params.action || 'flag_invalid';
    const checkScheme = params.check_scheme !== 'false';

    const isValidUrl = v => {
      try {
        const url = new URL(String(v).trim());
        return !checkScheme || ['http:', 'https:'].includes(url.protocol);
      } catch (_) { return false; }
    };

    let invalid = 0;
    let newHeaders = [...headers];
    let newRows    = rows.map(r => [...r]);
    if (action === 'flag_invalid') newHeaders.push('url_valid');

    for (let i = 0; i < newRows.length; i++) {
      const valid = isValidUrl(newRows[i][ci]);
      if (!valid) invalid++;
      if (action === 'flag_invalid')  newRows[i].push(valid ? 1 : 0);
      if (action === 'remove_invalid' && !valid) newRows[i][ci] = null;
    }

    await excel.writeToActiveSheet({ headers: newHeaders, rows: newRows });
    return {
      title: `اعتبارسنجی URL — ${params.column}`,
      stats: [['کل', rows.length], ['معتبر', rows.length - invalid], ['نامعتبر', invalid]],
    };
  },

  // ── 17. Detect Encoding ───────────────────────────────────────────

  async detectEncoding(params) {
    const { headers, rows } = await excel.readActiveSheet();
    // In browser JS, strings are always UTF-16 internally.
    // We detect if values have replacement chars or mojibake patterns.
    const ci = params.column ? excel.getColIndex(headers, params.column) : null;
    const cols = ci !== null ? [ci] : headers.map((_, i) => i);

    const MOJIBAKE = /[\uFFFD\u00C3\u00C2\u00E2\u0080]/;
    let issues = 0;
    const newRows = rows.map(r => [...r]);

    for (const col of cols) {
      for (let i = 0; i < newRows.length; i++) {
        const v = String(newRows[i][col] ?? '');
        if (MOJIBAKE.test(v)) {
          issues++;
          if (params.fix_encoding === 'true') {
            // Best effort: replace replacement chars
            newRows[i][col] = v.replace(/\uFFFD/g, '?');
          }
        }
      }
    }

    if (params.fix_encoding === 'true') {
      await excel.writeToActiveSheet({ headers, rows: newRows });
    }

    return {
      title: 'تشخیص کدگذاری',
      stats: [
        ['رشته‌های مشکوک', issues],
        ['تصحیح خودکار', params.fix_encoding === 'true' ? 'بله' : 'خیر'],
        ['کدگذاری داخلی', 'UTF-16 (JS)'],
      ],
      note: 'Excel Add-in: strings always stored as Unicode internally',
    };
  },

  // ── 18. Date Standardize ──────────────────────────────────────────

  async dateStandardize(params) {
    const { headers, rows } = await excel.readActiveSheet();
    const ci     = excel.getColIndex(headers, params.column);
    const fmt    = params.output_format || 'ISO8601';
    const onErr  = params.handle_errors || 'null';

    const formatDate = (d) => {
      if (fmt === 'ISO8601' || fmt === '%Y-%m-%d') return d.toISOString().split('T')[0];
      if (fmt === '%d/%m/%Y') return `${pad(d.getDate())}/${pad(d.getMonth()+1)}/${d.getFullYear()}`;
      if (fmt === '%m/%d/%Y') return `${pad(d.getMonth()+1)}/${pad(d.getDate())}/${d.getFullYear()}`;
      if (fmt === '%Y/%m/%d') return `${d.getFullYear()}/${pad(d.getMonth()+1)}/${pad(d.getDate())}`;
      if (fmt === 'unix')     return Math.floor(d.getTime() / 1000);
      return d.toISOString().split('T')[0];
    };
    const pad = n => String(n).padStart(2, '0');

    let converted = 0, errors = 0;
    const newRows = rows.map(r => {
      const row = [...r];
      const d   = new Date(row[ci]);
      if (isNaN(d.getTime())) {
        errors++;
        if (onErr === 'null')     row[ci] = null;
        if (onErr === 'original') { /* keep */ }
        if (onErr === 'error')    row[ci] = '#DATE_ERROR';
      } else {
        row[ci] = formatDate(d);
        converted++;
      }
      return row;
    });

    await excel.writeToActiveSheet({ headers, rows: newRows });
    return {
      title: `استانداردسازی تاریخ — ${params.column}`,
      stats: [['فرمت', fmt], ['تبدیل موفق', converted], ['خطا', errors]],
    };
  },

  // ── 19. Currency Convert ──────────────────────────────────────────

  async currencyConvert(params) {
    const { headers, rows } = await excel.readActiveSheet();
    const ci   = excel.getColIndex(headers, params.column);
    const from = params.from_currency || 'USD';
    const to   = params.to_currency   || 'EUR';

    let rate = 1;
    if (params.rate_source === 'live') {
      try {
        // ── Claude API Placeholder (currency rates) ──
        // Replace with actual FX API when ready
        // e.g. https://api.exchangerate-api.com/v4/latest/${from}
        const res  = await fetch(`https://api.exchangerate-api.com/v4/latest/${from}`);
        const data = await res.json();
        rate = data.rates[to] || 1;
      } catch (_) {
        // fallback static rates (approximate)
        const USD_RATES = { EUR:0.92, GBP:0.79, JPY:149.5, CNY:7.24, CAD:1.36, AUD:1.53, IRR:42000, USD:1 };
        const FROM_USD  = { EUR:1.09, GBP:1.27, JPY:0.0067, CNY:0.138, CAD:0.74, AUD:0.65, IRR:0.000024, USD:1 };
        rate = (FROM_USD[from] || 1) * (USD_RATES[to] || 1);
      }
    } else {
      rate = parseFloat(params.manual_rate) || 1;
    }

    const newHeaders = [...headers, `${params.column}_${to}`];
    const newRows = rows.map(r => {
      const row = [...r];
      const n   = excel.toNumber(r[ci]);
      row.push(n !== null ? parseFloat((n * rate).toFixed(4)) : null);
      return row;
    });

    await excel.writeToActiveSheet({ headers: newHeaders, rows: newRows });
    return {
      title: `تبدیل ارز — ${from} → ${to}`,
      stats: [['نرخ', rate.toFixed(6)], ['ستون جدید', `${params.column}_${to}`], ['ردیف', rows.length]],
    };
  },

  // ── 20. Unit Convert ──────────────────────────────────────────────

  async unitConvert(params) {
    const { headers, rows } = await excel.readActiveSheet();
    const ci   = excel.getColIndex(headers, params.column);
    const cat  = params.category || 'length';
    const from = params.from_unit || 'm';
    const to   = params.to_unit   || 'ft';

    // Conversion tables (value in SI base unit)
    const UNITS = {
      length:      { m:1, km:1000, cm:0.01, mm:0.001, ft:0.3048, in:0.0254, yd:0.9144, mi:1609.344 },
      mass:        { kg:1, g:0.001, mg:0.000001, lb:0.453592, oz:0.028349, t:1000 },
      temperature: null, // special case
      area:        { m2:1, km2:1e6, cm2:0.0001, ft2:0.092903, in2:0.000645, acre:4046.86, ha:10000 },
      volume:      { m3:1, l:0.001, ml:0.000001, gal:0.003785, fl_oz:0.0000295, cup:0.000237 },
      speed:       { ms:1, kmh:0.27778, mph:0.44704, knot:0.51444 },
      pressure:    { pa:1, kpa:1000, mpa:1e6, bar:100000, psi:6894.76, atm:101325 },
    };

    const convert = (val) => {
      if (cat === 'temperature') {
        if (from === 'C' && to === 'F') return val * 9/5 + 32;
        if (from === 'F' && to === 'C') return (val - 32) * 5/9;
        if (from === 'C' && to === 'K') return val + 273.15;
        if (from === 'K' && to === 'C') return val - 273.15;
        return val;
      }
      const table = UNITS[cat];
      if (!table) return val;
      const toSI = table[from] || 1;
      const fromSI = table[to]  || 1;
      return val * toSI / fromSI;
    };

    const newHeaders = [...headers, `${params.column}_${to}`];
    const newRows = rows.map(r => {
      const row = [...r];
      const n   = excel.toNumber(r[ci]);
      row.push(n !== null ? parseFloat(convert(n).toFixed(6)) : null);
      return row;
    });

    await excel.writeToActiveSheet({ headers: newHeaders, rows: newRows });
    return {
      title: `تبدیل واحد — ${from} → ${to}`,
      stats: [['دسته', cat], ['مبدأ', from], ['مقصد', to], ['ردیف', rows.length]],
    };
  },

  // ── 21. Detect Duplicate Key ──────────────────────────────────────

  async detectDupKey(params) {
    const { headers, rows } = await excel.readActiveSheet();
    const ci     = excel.getColIndex(headers, params.key_columns);
    const action = params.action || 'report';

    const seen    = new Map();
    const dupIdxs = [];

    rows.forEach((r, i) => {
      const key = String(r[ci] ?? '');
      if (seen.has(key)) dupIdxs.push(i);
      else seen.set(key, i);
    });

    let newHeaders = [...headers];
    let newRows    = rows.map(r => [...r]);

    if (action === 'flag') {
      newHeaders.push('is_duplicate_key');
      const dupSet = new Set(dupIdxs);
      newRows = newRows.map((r, i) => { r.push(dupSet.has(i) ? 1 : 0); return r; });
    } else if (action === 'remove_all') {
      const dupKeys = new Set(dupIdxs.map(i => String(rows[i][ci] ?? '')));
      const firstIdxs = new Set([...seen.values()].filter(i => !dupKeys.has(String(rows[i][ci]??''))));
      newRows = newRows.filter((_, i) => !dupKeys.has(String(rows[i][ci]??'')));
    } else if (action === 'keep_first') {
      const dupSet = new Set(dupIdxs);
      newRows = newRows.filter((_, i) => !dupSet.has(i));
    } else if (action === 'keep_last') {
      const keep = new Set(Object.values(Object.fromEntries([...seen.entries()].map(([k,v])=>[k,v]))));
      newRows = newRows.filter((_, i) => keep.has(i) || !dupIdxs.includes(i) === false);
    }

    if (action !== 'report') {
      await excel.writeToActiveSheet({ headers: newHeaders, rows: newRows });
    }

    return {
      title: `تشخیص کلید تکراری — ${params.key_columns}`,
      stats: [
        ['کل ردیف', rows.length],
        ['کلید تکراری', dupIdxs.length],
        ['کلید یکتا', seen.size],
        ['عملیات', action],
      ],
    };
  },

  // ── 22. Detect Constant Column ────────────────────────────────────

  async detectConstant(params) {
    const { headers, rows } = await excel.readActiveSheet();
    const threshold = parseInt(params.threshold) || 1; // unique value count ≤ this = constant

    const constantCols = [];
    headers.forEach((h, ci) => {
      const unique = new Set(rows.map(r => String(r[ci] ?? '')));
      if (unique.size <= threshold) constantCols.push({ col: h, uniqueCount: unique.size });
    });

    return {
      title: 'تشخیص ستون ثابت',
      stats: [
        ['کل ستون', headers.length],
        ['ستون ثابت', constantCols.length],
        ['ستون متغیر', headers.length - constantCols.length],
      ],
      detail: constantCols.map(c => `${c.col} (${c.uniqueCount} مقدار یکتا)`).join(' | '),
      note: constantCols.length
        ? 'ستون‌های ثابت: ' + constantCols.map(c=>c.col).join(', ')
        : 'هیچ ستون ثابتی یافت نشد',
    };
  },

  // ── 23. Invalid Values ────────────────────────────────────────────

  async invalidValues(params) {
    const { headers, rows } = await excel.readActiveSheet();
    const ci       = excel.getColIndex(headers, params.column);
    const ruleType = params.rule_type || 'range';
    const action   = params.action || 'flag';

    const isInvalid = (v) => {
      if (ruleType === 'not_null') return excel.isEmpty(v);
      if (ruleType === 'range') {
        const n = excel.toNumber(v);
        if (n === null) return true;
        const min = params.min_val !== '' ? parseFloat(params.min_val) : -Infinity;
        const max = params.max_val !== '' ? parseFloat(params.max_val) :  Infinity;
        return n < min || n > max;
      }
      if (ruleType === 'allowed_list') {
        const list = (params.allowed_list || '').split(',').map(s=>s.trim());
        return !list.includes(String(v ?? '').trim());
      }
      if (ruleType === 'regex') {
        try { return !new RegExp(params.regex_pattern||'').test(String(v??'')); }
        catch(_) { return true; }
      }
      return false;
    };

    let violations = 0;
    let newHeaders = [...headers];
    let newRows    = rows.map(r => [...r]);

    if (action === 'flag') newHeaders.push('is_invalid');

    for (let i = 0; i < newRows.length; i++) {
      const bad = isInvalid(newRows[i][ci]);
      if (bad) violations++;
      if (action === 'flag')         newRows[i].push(bad ? 1 : 0);
      if (action === 'remove' && bad) newRows[i][ci] = null;
      if (action === 'replace_null' && bad) newRows[i][ci] = null;
    }

    if (action === 'remove') newRows = newRows.filter(r => r[ci] !== null);

    await excel.writeToActiveSheet({ headers: newHeaders, rows: newRows });
    return {
      title: `تشخیص مقادیر نامعتبر — ${params.column}`,
      stats: [['قانون', ruleType], ['نقض', violations], ['معتبر', rows.length - violations]],
    };
  },

  // ── 24. Missing Value Strategy ────────────────────────────────────

  async missingStrategy(params) {
    const { headers, rows } = await excel.readActiveSheet();
    const strategy  = params.strategy || 'mean';
    const threshold = parseFloat(params.threshold) || 50;
    const ci        = params.column ? excel.getColIndex(headers, params.column) : null;
    const constVal  = params.constant_value ?? 0;

    const colIndices = ci !== null
      ? [ci]
      : headers.map((_, i) => i);

    // Drop cols over threshold first
    let keepCols = headers.map((_, i) => true);
    if (strategy === 'drop_cols') {
      headers.forEach((_, i) => {
        const pct = (rows.filter(r=>excel.isEmpty(r[i])).length / rows.length) * 100;
        if (pct > threshold) keepCols[i] = false;
      });
    }

    let newHeaders = headers.filter((_, i) => keepCols[i]);
    let newRows    = rows.map(r => r.filter((_, i) => keepCols[i]));

    if (strategy === 'drop_rows') {
      newRows = newRows.filter(r =>
        colIndices.every(i => !excel.isEmpty(r[i]))
      );
    } else if (strategy !== 'drop_cols') {
      for (const ci2 of colIndices) {
        const vals    = newRows.map(r => r[ci2]);
        const numeric = vals.map(v=>excel.toNumber(v)).filter(v=>v!==null);
        let fillVal;
        if (strategy === 'mean')     fillVal = numeric.length ? numeric.reduce((a,b)=>a+b,0)/numeric.length : 0;
        if (strategy === 'median')   fillVal = this._median(numeric);
        if (strategy === 'mode')     fillVal = this._mode(vals.filter(v=>!excel.isEmpty(v)));
        if (strategy === 'constant') fillVal = constVal;

        for (let i = 0; i < newRows.length; i++) {
          if (!excel.isEmpty(newRows[i][ci2])) continue;
          if (strategy === 'forward_fill') {
            newRows[i][ci2] = i > 0 ? newRows[i-1][ci2] : null;
          } else if (strategy === 'backward_fill') {
            // filled in second pass below
          } else if (strategy === 'interpolate') {
            newRows[i][ci2] = fillVal ?? 0; // simple for now
          } else {
            newRows[i][ci2] = fillVal;
          }
        }

        if (strategy === 'backward_fill') {
          for (let i = newRows.length - 2; i >= 0; i--) {
            if (excel.isEmpty(newRows[i][ci2])) {
              newRows[i][ci2] = newRows[i+1][ci2];
            }
          }
        }
      }
    }

    await excel.writeToActiveSheet({ headers: newHeaders, rows: newRows });
    return {
      title: 'استراتژی مقادیر خالی',
      stats: [
        ['استراتژی', strategy],
        ['ردیف نهایی', newRows.length],
        ['ستون نهایی', newHeaders.length],
      ],
    };
  },

  // ── MATH HELPERS ──────────────────────────────────────────────────

  _median(sorted) {
    if (!sorted.length) return 0;
    const s = [...sorted].sort((a,b)=>a-b);
    const m = Math.floor(s.length / 2);
    return s.length % 2 ? s[m] : (s[m-1] + s[m]) / 2;
  },

  _percentile(sortedArr, p) {
    const idx = (p / 100) * (sortedArr.length - 1);
    const lo  = Math.floor(idx);
    const hi  = Math.ceil(idx);
    return sortedArr[lo] + (sortedArr[hi] - sortedArr[lo]) * (idx - lo);
  },

  _mode(arr) {
    const freq = {};
    arr.forEach(v => freq[v] = (freq[v]||0) + 1);
    return Object.entries(freq).sort((a,b)=>b[1]-a[1])[0]?.[0];
  },
};

window.__SWAKModules = window.__SWAKModules || {};
window.__SWAKModules['clean'] = CleanModule;
