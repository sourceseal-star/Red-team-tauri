/**
 * Honeypot HTTP Server — servidor falso que captura atacantes
 * Cada request se loguea en SQLite con IP, UA, headers, payload
 */

const http = require('http');
const { v4: uuidv4 } = require('uuid');
const { insertAttack } = require('./database');
const { classify } = require('../utils/classifier');
const geoip = require('../utils/geoip');

let server = null;
let activeToken = null;
let startTime = null;
let attackCallback = null; // callback para WebSocket alerts
let stats = { attacks_count: 0, unique_ips: new Set() };

// Endpoints falsos que atraen atacantes
const FAKE_ENDPOINTS = [
  { path: '/admin/login', status: 200, body: '<html><body><h1>Admin Login</h1><form action="/admin/login" method="POST"><input name="user"><input name="pass" type="password"><button>Login</button></form></body></html>' },
  { path: '/wp-login.php', status: 200, body: '<html><body><h1>WordPress Login</h1><form method="POST"><input name="log"><input name="pwd" type="password"><button>Submit</button></form></body></html>' },
  { path: '/phpmyadmin', status: 200, body: '<html><body><h1>phpMyAdmin</h1><form method="POST"><input name="username"><input name="password" type="password"><button>Go</button></form></body></html>' },
  { path: '/.env', status: 200, body: 'DB_PASSWORD=s3cr3t\nAPI_KEY=sk-xxxxxxxxxxxx\nJWT_SECRET=super_secret_jwt_123\nDATABASE_URL=postgres://user:pass@db:5432/prod' },
  { path: '/.git/config', status: 200, body: '[core]\n\trepositoryformatversion = 0\n[remote "origin"]\n\turl = git@github.com:company/private-repo.git\n[branch "main"]\n\tremote = origin\n\tmerge = refs/heads/main' },
  { path: '/api/v1/users', status: 200, body: '[{"id":1,"email":"admin@sourceseal.co","role":"admin"},{"id":2,"email":"ceo@sourceseal.co","role":"ceo"}]' },
  { path: '/backup.sql', status: 200, body: '-- MySQL dump\nCREATE TABLE users (id INT, email VARCHAR(255), password VARCHAR(255));\nINSERT INTO users VALUES (1, "admin@sourceseal.co", "$2b$10$xxxx");' },
  { path: '/robots.txt', status: 200, body: 'User-agent: *\nDisallow: /admin/\nDisallow: /backup/\nDisallow: /.env\nDisallow: /api/internal/' },
];

function getClientIP(req) {
  return req.headers['x-forwarded-for']?.split(',')[0]?.trim() ||
         req.headers['x-real-ip'] ||
         req.socket.remoteAddress?.replace('::ffff:', '') ||
         'unknown';
}

function parseBody(req) {
  return new Promise((resolve) => {
    let body = '';
    req.on('data', chunk => body += chunk.toString());
    req.on('end', () => resolve(body.substring(0, 8192)));
    req.on('error', () => resolve(''));
  });
}

async function handleRequest(req, res) {
  const ip = getClientIP(req);
  const method = req.method;
  const url = req.url || '/';
  const userAgent = req.headers['user-agent'] || '';
  const headers = JSON.stringify(req.headers);

  // Get payload if POST
  let payload = '';
  if (method === 'POST' || method === 'PUT') {
    payload = await parseBody(req);
  }

  // Classify severity
  const { severity, attack_type } = classify(method, url, payload, userAgent);

  // GeoIP lookup
  const geo = await geoip.lookup(ip);
  const country = geo.country || 'Unknown';

  // Find matching fake endpoint
  const fakeEndpoint = FAKE_ENDPOINTS.find(e => url.startsWith(e.path));

  // Log attack to SQLite
  try {
    await insertAttack({
      token: activeToken,
      ip_address: ip,
      method,
      path: url,
      user_agent: userAgent,
      headers,
      payload,
      severity,
      country,
    });
  } catch (e) {
    console.error(`[honeypot] DB error: ${e.message}`);
  }

  // Update stats
  stats.attacks_count++;
  stats.unique_ips.add(ip);

  // Console log
  const ts = new Date().toISOString();
  console.log(`[HONEYPOT] ${ts} | ${ip} (${country}) | ${method} ${url} | [${severity.toUpperCase()}] ${attack_type}`);
  console.log(`  UA: ${userAgent.substring(0, 80)}`);
  if (payload) console.log(`  Payload: ${payload.substring(0, 100)}`);

  // WebSocket alert callback
  if (attackCallback) {
    attackCallback({
      ip, method, path: url, severity, attack_type, country,
      user_agent: userAgent, timestamp: ts
    });
  }

  // Respond with fake content
  if (fakeEndpoint) {
    res.writeHead(fakeEndpoint.status, { 'Content-Type': 'text/html' });
    res.end(fakeEndpoint.body);
  } else {
    // Default: pretend to be a server
    res.writeHead(404, { 'Content-Type': 'text/html' });
    res.end('<html><body><h1>404 Not Found</h1></body></html>');
  }
}

function start(port = 8080, token) {
  return new Promise((resolve, reject) => {
    if (server) {
      return reject(new Error('Honeypot already running'));
    }

    activeToken = token || `ss_hp_${uuidv4().substring(0, 8)}_${Date.now()}`;
    startTime = Date.now();
    stats = { attacks_count: 0, unique_ips: new Set() };

    server = http.createServer((req, res) => {
      handleRequest(req, res).catch(e => {
        console.error(`[honeypot] Handler error: ${e}`);
        res.writeHead(500);
        res.end('Internal Error');
      });
    });

    server.on('error', (e) => {
      if (e.code === 'EADDRINUSE') {
        reject(new Error(`Port ${port} already in use`));
      } else {
        reject(e);
      }
    });

    server.listen(port, '0.0.0.0', () => {
      console.log(`[HONEYPOT] Server listening on 0.0.0.0:${port}`);
      console.log(`[HONEYPOT] Token: ${activeToken}`);
      console.log(`[HONEYPOT] Capturing attacks...`);
      resolve({ token: activeToken, port, status: 'active' });
    });
  });
}

function stop() {
  return new Promise((resolve) => {
    if (!server) return resolve({ status: 'inactive' });
    server.close(() => {
      server = null;
      const result = { status: 'stopped', token: activeToken, attacks_captured: stats.attacks_count };
      activeToken = null;
      startTime = null;
      resolve(result);
    });
  });
}

function getStatus() {
  return {
    active: !!server,
    token: activeToken,
    port: server?.address()?.port || null,
    attacks_count: stats.attacks_count,
    unique_ips: stats.unique_ips.size,
    uptime: startTime ? Math.floor((Date.now() - startTime) / 1000) : 0,
  };
}

function onAttack(callback) {
  attackCallback = callback;
}

module.exports = { start, stop, getStatus, onAttack, FAKE_ENDPOINTS };
