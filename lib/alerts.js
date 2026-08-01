// Motor de alertas sobre el feed intercept/discovery. Reglas declarativas + cooldown.
// No genera alertas de la nada: sin evento que dispare, sin alerta (contrato anti-simulación).
const COOLDOWN_MS = 60_000;            // silencio por (regla+host) para no spamear
const last = new Map();                // key -> ts
let sink = () => {};                   // emisor (lo conecta server.js al WS)
let store = [];                        // últimas alertas (ring)
const MAX = 300;

const RULES = [
  { id: 'cred-plaintext', sev: 'critical', when: e => e.kind === 'CRED_CLEARTEXT' && e.cleartext,
    msg: e => `credencial en CLARO hacia ${e.host} (user ${e.user || '?'})` },
  { id: 'auth-over-http', sev: 'high', when: e => e.kind === 'AUTH_OVER_HTTP',
    msg: e => `${e.host} exige login por HTTP sin cifrar` },
  { id: 'default-creds', sev: 'critical', when: e => e.kind === 'AUDIT' && e.defaultCreds,
    msg: e => `${e.ip} acepta credenciales por defecto (${e.defaultCreds.user})` },
  { id: 'token-in-query', sev: e => e.cleartext ? 'medium' : 'low', when: e => e.kind === 'TOKEN_IN_QUERY',
    msg: e => `token/clave en query string hacia ${e.host}` },
  { id: 'cam-no-tls', sev: 'high', when: e => (e.kind === 'CAMERA' || e.kind === 'CAMERA_BANNER') && e.tls === false,
    msg: e => `cámara ${e.vendor || ''} en ${e.host} sin TLS` },
  { id: 'new-onvif', sev: 'info', when: e => e._src === 'discovery',
    msg: e => `nuevo dispositivo ONVIF en tu LAN: ${e.addr}` },
];

function feed(event, emit) {
  if (emit) sink = emit;
  for (const r of RULES) {
    let hit = false; try { hit = r.when(event); } catch (_) {}
    if (!hit) continue;
    const host = event.host || event.addr || event.ip || '?';
    const key = r.id + '|' + host;
    const now = Date.now();
    if ((last.get(key) || 0) + COOLDOWN_MS > now) continue;   // en silencio
    last.set(key, now);
    const sev = typeof r.sev === 'function' ? r.sev(event) : r.sev;
    const a = { id: r.id, severity: sev, host, msg: r.msg(event), ts: now, ref: event.id || null };
    store.push(a); if (store.length > MAX) store.shift();
    sink(a);
  }
}
function list() { return store.slice().reverse(); }
function clear() { store = []; last.clear(); }
module.exports = { feed, list, clear, RULES };
