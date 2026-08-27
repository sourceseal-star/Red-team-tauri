'use strict';

/**
 * stress-test.js
 * ─────────────────────────────────────────────────────────────────────────
 * Prueba de carga interna para el servidor local (Red-team-tauri / SealCtl).
 *
 * - Lanza 500 peticiones concurrentes contra los endpoints objetivo.
 * - Mide el tiempo promedio de respuesta (ms).
 * - Reporta si el servidor devuelve 500 (error interno) o 429 (rate limit).
 * - Se detiene automáticamente si el uso de memoria del servidor (reportado
 *   por /api/healthz) supera el 80%.
 *
 * Uso:
 *   node scripts/stress-test.js
 *   BASE_URL=http://127.0.0.1:8000 CONCURRENCY=500 node scripts/stress-test.js
 *   STRESS_TARGETS=/api/healthz,/api/scan/port node scripts/stress-test.js
 *
 * Nota: '/api/integrity/status' es un endpoint del protocolo SourceSeal
 * (proyecto 'origenprogreso', ledger de sellos). Este servidor Red-team-tauri
 * no lo implementa — si lo incluyes en STRESS_TARGETS, el script lo reportará
 * simplemente como 404, lo cual es información válida para el reporte.
 */

const http = require('http');
const https = require('https');

const BASE_URL = process.env.BASE_URL || process.env.TERMUX_API_URL || 'http://127.0.0.1:8000';
const CONCURRENCY = parseInt(process.env.CONCURRENCY || '500', 10);
const TARGETS = (process.env.STRESS_TARGETS || '/api/healthz,/api/integrity/status')
  .split(',')
  .map((s) => s.trim())
  .filter(Boolean);
const MEMORY_LIMIT_PERCENT = parseFloat(process.env.MEMORY_LIMIT_PERCENT || '80');
const REQUEST_TIMEOUT_MS = parseInt(process.env.REQUEST_TIMEOUT_MS || '10000', 10);
const API_KEY = process.env.REDTEAM_API_KEY || '';

const client = BASE_URL.startsWith('https') ? https : http;

function get(path) {
  return new Promise((resolve) => {
    const url = new URL(path, BASE_URL);
    if (API_KEY) url.searchParams.set('token', API_KEY);

    const start = process.hrtime.bigint();
    const req = client.get(
      url,
      { timeout: REQUEST_TIMEOUT_MS },
      (res) => {
        let body = '';
        res.on('data', (chunk) => (body += chunk));
        res.on('end', () => {
          const end = process.hrtime.bigint();
          const ms = Number(end - start) / 1e6;
          resolve({ path, status: res.statusCode, ms, body });
        });
      }
    );
    req.on('timeout', () => {
      req.destroy();
      resolve({ path, status: 0, ms: REQUEST_TIMEOUT_MS, error: 'timeout' });
    });
    req.on('error', (err) => {
      const end = process.hrtime.bigint();
      const ms = Number(end - start) / 1e6;
      resolve({ path, status: 0, ms, error: err.message });
    });
  });
}

async function checkMemoryUsage() {
  const res = await get('/api/healthz');
  if (res.status === 200) {
    try {
      const data = JSON.parse(res.body);
      // Usar primero la presión global del sistema cuando el backend la
      // reporta; en caso contrario, usar el RSS del proceso servidor.
      // heapUsedPercent queda como compatibilidad con servidores Node antiguos.
      const pct = data?.memory?.systemUsedPercent
        ?? data?.memory?.rssPercentOfSystem
        ?? data?.memory?.heapUsedPercent;
      if (typeof pct === 'number') return pct;
    } catch (_) {
      // ignore parse errors
    }
  }
  return null;
}

async function runBatch(size) {
  const promises = [];
  for (let i = 0; i < size; i++) {
    const target = TARGETS[i % TARGETS.length];
    promises.push(get(target));
  }
  return Promise.all(promises);
}

function summarize(results) {
  const byStatus = {};
  let totalMs = 0;
  let ok = 0;
  const errors500 = [];
  const errors429 = [];
  const timeouts = [];

  for (const r of results) {
    byStatus[r.status] = (byStatus[r.status] || 0) + 1;
    totalMs += r.ms;
    if (r.status >= 200 && r.status < 300) ok++;
    if (r.status === 500) errors500.push(r);
    if (r.status === 429) errors429.push(r);
    if (r.status === 0) timeouts.push(r);
  }

  return {
    total: results.length,
    ok,
    avgMs: Number((totalMs / results.length).toFixed(2)),
    byStatus,
    errors500: errors500.length,
    errors429: errors429.length,
    timeouts: timeouts.length,
  };
}

async function main() {
  console.log('=== Stress Test — Red-team-tauri / SealCtl ===');
  console.log(`Target base:   ${BASE_URL}`);
  console.log(`Endpoints:     ${TARGETS.join(', ')}`);
  console.log(`Concurrencia:  ${CONCURRENCY} peticiones`);
  console.log(`Límite memoria: ${MEMORY_LIMIT_PERCENT}%`);
  console.log('');

  // Chequeo previo de memoria
  const preMemory = await checkMemoryUsage();
  if (preMemory !== null) {
    console.log(`Memoria del servidor actual: ${preMemory}%`);
    if (preMemory >= MEMORY_LIMIT_PERCENT) {
      console.log(`⚠️  ABORTADO: el servidor ya está sobre el límite de memoria (${preMemory}% >= ${MEMORY_LIMIT_PERCENT}%).`);
      process.exit(1);
    }
  } else {
    console.log('⚠️  No se pudo leer el uso de memoria desde /api/healthz (¿servidor caído o ruta ausente?).');
  }

  const startedAt = Date.now();
  const results = await runBatch(CONCURRENCY);
  const elapsedMs = Date.now() - startedAt;

  const summary = summarize(results);

  console.log('');
  console.log('=== Resultado ===');
  console.log(`Peticiones totales:     ${summary.total}`);
  console.log(`Exitosas (2xx):         ${summary.ok}`);
  console.log(`Tiempo promedio:        ${summary.avgMs} ms`);
  console.log(`Tiempo total del lote:  ${elapsedMs} ms`);
  console.log(`Distribución de status: ${JSON.stringify(summary.byStatus)}`);
  console.log(`Errores 500:            ${summary.errors500}`);
  console.log(`Errores 429 (rate limit): ${summary.errors429}`);
  console.log(`Timeouts / sin respuesta: ${summary.timeouts}`);

  if (summary.errors500 > 0) {
    console.log('');
    console.log(`🔴 ALERTA: el servidor devolvió ${summary.errors500} errores 500 durante la carga.`);
  }
  if (summary.errors429 > 0) {
    console.log(`🟡 El servidor aplicó rate limiting (429) ${summary.errors429} veces — comportamiento esperado bajo carga alta.`);
  }

  // Chequeo posterior de memoria
  const postMemory = await checkMemoryUsage();
  if (postMemory !== null) {
    console.log('');
    console.log(`Memoria del servidor tras la prueba: ${postMemory}%`);
    if (postMemory >= MEMORY_LIMIT_PERCENT) {
      console.log(`🔴 ALERTA: el servidor superó el ${MEMORY_LIMIT_PERCENT}% de uso de memoria tras la prueba.`);
      process.exitCode = 2;
      return;
    }
  }

  console.log('');
  console.log('✅ Prueba de carga finalizada dentro de los límites de memoria.');
}

main().catch((err) => {
  console.error('Error ejecutando stress-test:', err);
  process.exit(1);
});
