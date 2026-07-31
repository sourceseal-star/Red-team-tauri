const express = require('express');
const { WebSocketServer } = require('ws');
const http = require('http');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');
const geo = require('./lib/geo');
const intel = require('./lib/intel');
const iot = require('./lib/iot');

const app = express();
const server = http.createServer(app);
const wss = new WebSocketServer({ server });
const PORT = process.env.PORT || 3000;
const EVIDENCE = path.join(__dirname, 'evidence');
fs.mkdirSync(EVIDENCE, { recursive: true });

app.use(express.json({ limit: '4mb' }));
app.use(express.static(path.join(__dirname, 'public')));

// CORS para el dashboard movil
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Content-Type, X-Sourceseal-Signature, X-Sourceseal-Timestamp');
  if (req.method === 'OPTIONS') return res.sendStatus(200);
  next();
});

// ─── WebSocket helpers ──────────────────────────────────────────────────────
function emit(type, payload) {
  const msg = JSON.stringify({ type, t: new Date().toISOString(), ...payload });
  wss.clients.forEach(c => { if (c.readyState === 1) c.send(msg); });
}
const procs = { nmap: null, mitm: null, honeypot: null, scan: null };

function runStreamed(name, cmd, args, tag, onDone) {
  if (procs[name]) { try { procs[name].kill('SIGTERM'); } catch (e) {} }
  emit('proc', { tag, state: 'running', cmd: cmd + ' ' + args.join(' ') });
  const started = Date.now(); let buf = '';
  const p = spawn(cmd, args, { env: { ...process.env, TERM: 'dumb' }, cwd: __dirname });
  procs[name] = p;
  p.stdout.on('data', d => { const s = d.toString(); buf += s; emit('stdout', { tag, line: s }); });
  p.stderr.on('data', d => emit('stderr', { tag, line: d.toString() }));
  p.on('close', code => {
    procs[name] = null;
    emit('proc', { tag, state: code === 0 ? 'done' : 'error', code, ms: Date.now() - started });
    if (onDone) onDone(buf, code);
  });
  p.on('error', e => emit('proc', { tag, state: 'error', error: e.message }));
  return p;
}

const REDTEAM_DIR = path.join(__dirname, 'redteam');
const SCENARIOS = ['biometric','business_logic','imei','keyhandling','multiplatform','payments','pegasus','pinning','recovery_page','rng','sidechannel','sourcesealcorp','zt_checks'];

// ─── Status ──────────────────────────────────────────────────────────────────
app.get('/api/status', (req, res) => {
  const ifaces = os.networkInterfaces(); let ip = '127.0.0.1';
  for (const k in ifaces) for (const i of ifaces[k]) if (i.family === 'IPv4' && !i.internal) ip = i.address;
  const reports = fs.readdirSync(EVIDENCE).filter(f => f.endsWith('.json'));
  res.json({
    node: os.hostname(), platform: os.platform(), arch: os.arch(),
    uptime_s: Math.floor(os.uptime()), load: os.loadavg()[0],
    mem_free_mb: Math.round(os.freemem() / 1e6), mem_total_mb: Math.round(os.totalmem() / 1e6),
    ip, port: PORT,
    nmap: !!procs.nmap, mitm: !!procs.mitm, honeypot: !!procs.honeypot, scan: !!procs.scan,
    reports: reports.length,
    modules: {
      geo: typeof geo.lookup === 'function',
      intel: typeof intel.assess === 'function',
      iot: typeof iot.scan === 'function',
      python: fs.existsSync(path.join(REDTEAM_DIR, 'runner', 'orchestrator.py')),
      honeypot: fs.existsSync(path.join(__dirname, 'honeypot', 'start-honeypot.js')),
      scenarios: SCENARIOS.length
    }
  });
});

// ─── Nmap + enriquecimiento automático ──────────────────────────────────────
app.get('/api/nmap', (req, res) => {
  const target = (req.query.target || '').trim();
  if (!target) return res.status(400).json({ error: 'target requerido' });
  runStreamed('nmap', 'nmap', ['-sT','-Pn','--top-ports','100','-T4', target], 'nmap', (buf) => {
    const ips = [...new Set((buf.match(/\b(\d{1,3}(?:\.\d{1,3}){3})\b/g) || []))]
      .filter(x => !/^(127\.|0\.0\.0\.0|255\.)/.test(x));
    emit('hosts', { ips, target });
  });
  res.json({ ok: true, target });
});

// ─── Geo / Intel / IoT ──────────────────────────────────────────────────────
app.get('/api/geo', async (req, res) => res.json(await geo.lookup((req.query.ip || '').trim())));
app.get('/api/intel', async (req, res) => res.json(await intel.assess((req.query.ip || '').trim())));
app.get('/api/iot', async (req, res) => {
  const t = (req.query.target || '').trim();
  if (!t) return res.status(400).json({ error: 'target requerido' });
  res.json(await iot.scan(t));
});
app.post('/api/iot/scan', async (req, res) => {
  const ips = (req.body.ips || []).filter(Boolean);
  res.json({ results: await iot.scanMany(ips, 6) });
});

// ─── MITM ────────────────────────────────────────────────────────────────────
app.post('/api/mitm/start', (req, res) => {
  const out = path.join(EVIDENCE, 'traffic-' + Date.now() + '.flow');
  runStreamed('mitm', 'mitmdump', ['-q','-w',out,'--set','console_eventlog_verbosity=info'], 'mitm');
  res.json({ ok: true, listen: '0.0.0.0:8080', capture: out });
});
app.post('/api/mitm/stop', (req, res) => { if (procs.mitm) procs.mitm.kill('SIGINT'); res.json({ ok: true }); });
app.get('/api/mitm/cert', (req, res) => {
  const ca = path.join(os.homedir(), '.mitmproxy', 'mitmproxy-ca-cert.cer');
  res.json({ exists: fs.existsSync(ca), path: ca });
});

// ─── Honeypot (integracion real) ────────────────────────────────────────────
app.post('/api/honeypot/start', (req, res) => {
  const port = parseInt(req.body && req.body.port || req.query.port || 8080);
  if (procs.honeypot) { try { procs.honeypot.kill('SIGTERM'); } catch(e){} }
  const hpPath = path.join(__dirname, 'honeypot', 'start-honeypot.js');
  if (!fs.existsSync(hpPath)) return res.status(404).json({ error: 'honeypot no encontrado' });
  emit('proc', { tag: 'honeypot', state: 'running', cmd: 'node honeypot/start-honeypot.js ' + port });
  const p = spawn('node', [hpPath, String(port)], { cwd: __dirname, env: { ...process.env, HONEYPOT_PORT: String(port) } });
  procs.honeypot = p;
  let responded = false;
  p.stdout.on('data', d => {
    const s = d.toString();
    emit('stdout', { tag: 'honeypot', line: s });
    if (!responded && /listening|activo|started|ready|port/i.test(s)) {
      responded = true;
      res.json({ ok: true, port, message: 'Honeypot activo en :' + port });
    }
  });
  p.stderr.on('data', d => emit('stderr', { tag: 'honeypot', line: d.toString() }));
  p.on('close', code => {
    procs.honeypot = null;
    emit('proc', { tag: 'honeypot', state: 'stopped', code });
  });
  setTimeout(() => { if (!responded) { responded = true; res.json({ ok: true, port, message: 'Honeypot iniciando en :' + port }); } }, 5000);
});
app.post('/api/honeypot/stop', (req, res) => {
  if (procs.honeypot) procs.honeypot.kill('SIGTERM');
  procs.honeypot = null;
  emit('proc', { tag: 'honeypot', state: 'stopped' });
  res.json({ ok: true });
});

// ─── Python Orchestrator (escenarios reales) ────────────────────────────────
// /scan — ejecuta el orchestrator Python (lo que el dashboard movil espera)
app.post('/scan', (req, res) => {
  const target = (req.body && req.body.target || 'build/app.apk').trim();
  const backend = (req.body && req.body.backend || 'http://localhost:' + PORT).trim();
  if (procs.scan) return res.status(409).json({ error: 'Escaneo en curso' });
  
  const args = [path.join(REDTEAM_DIR,'runner','orchestrator.py'),'--target',target,'--backend',backend,'--output',EVIDENCE];
  emit('proc', { tag: 'scan', state: 'running', cmd: 'python3 orchestrator.py --target ' + target });
  const started = Date.now();
  const p = spawn('python3', args, { cwd: REDTEAM_DIR, env: { ...process.env, PYTHONPATH: REDTEAM_DIR } });
  procs.scan = p;
  p.stdout.on('data', d => emit('stdout', { tag: 'scan', line: d.toString() }));
  p.stderr.on('data', d => emit('stderr', { tag: 'scan', line: d.toString() }));
  res.json({ ok: true, message: 'Escaneo iniciado', target, backend });
  p.on('close', code => {
    procs.scan = null;
    emit('proc', { tag: 'scan', state: code === 0 ? 'done' : 'error', code, ms: Date.now() - started });
    try {
      const files = fs.readdirSync(EVIDENCE).filter(f => f.startsWith('report-') && f.endsWith('.json')).sort().reverse();
      if (files.length > 0) {
        const report = JSON.parse(fs.readFileSync(path.join(EVIDENCE, files[0]), 'utf-8'));
        emit('report', { file: files[0], total: report.total_findings, by: report.by_severity, elapsed: ((Date.now()-started)/1000).toFixed(1) });
      }
    } catch(e){}
  });
});

// /latest — ultimo reporte (dashboard movil)
app.get('/latest', (req, res) => {
  try {
    const files = fs.readdirSync(EVIDENCE).filter(f => f.startsWith('report-') && f.endsWith('.json')).sort().reverse();
    if (files.length === 0) {
      const rdir = path.join(REDTEAM_DIR, 'reports');
      if (fs.existsSync(rdir)) {
        const rfiles = fs.readdirSync(rdir).filter(f => f.startsWith('report-') && f.endsWith('.json')).sort().reverse();
        if (rfiles.length > 0) return res.json(JSON.parse(fs.readFileSync(path.join(rdir, rfiles[0]), 'utf-8')));
      }
      return res.json({ started_at:'', finished_at:'', elapsed_seconds:0, total_findings:0, by_severity:{critical:0,high:0,medium:0,low:0,info:0}, findings:[], scenarios_run:[], target:'none', backend:'sealctl' });
    }
    res.json(JSON.parse(fs.readFileSync(path.join(EVIDENCE, files[0]), 'utf-8')));
  } catch(e) { res.status(500).json({ error: e.message }); }
});

// /history — historial de escaneos (dashboard movil)
app.get('/history', (req, res) => {
  try {
    const files = fs.readdirSync(EVIDENCE).filter(f => f.startsWith('report-') && f.endsWith('.json')).sort().reverse();
    const history = files.map(f => {
      try {
        const d = JSON.parse(fs.readFileSync(path.join(EVIDENCE, f), 'utf-8'));
        return { finished_at: d.finished_at || f, total_findings: d.total_findings || 0, by_severity: d.by_severity || {} };
      } catch { return null; }
    }).filter(Boolean);
    res.json(history);
  } catch(e) { res.json([]); }
});

// /playbooks — SOAR playbooks (dashboard movil)
app.get('/playbooks', (req, res) => {
  const pbDir = path.join(REDTEAM_DIR, 'defense', 'playbooks');
  try {
    if (!fs.existsSync(pbDir)) return res.json([]);
    const files = fs.readdirSync(pbDir).filter(f => f.endsWith('.yaml'));
    const playbooks = files.map(f => {
      try {
        const content = fs.readFileSync(path.join(pbDir, f), 'utf-8');
        const name = f.replace('.yaml','');
        const desc = (content.match(/description:\s*(.+)/)||[])[1] || '';
        const severity = (content.match(/severity:\s*(.+)/)||[])[1] || 'MEDIUM';
        const stepCount = (content.match(/-\s*name:/g)||[]).length;
        return { name, description: desc.trim(), severity: severity.trim(), mitre_techniques:[], steps:[], status:'idle', file:f, step_count: stepCount };
      } catch { return null; }
    }).filter(Boolean);
    res.json(playbooks);
  } catch(e) { res.json([]); }
});

// /trigger-playbook — ejecutar playbook SOAR (dashboard movil)
app.post('/trigger-playbook', (req, res) => {
  const name = (req.body && req.body.name || '').trim();
  if (!name) return res.status(400).json({ error: 'name requerido' });
  const pbFile = path.join(REDTEAM_DIR, 'defense', 'playbooks', name + '.yaml');
  if (!fs.existsSync(pbFile)) return res.status(404).json({ error: 'playbook ' + name + ' no encontrado' });
  const soarScript = path.join(REDTEAM_DIR, 'defense', 'soar.py');
  if (fs.existsSync(soarScript)) {
    const p = spawn('python3', [soarScript, '--playbook', name], { cwd: REDTEAM_DIR, env: { ...process.env, PYTHONPATH: REDTEAM_DIR } });
    p.stdout.on('data', d => emit('stdout', { tag: 'soar', line: d.toString() }));
    p.stderr.on('data', d => emit('stderr', { tag: 'soar', line: d.toString() }));
    p.on('close', code => emit('proc', { tag: 'soar', state: code === 0 ? 'done' : 'error', code }));
    res.json({ success: true, detail: 'Playbook ' + name + ' ejecutandose' });
  } else {
    res.json({ success: false, detail: 'SOAR module no disponible, ' + name + ' simulado' });
  }
});

// /incidents — incidentes activos (dashboard movil)
app.get('/incidents', (req, res) => {
  try {
    const files = fs.readdirSync(EVIDENCE).filter(f => f.startsWith('report-') && f.endsWith('.json')).sort().reverse();
    const incidents = [];
    if (files.length > 0) {
      const report = JSON.parse(fs.readFileSync(path.join(EVIDENCE, files[0]), 'utf-8'));
      for (const f of (report.findings || [])) {
        if (f.severity === 'critical' || f.severity === 'high') {
          incidents.push({
            id: 'inc-' + f.scenario + '-' + Date.now(),
            severity: f.severity, title: f.title, description: f.description,
            mitre_techniques: [], kill_chain_phases: [],
            confidence: f.severity === 'critical' ? 0.95 : 0.75,
            timestamp: f.timestamp || report.finished_at, status: 'open',
            related_findings: [f.scenario]
          });
        }
      }
    }
    res.json(incidents);
  } catch(e) { res.json([]); }
});

// /downloads — archivos descargables (dashboard movil)
app.get('/downloads', (req, res) => {
  try {
    const items = [];
    const reports = fs.readdirSync(EVIDENCE).filter(f => f.endsWith('.json'));
    for (const f of reports) {
      const stat = fs.statSync(path.join(EVIDENCE, f));
      items.push({ id:f, name:f, type:'report', date:stat.mtime.toISOString(), size:(stat.size/1024).toFixed(1)+'KB', url:'/api/reports/'+f });
    }
    const rdir = path.join(REDTEAM_DIR, 'reports');
    if (fs.existsSync(rdir)) {
      const strings = fs.readdirSync(rdir).filter(f => f.endsWith('-strings.txt'));
      for (const f of strings) {
        const stat = fs.statSync(path.join(rdir, f));
        items.push({ id:f, name:f, type:'strings', date:stat.mtime.toISOString(), size:(stat.size/1024).toFixed(1)+'KB' });
      }
    }
    res.json(items);
  } catch(e) { res.json([]); }
});

// ─── Defense modules ─────────────────────────────────────────────────────────
app.get('/api/defense/status', (req, res) => {
  const checks = [
    { name:'XDR', file:'defense/xdr.py', desc:'Extended Detection & Response' },
    { name:'ZTNA', file:'defense/ztna.py', desc:'Zero Trust Network Access' },
    { name:'SOAR', file:'defense/soar.py', desc:'Security Orchestration & Response' },
    { name:'NDR', file:'defense/ndr.py', desc:'Network Detection & Response' },
    { name:'RASP', file:'defense/rasp.py', desc:'Runtime App Self-Protection' },
    { name:'Deception', file:'defense/deception.py', desc:'Deception & Honeytokens' },
    { name:'Attestation', file:'attestation/server.py', desc:'Device Attestation' },
    { name:'Integrity', file:'integrity/seal_manager.py', desc:'Seal & Integrity Manager' },
    { name:'NDR-Engine', file:'ndr/engine.py', desc:'ML Network Detection Engine' },
  ];
  res.json({ modules: checks.map(m => ({ ...m, available: fs.existsSync(path.join(REDTEAM_DIR, m.file)) })) });
});

app.post('/api/defense/run', (req, res) => {
  const mod = (req.body && req.body.module || '').trim();
  if (!mod) return res.status(400).json({ error: 'module requerido' });
  const moduleMap = {
    'xdr':'defense/xdr.py','ztna':'defense/ztna.py','soar':'defense/soar.py',
    'ndr':'defense/ndr.py','rasp':'defense/rasp.py','deception':'defense/deception.py',
    'attestation':'attestation/server.py','integrity':'integrity/seal_manager.py','ndr-engine':'ndr/engine.py'
  };
  const file = moduleMap[mod];
  if (!file) return res.status(400).json({ error: 'modulo ' + mod + ' no reconocido' });
  const fp = path.join(REDTEAM_DIR, file);
  if (!fs.existsSync(fp)) return res.status(404).json({ error: file + ' no encontrado' });
  runStreamed(mod, 'python3', [fp], 'defense-' + mod);
  res.json({ ok: true, module: mod, message: mod + ' ejecutandose' });
});

// ─── Escenarios individuales ─────────────────────────────────────────────────
app.post('/api/scenario/:name', (req, res) => {
  const name = req.params.name;
  if (!SCENARIOS.includes(name)) return res.status(400).json({ error: 'escenario ' + name + ' no disponible' });
  const target = (req.body && req.body.target || 'build/app.apk').trim();
  const backend = (req.body && req.body.backend || 'http://localhost:' + PORT).trim();
  const scriptPath = path.join(REDTEAM_DIR, 'scenarios', name + '.py');
  const p = spawn('python3', ['-c',
    `import sys; sys.path.insert(0,'${REDTEAM_DIR.replace(/\\/g,'\\\\')}')\nfrom scenarios import ${name}\nimport json\nresults = ${name}.run('${target}','${backend}','${EVIDENCE.replace(/\\/g,'\\\\')}')\nprint(json.dumps(results, indent=2))`
  ], { cwd: REDTEAM_DIR, env: { ...process.env, PYTHONPATH: REDTEAM_DIR } });
  let out = '';
  p.stdout.on('data', d => { out += d.toString(); emit('stdout', { tag: 'scenario-' + name, line: d.toString() }); });
  p.stderr.on('data', d => emit('stderr', { tag: 'scenario-' + name, line: d.toString() }));
  p.on('close', code => emit('proc', { tag: 'scenario-' + name, state: code === 0 ? 'done' : 'error', code }));
  res.json({ ok: true, scenario: name, message: 'Escenario ' + name + ' ejecutandose' });
});

app.get('/api/scenarios', (req, res) => res.json({ scenarios: SCENARIOS }));

// ─── IOC feed ────────────────────────────────────────────────────────────────
app.get('/api/iocs', (req, res) => {
  try {
    const iocFile = path.join(REDTEAM_DIR, 'data', 'iocs.json');
    if (fs.existsSync(iocFile)) res.json({ iocs: JSON.parse(fs.readFileSync(iocFile, 'utf-8')) });
    else res.json({ iocs: [], message: 'No hay IOCs cargados' });
  } catch(e) { res.json({ iocs: [], error: e.message }); }
});

// ─── MITRE ATT&CK mapping ────────────────────────────────────────────────────
app.get('/api/mitre', (req, res) => {
  try {
    const mitreFile = path.join(REDTEAM_DIR, 'defense', 'mitre_map.yaml');
    if (fs.existsSync(mitreFile)) res.type('text/yaml').send(fs.readFileSync(mitreFile, 'utf-8'));
    else res.json({ error: 'MITRE map no encontrado' });
  } catch(e) { res.status(500).json({ error: e.message }); }
});

// ─── Reportes ────────────────────────────────────────────────────────────────
app.post('/api/report/generate', (req, res) => {
  const { target = 'manual', findings = [] } = req.body;
  const by = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
  findings.forEach(f => { if (by[f.severity] != null) by[f.severity]++; });
  const report = {
    started_at: new Date(Date.now()-1000).toISOString(), finished_at: new Date().toISOString(),
    elapsed_seconds: 1.0, total_findings: findings.length, by_severity: by,
    findings, errors: [], target, backend: 'sealctl@' + os.hostname(),
    scenarios_run: [...new Set(findings.map(f => f.scenario))]
  };
  const file = 'report-' + Date.now() + '.json';
  fs.writeFileSync(path.join(EVIDENCE, file), JSON.stringify(report, null, 2));
  emit('report', { file, total: findings.length, by });
  res.json({ ok: true, file, report });
});

app.get('/api/reports', (req, res) => {
  res.json(fs.readdirSync(EVIDENCE).filter(f => f.endsWith('.json'))
    .map(f => ({ file: f, size: fs.statSync(path.join(EVIDENCE, f)).size }))
    .sort((a,b) => b.file.localeCompare(a.file)));
});

app.get('/api/reports/:file', (req, res) => {
  const fp = path.join(EVIDENCE, path.basename(req.params.file));
  if (!fs.existsSync(fp)) return res.status(404).json({ error: 'no existe' });
  res.download(fp);
});


// --- Ejecutar comandos personalizados (solo lectura, seguridad basica) ---
app.post('/api/exec', (req, res) => {
  const cmd = req.body.cmd || '';
  if (!cmd || /rm |dd |mkfs|:(){:|&;}:/.test(cmd)) return res.status(400).json({ error: 'comando no permitido' });
  const child = spawn('sh', ['-c', cmd], { timeout: 10000 });
  let out = '', err = '';
  child.stdout.on('data', d => out += d.toString());
  child.stderr.on('data', d => err += d.toString());
  child.on('close', code => res.json({ output: out || err || 'comando ejecutado (sin salida)', code }));
  child.on('error', e => res.status(500).json({ error: e.message }));
});

// --- Detener nmap ---
app.post('/api/nmap/stop', (req, res) => {
  if (procs.nmap) { procs.nmap.kill('SIGTERM'); procs.nmap = null; }
  res.json({ ok: true });
});

// ─── WebSocket ───────────────────────────────────────────────────────────────
wss.on('connection', ws => {
  ws.send(JSON.stringify({ type: 'hello', msg: 'sealctl conectado — todos los modulos activos' }));
  const hb = setInterval(() => { try { ws.send(JSON.stringify({ type: 'ping' })); } catch(e){} }, 15000);
  ws.on('close', () => clearInterval(hb));
});

// ─── Start ──────────────────────────────────────────────────────────────────
server.listen(PORT, '0.0.0.0', () => {
  console.log('\\n  SealCtl v2.0 en http://localhost:' + PORT + '\\n  Recon: geo/intel/iot/nmap/mitm | Defense: xdr/ztna/soar/ndr/rasp | Honeypot | ' + SCENARIOS.length + ' escenarios Python\\n');
});
