/**
 * API Client para OSINT - con auth headers.
 * Usa getApiKey() de lib/api.ts que lee el token de localStorage.
 * Endpoints mapeados a los que EXISTEN en dashboard_server.py.
 */
import { getBaseUrl, getApiKey } from '../lib/api';

const OSINT_BASE = `${getBaseUrl()}/api/osint`;

function authH(json = false): Record<string, string> {
  const h: Record<string, string> = {}
  const key = getApiKey()
  if (key) h['Authorization'] = `Bearer ${key}`
  if (json) h['Content-Type'] = 'application/json'
  return h
}

export const osintApi = {
  // GET /api/osint/full/{target} — funciona con IPs y dominios
  fullScan: async (target: string): Promise<any> => {
    const r = await fetch(`${OSINT_BASE}/full/${encodeURIComponent(target)}`, { headers: authH() })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  },

  quickScan: async (target: string): Promise<any> => {
    const r = await fetch(`${OSINT_BASE}/full/${encodeURIComponent(target)}`, { headers: authH() })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  },

  // GET /api/osint/whois/{domain}
  whois: async (target: string) => {
    const r = await fetch(`${OSINT_BASE}/whois/${encodeURIComponent(target)}`, { headers: authH() })
    return r.json()
  },

  // GET /api/osint/whois/{domain} (whois cubre DNS)
  dns: async (domain: string) => {
    const r = await fetch(`${OSINT_BASE}/whois/${encodeURIComponent(domain)}`, { headers: authH() })
    return r.json()
  },

  // GET /api/osint/subdomains/{domain}
  subdomains: async (domain: string) => {
    const r = await fetch(`${OSINT_BASE}/subdomains/${encodeURIComponent(domain)}`, { headers: authH() })
    return r.json()
  },

  // GET /api/osint/emails/{domain}
  emails: async (domain: string) => {
    const r = await fetch(`${OSINT_BASE}/emails/${encodeURIComponent(domain)}`, { headers: authH() })
    return r.json()
  },

  // GET /api/osint/full/{entity} — threat intel para IPs y dominios
  threatIntel: async (entity: string) => {
    const r = await fetch(`${OSINT_BASE}/full/${encodeURIComponent(entity)}`, { headers: authH() })
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
