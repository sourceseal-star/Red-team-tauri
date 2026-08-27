import { useState, useEffect, useCallback } from 'react';
import {
  Bug, Server, AlertTriangle, CheckCircle2, XCircle,
  Loader2, RefreshCw, Play, Square, Activity, Zap, Search,
  ChevronDown, ChevronUp, Crosshair, Clock
} from 'lucide-react';
import { getApiKey } from '../lib/api';

function krakenHeaders(): Record<string, string> {
  const key = getApiKey();
  return key ? { 'Authorization': `Bearer ${key}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' };
}

interface Exploit {
  ip: string; port: number; service: string;
  vulnerability: string; cve: string;
  success: boolean; attempted_at: string;
}

interface Host {
  ip: string; last_seen: string; os: string;
}

interface ScanLog {
  target: string; started_at: string;
  hosts_found: number; exploits_found: number;
}

interface Priority {
  ip: string; exploit_count: number; services: string;
}

type TabId = 'exploits' | 'hosts' | 'priorities' | 'scanlog' | 'scripts';

const TABS: { id: TabId; label: string; icon: typeof Bug }[] = [
  { id: 'exploits', label: 'Exploits', icon: Crosshair },
  { id: 'hosts', label: 'Hosts', icon: Server },
  { id: 'priorities', label: 'Prioridades', icon: Zap },
  { id: 'scanlog', label: 'Scan Log', icon: Clock },
  { id: 'scripts', label: 'NSE Scripts', icon: Bug },
];

export default function KrakenPanel() {
  const [target, setTarget] = useState('192.168.1.0/24');
  const [scanning, setScanning] = useState(false);
  const [daemonRunning, setDaemonRunning] = useState(false);
  const [activeTab, setActiveTab] = useState<TabId>('exploits');
  const [exploits, setExploits] = useState<Exploit[]>([]);
  const [hosts, setHosts] = useState<Host[]>([]);
  const [scans, setScans] = useState<ScanLog[]>([]);
  const [priorities, setPriorities] = useState<Priority[]>([]);
  const [scripts, setScripts] = useState<string[]>([]);
  const [ports, setPorts] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [scanResult, setScanResult] = useState<{ hosts_found: number; exploits_found: number } | null>(null);
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());

  const toggleRow = (idx: number) => {
    setExpandedRows(prev => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx); else next.add(idx);
      return next;
    });
  };

  const loadResults = useCallback(async () => {
    try {
      const [resResults, resPrio, resDaemon, resScripts] = await Promise.all([
        fetch('/api/kraken/results', { headers: krakenHeaders() }),
        fetch('/api/kraken/priorities', { headers: krakenHeaders() }),
        fetch('/api/kraken/daemon/status', { headers: krakenHeaders() }),
        fetch('/api/kraken/scripts', { headers: krakenHeaders() }),
      ]);
      if (resResults.ok) {
        const d = await resResults.json();
        setExploits(d.exploits || []);
        setHosts(d.hosts || []);
        setScans(d.scans || []);
      }
      if (resPrio.ok) {
        const d = await resPrio.json();
        setPriorities(d.priorities || []);
      }
      if (resDaemon.ok) {
        const d = await resDaemon.json();
        setDaemonRunning(d.running || false);
      }
      if (resScripts.ok) {
        const d = await resScripts.json();
        setScripts(d.scripts || []);
        setPorts(d.ports || '');
      }
    } catch (e) {
      // ignore on first load
    }
  }, []);

  useEffect(() => { loadResults(); }, [loadResults]);

  useEffect(() => {
    if (!daemonRunning) return;
    const i = setInterval(async () => {
      try {
        const res = await fetch('/api/kraken/daemon/status', { headers: krakenHeaders() });
        if (res.ok) {
          const d = await res.json();
          setDaemonRunning(d.running || false);
          if (d.running) loadResults();
        }
      } catch {}
    }, 5000);
    return () => clearInterval(i);
  }, [daemonRunning, loadResults]);

  const handleScan = async () => {
    setScanning(true);
    setError(null);
    setStatusMsg(null);
    setScanResult(null);
    try {
      const res = await fetch(`/api/kraken/scan?target=${encodeURIComponent(target.trim())}`, {
        headers: krakenHeaders(),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || `HTTP ${res.status}`);
      } else {
        setScanResult({ hosts_found: data.hosts_found || 0, exploits_found: data.exploits_found || 0 });
        setStatusMsg(`Escaneo completado: ${data.hosts_found} hosts, ${data.exploits_found} exploits`);
        loadResults();
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setScanning(false);
    }
  };

  const handleDaemonToggle = async () => {
    setError(null);
    try {
      if (daemonRunning) {
        const res = await fetch('/api/kraken/daemon/stop', {
          method: 'POST', headers: krakenHeaders(),
        });
        if (res.ok) {
          setDaemonRunning(false);
          setStatusMsg('Daemon detenido');
        }
      } else {
        const res = await fetch(`/api/kraken/daemon/start?target=${encodeURIComponent(target.trim())}&interval=3600`, {
          method: 'POST', headers: krakenHeaders(),
        });
        const data = await res.json();
        if (res.ok) {
          setDaemonRunning(true);
          setStatusMsg(`Daemon iniciado — target: ${target}, intervalo: 60 min`);
        } else {
          setError(data.error || `HTTP ${res.status}`);
        }
      }
    } catch (e: any) {
      setError(e.message);
    }
  };

  return (
    <div className="bg-[var(--ss-bg-2)] border border-[var(--ss-border)] rounded-lg p-3.5 h-full flex flex-col font-sans space-y-3 overflow-hidden">
      {/* HEADER */}
      <div className="flex items-center justify-between pb-2 border-b border-[var(--ss-border)]">
        <h3 className="text-xs font-bold uppercase tracking-widest text-red-400 flex items-center gap-2 font-mono">
          <Bug size={15} /> KRAKEN v4.0 — NSE Exploit Scanner
        </h3>
        <div className={`flex items-center gap-1 text-[10px] font-mono ${daemonRunning ? 'text-green-400' : 'text-slate-500'}`}>
          <div className={`w-1.5 h-1.5 rounded-full ${daemonRunning ? 'bg-green-400 animate-pulse' : 'bg-slate-600'}`} />
          {daemonRunning ? 'DAEMON' : 'IDLE'}
        </div>
      </div>

      {/* CONTROLS */}
      <div className="flex flex-col gap-2">
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              value={target}
              onChange={e => setTarget(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !scanning && handleScan()}
              placeholder="192.168.1.0/24 o IP"
              className="w-full bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded-md pl-8 pr-3 py-2 text-xs text-slate-200 font-mono outline-none focus:border-red-500/50 placeholder:text-slate-600"
            />
          </div>
          <button
            onClick={handleScan}
            disabled={scanning || !target.trim()}
            className="px-3 py-2 text-xs font-mono border border-red-500/40 text-red-300 rounded-md hover:bg-red-500/10 disabled:opacity-40 transition flex items-center gap-1.5 shrink-0"
          >
            {scanning ? <Loader2 size={14} className="animate-spin" /> : <Crosshair size={14} />}
            {scanning ? 'Scanning...' : 'Escanear'}
          </button>
          <button
            onClick={handleDaemonToggle}
            className={`px-3 py-2 text-xs font-mono border rounded-md transition flex items-center gap-1.5 shrink-0 ${
              daemonRunning
                ? 'border-red-500/40 text-red-300 hover:bg-red-500/10'
                : 'border-green-500/40 text-green-300 hover:bg-green-500/10'
            }`}
          >
            {daemonRunning ? <Square size={14} /> : <Play size={14} />}
            {daemonRunning ? 'Stop' : 'Daemon'}
          </button>
        </div>

        {error && (
          <div className="text-xs font-mono text-red-400 bg-red-500/10 border border-red-500/30 rounded-md p-2 flex items-start gap-2">
            <AlertTriangle size={14} className="shrink-0 mt-0.5" />
            <span className="break-all">{error}</span>
          </div>
        )}
        {statusMsg && !error && (
          <div className="text-xs font-mono text-green-400 bg-green-500/10 border border-green-500/30 rounded-md p-2 flex items-center gap-2">
            <CheckCircle2 size={14} className="shrink-0" />
            <span>{statusMsg}</span>
          </div>
        )}
        {scanResult && (
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded-md p-2.5 text-center">
              <div className="text-[10px] text-slate-500 uppercase font-mono">Hosts</div>
              <div className="text-lg font-bold text-cyan-400 font-mono">{scanResult.hosts_found}</div>
            </div>
            <div className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded-md p-2.5 text-center">
              <div className="text-[10px] text-slate-500 uppercase font-mono">Exploits</div>
              <div className="text-lg font-bold text-red-400 font-mono">{scanResult.exploits_found}</div>
            </div>
          </div>
        )}
      </div>

      {/* TABS */}
      <div className="flex gap-1 overflow-x-auto pb-1 border-b border-[var(--ss-border)]">
        {TABS.map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-1.5 text-[11px] font-mono rounded-t-md border-b-2 transition flex items-center gap-1.5 whitespace-nowrap ${
                activeTab === tab.id
                  ? 'border-red-500 text-red-300 bg-red-500/5'
                  : 'border-transparent text-slate-500 hover:text-slate-300'
              }`}
            >
              <Icon size={12} />
              {tab.label}
              {tab.id === 'exploits' && exploits.length > 0 && (
                <span className="ml-1 text-[9px] bg-red-500/20 text-red-400 px-1.5 rounded-full">{exploits.length}</span>
              )}
              {tab.id === 'hosts' && hosts.length > 0 && (
                <span className="ml-1 text-[9px] bg-slate-500/20 text-slate-400 px-1.5 rounded-full">{hosts.length}</span>
              )}
            </button>
          );
        })}
      </div>

      {/* TAB CONTENT */}
      <div className="flex-1 overflow-y-auto space-y-1.5 pr-1">
        {activeTab === 'exploits' && (
          exploits.length === 0 ? (
            <div className="text-slate-500 text-xs font-mono italic text-center py-8">
              No hay exploits registrados. Ejecuta un escaneo para comenzar.
            </div>
          ) : (
            exploits.map((exp, idx) => (
              <div key={idx} className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded-md p-2 text-xs font-mono">
                <div className="flex items-center justify-between gap-2 cursor-pointer" onClick={() => toggleRow(idx)}>
                  <div className="flex items-center gap-2 min-w-0">
                    {exp.success ? (
                      <CheckCircle2 size={14} className="text-green-400 shrink-0" />
                    ) : (
                      <XCircle size={14} className="text-red-400 shrink-0" />
                    )}
                    <span className="text-slate-200 truncate">{exp.ip}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 shrink-0">
                      :{exp.port}
                    </span>
                    <span className="text-slate-400 text-[10px] shrink-0">{exp.service}</span>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {exp.cve !== 'N/A' && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-red-500/10 text-red-300 border border-red-500/30">
                        {exp.cve}
                      </span>
                    )}
                    {expandedRows.has(idx) ? <ChevronUp size={12} className="text-slate-500" /> : <ChevronDown size={12} className="text-slate-500" />}
                  </div>
                </div>
                {expandedRows.has(idx) && (
                  <div className="mt-2 pt-2 border-t border-[var(--ss-border)] text-[11px] text-slate-400 break-all">
                    {exp.vulnerability}
                  </div>
                )}
              </div>
            ))
          )
        )}

        {activeTab === 'hosts' && (
          hosts.length === 0 ? (
            <div className="text-slate-500 text-xs font-mono italic text-center py-8">
              No hay hosts registrados.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
              {hosts.map((h, idx) => (
                <div key={idx} className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded-md p-2 text-xs font-mono">
                  <div className="flex items-center justify-between">
                    <span className="text-cyan-300 font-semibold">{h.ip}</span>
                    <span className="text-[10px] text-slate-500">{h.last_seen?.slice(0, 19) || ''}</span>
                  </div>
                  <div className="text-[10px] text-slate-400 mt-0.5">OS: {h.os || 'Unknown'}</div>
                </div>
              ))}
            </div>
          )
        )}

        {activeTab === 'priorities' && (
          priorities.length === 0 ? (
            <div className="text-slate-500 text-xs font-mono italic text-center py-8">
              No hay IPs priorizadas. Escanea y encuentra exploits para generar prioridades.
            </div>
          ) : (
            priorities.map((p, idx) => (
              <div key={idx} className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded-md p-2.5 text-xs font-mono">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-amber-400 font-bold text-base">#{idx + 1}</span>
                    <span className="text-slate-200">{p.ip}</span>
                  </div>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-red-500/10 text-red-300 border border-red-500/30">
                    {p.exploit_count} exploits
                  </span>
                </div>
                {p.services && (
                  <div className="text-[10px] text-slate-500 mt-1">Servicios: {p.services}</div>
                )}
              </div>
            ))
          )
        )}

        {activeTab === 'scanlog' && (
          scans.length === 0 ? (
            <div className="text-slate-500 text-xs font-mono italic text-center py-8">
              No hay escaneos registrados.
            </div>
          ) : (
            <div className="space-y-1">
              {scans.map((s, idx) => (
                <div key={idx} className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded-md p-2 text-xs font-mono flex items-center justify-between">
                  <div>
                    <span className="text-slate-200">{s.target}</span>
                    <span className="text-[10px] text-slate-500 ml-2">{s.started_at?.slice(0, 19)}</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="text-[10px] text-cyan-400">{s.hosts_found} hosts</span>
                    <span className="text-[10px] text-red-400">{s.exploits_found} exploits</span>
                  </div>
                </div>
              ))}
            </div>
          )
        )}

        {activeTab === 'scripts' && (
          <div className="space-y-2">
            <div className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded-md p-2.5">
              <div className="text-[10px] text-slate-500 uppercase font-mono mb-1.5">Puertos escaneados</div>
              <div className="text-xs text-slate-300 font-mono break-all">{ports || 'N/A'}</div>
            </div>
            <div className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded-md p-2.5">
              <div className="text-[10px] text-slate-500 uppercase font-mono mb-1.5">Scripts NSE activos ({scripts.length})</div>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-1">
                {scripts.map((s, idx) => (
                  <div key={idx} className="text-[10px] font-mono text-slate-300 bg-[var(--ss-bg-2)] border border-[var(--ss-border)] rounded px-1.5 py-1">
                    {s}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* FOOTER */}
      <div className="flex items-center justify-between pt-1 border-t border-[var(--ss-border)] text-[10px] font-mono text-slate-600">
        <span className="flex items-center gap-1"><Activity size={10} /> {exploits.length} exploits | {hosts.length} hosts</span>
        <button onClick={loadResults} className="flex items-center gap-1 text-slate-500 hover:text-slate-300 transition">
          <RefreshCw size={10} /> Refresh
        </button>
      </div>
    </div>
  );
}
