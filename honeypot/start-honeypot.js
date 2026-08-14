#!/usr/bin/env node
/**
 * start-honeypot.js — Inicio rápido del honeypot SourceSeal
 * 
 * Uso:
 *   node start-honeypot.js                    # Puerto 8080 (default)
 *   node start-honeypot.js 9090               # Puerto 9090
 *   HONEYPOT_PORT=9090 node start-honeypot.js # Via env var
 */

const express = require('express');
const http = require('http');
const cors = require('cors');
const helmet = require('helmet');
const { Server: SocketServer } = require('socket.io');
const { v4: uuidv4 } = require('uuid');

const honeypot = require('./src/honeypot/server');
const honeypotRoutes = require('./src/api/honeypot.routes');

// ── Config ────────────────────────────────────────────────────────────────────
const API_PORT = parseInt(process.env.PORT || process.argv[2] || 8080);
const HONEYPOT_PORT = parseInt(process.env.HONEYPOT_PORT || 8080);

// ── Express app (API server) ──────────────────────────────────────────────────
const app = express();
app.use(helmet({ contentSecurityPolicy: false }));
const ALLOWED_ORIGINS = (process.env.ALLOWED_ORIGINS || 'http://localhost:5173,http://127.0.0.1:5173').split(',');
app.use(cors({ origin: ALLOWED_ORIGINS }));
app.use(express.json({ limit: '1mb' }));
app.use(express.urlencoded({ extended: true }));

// ── API routes ────────────────────────────────────────────────────────────────
app.use('/api/honeypot', honeypotRoutes);

// ── Health ────────────────────────────────────────────────────────────────────
app.get('/health', (req, res) => {
  const status = honeypot.getStatus();
  res.json({ status: 'ok', honeypot, uptime: process.uptime(), ...status });
});

// ── HTTP server + Socket.io ──────────────────────────────────────────────────
const server = http.createServer(app);
const io = new SocketServer(server, { cors: { origin: ALLOWED_ORIGINS } });

io.on('connection', (socket) => {
  console.log(`[socket] Cliente conectado: ${socket.id}`);
  socket.emit('honeypot.connected', honeypot.getStatus());
  socket.on('disconnect', () => {
    console.log(`[socket] Cliente desconectado: ${socket.id}`);
  });
});

// ── WebSocket alert on attack ─────────────────────────────────────────────────
honeypot.onAttack((attack) => {
  io.emit('honeypot.attack', attack);
});

// ── Start ─────────────────────────────────────────────────────────────────────
async function main() {
  const banner = `
╔══════════════════════════════════════════════════════════╗
║         🐝 SourceSeal Honeypot — Starting...              ║
╠══════════════════════════════════════════════════════════╣
║  API:     http://0.0.0.0:${API_PORT}                       ║
║  Docs:    http://0.0.0.0:${API_PORT}/api/honeypot/docs     ║
║  Status:  http://0.0.0.0:${API_PORT}/api/honeypot/status   ║
║  WS:      ws://0.0.0.0:${API_PORT} (socket.io)            ║
╚══════════════════════════════════════════════════════════╝
`;
  console.log(banner);

  // Install sqlite3 and geoip-lite if not present
  try { require('sqlite3'); } catch (e) {
    console.log('[setup] sqlite3 not found. Run: npm install sqlite3');
    console.log('[setup] Continuing without DB persistence (attacks logged to console only)');
  }

  // Auto-activate honeypot on start
  try {
    const token = `ss_hp_${uuidv4().substring(0, 8)}_${Date.now()}`;
    const result = await honeypot.start(HONEYPOT_PORT, token);
    console.log(`\n[HONEYPOT] ✅ Active! Token: ${result.token}`);
    console.log(`[HONEYPOT] Listening on port ${HONEYPOT_PORT}`);
    console.log(`[HONEYPOT] Capturing attacks in real-time...\n`);
    
    // Print ready-to-use curl commands
    console.log('━━━ READY TO USE IN TERMUX ━━━');
    console.log(`curl http://localhost:${API_PORT}/api/honeypot/status`);
    console.log(`curl "http://localhost:${API_PORT}/api/honeypot/attacks?token=${token}"`);
    console.log(`curl "http://localhost:${API_PORT}/api/honeypot/attacks/export?format=csv&token=${token}" > attacks.csv`);
    console.log(`curl "http://localhost:${API_PORT}/api/honeypot/stats?token=${token}"`);
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`);
  } catch (e) {
    console.error(`[HONEYPOT] Failed to start: ${e.message}`);
    console.error('[HONEYPOT] API still available. Activate manually:');
    console.error(`curl -X POST http://localhost:${API_PORT}/api/honeypot/activate`);
  }

  server.listen(API_PORT, '0.0.0.0', () => {
    console.log(`[API] Server ready on http://0.0.0.0:${API_PORT}`);
  });
}

main().catch(e => {
  console.error('Fatal error:', e);
  process.exit(1);
});
