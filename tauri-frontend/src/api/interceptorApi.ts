/**
 * API Client para Interceptor v2 - con auth headers.
 * Usa getApiKey() de lib/api.ts que lee el token de localStorage.
 */
import { getBaseUrl, getApiKey } from '../lib/api';

const INTERCEPTOR_BASE = `${getBaseUrl()}/api/interceptor/v2`;

function authH(json = false): Record<string, string> {
  const h: Record<string, string> = {}
  const key = getApiKey()
  if (key) h['Authorization'] = `Bearer ${key}`
  if (json) h['Content-Type'] = 'application/json'
  return h
}

export interface ProxyStatus {
  running: boolean
  port?: number
  total_flows: number
  total_alerts: number
}

export interface InterceptedFlow {
  flow_id: string
  src_ip: string
  dst_host: string
  dst_port: number
  method: string
  path: string
  status_code: number
  request_size: number
  is_suspicious: boolean
  is_malicious: boolean
  severity: string
  alerts_count: number
  timestamp: string
  raw_data: string
}

export interface InterceptorAlert {
  flow_id: string
  src_ip: string
  alert_type: string
  severity: string
  payload: string
  pattern_matched: string
  cwe: string
  mitre: string
  timestamp: string
}

export interface InterceptorStats {
  active: boolean
  total_flows: number
  total_alerts: number
  by_severity: Record<string, number>
  attack_types: Record<string, number>
  unique_src_ips: number
}

export const interceptorApi = {
  control: async (action: 'start' | 'stop' | 'status', port: number = 8888): Promise<ProxyStatus | any> => {
    const r = await fetch(`${INTERCEPTOR_BASE}/control`, {
      method: 'POST',
      headers: authH(true),
      body: JSON.stringify({ action, port }),
    })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  },

  getFlows: async (limit: number = 50, filterMalicious: boolean = false): Promise<{ total: number; flows: InterceptedFlow[] }> => {
    const r = await fetch(
      `${INTERCEPTOR_BASE}/flows?limit=${limit}&filter_malicious=${filterMalicious}`,
      { headers: authH() }
    )
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  },

  getAlerts: async (limit: number = 50, severity?: string): Promise<{ total: number; alerts: InterceptorAlert[] }> => {
    const url = severity
      ? `${INTERCEPTOR_BASE}/alerts?limit=${limit}&severity=${severity}`
      : `${INTERCEPTOR_BASE}/alerts?limit=${limit}`
    const r = await fetch(url, { headers: authH() })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  },

  getStats: async (): Promise<InterceptorStats> => {
    const r = await fetch(`${INTERCEPTOR_BASE}/stats`, { headers: authH() })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  },

  analyzeFlow: async (flowId: string, analyzeInjections: boolean = true): Promise<any> => {
    const r = await fetch(`${INTERCEPTOR_BASE}/analyze-flow/${flowId}`, {
      method: 'POST',
      headers: authH(true),
      body: JSON.stringify({ analyze_injections: analyzeInjections }),
    })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  },
}
