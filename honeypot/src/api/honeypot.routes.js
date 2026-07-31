/**
 * API Routes — Endpoints para consultar el honeypot desde Termux
 */

const express = require('express');
const router = express.Router();
const honeypot = require('../honeypot/server');
const db = require('../honeypot/database');
const { v4: uuidv4 } = require('uuid');

// ── ACTIVAR HONEYPOT ─────────────────────────────────────────────────────────
router.post('/activate', async (req, res) => {
  try {
    const port = parseInt(req.body?.port || req.query?.port || process.env.HONEYPOT_PORT || 8080);
    const token = req.body?.token || `ss_hp_${uuidv4().substring(0, 8)}_${Date.now()}`;
    
    const result = await honeypot.start(port, token);
    res.json({
      ...result,
      message: `Honeypot activo en puerto ${port}`,
      docs: '/api/honeypot/docs',
    });
  } catch (e) {
    res.status(400).json({ error: e.message });
  }
});

// ── DESACTIVAR HONEYPOT ───────────────────────────────────────────────────────
router.post('/deactivate', async (req, res) => {
  try {
    const result = await honeypot.stop();
    res.json(result);
  } catch (e) {
    res.status(400).json({ error: e.message });
  }
});

// ── ESTADO DEL HONEYPOT ──────────────────────────────────────────────────────
router.get('/status', (req, res) => {
  res.json(honeypot.getStatus());
});

// ── CONSULTAR ATAQUES ─────────────────────────────────────────────────────────
router.get('/attacks', async (req, res) => {
  try {
    const token = req.query.token || honeypot.getStatus().token;
    const limit = Math.min(parseInt(req.query.limit) || 100, 1000);
    const offset = parseInt(req.query.offset) || 0;
    
    if (!token) {
      return res.status(400).json({ error: 'Token required. Activate honeypot first.' });
    }
    
    const attacks = await db.getAttacks(token, limit, offset);
    res.json({
      total: attacks.length,
      attacks,
    });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ── TOP IPs MÁS ACTIVAS ──────────────────────────────────────────────────────
router.get('/attacks/top-ips', async (req, res) => {
  try {
    const hours = parseInt(req.query.hours) || 24;
    const limit = parseInt(req.query.limit) || 20;
    const ips = await db.getTopIPs(hours, limit);
    res.json({
      hours,
      total_ips: ips.length,
      top_ips: ips,
    });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ── EXPORTAR ATAQUES (CSV / JSON / TXT) ───────────────────────────────────────
router.get('/attacks/export', async (req, res) => {
  try {
    const token = req.query.token || honeypot.getStatus().token;
    const format = req.query.format || 'json';
    
    if (!token) {
      return res.status(400).json({ error: 'Token required.' });
    }
    
    const data = await db.exportAttacks(token, format);
    
    if (format === 'csv') {
      res.setHeader('Content-Type', 'text/csv');
      res.setHeader('Content-Disposition', `attachment; filename="honeypot-attacks-${Date.now()}.csv"`);
    } else if (format === 'txt') {
      res.setHeader('Content-Type', 'text/plain');
    } else {
      res.setHeader('Content-Type', 'application/json');
    }
    
    res.send(data);
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ── ESTADÍSTICAS ──────────────────────────────────────────────────────────────
router.get('/stats', async (req, res) => {
  try {
    const token = req.query.token || honeypot.getStatus().token;
    const stats = await db.getStats(token);
    res.json(stats);
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ── ATAQUES POR PAÍS ──────────────────────────────────────────────────────────
router.get('/attacks/by-country', async (req, res) => {
  try {
    const token = req.query.token || honeypot.getStatus().token;
    const data = await db.getByCountry(token);
    res.json(data);
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ── LIMPIAR ATAQUES ───────────────────────────────────────────────────────────
router.delete('/attacks', async (req, res) => {
  try {
    const token = req.query.token || honeypot.getStatus().token;
    const result = await db.clearAttacks(token);
    res.json(result);
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ── DOCUMENTACIÓN AUTOMÁTICA ──────────────────────────────────────────────────
router.get('/docs', (req, res) => {
  res.json({
    title: 'SourceSeal Honeypot API',
    version: '1.0.0',
    description: 'Honeypot HTTP real para captura y análisis de ataques',
    endpoints: {
      'POST /api/honeypot/activate': {
        description: 'Activa el honeypot y genera token único',
        body: '{ "port": 8080 }',
        returns: '{ "token": "ss_hp_xxx", "port": 8080, "status": "active" }',
      },
      'POST /api/honeypot/deactivate': {
        description: 'Desactiva el honeypot',
        returns: '{ "status": "stopped", "attacks_captured": N }',
      },
      'GET /api/honeypot/status': {
        description: 'Estado actual del honeypot',
        returns: '{ "active": true, "token": "ss_hp_xxx", "attacks_count": N, "unique_ips": N, "uptime": N }',
      },
      'GET /api/honeypot/attacks?token=XXX&limit=100': {
        description: 'Últimos N ataques capturados',
        params: 'token (requerido), limit (default 100), offset (default 0)',
      },
      'GET /api/honeypot/attacks/top-ips?hours=24': {
        description: 'IPs más activas en las últimas N horas',
        params: 'hours (default 24), limit (default 20)',
      },
      'GET /api/honeypot/attacks/export?format=csv&token=XXX': {
        description: 'Exporta ataques en CSV, JSON o TXT',
        params: 'format (csv|json|txt), token (requerido)',
      },
      'GET /api/honeypot/stats?token=XXX': {
        description: 'Estadísticas: total, unique_ips, top_paths, timeline',
      },
      'GET /api/honeypot/attacks/by-country?token=XXX': {
        description: 'Distribución geográfica de ataques',
      },
      'DELETE /api/honeypot/attacks?token=XXX': {
        description: 'Elimina todos los ataques del token',
      },
      'GET /api/honeypot/docs': {
        description: 'Esta documentación',
      },
    },
    curl_examples: {
      activate: 'curl -X POST http://localhost:8080/api/honeypot/activate',
      status: 'curl http://localhost:8080/api/honeypot/status',
      attacks: 'curl "http://localhost:8080/api/honeypot/attacks?token=ss_hp_XXX&limit=50"',
      top_ips: 'curl "http://localhost:8080/api/honeypot/attacks/top-ips?hours=24"',
      export_csv: 'curl "http://localhost:8080/api/honeypot/attacks/export?format=csv&token=ss_hp_XXX" > attacks.csv',
      stats: 'curl "http://localhost:8080/api/honeypot/stats?token=ss_hp_XXX"',
      by_country: 'curl "http://localhost:8080/api/honeypot/attacks/by-country?token=ss_hp_XXX"',
      clear: 'curl -X DELETE "http://localhost:8080/api/honeypot/attacks?token=ss_hp_XXX"',
    },
    severity_levels: {
      critical: 'Acceso a /admin, /.env, /.git, /backup, /phpmyadmin',
      high: 'SQL injection, XSS, path traversal, code injection',
      medium: 'Reconocimiento (wp-login, xmlrpc, scanners)',
      low: 'Probes genéricos (favicon, robots.txt)',
    },
  });
});

module.exports = router;
