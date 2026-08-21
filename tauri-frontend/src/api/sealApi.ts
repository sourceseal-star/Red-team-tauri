/**
 * SEAL API Client - Cliente para SEAL SUPER PACK
 * =============================================
 * Escaneo, ataque, fingerprinting y orquestación de dispositivos.
 */

const API_BASE = '/api';

function getHeaders(): Record<string, string> {
  const token = localStorage.getItem('api_token');
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function apiCall<T = any>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const res = await fetch(url, {
    headers: getHeaders(),
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

export const sealApi = {
  // ── Devices ──────────────────────────────
  getDevices: (status?: string, risk?: string) => {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    if (risk) params.set('risk', risk);
    const qs = params.toString();
    return apiCall(`/devices${qs ? `?${qs}` : ''}`);
  },

  getDevice: (ip: string) => apiCall(`/devices/${ip}`),

  scanDevice: (ip: string, deep = false) =>
    apiCall(`/devices/${ip}/scan${deep ? '?deep=true' : ''}`),

  // ── Network Scan ─────────────────────────
  scanNetwork: (network?: string, deep = false) => {
    const params = new URLSearchParams();
    if (network) params.set('network', network);
    if (deep) params.set('deep', 'true');
    const qs = params.toString();
    return apiCall(`/scan${qs ? `?${qs}` : ''}`);
  },

  quickScan: (network?: string) => {
    const params = new URLSearchParams();
    if (network) params.set('network', network);
    const qs = params.toString();
    return apiCall(`/scan/quick${qs ? `?${qs}` : ''}`);
  },

  // ── Alerts ───────────────────────────────
  getAlerts: (resolved?: boolean, severity?: string, limit = 100) => {
    const params = new URLSearchParams();
    if (resolved !== undefined) params.set('resolved', String(resolved));
    if (severity) params.set('severity', severity);
    params.set('limit', String(limit));
    return apiCall(`/alerts?${params.toString()}`);
  },

  resolveAlert: (id: number) =>
    apiCall(`/alerts/${id}/resolve`, { method: 'POST' }),

  // ── Status & Stats ───────────────────────
  getStatus: () => apiCall('/status'),
  getStats: () => apiCall('/stats'),

  // ── Hikvision ────────────────────────────
  scanHikvision: (network?: string) => {
    const qs = network ? `?network=${encodeURIComponent(network)}` : '';
    return apiCall(`/hikvision/scan${qs}`);
  },

  attackHikvision: (ip: string) => apiCall(`/hikvision/attack/${ip}`),

  // ── ONVIF ────────────────────────────────
  scanOnvif: (network?: string) => {
    const qs = network ? `?network=${encodeURIComponent(network)}` : '';
    return apiCall(`/onvif/scan${qs}`);
  },

  checkOnvif: (ip: string) => apiCall(`/onvif/check/${ip}`),

  // ── Vendor Dicts ─────────────────────────
  getVendors: () => apiCall('/dicts/vendors'),
  getVendorCreds: (vendor: string) => apiCall(`/dicts/${encodeURIComponent(vendor)}`),

  // ── Integration ARTO+SEAL ────────────────
  integratedHealth: () => apiCall('/integrated/health'),

  integratedScan: (network?: string) => {
    const qs = network ? `?network=${encodeURIComponent(network)}` : '';
    return apiCall(`/integrated/scan${qs}`);
  },

  integratedAttack: (ip: string) =>
    apiCall(`/integrated/attack/${ip}`, { method: 'POST' }),
};
