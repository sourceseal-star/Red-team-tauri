import { useState, useEffect, useCallback } from 'react';
import {
  Shield, Scan, Bug, Activity, FileText, Cpu,
  Loader2, RefreshCw, Play, AlertTriangle, CheckCircle2,
  XCircle, ChevronDown, ChevronUp, Crosshair, Eye, Zap
} from 'lucide-react';
import { getApiKey, authUrl } from '../lib/api';

const API_BASE = import.meta.env.VITE_API_BASE || '';
const LEV = '/api/leviathan';

function levHeaders(): Record<string, string> {
  const key = getApiKey();
  const h: Record<string, string> = { 'Content-Type': 'application/json' };
  if (key) h['Authorization'] = `Bearer ${key}`;
  return h;
}

interface LevModule { name: string; category: string; description: string; version: string }
interface LevScan { id: string; target: string; modules: string; status: string; started_at: string }
interface LevCamera { ip: string; port: number; vendor: string; model: string; is_accessible: number; is_vulnerable: number; rtsp_url: string; last_seen: string }

export default function LeviathanPanel() {
  const [status, setStatus] = useState<Record<string, any> | null>(null);
  const [modules, setModules] = useState<LevModule[]>([]);
  const [cameras, setCameras] = useState<LevCamera[]>([]);
  const [scans, setScans] = useState<LevScan[]>([]);
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  const [scanTarget, setScanTarget] = useState('');
  const [scanModules, setScanModules] = useState('all');
  const [exploitTarget, setExploitTarget] = useState('');
  const [exploitModule, setExploitModule] = useState('hikvision_rce');
  const [scanResult, setScanResult] = useState<string | null>(null);
  const [exploitResult, setExploitResult] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>('status');
  const [error, setError] = useState<string | null>(null);

  const toggle = (s: string) => setExpanded(expanded === s ? null : s);
  const setLoadingKey = (k: string, v: boolean) => setLoading(prev => ({ ...prev, [k]: v }));

  const fetchStatus = useCallback(async () => {
    setLoadingKey('status', true);
    try {
      const [s, m, c, sc] = await Promise.all([
        fetch(authUrl(`${API_BASE}${LEV}/status`), { headers: levHeaders() }).then(r => r.json()).catch(() => null),
        fetch(authUrl(`${API_BASE}${LEV}/modules`), { headers: levHeaders() }).then(r => r.json()).catch(() => null),
        fetch(authUrl(`${API_BASE}${LEV}/cameras`), { headers: levHeaders() }).then(r => r.json()).catch(() => null),
        fetch(authUrl(`${API_BASE}${LEV}/scans`), { headers: levHeaders() }).then(r => r.json()).catch(() => null),
      ]);
      setStatus(s);
      setModules(Array.isArray(m) ? m : (m?.modules || []));
      setCameras(Array.isArray(c) ? c : (c?.cameras || []));
      setScans(Array.isArray(sc) ? sc : (sc?.scans || []));
      setError(null);
    } catch (e: any) {
      setError(e.message || 'Error de conexión con LEVIATHAN');
    }
    setLoadingKey('status', false);
  }, []);

  useEffect(() => { fetchStatus(); }, [fetchStatus]);

  const runScan = async () => {
    if (!scanTarget.trim()) return;
    setLoadingKey('scan', true); setScanResult(null);
    try {
      const res = await fetch(`${API_BASE}${LEV}/scan`, {
        method: 'POST', headers: levHeaders(),
        body: JSON.stringify({ target: scanTarget, modules: scanModules === 'all' ? null : scanModules.split(',') }),
      });
      setScanResult(JSON.stringify(await res.json(), null, 2));
      fetchStatus();
    } catch (e: any) { setScanResult(`Error: ${e.message}`); }
    setLoadingKey('scan', false);
  };

  const runExploit = async () => {
    if (!exploitTarget.trim()) return;
    setLoadingKey('exploit', true); setExploitResult(null);
    try {
      const res = await fetch(`${API_BASE}${LEV}/exploit`, {
        method: 'POST', headers: levHeaders(),
        body: JSON.stringify({ target: exploitTarget, module: exploitModule }),
      });
      setExploitResult(JSON.stringify(await res.json(), null, 2));
    } catch (e: any) { setExploitResult(`Error: ${e.message}`); }
    setLoadingKey('exploit', false);
  };

  const genReport = async (format: string) => {
    setLoadingKey(`report_${format}`, true);
    try {
      const res = await fetch(`${API_BASE}${LEV}/report`, {
        method: 'POST', headers: levHeaders(),
        body: JSON.stringify({ target: scanTarget || 'last', format }),
      });
      const data = await res.json();
      if (data.report_url) window.open(data.report_url, '_blank');
    } catch (e: any) { setError(e.message); }
    setLoadingKey(`report_${format}`, false);
  };

  const moduleIcon = (cat: string) => {
    switch (cat) {
      case 'scanner': return <Scan className="w-4 h-4 text-cyan-400" />;
      case 'exploiter': return <Bug className="w-4 h-4 text-red-400" />;
      case 'ai_analyzer': return <Cpu className="w-4 h-4 text-purple-400" />;
      case 'reporter': return <FileText className="w-4 h-4 text-green-400" />;
      default: return <Activity className="w-4 h-4 text-slate-400" />;
    }
  };

  const catColor = (cat: string) => {
    switch (cat) {
      case 'scanner': return 'border-cyan-500/30 bg-cyan-900/5';
      case 'exploiter': return 'border-red-500/30 bg-red-900/5';
      case 'ai_analyzer': return 'border-purple-500/30 bg-purple-900/5';
      case 'reporter': return 'border-green-500/30 bg-green-900/5';
      default: return 'border-slate-500/30 bg-slate-900/5';
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Shield className="w-8 h-8 text-cyan-500" />
          <div>
            <h1 className="text-xl font-bold">LEVIATHAN</h1>
            <p className="text-xs text-slate-400">Red Team Automatizado — Scanners, Exploiters, AI y Reporters</p>
          </div>
        </div>
        <button onClick={fetchStatus} disabled={loading.status} className="p-2 rounded-lg border border-slate-700 hover:border-slate-500 transition">
          <RefreshCw className={`w-5 h-5 ${loading.status ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {error && (
        <div className="p-3 rounded-lg border border-red-500/30 bg-red-900/10 text-red-300 text-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" /> {error}
        </div>
      )}

      {/* Estado */}
      <Section title="Estado del Sistema" icon={<Activity className="w-4 h-4 text-cyan-400" />} expanded={expanded === 'status'} onClick={() => toggle('status')}>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard label="Scanners" value={status?.scanners ?? modules.filter(m => m.category === 'scanner').length} icon={<Scan className="w-4 h-4 text-cyan-400" />} />
          <StatCard label="Exploiters" value={status?.exploiters ?? modules.filter(m => m.category === 'exploiter').length} icon={<Bug className="w-4 h-4 text-red-400" />} />
          <StatCard label="AI Analyzers" value={status?.analyzers ?? modules.filter(m => m.category === 'ai_analyzer').length} icon={<Cpu className="w-4 h-4 text-purple-400" />} />
          <StatCard label="Reporters" value={status?.reporters ?? modules.filter(m => m.category === 'reporter').length} icon={<FileText className="w-4 h-4 text-green-400" />} />
        </div>
        <div className="text-xs text-slate-500 mt-2">
          Endpoints: <code className="text-cyan-400">/api/leviathan/*</code> + <code className="text-cyan-400">/api/v1/*</code>
        </div>
      </Section>

      {/* Módulos */}
      <Section title={`Módulos (${modules.length})`} icon={<Cpu className="w-4 h-4 text-purple-400" />} expanded={expanded === 'modules'} onClick={() => toggle('modules')}>
        {modules.length === 0 ? (
          <p className="text-sm text-slate-500">No hay módulos cargados. Verifica que leviathan_core esté instalado.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {modules.map(m => (
              <div key={m.name} className={`p-3 rounded-lg border ${catColor(m.category)}`}>
                <div className="flex items-center gap-2 mb-1">{moduleIcon(m.category)}<code className="text-xs font-mono text-slate-200">{m.name}</code></div>
                <p className="text-xs text-slate-400">{m.description}</p>
                <span className="text-[10px] text-slate-600 mt-1 block">v{m.version}</span>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* Escaneo */}
      <Section title="Escaneo de Red" icon={<Scan className="w-4 h-4 text-cyan-400" />} expanded={expanded === 'scan'} onClick={() => toggle('scan')}>
        <div className="flex flex-col md:flex-row gap-2">
          <input type="text" value={scanTarget} onChange={e => setScanTarget(e.target.value)}
            placeholder="192.168.1.0/24 (soporta /22, /20, /16)"
            className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-cyan-500 outline-none" />
          <input type="text" value={scanModules} onChange={e => setScanModules(e.target.value)}
            placeholder="all o rtsp_scanner,http_fingerprint"
            className="w-full md:w-48 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-cyan-500 outline-none" />
          <button onClick={runScan} disabled={loading.scan}
            className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-700 text-white text-sm font-medium flex items-center gap-2 disabled:opacity-50">
            {loading.scan ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />} Escanear
          </button>
        </div>
        {scanResult && <pre className="mt-3 bg-slate-900 border border-slate-800 rounded-lg p-3 text-xs text-slate-300 overflow-auto max-h-64">{scanResult}</pre>}
      </Section>

      {/* Explotación */}
      <Section title="Explotación Dirigida" icon={<Crosshair className="w-4 h-4 text-red-400" />} expanded={expanded === 'exploit'} onClick={() => toggle('exploit')}>
        <div className="flex flex-col md:flex-row gap-2">
          <input type="text" value={exploitTarget} onChange={e => setExploitTarget(e.target.value)}
            placeholder="IP objetivo (ej: 192.168.1.100)"
            className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-red-500 outline-none" />
          <select value={exploitModule} onChange={e => setExploitModule(e.target.value)}
            className="w-full md:w-48 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 outline-none">
            <option value="hikvision_rce">Hikvision RCE</option>
            <option value="dahua_backdoor">Dahua Backdoor</option>
            <option value="generic_brute">Generic Brute</option>
            <option value="exploit_chain">Exploit Chain</option>
            <option value="kraken_integration">KRAKEN Integration</option>
          </select>
          <button onClick={runExploit} disabled={loading.exploit}
            className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white text-sm font-medium flex items-center gap-2 disabled:opacity-50">
            {loading.exploit ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />} Ejecutar
          </button>
        </div>
        {exploitResult && <pre className="mt-3 bg-slate-900 border border-slate-800 rounded-lg p-3 text-xs text-slate-300 overflow-auto max-h-64">{exploitResult}</pre>}
      </Section>

      {/* Cámaras */}
      <Section title={`Cámaras Detectadas (${cameras.length})`} icon={<Eye className="w-4 h-4 text-amber-400" />} expanded={expanded === 'cameras'} onClick={() => toggle('cameras')}>
        {cameras.length === 0 ? (
          <p className="text-sm text-slate-500">No hay cámaras detectadas. Ejecuta un escaneo.</p>
        ) : (
          <div className="overflow-auto">
            <table className="w-full text-xs">
              <thead><tr className="text-slate-400 border-b border-slate-700">
                <th className="text-left py-2 px-2">IP</th><th className="text-left py-2 px-2">Puerto</th>
                <th className="text-left py-2 px-2">Vendor</th><th className="text-left py-2 px-2">Modelo</th>
                <th className="text-center py-2 px-2">Acceso</th><th className="text-center py-2 px-2">Vuln</th>
                <th className="text-left py-2 px-2">RTSP</th><th className="text-left py-2 px-2">Última vez</th>
              </tr></thead>
              <tbody>
                {cameras.map((c, i) => (
                  <tr key={i} className="border-b border-slate-800 hover:bg-slate-900/50">
                    <td className="py-2 px-2 font-mono text-cyan-300">{c.ip}</td>
                    <td className="py-2 px-2 text-slate-300">{c.port}</td>
                    <td className="py-2 px-2 text-slate-300">{c.vendor || '—'}</td>
                    <td className="py-2 px-2 text-slate-300">{c.model || '—'}</td>
                    <td className="py-2 px-2 text-center">{c.is_accessible ? <CheckCircle2 className="w-4 h-4 text-green-400 inline" /> : <XCircle className="w-4 h-4 text-slate-600 inline" />}</td>
                    <td className="py-2 px-2 text-center">{c.is_vulnerable ? <AlertTriangle className="w-4 h-4 text-red-400 inline" /> : <span className="text-slate-600">—</span>}</td>
                    <td className="py-2 px-2 font-mono text-slate-400 text-[10px]">{c.rtsp_url || '—'}</td>
                    <td className="py-2 px-2 text-slate-500 text-[10px]">{c.last_seen || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      {/* Historial */}
      <Section title={`Historial (${scans.length})`} icon={<FileText className="w-4 h-4 text-green-400" />} expanded={expanded === 'scans'} onClick={() => toggle('scans')}>
        {scans.length === 0 ? (
          <p className="text-sm text-slate-500">No hay escaneos registrados.</p>
        ) : (
          <div className="space-y-2">
            {scans.map((s, i) => (
              <div key={i} className="flex items-center justify-between p-2 rounded border border-slate-800 bg-slate-900/30">
                <div className="flex items-center gap-3">
                  <code className="text-xs font-mono text-cyan-300">{s.target}</code>
                  <span className={`text-[10px] px-2 py-0.5 rounded ${
                    s.status === 'completed' ? 'bg-green-900/30 text-green-400' :
                    s.status === 'running' ? 'bg-yellow-900/30 text-yellow-400' : 'bg-slate-800 text-slate-400'
                  }`}>{s.status}</span>
                </div>
                <span className="text-[10px] text-slate-500">{s.started_at || ''}</span>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* Informes */}
      <Section title="Generar Informes" icon={<FileText className="w-4 h-4 text-green-400" />} expanded={expanded === 'reports'} onClick={() => toggle('reports')}>
        <div className="flex flex-wrap gap-2">
          {['json', 'html', 'pdf'].map(fmt => (
            <button key={fmt} onClick={() => genReport(fmt)} disabled={loading[`report_${fmt}`]}
              className="px-4 py-2 rounded-lg border border-green-500/30 bg-green-900/10 hover:bg-green-900/20 text-green-300 text-sm font-medium uppercase disabled:opacity-50 flex items-center gap-2">
              {loading[`report_${fmt}`] ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />} {fmt}
            </button>
          ))}
        </div>
      </Section>
    </div>
  );
}

function Section({ title, icon, expanded, onClick, children }: { title: string; icon: React.ReactNode; expanded: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <div className="border border-slate-800 rounded-lg overflow-hidden">
      <button onClick={onClick} className="w-full flex items-center justify-between p-3 bg-slate-900/50 hover:bg-slate-900 transition">
        <span className="flex items-center gap-2 text-sm font-medium">{icon} {title}</span>
        {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>
      {expanded && <div className="p-4">{children}</div>}
    </div>
  );
}

function StatCard({ label, value, icon }: { label: string; value: number; icon: React.ReactNode }) {
  return (
    <div className="p-3 rounded-lg border border-slate-800 bg-slate-900/30">
      <div className="flex items-center gap-2 mb-1">{icon}<span className="text-xs text-slate-400">{label}</span></div>
      <span className="text-2xl font-bold text-slate-100">{value}</span>
    </div>
  );
}
