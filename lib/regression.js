// Puente de evidencia: histórico (redteam-*.json) vs probes REALES contra la propia consola.
// NO se apropia de métricas ajenas: cada control marca applies=true/false al cuerpo 'sealctl'.
// Probe de red real a 127.0.0.1 (determinista). La LÓGICA de decisión la cubre /api/selftest.
const http = require('http');
function req(method, p, headers = {}, body = null) {
  return new Promise(res => {
    const r = http.request({ host: '127.0.0.1', port: process.env.PORT || 3000, path: p, method, headers }, resp => {
      let b = ''; resp.on('data', d => b += d); const fin = () => res({ status: resp.statusCode, headers: resp.headers, body: b });
      resp.on('end', fin); resp.on('close', fin);
    });
    r.on('error', e => res({ status: 0, error: e.message, headers: {}, body: '' }));
    if (body) r.write(body); r.end();
  });
}
// controles del histórico y su relación con el cuerpo 'sealctl'
const CONTROLS = [
  { id: 'A4', title: 'Rate limiting', hist: 'FALLÓ', applies: true,
    probe: async () => { let got429 = false; const H = process.env.CONSOLE_TOKEN ? { 'Authorization': 'Bearer ' + process.env.CONSOLE_TOKEN } : {};
      for (let i = 0; i < 16; i++) { const r = await req('GET', '/api/iot?target=127.0.0.1', H); if (r.status === 429) { got429 = true; break; } }
      return { now: got429 ? 'PASA' : 'FALLA', evidence: got429 ? '429 + Retry-After observado' : 'ningún 429 en 16 req' }; } },
  { id: 'A7', title: 'Path traversal', hist: 'FALLÓ', applies: true,
    probe: async () => { const r = await req('GET', '/api/reports/..%2f..%2f..%2fetc%2fpasswd');
      const leak = /root:/.test(r.body); return { now: leak ? 'FALLA' : 'PASA', evidence: `status ${r.status} · fuga /etc/passwd: ${leak}` }; } },
  { id: 'HDR', title: 'Headers de seguridad', hist: 'ausentes', applies: true,
    probe: async () => { const r = await req('GET', '/api/status'); const h = r.headers;
      const have = ['x-frame-options', 'x-content-type-options', 'referrer-policy'].filter(k => h[k]);
      return { now: have.length === 3 ? 'PASA' : 'FALLA', evidence: `presentes: ${have.join(',') || 'ninguno'}` }; } },
  { id: 'A5', title: 'Firma HMAC', hist: 'FALLÓ', applies: false, note: 'la consola usa Bearer token, no HMAC+nonce; A5 es del backend sourcesealcorp' },
  { id: 'A6', title: 'Replay attack', hist: 'FALLÓ', applies: false, note: 'idem: anti-replay por nonce vive en el backend original, no verificado en este cuerpo' },
  { id: 'A1', title: 'Reuso de hash', hist: 'FALLÓ', applies: false, note: 'control del flujo de hashes/recuperación del backend original' },
  { id: 'A2', title: 'Time-lock', hist: 'FALLÓ', applies: false, note: 'control del backend original' },
  { id: 'IDOR', title: 'IDOR /api/hashes/{id}', hist: 'sin auth', applies: false, note: 'endpoint del backend sourcesealcorp, no de la consola' },
  { id: 'TLS', title: 'Certificado TLS', hist: 'inválido', applies: false, note: 'HTTPS lo termina Replit/ingress; en Termux localhost es HTTP por diseño' },
];
async function run() {
  const rows = [];
  for (const c of CONTROLS) {
    if (!c.applies) { rows.push({ ...c, now: 'N/A', evidence: c.note }); continue; }
    try { const p = await c.probe(); rows.push({ ...c, ...p }); }
    catch (e) { rows.push({ ...c, now: 'ERR', evidence: e.message }); }
  }
  const appl = rows.filter(r => r.applies);
  const passed = appl.filter(r => r.now === 'PASA').length;
  return { ran_at: new Date().toISOString(), rows,
    index: appl.length ? +(passed / appl.length).toFixed(2) : 0,   // 0..1 sobre los aplicables
    applicable: appl.length, passed, not_applicable: rows.length - appl.length };
}
module.exports = { run, CONTROLS };
