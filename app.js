/**
 * SWAK — app.js
 * Entry point: Office.js initialization + tool router
 * Connects UI (ui_preview_v2.0.0.html) to backend modules
 */

// ── CONFIG ────────────────────────────────────────────────────────────────

const SWAK_CONFIG = {
  version:    '2.0.0',
  serverUrl:  'http://127.0.0.1:5000',   // Local Python backend
  apiTimeout: 30000,                      // 30s per tool call
};

// ── OFFICE.JS INIT ────────────────────────────────────────────────────────

Office.onReady(async (info) => {
  if (info.host !== Office.HostType.Excel) {
    console.error('SWAK: This add-in only works in Excel');
    return;
  }
  console.log(`SWAK v${SWAK_CONFIG.version} — Office.js ready`);

  // Check if Python backend is running
  await _checkBackendStatus();
});

// ── BACKEND STATUS CHECK ──────────────────────────────────────────────────

async function _checkBackendStatus() {
  try {
    const res = await fetch(`${SWAK_CONFIG.serverUrl}/health`, {
      signal: AbortSignal.timeout(3000),
    });
    if (res.ok) {
      console.log('SWAK: Python backend connected ✓');
      window.__SWAK_BACKEND_AVAILABLE = true;
    }
  } catch (_) {
    console.warn('SWAK: Python backend not running — using JS fallback');
    window.__SWAK_BACKEND_AVAILABLE = false;
  }
}

// ── MODULE REGISTRY ───────────────────────────────────────────────────────
// Maps tierId → module object
// Modules register themselves via window.__SWAKModules

window.__SWAKModules = window.__SWAKModules || {};

// Tier → backend route (for Python server)
const TIER_ROUTES = {
  clean:        '/api/clean',
  filter:       '/api/filter',
  transform:    '/api/transform',
  stats:        '/api/stats',
  ml:           '/api/ml',
  viz:          '/api/viz',
  ai:           '/api/ai',
  import:       '/api/import',
  export:       '/api/export',
  profiling:    '/api/profiling',
  dataeng:      '/api/dataeng',
  productivity: '/api/productivity',
};

// ── MAIN ENTRY POINT (called by UI) ──────────────────────────────────────
/**
 * UI calls: window.executeToolAction(tierId, toolId, params)
 * This replaces the simulated runTool() in ui_preview_v2.0.0.html
 */
window.executeToolAction = async function(tierId, toolId, params) {
  console.log(`SWAK: executing ${tierId}/${toolId}`, params);

  try {
    // 1. Validate license for Pro tools
    const isPro = window.__SWAK_IS_PRO || false;
    // License validation handled by license.js

    // 2. Try Python backend first (has Cython compiled code)
    if (window.__SWAK_BACKEND_AVAILABLE) {
      return await _callPythonBackend(tierId, toolId, params);
    }

    // 3. Fallback: JS module in browser
    const mod = window.__SWAKModules[tierId];
    if (!mod) throw new Error(`ماژول "${tierId}" بارگذاری نشده`);
    return await mod.run(toolId, params);

  } catch (err) {
    console.error(`SWAK error [${tierId}/${toolId}]:`, err);
    throw err;
  }
};

// ── PYTHON BACKEND CALLER ─────────────────────────────────────────────────

async function _callPythonBackend(tierId, toolId, params) {
  const route = TIER_ROUTES[tierId];
  if (!route) throw new Error(`روت ناشناخته: ${tierId}`);

  // Read Excel data
  const data = await excel.readActiveSheet();

  const body = {
    tool_id: toolId,
    params,
    headers: data.headers,
    rows:    data.rows,
    license_key: window.__SWAK_LICENSE_KEY || null,
  };

  const res = await fetch(`${SWAK_CONFIG.serverUrl}${route}`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(body),
    signal:  AbortSignal.timeout(SWAK_CONFIG.apiTimeout),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || `Server error ${res.status}`);
  }

  const result = await res.json();

  // Write result back to Excel if server returned data
  if (result.headers && result.rows) {
    await excel.writeToActiveSheet({ headers: result.headers, rows: result.rows });
  } else if (result.new_sheet) {
    await excel.addNewSheet(result.new_sheet.name, {
      headers: result.new_sheet.headers,
      rows:    result.new_sheet.rows,
    });
  }

  return result.summary || result;
}

// ── HELPER: display result in UI ──────────────────────────────────────────

window.displayToolResult = function(result) {
  // This is called after executeToolAction resolves
  // The UI's showResult panel reads from this
  window.__SWAK_LAST_RESULT = result;
  // Trigger UI refresh
  if (typeof window.refreshResultPanel === 'function') {
    window.refreshResultPanel(result);
  }
};
