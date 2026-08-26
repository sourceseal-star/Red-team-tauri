import { useState, useEffect, useCallback } from 'react';
import {
  Shield, Scan, Bug, Cpu, FileText, Activity,
  Loader2, RefreshCw, Play, AlertTriangle, Camera
} from 'lucide-react';
import { getApiKey, authUrl } from '../lib/api';

const API_BASE = (import.meta as any).env?.VITE_API_BASE || '';
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

export default function LeviathanWidget() {
  const [status, setStatus] = useState<Record<string, any> | null>(null);
  const [modules, setModules] = useState<LevModule[]>([]);
  const [cameras, setCameras] = useState<LevCamera[]>([]);
  const [scans, setScans] = useState<LevScan[]>([]);
  const [loading, setLoading] = useState(false);
  const [scanTarget, setScanTarget] = useState('');
  const [scanResult, setScanResult] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    setLoading(true);
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
      setError(e.message || 'Sin conexión');
    }
    setLoading(false);
  }, []);

  useEffect(() => { fetchStatus(); const i = setInterval(fetchStatus, 15000); return () => clearInterval(i); }, [fetchStatus]);

  const runScan = async () => {
    if (!scanTarget.trim()) return;
    setScanning(true); setScanResult(null);
    try {
      const res = await fetch(`${API_BASE}${LEV}/scan`, {
        method: 'POST', headers: levHeaders(),
        body: JSON.stringify({ target: scanTarget, modules: null }),
      });
      setScanResult(JSON.stringify(await res.json(), null, 2));
      fetchStatus();
    } catch (e: any) { setScanResult(`Error: ${e.message}`); }
    setScanning(false);
  };

  const catCount = (cat: string) => modules.filter(m => m.category === cat).length;
  const activeScans = scans.filter(s => s.status === 'running' || s.status === 'active');
  const vulnCameras = cameras.filter(c => c.is_vulnerable);

  return (
    <div className="p-3 space-y-3 text-slate-100">
      {/* Header compacto */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className="w-5 h-5 text-purple-400" />
          <span className="text-xs font-bold text-purple-300">LEVIATHAN v3.0</span>
        </div>
        <button onClick={fetchStatus} disabled={loading} className="p-1 rounded hover:bg-slate-800 transition">
          <RefreshCw className={`w-3.5 h-3.5 text-slate-500 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-1.5 text-[10px] text-red-400 bg-red-900/20 border border-red-800/30 rounded px-2 py-1">
          <AlertTriangle className="w-3 h-3 flex-shrink-0" /> {error}
        </div>
      )}

      {/* Stats grid */}
      <div className="grid grid-cols-4 gap-1.5">
        <MiniStat icon={<Scan className="w-3 h-3 text-cyan-400" />} label="Scan" value={catCount('scanner')} />
        <MiniStat icon={<Bug className="w-3 h-3 text-red-400" />} label="Exploit" value={catCount('exploiter')} />
        <MiniStat icon={<Cpu className="w-3 h-3 text-purple-400" />} label="AI" value={catCount('ai_analyzer')} />
        <MiniStat icon={<FileText className="w-3 h-3 text-green-400" />} label="Report" value={catCount('reporter')} />
      </div>

      {/* Resumen rápido */}
      <div className="grid grid-cols-3 gap-1.5 text-center">
        <div className="bg-slate-900/60 border border-slate-800 rounded p-1.5">
          <div className="text-lg font-bold text-cyan-400">{modules.length}</div>
          <div className="text-[9px] text-slate-500 uppercase">Módulos</div>
        </div>
        <div className="bg-slate-900/60 border border-slate-800 rounded p-1.5">
          <div className="text-lg font-bold text-red-400">{cameras.length}</div>
          <div className="text-[9px] text-slate-500 uppercase">Cámaras</div>
        </div>
        <div className="bg-slate-900/60 border border-slate-800 rounded p-1.5">
          <div className="text-lg font-bold text-amber-400">{activeScans.length}</div>
          <div className="text-[9px] text-slate-500 uppercase">Scans</div>
        </div>
      </div>

      {/* Cámaras vulnerables detectadas */}
      {vulnCameras.length > 0 && (
        <div className="bg-red-900/10 border border-red-800/30 rounded p-2">
          <div className="flex items-center gap-1.5 mb-1">
            <Camera className="w-3 h-3 text-red-400" />
            <span className="text-[10px] font-bold text-red-400">Cámaras Vulnerables ({vulnCameras.length})</span>
          </div>
          <div className="space-y-1 max-h-20 overflow-y-auto">
            {vulnCameras.slice(0, 5).map((c, i) => (
              <div key={i} className="flex items-center justify-between text-[10px]">
                <span className="text-slate-300 font-mono">{c.ip}:{c.port}</span>
                <span className="text-red-400">{c.vendor}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Scans recientes */}
      {scans.length > 0 && (
        <div className="bg-slate-900/60 border border-slate-800 rounded p-2">
          <div className="flex items-center gap-1.5 mb-1">
            <Activity className="w-3 h-3 text-cyan-400" />
            <span className="text-[10px] font-bold text-slate-400">Scans Recientes</span>
          </div>
          <div className="space-y-1 max-h-20 overflow-y-auto">
            {scans.slice(0, 5).map((s, i) => (
              <div key={i} className="flex items-center justify-between text-[10px]">
                <span className="text-slate-300 font-mono">{s.target}</span>
                <span className={s.status === 'running' ? 'text-green-400' : s.status === 'completed' ? 'text-cyan-400' : 'text-slate-500'}>
                  {s.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Quick scan */}
      <div className="flex gap-1.5">
        <input
          type="text"
          value={scanTarget}
          onChange={e => setScanTarget(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && runScan()}
          placeholder="192.168.1.0/28"
          className="flex-1 bg-slate-900 border border-slate-700 rounded px-2 py-1 text-[11px] text-slate-100 placeholder-slate-600 focus:border-purple-500 outline-none"
        />
        <button
          onClick={runScan}
          disabled={scanning}
          className="px-2 py-1 rounded bg-purple-600 hover:bg-purple-700 text-white text-[10px] font-medium flex items-center gap-1 disabled:opacity-50"
        >
          {scanning ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />} Scan
        </button>
      </div>

      {scanResult && (
        <pre className="bg-slate-900 border border-slate-800 rounded p-2 text-[9px] text-slate-300 max-h-32 overflow-auto font-mono">
          {scanResult}
        </pre>
      )}
    </div>
  );
}

function MiniStat({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) {
  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded p-1.5 text-center">
      <div className="flex items-center justify-center mb-0.5">{icon}</div>
      <div className="text-sm font-bold text-slate-200">{value}</div>
      <div className="text-[8px] text-slate-600 uppercase">{label}</div>
    </div>
  );
}
