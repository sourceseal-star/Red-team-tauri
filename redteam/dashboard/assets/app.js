// SOURCESEAL RedTeam — Dashboard frontend
// Carga reportes desde /api/reports (Vercel/Express) o desde reports/*.json
(() => {
  const $ = (id) => document.getElementById(id);
  const state = { findings: [], report: null, history: [] };

  const SEV_COLORS = {
    critical: "#f6465d", high: "#ff8d3a",
    medium: "#f0b90b", low: "#0ecb81", info: "#4f8df9",
  };

  async function fetchJSON(url) {
    try {
      const r = await fetch(url, { cache: "no-store" });
      if (!r.ok) return null;
      return await r.json();
    } catch { return null; }
  }

  async function loadData() {
    setStatus("loading", "cargando...");
    // 1) Intentar API serverless
    let latest = await fetchJSON("/api/latest");
    let history = await fetchJSON("/api/history") || [];
    // 2) Fallback: archivo estático
    if (!latest) {
      latest = await fetchJSON("reports/latest.json");
    }
    if (latest) {
      state.report = latest;
      state.findings = latest.findings || [];
      state.agent = latest.agent || "redteam-agent";
    }
    state.history = history;
    render();
    setStatus(latest ? "on" : "off", latest ? "conectado" : "sin datos");
  }

  function setStatus(kind, text) {
    const dot = $("status-dot");
    dot.classList.remove("on", "off", "warn");
    dot.classList.add(kind);
    $("status-text").textContent = text;
  }

  function render() {
    renderKPIs();
    renderTable();
    renderScenarioBars();
    renderSeverityChart();
    renderTimeline();
    if (state.report && state.report.agent) $("agent-id").textContent = `agent: ${state.report.agent}`;
    $("last-scan").textContent = state.report
      ? new Date(state.report.finished_at).toLocaleString()
      : "—";
  }

  function renderKPIs() {
    const s = state.report?.by_severity || { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
    $("kpi-critical").textContent = s.critical || 0;
    $("kpi-high").textContent = s.high || 0;
    $("kpi-medium").textContent = s.medium || 0;
    $("kpi-low").textContent = (s.low || 0) + (s.info || 0);
    $("kpi-total").textContent = state.report?.total_findings || state.findings.length;
  }

  function renderTable() {
    const filter = ($("filter").value || "").toLowerCase();
    const body = $("findings-body");
    const rows = state.findings.filter(f => {
      if (!filter) return true;
      return (f.title + " " + (f.scenario || f.type || "") + " " + (f.endpoint || f.path || "") + " " + (f.description || f.detail || ""))
        .toLowerCase().includes(filter);
    });
    if (!rows.length) {
      body.innerHTML = `<tr><td colspan="6" class="empty">Sin hallazgos</td></tr>`;
      return;
    }
    body.innerHTML = rows.slice(0, 200).map((f, i) => `
      <tr data-idx="${state.findings.indexOf(f)}">
        <td>${i + 1}</td>
        <td><span class="badge ${f.severity}">${f.severity}</span></td>
        <td><code>${f.scenario}</code></td>
        <td>${escapeHTML(f.title)}</td>
        <td class="muted small">${formatDate(f.timestamp)}</td>
        <td><span class="badge ${f.severity === "critical" || f.severity === "high" ? "high" : "low"}">
          ${f.severity === "critical" || f.severity === "high" ? "ABIERTO" : "OK"}</span></td>
      </tr>
    `).join("");
    body.querySelectorAll("tr").forEach(tr => {
      tr.addEventListener("click", () => showDetail(parseInt(tr.dataset.idx)));
    });
  }

  function renderScenarioBars() {
    const counts = {};
    state.findings.forEach(f => { const key = f.scenario || f.type || "real-scan"; counts[key] = (counts[key] || 0) + 1; });
    const max = Math.max(1, ...Object.values(counts));
    const html = Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .map(([k, v]) => `
        <div class="bar-row">
          <div class="bar-label">${k}</div>
          <div class="bar-track"><div class="bar-fill" style="width:${(v / max) * 100}%"></div></div>
          <div class="bar-count">${v}</div>
        </div>`).join("");
    $("scenario-bars").innerHTML = html || '<p class="muted small">Sin datos</p>';
  }

  function renderSeverityChart() {
    const c = $("severity-chart");
    const ctx = c.getContext("2d");
    ctx.clearRect(0, 0, c.width, c.height);
    const s = state.report?.by_severity || {};
    const data = [
      { k: "critical", v: s.critical || 0, c: SEV_COLORS.critical },
      { k: "high",     v: s.high || 0,     c: SEV_COLORS.high },
      { k: "medium",   v: s.medium || 0,   c: SEV_COLORS.medium },
      { k: "low/info", v: (s.low || 0) + (s.info || 0), c: SEV_COLORS.info },
    ];
    const total = data.reduce((a, b) => a + b.v, 0) || 1;
    const cx = c.width / 2, cy = c.height / 2, r = 90, ir = 55;
    let start = -Math.PI / 2;
    data.forEach(d => {
      const angle = (d.v / total) * Math.PI * 2;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.arc(cx, cy, r, start, start + angle);
      ctx.closePath();
      ctx.fillStyle = d.c;
      ctx.fill();
      start += angle;
    });
    // hole
    ctx.beginPath();
    ctx.arc(cx, cy, ir, 0, Math.PI * 2);
    ctx.fillStyle = "#181a20";
    ctx.fill();
    // center text
    ctx.fillStyle = "#eaecef";
    ctx.font = "bold 22px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(total, cx, cy + 4);
    ctx.font = "11px sans-serif";
    ctx.fillStyle = "#848e9c";
    ctx.fillText("total", cx, cy + 22);

    $("legend").innerHTML = data.map(d =>
      `<li><span class="swatch" style="background:${d.c}"></span>${d.k} <strong>${d.v}</strong></li>`
    ).join("");
  }

  function renderTimeline() {
    const c = $("timeline-chart");
    const ctx = c.getContext("2d");
    ctx.clearRect(0, 0, c.width, c.height);
    if (!state.history.length) {
      ctx.fillStyle = "#848e9c";
      ctx.font = "12px sans-serif";
      ctx.fillText("Sin histórico", 10, 30);
      return;
    }
    const data = state.history.slice(-20);
    const max = Math.max(1, ...data.map(d => (d.by_severity?.critical || 0) + (d.by_severity?.high || 0)));
    const w = c.width / data.length;
    data.forEach((d, i) => {
      const crit = d.by_severity?.critical || 0;
      const high = d.by_severity?.high || 0;
      const hC = (crit / max) * (c.height - 30);
      const hH = ((crit + high) / max) * (c.height - 30);
      ctx.fillStyle = SEV_COLORS.critical;
      ctx.fillRect(i * w + 2, c.height - 20 - hC, w - 4, hC);
      ctx.fillStyle = SEV_COLORS.high;
      ctx.fillRect(i * w + 2, c.height - 20 - hH, w - 4, hH - hC);
    });
    // baseline
    ctx.strokeStyle = "#2b3139";
    ctx.beginPath();
    ctx.moveTo(0, c.height - 20);
    ctx.lineTo(c.width, c.height - 20);
    ctx.stroke();
  }

  function showDetail(idx) {
    const f = state.findings[idx];
    if (!f) return;
    const card = $("detail-card"), content = $("detail-content");
    card.hidden = false;
    content.innerHTML = `
      <h3><span class="badge ${f.severity}">${f.severity}</span> ${escapeHTML(f.title)}</h3>
      <div class="row"><div class="key">Escenario</div><code>${f.scenario || f.type || "real-scan"}</code></div>
      ${f.endpoint || f.path ? `<div class="row"><div class="key">Endpoint</div><code>${escapeHTML(f.endpoint || f.path)}</code></div>` : ""}
      <div class="row"><div class="key">Descripción</div>${escapeHTML(f.description || "")}</div>
      <div class="row"><div class="key">Evidencia</div><code>${escapeHTML(f.evidence_path || "—")}</code></div>
      <div class="row"><div class="key">Remediación</div>${escapeHTML(f.remediation || "")}</div>
      <div class="row"><div class="key">Detectado</div>${formatDate(f.timestamp)}</div>
    `;
    card.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function formatDate(iso) {
    if (!iso) return "—";
    try { return new Date(iso).toLocaleString(); } catch { return iso; }
  }
  function escapeHTML(s) {
    return String(s || "").replace(/[<>&"']/g, c => ({
      "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;", "'": "&#39;"
    }[c]));
  }

  // Events
  $("filter").addEventListener("input", renderTable);
  $("refresh-btn").addEventListener("click", loadData);
  $("run-scan").addEventListener("click", async () => {
    const btn = $("run-scan");
    const status = $("action-status");
    btn.disabled = true;
    status.textContent = "Iniciando escaneo...";
    try {
      // Soporta GET y POST
      const r = await fetch("/api/scan", { method: "POST" }).then(x => x.json()).catch(() =>
        fetch("/api/scan").then(x => x.json()).catch(() => ({}))
      );
      if (r?.status === "started" || r?.status === "running" || r?.ok) {
        status.textContent = "Escaneando... (puede tardar 30-60s)";
        let attempts = 0;
        const poll = setInterval(async () => {
          attempts++;
          try {
            const s = await fetch("/api/scan/status").then(x => x.json());
            if (s.progress) status.textContent = s.progress;
            if (!s.running && s.last_result) {
              clearInterval(poll);
              const res = s.last_result;
              status.textContent = res.ok
                ? `\u2705 ${res.findings} hallazgos en ${res.elapsed}s`
                : `\u274c ${s.last_error || "Error"}`;
              btn.disabled = false;
              await loadData();
            } else if (attempts > 120) {
              clearInterval(poll);
              status.textContent = "Timeout - revisa el servidor";
              btn.disabled = false;
            }
          } catch(e) {
            if (attempts > 120) {
              clearInterval(poll);
              status.textContent = "Error de conexion";
              btn.disabled = false;
            }
          }
        }, 2000);
      } else {
        status.textContent = r?.error ? `\u274c ${r.error}` : "\u274c No se pudo iniciar";
        btn.disabled = false;
      }
    } catch(e) {
      status.textContent = "\u274c Error: " + e.message;
      btn.disabled = false;
    }
  });
  $("download-report").addEventListener("click", () => {
    if (!state.report) return;
    const blob = new Blob([JSON.stringify(state.report, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `redteam-${Date.now()}.json`;
    a.click();
  });

  // PWA install
  let deferredPrompt;
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredPrompt = e;
    $("install-pwa").hidden = false;
  });
  $("install-pwa").addEventListener("click", async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    $("install-pwa").hidden = outcome !== "accepted";
    deferredPrompt = null;
  });

  // Register service worker (PWA offline)
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  }

  // Initial load + auto-refresh every 30s
  loadData();
  setInterval(loadData, 30000);
})();
