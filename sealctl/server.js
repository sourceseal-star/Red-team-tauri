#!/usr/bin/env node
/**
 * SealCtl — Console REST API Server
 * Une geo.js + intel.js + iot.js en una API HTTP con SSE streaming.
 * Stdlib only — sin dependencias npm.
 */
const http = require('http');
const fs = require('fs');
const path = require('path');
const url = require('url');
const { lookup, isPrivate } = require('./lib/geo');
const { assess } = require('./lib/intel');
const { scan, scanMany } = require('./lib/iot');

const PORT = process.env.SEALCTL_PORT || 4000;
const PUBLIC_DIR = path.join(__dirname, 'public');

// ─── CORS + helpers ──────────────────────────────────────────────────────────
function cors(res) {
  res.setHeader('Access-Control-Allow-Origin', process.env.ALLOWED_ORIGINS || 'http://localhost:5173');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
}
function json(res, code, data) {
  cors(res);
  res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(data, null, 2));
}
function parseBody(req) {
  return new Promise(resolve => {
    let b = ''; req.on('data', d => { b += d; if (b.length > 1e6) req.destroy(); });
    req.on('end', () => { try { resolve(JSON.parse(b || '{}')); } catch { resolve({}); } });
    req.on('error', () => resolve({}));
  });
}

// ─── Routes ──────────────────────────────────────────────────────────────────
const server = http.createServer(async (req, res) => {
  const u = url.parse(req.url, true);
  const p = u.pathname;

  // OPTIONS preflight
  if (req.method === 'OPTIONS') { cors(res); res.writeHead(204); res.end(); return; }

  // Static files
  if (req.method === 'GET' && (p === '/' || p === '/index.html')) {
    const f = path.join(PUBLIC_DIR, 'index.html');
    if (fs.existsSync(f)) { cors(res); res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' }); fs.createReadStream(f).pipe(res); return; }
    json(res, 404, { error: 'index.html no encontrado' }); return;
  }
  if (req.method === 'GET' && p.startsWith('/public/')) {
    const f = path.join(PUBLIC_DIR, p.replace('/public/', ''));
    if (fs.existsSync(f)) { cors(res); res.writeHead(200, { 'Content-Type': 'application/octet-stream' }); fs.createReadStream(f).pipe(res); return; }
    json(res, 404, { error: 'archivo no encontrado' }); return;
  }

  // ── /api/geo?ip=X ──────────────────────────────────────────────────────────
  if (req.method === 'GET' && p === '/api/geo') {
    const ip = u.query.ip;
    if (!ip) return json(res, 400, { error: 'param ?ip= requerido' });
    const r = await lookup(ip);
    return json(res, 200, r);
  }

  // ── /api/intel?ip=X ────────────────────────────────────────────────────────
  if (req.method === 'GET' && p === '/api/intel') {
    const ip = u.query.ip;
    if (!ip) return json(res, 400, { error: 'param ?ip= requerido' });
    const r = await assess(ip);
    return json(res, 200, r);
  }

  // ── /api/iot?ip=X ──────────────────────────────────────────────────────────
  if (req.method === 'GET' && p === '/api/iot') {
    const ip = u.query.ip;
    if (!ip) return json(res, 400, { error: 'param ?ip= requerido' });
    const r = await scan(ip);
    return json(res, 200, r);
  }

  // ── /api/full?ip=X (geo + intel + iot combinado) ─────────────────────────────
  if (req.method === 'GET' && p === '/api/full') {
    const ip = u.query.ip;
    if (!ip) return json(res, 400, { error: 'param ?ip= requerido' });
    const [geoR, intelR, iotR] = await Promise.all([lookup(ip), assess(ip), scan(ip)]);
    return json(res, 200, { ip, geo: geoR, intel: intelR, iot: iotR });
  }

  // ── /api/scan-batch (POST { ips: [...] }) ───────────────────────────────────
  if (req.method === 'POST' && p === '/api/scan-batch') {
    const body = await parseBody(req);
    const ips = Array.isArray(body.ips) ? body.ips.filter(x => typeof x === 'string') : [];
    if (!ips.length) return json(res, 400, { error: 'body { ips: [...] } requerido' });
    const results = await scanMany(ips, body.concurrency || 6);
    return json(res, 200, { total: results.length, results });
  }

  // ── /api/stream?ip=X (SSE: eventos en vivo del escaneo IoT) ─────────────────
  if (req.method === 'GET' && p === '/api/stream') {
    const ip = u.query.ip;
    if (!ip) return json(res, 400, { error: 'param ?ip= requerido' });
    cors(res);
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    });
    const send = (event, data) => {
      res.write(`event: ${event}\n`);
      res.write(`data: ${JSON.stringify(data)}\n\n`);
    };
    send('start', { ip, ts: Date.now() });
    // Geolocalización primero
    const geo = await lookup(ip);
    send('geo', geo);
    // Intel
    const intel = await assess(ip);
    send('intel', intel);
    // IoT scan con progreso por puerto
    const { scan: scanFn } = require('./lib/iot');
    // Re-ejecutar scan pero emitir progreso
    const fullResult = await scanFn(ip);
    send('iot', fullResult);
    send('done', { ip, ts: Date.now() });
    res.end();
    return;
  }

  // ── /api/health ─────────────────────────────────────────────────────────────
  if (req.method === 'GET' && p === '/api/health') {
    return json(res, 200, { status: 'ok', ts: new Date().toISOString(), modules: ['geo', 'intel', 'iot'], version: '1.0.0' });
  }

  // 404
  json(res, 404, { error: `ruta no encontrada: ${p}`, routes: ['/api/geo', '/api/intel', '/api/iot', '/api/full', '/api/scan-batch', '/api/stream', '/api/health'] });
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`╔══════════════════════════════════════════╗`);
  console.log(`║  SealCtl Console v1.0 — puerto ${PORT}     ║`);
  console.log(`║  http://localhost:${PORT}                   ║`);
  console.log(`╠══════════════════════════════════════════╣`);
  console.log(`║  Módulos: geo · intel · iot               ║`);
  console.log(`║  API: /api/geo /api/intel /api/iot        ║`);
  console.log(`║       /api/full /api/scan-batch /stream   ║`);
  console.log(`╚══════════════════════════════════════════╝`);
});
