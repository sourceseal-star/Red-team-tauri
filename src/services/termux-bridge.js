'use strict';

/**
 * termux-bridge.js
 * ─────────────────────────────────────────────────────────────────────────
 * Puente de comunicación entre el frontend/backend en Replit y el backend
 * local (Termux / Red-team-tauri) que corre en el dispositivo del usuario.
 *
 * - axios + axios-retry: 3 reintentos con backoff exponencial.
 * - Heartbeat: GET /api/healthz cada 60s para detectar caídas.
 * - Si el backend de Termux no responde, activa "MODO RESILIENCIA":
 *   la app sigue funcionando localmente y expone un mensaje claro.
 * - Timeout estricto de 5s por petición para no congelar el frontend.
 *
 * Uso:
 *   const bridge = require('./services/termux-bridge');
 *   bridge.startHeartbeat();
 *   bridge.onStateChange((state) => { ... });
 *   const data = await bridge.request({ method: 'get', url: '/api/scan/port', params: {...} });
 */

const axios = require('axios');
const axiosRetryModule = require('axios-retry');
const axiosRetry = axiosRetryModule.default || axiosRetryModule;
const { EventEmitter } = require('events');

// ─── Configuración ──────────────────────────────────────────────────────────
const TERMUX_API_URL = process.env.TERMUX_API_URL || 'http://127.0.0.1:8000';
const REQUEST_TIMEOUT_MS = 5000;      // máximo 5s por petición
const HEARTBEAT_INTERVAL_MS = 60000;  // cada 60s
const MAX_RETRIES = 3;

const STATE = {
  NORMAL: 'NORMAL',
  RESILIENCE: 'MODO RESILIENCIA',
};

const RESILIENCE_MESSAGE =
  'Sistema operando en modo local. Sincronización pendiente.';

// ─── Estado global del bridge ───────────────────────────────────────────────
const emitter = new EventEmitter();

let currentState = STATE.NORMAL;
let lastSuccessAt = null;
let lastError = null;
let heartbeatTimer = null;

// ─── Cliente axios con reintentos ───────────────────────────────────────────
const client = axios.create({
  baseURL: TERMUX_API_URL,
  timeout: REQUEST_TIMEOUT_MS,
});

axiosRetry(client, {
  retries: MAX_RETRIES,
  retryDelay: axiosRetry.exponentialDelay, // backoff exponencial: 1s, 2s, 4s...
  retryCondition: (error) => {
    // Reintentar en errores de red, timeout, o 5xx del servidor Termux
    return (
      axiosRetry.isNetworkOrIdempotentRequestError(error) ||
      error.code === 'ECONNABORTED' ||
      (error.response && error.response.status >= 500)
    );
  },
  onRetry: (retryCount, error, requestConfig) => {
    console.log(
      `[termux-bridge] Reintento ${retryCount}/${MAX_RETRIES} → ${requestConfig.url} (${error.code || error.message})`
    );
  },
});

// ─── Transición de estado ───────────────────────────────────────────────────
function setState(newState, errorInfo) {
  const changed = newState !== currentState;
  currentState = newState;

  if (newState === STATE.RESILIENCE) {
    lastError = errorInfo || lastError;
  } else {
    lastError = null;
  }

  if (changed) {
    console.log(`[termux-bridge] Estado → ${currentState}`);
    emitter.emit('stateChange', getStatus());
  }
}

function getStatus() {
  return {
    state: currentState,
    isResilienceMode: currentState === STATE.RESILIENCE,
    message: currentState === STATE.RESILIENCE ? RESILIENCE_MESSAGE : 'Conexión con Termux estable.',
    termuxApiUrl: TERMUX_API_URL,
    lastSuccessAt,
    lastError: lastError ? (lastError.message || String(lastError)) : null,
  };
}

function onStateChange(listener) {
  emitter.on('stateChange', listener);
  return () => emitter.off('stateChange', listener);
}

// ─── Heartbeat ───────────────────────────────────────────────────────────────
async function checkHealth() {
  try {
    const res = await client.get('/api/healthz');
    lastSuccessAt = new Date().toISOString();
    setState(STATE.NORMAL);
    return { ok: true, data: res.data };
  } catch (err) {
    setState(STATE.RESILIENCE, err);
    return { ok: false, error: err.message };
  }
}

function startHeartbeat() {
  if (heartbeatTimer) return; // ya corriendo

  // Primer chequeo inmediato, luego cada 60s
  checkHealth();
  heartbeatTimer = setInterval(checkHealth, HEARTBEAT_INTERVAL_MS);
  console.log(
    `[termux-bridge] Heartbeat iniciado → ${TERMUX_API_URL}/api/healthz cada ${HEARTBEAT_INTERVAL_MS / 1000}s`
  );
}

function stopHeartbeat() {
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer);
    heartbeatTimer = null;
    console.log('[termux-bridge] Heartbeat detenido.');
  }
}

// ─── Petición genérica al backend de Termux ─────────────────────────────────
// Respeta el timeout de 5s y los reintentos configurados arriba.
// Si falla, activa MODO RESILIENCIA y relanza el error para que el caller decida.
async function request(config) {
  try {
    const res = await client.request(config);
    lastSuccessAt = new Date().toISOString();
    if (currentState !== STATE.NORMAL) setState(STATE.NORMAL);
    return res.data;
  } catch (err) {
    setState(STATE.RESILIENCE, err);
    throw err;
  }
}

module.exports = {
  STATE,
  RESILIENCE_MESSAGE,
  TERMUX_API_URL,
  startHeartbeat,
  stopHeartbeat,
  checkHealth,
  request,
  getStatus,
  onStateChange,
};
