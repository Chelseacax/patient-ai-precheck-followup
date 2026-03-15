'use strict';

const STATUS_ICONS = { queued: '⏳', running: '🔄', success: '✅', failed: '❌' };

let ws = null;
let actionsSchema = {};
let wsReconnectTimer = null;

// ── DOM refs ────────────────────────────────────────────────────────────────
const dot         = document.getElementById('status-dot');
const statusLabel = document.getElementById('status-label');
const urlDisplay  = document.getElementById('url-display');
const screen      = document.getElementById('screen');
const placeholder = document.getElementById('screen-placeholder');
const logList     = document.getElementById('log-list');
const actionSel   = document.getElementById('action-select');
const paramsArea  = document.getElementById('params-area');
const schemaHint  = document.getElementById('schema-hint');
const execBtn     = document.getElementById('btn-execute');
const execStatus  = document.getElementById('exec-status');

// ── WebSocket ───────────────────────────────────────────────────────────────
function connectWS() {
  if (ws) ws.close();
  ws = new WebSocket(`ws://${location.host}/ws`);

  ws.onopen = () => {
    dot.classList.add('connected');
    statusLabel.textContent = 'Connected';
    if (wsReconnectTimer) { clearTimeout(wsReconnectTimer); wsReconnectTimer = null; }
  };

  ws.onclose = () => {
    dot.classList.remove('connected');
    statusLabel.textContent = 'Disconnected';
    wsReconnectTimer = setTimeout(connectWS, 3000);
  };

  ws.onerror = () => {
    dot.classList.remove('connected');
    statusLabel.textContent = 'Error';
  };

  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    handleWsMessage(msg);
  };
}

function handleWsMessage(msg) {
  switch (msg.type) {
    case 'screenshot':
      screen.src = 'data:image/jpeg;base64,' + msg.data;
      screen.style.display = 'block';
      placeholder.style.display = 'none';
      if (msg.url) urlDisplay.textContent = msg.url;
      break;

    case 'log_sync':
      logList.innerHTML = '';
      (msg.log || []).forEach(entry => prependLogEntry(entry));
      break;

    case 'action_started':
    case 'action_update':
    case 'action_complete':
    case 'action_failed':
      upsertLogEntry(msg.entry);
      break;
  }
}

// ── Log rendering ────────────────────────────────────────────────────────────
function makeLogEl(entry) {
  const el = document.createElement('div');
  el.className = `log-entry entry-${entry.status}`;
  el.id = 'log-' + entry.id;

  const paramsStr = JSON.stringify(entry.params || {});
  let extra = '';
  if (entry.result) extra = `<div class="log-result">→ ${JSON.stringify(entry.result).slice(0, 120)}</div>`;
  if (entry.error)  extra = `<div class="log-error">✗ ${entry.error}</div>`;

  el.innerHTML = `
    <div class="log-icon">${STATUS_ICONS[entry.status] || '⏳'}</div>
    <div class="log-body">
      <span class="log-action">${entry.action}</span>
      <span class="log-time">${entry.timestamp}</span>
      <div class="log-params">${paramsStr}</div>
      ${extra}
    </div>`;
  return el;
}

function prependLogEntry(entry) {
  const el = makeLogEl(entry);
  logList.prepend(el);
}

function upsertLogEntry(entry) {
  const existing = document.getElementById('log-' + entry.id);
  if (existing) {
    const fresh = makeLogEl(entry);
    existing.replaceWith(fresh);
  } else {
    prependLogEntry(entry);
  }
}

// ── Load actions schema ──────────────────────────────────────────────────────
async function loadActions() {
  try {
    const res = await fetch('/api/actions');
    actionsSchema = await res.json();

    actionSel.innerHTML = '<option value="">— select action —</option>';
    for (const [name] of Object.entries(actionsSchema)) {
      const opt = document.createElement('option');
      opt.value = name;
      opt.textContent = name;
      actionSel.appendChild(opt);
    }
  } catch (e) {
    console.error('Failed to load actions', e);
  }
}

actionSel.addEventListener('change', () => {
  const name = actionSel.value;
  if (!name || !actionsSchema[name]) {
    schemaHint.textContent = '';
    paramsArea.value = '{}';
    return;
  }
  const schema = actionsSchema[name];
  const params = {};
  const lines = [];
  for (const [pName, meta] of Object.entries(schema.params_schema || {})) {
    lines.push(`  "${pName}": ""  // ${meta.type} ${meta.required ? '(required)' : '(optional)'} – ${meta.description}`);
    if (meta.required) params[pName] = '';
  }
  schemaHint.textContent = lines.length ? `{\n${lines.join(',\n')}\n}` : '(no parameters)';
  paramsArea.value = JSON.stringify(params, null, 2);
});

// ── Execute action ───────────────────────────────────────────────────────────
async function executeAction() {
  const action = actionSel.value;
  if (!action) { execStatus.textContent = 'Select an action first.'; return; }

  let params = {};
  try {
    params = JSON.parse(paramsArea.value || '{}');
  } catch {
    execStatus.textContent = '⚠ Invalid JSON in params.';
    return;
  }

  execBtn.disabled = true;
  execStatus.textContent = 'Executing…';

  try {
    const res = await fetch('/api/agent/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, params, source: 'manual' }),
    });
    const data = await res.json();
    if (data.success) {
      execStatus.textContent = `✅ Done: ${JSON.stringify(data.result).slice(0, 80)}`;
    } else {
      execStatus.textContent = `❌ ${data.error}`;
    }
  } catch (e) {
    execStatus.textContent = `❌ Network error: ${e.message}`;
  } finally {
    execBtn.disabled = false;
  }
}

execBtn.addEventListener('click', executeAction);

// ── Init ─────────────────────────────────────────────────────────────────────
loadActions();
connectWS();
