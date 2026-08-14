// Mock para @tauri-apps/api/tauri — permite correr el frontend en el browser sin Rust
const mockServices = [
  { name: 'dashboard_server', status: 'running', pid: 1234, uptime: '2h 14m', lastLogs: ['[INFO] Server started on :5000'] },
  { name: 'orchestrator', status: 'stopped', pid: undefined, uptime: undefined, lastLogs: [] },
  { name: 'rasp_attestation', status: 'running', pid: 1235, uptime: '2h 14m', lastLogs: ['[INFO] Attestation server ready'] },
  { name: 'soar_engine', status: 'stopped', pid: undefined, uptime: undefined, lastLogs: [] },
  { name: 'tip_taxii', status: 'running', pid: 1236, uptime: '1h 52m', lastLogs: ['[INFO] TAXII server ready'] },
  { name: 'ndr_engine', status: 'error', pid: undefined, uptime: undefined, lastLogs: ['[ERROR] Could not bind interface eth0'] },
]

const mockResources = { cpu_usage: 12.4, memory_used: 512 * 1024 * 1024, memory_total: 2048 * 1024 * 1024 }

const mockConfigs = [
  { name: 'orchestrator.yaml', path: 'redteam/runner/orchestrator.yaml' },
  { name: 'soar_playbooks.json', path: 'redteam/soar/playbooks/' },
  { name: 'tip_config.yaml', path: 'redteam/tip/config.yaml' },
]

const mockReports = [
  { id: 'report-20260729-142416', date: '2026-07-29 14:24', findings: 24, critical: 2 },
  { id: 'report-20260727-142228', date: '2026-07-27 14:22', findings: 18, critical: 1 },
  { id: 'report-20260724-061921', date: '2026-07-24 06:19', findings: 11, critical: 0 },
]

const mockIocs = [
  { id: '1', type: 'domain', value: 'evil-c2.example.com', confidence: 90, tags: ['c2', 'malware'] },
  { id: '2', type: 'ip', value: '198.51.100.42', confidence: 75, tags: ['scanner'] },
  { id: '3', type: 'hash', value: 'a3f1...d9e2', confidence: 95, tags: ['ransomware'] },
]

const mockDevices = [
  { id: 'dev-001', name: 'Pixel 8 Pro', platform: 'android', attestation: 'passed', last_seen: '2026-07-29' },
  { id: 'dev-002', name: 'iPhone 15', platform: 'ios', attestation: 'passed', last_seen: '2026-07-28' },
  { id: 'dev-003', name: 'Galaxy S24', platform: 'android', attestation: 'failed', last_seen: '2026-07-25' },
]

export async function invoke(cmd: string, _args?: Record<string, unknown>): Promise<unknown> {
  await new Promise(r => setTimeout(r, 80))
  switch (cmd) {
    case 'get_services_status': return mockServices
    case 'start_service': return { ok: true }
    case 'stop_service': return { ok: true }
    case 'restart_service': return { ok: true }
    case 'start_all_services': return { ok: true }
    case 'stop_all_services': return { ok: true }
    case 'get_system_resources': return mockResources
    case 'get_service_logs': return ['[INFO] mock log line 1', '[INFO] mock log line 2']
    case 'get_config_files': return mockConfigs
    case 'read_config_file': return '# mock config\nkey: value\n'
    case 'write_config_file': return { ok: true }
    case 'validate_yaml': return { valid: true }
    case 'validate_json': return { valid: true }
    case 'get_report_list': return mockReports
    case 'get_report_detail': return { findings: [], summary: 'Mock report' }
    case 'export_reports': return { path: '/tmp/export.zip' }
    case 'get_honeypot_status': return { active: true, tokens_deployed: 12, triggers_today: 3 }
    case 'toggle_honeypot': return { ok: true }
    case 'rotate_tokens': return { ok: true, rotated: 12 }
    case 'get_soar_dags': return []
    case 'save_soar_dag': return { ok: true }
    case 'dry_run_soar': return { ok: true, steps: [] }
    case 'get_tip_iocs': return mockIocs
    case 'import_stix': return { ok: true, imported: 5 }
    case 'get_rasp_devices': return mockDevices
    case 'revoke_device': return { ok: true }
    case 'run_terminal_command': return { stdout: '# mock output\n', stderr: '', code: 0 }
    case 'get_settings': return { api_url: 'https://api.sourcesealcorp.local', interval: 15 }
    case 'save_settings': return { ok: true }
    case 'reset_all': return { ok: true }
    default: return null
  }
}
