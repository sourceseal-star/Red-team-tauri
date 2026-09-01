import { useState, useEffect, useCallback } from 'react';
import { Server, Cloud, Cpu, HardDrive, RefreshCw, Activity, Database,
         AlertTriangle, Radio, Shield, Zap, Clock, MemoryStick, Gauge } from 'lucide-react';

export default function ControlTower() {
  const [health, setHealth] = useState<any>(null);
  const [services, setServices] = useState<any[]>([]);
  const [resources, setResources] = useState<any>(null);
  const [latest, setLatest] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  const authH = useCallback((): Record<string, string> => {
    const k = localStorage.getItem('api_token');
    return k ? { 'Authorization': `Bearer ${k}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' };
  }, []);

  const loadAll = useCallback(async () => {
    try {
      const [healthRes, svcRes, resRes, latestRes] = await Promise.all([
        fetch('/api/health', { headers: authH() }).catch(() => null),
        fetch('/api/services', { headers: authH() }).catch(() => null),
        fetch('/api/resources', { headers: authH() }).catch(() => null),
        fetch('/api/latest', { headers: authH() }).catch(() => null),
      ]);

      if (healthRes?.ok) setHealth(await healthRes.json());
      if (svcRes?.ok) {
        const sd = await svcRes.json();
        setServices(Array.isArray(sd) ? sd : (sd.services || []));
      }
      if (resRes?.ok) setResources(await resRes.json());
      if (latestRes?.ok) setLatest(await latestRes.json());
      setError(null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [authH]);

  useEffect(() => {
    loadAll();
    const interval = setInterval(loadAll, 5000);
    return () => clearInterval(interval);
  }, [loadAll]);

  const svcAction = async (action: string, name?: string) => {
    try {
      const url = name ? `/api/services/${action}?name=${name}` : `/api/services/${action}-all`;
      const r = await fetch(url, { method: 'POST', headers: authH() });
      const data = await r.json();
      setActionMsg(data.ok ? `✅ ${action} ${name || 'all'} OK` : `❌ ${data.error || 'fallo'}`);
      setTimeout(() => setActionMsg(null), 3000);
      loadAll();
    } catch (e: any) {
      setActionMsg(`❌ ${e.message}`);
    }
  };

  if (loading && !health) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-600">
        <RefreshCw size={24} className="animate-spin" />
      </div>
    );
  }

  const svcRunning = services.filter(s => s.status === 'running' || s.status === 'ok').length;
  const cpu = resources?.cpu_usage ?? health?.cpu ?? 0;
  const ram = resources?.memory_percent ?? health?.memory_percent ?? 0;
  const uptime = health?.uptime?.human || health?.uptime || '—';

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Cloud size={18} className="text-cyan-400" />
            Control Tower
          </h2>
          <p className="text-xs text-slate-500">Monitor del backend · {uptime}</p>
        </div>
        <button onClick={loadAll} className="p-2 hover:bg-slate-800 rounded-lg text-slate-400">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-800 rounded-lg p-3 text-xs text-red-400 flex items-center gap-2">
          <AlertTriangle size={14} /> {error}
        </div>
      )}

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <div className={`w-2 h-2 rounded-full ${health?.status === 'ok' ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`} />
            <Shield size={14} className="text-slate-500" />
          </div>
          <p className="text-[10px] text-slate-500 uppercase">Backend</p>
          <p className="text-xl font-bold text-white">{health?.status === 'ok' ? 'Online' : 'Offline'}</p>
          <p className="text-[9px] text-slate-600 mt-1">{health?.version || '—'}</p>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Server size={14} className="text-blue-400" />
          </div>
          <p className="text-[10px] text-slate-500 uppercase">Servicios</p>
          <p className="text-xl font-bold text-white">{svcRunning}<span className="text-sm text-slate-600">/{services.length}</span></p>
          <p className="text-[9px] text-slate-600 mt-1">activos</p>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Gauge size={14} className="text-cyan-400" />
          </div>
          <p className="text-[10px] text-slate-500 uppercase">CPU</p>
          <p className="text-xl font-bold text-white">{Math.round(cpu)}<span className="text-sm text-slate-600">%</span></p>
          <div className="h-1 bg-slate-800 rounded-full mt-2 overflow-hidden">
            <div className="h-full bg-cyan-400 rounded-full transition-all" style={{ width: `${cpu}%` }} />
          </div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <MemoryStick size={14} className="text-purple-400" />
          </div>
          <p className="text-[10px] text-slate-500 uppercase">RAM</p>
          <p className="text-xl font-bold text-white">{Math.round(ram)}<span className="text-sm text-slate-600">%</span></p>
          <div className="h-1 bg-slate-800 rounded-full mt-2 overflow-hidden">
            <div className="h-full bg-purple-400 rounded-full transition-all" style={{ width: `${ram}%` }} />
          </div>
        </div>
      </div>

      {/* Service control panel */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-xs font-bold text-white flex items-center gap-2">
            <Cpu size={12} className="text-cyan-400" /> Servicios del Sistema
          </h4>
          <div className="flex gap-2">
            <button onClick={() => svcAction('start-all')} className="px-2 py-1 text-[10px] bg-green-900/40 border border-green-800 rounded text-green-400 hover:bg-green-900/60">Start All</button>
            <button onClick={() => svcAction('stop-all')} className="px-2 py-1 text-[10px] bg-red-900/40 border border-red-800 rounded text-red-400 hover:bg-red-900/60">Stop All</button>
          </div>
        </div>

        {actionMsg && (
          <div className="mb-2 text-[10px] text-slate-300 bg-slate-950/50 rounded px-2 py-1 border border-slate-800">{actionMsg}</div>
        )}

        {services.length === 0 ? (
          <p className="text-xs text-slate-600 text-center py-4">No hay servicios registrados</p>
        ) : (
          <div className="space-y-1.5">
            {services.map(svc => {
              const running = svc.status === 'running' || svc.status === 'ok';
              return (
                <div key={svc.name} className="flex items-center justify-between bg-slate-950/40 rounded-lg px-3 py-2 border border-slate-800">
                  <div className="flex items-center gap-2">
                    <div className={`w-1.5 h-1.5 rounded-full ${running ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`} />
                    <span className="text-xs font-medium text-slate-200">{svc.name}</span>
                    {svc.port && <span className="text-[9px] text-slate-600 font-mono">:{svc.port}</span>}
                    {svc.pid && <span className="text-[9px] text-slate-600 font-mono">PID:{svc.pid}</span>}
                  </div>
                  <div className="flex gap-1">
                    {!running && <button onClick={() => svcAction('start', svc.name)} className="px-2 py-0.5 text-[9px] bg-green-900/30 rounded text-green-400 hover:bg-green-900/50 border border-green-900/50">Start</button>}
                    {running && <button onClick={() => svcAction('stop', svc.name)} className="px-2 py-0.5 text-[9px] bg-red-900/30 rounded text-red-400 hover:bg-red-900/50 border border-red-900/50">Stop</button>}
                    <button onClick={() => svcAction('restart', svc.name)} className="px-2 py-0.5 text-[9px] bg-slate-800 rounded text-slate-400 hover:bg-slate-700 border border-slate-700">Restart</button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Latest scan + system info */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
          <h4 className="text-xs font-bold text-white mb-3 flex items-center gap-2">
            <Activity size={12} className="text-amber-400" /> Último Escaneo
          </h4>
          {latest ? (
            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-slate-500">Findings totales</span>
                <span className="text-white font-bold">{latest.total_findings || 0}</span>
              </div>
              {latest.by_severity && (
                <div className="flex gap-2">
                  {['critical', 'high', 'medium', 'low', 'info'].map(sev => {
                    const count = latest.by_severity[sev] || 0;
                    const colors: Record<string, string> = { critical: 'text-red-400', high: 'text-orange-400', medium: 'text-yellow-400', low: 'text-green-400', info: 'text-blue-400' };
                    return count > 0 ? <span key={sev} className={`text-[10px] ${colors[sev]}`}>{sev}: {count}</span> : null;
                  })}
                </div>
              )}
              {latest.timestamp && <p className="text-[9px] text-slate-600">{latest.timestamp}</p>}
            </div>
          ) : (
            <p className="text-xs text-slate-600">Sin escaneos recientes</p>
          )}
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
          <h4 className="text-xs font-bold text-white mb-3 flex items-center gap-2">
            <Database size={12} className="text-cyan-400" /> Sistema
          </h4>
          <div className="space-y-1.5 text-xs">
            <div className="flex justify-between"><span className="text-slate-500">Versión</span><span className="text-slate-300 font-mono">{health?.version || '—'}</span></div>
            <div className="flex justify-between"><span className="text-slate-500">Uptime</span><span className="text-slate-300">{uptime}</span></div>
            <div className="flex justify-between"><span className="text-slate-500">Nmap</span><span className={health?.has_nmap ? 'text-green-400' : 'text-red-400'}>{health?.has_nmap ? 'Disponible' : 'No instalado'}</span></div>
            <div className="flex justify-between"><span className="text-slate-500">Honeypot</span><span className={health?.honeypot_running ? 'text-green-400' : 'text-slate-600'}>{health?.honeypot_running ? 'Activo' : 'Inactivo'}</span></div>
            <div className="flex justify-between"><span className="text-slate-500">WS Clients</span><span className="text-slate-300">{health?.ws_clients ?? 0}</span></div>
            <div className="flex justify-between"><span className="text-slate-500">Dist Built</span><span className={health?.dist_built ? 'text-green-400' : 'text-red-400'}>{health?.dist_built ? 'Sí' : 'No'}</span></div>
          </div>
        </div>
      </div>

      {/* Gateway mesh (optional, at bottom) */}
      <div className="bg-slate-900/40 border border-slate-800/50 rounded-xl p-3">
        <h4 className="text-[10px] text-slate-600 flex items-center gap-1">
          <Radio size={10} /> Gateway Mesh (opcional · :8080)
        </h4>
        <p className="text-[9px] text-slate-700 mt-1">Para federación multi-nodo. No requerido para funcionamiento normal.</p>
      </div>
    </div>
  );
}
