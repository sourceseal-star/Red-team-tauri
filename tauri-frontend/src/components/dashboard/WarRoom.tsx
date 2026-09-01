import { useState, useEffect, useRef, useCallback, lazy, Suspense } from 'react';
import { useScanStore } from '../../hooks/useScanStore';
import {
  Wifi, Camera, Send, Radio, Activity, Terminal,
  Crosshair, AlertTriangle, Globe, Server, ChevronDown, ChevronRight
} from 'lucide-react';

const TopologyMap = lazy(() => import('./TopologyMap'));

interface UltraLogEntry { time: string; type: 'sent'|'received'|'error'|'info'; message: string }
interface CameraItem { ip: string; port?: number; rtsp_url?: string; brand?: string; rtsp?: boolean }
interface ScanResult {
  id: string;
  type: 'topology' | 'cameras' | 'wifi' | 'ports' | 'osint' | 'radio';
  target: string;
  status: 'running' | 'done' | 'error';
  startedAt: string;
  findings?: any[];
  summary?: string;
  error?: string;
}
interface AlertItem {
  id: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  title: string;
  source: string;
  timestamp: string;
}
interface BackendStatus {
  ok: boolean;
  latency: number;
  services: number;
  cpu: number;
  memory: number;
}
type BottomView = 'alerts' | 'terminal' | 'comms';

const sevColor = (s: string) => ({
  critical: 'text-red-400 border-red-500/40 bg-red-500/10',
  high: 'text-orange-400 border-orange-500/40 bg-orange-500/10',
  medium: 'text-amber-400 border-amber-500/40 bg-amber-500/10',
  low: 'text-cyan-400 border-cyan-500/40 bg-cyan-500/10',
  info: 'text-slate-400 border-slate-500/40 bg-slate-500/10',
}[s] || 'text-slate-400 border-slate-500/40');

const sevIcon = (s: string) => ({
  critical: '🔴', high: '🟠', medium: '🟡', low: '🔵', info: '⚪',
}[s] || '⚪');

function getToken(): string | null {
  return localStorage.getItem('api_token');
}

function authHeaders(): Record<string,string> {
  const t = getToken();
  return t ? { 'Authorization': `Bearer ${t}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' };
}

export default function WarRoom() {
  const [target, setTarget] = useState('192.168.1.0/24');
  const [scanResults, setScanResults] = useState<ScanResult[]>([]);
  const [activeScan, setActiveScan] = useState<string | null>(null);
  const [backend, setBackend] = useState<BackendStatus>({ ok: false, latency: 0, services: 0, cpu: 0, memory: 0 });
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [expandedResult, setExpandedResult] = useState<string | null>(null);

  const hosts = useScanStore(s => s.hosts);
  const loading = useScanStore(s => s.loading);
  const { setHosts, setLoading, setError, pushLog } = useScanStore();
  const [traceroute, setTraceroute] = useState<{ target: string; hops: any[] } | null>(null);
  const [tracing, setTracing] = useState(false);
  const [selectedIp, setSelectedIp] = useState<string | null>(null);

  const [cameras, setCameras] = useState<CameraItem[]>([]);
  const [camLoading, setCamLoading] = useState(false);
  const [motionStatus, setMotionStatus] = useState<Record<string,string>>({});
  const [motionLoading, setMotionLoading] = useState<Record<string,boolean>>({});

  const [freqOffset, setFreqOffset] = useState(0);
  const [ultraMsg, setUltraMsg] = useState('');
  const [ultraLog, setUltraLog] = useState<UltraLogEntry[]>([]);
  const [isListening, setIsListening] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const audioCtxRef = useRef<AudioContext | null>(null);

  const [cmd, setCmd] = useState('');
  const [cmdOutput, setCmdOutput] = useState<string[]>([]);
  const [cmdRunning, setCmdRunning] = useState(false);

  const [bottomView, setBottomView] = useState<BottomView>('alerts');

  // ── Backend health check ──
  const checkBackend = useCallback(async () => {
    const t0 = performance.now();
    try {
      const res = await fetch('/api/health', { headers: authHeaders() });
      const latency = Math.round(performance.now() - t0);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      let cpu = 0, memory = 0, services = 0;
      try {
        const r2 = await fetch('/api/resources', { headers: authHeaders() });
        if (r2.ok) {
          const rd = await r2.json();
          cpu = rd.cpu_usage || rd.cpu_percent || 0;
          memory = rd.memory_used || 0;
        }
      } catch {}
      try {
        const r3 = await fetch('/api/services', { headers: authHeaders() });
        if (r3.ok) {
          const svcs = await r3.json();
          services = Array.isArray(svcs) ? svcs.filter((s:any) => s.status === 'running').length : 0;
        }
      } catch {}
      setBackend({ ok: true, latency, services, cpu, memory });
    } catch {
      setBackend(prev => ({ ...prev, ok: false }));
    }
  }, []);

  useEffect(() => {
    checkBackend();
    const id = setInterval(checkBackend, 5000);
    return () => clearInterval(id);
  }, [checkBackend]);

  // ── Alerts poll ──
  const fetchAlerts = useCallback(async () => {
    try {
      const res = await fetch('/api/alerts', { headers: authHeaders() });
      if (!res.ok) return;
      const data = await res.json();
      const raw = Array.isArray(data) ? data : (data.alerts || []);
      setAlerts(raw.slice(0, 20).map((a:any) => ({
        id: a.id || Math.random().toString(36).slice(2),
        severity: a.severity || 'info',
        title: a.title || a.message || 'Alerta',
        source: a.source || a.module || 'system',
        timestamp: a.timestamp || a.created_at || new Date().toISOString(),
      })));
    } catch {}
  }, []);

  useEffect(() => {
    fetchAlerts();
    const id = setInterval(fetchAlerts, 15000);
    return () => clearInterval(id);
  }, [fetchAlerts]);

  // ── Scan: Topología ──
  const runTopology = async () => {
    const scanId = `topo-${Date.now()}`;
    setActiveScan(scanId);
    setLoading(true); setError(null); pushLog(`⏳ Topología ${target}...`);
    setScanResults(prev => [{ id: scanId, type: 'topology', target, status: 'running', startedAt: new Date().toISOString() }, ...prev]);
    try {
      const res = await fetch('/api/scan/topology', {
        method: 'POST', headers: authHeaders(),
        body: JSON.stringify({ target, cidr: target }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const items = (data.results || data.hosts || []).map((h:any) => ({
        ip: h.ip, mac: h.mac, vendor: h.vendor,
        ports: h.ports || [], risk: h.risk,
        risk_reasons: h.risk_reasons || [],
        first_seen: h.first_seen || new Date().toISOString(),
        type: h.type || 'unknown',
      }));
      setHosts(items);
      pushLog(`✔ Topología: ${items.length} hosts`);
      const findings = items.filter((h:any) => h.risk === 'high' || h.risk === 'critical' || (h.ports && h.ports.length > 0));
      setScanResults(prev => prev.map(s => s.id === scanId ? {
        ...s, status: 'done', summary: `${items.length} hosts, ${findings.length} con hallazgos`,
        findings: items.map((h:any) => ({
          ip: h.ip, type: 'host', severity: h.risk || 'info',
          title: `${h.ip} — ${h.vendor || 'unknown'}`,
          detail: h.ports?.length ? `${h.ports.length} puertos: ${h.ports.map((p:any)=>typeof p === 'string' ? p : p.port).join(', ')}` : 'Sin puertos',
        })),
      } : s));
    } catch (e:any) {
      setError(e.message); pushLog(`✘ Topología: ${e.message}`);
      setScanResults(prev => prev.map(s => s.id === scanId ? { ...s, status: 'error', error: e.message } : s));
    } finally { setLoading(false); setActiveScan(null); }
  };

  // ── Scan: Cámaras ──
  const scanCameras = async () => {
    const scanId = `cam-${Date.now()}`;
    setActiveScan(scanId); setCamLoading(true);
    pushLog(`⏳ Cámaras en ${target}...`);
    setScanResults(prev => [{ id: scanId, type: 'cameras', target, status: 'running', startedAt: new Date().toISOString() }, ...prev]);
    try {
      const res = await fetch('/api/scan/cameras', {
        method: 'POST', headers: authHeaders(),
        body: JSON.stringify({ target, cidr: target }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const cams = (data.results || data.cameras || []).map((c:any) => ({
        ip: c.ip, port: c.port || (c.ports ? Object.keys(c.ports)[0] : 80),
        rtsp_url: c.rtsp ? `rtsp://${c.ip}:554` : undefined,
        brand: c.vendor || c.brand, rtsp: c.rtsp,
      }));
      setCameras(cams);
      pushLog(`✔ Cámaras: ${cams.length} detectadas`);
      setScanResults(prev => prev.map(s => s.id === scanId ? {
        ...s, status: 'done', summary: `${cams.length} cámaras`,
        findings: cams.map((c:any) => ({
          ip: c.ip, type: 'camera', severity: c.rtsp ? 'high' : 'medium',
          title: `Cámara ${c.ip} (${c.brand || 'N/A'})`,
          detail: c.rtsp ? `RTSP activo :554` : `Puerto ${c.port}`,
        })),
      } : s));
    } catch (e:any) {
      pushLog(`✘ Cámaras: ${e.message}`);
      setScanResults(prev => prev.map(s => s.id === scanId ? { ...s, status: 'error', error: e.message } : s));
    } finally { setCamLoading(false); setActiveScan(null); }
  };

  // ── Scan: WiFi ──
  const scanWifi = async () => {
    const scanId = `wifi-${Date.now()}`;
    setActiveScan(scanId); pushLog('⏳ Escaneando WiFi...');
    setScanResults(prev => [{ id: scanId, type: 'wifi', target: 'wlan0', status: 'running', startedAt: new Date().toISOString() }, ...prev]);
    try {
      const res = await fetch('/api/scan/wifi', {
        method: 'POST', headers: authHeaders(),
        body: JSON.stringify({ interface: 'wlan0' }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const networks = data.networks || [];
      pushLog(`✔ WiFi: ${networks.length} redes`);
      setScanResults(prev => prev.map(s => s.id === scanId ? {
        ...s, status: 'done', summary: `${networks.length} redes, ${data.security_analysis?.open_networks || 0} abiertas`,
        findings: networks.map((n:any) => ({
          ip: n.bssid, type: 'wifi', severity: n.security === 'Open' ? 'high' : n.wps ? 'medium' : 'low',
          title: `${n.ssid || '(hidden)'} — ${n.security}`,
          detail: `BSSID: ${n.bssid} | Ch: ${n.channel} | ${n.signal_dbm}dBm${n.wps ? ' | WPS ✓' : ''}`,
        })),
      } : s));
    } catch (e:any) {
      pushLog(`✘ WiFi: ${e.message}`);
      setScanResults(prev => prev.map(s => s.id === scanId ? { ...s, status: 'error', error: e.message } : s));
    } finally { setActiveScan(null); }
  };

  // ── Scan: Puertos ──
  const scanPorts = async () => {
    const scanId = `port-${Date.now()}`;
    setActiveScan(scanId); pushLog(`⏳ Puertos: ${target}...`);
    setScanResults(prev => [{ id: scanId, type: 'ports', target, status: 'running', startedAt: new Date().toISOString() }, ...prev]);
    try {
      let res = await fetch('/api/iot/scan-network', {
        method: 'POST', headers: authHeaders(),
        body: JSON.stringify({ cidr: target }),
      });
      if (!res.ok) {
        res = await fetch('/api/scan/', {
          method: 'POST', headers: authHeaders(),
          body: JSON.stringify({ target, scan_type: 'port' }),
        });
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const hosts = data.results || data.hosts || data.devices || [];
      const totalPorts = hosts.reduce((acc:number, h:any) => acc + (h.ports?.length || h.open_ports?.length || 0), 0);
      pushLog(`✔ Puertos: ${hosts.length} hosts, ${totalPorts} abiertos`);
      setScanResults(prev => prev.map(s => s.id === scanId ? {
        ...s, status: 'done', summary: `${hosts.length} hosts, ${totalPorts} puertos`,
        findings: hosts.map((h:any) => ({
          ip: h.ip, type: 'port', severity: (h.ports?.length || 0) > 5 ? 'high' : 'medium',
          title: `${h.ip} — ${h.ports?.length || 0} puertos`,
          detail: (h.ports || h.open_ports || []).map((p:any) => typeof p === 'string' ? p : `${p.port}/${p.service||'?'}`).join(', ') || 'Sin puertos',
        })),
      } : s));
    } catch (e:any) {
      pushLog(`✘ Puertos: ${e.message}`);
      setScanResults(prev => prev.map(s => s.id === scanId ? { ...s, status: 'error', error: e.message } : s));
    } finally { setActiveScan(null); }
  };

  // ── OSINT Lookup ──
  const osintLookup = async () => {
    const ip = target.split('/')[0];
    const scanId = `osint-${Date.now()}`;
    setActiveScan(scanId); pushLog(`⏳ OSINT: ${ip}...`);
    setScanResults(prev => [{ id: scanId, type: 'osint', target: ip, status: 'running', startedAt: new Date().toISOString() }, ...prev]);
    try {
      const [geoRes, intelRes] = await Promise.all([
        fetch(`/api/geo?ip=${encodeURIComponent(ip)}`, { headers: authHeaders() }).then(r => r.ok ? r.json() : null).catch(() => null),
        fetch(`/api/intel?ip=${encodeURIComponent(ip)}`, { headers: authHeaders() }).then(r => r.ok ? r.json() : null).catch(() => null),
      ]);
      const findings: any[] = [];
      if (geoRes) findings.push({
        ip, type: 'geo', severity: 'info',
        title: `Geo: ${geoRes.country || '?'} — ${geoRes.city || '?'}`,
        detail: `ISP: ${geoRes.isp || '?'} | Coords: ${geoRes.lat || '?'},${geoRes.lon || '?'}`,
      });
      if (intelRes) findings.push({
        ip, type: 'intel', severity: (intelRes.risk_score || 0) > 70 ? 'high' : (intelRes.risk_score || 0) > 40 ? 'medium' : 'low',
        title: `Threat Intel: score ${intelRes.risk_score || '?'}`,
        detail: intelRes.tags?.join(', ') || intelRes.description || 'Sin datos',
      });
      if (findings.length === 0) findings.push({ ip, type: 'osint', severity: 'info', title: 'Sin datos OSINT', detail: 'No se encontraron resultados' });
      pushLog(`✔ OSINT: ${findings.length} resultados`);
      setScanResults(prev => prev.map(s => s.id === scanId ? { ...s, status: 'done', summary: `${findings.length} resultados`, findings } : s));
    } catch (e:any) {
      pushLog(`✘ OSINT: ${e.message}`);
      setScanResults(prev => prev.map(s => s.id === scanId ? { ...s, status: 'error', error: e.message } : s));
    } finally { setActiveScan(null); }
  };

  // ── Traceroute ──
  const runTraceroute = async (ip: string) => {
    setTracing(true); setTraceroute(null);
    try {
      const res = await fetch(`/api/topology/traceroute?target_ip=${ip}`, { headers: authHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setTraceroute({ target: ip, hops: data.hops || [] });
      pushLog(`🛤️ Traceroute a ${ip}: ${data.total_hops || 0} saltos`);
    } catch (e:any) { pushLog(`✘ Traceroute: ${e.message}`); }
    finally { setTracing(false); }
  };

  // ── Motion detect ──
  const detectMotion = async (cam: CameraItem) => {
    const rtspUrl = cam.rtsp_url || `rtsp://${cam.ip}:554`;
    setMotionStatus(prev => ({ ...prev, [cam.ip]: 'Detectando...' }));
    setMotionLoading(prev => ({ ...prev, [cam.ip]: true }));
    try {
      const res = await fetch(`/api/vision/motion-detect?rtsp_url=${encodeURIComponent(rtspUrl)}&threshold=0.02&duration=6`, { method: 'POST', headers: authHeaders() });
      const data = await res.json();
      setMotionStatus(prev => ({ ...prev, [cam.ip]: data.motion_detected ? `🚨 ${data.captures?.length || 0} capturas` : '✅ Sin movimiento' }));
    } catch { setMotionStatus(prev => ({ ...prev, [cam.ip]: '❌ Error' })); }
    finally { setMotionLoading(prev => ({ ...prev, [cam.ip]: false })); }
  };

  // ── Ultrasonic send (existente, sin cambios) ──
  const sendUltrasonicBrowser = async (message: string, offset: number) => {
    if (!message.trim()) return;
    setIsSending(true);
    if (!audioCtxRef.current) audioCtxRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
    const ctx = audioCtxRef.current;
    const baseFreq = 18000 + offset;
    const freqMap: Record<string, [number, number]> = {
      '0': [baseFreq, baseFreq + 400], '1': [baseFreq + 100, baseFreq + 500],
      '2': [baseFreq + 200, baseFreq + 600], '3': [baseFreq + 300, baseFreq + 700],
      '4': [baseFreq + 400, baseFreq + 800], '5': [baseFreq + 500, baseFreq + 900],
      '6': [baseFreq + 600, baseFreq + 1000], '7': [baseFreq + 700, baseFreq + 1100],
      '8': [baseFreq + 800, baseFreq + 1200], '9': [baseFreq + 900, baseFreq + 1300],
      'A': [baseFreq + 1000, baseFreq + 1400], 'B': [baseFreq + 1100, baseFreq + 1500],
      'C': [baseFreq + 1200, baseFreq + 1600], 'D': [baseFreq + 1300, baseFreq + 1700],
      'E': [baseFreq + 1400, baseFreq + 1800], 'F': [baseFreq + 1500, baseFreq + 1900],
      '*': [baseFreq + 100, baseFreq + 1900], '#': [baseFreq, baseFreq + 1900]
    };
    const duration = 0.12, sampleRate = ctx.sampleRate;
    const symbolSamples = Math.floor(sampleRate * duration);
    const gapSamples = Math.floor(sampleRate * 0.025);
    const msgBytes = new TextEncoder().encode(message);
    const checksum = msgBytes.reduce((a, b) => a + b, 0) % 256;
    const hexStr = Array.from(msgBytes).map(b => b.toString(16).padStart(2, '0').toUpperCase()).join('');
    const symbols = (hexStr + '*' + checksum.toString(16).padStart(2, '0').toUpperCase()).split('');
    const syncSamples = Math.floor(sampleRate * 0.3);
    const totalSamples = syncSamples + Math.floor(sampleRate * 0.05) + symbols.length * (symbolSamples + gapSamples) + Math.floor(sampleRate * 0.2);
    const buffer = ctx.createBuffer(1, totalSamples, sampleRate);
    const data = buffer.getChannelData(0);
    let idx = 0;
    for (let i = 0; i < syncSamples; i++) data[idx++] = 0.5 * Math.sin(2 * Math.PI * (baseFreq + 1500) * (i / sampleRate));
    for (let i = 0; i < Math.floor(sampleRate * 0.05); i++) data[idx++] = 0;
    for (const sym of symbols) {
      if (freqMap[sym]) {
        const [f1, f2] = freqMap[sym];
        for (let i = 0; i < symbolSamples && idx < data.length; i++) {
          const t = i / sampleRate;
          data[idx++] = 0.5 * Math.sin(2 * Math.PI * f1 * t) + 0.5 * Math.sin(2 * Math.PI * f2 * t);
        }
      } else { idx += symbolSamples; }
      for (let i = 0; i < gapSamples && idx < data.length; i++) data[idx++] = 0;
    }
    const syncFreq = baseFreq + 1500;
    for (let i = 0; i < Math.floor(sampleRate * 0.2) && idx < data.length; i++)
      data[idx++] = 0.5 * Math.sin(2 * Math.PI * syncFreq * (i / sampleRate));
    const source = ctx.createBufferSource();
    source.buffer = buffer; source.connect(ctx.destination);
    source.start(); source.stop(ctx.currentTime + totalSamples / sampleRate);
    try { await fetch('/api/comms/ultrasonic-send', { method: 'POST', headers: authHeaders(), body: JSON.stringify({ message, freq_offset: offset }) }); } catch {}
    setUltraLog(prev => [{ time: new Date().toLocaleTimeString(), type: 'sent', message: `"${message}" @ ${baseFreq}Hz (${symbols.length} símbolos)` }, ...prev].slice(0, 30));
    setIsSending(false);
  };

  const listenUltrasonic = async () => {
    setIsListening(true);
    setUltraLog(prev => [{ time: new Date().toLocaleTimeString(), type: 'info', message: 'Escuchando 6s...' }, ...prev]);
    try {
      const res = await fetch('/api/comms/ultrasonic-receive?duration=6', { method: 'POST', headers: authHeaders() });
      const data = await res.json();
      setUltraLog(prev => [{
        time: new Date().toLocaleTimeString(),
        type: data.message && !data.message.startsWith('❌') ? 'received' : 'info',
        message: data.message || data.error || 'Sin señal',
      }, ...prev].slice(0, 30));
    } catch (err:any) {
      setUltraLog(prev => [{ time: new Date().toLocaleTimeString(), type: 'error', message: err.message }, ...prev]);
    }
    setIsListening(false);
  };

  // ── Terminal ──
  const runCommand = async () => {
    if (!cmd.trim()) return;
    setCmdRunning(true);
    setCmdOutput(prev => [`$ ${cmd}`, ...prev]);
    try {
      const res = await fetch('/api/terminal', {
        method: 'POST', headers: authHeaders(),
        body: JSON.stringify({ command: cmd }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const out = (data.stdout || '') + (data.stderr ? `\n[stderr] ${data.stderr}` : '');
      setCmdOutput(prev => [out || '(sin output)', ...prev].slice(0, 50));
    } catch (e:any) {
      setCmdOutput(prev => [`[error] ${e.message}`, ...prev].slice(0, 50));
    } finally { setCmdRunning(false); setCmd(''); }
  };

  // Auto-scan topology on mount
  useEffect(() => { runTopology(); }, []);

  const logColor = (type: string) => ({ sent: 'text-cyan-300', received: 'text-green-300', error: 'text-red-300' }[type] || 'text-gray-400');

  return (
    <div className="h-full w-full flex flex-col gap-2 font-mono text-sm">
      {/* ════════ BARRA SUPERIOR: Estado + Quick Actions ════════ */}
      <div className="flex items-center gap-2 px-3 py-2 bg-[var(--ss-bg-2)] border border-[var(--ss-border)] rounded-lg">
        <div className="flex items-center gap-2 pr-3 border-r border-[var(--ss-border)]">
          <span className={`w-2.5 h-2.5 rounded-full ${backend.ok ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
          <span className="text-xs text-gray-400">
            {backend.ok ? `Backend OK · ${backend.latency}ms` : 'Backend OFF'}
          </span>
          {backend.ok && (
            <span className="text-[10px] text-gray-500 hidden sm:inline">
              · {backend.services} svc · {backend.cpu.toFixed(0)}% CPU · {(backend.memory/1048576).toFixed(0)}MB
            </span>
          )}
        </div>

        <div className="flex items-center gap-1">
          <Crosshair size={14} className="text-cyan-400" />
          <input
            type="text"
            value={target}
            onChange={e => setTarget(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') runTopology(); }}
            placeholder="192.168.1.0/24"
            className="w-36 bg-[var(--ss-bg-3)] border border-[var(--ss-border)] text-cyan-300 px-2 py-1 rounded text-xs focus:border-cyan-500 focus:outline-none"
          />
        </div>

        <div className="flex items-center gap-1 flex-wrap">
          <button onClick={runTopology} disabled={!!activeScan} className="flex items-center gap-1 px-2 py-1 text-[10px] border border-cyan-500/30 text-cyan-300 rounded hover:bg-cyan-500/10 disabled:opacity-40 transition">
            <Wifi size={11} /> Topología
          </button>
          <button onClick={scanCameras} disabled={!!activeScan} className="flex items-center gap-1 px-2 py-1 text-[10px] border border-amber-500/30 text-amber-300 rounded hover:bg-amber-500/10 disabled:opacity-40 transition">
            <Camera size={11} /> Cámaras
          </button>
          <button onClick={scanWifi} disabled={!!activeScan} className="flex items-center gap-1 px-2 py-1 text-[10px] border border-green-500/30 text-green-300 rounded hover:bg-green-500/10 disabled:opacity-40 transition">
            <Wifi size={11} /> WiFi
          </button>
          <button onClick={scanPorts} disabled={!!activeScan} className="flex items-center gap-1 px-2 py-1 text-[10px] border border-orange-500/30 text-orange-300 rounded hover:bg-orange-500/10 disabled:opacity-40 transition">
            <Server size={11} /> Puertos
          </button>
          <button onClick={osintLookup} disabled={!!activeScan} className="flex items-center gap-1 px-2 py-1 text-[10px] border border-indigo-500/30 text-indigo-300 rounded hover:bg-indigo-500/10 disabled:opacity-40 transition">
            <Globe size={11} /> OSINT
          </button>
        </div>

        {activeScan && (
          <span className="text-[10px] text-cyan-400 animate-pulse ml-auto">⟳ escaneando...</span>
        )}
      </div>

      {/* ════════ FILA SUPERIOR: Topología + Cámaras ════════ */}
      <div className="grid grid-cols-1 gap-2 lg:flex-1 lg:grid-cols-2 lg:min-h-0">
        {/* Topología */}
        <div className="h-[300px] lg:h-auto bg-[var(--ss-bg-2)] border border-[var(--ss-border)] rounded-lg overflow-hidden flex flex-col">
          <div className="p-2 bg-[var(--ss-bg-3)] border-b border-[var(--ss-border)] flex items-center justify-between">
            <span className="text-xs text-cyan-400 flex items-center gap-2">
              <Wifi size={14} /> TOPOLOGÍA
              {loading && <span className="text-[9px] text-gray-500 animate-pulse">escaneando...</span>}
            </span>
            <button onClick={runTopology} disabled={loading} className="px-2 py-1 text-[10px] border border-cyan-500/30 text-cyan-300 rounded hover:bg-cyan-500/10 disabled:opacity-50 transition">↻ Escanear</button>
          </div>
          <div className="flex-1 min-h-0 relative">
            <Suspense fallback={<div className="h-full flex items-center justify-center text-cyan-400 animate-pulse text-sm">Cargando topología...</div>}>
              <TopologyMap />
            </Suspense>
            {traceroute && (
              <div className="absolute bottom-2 left-2 right-2 bg-[var(--ss-bg-3)] border border-cyan-500/30 rounded p-2 max-h-40 overflow-y-auto">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] text-cyan-400">🛤️ Traceroute a {traceroute.target}</span>
                  <button onClick={() => setTraceroute(null)} className="text-[10px] text-gray-500 hover:text-red-400">✕</button>
                </div>
                {traceroute.hops.length === 0 ? (
                  <div className="text-[9px] text-gray-500">Sin saltos</div>
                ) : traceroute.hops.map((hop, i) => (
                  <div key={i} className="text-[9px] text-gray-400 flex gap-2">
                    <span className="text-cyan-500 w-4">{hop.hop}</span>
                    <span className="flex-1">{hop.ip || '*'}</span>
                    <span className="text-amber-400">{hop.rtt_avg_ms ? `${hop.rtt_avg_ms}ms` : '---'}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
          {hosts.length > 0 && (
            <div className="border-t border-[var(--ss-border)] p-1 flex gap-1 overflow-x-auto">
              {hosts.slice(0, 10).map(h => (
                <button key={h.ip} onClick={() => { setSelectedIp(h.ip); runTraceroute(h.ip); }} disabled={tracing}
                  className={`px-2 py-1 text-[9px] border rounded whitespace-nowrap transition disabled:opacity-50
                    ${selectedIp === h.ip ? 'bg-cyan-500/20 border-cyan-400 text-cyan-200' : 'border-[var(--ss-border)] text-gray-400 hover:border-cyan-500/50 hover:text-cyan-300'}`}>
                  {tracing && selectedIp === h.ip ? '⏳' : '🛤️'} {h.ip}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Cámaras */}
        <div className="h-[300px] lg:h-auto bg-[var(--ss-bg-2)] border border-[var(--ss-border)] rounded-lg overflow-hidden flex flex-col">
          <div className="p-2 bg-[var(--ss-bg-3)] border-b border-[var(--ss-border)] flex items-center justify-between">
            <span className="text-xs text-amber-400 flex items-center gap-2">
              <Camera size={14} /> CÁMARAS
              {camLoading && <span className="text-[9px] text-gray-500 animate-pulse">escaneando...</span>}
            </span>
            <button onClick={scanCameras} disabled={camLoading} className="px-2 py-1 text-[10px] border border-amber-500/30 text-amber-300 rounded hover:bg-amber-500/10 disabled:opacity-50 transition">↻ Escanear</button>
          </div>
          <div className="flex-1 overflow-y-auto p-2 grid grid-cols-2 gap-2 min-h-0">
            {cameras.length === 0 && !camLoading && (
              <div className="col-span-2 flex items-center justify-center text-gray-500 text-xs h-full">
                Presiona "Escanear" para detectar cámaras IP
              </div>
            )}
            {cameras.map(cam => (
              <div key={cam.ip} className="bg-[var(--ss-bg-3)] rounded border border-[var(--ss-border)] p-2">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-[10px] text-gray-300">{cam.ip}</span>
                  <span className="text-[8px] text-gray-500">{cam.brand || 'N/A'}</span>
                </div>
                <div className="aspect-video bg-black/50 rounded flex items-center justify-center overflow-hidden">
                  <img src={`/api/iot/snapshot?ip=${cam.ip}&port=${cam.port||80}&path=/snapshot.cgi&_t=${Date.now()}`} className="w-full h-full object-contain" onError={e => (e.target as HTMLImageElement).style.display = 'none'} />
                </div>
                <div className="flex gap-1 mt-1">
                  <button onClick={() => window.open(`/api/iot/snapshot?ip=${cam.ip}&port=${cam.port||80}&path=/snapshot.cgi`, '_blank')} className="px-2 py-0.5 text-[9px] bg-cyan-600/30 border border-cyan-500/30 text-cyan-300 rounded hover:bg-cyan-600/50 transition">📷 Snap</button>
                  {cam.rtsp && (
                    <button onClick={() => detectMotion(cam)} disabled={motionLoading[cam.ip]} className="px-2 py-0.5 text-[9px] bg-red-600/30 border border-red-500/30 text-red-300 rounded hover:bg-red-600/50 disabled:opacity-50 transition">🔍 Mov</button>
                  )}
                </div>
                {motionStatus[cam.ip] && <div className="text-[9px] text-gray-400 mt-1">{motionStatus[cam.ip]}</div>}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ════════ FILA MEDIA: RESULTADOS DE ESCANEO ════════ */}
      <div className="bg-[var(--ss-bg-2)] border border-[var(--ss-border)] rounded-lg max-h-64 overflow-y-auto">
        <div className="p-2 bg-[var(--ss-bg-3)] border-b border-[var(--ss-border)] flex items-center justify-between sticky top-0 z-10">
          <span className="text-xs text-gray-400 flex items-center gap-2">
            <Activity size={14} /> RESULTADOS DE ESCANEO
            <span className="text-[10px] text-gray-600">{scanResults.length} scans</span>
          </span>
          {scanResults.length > 0 && (
            <button onClick={() => setScanResults([])} className="text-[10px] text-gray-500 hover:text-red-400">Limpiar</button>
          )}
        </div>
        {scanResults.length === 0 ? (
          <div className="p-4 text-center text-gray-600 text-xs">No hay scans. Usa los botones de arriba para empezar.</div>
        ) : (
          <div className="divide-y divide-[var(--ss-border)]">
            {scanResults.map(s => (
              <div key={s.id} className="p-2">
                <div className="flex items-center gap-2 cursor-pointer" onClick={() => setExpandedResult(expandedResult === s.id ? null : s.id)}>
                  <span className="text-xs">{expandedResult === s.id ? <ChevronDown size={12} /> : <ChevronRight size={12} />}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${s.status === 'done' ? 'bg-green-500/20 text-green-400' : s.status === 'error' ? 'bg-red-500/20 text-red-400' : 'bg-cyan-500/20 text-cyan-400 animate-pulse'}`}>
                    {s.status === 'running' ? '⟳' : s.status === 'done' ? '✓' : '✘'} {s.type.toUpperCase()}
                  </span>
                  <span className="text-xs text-gray-300 flex-1">{s.target}</span>
                  <span className="text-[10px] text-gray-500">{s.summary || s.error || '...'}</span>
                  <span className="text-[9px] text-gray-600">{new Date(s.startedAt).toLocaleTimeString()}</span>
                </div>
                {expandedResult === s.id && s.findings && (
                  <div className="mt-1 ml-6 space-y-1 max-h-48 overflow-y-auto">
                    {s.findings.map((f, i) => (
                      <div key={i} className={`p-1.5 rounded border text-xs ${sevColor(f.severity)}`}>
                        <span className="mr-1">{sevIcon(f.severity)}</span>
                        <span className="font-bold">{f.title}</span>
                        <div className="text-[10px] text-gray-400 mt-0.5">{f.detail}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ════════ PANEL INFERIOR: Tabs ════════ */}
      <div className="bg-[var(--ss-bg-2)] border border-[var(--ss-border)] rounded-lg flex flex-col h-48">
        <div className="flex items-center border-b border-[var(--ss-border)] bg-[var(--ss-bg-3)]">
          {[
            { id: 'alerts', label: 'Alertas', icon: AlertTriangle, color: 'text-yellow-400', badge: alerts.length },
            { id: 'terminal', label: 'Terminal', icon: Terminal, color: 'text-slate-400' },
            { id: 'comms', label: 'Ultrasonido', icon: Radio, color: 'text-pink-400' },
          ].map(tab => (
            <button key={tab.id} onClick={() => setBottomView(tab.id as BottomView)}
              className={`flex items-center gap-1.5 px-3 py-2 text-xs border-b-2 transition
                ${bottomView === tab.id ? `border-cyan-500 ${tab.color}` : 'border-transparent text-gray-500 hover:text-gray-300'}`}>
              <tab.icon size={12} /> {tab.label}
              {tab.badge ? <span className="ml-1 px-1.5 py-0.5 bg-red-500/20 text-red-400 text-[9px] rounded-full">{tab.badge}</span> : null}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto p-2">
          {bottomView === 'alerts' && (
            <div className="space-y-1">
              {alerts.length === 0 ? (
                <div className="text-center text-gray-600 text-xs py-4">Sin alertas. Sistema tranquilo.</div>
              ) : alerts.map(a => (
                <div key={a.id} className={`p-1.5 rounded border text-xs ${sevColor(a.severity)} flex items-center gap-2`}>
                  <span>{sevIcon(a.severity)}</span>
                  <span className="font-bold flex-1">{a.title}</span>
                  <span className="text-[10px] text-gray-500">{a.source}</span>
                  <span className="text-[9px] text-gray-600">{new Date(a.timestamp).toLocaleTimeString()}</span>
                </div>
              ))}
            </div>
          )}

          {bottomView === 'terminal' && (
            <div className="flex flex-col h-full">
              <div className="flex-1 overflow-y-auto mb-2 space-y-0.5">
                {cmdOutput.length === 0 ? (
                  <div className="text-gray-600 text-xs">Terminal lista. Escribe un comando y presiona Enter.</div>
                ) : cmdOutput.map((line, i) => (
                  <div key={i} className={`text-xs ${line.startsWith('$') ? 'text-cyan-400' : line.startsWith('[error]') ? 'text-red-400' : 'text-gray-300'}`}>
                    <pre className="whitespace-pre-wrap font-mono">{line}</pre>
                  </div>
                ))}
              </div>
              <div className="flex items-center gap-2">
                <span className="text-cyan-400 text-xs">$</span>
                <input type="text" value={cmd} onChange={e => setCmd(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') runCommand(); }}
                  disabled={cmdRunning}
                  placeholder="whoami, ifconfig, nmap -sV 192.168.1.1..."
                  className="flex-1 bg-[var(--ss-bg-3)] border border-[var(--ss-border)] text-gray-300 px-2 py-1 rounded text-xs focus:border-cyan-500 focus:outline-none disabled:opacity-50" />
                <button onClick={runCommand} disabled={cmdRunning || !cmd.trim()} className="px-3 py-1 text-xs bg-cyan-600/30 border border-cyan-500/30 text-cyan-300 rounded hover:bg-cyan-600/50 disabled:opacity-50 transition">Ejecutar</button>
              </div>
            </div>
          )}

          {bottomView === 'comms' && (
            <div className="flex flex-col gap-2 h-full">
              <div className="flex items-center gap-2">
                <input type="text" value={ultraMsg} onChange={e => setUltraMsg(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') sendUltrasonicBrowser(ultraMsg, freqOffset); }}
                  placeholder="Mensaje a transmitir..."
                  className="flex-1 bg-[var(--ss-bg-3)] border border-[var(--ss-border)] text-pink-300 px-2 py-1 rounded text-xs focus:border-pink-500 focus:outline-none" />
                <button onClick={() => sendUltrasonicBrowser(ultraMsg, freqOffset)} disabled={isSending || !ultraMsg.trim()} className="px-3 py-1 text-xs bg-pink-600/30 border border-pink-500/30 text-pink-300 rounded hover:bg-pink-600/50 disabled:opacity-50 transition">
                  <Send size={11} className="inline" /> Enviar
                </button>
                <button onClick={listenUltrasonic} disabled={isListening} className="px-3 py-1 text-xs bg-cyan-600/30 border border-cyan-500/30 text-cyan-300 rounded hover:bg-cyan-600/50 disabled:opacity-50 transition">
                  <Radio size={11} className="inline" /> {isListening ? 'Escuchando...' : 'Escuchar'}
                </button>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-gray-500">Offset:</span>
                <input type="range" min="0" max="2000" value={freqOffset} onChange={e => setFreqOffset(Number(e.target.value))} className="flex-1" />
                <span className="text-[10px] text-gray-400">{18000 + freqOffset}Hz</span>
              </div>
              <div className="flex-1 overflow-y-auto space-y-0.5">
                {ultraLog.map((entry, i) => (
                  <div key={i} className={`text-xs ${logColor(entry.type)}`}>
                    <span className="text-gray-600 text-[10px]">[{entry.time}]</span> {entry.message}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
