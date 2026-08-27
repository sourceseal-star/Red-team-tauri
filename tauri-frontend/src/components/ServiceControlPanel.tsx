import React, { useState, useEffect, useCallback } from 'react';
import { Play, Square, RotateCw, Terminal, Activity, Cpu, HardDrive, AlertTriangle, CheckCircle, XCircle, RefreshCw } from 'lucide-react';

interface Service {
  name: string;
  description?: string;
  status: 'running' | 'stopped' | 'error' | 'restarting';
  pid?: number;
  uptime?: string;
  cpu?: number;
  memory?: number;
  port?: number;
  lastLog?: string;
}

function getApiKey(): string | null {
  return localStorage.getItem('api_token');
}

const statusConfig = {
  running: { color: 'text-green-400', bg: 'bg-green-900/20', border: 'border-green-800', icon: CheckCircle, label: 'Running' },
  stopped: { color: 'text-slate-400', bg: 'bg-slate-900/40', border: 'border-slate-700', icon: XCircle, label: 'Stopped' },
  error: { color: 'text-red-400', bg: 'bg-red-900/20', border: 'border-red-800', icon: AlertTriangle, label: 'Error' },
  restarting: { color: 'text-amber-400', bg: 'bg-amber-900/20', border: 'border-amber-800', icon: RotateCw, label: 'Restarting' },
};

export default function ServiceControlPanel() {
  const [services, setServices] = useState<Service[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedService, setSelectedService] = useState<string | null>(null);
  const [logs, setLogs] = useState('');
  const [actionMsg, setActionMsg] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const apiKey = getApiKey();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (apiKey) headers['X-API-Key'] = apiKey;

  const fetchServices = useCallback(async () => {
    try {
      setRefreshing(true);
      const res = await fetch('/api/services', { headers });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setServices(Array.isArray(data) ? data : []);
    } catch (err) {
      // Fallback: show empty state, not mock
      setServices([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchServices();
    const interval = setInterval(fetchServices, 5000);
    return () => clearInterval(interval);
  }, [fetchServices]);

  const handleAction = async (action: 'start' | 'stop' | 'restart', name: string) => {
    try {
      const res = await fetch(`/api/services/${action}?name=${encodeURIComponent(name)}`, {
        method: 'POST',
        headers,
      });
      const data = await res.json();
      if (!res.ok) {
        setActionMsg(`${name}: ${data.error || 'error'}`);
        setTimeout(() => setActionMsg(''), 3000);
      } else {
        setActionMsg(`${name}: ${action} OK`);
        setTimeout(() => setActionMsg(''), 2000);
        fetchServices();
      }
    } catch (err) {
      setActionMsg(`${name}: connection error`);
      setTimeout(() => setActionMsg(''), 3000);
    }
  };

  const handleStartAll = async () => {
    try {
      await fetch('/api/services/start-all', { method: 'POST', headers });
      setActionMsg('All services starting...');
      setTimeout(() => setActionMsg(''), 3000);
      fetchServices();
    } catch {}
  };

  const handleStopAll = async () => {
    try {
      await fetch('/api/services/stop-all', { method: 'POST', headers });
      setActionMsg('All services stopping...');
      setTimeout(() => setActionMsg(''), 3000);
      fetchServices();
    } catch {}
  };

  const fetchLogs = async (name: string) => {
    try {
      const res = await fetch(`/api/services/${encodeURIComponent(name)}/logs`, { headers });
      if (res.ok) {
        const data = await res.json();
        setLogs(data.logs || data.content || 'No logs available');
      } else {
        setLogs('Error fetching logs');
      }
    } catch {
      setLogs('Connection error');
    }
  };

  if (loading && services.length === 0) {
    return (
      <div className="flex items-center justify-center h-full p-8">
        <div className="w-5 h-5 border-2 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin mr-3" />
        <span className="text-xs text-slate-500">Cargando servicios...</span>
      </div>
    );
  }

  if (!loading && services.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 text-center">
        <AlertTriangle size={24} className="text-amber-500/50 mb-2" />
        <p className="text-xs text-slate-500">No se pudieron cargar los servicios</p>
        <p className="text-[10px] text-slate-600 mt-1">Verifica que el backend esté corriendo en puerto 8001</p>
        <button onClick={fetchServices} className="mt-3 px-3 py-1.5 text-[10px] bg-slate-800 border border-slate-700 rounded-lg text-slate-300 hover:bg-slate-700 flex items-center gap-1">
          <RefreshCw size={10} /> Reintentar
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-slate-800/50">
        <div className="flex items-center gap-2">
          <Activity size={12} className="text-cyan-400" />
          <span className="text-[10px] font-bold text-slate-400 uppercase">{services.length} servicios</span>
          {refreshing && <RefreshCw size={10} className="text-slate-600 animate-spin" />}
        </div>
        <div className="flex gap-1.5">
          <button onClick={handleStartAll} className="px-2 py-1 text-[9px] bg-green-900/30 border border-green-800 rounded text-green-400 hover:bg-green-900/50 flex items-center gap-1">
            <Play size={8} /> Start All
          </button>
          <button onClick={handleStopAll} className="px-2 py-1 text-[9px] bg-red-900/30 border border-red-800 rounded text-red-400 hover:bg-red-900/50 flex items-center gap-1">
            <Square size={8} /> Stop All
          </button>
        </div>
      </div>

      {actionMsg && (
        <div className="px-3 py-1.5 text-[10px] text-cyan-400 bg-cyan-900/20 border-b border-cyan-900/30">
          {actionMsg}
        </div>
      )}

      {/* Services list */}
      <div className="flex-1 overflow-auto p-2 space-y-1.5">
        {services.map((svc) => {
          const cfg = statusConfig[svc.status] || statusConfig.stopped;
          const Icon = cfg.icon;
          return (
            <div key={svc.name} className={`rounded-lg border ${cfg.border} ${cfg.bg} p-2.5`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <Icon size={12} className={`${cfg.color} flex-shrink-0`} />
                  <div className="min-w-0">
                    <div className="text-[11px] font-bold text-slate-200 truncate">{svc.name}</div>
                    {svc.description && <div className="text-[9px] text-slate-500 truncate">{svc.description}</div>}
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <button onClick={() => handleAction('start', svc.name)} disabled={svc.status === 'running'} className="p-1 text-green-400 hover:bg-green-900/30 rounded disabled:opacity-30" title="Start">
                    <Play size={10} />
                  </button>
                  <button onClick={() => handleAction('stop', svc.name)} disabled={svc.status === 'stopped'} className="p-1 text-red-400 hover:bg-red-900/30 rounded disabled:opacity-30" title="Stop">
                    <Square size={10} />
                  </button>
                  <button onClick={() => handleAction('restart', svc.name)} className="p-1 text-amber-400 hover:bg-amber-900/30 rounded" title="Restart">
                    <RotateCw size={10} />
                  </button>
                  <button onClick={() => { setSelectedService(svc.name); fetchLogs(svc.name); }} className="p-1 text-slate-400 hover:bg-slate-800 rounded" title="Logs">
                    <Terminal size={10} />
                  </button>
                </div>
              </div>

              {/* Stats row */}
              <div className="flex items-center gap-3 mt-1.5 text-[9px] text-slate-500">
                {svc.pid && <span className="flex items-center gap-0.5"><Cpu size={8} /> PID {svc.pid}</span>}
                {svc.port && svc.port > 0 && <span>:{svc.port}</span>}
                {svc.uptime && <span>{svc.uptime}</span>}
                {svc.cpu !== undefined && svc.cpu > 0 && <span className="flex items-center gap-0.5"><Cpu size={8} /> {svc.cpu}%</span>}
                {svc.memory !== undefined && svc.memory > 0 && <span className="flex items-center gap-0.5"><HardDrive size={8} /> {svc.memory}MB</span>}
              </div>

              {svc.lastLog && (
                <div className="mt-1 text-[9px] text-slate-600 truncate font-mono">{svc.lastLog}</div>
              )}
            </div>
          );
        })}
      </div>

      {/* Logs modal */}
      {selectedService && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50" onClick={() => setSelectedService(null)}>
          <div className="bg-slate-900 border border-slate-700 rounded-2xl p-4 max-w-2xl w-full max-h-[60vh] flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2"><Terminal size={14} className="text-cyan-400" /> Logs: {selectedService}</h3>
              <button onClick={() => setSelectedService(null)} className="text-slate-500 hover:text-white text-xs">✕</button>
            </div>
            <pre className="flex-1 overflow-auto text-[10px] text-slate-400 font-mono bg-slate-950 rounded p-3 border border-slate-800">{logs || 'Cargando...'}</pre>
            <button onClick={() => fetchLogs(selectedService)} className="mt-2 px-3 py-1.5 text-[10px] bg-slate-800 border border-slate-700 rounded text-slate-300 hover:bg-slate-700 flex items-center gap-1 self-start">
              <RefreshCw size={10} /> Refrescar logs
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
