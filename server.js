const express = require('express');
const { WebSocketServer } = require('ws');
const http = require('http');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');
const geo = require('./lib/geo');
const intel = require('./lib/intel');
const iot = require('./lib/iot');
const discovery = require('./lib/discovery');
const alerts = require('./lib/alerts');
const exporter = require('./lib/export');
const regression = require('./lib/regression');
const casefile = require('./lib/casefile');

// ─── Security: API Key Authentication ────────────────────────────────────────
const API_KEY = process.env.REDTEAM_API_KEY || crypto.randomBytes(24).toString('hex');
const HOST = process.env.HOST || '127.0.0.1';
const PORT = process.env.PORT || 3000;

if (!process.env.REDTEAM_API_KEY) {
  console.log('  ⚠ ADVERTENCIA: REDTEAM_API_KEY no configurada. Usando clave temporal.');
  console.log('  ⚠ Clave de esta sesion: ' + API_KEY);
  console.log('  ⚠ Configura REDTEAM_API_KEY en .env para persistencia.');
}

function authenticateToken(req, res, next) {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.startsWith('Bearer ') ? authHeader.slice(7) : null;
  const queryToken = req.query.token;
  const providedToken = token || queryToken;
  if (!providedToken || providedToken !== API_KEY) {
    return res.status(401).json({ error: 'Acceso no autorizado' });
  }
  next();
}

const app = express();
const server = http.createServer(app);

// ─── Security: Rate Limiting (simple in-memory) ──────────────────────────────
const rateBuckets = new Map();
function rateLimit(windowMs, max) {
  return (req, res, next) => {
    const key = req.ip + ':' + Math.floor(Date.now() / windowMs);
    const count = rateBuckets.get(key) || 0;
    if (count >= max) {
      return res.status(429).json({ error: 'Demasiadas solicitudes. Intente mas tarde.' });
    }
    rateBuckets.set(key, count + 1);
    // Cleanup old entries
    if (rateBuckets.size > 10000) {
      for (const [k] of rateBuckets) {
        if (parseInt(k.split(':').pop()) < Math.floor(Date.now() / windowMs) - 1) rateBuckets.delete(k);
      }
    }
    next();
  };
}

const globalLimiter = rateLimit(60000, 60);   // 60 req/min
const heavyLimiter = rateLimit(60000, 10);    // 10 req/min for scans/exec

// ─── Security: CORS restringido ─────────────────────────────────────────────
const ALLOWED_ORIGINS = (process.env.ALLOWED_ORIGINS || 'http://localhost:3000,http://127.0.0.1:3000,http://localhost:5000,http://127.0.0.1:5000').split(',').map(s => s.trim());

app.use((req, res, next) => {
  const origin = req.headers.origin;
  if (origin && ALLOWED_ORIGINS.includes(origin)) {
    res.header('Access-Control-Allow-Origin', origin);
    res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
    res.header('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  }
  if (req.method === 'OPTIONS') return res.sendStatus(200);
  next();
});

app.use(express.json({ limit: '4mb' }));
function appendIntercept(rec){ rec.ts=rec.ts||Date.now()/1000; rec.id=rec.id||require('crypto').createHash('sha1').update(JSON.stringify(rec)+Math.random()).digest('hex').slice(0,12);
  fs.appendFileSync(path.join(EVIDENCE,'intercept.jsonl'), JSON.stringify(rec)+'\n'); alerts.feed(rec, a=>emit('alert',a)); }

// ─── Public static (dashboard) — sin auth pero solo sirve HTML/JS/CSS ────────
app.use(express.static(path.join(__dirname, 'public')));

// ─── Rate limiting global ────────────────────────────────────────────────────
app.use('/api/', globalLimiter);

// ─── WebSocket helpers ──────────────────────────────────────────────────────
const wss = new WebSocketServer({ server });
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

const EVIDENCE = path.join(__dirname, 'evidence');
fs.mkdirSync(EVIDENCE, { recursive: true });
const REDTEAM_DIR = path.join(__dirname, 'redteam');
const SCENARIOS = ['biometric','business_logic','imei','keyhandling','multiplatform','payments','pegasus','recovery_page','rng','sidechannel','sourcesealcorp','zt_checks'];

// ─── Status (autenticado) ────────────────────────────────────────────────────
app.use((req,res,next)=>{ res.set({'X-Frame-Options':'DENY','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer'}); if(req.secure||req.headers['x-forwarded-proto']==='https') res.set('Strict-Transport-Security','max-age=31536000'); next(); });

app.get('/api/status', authenticateToken, (req, res) => {
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

// ─── Nmap + enriquecimiento automatico (autenticado) ────────────────────────
app.get('/api/nmap', authenticateToken, heavyLimiter, (req, res) => {
  const target = (req.query.target || '').trim();
  if (!target) return res.status(400).json({ error: 'target requerido' });
  // Validar formato de target (IP, CIDR o hostname)
  if (!/^[a-zA-Z0-9.\-\/]+$/.test(target)) return res.status(400).json({ error: 'target invalido' });
  runStreamed('nmap', 'nmap', ['-sT','-Pn','--top-ports','100','-T4', target], 'nmap', (buf) => {
    const ips = [...new Set((buf.match(/\b(\d{1,3}(?:\.\d{1,3}){3})\b/g) || []))]
      .filter(x => !/^(127\.|0\.0\.0\.0|255\.)/.test(x));
    emit('hosts', { ips, target });
  });
  res.json({ ok: true, target });
});

app.post('/api/nmap/stop', authenticateToken, (req, res) => {
  if (procs.nmap) { procs.nmap.kill('SIGTERM'); procs.nmap = null; }
  res.json({ ok: true });
});

// ─── Geo / Intel / IoT (autenticado) ────────────────────────────────────────
app.get('/api/geo', authenticateToken, async (req, res) => {
  const ip = (req.query.ip || '').trim();
  if (!ip) return res.status(400).json({ error: 'ip requerido' });
  res.json(await geo.lookup(ip));
});
app.get('/api/intel', authenticateToken, async (req, res) => {
  const ip = (req.query.ip || '').trim();
  if (!ip) return res.status(400).json({ error: 'ip requerido' });
  res.json(await intel.assess(ip));
});
app.get('/api/iot', authenticateToken, async (req, res) => {
  const t = (req.query.target || '').trim();
  if (!t) return res.status(400).json({ error: 'target requerido' });
  res.json(await iot.scan(t));
});

// ---- Expansión de CIDR/rango de red a lista de IPs ----
function expandCIDR(cidr) {
  const cidrMatch = cidr.match(/^(\d+)\.(\d+)\.(\d+)\.(\d+)\/(\d+)$/);
  if (!cidrMatch) {
    // IP simple o rango con guion
    const rangeMatch = cidr.match(/^(\d+)\.(\d+)\.(\d+)\.(\d+)-(\d+)\.(\d+)\.(\d+)\.(\d+)$/);
    if (rangeMatch) {
      const start = parseInt(rangeMatch[1]) * 16777216 + parseInt(rangeMatch[2]) * 65536 + parseInt(rangeMatch[3]) * 256 + parseInt(rangeMatch[4]);
      const end = parseInt(rangeMatch[5]) * 16777216 + parseInt(rangeMatch[6]) * 65536 + parseInt(rangeMatch[7]) * 256 + parseInt(rangeMatch[8]);
      const ips = [];
      for (let i = start; i <= end && ips.length < 254; i++) {
        ips.push([Math.floor(i/16777216)%256, Math.floor(i/65536)%256, Math.floor(i/256)%256, i%256].join('.'));
      }
      return ips;
    }
    // IP simple
    return [cidr.trim()];
  }
  const base = parseInt(cidrMatch[1]) * 16777216 + parseInt(cidrMatch[2]) * 65536 + parseInt(cidrMatch[3]) * 256 + parseInt(cidrMatch[4]);
  const prefix = parseInt(cidrMatch[5]);
  if (prefix < 16 || prefix > 30) return [cidr.trim()]; // /16 o más amplio es demasiado
  const mask = prefix === 0 ? 0 : (0xFFFFFFFF << (32 - prefix)) >>> 0;
  const network = (base & mask) >>> 0;
  const broadcast = (network | (~mask >>> 0)) >>> 0;
  const ips = [];
  for (let i = network + 1; i < broadcast && ips.length < 254; i++) {
    ips.push([Math.floor(i/16777216)%256, Math.floor(i/65536)%256, Math.floor(i/256)%256, i%256].join('.'));
  }
  return ips;
}

app.post('/api/iot/scan', authenticateToken, async (req, res) => {
  let ips = req.body.ips || [];
  if (typeof ips === 'string') ips = ips.split(/[\s,]+/);
  ips = ips.filter(Boolean).slice(0, 100);
  if (!ips.length) return res.status(400).json({ error: 'ips requerido (array o string separado por comas)' });
  try { res.json({ results: await iot.scanMany(ips, 6) }); }
  catch(e) { res.status(500).json({ error: e.message }); }
});

// ─── MITM (autenticado) ──────────────────────────────────────────────────────
app.post('/api/mitm/start', authenticateToken, heavyLimiter, (req, res) => {
  const out = path.join(EVIDENCE, 'traffic-' + Date.now() + '.flow');
  const addon = path.join(__dirname,'lib','mitm_addon.py');
  const jsonl = path.join(EVIDENCE,'intercept.jsonl');
  runStreamed('mitm', 'mitmdump', ['-s', addon, '-q', '-w', out, '--set', 'console_eventlog_verbosity=info'], 'mitm');
  tailJsonl(jsonl);
  res.json({ ok: true, listen: '0.0.0.0:8080', capture: out });
});
app.post('/api/mitm/stop', authenticateToken, (req, res) => { if (procs.mitm) procs.mitm.kill('SIGINT'); res.json({ ok: true }); });
app.get('/api/mitm/cert', authenticateToken, (req, res) => {
  const ca = path.join(os.homedir(), '.mitmproxy', 'mitmproxy-ca-cert.cer');
  res.json({ exists: fs.existsSync(ca) });
});

// ─── Honeypot (autenticado) ─────────────────────────────────────────────────
app.post('/api/honeypot/start', authenticateToken, (req, res) => {
  const port = parseInt(req.body && req.body.port || req.query.port || 8080);
  if (port < 1 || port > 65535) return res.status(400).json({ error: 'puerto invalido' });
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
app.post('/api/honeypot/stop', authenticateToken, (req, res) => {
  if (procs.honeypot) procs.honeypot.kill('SIGTERM');
  procs.honeypot = null;
  emit('proc', { tag: 'honeypot', state: 'stopped' });
  res.json({ ok: true });
});

// ─── Python Orchestrator (autenticado) ──────────────────────────────────────
app.post('/scan', authenticateToken, heavyLimiter, (req, res) => {
  const target = String((req.body && req.body.target) || 'build/app.apk').trim().slice(0, 500);
  const backend = String((req.body && req.body.backend) || 'http://localhost:' + PORT).trim().slice(0, 500);
  if (procs.scan) return res.status(409).json({ error: 'Escaneo en curso' });
  
  const args = [path.join(REDTEAM_DIR,'runner','orchestrator.py'),'--target',target,'--backend',backend,'--output',EVIDENCE];
  emit('proc', { tag: 'scan', state: 'running', cmd: 'python3 orchestrator.py' });
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

app.get('/latest', authenticateToken, (req, res) => {
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
  } catch(e) { res.status(500).json({ error: 'Error interno' }); }
});

app.get('/history', authenticateToken, (req, res) => {
  try {
    const files = fs.readdirSync(EVIDENCE).filter(f => f.startsWith('report-') && f.endsWith('.json')).sort().reverse();
    const history = files.map(f => {
      try {
        const d = JSON.parse(fs.readFileSync(path.join(EVIDENCE, f), 'utf-8'));
        return { finished_at: d.finished_at || f, total_findings: d.total_findings || 0, target: d.target || 'unknown' };
      } catch { return null; }
    }).filter(Boolean);
    res.json(history);
  } catch(e) { res.status(500).json({ error: 'Error interno' }); }
});

// ─── Defense playbooks (autenticado + path traversal fix) ───────────────────
app.post('/trigger-playbook', authenticateToken, (req, res) => {
  const name = path.basename(String((req.body && req.body.name) || '').trim()).replace(/[^a-zA-Z0-9_-]/g, '');
  if (!name) return res.status(400).json({ error: 'Nombre de playbook invalido' });
  const pbFile = path.join(REDTEAM_DIR, 'defense', 'playbooks', name + '.yaml');
  if (!fs.existsSync(pbFile)) return res.status(404).json({ error: 'playbook no encontrado' });
  const started = Date.now();
  const p = spawn('python3', [path.join(REDTEAM_DIR, 'runner', 'playbook_runner.py'), '--playbook', pbFile], { cwd: REDTEAM_DIR, env: { ...process.env, PYTHONPATH: REDTEAM_DIR } });
  p.stdout.on('data', d => emit('stdout', { tag: 'playbook-' + name, line: d.toString() }));
  p.stderr.on('data', d => emit('stderr', { tag: 'playbook-' + name, line: d.toString() }));
  p.on('close', code => emit('proc', { tag: 'playbook-' + name, state: code === 0 ? 'done' : 'error', code, ms: Date.now() - started }));
  res.json({ ok: true, playbook: name, message: 'Playbook ejecutandose' });
});

// ─── Escenarios individuales (autenticado + sin inyeccion Python) ────────────
app.post('/api/scenario/:name', authenticateToken, heavyLimiter, (req, res) => {
  const name = path.basename(req.params.name).replace(/[^a-zA-Z0-9_-]/g, '');
  if (!SCENARIOS.includes(name)) return res.status(400).json({ error: 'escenario no disponible' });
  const target = String((req.body && req.body.target) || 'build/app.apk').trim().slice(0, 500);
  const backend = String((req.body && req.body.backend) || 'http://localhost:' + PORT).trim().slice(0, 500);
  // SEGURIDAD: pasar argumentos en vez de interpolar strings en python3 -c
  const runnerScript = path.join(REDTEAM_DIR, 'runner', 'run_scenario.py');
  let args;
  if (fs.existsSync(runnerScript)) {
    args = [runnerScript, '--name', name, '--target', target, '--backend', backend, '--output', EVIDENCE];
  } else {
    // Fallback: crear runner temporal seguro
    const tmpRunner = path.join(REDTEAM_DIR, 'runner', '_safe_runner.py');
    fs.writeFileSync(tmpRunner, `import sys, json, argparse, importlib
parser = argparse.ArgumentParser()
parser.add_argument('--name', required=True)
parser.add_argument('--target', required=True)
parser.add_argument('--backend', required=True)
parser.add_argument('--output', required=True)
a = parser.parse_args()
sys.path.insert(0, '${REDTEAM_DIR.replace(/\\/g, '\\\\')}')
mod = importlib.import_module('scenarios.' + a.name)
results = mod.run(a.target, a.backend, a.output)
print(json.dumps(results, indent=2))
`);
    args = [tmpRunner, '--name', name, '--target', target, '--backend', backend, '--output', EVIDENCE];
  }
  emit('proc', { tag: 'scenario-' + name, state: 'running' });
  const p = spawn('python3', args, { cwd: REDTEAM_DIR, env: { ...process.env, PYTHONPATH: REDTEAM_DIR } });
  p.stdout.on('data', d => emit('stdout', { tag: 'scenario-' + name, line: d.toString() }));
  p.stderr.on('data', d => emit('stderr', { tag: 'scenario-' + name, line: d.toString() }));
  p.on('close', code => emit('proc', { tag: 'scenario-' + name, state: code === 0 ? 'done' : 'error', code }));
  res.json({ ok: true, scenario: name, message: 'Escenario ejecutandose' });
});

app.get('/api/scenarios', authenticateToken, (req, res) => res.json({ scenarios: SCENARIOS }));

// ─── IOC feed (autenticado) ──────────────────────────────────────────────────
app.get('/api/iocs', authenticateToken, (req, res) => {
  try {
    const iocFile = path.join(REDTEAM_DIR, 'data', 'iocs.json');
    if (fs.existsSync(iocFile)) res.json({ iocs: JSON.parse(fs.readFileSync(iocFile, 'utf-8')) });
    else res.json({ iocs: [], message: 'No hay IOCs cargados' });
  } catch(e) { res.json({ iocs: [], error: 'Error interno' }); }
});

// ─── MITRE ATT&CK mapping (autenticado) ─────────────────────────────────────
app.get('/api/mitre', authenticateToken, (req, res) => {
  try {
    const mitreFile = path.join(REDTEAM_DIR, 'defense', 'mitre_map.yaml');
    if (fs.existsSync(mitreFile)) res.type('text/yaml').send(fs.readFileSync(mitreFile, 'utf-8'));
    else res.json({ error: 'MITRE map no encontrado' });
  } catch(e) { res.status(500).json({ error: 'Error interno' }); }
});

// ─── Reportes (autenticado) ──────────────────────────────────────────────────
app.post('/api/report/generate', authenticateToken, (req, res) => {
  const target = String((req.body && req.body.target) || 'manual').slice(0, 200);
  const findings = Array.isArray(req.body.findings) ? req.body.findings.slice(0, 1000) : [];
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
  res.json({ ok: true, file });
});

app.get('/api/reports', authenticateToken, (req, res) => {
  res.json(fs.readdirSync(EVIDENCE).filter(f => f.endsWith('.json'))
    .map(f => ({ file: f, size: fs.statSync(path.join(EVIDENCE, f)).size }))
    .sort((a,b) => b.file.localeCompare(a.file)));
});

app.get('/api/reports/:file', authenticateToken, (req, res) => {
  const safeFile = path.basename(req.params.file);
  const fp = path.join(EVIDENCE, safeFile);
  if (!fs.existsSync(fp)) return res.status(404).json({ error: 'no existe' });
  res.download(fp);
});

// ─── /api/exec: WHITELIST de comandos seguros (autenticado) ──────────────────
const SAFE_COMMANDS = {
  'uptime': { cmd: 'uptime', args: [] },
  'disk_usage': { cmd: 'df', args: ['-h'] },
  'memory': { cmd: 'free', args: ['-m'] },
  'processes': { cmd: 'ps', args: ['aux'] },
  'hostname': { cmd: 'hostname', args: [] },
  'whoami': { cmd: 'whoami', args: [] },
  'date': { cmd: 'date', args: [] },
  'uname': { cmd: 'uname', args: ['-a'] },
};

app.post('/api/exec', authenticateToken, heavyLimiter, (req, res) => {
  const action = String(req.body.action || '').trim();
  if (!action || !SAFE_COMMANDS[action]) {
    return res.status(400).json({ error: 'Accion no permitida. Disponibles: ' + Object.keys(SAFE_COMMANDS).join(', ') });
  }
  const spec = SAFE_COMMANDS[action];
  const child = spawn(spec.cmd, spec.args, { timeout: 10000 });
  let out = '', err = '';
  child.stdout.on('data', d => out += d.toString());
  child.stderr.on('data', d => err += d.toString());
  child.on('close', code => res.json({ output: out || err || 'comando ejecutado (sin salida)', code, action }));
  child.on('error', () => res.status(500).json({ error: 'Error al ejecutar comando' }));
});

// ─── WebSocket autenticado ──────────────────────────────────────────────────
server.on('upgrade', (request, socket, head) => {
  const url = new URL(request.url, 'http://' + (request.headers.host || 'localhost'));
  const token = url.searchParams.get('token');
  if (token !== API_KEY) {
    socket.write('HTTP/1.1 401 Unauthorized\r\n\r\n');
    socket.destroy();
    return;
  }
  wss.handleUpgrade(request, socket, head, (ws) => {
    wss.emit('connection', ws, request);
  });
});


// ---- tail del jsonl de interceptacion -> WS en vivo ----
function tailJsonl(file){
  let pos=0;
  const tick=()=>{
    fs.stat(file,(e,st)=>{ if(e){return setTimeout(tick,1500)}
      if(st.size<pos)pos=0; if(st.size===pos){return setTimeout(tick,800)}
      const fd=fs.openSync(file,'r');const buf=Buffer.alloc(st.size-pos);fs.readSync(fd,buf,0,buf.length,pos);fs.closeSync(fd);pos=st.size;
      buf.toString('utf8').split('\n').filter(Boolean).forEach(line=>{ try{const _ev=JSON.parse(line); emit('intercept',_ev); alerts.feed(_ev, a=>emit('alert',a))}catch(_){} });
      setTimeout(tick,800);
    });
  }; tick();
}
app.get('/api/intercept/list', authenticateToken, (req,res)=>{
  const f=path.join(EVIDENCE,'intercept.jsonl'); if(!fs.existsSync(f))return res.json([]);
  const lines=fs.readFileSync(f,'utf8').split('\n').filter(Boolean).slice(-500).reverse();
  res.json(lines.map(l=>{try{return JSON.parse(l)}catch(_){return null}}).filter(Boolean));
});
app.post('/api/intercept/clear', authenticateToken, (req,res)=>{fs.writeFileSync(path.join(EVIDENCE,'intercept.jsonl'),'');res.json({ok:true})});

// ---- login-audit defensivo: credenciales TUYAS contra TUS dispositivos ----
app.post('/api/iot/login', authenticateToken, async (req,res)=>{
  const {ip,user,pass,port}=req.body||{};
  if(!ip||user==null||pass==null)return res.status(400).json({error:'ip,user,pass requeridos (los TUYOS, contra TUS dispositivos)'});
  const _la = await iot.loginAudit(ip,String(user),String(pass),+(port||80)); if(_la.defaultCreds||(_la.tests||[]).some(t=>t.cleartext)) appendIntercept({ _src:'audit', kind:'AUDIT', ip, ..._la }); res.json(_la);
});


wss.on('connection', ws => {
  ws.send(JSON.stringify({ type: 'hello', msg: 'sealctl conectado - todos los modulos activos' }));
  const hb = setInterval(() => { try { ws.send(JSON.stringify({ type: 'ping' })); } catch(e){} }, 15000);
  ws.on('close', () => clearInterval(hb));
});

// ─── Start ──────────────────────────────────────────────────────────────────

// ---- WS-Discovery pasivo (solo tu LAN) ----
app.post('/api/discovery/start', authenticateToken, (req,res)=>{
  const r=discovery.start(rec=>emit('discovery',rec));
  res.json({ok:true, listening:r.ok, already:!!r.already, count:r.count, note:'multicast 239.255.255.250:3702 · solo ve tu broadcast domain'});
});
app.post('/api/discovery/stop', authenticateToken, (req,res)=>res.json(discovery.stop()));
app.get('/api/discovery/list', authenticateToken, (req,res)=>res.json({running:discovery.isRunning(), devices:discovery.list()}));


app.get('/api/alerts', authenticateToken, (req,res)=>res.json(alerts.list()));
app.post('/api/alerts/clear', authenticateToken, (req,res)=>{alerts.clear();res.json({ok:true})});
app.post('/api/report/unified', authenticateToken, (req,res)=>{ const r=exporter.build({ target:req.body&&req.body.target, legacy_quirks:!!(req.body&&req.body.legacy_quirks) });
  const file='unified-'+Date.now()+'.json'; fs.writeFileSync(path.join(EVIDENCE,file), JSON.stringify(r,null,2)); res.json({ok:true,file,report:r}); });
app.get('/api/regression', authenticateToken, (req,res)=>regression.run().then(r=>res.json(r)));
app.get('/api/selftest', authenticateToken, (req,res)=>res.json(selftest()));


function selftest(){
  const V=[]; const ok=(c,d)=>V.push({case:c,st:'PASS',d}); const no=(c,d)=>V.push({case:c,st:'FAIL',d});
  let fired=[]; const cap=a=>fired.push(a);
  alerts.feed({kind:'CRED_CLEARTEXT',cleartext:true,host:'192.168.1.50',user:'admin'}, cap);
  (fired.some(a=>a.id==='cred-plaintext'&&a.severity==='critical'))?ok('alert_cred_plaintext','dispara critical'):no('alert_cred_plaintext','no disparo');
  fired=[]; alerts.feed({kind:'OUT_OF_SCOPE',host:'8.8.8.8'}, cap);
  (fired.length===0)?ok('alert_out_of_scope_silente','fuera de cerco no alerta'):no('alert_out_of_scope_silente','alerto fuera de cerco');
  const rep=exporter.build({target:'selftest'});
  (rep&&rep.by_severity&&Array.isArray(rep.findings))?ok('export_schema','tiene by_severity+findings[]'):no('export_schema','schema roto');
  const na=regression.CONTROLS.filter(c=>!c.applies);
  (na.length>0)?ok('regression_no_infla',na.length+' controles marcados applies=false'):no('regression_no_infla','todo applies=true (sospechoso)');
  const P=V.filter(x=>x.st==='PASS').length;
  return {ran_at:new Date().toISOString(),pasadas:P,totales:V.length,veredictos:V};
}


// ---- endpoints ampliados: recon, bulk, cidr, ssdp ----
// Recon combinado: DNS + geo + intel + port scan en una llamada
app.get('/api/recon', authenticateToken, heavyLimiter, async (req,res)=>{
  const target = (req.query.target || '').trim();
  if (!target) return res.status(400).json({ error: 'target requerido (IP o hostname)' });
  try {
    const geoRecon = await geo.recon(target);
    const ips = geoRecon.resolved_ips || [target];
    const results = [];
    for (const ip of ips.slice(0, 3)) {
      const [intelData, iotData] = await Promise.all([
        intel.assess(ip, { ports: null }).catch(e => ({ error: e.message })),
        iot.scan(ip, { ports: [22, 80, 443, 8080, 8443, 554, 21, 23, 3306, 6379] }).catch(e => ({ error: e.message }))
      ]);
      results.push({ ip, rdns: geoRecon.results?.find(r => r.ip === ip)?.rdns || null,
        geo: geoRecon.results?.find(r => r.ip === ip)?.geo || null,
        intel: intelData, ports: iotData });
    }
    res.json({ target, resolved_ips: ips, results });
  } catch(e) { res.status(500).json({ error: 'recon fallo: ' + e.message }); }
});

// Geo bulk: array de IPs
app.post('/api/geo/bulk', authenticateToken, async (req,res)=>{
  const ips = (req.body.ips || []).filter(Boolean).slice(0, 50);
  if (!ips.length) return res.status(400).json({ error: 'ips requerido (array, max 50)' });
  res.json({ results: await geo.lookupMany(ips, 4) });
});

// Geo CIDR: expandir y geolocalizar
app.get('/api/geo/cidr', authenticateToken, heavyLimiter, async (req,res)=>{
  const cidr = (req.query.cidr || '').trim();
  if (!cidr) return res.status(400).json({ error: 'cidr requerido (ej 192.168.1.0/24)' });
  const ips = geo.expandCidr(cidr);
  if (ips.length > 256) return res.status(400).json({ error: 'CIDR demasiado amplio (max /24)' });
  res.json({ cidr, expanded: ips.length, results: await geo.lookupMany(ips, 4) });
});

// Geo distancia entre dos IPs
app.get('/api/geo/distance', authenticateToken, async (req,res)=>{
  const ip1 = (req.query.ip1 || '').trim(), ip2 = (req.query.ip2 || '').trim();
  if (!ip1 || !ip2) return res.status(400).json({ error: 'ip1 e ip2 requeridos' });
  const [g1, g2] = await Promise.all([geo.lookup(ip1), geo.lookup(ip2)]);
  const km = geo.haversine(g1.lat, g1.lon, g2.lat, g2.lon);
  res.json({ ip1, ip2, geo1: g1, geo2: g2, distance_km: km });
});

// Intel deep: assess + TLS cert + RDAP + port correlation
app.get('/api/intel/deep', authenticateToken, heavyLimiter, async (req,res)=>{
  const ip = (req.query.ip || '').trim();
  if (!ip) return res.status(400).json({ error: 'ip requerido' });
  res.json(await intel.assess(ip, { tls: true, rdap: true }));
});

// IoT scan con puertos custom
app.post('/api/iot/scan-custom', authenticateToken, heavyLimiter, async (req,res)=>{
  const { ip, ports } = req.body;
  if (!ip) return res.status(400).json({ error: 'ip requerido' });
  const validPorts = (ports || []).filter(p => typeof p === 'number' && p > 0 && p < 65536).slice(0, 50);
  res.json(await iot.scan(ip, { ports: validPorts.length ? validPorts : undefined }));
});

// SSDP/UPnP discovery en la red local
app.get('/api/ssdp', authenticateToken, async (req,res)=>{
  try { res.json({ devices: await iot.ssdpDiscover(3000) }); }
  catch(e) { res.status(500).json({ error: 'ssdp fallo: ' + e.message }); }
});

// Geo DNS resolve (hostname -> IPs)
app.get('/api/geo/dns', authenticateToken, async (req,res)=>{
  const host = (req.query.host || '').trim();
  if (!host) return res.status(400).json({ error: 'host requerido' });
  const ips = await geo.resolveHost(host);
  const results = [];
  for (const ip of ips) { const rdns = await geo.reverse(ip); results.push({ ip, rdns, forward: host }); }
  res.json({ host, ips, results });
});


// ---- modulos fusionados del zip: c2-sinkhole, canary, ids, ndr, soar ----
// C2 sinkhole status
app.get('/api/c2-sinkhole/status', authenticateToken, (req,res)=>{
  const py = path.join(__dirname, 'redteam', 'honeypot', 'c2-sinkhole', 'sinkhole.py');
  res.json({ available: fs.existsSync(py), script: py });
});
// IDS rules (Suricata-compatible)
app.get('/api/ids/rules', authenticateToken, (req,res)=>{
  const rulesFile = path.join(__dirname, 'redteam', 'honeypot', 'network-ids', 'suricata.rules');
  if (fs.existsSync(rulesFile)) res.type('text/plain').send(fs.readFileSync(rulesFile, 'utf8'));
  else res.json({ error: 'reglas IDS no encontradas' });
});
// IDS patterns para pcap matching
app.get('/api/ids/patterns', authenticateToken, (req,res)=>{
  try {
    const { execSync } = require('child_process');
    const out = execSync('python3 -c "import sys; sys.path.insert(0,\"redteam/honeypot/network-ids\"); import ids_rules; print(json.dumps(ids_rules.PCAP_PATTERNS))"', { encoding: 'utf8', timeout: 5000 });
    res.json({ patterns: JSON.parse(out) });
  } catch(e) { res.json({ error: 'no se pudieron cargar los patrones: ' + e.message }); }
});
// Canary files - generar
app.post('/api/canary/generate', authenticateToken, (req,res)=>{
  const dir = String(req.body.dir || '/tmp/canary').slice(0, 200);
  const name = req.body.name ? String(req.body.name).slice(0, 100) : '';
  try {
    const { execSync } = require('child_process');
    const args = ['redteam/honeypot/canary-files/generate.py', '--dir', dir];
    if (name) args.push('--name', name);
    const out = execSync('python3 ' + args.map(a => '\"' + a.replace(/'/g, "'\\''") + '\"').join(' '), { encoding: 'utf8', timeout: 5000 });
    res.json({ ok: true, output: out.trim() });
  } catch(e) { res.json({ ok: false, error: e.message.slice(0, 200) }); }
});
// Notifier - enviar alerta
app.post('/api/notify', authenticateToken, (req,res)=>{
  const report = req.body.report || {};
  try {
    const { execSync } = require('child_process');
    const tmpFile = path.join(EVIDENCE, 'notify-' + Date.now() + '.json');
    fs.writeFileSync(tmpFile, JSON.stringify(report));
    const out = execSync('python3 redteam/integration/notifier.py ' + tmpFile, { encoding: 'utf8', timeout: 10000 });
    fs.unlinkSync(tmpFile);
    res.json({ ok: true, output: out.trim() });
  } catch(e) { res.json({ ok: false, error: e.message.slice(0, 200) }); }
});
// TheHive case creation
app.post('/api/thehive/case', authenticateToken, (req,res)=>{
  const finding = req.body.finding || {};
  try {
    const { execSync } = require('child_process');
    const tmpFile = path.join(EVIDENCE, 'thehive-' + Date.now() + '.json');
    fs.writeFileSync(tmpFile, JSON.stringify(finding));
    const out = execSync('python3 redteam/integration/thehive/case_creator.py ' + tmpFile, { encoding: 'utf8', timeout: 10000, env: { ...process.env, THEHIVE_URL: process.env.THEHIVE_URL || '', THEHIVE_API_KEY: process.env.THEHIVE_API_KEY || '' } });
    fs.unlinkSync(tmpFile);
    res.json({ ok: true, output: out.trim() });
  } catch(e) { res.json({ ok: false, error: e.message.slice(0, 200) }); }
});
// Semgrep rules - ver
app.get('/api/semgrep/rules', authenticateToken, (req,res)=>{
  const dir = path.join(__dirname, 'build', 'ci', 'semgrep-rules');
  if (!fs.existsSync(dir)) return res.json({ rules: [] });
  const files = fs.readdirSync(dir).filter(f => f.endsWith('.yml'));
  const rules = files.map(f => ({ name: f, content: fs.readFileSync(path.join(dir, f), 'utf8') }));
  res.json({ rules });
});
// NDR status
app.get('/api/ndr/status', authenticateToken, (req,res)=>{
  const ndrDir = path.join(__dirname, 'redteam', 'ndr');
  if (!fs.existsSync(ndrDir)) return res.json({ available: false });
  const files = fs.readdirSync(ndrDir).filter(f => f.endsWith('.py'));
  res.json({ available: true, modules: files, dir: ndrDir });
});
// SOAR status
app.get('/api/soar/status', authenticateToken, (req,res)=>{
  const soarDir = path.join(__dirname, 'redteam', 'soar');
  if (!fs.existsSync(soarDir)) return res.json({ available: false });
  const files = fs.readdirSync(soarDir).filter(f => f.endsWith('.py'));
  res.json({ available: true, modules: files, dir: soarDir });
});
// RASP status
app.get('/api/rasp/status', authenticateToken, (req,res)=>{
  const raspDir = path.join(__dirname, 'redteam', 'rasp');
  if (!fs.existsSync(raspDir)) return res.json({ available: false });
  const files = fs.readdirSync(raspDir).filter(f => f.endsWith('.py'));
  res.json({ available: true, modules: files, dir: raspDir });
});
// Deception status
app.get('/api/deception/status', authenticateToken, (req,res)=>{
  const decDir = path.join(__dirname, 'redteam', 'deception');
  if (!fs.existsSync(decDir)) return res.json({ available: false });
  const files = fs.readdirSync(decDir).filter(f => f.endsWith('.py'));
  res.json({ available: true, modules: files, dir: decDir });
});


// ---- VIDEO: snapshot, stream proxy, deteccion de URLs de video ----
// Snapshot: capturar un frame de una camara y devolverlo como imagen
app.get('/api/iot/snapshot', authenticateToken, async (req,res)=>{
  const ip = (req.query.ip || '').trim();
  const port = parseInt(req.query.port) || 80;
  const snapPath = (req.query.path || '/snapshot.cgi').slice(0, 200);
  const user = req.query.user || '';
  const pass = req.query.pass || '';
  if (!ip) return res.status(400).json({ error: 'ip requerido' });
  const http = require('http');
  const https = require('https');
  const proto = (port === 443 || port === 8443) ? https : http;
  let responded = false;
  const safeJson = (code, obj) => { if (!responded && !res.headersSent) { responded = true; res.status(code).json(obj); } };
  try {
    const headers = { 'User-Agent': 'sealctl-snapshot/1.0' };
    if (user && pass) headers['Authorization'] = 'Basic ' + Buffer.from(user + ':' + pass).toString('base64');
    const reqOpts = { host: ip, port, path: snapPath, timeout: 5000, headers, rejectUnauthorized: false };
    const upstreamReq = proto.get(reqOpts, r2 => {
      const ct = r2.headers['content-type'] || '';
      const chunks = [];
      r2.on('data', d => { chunks.push(d); if (Buffer.concat(chunks).length > 2000000) r2.destroy(); });
      r2.on('end', () => {
        const buf = Buffer.concat(chunks);
        if (responded) return;
        responded = true;
        if (ct.startsWith('image/')) {
          res.set('Content-Type', ct);
          res.set('Cache-Control', 'no-cache, no-store');
          res.send(buf);
        } else if (ct.startsWith('text/') || ct.includes('json') || ct.includes('html')) {
          res.json({ ok: false, content_type: ct, length: buf.length, preview: buf.toString('utf8').slice(0, 200) });
        } else if (buf.length > 0) {
          // Intentar como imagen JPEG
          res.set('Content-Type', 'image/jpeg');
          res.set('Cache-Control', 'no-cache, no-store');
          res.send(buf);
        } else {
          res.json({ ok: false, error: 'respuesta vacia' });
        }
      });
      r2.on('error', e => safeJson(502, { error: 'camara no respondio: ' + e.message }));
    });
    upstreamReq.on('error', e => safeJson(502, { error: 'conexion fallida: ' + e.message }));
    upstreamReq.on('timeout', function() { this.destroy(); safeJson(504, { error: 'timeout' }); });
  } catch(e) { safeJson(500, { error: e.message }); }
});

// Stream proxy: redirige MJPEG stream desde la camara al cliente (evita CORS)
app.get('/api/iot/stream', authenticateToken, (req,res)=>{
  const ip = (req.query.ip || '').trim();
  const port = parseInt(req.query.port) || 80;
  const streamPath = (req.query.path || '/mjpg/video.mjpg').slice(0, 200);
  const user = req.query.user || '';
  const pass = req.query.pass || '';
  if (!ip) return res.status(400).json({ error: 'ip requerido' });
  const http = require('http');
  const https = require('https');
  const proto = (port === 443 || port === 8443) ? https : http;
  const headers = { 'User-Agent': 'sealctl-stream/1.0' };
  if (user && pass) headers['Authorization'] = 'Basic ' + Buffer.from(user + ':' + pass).toString('base64');
  let headersSent = false;
  const safeJson = (code, obj) => { if (!headersSent && !res.headersSent) { res.status(code).json(obj); } else { try { res.end(); } catch(e){} } };
  const upstream = proto.request({ host: ip, port, path: streamPath, method: 'GET', headers, rejectUnauthorized: false, timeout: 30000 }, upstream_res => {
    const ct = upstream_res.headers['content-type'] || '';
    if (!ct.includes('multipart') && !ct.includes('image/') && !ct.includes('video/') && !ct.includes('octet-stream')) {
      upstream_res.destroy();
      return safeJson(400, { error: 'el endpoint no retorna video/stream (content-type: ' + ct + ')' });
    }
    headersSent = true;
    res.set('Content-Type', ct || 'multipart/x-mixed-replace; boundary=--BoundaryString');
    res.set('Cache-Control', 'no-cache, no-store');
    res.set('Connection', 'keep-alive');
    upstream_res.pipe(res);
    req.on('close', () => { try { upstream_res.destroy(); } catch(e){} });
  });
  upstream.on('error', e => safeJson(502, { error: 'stream fallido: ' + e.message }));
  upstream.on('timeout', () => { upstream.destroy(); safeJson(504, { error: 'stream timeout' }); });
  upstream.end();
});

// Detección de URLs de video disponibles para una IP — prueba MULTIPLES PUERTOS
app.get('/api/iot/video-urls', authenticateToken, async (req,res)=>{
  const ip = (req.query.ip || '').trim();
  if (!ip) return res.status(400).json({ error: 'ip requerido' });
  const http = require('http');
  const https = require('https');
  const user = req.query.user || '';
  const pass = req.query.pass || '';
  const authHdr = (user && pass) ? { 'Authorization': 'Basic ' + Buffer.from(user + ':' + pass).toString('base64') } : {};

  // Puertos web a probar para cada path de video
  const WEB_PORTS = [80, 81, 8080, 8000, 8888, 8443, 85, 8081, 8001, 8088, 9000];

  // Paths de video por vendor — sin puerto fijo, se prueba en todos los WEB_PORTS
  const VIDEO_PATHS = [
    { path: '/mjpg/video.mjpg', type: 'mjpeg', vendor: 'Axis' },
    { path: '/video/mjpg.cgi', type: 'mjpeg', vendor: 'Foscam' },
    { path: '/cgi-bin/viewer/video.jpg', type: 'snapshot', vendor: 'Axis' },
    { path: '/snapshot.cgi', type: 'snapshot', vendor: 'Generic' },
    { path: '/cgi-bin/snapshot.cgi', type: 'snapshot', vendor: 'Dahua' },
    { path: '/snapshot.jpg', type: 'snapshot', vendor: 'Generic' },
    { path: '/image/jpeg.cgi', type: 'snapshot', vendor: 'Edimax' },
    { path: '/ISAPI/Streaming/channels/101/picture', type: 'snapshot', vendor: 'Hikvision' },
    { path: '/ISAPI/Streaming/channels/102/picture', type: 'snapshot', vendor: 'Hikvision' },
    { path: '/ISAPI/Streaming/channels/1/picture', type: 'snapshot', vendor: 'Hikvision' },
    { path: '/ISAPI/Streaming/channels/101/httppreview', type: 'mjpeg', vendor: 'Hikvision' },
    { path: '/ISAPI/Streaming/channels/1/httppreview', type: 'mjpeg', vendor: 'Hikvision' },
    { path: '/live/cam.html', type: 'html', vendor: 'Generic' },
    { path: '/mjpg/1/video.mjpg', type: 'mjpeg', vendor: 'Axis' },
    { path: '/stream/video.mjpeg', type: 'mjpeg', vendor: 'Generic' },
    { path: '/cgi-bin/viewer/video.mjpg', type: 'mjpeg', vendor: 'Generic' },
    { path: '/videostream.cgi', type: 'mjpeg', vendor: 'Foscam' },
    { path: '/videostream.jpg', type: 'snapshot', vendor: 'Foscam' },
    { path: '/goform/video', type: 'mjpeg', vendor: 'Wansview' },
    { path: '/video.cgi', type: 'mjpeg', vendor: 'Generic' },
    { path: '/video.mjpg', type: 'mjpeg', vendor: 'Generic' },
    { path: '/cgi-bin/view/image', type: 'snapshot', vendor: 'Generic' },
    { path: '/cgi-bin/viewer/view.jpg', type: 'snapshot', vendor: 'Vivotek' },
    { path: '/cgi-bin/camcam/cam.cgi', type: 'snapshot', vendor: 'Bosch' },
    { path: '/onvif/device_service', type: 'onvif', vendor: 'ONVIF' },
    { path: '/doc/page/login.asp', type: 'html', vendor: 'Hikvision web' },
    { path: '/doc/page/preview.asp', type: 'html', vendor: 'Hikvision preview' },
    // Dahua
    { path: '/cgi-bin/snapshot.cgi?channel=1', type: 'snapshot', vendor: 'Dahua' },
    { path: '/cgi-bin/snapshot.cgi?channel=1&subtype=0', type: 'snapshot', vendor: 'Dahua' },
    // Amcrest
    { path: '/cgi-bin/snapshot.cgi?1', type: 'snapshot', vendor: 'Amcrest' },
    // Xiongmai
    { path: '/snap.jpg', type: 'snapshot', vendor: 'Xiongmai' },
    { path: '/tmpfs/snap.jpg', type: 'snapshot', vendor: 'Xiongmai' },
    { path: '/webcapture.jpg', type: 'snapshot', vendor: 'Xiongmai' },
    // Generic MJPEG streams
    { path: '/stream?topic=/cam01/image', type: 'mjpeg', vendor: 'ROS/Generic' },
    { path: '/?action=stream', type: 'mjpeg', vendor: 'OctoPrint/Generic' },
    { path: '/video/feed', type: 'mjpeg', vendor: 'Generic' },
    { path: '/mjpeg', type: 'mjpeg', vendor: 'Generic' },
    { path: '/cam.mjpg', type: 'mjpeg', vendor: 'Generic' },
    { path: '/stream.mjpg', type: 'mjpeg', vendor: 'Generic' },
  ];

  const results = [];
  const probes = [];

  // Generar todas las combinaciones path × puerto
  for (const vp of VIDEO_PATHS) {
    for (const port of WEB_PORTS) {
      probes.push({ ...vp, port });
    }
  }

  // Limitar concurrencia para no saturar
  const CONC = 10;
  let idx = 0;
  const worker = async () => {
    while (idx < probes.length) {
      const vp = probes[idx++];
      await new Promise(resolve => {
        const proto = (vp.port === 443 || vp.port === 8443) ? https : http;
        const reqOpts = {
          host: ip, port: vp.port, path: vp.path, method: 'GET',
          timeout: 2500,
          headers: { ...authHdr, 'User-Agent': 'sealctl-probe/1.0' },
          rejectUnauthorized: false
        };
        const r = proto.request(reqOpts, resp => {
          const ct = resp.headers['content-type'] || '';
          const sc = resp.statusCode;
          resp.destroy();
          if (sc === 200 || sc === 401) {
            const isVideo = ct.includes('image') || ct.includes('multipart') || ct.includes('video') || ct.includes('octet-stream');
            const isHtml = ct.includes('text/html');
            const isAuth = sc === 401;
            if (isVideo || isHtml || isAuth) {
              const streamUrl = isVideo
                ? `/api/iot/stream?ip=${encodeURIComponent(ip)}&port=${vp.port}&path=${encodeURIComponent(vp.path)}${user ? '&user=' + encodeURIComponent(user) : ''}${pass ? '&pass=' + encodeURIComponent(pass) : ''}`
                : null;
              const snapshotUrl = (isVideo && (vp.type === 'snapshot' || vp.type === 'mjpeg'))
                ? `/api/iot/snapshot?ip=${encodeURIComponent(ip)}&port=${vp.port}&path=${encodeURIComponent(vp.path)}${user ? '&user=' + encodeURIComponent(user) : ''}${pass ? '&pass=' + encodeURIComponent(pass) : ''}`
                : null;
              results.push({
                ...vp, status: sc, content_type: ct, available: true,
                needs_auth: isAuth,
                stream_url: streamUrl,
                snapshot_url: snapshotUrl
              });
            }
          }
          resolve();
        });
        r.on('error', () => resolve());
        r.on('timeout', () => { r.destroy(); resolve(); });
        r.end();
      });
    }
  };
  await Promise.all(Array.from({ length: CONC }, () => worker()));

  // Also check RTSP on multiple ports
  const RTSP_PORTS = [554, 8554, 10554, 15554];
  for (const rtspPort of RTSP_PORTS) {
    try {
      const net = require('net');
      const rtspResult = await new Promise(resolve => {
        const sock = net.createConnection({ host: ip, port: rtspPort }, () => {
          sock.write('OPTIONS rtsp://' + ip + ':' + rtspPort + '/ RTSP/1.0\r\nCSeq: 1\r\n\r\n');
          let buf = '';
          sock.on('data', d => {
            buf += d.toString();
            if (/RTSP\/1\.0 \d+/.test(buf)) {
              sock.destroy();
              resolve({ available: true, url: 'rtsp://' + ip + ':' + rtspPort + '/' });
            }
          });
          sock.setTimeout(2000, () => {
            sock.destroy();
            resolve(buf.includes('RTSP') ? { available: true, url: 'rtsp://' + ip + ':' + rtspPort + '/' } : null);
          });
        });
        sock.on('error', () => resolve(null));
        sock.setTimeout(2500, () => { try { sock.destroy(); } catch(e){} resolve(null); });
      });
      if (rtspResult && rtspResult.available) {
        results.push({ path: '/', port: rtspPort, type: 'rtsp', vendor: 'RTSP', available: true,
          rtsp_url: rtspResult.url, stream_url: null, snapshot_url: null,
          note: 'RTSP requiere VLC o player externo. URL: ' + rtspResult.url });
        break; // un RTSP es suficiente
      }
    } catch(e) {}
  }

  // Deduplicar por port+path
  const seen = new Set();
  const deduped = results.filter(r => {
    const key = r.port + ':' + r.path;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  // Ordenar: snapshot > mjpeg > html > rtsp
  const order = { snapshot: 0, mjpeg: 1, onvif: 2, html: 3, rtsp: 4 };
  deduped.sort((a, b) => (order[a.type] || 5) - (order[b.type] || 5));

  res.json({
    ip, video_sources: deduped, total: deduped.length,
    ports_probed: WEB_PORTS.length,
    paths_probed: VIDEO_PATHS.length,
    total_probes: probes.length,
    note: deduped.length > 0
      ? deduped.length + ' fuente(s) de video disponible(s)'
      : 'no se detectaron fuentes de video HTTP (probaron ' + probes.length + ' combinaciones en ' + WEB_PORTS.length + ' puertos)'
  });
});

// ---- expediente de reapertura (casefile) ----
app.get('/api/casefile', authenticateToken, async (req,res)=>{
  try { const r = await casefile.run(req.query.path); res.json(r); }
  catch(e) { res.status(500).json({error:'casefile falló: '+e.message}); }
});
app.get('/api/casefile/apk', authenticateToken, (req,res)=>{
  res.json(casefile.probeApk());
});
app.get('/api/casefile/sanitize', authenticateToken, (req,res)=>{
  const raw = req.query.url || '';
  const clean = casefile.sanitizeUrl(raw);
  res.json({ raw, sanitized: clean, changed: clean !== raw.trim() });
});


// Escaneo de red completo — acepta CIDR (192.168.1.0/24) o rango (192.168.1.1-192.168.1.254)
app.post('/api/iot/scan-network', authenticateToken, heavyLimiter, async (req, res) => {
  const cidr = (req.body.cidr || req.body.network || req.body.range || '').trim();
  if (!cidr) return res.status(400).json({ error: 'cidr requerido (ej: 192.168.1.0/24 o 192.168.1.1-192.168.1.254)' });
  const ips = expandCIDR(cidr);
  if (ips.length === 0) return res.status(400).json({ error: 'rango invalido' });
  if (ips.length > 254) return res.status(400).json({ error: 'maximo 254 IPs por escaneo' });
  try {
    const results = await iot.scanMany(ips, 15, { fast: true });
    // Filtrar solo los que tienen al menos un puerto abierto
    const active = results.filter(r => r.ports_open && r.ports_open.length > 0);
    const cameras = active.filter(r => r.type === 'camera' || r.type === 'radio/voip' || r.vendor);
    const allOpen = active;
    res.json({
      network: cidr,
      total_ips: ips.length,
      total_scanned: results.length,
      cameras_found: cameras.length,
      devices_with_open_ports: allOpen.length,
      cameras: cameras,
      all_devices: allOpen,
      full_results: results
    });
  } catch(e) { res.status(500).json({ error: e.message }); }
});

// Auto-detectar red local del servidor y escanear
app.post('/api/iot/scan-local', authenticateToken, heavyLimiter, async (req, res) => {
  const os = require('os');
  const ifaces = os.networkInterfaces();
  let localIP = null, localMask = null;
  for (const name in ifaces) {
    for (const iface of ifaces[name]) {
      if (iface.family === 'IPv4' && !iface.internal) {
        localIP = iface.address;
        localMask = iface.netmask || '255.255.255.0';
        break;
      }
    }
    if (localIP) break;
  }
  if (!localIP) return res.status(500).json({ error: 'no se pudo detectar IP local' });
  // Construir CIDR desde IP + mascara
  const parts = localIP.split('.').map(Number);
  // Asumir /24 si la mascara es 255.255.255.0
  let prefix = 24;
  if (localMask === '255.255.0.0') prefix = 16;
  else if (localMask === '255.255.255.128') prefix = 25;
  else if (localMask === '255.255.255.0') prefix = 24;
  else if (localMask === '255.255.254.0') prefix = 23;
  const cidr = parts[0] + '.' + parts[1] + '.' + parts[2] + '.0/' + prefix;
  const ips = expandCIDR(cidr);
  if (ips.length === 0) return res.status(500).json({ error: 'no se pudo expandir CIDR: ' + cidr });
  try {
    const results = await iot.scanMany(ips, 15, { fast: true });
    const active = results.filter(r => r.ports_open && r.ports_open.length > 0);
    const cameras = active.filter(r => r.type === 'camera' || r.type === 'radio/voip' || r.vendor);
    const allOpen = active;
    res.json({
      detected_ip: localIP,
      detected_mask: localMask,
      detected_cidr: cidr,
      total_ips: ips.length,
      total_scanned: results.length,
      cameras_found: cameras.length,
      devices_with_open_ports: allOpen.length,
      cameras: cameras,
      all_devices: allOpen,
      full_results: results
    });
  } catch(e) { res.status(500).json({ error: e.message }); }
});



// ── ENDPOINTS DEL DASHBOARD (stub/implementación ligera para Termux) ────────────

// Settings — configuración del frontend
let _settings = { api_url: '', interval: 15, scan_on_startup: false, notify_slack: false, slack_webhook: '' };
app.get('/api/settings', authenticateToken, (req, res) => res.json(_settings));
app.post('/api/settings', authenticateToken, (req, res) => {
  if (req.body) _settings = Object.assign(_settings, req.body);
  res.json({ ok: true });
});

// Services — estado de módulos del backend
app.get('/api/services', authenticateToken, (req, res) => {
  res.json([
    { name: 'geo', status: 'running', label: 'Geo Intel' },
    { name: 'intel', status: 'running', label: 'Threat Intel' },
    { name: 'iot', status: 'running', label: 'IoT Scanner' },
    { name: 'mitm', status: procs.mitm ? 'running' : 'stopped', label: 'MITM Proxy' },
    { name: 'honeypot', status: procs.honeypot ? 'running' : 'stopped', label: 'Honeypot' },
    { name: 'nmap', status: 'stopped', label: 'Nmap' },
  ]);
});
app.post('/api/services/start', authenticateToken, (req, res) => res.json({ ok: false, message: 'use endpoint especifico del modulo' }));
app.post('/api/services/stop', authenticateToken, (req, res) => res.json({ ok: false, message: 'use endpoint especifico del modulo' }));
app.post('/api/services/restart', authenticateToken, (req, res) => res.json({ ok: false, message: 'use endpoint especifico del modulo' }));
app.post('/api/services/start-all', authenticateToken, (req, res) => res.json({ ok: true }));
app.post('/api/services/stop-all', authenticateToken, (req, res) => { for (const k in procs) if (procs[k]) try { procs[k].kill(); } catch(e){} res.json({ ok: true }); });
app.get('/api/services/:name/logs', authenticateToken, (req, res) => res.json(['no logs available for ' + req.params.name]));

// Resources — CPU/memoria del sistema
app.get('/api/resources', authenticateToken, (req, res) => {
  const os = require('os');
  const total = os.totalmem();
  const free = os.freemem();
  const cpus = os.cpus();
  const load = os.loadavg();
  res.json({
    cpu_percent: Math.round((load[0] / cpus.length) * 100),
    cpu_cores: cpus.length,
    memory_total: total,
    memory_used: total - free,
    memory_percent: Math.round(((total - free) / total) * 100),
    uptime: os.uptime(),
    load_avg: load
  });
});

// Scan status — estado del escaneo de reportes
app.get('/api/scan/status', authenticateToken, (req, res) => res.json({ running: false, progress: '' }));

// Config files — listar/editar archivos de configuración
app.get('/api/config', authenticateToken, (req, res) => {
  try {
    const files = fs.readdirSync(__dirname).filter(f => f.endsWith('.js') || f.endsWith('.json') || f.endsWith('.md'));
    res.json(files.map(f => ({ name: f, path: f, size: fs.statSync(path.join(__dirname, f)).size })));
  } catch(e) { res.json([]); }
});
app.get('/api/config/read', authenticateToken, (req, res) => {
  const p = String(req.query.path || '').replace(/\.\./g, '').slice(0, 200);
  if (!p) return res.status(400).json({ error: 'path requerido' });
  try {
    const fp = path.join(__dirname, p);
    if (!fp.startsWith(__dirname)) return res.status(403).json({ error: 'acceso denegado' });
    res.json({ content: fs.readFileSync(fp, 'utf8').slice(0, 50000), path: p });
  } catch(e) { res.status(404).json({ error: 'archivo no encontrado' }); }
});
app.post('/api/config/write', authenticateToken, (req, res) => {
  const p = String(req.body?.path || '').replace(/\.\./g, '').slice(0, 200);
  if (!p) return res.status(400).json({ error: 'path requerido' });
  try {
    const fp = path.join(__dirname, p);
    if (!fp.startsWith(__dirname)) return res.status(403).json({ error: 'acceso denegado' });
    fs.writeFileSync(fp, String(req.body?.content || '').slice(0, 100000));
    res.json({ ok: true });
  } catch(e) { res.status(500).json({ error: e.message }); }
});

// Honeypot — toggle y rotate
app.get('/api/honeypot', authenticateToken, (req, res) => {
  res.json({ running: !!procs.honeypot, tokens: 0, port: 0 });
});
app.post('/api/honeypot/toggle', authenticateToken, (req, res) => {
  res.json({ running: !!procs.honeypot, message: 'use /api/honeypot/start o /api/honeypot/stop' });
});
app.post('/api/honeypot/rotate', authenticateToken, (req, res) => {
  res.json({ ok: true, tokens_deployed: 0 });
});

// SOAR — DAGs
let _dags = [];
app.get('/api/soar/dags', authenticateToken, (req, res) => res.json(_dags));
app.post('/api/soar/dags', authenticateToken, (req, res) => {
  const id = 'dag_' + Date.now();
  _dags.push(Object.assign({ id }, req.body || {}));
  res.json({ ok: true, id });
});
app.post('/api/soar/dry-run', authenticateToken, (req, res) => {
  res.json({ ok: true, steps: _dags.map(d => d.id || 'unknown'), count: _dags.length });
});

// TIP — IOCs
let _iocs = [];
app.get('/api/tip/iocs', authenticateToken, (req, res) => res.json(_iocs));
app.post('/api/tip/iocs', authenticateToken, (req, res) => {
  const id = 'ioc_' + Date.now();
  _iocs.push(Object.assign({ id, created: new Date().toISOString() }, req.body || {}));
  res.json({ ok: true, id });
});
app.delete('/api/tip/iocs/:id', authenticateToken, (req, res) => {
  _iocs = _iocs.filter(i => i.id !== req.params.id);
  res.json({ ok: true });
});
app.post('/api/tip/update', authenticateToken, (req, res) => {
  res.json({ ok: true, iocs_loaded: _iocs.length });
});
app.post('/api/tip/import-stix', authenticateToken, (req, res) => {
  res.json({ ok: true, imported: 0 });
});

// RASP — devices
let _raspDevices = [];
app.get('/api/rasp/devices', authenticateToken, (req, res) => res.json(_raspDevices));
app.post('/api/rasp/devices', authenticateToken, (req, res) => {
  const id = 'dev_' + Date.now();
  _raspDevices.push(Object.assign({ id }, req.body || {}));
  res.json({ ok: true, id });
});
app.delete('/api/rasp/devices/:id', authenticateToken, (req, res) => {
  _raspDevices = _raspDevices.filter(d => d.id !== req.params.id);
  res.json({ ok: true });
});

// Terminal — ejecutar comandos
app.post('/api/terminal', authenticateToken, heavyLimiter, (req, res) => {
  const cmd = String(req.body?.command || '').slice(0, 500);
  if (!cmd) return res.status(400).json({ error: 'command requerido' });
  try {
    const { execSync } = require('child_process');
    const stdout = execSync(cmd, { timeout: 10000, encoding: 'utf8', maxBuffer: 100000 });
    res.json({ stdout: stdout.slice(0, 50000), stderr: '', code: 0 });
  } catch(e) {
    res.json({ stdout: '', stderr: String(e.stderr || e.message).slice(0, 50000), code: e.status || 1 });
  }
});


server.listen(PORT, HOST, () => {
  console.log('\\n  SealCtl v2.1 (hardened) en http://' + HOST + ':' + PORT);
  console.log('  Recon: geo/intel/iot/nmap/mitm | Defense: playbooks/scenarios | Honeypot');
  console.log('  Auth: Bearer token requerido en todas las rutas /api/*');
  console.log('  ' + SCENARIOS.length + ' escenarios Python | Binding: ' + HOST + '\n');
});
