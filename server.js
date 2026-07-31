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

app.use(express.json({ limit: '2mb' }));
app.use(express.static(path.join(__dirname, 'public')));

function emit(type, payload) {
  const msg = JSON.stringify({ type, t: new Date().toISOString(), ...payload });
  wss.clients.forEach(c => { if (c.readyState === 1) c.send(msg); });
}
const procs = { nmap: null, mitm: null };

function runStreamed(name, cmd, args, tag, onDone) {
  if (procs[name]) { try { procs[name].kill('SIGTERM'); } catch (e) {} }
  emit('proc', { tag, state: 'running', cmd: `${cmd} ${args.join(' ')}` });
  const started = Date.now(); let buf = '';
  const p = spawn(cmd, args, { env: { ...process.env, TERM: 'dumb' } });
  procs[name] = p;
  p.stdout.on('data', d => { const s = d.toString(); buf += s; emit('stdout', { tag, line: s }); });
  p.stderr.on('data', d => emit('stderr', { tag, line: d.toString() }));
  p.on('close', code => { procs[name] = null; emit('proc', { tag, state: code === 0 ? 'done' : 'error', code, ms: Date.now() - started }); if (onDone) onDone(buf, code); });
  p.on('error', e => emit('proc', { tag, state: 'error', error: e.message }));
  return p;
}

app.get('/api/status', (req, res) => {
  const ifaces = os.networkInterfaces(); let ip = '127.0.0.1';
  for (const k in ifaces) for (const i of ifaces[k]) if (i.family === 'IPv4' && !i.internal) ip = i.address;
  res.json({ node: os.hostname(), platform: os.platform(), arch: os.arch(), uptime_s: Math.floor(os.uptime()),
    load: os.loadavg()[0], mem_free_mb: Math.round(os.freemem() / 1e6), mem_total_mb: Math.round(os.totalmem() / 1e6),
    ip, port: PORT, nmap: !!procs.nmap, mitm: !!procs.mitm,
    reports: fs.readdirSync(EVIDENCE).filter(f => f.endsWith('.json')).length });
});

// nmap + enriquecimiento automático de IPs al terminar
app.get('/api/nmap', (req, res) => {
  const target = (req.query.target || '').trim();
  if (!target) return res.status(400).json({ error: 'target requerido' });
  runStreamed('nmap', 'nmap', ['-sT', '-Pn', '--top-ports', '100', '-T4', target], 'nmap', (buf) => {
    const ips = [...new Set((buf.match(/\b(\d{1,3}(?:\.\d{1,3}){3})\b/g) || []))]
      .filter(x => !/^(127\.|0\.0\.0\.0|255\.)/.test(x));
    emit('hosts', { ips, target }); // el frontend enriquece cada una (geo+intel) y pinta el mapa
  });
  res.json({ ok: true, target });
});

// geo / intel / iot : endpoints reales
app.get('/api/geo', async (req, res) => res.json(await geo.lookup((req.query.ip || '').trim())));
app.get('/api/intel', async (req, res) => res.json(await intel.assess((req.query.ip || '').trim())));
app.get('/api/iot', async (req, res) => {
  const t = (req.query.target || '').trim();
  if (!t) return res.status(400).json({ error: 'target requerido' });
  res.json(await iot.scan(t));
});
app.post('/api/iot/scan', async (req, res) => {
  const ips = (req.body.ips || []).filter(Boolean);
  res.json(await iot.scanMany(ips, 6));
});

// mitm
app.post('/api/mitm/start', (req, res) => {
  const out = path.join(EVIDENCE, `traffic-${Date.now()}.flow`);
  runStreamed('mitm', 'mitmdump', ['-q', '-w', out, '--set', 'console_eventlog_verbosity=info'], 'mitm');
  res.json({ ok: true, listen: '0.0.0.0:8080', capture: out });
});
app.post('/api/mitm/stop', (req, res) => { if (procs.mitm) procs.mitm.kill('SIGINT'); res.json({ ok: true }); });
app.get('/api/mitm/cert', (req, res) => {
  const ca = path.join(os.homedir(), '.mitmproxy', 'mitmproxy-ca-cert.cer');
  res.json({ exists: fs.existsSync(ca), path: ca });
});

// reportes (schema compatible con redteam-*.json)
app.post('/api/report/generate', (req, res) => {
  const { target = 'manual', findings = [] } = req.body;
  const by = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
  findings.forEach(f => { if (by[f.severity] != null) by[f.severity]++; });
  const report = { started_at: new Date(Date.now() - 1000).toISOString(), finished_at: new Date().toISOString(),
    elapsed_seconds: 1.0, total_findings: findings.length, by_severity: by, findings, errors: [],
    target, backend: 'sealctl@termux', scenarios_run: new Set(findings.map(f => f.scenario)).size };
  const file = `sealctl-${Date.now()}.json`;
  fs.writeFileSync(path.join(EVIDENCE, file), JSON.stringify(report, null, 2));
  emit('report', { file, total: findings.length, by });
  res.json({ ok: true, file, report });
});
app.get('/api/reports', (req, res) => {
  res.json(fs.readdirSync(EVIDENCE).filter(f => f.endsWith('.json'))
    .map(f => ({ file: f, size: fs.statSync(path.join(EVIDENCE, f)).size })).sort((a, b) => b.file.localeCompare(a.file)));
});
app.get('/api/reports/:file', (req, res) => {
  const fp = path.join(EVIDENCE, path.basename(req.params.file));
  if (!fs.existsSync(fp)) return res.status(404).json({ error: 'no existe' });
  res.download(fp);
});

wss.on('connection', ws => {
  ws.send(JSON.stringify({ type: 'hello', msg: 'sealctl conectado' }));
  const hb = setInterval(() => { try { ws.send(JSON.stringify({ type: 'ping' })); } catch (e) {} }, 15000);
  ws.on('close', () => clearInterval(hb));
});

server.listen(PORT, '0.0.0.0', () => console.log(`\n  sealctl en http://localhost:${PORT}\n`));