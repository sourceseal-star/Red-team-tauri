#!/usr/bin/env node
/**
 * stress-test.js — Prueba de carga interna para el servidor Red-team-tauri.
 *
 * - 500 peticiones concurrentes a /api/healthz y /api/integrity/status
 * - Mide tiempo promedio de respuesta en ms
 * - Reporta errores 500 y 429 (Rate Limit)
 * - Se detiene automáticamente si el uso de memoria del servidor supera 80 %
 *
 * Uso:
 *   node scripts/stress-test.js [base_url]
 *   node scripts/stress-test.js http://localhost:8001
 *
 * Compatible con Node 22.
 */

'use strict';

// ── Config ────────────────────────────────────────────────────────────────────
const BASE_URL      = process.argv[2] || process.env.TERMUX_API_URL || 'http://localhost:8001';
const TOTAL_REQ     = 500;
const CONCURRENCY   = 50;   // Peticiones en vuelo simultáneas
const MEM_THRESHOLD = 0.80;  // 80 % del heap total → parar
const ENDPOINTS     = ['/api/healthz', '/api/integrity/status'];

// ── Helpers ───────────────────────────────────────────────────────────────────
const { performance } = require('perf_hooks');

async function fetchOne(url) {
  const t0 = performance.now();
  let status = 0;
  let ok = false;
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 5000);
    const res = await fetch(url, { signal: ctrl.signal });
    clearTimeout(timer);
    status = res.status;
    ok = res.ok;
    await res.text(); // Consumir body para liberar el socket
  } catch (err) {
    status = err.name === 'AbortError' ? 408 : 0;
  }
  const elapsed = performance.now() - t0;
  return { status, ok, elapsed };
}

function checkLocalMemory() {
  const mem = process.memoryUsage();
  return mem.heapUsed / mem.heapTotal;
}

function pickEndpoint(i) {
  return ENDPOINTS[i % ENDPOINTS.length];
}

// ── Runner con pool de concurrencia ──────────────────────────────────────────
async function runPool(total, concurrency) {
  const results = [];
  let launched = 0;
  let stopped = false;

  async function worker() {
    while (launched < total && !stopped) {
      const idx = launched++;
      const url = `${BASE_URL}${pickEndpoint(idx)}`;

      // Verificar memoria local antes de cada petición
      const memRatio = checkLocalMemory();
      if (memRatio > MEM_THRESHOLD) {
        console.error(
          `\n🛑  Memoria local >${(MEM_THRESHOLD * 100).toFixed(0)}%` +
          ` (heap: ${(memRatio * 100).toFixed(1)}%) — deteniendo prueba.`
        );
        stopped = true;
        break;
      }

      const result = await fetchOne(url);
      results.push({ idx, url, ...result });
    }
  }

  const workers = Array.from({ length: concurrency }, () => worker());
  await Promise.all(workers);
  return results;
}

// ── Informe ───────────────────────────────────────────────────────────────────
function report(results) {
  const total = results.length;
  const succeeded = results.filter(r => r.ok).length;
  const err500    = results.filter(r => r.status === 500).length;
  const err429    = results.filter(r => r.status === 429).length;
  const err408    = results.filter(r => r.status === 408).length;
  const connFail  = results.filter(r => r.status === 0).length;
  const latencies = results.map(r => r.elapsed).sort((a, b) => a - b);
  const avg   = latencies.reduce((s, v) => s + v, 0) / latencies.length;
  const p50   = latencies[Math.floor(latencies.length * 0.50)];
  const p95   = latencies[Math.floor(latencies.length * 0.95)];
  const p99   = latencies[Math.floor(latencies.length * 0.99)];

  console.log('\n══════════════════════════════════════════════');
  console.log(' SourceSeal Stress Test — Resultados');
  console.log('══════════════════════════════════════════════');
  console.log(`  Destino:          ${BASE_URL}`);
  console.log(`  Peticiones:       ${total} / ${TOTAL_REQ}`);
  console.log(`  Concurrencia:     ${CONCURRENCY}`);
  console.log(`  ✅  Exitosas (2xx): ${succeeded}`);
  console.log(`  ❌  500 (Server):  ${err500}`);
  console.log(`  🚦  429 (RateLimit):${err429}`);
  console.log(`  ⏱   408 (Timeout): ${err408}`);
  console.log(`  🔌  Sin conexión:  ${connFail}`);
  console.log('──────────────────────────────────────────────');
  console.log(`  Latencia media:   ${avg.toFixed(1)} ms`);
  console.log(`  p50:              ${p50.toFixed(1)} ms`);
  console.log(`  p95:              ${p95.toFixed(1)} ms`);
  console.log(`  p99:              ${p99.toFixed(1)} ms`);
  console.log('══════════════════════════════════════════════\n');

  if (err500 > 0) {
    console.warn(`⚠️  ${err500} respuestas 500 detectadas — el servidor está fallando bajo carga.`);
  }
  if (err429 > 0) {
    console.warn(`⚠️  ${err429} respuestas 429 — rate limiting activado.`);
  }
  if (connFail > 0) {
    console.error(`🛑  ${connFail} conexiones fallidas — verificar que el servidor está corriendo en ${BASE_URL}`);
  }

  const memAfter = process.memoryUsage();
  console.log(`  Heap post-test:  ${(memAfter.heapUsed / 1024 / 1024).toFixed(1)} MB / ${(memAfter.heapTotal / 1024 / 1024).toFixed(1)} MB`);
}

// ── Main ──────────────────────────────────────────────────────────────────────
(async () => {
  console.log(`\n🚀  Iniciando stress test → ${BASE_URL}`);
  console.log(`    ${TOTAL_REQ} peticiones · concurrencia ${CONCURRENCY} · endpoints: ${ENDPOINTS.join(', ')}`);
  console.log(`    Se detiene si memoria heap > ${(MEM_THRESHOLD * 100).toFixed(0)}%\n`);

  const t0 = performance.now();
  const results = await runPool(TOTAL_REQ, CONCURRENCY);
  const totalMs = performance.now() - t0;

  console.log(`\n⏱   Tiempo total: ${(totalMs / 1000).toFixed(2)} s`);
  report(results);
})();
