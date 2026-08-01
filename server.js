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
const ALLOWED_ORIGINS = (process.env.ALLOWED_ORIGINS || 'http://localhost:3000,http://127.0.0.1:3000').split(',').map(s => s.trim());

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
app.post('/api/iot/scan', authenticateToken, async (req, res) => {
  const ips = (req.body.ips || []).filter(Boolean).slice(0, 100);
  if (!ips.length) return res.status(400).json({ error: 'ips requerido' });
  res.json({ results: await iot.scanMany(ips, 6) });
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

server.listen(PORT, HOST, () => {
  console.log('\\n  SealCtl v2.1 (hardened) en http://' + HOST + ':' + PORT);
  console.log('  Recon: geo/intel/iot/nmap/mitm | Defense: playbooks/scenarios | Honeypot');
  console.log('  Auth: Bearer token requerido en todas las rutas /api/*');
  console.log('  ' + SCENARIOS.length + ' escenarios Python | Binding: ' + HOST + '\n');
});
