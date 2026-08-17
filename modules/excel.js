/**
 * SWAK — ExcelHelper
 * Office.js wrapper for reading/writing Excel data
 * All tool modules use this class exclusively for Excel interaction
 */

class ExcelHelper {

  // ── READ ──────────────────────────────────────────────────────────────

  /**
   * Read all data from the active sheet (including headers)
   * Returns: { headers: string[], rows: any[][], rowCount, colCount }
   */
  async readActiveSheet() {
    return new Promise((resolve, reject) => {
      Excel.run(async (ctx) => {
        try {
          const sheet = ctx.workbook.worksheets.getActiveWorksheet();
          const usedRange = sheet.getUsedRange();
          usedRange.load(['values', 'rowCount', 'columnCount']);
          await ctx.sync();

          const values = usedRange.values;
          if (!values || values.length === 0) {
            return resolve({ headers: [], rows: [], rowCount: 0, colCount: 0 });
          }

          const headers = values[0].map(h => String(h ?? ''));
          const rows = values.slice(1);

          resolve({
            headers,
            rows,
            rowCount: rows.length,
            colCount: headers.length
          });
        } catch (err) {
          reject(new Error('خواندن شیت ناموفق: ' + err.message));
        }
      });
    });
  }

  /**
   * Read only the selected range
   * Returns same shape as readActiveSheet
   */
  async readSelectedRange() {
    return new Promise((resolve, reject) => {
      Excel.run(async (ctx) => {
        try {
          const range = ctx.workbook.getSelectedRange();
          range.load(['values', 'rowCount', 'columnCount']);
          await ctx.sync();

          const values = range.values;
          if (!values || values.length === 0) {
            return resolve({ headers: [], rows: [], rowCount: 0, colCount: 0 });
          }

          const headers = values[0].map(h => String(h ?? ''));
          const rows = values.slice(1);

          resolve({ headers, rows, rowCount: rows.length, colCount: headers.length });
        } catch (err) {
          reject(new Error('خواندن محدوده ناموفق: ' + err.message));
        }
      });
    });
  }

  /**
   * Get column names from the active sheet (first row only)
   */
  async getColumnNames() {
    return new Promise((resolve, reject) => {
      Excel.run(async (ctx) => {
        try {
          const sheet = ctx.workbook.worksheets.getActiveWorksheet();
          const firstRow = sheet.getUsedRange().getRow(0);
          firstRow.load('values');
          await ctx.sync();
          resolve((firstRow.values[0] || []).map(v => String(v ?? '')));
        } catch (err) {
          reject(new Error('خواندن ستون‌ها ناموفق: ' + err.message));
        }
      });
    });
  }

  /**
   * Read a named sheet by name
   */
  async readSheet(sheetName) {
    return new Promise((resolve, reject) => {
      Excel.run(async (ctx) => {
        try {
          const sheet = ctx.workbook.worksheets.getItem(sheetName);
          const usedRange = sheet.getUsedRange();
          usedRange.load(['values', 'rowCount', 'columnCount']);
          await ctx.sync();

          const values = usedRange.values;
          if (!values || values.length === 0) {
            return resolve({ headers: [], rows: [], rowCount: 0, colCount: 0 });
          }

          resolve({
            headers: values[0].map(h => String(h ?? '')),
            rows: values.slice(1),
            rowCount: values.length - 1,
            colCount: values[0].length
          });
        } catch (err) {
          reject(new Error(`شیت "${sheetName}" یافت نشد: ` + err.message));
        }
      });
    });
  }

  // ── WRITE ─────────────────────────────────────────────────────────────

  /**
   * Write 2D array (with headers) to the active sheet, replacing content
   * data: { headers: string[], rows: any[][] }
   */
  async writeToActiveSheet(data) {
    return new Promise((resolve, reject) => {
      Excel.run(async (ctx) => {
        try {
          const sheet = ctx.workbook.worksheets.getActiveWorksheet();

          // Clear existing content
          sheet.getUsedRange().clear();

          const allRows = [data.headers, ...data.rows];
          const range = sheet.getRangeByIndexes(0, 0, allRows.length, data.headers.length);
          range.values = allRows;

          // Bold header row
          sheet.getRangeByIndexes(0, 0, 1, data.headers.length).format.font.bold = true;

          await ctx.sync();
          resolve({ rowsWritten: data.rows.length });
        } catch (err) {
          reject(new Error('نوشتن به شیت ناموفق: ' + err.message));
        }
      });
    });
  }

  /**
   * Create a new sheet with data
   * name: sheet name, data: { headers, rows }
   */
  async addNewSheet(name, data) {
    return new Promise((resolve, reject) => {
      Excel.run(async (ctx) => {
        try {
          // Delete existing sheet with same name if exists
          try {
            const existing = ctx.workbook.worksheets.getItem(name);
            existing.delete();
            await ctx.sync();
          } catch (_) { /* sheet didn't exist, that's fine */ }

          const sheet = ctx.workbook.worksheets.add(name);
          sheet.activate();

          const allRows = [data.headers, ...data.rows];
          const range = sheet.getRangeByIndexes(0, 0, allRows.length, data.headers.length);
          range.values = allRows;

          // Style header
          const headerRange = sheet.getRangeByIndexes(0, 0, 1, data.headers.length);
          headerRange.format.font.bold = true;
          headerRange.format.fill.color = '#1a1a2e';
          headerRange.format.font.color = '#ffffff';

          // Auto-fit columns
          sheet.getUsedRange().format.autofitColumns();

          await ctx.sync();
          resolve({ sheetName: name, rowsWritten: data.rows.length });
        } catch (err) {
          reject(new Error('ساخت شیت جدید ناموفق: ' + err.message));
        }
      });
    });
  }

  /**
   * Add a single column to the active sheet
   * colName: string, values: any[] (one per data row, no header)
   */
  async addColumn(colName, values) {
    return new Promise((resolve, reject) => {
      Excel.run(async (ctx) => {
        try {
          const sheet = ctx.workbook.worksheets.getActiveWorksheet();
          const usedRange = sheet.getUsedRange();
          usedRange.load(['columnCount', 'rowCount']);
          await ctx.sync();

          const newColIdx = usedRange.columnCount;
          // Header
          sheet.getRangeByIndexes(0, newColIdx, 1, 1).values = [[colName]];
          sheet.getRangeByIndexes(0, newColIdx, 1, 1).format.font.bold = true;
          // Values
          const colRange = sheet.getRangeByIndexes(1, newColIdx, values.length, 1);
          colRange.values = values.map(v => [v]);

          await ctx.sync();
          resolve({ colAdded: colName });
        } catch (err) {
          reject(new Error('افزودن ستون ناموفق: ' + err.message));
        }
      });
    });
  }

  /**
   * Update values in a specific column (by header name)
   */
  async updateColumn(colName, values) {
    return new Promise((resolve, reject) => {
      Excel.run(async (ctx) => {
        try {
          const sheet = ctx.workbook.worksheets.getActiveWorksheet();
          const usedRange = sheet.getUsedRange();
          usedRange.load('values');
          await ctx.sync();

          const headers = usedRange.values[0];
          const colIdx = headers.findIndex(h => String(h) === colName);
          if (colIdx === -1) throw new Error(`ستون "${colName}" یافت نشد`);

          const colRange = sheet.getRangeByIndexes(1, colIdx, values.length, 1);
          colRange.values = values.map(v => [v]);

          await ctx.sync();
          resolve({ colUpdated: colName });
        } catch (err) {
          reject(new Error('آپدیت ستون ناموفق: ' + err.message));
        }
      });
    });
  }

  /**
   * Highlight cells in a range with a color
   * range: 'A1:D10' or Excel.Range object
   * color: hex string e.g. '#FF0000'
   */
  async highlightCells(rangeAddress, color) {
    return new Promise((resolve, reject) => {
      Excel.run(async (ctx) => {
        try {
          const sheet = ctx.workbook.worksheets.getActiveWorksheet();
          const range = sheet.getRange(rangeAddress);
          range.format.fill.color = color;
          await ctx.sync();
          resolve(true);
        } catch (err) {
          reject(new Error('هایلایت ناموفق: ' + err.message));
        }
      });
    });
  }

  /**
   * Delete specific rows (by 0-based indices relative to data, not sheet)
   * Deletes from bottom to top to preserve indices
   */
  async deleteRows(rowIndices) {
    return new Promise((resolve, reject) => {
      Excel.run(async (ctx) => {
        try {
          const sheet = ctx.workbook.worksheets.getActiveWorksheet();
          // +1 because row 0 is header
          const sheetIndices = rowIndices.map(i => i + 1).sort((a, b) => b - a);

          for (const idx of sheetIndices) {
            sheet.getRangeByIndexes(idx, 0, 1, 1).getEntireRow().delete(Excel.DeleteShiftDirection.up);
          }

          await ctx.sync();
          resolve({ deletedRows: rowIndices.length });
        } catch (err) {
          reject(new Error('حذف ردیف‌ها ناموفق: ' + err.message));
        }
      });
    });
  }

  /**
   * Delete specific columns by index (0-based)
   */
  async deleteColumns(colIndices) {
    return new Promise((resolve, reject) => {
      Excel.run(async (ctx) => {
        try {
          const sheet = ctx.workbook.worksheets.getActiveWorksheet();
          const sorted = [...colIndices].sort((a, b) => b - a);

          for (const idx of sorted) {
            sheet.getRangeByIndexes(0, idx, 1, 1).getEntireColumn().delete(Excel.DeleteShiftDirection.left);
          }

          await ctx.sync();
          resolve({ deletedCols: colIndices.length });
        } catch (err) {
          reject(new Error('حذف ستون‌ها ناموفق: ' + err.message));
        }
      });
    });
  }

  /**
   * Get list of all sheet names in workbook
   */
  async getSheetNames() {
    return new Promise((resolve, reject) => {
      Excel.run(async (ctx) => {
        try {
          const sheets = ctx.workbook.worksheets;
          sheets.load('items/name');
          await ctx.sync();
          resolve(sheets.items.map(s => s.name));
        } catch (err) {
          reject(new Error('دریافت نام شیت‌ها ناموفق: ' + err.message));
        }
      });
    });
  }

  // ── HELPERS ───────────────────────────────────────────────────────────

  /**
   * Convert data object to 2D array for writing
   * data: array of objects with same keys
   */
  objectsToTable(data) {
    if (!data || data.length === 0) return { headers: [], rows: [] };
    const headers = Object.keys(data[0]);
    const rows = data.map(obj => headers.map(h => obj[h] ?? ''));
    return { headers, rows };
  }

  /**
   * Convert headers+rows back to array of objects
   */
  tableToObjects(headers, rows) {
    return rows.map(row =>
      Object.fromEntries(headers.map((h, i) => [h, row[i]]))
    );
  }

  /**
   * Get column index by name
   */
  getColIndex(headers, colName) {
    const idx = headers.findIndex(h => String(h).trim() === String(colName).trim());
    if (idx === -1) throw new Error(`ستون "${colName}" یافت نشد`);
    return idx;
  }

  /**
   * Extract a single column's values from rows
   */
  getColValues(rows, colIdx) {
    return rows.map(row => row[colIdx]);
  }

  /**
   * Check if a value is considered empty/null/missing
   */
  isEmpty(val) {
    if (val === null || val === undefined) return true;
    if (typeof val === 'string' && val.trim() === '') return true;
    if (typeof val === 'number' && isNaN(val)) return true;
    return false;
  }

  /**
   * Parse a value as number, return null if not parseable
   */
  toNumber(val) {
    if (val === null || val === undefined || val === '') return null;
    const n = Number(val);
    return isNaN(n) ? null : n;
  }
}

// Export singleton
window.ExcelHelper = ExcelHelper;
const excelHelper = new ExcelHelper();
window.excel = excelHelper;
