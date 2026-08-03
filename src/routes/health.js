'use strict';

const express = require('express');
const os = require('os');

const router = express.Router();

/**
 * GET /api/healthz
 * Health check público — sin autenticación.
 * Reporta estado operacional, uptime, uso de memoria y timestamp.
 */
router.get('/healthz', (req, res) => {
  const mem = process.memoryUsage();
  const systemTotalBytes = os.totalmem();
  const systemFreeBytes = os.freemem();

  // % de memoria RSS del proceso respecto a la RAM total del sistema.
  // (heapUsed/heapTotal NO es fiable como gate de alarma: heapTotal es
  // dinámico y crece bajo demanda, por lo que puede marcar >80% recién
  // arrancado el proceso sin que haya presión de memoria real).
  const rssPercentOfSystem = Number(((mem.rss / systemTotalBytes) * 100).toFixed(2));

  res.json({
    status: 'operational',
    uptime: process.uptime(),
    memory: {
      rss: mem.rss,
      heapTotal: mem.heapTotal,
      heapUsed: mem.heapUsed,
      external: mem.external,
      arrayBuffers: mem.arrayBuffers,
      heapUsedPercent: Number(((mem.heapUsed / mem.heapTotal) * 100).toFixed(2)),
      // Métrica recomendada para gates de "% de memoria usado" (stress-test la usa)
      rssPercentOfSystem,
      systemFreeMemMB: Number((systemFreeBytes / 1024 / 1024).toFixed(2)),
      systemTotalMemMB: Number((systemTotalBytes / 1024 / 1024).toFixed(2)),
    },
    timestamp: new Date().toISOString(),
  });
});

module.exports = router;
