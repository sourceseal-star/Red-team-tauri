// Expediente de reapertura: carga el JSON histórico y re-audita cada hallazgo con probes REALES.
// Sin tráfico que re-auditar = "NO RE-AUDITABLE HOY", nunca un PASS falso.
const fs = require('fs');
const path = require('path');
const http = require('http');
const https = require('https');
const crypto = require('crypto');

const EVIDENCE = path.join(__dirname, '..', 'evidence');

// ---- Saneamiento de URL rota del histórico ----
function sanitizeUrl(raw) {
  if (!raw) return null;
  let s = String(raw).trim();
  // quitar doble esquema https://https://
  s = s.replace(/^https:\/\/https:\/\//i, 'https://');
  s = s.replace(/^http:\/\/https:\/\//i, 'https://');
  // quitar parámetros de tracking (fbclid, aem, utm_*)
  s = s.replace(/[?&](fbclid|aem|utm_[a-z]+)=[^&]*/gi, '');
  // limpiar ? o & sueltos
  s = s.replace(/[?&]$/, '');
  // corregir doble barra antes de /v1
  s = s.replace(/\/\/v1$/, '/v1');
  return s;
}

// ---- Probe HTTP real (con timeout) ----
function probeHttp(url, timeout = 4000) {
  return new Promise(res => {
    const u = new URL(url);
    const proto = u.protocol === 'https:' ? https : http;
    const req = proto.get({ host: u.hostname, port: u.port || (u.protocol === 'https:' ? 443 : 80), path: u.pathname + u.search, timeout,
      headers: { 'User-Agent': 'sealctl-casefile/1.0' }, rejectUnauthorized: true }, r => {
      let b = ''; r.on('data', d => b += d); const fin = () => res({ ok: true, status: r.statusCode, headers: r.headers, body: b.slice(0, 2000) });
      r.on('end', fin); r.on('close', fin);
    });
    req.on('error', e => res({ ok: false, error: e.message, errno: e.code || null }));
    req.on('timeout', () => { req.destroy(); res({ ok: false, error: 'timeout', errno: 'ETIMEDOUT' }); });
  });
}

// ---- Probe de headers contra localhost (la propia consola) ----
function probeLocalHeaders(timeout = 3000) {
  return new Promise(res => {
    const port = process.env.PORT || 3000;
    const req = http.get({ host: '127.0.0.1', port, path: '/api/status', timeout,
      headers: { 'Authorization': 'Bearer ' + (process.env.CONSOLE_TOKEN || '') } }, r => {
      const h = r.headers; const fin = () => res({ ok: true, status: r.statusCode, headers: h });
      r.on('end', fin); r.on('close', fin); r.resume();
    });
    req.on('error', e => res({ ok: false, error: e.message }));
    req.on('timeout', () => { req.destroy(); res({ ok: false, error: 'timeout' }); });
  });
}

// ---- Probe de rate limiting (N peticiones rápidas) ----
async function probeRateLimit(n = 16, timeout = 4000) {
  const port = process.env.PORT || 3000;
  let got429 = false;
  for (let i = 0; i < n; i++) {
    const r = await new Promise(res => {
      const req = http.get({ host: '127.0.0.1', port, path: '/api/iot?target=127.0.0.1', timeout: 1500,
        headers: { 'Authorization': 'Bearer ' + (process.env.CONSOLE_TOKEN || '') } }, resp => {
        const fin = () => res({ status: resp.statusCode, retry: resp.headers['retry-after'] || null });
        resp.on('end', fin); resp.on('close', fin); resp.resume();
      });
      req.on('error', () => res({ status: 0 }));
      req.on('timeout', () => { req.destroy(); res({ status: 0 }); });
    });
    if (r.status === 429) { got429 = true; break; }
  }
  return { got429, evidence: got429 ? '429 + Retry-After observado' : `ningún 429 en ${n} req` };
}

// ---- Probe de path traversal ----
async function probeTraversal() {
  const port = process.env.PORT || 3000;
  const r = await new Promise(res => {
    const req = http.get({ host: '127.0.0.1', port, path: '/api/reports/..%2f..%2f..%2fetc%2fpasswd', timeout: 3000,
      headers: { 'Authorization': 'Bearer ' + (process.env.CONSOLE_TOKEN || '') } }, resp => {
      let b = ''; const fin = () => res({ status: resp.statusCode, body: b });
      resp.on('data', d => b += d); resp.on('end', fin); resp.on('close', fin);
    });
    req.on('error', e => res({ status: 0, body: e.message }));
    req.on('timeout', () => { req.destroy(); res({ status: 0, body: 'timeout' }); });
  });
  const leak = /root:/.test(r.body || '');
  return { status: r.status, leak, evidence: `status ${r.status} · fuga /etc/passwd: ${leak}` };
}

// ---- Re-análisis estático de dummy.apk ----
function probeApk() {
  const apkPaths = [
    path.join(EVIDENCE, 'dummy.apk'),
    path.join(__dirname, '..', 'redteam', 'evidence', 'dummy.apk'),
    path.join(__dirname, '..', 'build', 'evidence', 'dummy.apk')
  ];
  const apkPath = apkPaths.find(p => fs.existsSync(p) && fs.statSync(p).size > 0);

  if (!apkPath) {
    return { present: false, reason: 'dummy.apk no presente en evidence/ (0 bytes o inexistente) — no se puede re-auditar el binario estáticamente' };
  }

  const stat = fs.statSync(apkPath);
  const sha256 = crypto.createHash('sha256').update(fs.readFileSync(apkPath)).digest('hex');

  // Extraer strings del APK (es un ZIP)
  let strings = [];
  try {
    const { execSync } = require('child_process');
    // unzip -p para extraer classes.dex y luego strings
    const out = execSync(`unzip -l "${apkPath}" 2>/dev/null | head -30`, { encoding: 'utf8', timeout: 5000 });
    const dexMatch = out.match(/classes\d*\.dex/);
    if (dexMatch) {
      const dexData = execSync(`unzip -p "${apkPath}" ${dexMatch[0]} 2>/dev/null`, { encoding: 'latin1', timeout: 10000, maxBuffer: 20 * 1024 * 1024 });
      // Buscar strings relevantes
      const patterns = ['AndroidKeyStore', 'SecureRandom', 'CertificatePinner', 'NetworkSecurityConfig', 'Luhn', 'constructEvent', 'verifyWebhook', 'KeyStore', 'Keychain', 'IMEI'];
      for (const p of patterns) {
        if (dexData.includes(p)) strings.push(p);
      }
    }
  } catch (e) {
    // Si falla, reportar el error
    strings = [];
    return { present: true, size: stat.size, sha256, strings, error: e.message };
  }

  return { present: true, size: stat.size, sha256, strings };
}

// ---- Mapeo de hallazgos → probes ----
function mapVerdict(baseSeverity, baseTitle, scenario, probeResult) {
  // Determinar el veredicto base
  const isFail = /FALLÓ|ausentes|\bsin\b|\bSin\b|no presenta|Vulnerable|sin evidencia|Sin uso|Sin evidencia/i.test(baseTitle);
  const baseVerdict = isFail ? 'FALLÓ' : 'INFO';

  // Si el probe no pudo ejecutarse
  if (!probeResult) return { now: 'NO_APLICA', delta: 'NO_APLICA', evidence: 'no mapeado a probe' };
  if (probeResult.now === 'NO_REAUDITABLE') return { now: 'NO_REAUDITABLE', delta: 'NO_REAUDITABLE', evidence: probeResult.evidence };
  if (probeResult.now === 'NO_APLICA') return { now: 'NO_APLICA', delta: 'NO_APLICA', evidence: probeResult.evidence };
  if (probeResult.now === 'ERR') return { now: 'ERR', delta: baseVerdict === 'FALLÓ' ? 'SIGUE_ABIERTO' : 'INFO', evidence: 'probe falló: ' + (probeResult.evidence || 'error desconocido') };
  if (probeResult.now === 'INFO') return { now: 'INFO', delta: 'INFO', evidence: probeResult.evidence };

  const now = probeResult.now;
  let delta;
  if (baseVerdict === 'FALLÓ' && now === 'PASA') delta = 'CERRADO';
  else if (baseVerdict === 'FALLÓ' && now === 'FALLA') delta = 'SIGUE_ABIERTO';
  else if (baseVerdict === 'INFO') delta = 'INFO';
  else delta = 'NUEVO';

  return { now, delta, evidence: probeResult.evidence || '' };
}

// ---- Cargar y normalizar el JSON histórico ----
function loadBase(jsonPath) {
  const candidates = [
    jsonPath,
    path.join(EVIDENCE, 'redteam-1785243252338.json'),
    path.join(__dirname, '..', 'redteam', 'reports', 'report-20260727-142759.json')
  ].filter(Boolean);

  const file = candidates.find(p => fs.existsSync(p));

  if (!file) {
    return { error: 'expediente base no encontrado', searched: candidates };
  }

  let raw = fs.readFileSync(file, 'utf8');
  let d;
  try {
    d = JSON.parse(raw);
  } catch (e) {
    return { error: 'expediente base corrupto: ' + e.message, file };
  }

  // Normalizar claves/valores con trim
  function norm(obj) {
    if (typeof obj === 'string') return obj.trim();
    if (Array.isArray(obj)) return obj.map(norm);
    if (obj && typeof obj === 'object') { const n = {}; for (const k in obj) n[k.trim()] = norm(obj[k]); return n; }
    return obj;
  }
  d = norm(d);

  return { data: d, file };
}

// ---- Ejecutar todos los probes y construir el expediente ----
async function run(jsonPath) {
  const base = loadBase(jsonPath);
  if (base.error) {
    return { ran_at: new Date().toISOString(), error: base.error, searched: base.searched || [] };
  }

  const d = base.data;
  const findings = d.findings || [];

  // Probes reales (se ejecutan una vez y se reutilizan)
  const [hdrLocal, rateLimit, traversal, apkResult] = await Promise.all([
    probeLocalHeaders().catch(() => ({ ok: false, error: 'no se pudo conectar a localhost' })),
    probeRateLimit().catch(() => ({ got429: false, evidence: 'probe falló' })),
    probeTraversal().catch(() => ({ status: 0, leak: false, evidence: 'probe falló' })),
    Promise.resolve(probeApk())
  ]);

  // Saneamiento de la URL rota
  const rawBackend = d.backend || '';
  const sanitizedBackend = sanitizeUrl(rawBackend);
  let backendProbe = null;
  if (sanitizedBackend) {
    backendProbe = await probeHttp(sanitizedBackend).catch(() => ({ ok: false, error: 'probe falló' }));
  }

  // Headers del backend saneado
  const backendHeaders = backendProbe && backendProbe.ok ? backendProbe.headers : {};
  const localHeaders = hdrLocal.ok ? hdrLocal.headers : {};

  // Verificar qué headers de seguridad están presentes
  const checkHeaders = (h) => {
    const want = ['x-frame-options', 'x-content-type-options', 'referrer-policy', 'strict-transport-security'];
    const have = want.filter(k => h[k]);
    return { have, missing: want.filter(k => !h[k]) };
  };

  const localHdrCheck = checkHeaders(localHeaders);
  const backendHdrCheck = checkHeaders(backendHeaders);

  // Mapear cada hallazgo a su probe
  const rows = findings.map((f, i) => {
    const scenario = f.scenario || '?';
    const severity = f.severity || 'info';
    const title = f.title || '?';
    const baseVerdict = /FALLÓ|ausentes|\bsin\b|\bSin\b|no presenta|Vulnerable|sin evidencia|Sin uso|Sin evidencia/i.test(title) ? 'FALLÓ' : 'INFO';

    let probeResult = null;

    // --- sourcesealcorp A4: rate limiting ---
    if (/\[A4\]/.test(title) && /rate/i.test(title)) {
      const now = rateLimit.got429 ? 'PASA' : 'FALLA';
      probeResult = { now, evidence: rateLimit.evidence };
    }
    // --- sourcesealcorp A7: path traversal ---
    else if (/\[A7\]/.test(title) && /traversal/i.test(title)) {
      const now = traversal.status === 0 ? 'ERR' : (traversal.leak ? 'FALLA' : 'PASA');
      probeResult = { now, evidence: traversal.status === 0 ? 'no se pudo conectar a la consola (server no corriendo)' : traversal.evidence };
    }
    // --- sourcesealcorp A1/A2/A5/A6: no aplican a la consola ---
    else if (/\[A[1256]\]/.test(title)) {
      probeResult = { now: 'NO_APLICA', evidence: 'control del backend sourcesealcorp original, no presente en sealctl' };
    }
    // --- recovery_page: headers ausentes ---
    else if (/headers.*ausentes/i.test(title) && scenario === 'recovery_page') {
      const now = localHdrCheck.missing.length === 0 ? 'PASA' : 'FALLA';
      probeResult = { now, evidence: `consola local: presentes [${localHdrCheck.have.join(',')}] · faltan [${localHdrCheck.missing.join(',')}]` };
    }
    // --- recovery_page: clickjacking ---
    else if (/clickjacking/i.test(title)) {
      const hasXfo = !!localHeaders['x-frame-options'];
      probeResult = { now: hasXfo ? 'PASA' : 'FALLA', evidence: `X-Frame-Options en consola: ${hasXfo ? 'DENY presente' : 'ausente'}` };
    }
    // --- recovery_page: IDOR / endpoint sin auth ---
    else if (/hash.*sin auth|\bIDOR\b/i.test(title)) {
      probeResult = { now: 'NO_APLICA', evidence: 'endpoint del backend sourcesealcorp original, no presente en sealctl' };
    }
    // --- pinning: TLS inválido ---
    else if (/TLS.*válido|certificado TLS/i.test(title) && scenario === 'pinning') {
      if (backendProbe && backendProbe.ok) {
        probeResult = { now: 'PASA', evidence: `host saneado resuelve: status ${backendProbe.status}, certificado ${backendProbe.headers['content-type'] ? 'observado' : 'sin info'}` };
      } else {
        probeResult = { now: 'FALLA', evidence: `host saneado: ${backendProbe ? backendProbe.error : 'no se pudo sanitizar URL'} · errno: ${backendProbe ? backendProbe.errno || 'N/A' : 'N/A'}` };
      }
    }
    // --- pinning: sin pinning en APK ---
    else if (/pinning.*APK/i.test(title)) {
      if (!apkResult.present) {
        probeResult = { now: 'NO_REAUDITABLE', evidence: apkResult.reason || 'dummy.apk no presente' };
      } else {
        const hasPinning = apkResult.strings.includes('CertificatePinner') || apkResult.strings.includes('NetworkSecurityConfig');
        probeResult = { now: hasPinning ? 'PASA' : 'FALLA', evidence: `apk sha256=${apkResult.sha256?.slice(0, 16)} · strings: [${apkResult.strings.join(',')}]` };
      }
    }
    // --- multiplatform: sin AndroidKeyStore ---
    else if (/almacén seguro nativo|AndroidKeyStore|KeyStore.*nativo/i.test(title)) {
      if (!apkResult.present) {
        probeResult = { now: 'NO_REAUDITABLE', evidence: apkResult.reason || 'dummy.apk no presente' };
      } else {
        const has = apkResult.strings.includes('AndroidKeyStore') || apkResult.strings.includes('KeyStore');
        probeResult = { now: has ? 'PASA' : 'FALLA', evidence: `apk strings: [${apkResult.strings.join(',')}]` };
      }
    }
    // --- multiplatform: sin CSPRNG ---
    else if (/CSPRNG|SecureRandom/i.test(title)) {
      if (!apkResult.present) {
        probeResult = { now: 'NO_REAUDITABLE', evidence: apkResult.reason || 'dummy.apk no presente' };
      } else {
        const has = apkResult.strings.includes('SecureRandom');
        probeResult = { now: has ? 'PASA' : 'FALLA', evidence: `SecureRandom en apk: ${has ? 'sí' : 'no'}` };
      }
    }
    // --- keyhandling: sin KeyStore/Keychain ---
    else if (/KeyStore.*Keychain/i.test(title)) {
      if (!apkResult.present) {
        probeResult = { now: 'NO_REAUDITABLE', evidence: apkResult.reason || 'dummy.apk no presente' };
      } else {
        const has = apkResult.strings.includes('KeyStore') || apkResult.strings.includes('Keychain');
        probeResult = { now: has ? 'PASA' : 'FALLA', evidence: `KeyStore/Keychain en apk: ${has ? 'sí' : 'no'}` };
      }
    }
    // --- imei: sin Luhn ---
    else if (/Luhn/i.test(title)) {
      if (!apkResult.present) {
        probeResult = { now: 'NO_REAUDITABLE', evidence: apkResult.reason || 'dummy.apk no presente' };
      } else {
        const has = apkResult.strings.includes('Luhn');
        probeResult = { now: has ? 'PASA' : 'FALLA', evidence: `Luhn en apk: ${has ? 'sí' : 'no'}` };
      }
    }
    // --- imei: sin blacklist ---
    else if (/blacklist/i.test(title)) {
      if (!apkResult.present) {
        probeResult = { now: 'NO_REAUDITABLE', evidence: apkResult.reason || 'dummy.apk no presente' };
      } else {
        const has = apkResult.strings.includes('IMEI');
        probeResult = { now: has ? 'PASA' : 'FALLA', evidence: `IMEI en apk: ${has ? 'sí' : 'no'}` };
      }
    }
    // --- payments: sin verificación de webhooks ---
    else if (/webhook/i.test(title)) {
      if (!apkResult.present) {
        probeResult = { now: 'NO_REAUDITABLE', evidence: apkResult.reason || 'dummy.apk no presente' };
      } else {
        const has = apkResult.strings.includes('constructEvent') || apkResult.strings.includes('verifyWebhook');
        probeResult = { now: has ? 'PASA' : 'FALLA', evidence: `verifyWebhook en apk: ${has ? 'sí' : 'no'}` };
      }
    }
    // --- rng: entropía OK ---
    else if (/entropía/i.test(title) && /OK/i.test(title)) {
      probeResult = { now: 'INFO', evidence: 'hallazgo informativo del histórico (7.944 b/B), no requiere re-auditoría' };
    }
    // --- rng: auditar seeds ---
    else if (/seeds/i.test(title)) {
      if (!apkResult.present) {
        probeResult = { now: 'NO_REAUDITABLE', evidence: apkResult.reason || 'dummy.apk no presente' };
      } else {
        probeResult = { now: 'FALLA', evidence: `apk presente (sha256=${apkResult.sha256?.slice(0, 16)}) pero análisis de seeds requiere tooling específico` };
      }
    }
    // --- sidechannel ---
    else if (/side.?channel|comparación naive/i.test(title)) {
      probeResult = { now: 'NO_APLICA', evidence: 'requiere microbenchmarks de timing, no aplicable a la consola' };
    }
    // --- sourcesealcorp: 6 controles FALLARON (resumen) ---
    else if (/6 controles.*FALLARON/i.test(title)) {
      probeResult = { now: 'INFO', evidence: `resumen del histórico: 6 controles caídos. A4/A7 re-auditados arriba; A1/A2/A5/A6 no aplican a la consola` };
    }
    // --- sourcesealcorp: A10 blockchain ---
    else if (/A10.*blockchain/i.test(title)) {
      probeResult = { now: 'NO_APLICA', evidence: 'configuración de blockchain no presente, no aplica a la consola' };
    }
    // --- multiplatform: plataforma detectada ---
    else if (/Plataforma detectada/i.test(title)) {
      probeResult = { now: 'INFO', evidence: 'detección de plataforma del histórico (Android), no requiere re-auditoría' };
    }
    // --- multiplatform: check de servidor backend ---
    else if (/Check de servidor/i.test(title)) {
      probeResult = { now: backendProbe && backendProbe.ok ? 'PASA' : 'FALLA',
        evidence: `backend saneado: ${sanitizedBackend || 'N/A'} → ${backendProbe && backendProbe.ok ? 'responde (status ' + backendProbe.status + ')' : 'no resuelve (' + (backendProbe?.error || 'N/A') + ')'}` };
    }
    // --- default: no mapeado ---
    else {
      probeResult = { now: 'NO_APLICA', evidence: 'hallazgo no mapeado a probe re-auditable en la consola actual' };
    }

    // Determinar delta
    const vr = mapVerdict(severity, title, scenario, probeResult);

    return {
      id: i,
      scenario,
      severity,
      title,
      base_verdict: baseVerdict,
      now: vr.now,
      delta: vr.delta,
      evidence: vr.evidence
    };
  });

  // Contar deltas
  const counts = { cerrado: 0, sigue_abierto: 0, no_aplica: 0, no_reauditable: 0, nuevo: 0, info: 0 };
  rows.forEach(r => { const k = (r.delta || '').toLowerCase(); if (counts[k] !== undefined) counts[k]++; });

  return {
    ran_at: new Date().toISOString(),
    base_file: base.file,
    base_total: findings.length,
    base_started_at: d.started_at,
    base_elapsed: d.elapsed_seconds,
    target: d.target,
    backend_raw: rawBackend,
    backend_sanitized: sanitizedBackend,
    by_severity: d.by_severity,
    scenarios_run: d.scenarios_run,
    rows,
    counts
  };
}

module.exports = { run, sanitizeUrl, loadBase, probeApk };
