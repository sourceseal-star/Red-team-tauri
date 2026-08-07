/**
 * Cliente HTTP real — conecta directamente con el backend Python.
 * Todas las funciones hacen fetch() reales; no hay mocks.
 */

// API key management — se guarda en SecureStore (mobile) o localStorage (web)
let _apiKey: string | null = null

export function getApiKey(): string | null {
  if (_apiKey) return _apiKey
  if (typeof window !== 'undefined' && window.localStorage) {
    _apiKey = localStorage.getItem('sealctl_api_key')
  }
  return _apiKey
}

export function setApiKey(key: string) {
  _apiKey = key
  if (typeof window !== 'undefined' && window.localStorage) {
    localStorage.setItem('sealctl_api_key', key)
  }
}

export function clearApiKey() {
  _apiKey = null
  if (typeof window !== 'undefined' && window.localStorage) {
    localStorage.removeItem('sealctl_api_key')
  }
}

// Construye la URL completa para recursos que no pueden usar headers (img, video)
export function authUrl(path: string): string {
  const key = getApiKey()
  const sep = path.includes('?') ? '&' : '?'
  return BASE + path + (key ? `${sep}token=${encodeURIComponent(key)}` : '')
}

function authHeaders(): Record<string, string> {
  const key = getApiKey()
  return key ? { 'Authorization': `Bearer ${key}` } : {}
}

const BASE = "/api"

async function get<T>(path: string): Promise<T> {
  const r = await fetch(BASE + path, { headers: { ...authHeaders() } })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return r.json()
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return r.json()
}

async function del<T>(path: string): Promise<T> {
  const r = await fetch(BASE + path, { method: "DELETE", headers: { ...authHeaders() } })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return r.json()
}

/** GET con header X-Api-Key para rutas de escaneo de red protegidas. */
async function getWithKey<T>(path: string, apiKey: string): Promise<T> {
  const r = await fetch(BASE + path, {
    headers: { "X-Api-Key": apiKey },
  })
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
  cpu_percent?: number
  cpu_cores?: number
  uptime?: string | number
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
  backend_url?: string
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


// ── Tipos: Geo + Intel + Cámaras + Video ────────────────────────────────────────

export interface IPGeolocationResponse {
  ip: string
  country: string
  country_code?: string
  city: string
  lat: number | null
  lon: number | null
  isp: string
  as: string
  timezone?: string | null
  proxy?: boolean
  hosting?: boolean
  mobile?: boolean
  private?: boolean
  error?: string
  note?: string
}

export interface IPVerificationResponse {
  ip: string
  rdns: string | null
  asn?: string
  org?: string
  abuse_contact?: string
  country?: string
  network_name?: string
}

export interface IPTrustScoreResponse {
  ip: string
  score: number
  label: string
  rdns: string | null
  breakdown: { f: string; w: number }[]
  flags: IPGeolocationResponse
  tls?: { present: boolean; self_signed?: boolean; issuer?: string; valid_to?: string }
  rdap?: { ok: boolean; network?: string; country?: string }
  note?: string
}

export interface CameraFinding {
  port: number
  protocol: string
  vendor?: string
  evidence: string
}

export interface CameraScanResult {
  ok: boolean
  ip: string
  is_camera_exposed: boolean
  ports_scanned: number
  open_ports: { port: number; banner_preview?: string }[]
  findings: CameraFinding[]
  scanned_at: string
  error?: string
}

export interface RadioScanResult {
  ok: boolean
  ip: string
  is_radio_exposed: boolean
  ports_scanned: number
  findings: CameraFinding[]
  scanned_at: string
  error?: string
}

export interface VideoSource {
  path: string
  port: number
  type: 'mjpeg' | 'snapshot' | 'rtsp' | 'html'
  vendor: string
  available: boolean
  stream_url: string | null
  snapshot_url: string | null
  rtsp_url?: string
  content_type?: string
  note?: string
}

export interface VideoUrlsResponse {
  ip: string
  video_sources: VideoSource[]
  total: number
  note: string
}


export interface NetworkScanResult {
  network: string
  total_ips: number
  total_scanned: number
  cameras_found: number
  devices_with_open_ports: number
  cameras: CameraScanResult[]
  all_devices: any[]
  full_results: any[]
}

export interface LocalScanResult {
  detected_ip: string
  detected_mask: string
  detected_cidr: string
  total_ips: number
  total_scanned: number
  cameras_found: number
  devices_with_open_ports: number
  cameras: CameraScanResult[]
  all_devices: any[]
  full_results: any[]
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


  // Geo + Threat Intel
  getGeo:           (ip: string) => get<unknown>(`/geo?ip=${encodeURIComponent(ip)}`),
  getIntel:         (ip: string) => get<unknown>(`/intel?ip=${encodeURIComponent(ip)}`),

  // Escaneo de red — cámaras IP y radio (REAL)
  // Requiere X-Api-Key = REDTEAM_API_KEY configurado en el servidor.
  scanCameras: (target: string, apiKey: string, timeout?: number) =>
    getWithKey<unknown>(
      `/network/cameras?target=${encodeURIComponent(target)}${timeout ? `&timeout=${timeout}` : ''}`,
      apiKey
    ),
  scanRadio: (target: string, apiKey: string, timeout?: number) =>
    getWithKey<unknown>(
      `/network/radio?target=${encodeURIComponent(target)}${timeout ? `&timeout=${timeout}` : ''}`,
      apiKey
    ),

  // IP Actions (nuevos endpoints SealCtl)
  ipGeolocate:     (ip: string) => get<IPGeolocationResponse>(`/geo?ip=${encodeURIComponent(ip)}`),
  ipVerifySource:  (ip: string) => get<IPVerificationResponse>(`/intel/deep?ip=${encodeURIComponent(ip)}`),
  ipTrustScore:    (ip: string) => get<IPTrustScoreResponse>(`/intel/deep?ip=${encodeURIComponent(ip)}`),
  ipScanCameras:   (ip: string) => get<CameraScanResult>(`/iot?target=${encodeURIComponent(ip)}`),
  ipScanRadio:     (ip: string) => get<RadioScanResult>(`/iot?target=${encodeURIComponent(ip)}`),

  // Video de cámaras IP
  ipVideoUrls:     (ip: string, user?: string, pass?: string) =>
    get<VideoUrlsResponse>(`/iot/video-urls?ip=${encodeURIComponent(ip)}${user ? `&user=${encodeURIComponent(user)}` : ''}${pass ? `&pass=${encodeURIComponent(pass)}` : ''}`),
  ipSnapshot:      (ip: string, port: number, path: string, user?: string, pass?: string) =>
    `/iot/snapshot?ip=${encodeURIComponent(ip)}&port=${port}&path=${encodeURIComponent(path)}${user ? `&user=${encodeURIComponent(user)}` : ''}${pass ? `&pass=${encodeURIComponent(pass)}` : ''}`,
  ipStreamUrl:      (ip: string, port: number, path: string, user?: string, pass?: string) =>
    `/iot/stream?ip=${encodeURIComponent(ip)}&port=${port}&path=${encodeURIComponent(path)}${user ? `&user=${encodeURIComponent(user)}` : ''}${pass ? `&pass=${encodeURIComponent(pass)}` : ''}`,

  // Escaneo de red por CIDR o rango
  scanNetwork:     (cidr: string) => post<NetworkScanResult>('/iot/scan-network', { cidr }),
  scanLocal:       () => post<LocalScanResult>("/iot/scan-local", {}),
  wifiScan:        (interface_name = "wlan0") => post<WiFiScanResult>("/scan/wifi", { interface: interface_name }),
}

// ── WiFi Scan ──────────────────────────────────────────────────────────────────
export interface WiFiNetwork {
  ssid: string
  bssid: string
  security: string
  signal_dbm: number
  frequency?: number
  channel: number
  hidden: boolean
  wps?: boolean
}

export interface WiFiScanResult {
  scan_id?: string
  networks_found: number
  networks: WiFiNetwork[]
  connected_devices: { hostname: string; ip: string; mac: string; vendor: string; type: string }[]
  security_analysis: {
    open_networks: number
    wep_networks: number
    wpa_networks: number
    wpa2_networks: number
    wpa3_networks: number
    wps_enabled: number
    hidden_networks: number
    risk_score: number
  }
  scan_method?: string | null
  interface?: string
  warning?: string | null
}
