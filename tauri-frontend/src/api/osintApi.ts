/**
 * API Client para OSINT v2 - con auth headers.
 * Usa getApiKey() de lib/api.ts que lee el token de localStorage.
 */
import { getBaseUrl, getApiKey } from '../lib/api';

const OSINT_BASE = `${getBaseUrl()}/api/osint/v2`;

function authH(json = false): Record<string, string> {
  const h: Record<string, string> = {}
  const key = getApiKey()
  if (key) h['Authorization'] = `Bearer ${key}`
  if (json) h['Content-Type'] = 'application/json'
  return h
}

export interface OSINTScanResult {
  target: string
  type: string
  is_malicious: boolean
  threat_level: 'LOW' | 'HIGH' | 'CRITICAL'
  malicious_indicators: number
  results: {
    whois?: any
    dns?: any
    subdomains?: string[]
    threat_intel?: any
    email?: any
    headers?: any
  }
  errors: string[]
  timestamp: string
}

export interface QuickScanResult {
  target: string
  type: string
  is_malicious: boolean
  threat_level: 'LOW' | 'HIGH'
  key_findings: {
    open_ports: number
    vulnerabilities: number
    subdomains: number
    breaches: number
  }
}

export const osintApi = {
  fullScan: async (target: string, scanType: string = 'auto'): Promise<OSINTScanResult> => {
    const r = await fetch(`${OSINT_BASE}/full-scan`, {
      method: 'POST',
      headers: authH(true),
      body: JSON.stringify({ target, scan_type: scanType }),
    })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  },

  quickScan: async (target: string, scanType: string = 'auto'): Promise<QuickScanResult> => {
    const r = await fetch(`${OSINT_BASE}/quick-scan/${encodeURIComponent(target)}?scan_type=${scanType}`, {
      headers: authH(),
    })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  },

  whois: async (target: string) => {
    const r = await fetch(`${OSINT_BASE}/whois/${encodeURIComponent(target)}`, { headers: authH() })
    return r.json()
  },

  dns: async (domain: string) => {
    const r = await fetch(`${OSINT_BASE}/dns/${encodeURIComponent(domain)}`, { headers: authH() })
    return r.json()
  },

  subdomains: async (domain: string) => {
    const r = await fetch(`${OSINT_BASE}/subdomains/${encodeURIComponent(domain)}`, { headers: authH() })
    return r.json()
  },

  threatIntel: async (entity: string, type: string = 'auto') => {
    const r = await fetch(`${OSINT_BASE}/threat/${encodeURIComponent(entity)}?entity_type=${type}`, { headers: authH() })
    return r.json()
  },
}

// ═════════════════════════════════════════════════════════════
// Multi-Engine Search — 7 motores + "all"
// ═════════════════════════════════════════════════════════════

export type SearchEngine = 'duckduckgo' | 'bing' | 'yahoo' | 'brave' | 'yandex' | 'google' | 'tor' | 'all';

export interface SearchResult {
  title: string;
  link: string;
  snippet: string;
  engine: string;
}

export interface MultiSearchResult {
  query: string;
  engine: string;
  engines_used?: string[];
  results: SearchResult[];
  total: number;
  errors?: string[];
}

export const searchApi = {
  search: async (q: string, engine: SearchEngine = 'all', num: number = 10): Promise<MultiSearchResult> => {
    const r = await fetch(`${OSINT_BASE}/search?q=${encodeURIComponent(q)}&engine=${engine}&num=${num}`, { headers: authH() })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  },

  engines: async () => {
    const r = await fetch(`${OSINT_BASE}/search/engines`, { headers: authH() })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  },
}
