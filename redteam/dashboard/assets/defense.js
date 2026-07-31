// defense.js — Cliente del Defense Mesh Dashboard
// Consume los endpoints /api/defense/* del dashboard server.

const $ = (sel) => document.querySelector(sel);
const fmt = (v) => v === undefined || v === null ? "—" : v;

async function fetchJson(path) {
  try {
    const r = await fetch(path);
    if (!r.ok) return null;
    return await r.json();
  } catch (_) {
    return null;
  }
}

async function refresh() {
  const ov = await fetchJson("/api/defense/overview");
  if (ov) {
    $("#metric-rasp").textContent = fmt(ov.rasp_signals);
    $("#metric-ndr").textContent = fmt(ov.ndr_findings);
    $("#metric-ztna").textContent = fmt(ov.bola_attempts);
    $("#metric-deception").textContent = fmt(ov.decoy_hits);
    $("#metric-soar").textContent = fmt(ov.playbook_runs);
  }
  const inc = await fetchJson("/api/defense/incidents");
  if (inc) {
    const tb = $("#incidents-table tbody");
    tb.innerHTML = "";
    for (const i of inc.slice(0, 20)) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${fmt(i.timestamp)}</td><td>${fmt(i.severity)}</td>
                      <td>${fmt(i.mitre_id)}</td><td>${fmt(i.category)}</td>
                      <td>${fmt(i.summary)}</td>`;
      tb.appendChild(tr);
    }
  }
  const pb = await fetchJson("/api/defense/playbooks");
  if (pb) {
    const tb = $("#playbooks-table tbody");
    tb.innerHTML = "";
    for (const p of pb.slice(0, 20)) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${fmt(p.playbook_id)}</td><td>${fmt(p.status)}</td>
                      <td>${fmt(p.latency_ms)}</td><td>${fmt(p.started_at)}</td>`;
      tb.appendChild(tr);
    }
  }
  const cov = await fetchJson("/api/defense/coverage");
  if (cov) {
    const g = $("#coverage-grid");
    g.innerHTML = "";
    for (const [tid, info] of Object.entries(cov)) {
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = `<h3>${tid}</h3><p class="metric">${fmt(info.count)}</p>
                        <p class="label">${fmt(info.tactic)}</p>`;
      g.appendChild(card);
    }
  }
}

async function simulate() {
  const r = await fetchJson("/api/defense/simulate");
  $("#last-result").textContent = JSON.stringify(r, null, 2);
  refresh();
}

$("#btn-refresh")?.addEventListener("click", refresh);
$("#btn-simulate")?.addEventListener("click", simulate);
refresh();
setInterval(refresh, 15000);
