import { useEffect, useState } from 'react';
import { useScanStore } from '../../hooks/useScanStore';
import NetworkGraph from './NetworkGraph';
import RiskPanel from './RiskPanel';
import CommandPalette from './CommandPalette';
import HostDetailDrawer from './HostDetailDrawer';
import { useWebSocket } from '../../hooks/useWebSocket';

const API = '/api';

export default function DashboardProV2() {
  const hosts = useScanStore(s => s.hosts);
  const loading = useScanStore(s => s.loading);
  const error = useScanStore(s => s.error);
  const log = useScanStore(s => s.log);
  const { setHosts, setLoading, setError, pushLog } = useScanStore();
  const ws = useWebSocket('/ws');

  const runScan = async (label: string, path: string, method = 'POST', body?: any) => {
    setLoading(true); setError(null); pushLog(`⏳ ${label}...`);
    try {
      const res = await fetch(`${API}${path}`, {
        method,
        headers: body ? { 'Content-Type': 'application/json' } : {},
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      // Normalizar: los endpoints devuelven { results: Host[] }
      const items = (data.results || data.hosts || []).map((h: any) => ({
        ip: h.ip || h.host,
        mac: h.mac, vendor: h.vendor,
        ports: h.ports || [],
        first_seen: new Date().toISOString(),
        type: h.type || 'unknown',
      }));
      setHosts(items);
      pushLog(`✔ ${label}: ${items.length} hosts`);
    } catch (e: any) {
      setError(e.message);
      pushLog(`✘ ${label}: ${e.message}`);
    } finally { setLoading(false); }
  };

  // WebSocket: alertas
  useEffect(() => {
    if (!ws) return;
    ws.onmessage = (ev) => {
      try {
        const m = JSON.parse(ev.data);
        if (m.type === 'alert') pushLog(`🚨 ${m.payload}`);
      } catch {}
    };
  }, [ws, pushLog]);

  // Escaneo inicial
  useEffect(() => { runScan('Topología inicial', '/scan/topology'); }, []);

  const actions = [
    { id: 'topo',   label: '🗺️ Escanear topología', run: () => runScan('Topología', '/scan/topology') },
    { id: 'cam',    label: '📹 Escanear cámaras',    run: () => runScan('Cámaras', '/scan/cameras') },
    { id: 'rou',    label: '📡 Escanear routers',    run: () => runScan('Routers', '/scan/routers') },
    { id: 'iot',    label: '🔌 Escanear IoT',        run: () => runScan('IoT', '/scan/iot') },
    { id: 'wifi',   label: '📶 Escanear WiFi',       run: () => runScan('WiFi', '/scan/wifi') },
    { id: 'radio',  label: '📻 Escanear espectro',   run: () => runScan('Radio', '/scan/radio') },
    { id: 'shodan', label: '🔍 Shodan global',       run: () => runScan('Shodan', '/osint/shodan', 'GET') },
    { id: 'canary', label: '🪤 Generar canary',      run: () => runScan('Canary', '/canary/generate') },
  ];

  const shodanLookup = async (ip: string) => {
    await runScan(`Shodan → ${ip}`, `/osint/shodan?ip=${ip}`, 'GET');
  };

  return (
    <div className="min-h-screen bg-[var(--ss-bg)] text-gray-200 font-mono p-4">
      {/* Header */}
      <header className="flex justify-between items-center pb-3 mb-4 border-b border-[var(--ss-border)]">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-gradient-to-br from-cyan-400 to-amber-400 rotate-45" />
          <div>
            <div className="text-lg font-bold tracking-wider">RED-TEAM <span className="text-cyan-400">TAURI</span></div>
            <div className="text-[10px] text-gray-500 tracking-widest">SOBERANÍA OPERATIVA · SSP-ZKP-2048-L4</div>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <CommandPalette actions={actions} />
          <div className="flex items-center gap-2 text-[10px] text-cyan-300">
            <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
            ONLINE
          </div>
        </div>
      </header>

      {error && (
        <div className="mb-3 px-3 py-2 bg-red-500/10 border border-red-500/30 text-red-300 text-xs">
          ⚠ {error}
        </div>
      )}

      {/* Stats rápidas */}
      <div className="grid grid-cols-4 gap-3 mb-4">
        {[
          { k: 'HOSTS', v: hosts.length, c: 'cyan' },
          { k: 'CRÍTICOS', v: hosts.filter(h => h.risk === 'critical').length, c: 'red' },
          { k: 'ALERTAS', v: log.filter(l => l.includes('🚨')).length, c: 'amber' },
          { k: 'OPERACIONES', v: log.length, c: 'green' },
        ].map(s => (
          <div key={s.k} className="bg-[var(--ss-bg-2)] border border-[var(--ss-border)] p-3 border-l-4"
               style={{ borderLeftColor: `var(--ss-${s.c})` }}>
            <div className="text-2xl font-bold" style={{ color: `var(--ss-${s.c})` }}>{s.v}</div>
            <div className="text-[9px] text-gray-500 tracking-widest">{s.k}</div>
          </div>
        ))}
      </div>

      {/* Grid principal */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
        <div className="lg:col-span-2"><NetworkGraph /></div>
        <div><RiskPanel /></div>
      </div>

      {/* Acciones rápidas */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-2 mb-4">
        {actions.map(a => (
          <button key={a.id} onClick={a.run} disabled={loading}
                  className="px-2 py-2 border border-cyan-500/30 text-cyan-300 text-[10px] uppercase tracking-wider hover:bg-cyan-500/10 hover:border-cyan-400 disabled:opacity-50 transition">
            {loading ? '⏳' : a.label}
          </button>
        ))}
      </div>

      {/* Log */}
      <div className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] p-3">
        <h3 className="text-[10px] uppercase tracking-widest text-amber-400 mb-2">Registro operativo</h3>
        <div className="h-40 overflow-y-auto text-[10px] space-y-0.5">
          {log.map((l, i) => <div key={i} className="text-gray-400">{l}</div>)}
        </div>
      </div>

      {/* Drawer lateral */}
      <HostDetailDrawer onShodan={shodanLookup} />
    </div>
  );
}
