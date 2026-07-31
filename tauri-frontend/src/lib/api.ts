/**
 * Cliente HTTP real — conecta directamente con el backend Python.
 * Todas las funciones hacen fetch() reales; no hay mocks.
 */

const BASE = "/api"

async function get<T>(path: string): Promise<T> {
  const r = await fetch(BASE + path)
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return r.json()
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return r.json()
}

async function del<T>(path: string): Promise<T> {
  const r = await fetch(BASE + path, { method: "DELETE" })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return r.json()
}

// ── Tipos ─────────────────────────────────────────────────────────────────────

export interface Service {
  name: string
  status: "running" | "stopped" | "error"
  pid?: number
  uptime?: string
  lastLogs: string[]
  description?: string
}

export interface Resources {
  cpu_usage: number
  memory_used: number
  memory_total: number
  memory_percent: number
}

export interface Finding {
  scenario: string
  severity: "critical" | "high" | "medium" | "low" | "info"
  title: string
  description: string
  evidence_path: string
  remediation: string
  timestamp: string
}

export interface Report {
  id?: string
  file?: string
  started_at?: string
  finished_at?: string
  elapsed_seconds?: number
  total_findings: number
  by_severity: { critical: number; high: number; medium: number; low: number; info: number }
  findings?: Finding[]
  errors?: unknown[]
  message?: string
}

export interface IOC {
  id: string
  type: string
  value: string
  confidence: number
  tags: string[]
  added?: string
}

export interface Device {
  id: string
  name: string
  platform: string
  attestation: "passed" | "failed" | "revoked" | "pending"
  last_seen: string
  enrolled?: boolean
  revoked_at?: string
}

export interface HoneypotStatus {
  active: boolean
  tokens_deployed: number
  triggers_today: number
  triggers_total?: number
  last_trigger?: string | null
  token_rotated_at?: string
}

export interface SoarDag {
  id: string
  name: string
  enabled: boolean
  trigger: "schedule" | "manual"
  interval_mins?: number
  steps: string[]
  last_run?: string | null
  description?: string
}

export interface ConfigFile {
  name: string
  path: string
  size?: number
  modified?: string
}

export interface Settings {
  api_url: string
  interval: number
  scan_on_startup?: boolean
  notify_slack?: boolean
  slack_webhook?: string
}

export interface ScanStatus {
  running: boolean
  progress: string
  last_result?: unknown
  last_error?: string | null
}

// ── Servicios ─────────────────────────────────────────────────────────────────

export const api = {
  // Servicios
  getServices:      () => get<Service[]>("/services"),
  startService:     (name: string) => post<{ ok: boolean; message: string }>("/services/start", { name }),
  stopService:      (name: string) => post<{ ok: boolean; message: string }>("/services/stop", { name }),
  restartService:   (name: string) => post<{ ok: boolean; message: string }>("/services/restart", { name }),
  startAll:         () => post<{ ok: boolean }>("/services/start-all"),
  stopAll:          () => post<{ ok: boolean }>("/services/stop-all"),
  getServiceLogs:   (name: string) => get<string[]>(`/services/${name}/logs`),

  // Recursos del sistema
  getResources:     () => get<Resources>("/resources"),

  // Escaneos
  startScan:        (target?: string) => post<{ status: string; message: string }>("/scan", target ? { target } : undefined),
  getScanStatus:    () => get<ScanStatus>("/scan/status"),
  getLatestReport:  () => get<Report>("/latest"),
  getHistory:       () => get<Report[]>("/history"),

  // Config
  listConfigFiles:  () => get<ConfigFile[]>("/config"),
  readConfig:       (path: string) => get<{ content: string; path: string }>(`/config/read?path=${encodeURIComponent(path)}`),
  writeConfig:      (path: string, content: string) => post<{ ok: boolean }>("/config/write", { path, content }),

  // Honeypot
  getHoneypot:      () => get<HoneypotStatus>("/honeypot"),
  toggleHoneypot:   () => post<HoneypotStatus>("/honeypot/toggle"),
  rotateTokens:     () => post<{ ok: boolean; tokens_deployed: number }>("/honeypot/rotate"),

  // SOAR
  getDags:          () => get<SoarDag[]>("/soar/dags"),
  saveDag:          (dag: Partial<SoarDag>) => post<{ ok: boolean; id: string }>("/soar/dags", dag),
  dryRun:           () => post<{ ok: boolean; steps: string[]; count: number }>("/soar/dry-run"),

  // Threat Intel / IOCs
  getIocs:          () => get<IOC[]>("/tip/iocs"),
  addIoc:           (ioc: Partial<IOC>) => post<{ ok: boolean; id: string }>("/tip/iocs", ioc),
  deleteIoc:        (id: string) => del<{ ok: boolean }>(`/tip/iocs/${id}`),
  importStix:       (bundle: unknown) => post<{ ok: boolean; imported: number }>("/tip/import-stix", bundle),
  updateFromFeeds:  () => post<{ ok: boolean; iocs_loaded: number }>("/tip/update", {}),

  // RASP dispositivos
  getDevices:       () => get<Device[]>("/rasp/devices"),
  revokeDevice:     (id: string) => del<{ ok: boolean }>(`/rasp/devices/${id}`),
  enrollDevice:     (device: Partial<Device>) => post<{ ok: boolean; id: string }>("/rasp/devices", device),

  // Terminal
  runCommand:       (command: string) => post<{ stdout: string; stderr: string; code: number }>("/terminal", { command }),

  // Settings
  getSettings:      () => get<Settings>("/settings"),
  saveSettings:     (s: Partial<Settings>) => post<{ ok: boolean }>("/settings", s),
}
