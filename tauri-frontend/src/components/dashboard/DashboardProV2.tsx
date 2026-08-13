import { useEffect, useState, lazy, Suspense } from 'react';
import { useScanStore } from '../../hooks/useScanStore';
const TopologyMap = lazy(() => import('./TopologyMap'));
const CameraGrid = lazy(() => import('../CameraGrid'));
import RiskPanel from './RiskPanel';
import CommandPalette from './CommandPalette';
import HostDetailDrawer from './HostDetailDrawer';
import { EvidenceExporter } from '../EvidenceExporter';
import { MurcielagoPanel } from '../MurcielagoPanel';
import { useWebSocket } from '../../hooks/useWebSocket';
import type { CameraWithSnapshot } from '../../types/camera';

type ViewMode = 'topology' | 'cameras' | 'evidence' | 'murcielago';

export default function DashboardProV2() {
  const hosts = useScanStore(s => s.hosts);
  const loading = useScanStore(s => s.loading);
  const error = useScanStore(s => s.error);
  const log = useScanStore(s => s.log);
  const { setHosts, setLoading, setError, pushLog } = useScanStore();
  const ws = useWebSocket('/ws');
  const [view, setView] = useState<ViewMode>('topology');
  const [cameras, setCameras] = useState<CameraWithSnapshot[]>([]);

  const runScan = async (label: string, path: string, method = 'POST', body?: any) => {
    setLoading(true); setError(null); pushLog(`⏳ ${label}...`);
    try {
      const res = await fetch(path, {
        method,
        headers: body ? { 'Content-Type': 'application/json' } : {},
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const items = (data.results || data.hosts || []).map((h: any) => ({
        ip: h.ip || h.host,
        mac: h.mac, vendor: h.vendor,
        ports: h.ports || [],
        risk: h.risk,
        risk_reasons: h.risk_reasons || [],
        first_seen: h.first_seen || new Date().toISOString(),
        type: h.type || 'unknown',
      }));
      setHosts(items);
      pushLog(`✔ ${label}: ${items.length} hosts`);
      return items;
    } catch (e: any) {
      setError(e.message);
      pushLog(`✘ ${label}: ${e.message}`);
      return [];
    } finally { setLoading(false); }
  };

  const runCameras = async () => {
    setView('cameras');
    setLoading(true); setError(null); pushLog('⏳ Escaneando cámaras...');
    try {
      const res = await fetch('/api/scan/cameras', { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const cams = (data.results || []).map((c: any) => ({
        ip: c.ip,
        rtsp: c.rtsp,
        ports: c.ports,
        type: c.type || 'camera',
        first_seen: c.first_seen,
      }));
      setCameras(cams);
      pushLog(`✔ Cámaras: ${cams.length} detectadas`);
    } catch (e: any) {
      setError(e.message);
      pushLog(`✘ Cámaras: ${e.message}`);
    } finally { setLoading(false); }
  };

  useEffect(() => {
    if (!ws) return;
    ws.onmessage = (ev) => {
      try {
        const m = JSON.parse(ev.data);
        if (m.type === 'alert') pushLog(`🚨 ${m.payload}`);
        if (m.type === 'progress') pushLog(`📊 ${m.payload}`);
      } catch {}
    };
  }, [ws, pushLog]);

  useEffect(() => { runScan('Topología', '/api/scan/topology'); }, []);

  const actions = [
    { id: 'topo',   label: '🗺️ Topología', run: () => { setView('topology'); runScan('Topología', '/api/scan/topology'); } },
    { id: 'cam',    label: '📹 Cámaras',    run: runCameras },
    { id: 'evid',   label: '📤 Evidencia',  run: () => setView('evidence') },
    { id: 'bat',    label: '🦇 Murciélago', run: () => setView('murcielago') },
    { id: 'rou',    label: '📡 Routers',    run: () => runScan('Routers',   '/api/scan/routers') },
    { id: 'iot',    label: '🔌 IoT',        run: () => runScan('IoT',       '/api/scan/iot') },
    { id: 'wifi',   label: '📶 WiFi',       run: () => runScan('WiFi',      '/api/scan/wifi') },
    { id: 'honey',  label: '🪤 Honeypot',   run: async () => {
        await fetch('/api/honeypot/start', { method: 'POST' });
        pushLog('🪤 Honeypot iniciado');
    }},
  ];

  const shodanLookup = async (ip: string) => {
    await runScan(`Shodan → ${ip}`, `/api/osint/shodan?ip=${ip}`, 'GET');
  };

  return (
    <div className="min-h-screen bg-[var(--ss-bg)] text-gray-200 font-mono p-4">
      <header className="flex justify-between items-center pb-3 mb-4 border-b border-[var(--ss-border)]">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-gradient-to-br from-cyan-400 to-amber-400 rotate-45" />
          <div>
            <div className="text-lg font-bold tracking-wider">RED-TEAM <span className="text-cyan-400">TAURI</span></div>
            <div className="text-[10px] text-gray-500 tracking-widest">SOBERANÍA OPERATIVA · UNIFIED :8001</div>
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

      <div className="grid grid-cols-4 gap-3 mb-4">
        {[
          { k: 'HOSTS', v: hosts.length, c: 'cyan' },
          { k: 'CRÍTICOS', v: hosts.filter(h => h.risk === 'critical').length, c: 'red' },
          { k: 'CÁMARAS', v: cameras.length, c: 'amber' },
          { k: 'OPERACIONES', v: log.length, c: 'green' },
        ].map(s => (
          <div key={s.k} className="bg-[var(--ss-bg-2)] border border-[var(--ss-border)] p-3 border-l-4"
               style={{ borderLeftColor: `var(--ss-${s.c})` }}>
            <div className="text-2xl font-bold" style={{ color: `var(--ss-${s.c})` }}>{s.v}</div>
            <div className="text-[9px] text-gray-500 tracking-widest">{s.k}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-2 mb-4">
        {actions.map(a => (
          <button key={a.id} onClick={a.run} disabled={loading}
                  className={`px-2 py-2 border text-[10px] uppercase tracking-wider disabled:opacity-50 transition font-mono
                    ${(a.id === 'topo' && view === 'topology') || (a.id === 'cam' && view === 'cameras') || (a.id === 'evid' && view === 'evidence') || (a.id === 'bat' && view === 'murcielago')
                      ? 'bg-cyan-500/20 border-cyan-400 text-cyan-200'
                      : 'border-cyan-500/30 text-cyan-300 hover:bg-cyan-500/10 hover:border-cyan-400'}`}>
            {loading && a.id !== 'evid' && a.id !== 'bat' ? '⏳' : a.label}
          </button>
        ))}
      </div>

      {/* Vista dinámica */}
      {view === 'cameras' ? (
        <div className="mb-4">
          <Suspense fallback={<div className="h-[400px] flex items-center justify-center text-cyan-400 animate-pulse text-sm font-mono">Cargando visor de cámaras...</div>}>
            <CameraGrid cameras={cameras} onRefresh={runCameras} />
          </Suspense>
        </div>
      ) : view === 'evidence' ? (
        <div className="mb-4 max-w-2xl">
          <EvidenceExporter />
        </div>
      ) : view === 'murcielago' ? (
        <div className="mb-4 max-w-2xl">
          <MurcielagoPanel />
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
          <div className="lg:col-span-2">
            <Suspense fallback={<div className="h-[400px] flex items-center justify-center text-cyan-400 animate-pulse text-sm font-mono">Cargando topología...</div>}>
              <TopologyMap />
            </Suspense>
          </div>
          <div><RiskPanel /></div>
        </div>
      )}

      <div className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] p-3">
        <h3 className="text-[10px] uppercase tracking-widest text-amber-400 mb-2">Registro operativo</h3>
        <div className="h-40 overflow-y-auto text-[10px] space-y-0.5">
          {log.map((l, i) => <div key={i} className="text-gray-400">{l}</div>)}
        </div>
      </div>

      <HostDetailDrawer onShodan={shodanLookup} />
    </div>
  );
}
