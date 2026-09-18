/**
 * API Client para OSINT - con auth headers.
 * Usa getApiKey() de lib/api.ts que lee el token de localStorage.
 * Endpoints mapeados a los que EXISTEN en dashboard_server.py.
 */
import { getBaseUrl, getApiKey } from '../lib/api';

const OSINT_BASE = `${getBaseUrl()}/api/osint`;
const OSINT_V2_BASE = `${getBaseUrl()}/api/osint/v2`;

function authH(json = false): Record<string, string> {
  const h: Record<string, string> = {}
  const key = getApiKey()
  if (key) h['Authorization'] = `Bearer ${key}`
  if (json) h['Content-Type'] = 'application/json'
  return h
}

export const osintApi = {
  // POST /api/osint/v2/full-scan — combina el escaneo según el tipo de objetivo
  fullScan: async (target: string): Promise<any> => {
    const r = await fetch(`${OSINT_V2_BASE}/full-scan`, {
      method: 'POST',
      headers: authH(true),
      body: JSON.stringify({ target }),
    })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  },

  quickScan: async (target: string): Promise<any> => {
    const r = await fetch(`${OSINT_V2_BASE}/quick-scan/${encodeURIComponent(target)}`, { headers: authH() })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  },

  // GET /api/osint/whois/{domain}
  whois: async (target: string) => {
    const r = await fetch(`${OSINT_BASE}/whois/${encodeURIComponent(target)}`, { headers: authH() })
    return r.json()
  },

  // GET /api/osint/dns/{domain}
  dns: async (domain: string) => {
    const r = await fetch(`${OSINT_BASE}/dns/${encodeURIComponent(domain)}`, { headers: authH() })
    return r.json()
  },

  // GET /api/osint/subdomains/{domain}
  subdomains: async (domain: string) => {
    const r = await fetch(`${OSINT_BASE}/subdomains/${encodeURIComponent(domain)}`, { headers: authH() })
    return r.json()
  },

  // POST /api/osint/email — accepts an email address, not only a domain
  emails: async (email: string) => {
    const r = await fetch(`${OSINT_BASE}/email`, {
      method: 'POST',
      headers: authH(true),
      body: JSON.stringify({ target: email }),
    })
    return r.json()
  },

  // GET /api/osint/threat-intel/{ip}
  threatIntel: async (entity: string) => {
    const r = await fetch(`${OSINT_BASE}/threat-intel/${encodeURIComponent(entity)}`, { headers: authH() })
    return r.json()
  },

  // GET /api/osint/social/{username}
  social: async (username: string) => {
    const r = await fetch(`${OSINT_BASE}/social/${encodeURIComponent(username)}`, { headers: authH() })
    return r.json()
  },

  // GET /api/osint/cert/{domain}
  cert: async (domain: string) => {
    const r = await fetch(`${OSINT_BASE}/cert/${encodeURIComponent(domain)}`, { headers: authH() })
    return r.json()
  },

  // GET /api/osint/history/{target}
  history: async (target: string) => {
    const r = await fetch(`${OSINT_BASE}/history/${encodeURIComponent(target)}`, { headers: authH() })
    return r.json()
  },
}
