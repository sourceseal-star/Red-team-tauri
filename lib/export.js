// Export unificado: intercept + discovery + intel -> schema EXACTO de redteam-*.json
// evidence_path ancla al evento real por id (#hash). legacy_quirks replica los trailing spaces del histórico.
const fs = require('fs'); const path = require('path');
const EVIDENCE = path.join(__dirname, '..', 'evidence');

function readJsonl(file) {
  const f = path.join(EVIDENCE, file); if (!fs.existsSync(f)) return [];
  return fs.readFileSync(f, 'utf8').split('\n').filter(Boolean).map(l => { try { return JSON.parse(l); } catch (_) { return null; } }).filter(Boolean);
}
const SEV = ['critical', 'high', 'medium', 'low', 'info'];
function mapEvent(e) {
  const base = { scenario: e.kind === 'AUDIT' ? 'iot-audit' : (e._src === 'discovery' ? 'discovery' : 'intercept'),
    evidence_path: e.id ? `evidence/intercept.jsonl#${e.id}` : '', timestamp: new Date((e.ts || Date.now()) * 1000).toISOString() };
  switch (e.kind) {
    case 'CRED_CLEARTEXT': return { ...base, severity: e.cleartext ? 'critical' : 'medium',
      title: `Credencial ${e.cleartext ? 'en claro' : 'capturada'} hacia ${e.host}`, description: `user ${e.user || '?'} · esquema ${e.scheme || '?'} · tls ${e.tls ? 'sí' : 'NO'}`, remediation: e.cleartext ? 'Migrar el dispositivo a HTTPS; nunca Basic sobre HTTP.' : 'Revisar exposición del token.' };
    case 'AUTH_OVER_HTTP': return { ...base, severity: 'high', title: `${e.host} pide login por HTTP`, description: `challenge: ${e.challenge || '?'}`, remediation: 'El dispositivo no debe pedir credenciales sin TLS.' };
    case 'AUDIT': return e.defaultCreds ? { ...base, severity: 'critical', title: `${e.ip} acepta credenciales por defecto`, description: `default ${e.defaultCreds.user}/${e.defaultCreds.pass} vía ${e.defaultCreds.scheme}`, remediation: 'Cambiar credenciales de fábrica inmediatamente.' }
      : { ...base, severity: 'info', title: `Login-audit ${e.ip}: ${e.verdict || 'sin hallazgo'}`, description: e.verdict || '', remediation: 'N/A' };
    case 'TOKEN_IN_QUERY': return { ...base, severity: e.cleartext ? 'medium' : 'low', title: `Token en query hacia ${e.host}`, description: `param ${e.param || '?'} · tls ${e.tls ? 'sí' : 'NO'}`, remediation: 'Mover el secreto a cabecera; no a la URL.' };
    case 'CAMERA': case 'CAMERA_BANNER': return { ...base, severity: e.tls === false ? 'high' : 'info', title: `Cámara ${e.vendor || ''} en ${e.host}`, description: e.snippet ? e.snippet.slice(0, 120) : `path ${e.path || '?'}`, remediation: e.tls === false ? 'Forzar TLS en la cámara.' : 'N/A' };
    default: return null;
  }
}
function build({ target = 'sealctl-unified', backend = 'sealctl@node', intelHosts = [], discovery = [], legacy_quirks = false } = {}) {
  const evs = readJsonl('intercept.jsonl');
  const findings = [];
  evs.forEach(e => { const m = mapEvent(e); if (m) findings.push(m); });
  discovery.filter(d => d.addr).forEach(d => findings.push({ scenario: 'discovery', severity: 'info',
    title: `Dispositivo ONVIF descubierto: ${d.addr}`, description: d.xaddrs || '', evidence_path: '', remediation: 'Verificar que es tuyo y auditar su login.', timestamp: new Date(d.ts || Date.now()).toISOString() }));
  intelHosts.filter(h => h.score > 50).forEach(h => findings.push({ scenario: 'intel', severity: h.score > 80 ? 'critical' : 'high',
    title: `IP de baja confianza: ${h.ip}`, description: `score ${h.score} (${h.label})`, evidence_path: '', remediation: 'Verificar origen antes de confiar.', timestamp: new Date().toISOString() }));
  const by = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
  findings.forEach(f => { if (by[f.severity] != null) by[f.severity]++; });
  const t0 = new Date(Date.now() - 1000).toISOString();
  let report = { started_at: t0, finished_at: new Date().toISOString(), elapsed_seconds: 1.0,
    total_findings: findings.length, by_severity: by, findings, errors: [], target, backend,
    scenarios_run: new Set(findings.map(f => f.scenario)).size };
  if (legacy_quirks) report = addQuirks(report);   // replica trailing spaces del histórico SI lo pides
  return report;
}
function addQuirks(o) {
  if (o && typeof o === 'object' && !Array.isArray(o)) { const n = {}; for (const k in o) n[k + ' '] = addQuirks(o[k]); return n; }
  if (Array.isArray(o)) return o.map(addQuirks);
  if (typeof o === 'string') return o + ' ';
  return o;
}
module.exports = { build };
