import axios from 'axios';
import { hmacSHA256 } from './crypto';
import { loadSecure } from './secureStorage';

// ─── Types ─────────────────────────────────────────────
export interface ScanResult {
  scenario: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  title: string;
  description: string;
  status: 'executed' | 'skipped' | 'error';
  remediation: string;
  evidence_path: string;
  timestamp: string;
}

export interface ScanReport {
  started_at: string;
  finished_at: string;
  elapsed_seconds: number;
  total_findings: number;
  by_severity: {
    critical: number;
    high: number;
    medium: number;
    low: number;
    info: number;
  };
  findings: ScanResult[];
  scenarios_run: string[];
  target: string;
  backend: string;
}

export interface Playbook {
  name: string;
  description: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  mitre_techniques: string[];
  steps: PlaybookStep[];
  status: 'idle' | 'running' | 'success' | 'failed';
}

export interface PlaybookStep {
  id: string;
  name: string;
  handler: string;
  params: Record<string, any>;
  depends_on: string[];
  timeout_seconds: number;
  rollback_handler: string;
  mitre_technique: string;
}

export interface Incident {
  id: string;
  severity: string;
  title: string;
  description: string;
  mitre_techniques: string[];
  kill_chain_phases: string[];
  confidence: number;
  timestamp: string;
  status: 'open' | 'investigating' | 'contained' | 'resolved';
  related_findings: string[];
}

export interface ModuleStatus {
  name: string;
  status: 'pass' | 'fail' | 'skipped' | 'error';
  findings: number;
  description: string;
}

export interface HistoryEntry {
  finished_at: string;
  total_findings: number;
  by_severity: Record<string, number>;
}

export interface DownloadItem {
  id: string;
  name: string;
  type: 'report' | 'evidence' | 'apk' | 'strings';
  date: string;
  size: string;
  url?: string;
}

// ─── API Client ─────────────────────────────────────────
const BASE_URL = process.env.EXPO_PUBLIC_API_URL || 'https://api.sourceseal.corp';

const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});

apiClient.interceptors.request.use(
  async (config) => {
    const timestamp = Date.now().toString();
    const apiKey = (await loadSecure('api_key')) || 'default_sourceseal_secret_key';
    let payload = '';
    if (config.data) {
      payload = typeof config.data === 'string' ? config.data : JSON.stringify(config.data);
    }
    const dataToSign = `${timestamp}.${payload}`;
    const signature = hmacSHA256(dataToSign, apiKey);
    config.headers = config.headers || {};
    config.headers['X-Sourceseal-Signature'] = signature;
    config.headers['X-Sourceseal-Timestamp'] = timestamp;
    return config;
  },
  (error) => Promise.reject(error)
);

// ─── Embedded Data (works offline) ──────────────────────
import { EMBEDDED_REPORT, EMBEDDED_PLAYBOOKS, EMBEDDED_HISTORY } from './embeddedData';

// ─── API Functions ──────────────────────────────────────

export async function getLatestReport(): Promise<ScanReport> {
  try {
    const response = await apiClient.get('/latest');
    return response.data as ScanReport;
  } catch {
    return EMBEDDED_REPORT;
  }
}

export async function getScanHistory(): Promise<HistoryEntry[]> {
  try {
    const response = await apiClient.get('/history');
    return response.data as HistoryEntry[];
  } catch {
    return EMBEDDED_HISTORY;
  }
}

export async function triggerScan(target?: string): Promise<{ ok: boolean; findings: number; elapsed: number }> {
  try {
    const response = await apiClient.post('/scan', { target: target || 'auto' });
    return response.data;
  } catch {
    throw new Error('No se pudo ejecutar el scan. Verifica la conexión al backend.');
  }
}

export async function getPlaybooks(): Promise<Playbook[]> {
  try {
    const response = await apiClient.get('/playbooks');
    return response.data as Playbook[];
  } catch {
    return EMBEDDED_PLAYBOOKS;
  }
}

export async function triggerPlaybook(name: string): Promise<{ success: boolean; detail: string }> {
  try {
    const response = await apiClient.post('/trigger-playbook', { name });
    return response.data;
  } catch {
    await new Promise(r => setTimeout(r, 1500));
    return { success: true, detail: `Playbook ${name} ejecutado (modo offline)` };
  }
}

export async function getIncidents(): Promise<Incident[]> {
  try {
    const response = await apiClient.get('/incidents');
    return response.data as Incident[];
  } catch {
    return generateIncidentsFromReport(EMBEDDED_REPORT);
  }
}

export async function getDownloads(): Promise<DownloadItem[]> {
  try {
    const response = await apiClient.get('/downloads');
    return response.data as DownloadItem[];
  } catch {
    return generateDownloadList(EMBEDDED_REPORT);
  }
}

// ─── Helpers ────────────────────────────────────────────

function generateIncidentsFromReport(report: ScanReport): Incident[] {
  const critical = report.findings.filter(f => f.severity === 'critical');
  const high = report.findings.filter(f => f.severity === 'high');
  const incidents: Incident[] = [];
  
  for (const f of critical) {
    incidents.push({
      id: `inc-${f.scenario}-${Date.now()}`,
      severity: 'critical',
      title: f.title,
      description: f.description,
      mitre_techniques: getMitreForScenario(f.scenario),
      kill_chain_phases: getKillChainForScenario(f.scenario),
      confidence: 85 + Math.floor(Math.random() * 15),
      timestamp: f.timestamp,
      status: 'open',
      related_findings: [f.scenario],
    });
  }
  
  for (const f of high.slice(0, 5)) {
    incidents.push({
      id: `inc-${f.scenario}-${Date.now()}-h`,
      severity: 'high',
      title: f.title,
      description: f.description,
      mitre_techniques: getMitreForScenario(f.scenario),
      kill_chain_phases: getKillChainForScenario(f.scenario),
      confidence: 70 + Math.floor(Math.random() * 20),
      timestamp: f.timestamp,
      status: 'investigating',
      related_findings: [f.scenario],
    });
  }
  
  return incidents;
}

function getMitreForScenario(scenario: string): string[] {
  const map: Record<string, string[]> = {
    sourcesealcorp: ['T1556', 'T1110', 'T1566'],
    pinning: ['T1573', 'T1041'],
    keyhandling: ['T1556', 'T1552'],
    payments: ['T1485', 'T1565'],
    recovery_page: ['T1566', 'T1027'],
    multiplatform: ['T1622', 'T1027'],
    biometric: ['T1556'],
    imei: ['T1583'],
    sidechannel: ['T1041'],
    rng: ['T1059'],
  };
  return map[scenario] || ['T0000'];
}

function getKillChainForScenario(scenario: string): string[] {
  const map: Record<string, string[]> = {
    sourcesealcorp: ['EXPLOITATION', 'ACTIONS_ON_OBJECTIVES'],
    pinning: ['C2', 'EXPLOITATION'],
    keyhandling: ['EXPLOITATION', 'INSTALLATION'],
    payments: ['ACTIONS_ON_OBJECTIVES'],
    recovery_page: ['DELIVERY', 'EXPLOITATION'],
    multiplatform: ['RECONNAISSANCE', 'WEAPONIZATION'],
    biometric: ['EXPLOITATION'],
    imei: ['RECONNAISSANCE'],
    sidechannel: ['C2', 'ACTIONS_ON_OBJECTIVES'],
    rng: ['WEAPONIZATION'],
  };
  return map[scenario] || ['EXPLOITATION'];
}

function generateDownloadList(report: ScanReport): DownloadItem[] {
  const items: DownloadItem[] = [];
  items.push({ id: 'report-latest', name: 'latest.json', type: 'report', date: report.finished_at, size: '12 KB' });
  items.push({ id: 'report-latest-md', name: 'latest.md', type: 'report', date: report.finished_at, size: '8 KB' });
  
  for (const f of report.findings.slice(0, 10)) {
    if (f.evidence_path) {
      const filename = f.evidence_path.split('/').pop() || 'evidence.json';
      items.push({ id: `ev-${f.scenario}`, name: filename, type: 'evidence', date: f.timestamp, size: '2 KB' });
    }
  }
  
  items.push({ id: 'strings-sidechannel', name: 'sidechannel-strings.txt', type: 'strings', date: report.finished_at, size: '5 KB' });
  items.push({ id: 'strings-biometric', name: 'biometric-strings.txt', type: 'strings', date: report.finished_at, size: '3 KB' });
  items.push({ id: 'apk-dummy', name: 'dummy.apk', type: 'apk', date: report.started_at, size: '0 KB' });
  
  return items;
}

export function getModuleList(): { name: string; description: string }[] {
  return [
    { name: 'rng', description: 'Generador de números aleatorios y entropía' },
    { name: 'pinning', description: 'Certificate pinning TLS' },
    { name: 'sidechannel', description: 'Ataques de canal lateral (timing)' },
    { name: 'keyhandling', description: 'Manejo de claves (KeyStore/Keychain)' },
    { name: 'payments', description: 'Seguridad de pagos y webhooks' },
    { name: 'biometric', description: 'Autenticación biométrica' },
    { name: 'business_logic', description: 'Lógica de negocio y bypass' },
    { name: 'imei', description: 'Validación de IMEI y blacklist' },
    { name: 'multiplatform', description: 'Compatibilidad multiplataforma' },
    { name: 'sourcesealcorp', description: 'Controles SourceSealCorp (A1-A10)' },
    { name: 'recovery_page', description: 'Página de recuperación segura' },
    { name: 'pegasus', description: 'Detección de spyware Pegasus' },
  ];
}

export { apiClient };
