/**
 * termux-bridge.js — Módulo de comunicación con el backend local en Termux.
 *
 * Características:
 *  - axios con axios-retry (3 intentos, backoff exponencial)
 *  - Heartbeat cada 60 s a GET /api/healthz
 *  - MODO RESILIENCIA cuando el backend cae
 *  - Timeout estricto de 5 s por petición
 *  - URL configurable vía TERMUX_API_URL
 *
 * Uso:
 *   const bridge = require('./src/services/termux-bridge');
 *   await bridge.init();
 *   const data = await bridge.get('/api/services');
 */

'use strict';

const axios = require('axios');
const axiosRetry = require('axios-retry').default ?? require('axios-retry');

// ── Configuración ─────────────────────────────────────────────────────────────
const TERMUX_API_URL  = process.env.TERMUX_API_URL  || 'http://localhost:8001';
const REQUEST_TIMEOUT = parseInt(process.env.TERMUX_TIMEOUT_MS || '5000', 10);
const HEARTBEAT_MS    = parseInt(process.env.TERMUX_HEARTBEAT_MS || '60000', 10);
const MAX_RETRIES     = 3;

// ── Estado global del bridge ──────────────────────────────────────────────────
let _status = 'CONNECTING'; // 'ONLINE' | 'RESILIENCE' | 'CONNECTING'
let _heartbeatTimer = null;
let _statusListeners = [];

/** Suscribirse a cambios de estado: fn(newStatus, oldStatus) */
function onStatusChange(fn) {
  _statusListeners.push(fn);
  return () => { _statusListeners = _statusListeners.filter(l => l !== fn); };
}

function _setStatus(newStatus) {
  if (newStatus === _status) return;
  const old = _status;
  _status = newStatus;
  _statusListeners.forEach(fn => {
    try { fn(newStatus, old); } catch (_) {}
  });
  if (newStatus === 'RESILIENCE') {
    console.warn('[termux-bridge] ⚠️  Sistema operando en modo local. Sincronización pendiente.');
  } else if (newStatus === 'ONLINE') {
    console.info('[termux-bridge] ✅  Backend Termux en línea.');
  }
}

// ── Cliente axios con reintentos ──────────────────────────────────────────────
const client = axios.create({
  baseURL: TERMUX_API_URL,
  timeout: REQUEST_TIMEOUT,
  headers: { 'Content-Type': 'application/json' },
});

axiosRetry(client, {
  retries: MAX_RETRIES,
  // Backoff exponencial: 500ms, 1000ms, 2000ms
  retryDelay: (retryCount) => axiosRetry.exponentialDelay(retryCount, undefined, 500),
  retryCondition: (error) => {
    // Reintentar solo en errores de red o 5xx, nunca en 4xx
    return axiosRetry.isNetworkOrIdempotentRequestError(error)
      || (error.response?.status >= 500);
  },
  onRetry: (retryCount, error) => {
    console.warn(`[termux-bridge] Reintento ${retryCount}/${MAX_RETRIES} — ${error.message}`);
  },
});

// Interceptor: si la petición falla tras todos los reintentos → RESILIENCE
client.interceptors.response.use(
  (res) => {
    _setStatus('ONLINE');
    return res;
  },
  (err) => {
    // Solo entramos en RESILIENCE cuando ya agotamos los reintentos
    const isRetryExhausted = err.config?.[axiosRetry.namespace]?.retryCount >= MAX_RETRIES
      || (!err.response && err.code !== 'ERR_BAD_REQUEST');
    if (isRetryExhausted || !err.response) {
      _setStatus('RESILIENCE');
    }
    return Promise.reject(err);
  }
);

// ── Heartbeat ─────────────────────────────────────────────────────────────────
async function _heartbeat() {
  try {
    await client.get('/api/healthz');
    // Si llegamos aquí, el backend respondió
    _setStatus('ONLINE');
  } catch (err) {
    _setStatus('RESILIENCE');
    console.warn(`[termux-bridge] Heartbeat falló: ${err.message}`);
  }
}

function startHeartbeat() {
  if (_heartbeatTimer) return;
  _heartbeat(); // Primer check inmediato
  _heartbeatTimer = setInterval(_heartbeat, HEARTBEAT_MS);
  console.info(`[termux-bridge] Heartbeat cada ${HEARTBEAT_MS / 1000}s → ${TERMUX_API_URL}/api/healthz`);
}

function stopHeartbeat() {
  if (_heartbeatTimer) {
    clearInterval(_heartbeatTimer);
    _heartbeatTimer = null;
  }
}

// ── API pública ───────────────────────────────────────────────────────────────

/** Inicializa el bridge: verifica conexión y arranca el heartbeat. */
async function init() {
  console.info(`[termux-bridge] Conectando a ${TERMUX_API_URL}…`);
  await _heartbeat();
  startHeartbeat();
}

/** GET hacia el backend Termux. Lanza si está en RESILIENCE y no hay fallback. */
async function get(path, config = {}) {
  const res = await client.get(path, config);
  return res.data;
}

/** POST hacia el backend Termux. */
async function post(path, data = {}, config = {}) {
  const res = await client.post(path, data, config);
  return res.data;
}

/** DELETE hacia el backend Termux. */
async function del(path, config = {}) {
  const res = await client.delete(path, config);
  return res.data;
}

/** Estado actual: 'ONLINE' | 'RESILIENCE' | 'CONNECTING' */
function getStatus() {
  return _status;
}

/** Mensaje de estado para mostrar en el frontend. */
function getStatusMessage() {
  if (_status === 'RESILIENCE') {
    return 'Sistema operando en modo local. Sincronización pendiente.';
  }
  if (_status === 'CONNECTING') {
    return 'Conectando con el backend Termux…';
  }
  return `Backend en línea — ${TERMUX_API_URL}`;
}

module.exports = {
  init,
  get,
  post,
  del,
  getStatus,
  getStatusMessage,
  onStatusChange,
  startHeartbeat,
  stopHeartbeat,
  /** Instancia axios directa para casos avanzados */
  client,
};
