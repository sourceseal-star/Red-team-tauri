/**
 * health.js — Endpoint GET /api/healthz para el servidor Express local (Termux).
 *
 * Devuelve estado operativo, uptime, uso de memoria y timestamp.
 * Compatible con Node 22 + Express 5.
 */

'use strict';

const { Router } = require('express');

const router = Router();

const _startTime = Date.now();

/**
 * GET /api/healthz
 * Respuesta:
 *   { status, uptime, memory, timestamp }
 */
router.get('/healthz', (_req, res) => {
  const uptimeMs = Date.now() - _startTime;
  const uptimeSec = Math.floor(uptimeMs / 1000);
  const h = Math.floor(uptimeSec / 3600);
  const m = Math.floor((uptimeSec % 3600) / 60);
  const s = uptimeSec % 60;
  const uptimeHuman = `${h}h ${m}m ${s}s`;

  const mem = process.memoryUsage();

  res.status(200).json({
    status: 'operational',
    uptime: {
      ms: uptimeMs,
      human: uptimeHuman,
    },
    memory: {
      rss_mb:         +(mem.rss / 1024 / 1024).toFixed(2),
      heap_used_mb:   +(mem.heapUsed / 1024 / 1024).toFixed(2),
      heap_total_mb:  +(mem.heapTotal / 1024 / 1024).toFixed(2),
      external_mb:    +(mem.external / 1024 / 1024).toFixed(2),
    },
    node_version: process.version,
    timestamp: new Date().toISOString(),
  });
});

/**
 * GET /api/health  (alias sin la z para compatibilidad)
 */
router.get('/health', (_req, res) => res.redirect('/api/healthz'));

module.exports = router;
