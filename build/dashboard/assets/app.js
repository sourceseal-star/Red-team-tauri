/* SOURCESEAL Centro de Control — app principal
   Tabs: Agent (RedTeam reports) · Monitor (SSE en vivo) · Editor (frontend) */

const $ = (id) => document.getElementById(id);

// ------------------------------------------------------------- Tabs
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    $('tab-' + btn.dataset.tab).classList.add('active');
  });
});

// ============================================================== TAB 1: AGENT
async function loadLatestReport() {
  try {
    const r = await fetch('/api/latest');
    const j = await r.json();
    const by = j.by_severity || {};
    $('kpi-critical').textContent = by.critical || 0;
    $('kpi-high').textContent = by.high || 0;
    $('kpi-medium').textContent = by.medium || 0;
    $('kpi-low').textContent = (by.low || 0) + (by.info || 0);
    $('kpi-total').textContent = j.total_findings || 0;
    $('last-scan').textContent = j.finished_at ? j.finished_at.replace('T', ' ').slice(0, 19) : '—';
    $('agent-id').textContent = 'agent: ' + (j.agent || 'redteam');

    const tbody = $('findings-body');
    const findings = j.findings || [];
    if (!findings.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="empty">Sin hallazgos. Ejecuta un escaneo.</td></tr>';
    } else {
      tbody.innerHTML = findings.map((f, i) => `
        <tr>
          <td>${i + 1}</td>
          <td><span class="sev ${f.severity}">${f.severity}</span></td>
          <td><code>${f.scenario}</code></td>
          <td>${escapeHtml(f.title)}</td>
          <td>${(f.timestamp || '').slice(11, 19)}</td>
        </tr>
      `).join('');
    }
    setStatus(true, `conectado · ${findings.length} hallazgos`);
  } catch (e) {
    setStatus(false, 'error: ' + e);
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

$('refresh-btn').addEventListener('click', loadLatestReport);
$('run-scan').addEventListener('click', async () => {
  $('action-status').textContent = 'escaneando…';
  try {
    const r = await fetch('/api/scan', { method: 'POST' });
    const j = await r.json();
    if (j.ok) { $('action-status').textContent = 'listo'; loadLatestReport(); }
    else $('action-status').textContent = 'error: ' + j.error;
  } catch (e) {
    $('action-status').textContent = 'error: ' + e;
  }
});
$('download-report').addEventListener('click', () => {
  window.location.href = '/api/latest?download=1';
});

// filtro de búsqueda
$('filter').addEventListener('input', (e) => {
  const q = e.target.value.toLowerCase();
  document.querySelectorAll('#findings-body tr').forEach(tr => {
    tr.style.display = tr.textContent.toLowerCase().includes(q) ? '' : 'none';
  });
});

// ============================================================== TAB 2: MONITOR
let sseSource = null;

async function startMonitor() {
  const url = $('monitor-url').value.trim();
  const interval = parseInt($('monitor-interval').value, 10) || 15;
  if (!url) { $('monitor-status').textContent = 'falta URL'; return; }
  $('monitor-status').textContent = 'configurando…';
  try {
    const r = await fetch('/api/site/configure', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, interval })
    });
    const j = await r.json();
    if (!j.ok) throw new Error(j.error || 'fail');
    $('monitor-status').textContent = `activo · ${url}`;
    openSSE();
  } catch (e) {
    $('monitor-status').textContent = 'error: ' + e;
  }
}

function openSSE() {
  if (sseSource) { sseSource.close(); sseSource = null; }
  sseSource = new EventSource('/api/site/events');
  sseSource.addEventListener('snapshot', (ev) => {
    const snap = JSON.parse(ev.data);
    renderSnapshot(snap);
  });
  sseSource.addEventListener('site.probe', (ev) => {
    const data = JSON.parse(ev.data).data;
    renderProbe(data);
    appendEvent('probe', `${data.status} · ${data.latency_ms}ms · ${data.body_size}b`);
  });
  sseSource.addEventListener('site.content_changed', (ev) => {
    const d = JSON.parse(ev.data);
    appendEvent('changed', `⚠ cambio detectado en ${d.url}`, 'changed');
    document.getElementById('diff-box').textContent = d.diff_summary || '(diff no disponible)';
  });
  sseSource.addEventListener('monitor.started', (ev) => {
    appendEvent('started', `monitor activo: ${JSON.parse(ev.data).url}`, 'started');
  });
  sseSource.onerror = () => {
    $('monitor-status').textContent = 'SSE reconectando…';
  };
}

function renderSnapshot(snap) {
  const last = snap.last;
  if (!last) return;
  renderProbe(last);
}

function renderProbe(p) {
  $('m-state').textContent = p.ok ? '✅ UP' : (p.error ? '❌ ERR' : '⚠ DEGRADED');
  $('m-state').style.color = p.ok ? 'var(--ok)' : 'var(--critical)';
  $('m-latency').textContent = p.latency_ms ? p.latency_ms + ' ms' : '—';
  $('m-status').textContent = p.status || '—';
  $('m-status').style.color = p.status && p.status < 400 ? 'var(--ok)' : 'var(--critical)';
  $('m-tls').textContent = p.tls_expires_in_days != null ? `${p.tls_expires_in_days}d` : '—';
  const changes = parseInt($('m-changes').textContent, 10) || 0;
  if (p.changed_since_last) $('m-changes').textContent = changes + 1;

  const headersBody = $('headers-body');
  const all = ['Strict-Transport-Security', 'Content-Security-Policy', 'X-Frame-Options',
               'X-Content-Type-Options', 'Referrer-Policy', 'Permissions-Policy'];
  headersBody.innerHTML = all.map(h => {
    const v = p.security_headers ? p.security_headers[h] : null;
    const cls = v ? '' : ' style="color:var(--critical)"';
    return `<tr><td>${h}</td><td${cls}>${v ? escapeHtml(v).slice(0, 80) : '❌ FALTA'}</td></tr>`;
  }).join('');

  if (p.diff_summary) $('diff-box').textContent = p.diff_summary;
}

function appendEvent(kind, text, cls = '') {
  const ul = $('event-log');
  const li = document.createElement('li');
  li.className = cls;
  const t = new Date().toLocaleTimeString();
  li.innerHTML = `<time>${t}</time>${escapeHtml(text)}`;
  ul.insertBefore(li, ul.firstChild);
  while (ul.children.length > 200) ul.removeChild(ul.lastChild);
}

$('monitor-start').addEventListener('click', startMonitor);

// ============================================================== TAB 3: EDITOR
// La lógica pesada vive en editor.js (módulo Editor).
// Aquí solo activamos el botón "publicar" si el backend tiene token.

(async function checkPublish() {
  try {
    const r = await fetch('/api/site/publish_check');
    const j = await r.json();
    if (j.publish_enabled) {
      $('publish-card').hidden = false;
      $('btn-publish').addEventListener('click', publishToReplit);
    }
  } catch (e) { /* silencioso */ }
})();

async function publishToReplit() {
  const siteUrl = $('site-url-input').value.trim();
  // Tomamos los patches del módulo Editor vía su estado público.
  const patches = (window.Editor && window.Editor.getPatches) ? window.Editor.getPatches() : [];
  if (!patches.length) return alert('No hay patches para publicar.');
  const $status = $('publish-status');
  $status.textContent = 'publicando…';
  try {
    const r = await fetch('/api/site/publish', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        site_url: siteUrl,
        files: patches.map(p => ({ path: p.path, content: p.modified }))
      })
    });
    const j = await r.json();
    if (j.ok) { $status.textContent = '✅ publicado'; }
    else { $status.textContent = '❌ ' + (j.error || 'fallo'); }
  } catch (e) {
    $status.textContent = '❌ ' + e;
  }
}

// ============================================================== INIT
function setStatus(ok, text) {
  $('status-dot').classList.toggle('on', ok);
  $('status-dot').classList.toggle('off', !ok);
  $('status-text').textContent = text;
}

loadLatestReport();
setInterval(loadLatestReport, 30_000);
