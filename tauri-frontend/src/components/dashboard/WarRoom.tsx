import { useState, useEffect, useRef, lazy, Suspense } from 'react';
import { useScanStore } from '../../hooks/useScanStore';
import { Wifi, Camera, Send, Mic, Radio, Sliders, Activity } from 'lucide-react';
import IntelPanel from '../IntelPanel';
import ExploitMatrix from '../ExploitMatrix';
import TrafficMonitor from '../TrafficMonitor';
import OSINTPanel from '../OSINTPanel';
import WiFiPanel from '../WiFiPanel';
import BlackMirrorPanel from '../BlackMirrorPanel';

const TopologyMap = lazy(() => import('./TopologyMap'));

interface UltraLogEntry {
  time: string;
  type: 'sent' | 'received' | 'error' | 'info';
  message: string;
}

interface CameraItem {
  ip: string;
  port?: number;
  rtsp_url?: string;
  brand?: string;
  rtsp?: boolean;
}

type BottomView = 'comms' | 'intel' | 'recon' | 'mirror';

export default function WarRoom() {
  // ---- Topología ----
  const hosts = useScanStore(s => s.hosts);
  const loading = useScanStore(s => s.loading);
  const { setHosts, setLoading, setError, pushLog } = useScanStore();
  const [traceroute, setTraceroute] = useState<{ target: string; hops: any[] } | null>(null);
  const [tracing, setTracing] = useState(false);
  const [selectedIp, setSelectedIp] = useState<string | null>(null);

  // ---- Cámaras ----
  const [cameras, setCameras] = useState<CameraItem[]>([]);
  const [camLoading, setCamLoading] = useState(false);
  const [motionStatus, setMotionStatus] = useState<Record<string, string>>({});
  const [motionLoading, setMotionLoading] = useState<Record<string, boolean>>({});

  // ---- Comms Ultrasónicas ----
  const [freqOffset, setFreqOffset] = useState(0);
  const [ultraMsg, setUltraMsg] = useState('');
  const [ultraLog, setUltraLog] = useState<UltraLogEntry[]>([]);
  const [isListening, setIsListening] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const audioCtxRef = useRef<AudioContext | null>(null);

  // ---- Vista del panel inferior ----
  const [bottomView, setBottomView] = useState<BottomView>('comms');

  // ---- Topología: escaneo inicial ----
  const runTopology = async () => {
    setLoading(true); setError(null); pushLog('⏳ Escaneando topología...');
    try {
      const res = await fetch('/api/scan/topology', { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const items = (data.results || []).map((h: any) => ({
        ip: h.ip, mac: h.mac, vendor: h.vendor,
        ports: h.ports || [], risk: h.risk,
        risk_reasons: h.risk_reasons || [],
        first_seen: h.first_seen || new Date().toISOString(),
        type: h.type || 'unknown',
      }));
      setHosts(items);
      pushLog(`✔ Topología: ${items.length} hosts`);
    } catch (e: any) {
      setError(e.message);
      pushLog(`✘ Topología: ${e.message}`);
    } finally { setLoading(false); }
  };

  useEffect(() => { runTopology(); }, []);

  // ---- Traceroute ----
  const runTraceroute = async (ip: string) => {
    setTracing(true);
    setTraceroute(null);
    try {
      const res = await fetch(`/api/topology/traceroute?target_ip=${ip}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setTraceroute({ target: ip, hops: data.hops || [] });
      pushLog(`🛤️ Traceroute a ${ip}: ${data.total_hops || 0} saltos`);
    } catch (e: any) {
      pushLog(`✘ Traceroute: ${e.message}`);
    } finally { setTracing(false); }
  };

  // ---- Escaneo de cámaras ----
  const scanCameras = async () => {
    setCamLoading(true);
    pushLog('⏳ Escaneando cámaras...');
    try {
      const res = await fetch('/api/scan/cameras', { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const cams = (data.results || []).map((c: any) => ({
        ip: c.ip, port: c.port || (c.ports ? Object.keys(c.ports)[0] : 80),
        rtsp_url: c.rtsp ? `rtsp://${c.ip}:554` : undefined,
        brand: c.vendor || c.brand,
        rtsp: c.rtsp,
      }));
      setCameras(cams);
      pushLog(`✔ Cámaras: ${cams.length} detectadas`);
    } catch (e: any) {
      pushLog(`✘ Cámaras: ${e.message}`);
    } finally { setCamLoading(false); }
  };

  // ---- Detección de movimiento ----
  const detectMotion = async (cam: CameraItem) => {
    const rtspUrl = cam.rtsp_url || `rtsp://${cam.ip}:554`;
    setMotionStatus(prev => ({ ...prev, [cam.ip]: 'Detectando...' }));
    setMotionLoading(prev => ({ ...prev, [cam.ip]: true }));
    try {
      const res = await fetch(
        `/api/vision/motion-detect?rtsp_url=${encodeURIComponent(rtspUrl)}&threshold=0.02&duration=6`,
        { method: 'POST' }
      );
      const data = await res.json();
      if (data.motion_detected) {
        setMotionStatus(prev => ({ ...prev, [cam.ip]: `🚨 ${data.captures?.length || 0} capturas con hash` }));
      } else {
        setMotionStatus(prev => ({ ...prev, [cam.ip]: '✅ Sin movimiento' }));
      }
    } catch {
      setMotionStatus(prev => ({ ...prev, [cam.ip]: '❌ Error' }));
    } finally {
      setMotionLoading(prev => ({ ...prev, [cam.ip]: false }));
    }
  };

  // ---- Envío ultrasónico desde el navegador (Web Audio API) ----
  const sendUltrasonicBrowser = async (message: string, offset: number) => {
    if (!message.trim()) return;
    setIsSending(true);

    if (!audioCtxRef.current) {
      audioCtxRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
    }
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

    const duration = 0.12;
    const sampleRate = ctx.sampleRate;
    const symbolSamples = Math.floor(sampleRate * duration);
    const gapSamples = Math.floor(sampleRate * 0.025);

    const msgBytes = new TextEncoder().encode(message);
    const checksum = msgBytes.reduce((a, b) => a + b, 0) % 256;
    const hexStr = Array.from(msgBytes).map(b => b.toString(16).padStart(2, '0').toUpperCase()).join('');
    const symbols = (hexStr + '*' + checksum.toString(16).padStart(2, '0').toUpperCase()).split('');

    const syncSamples = Math.floor(sampleRate * 0.3);
    const totalSamples = syncSamples + Math.floor(sampleRate * 0.05) +
      symbols.length * (symbolSamples + gapSamples) + Math.floor(sampleRate * 0.2);

    const buffer = ctx.createBuffer(1, totalSamples, sampleRate);
    const data = buffer.getChannelData(0);

    let idx = 0;
    for (let i = 0; i < syncSamples; i++) {
      data[idx++] = 0.5 * Math.sin(2 * Math.PI * (baseFreq + 1500) * (i / sampleRate));
    }
    for (let i = 0; i < Math.floor(sampleRate * 0.05); i++) data[idx++] = 0;

    for (const sym of symbols) {
      if (freqMap[sym]) {
        const [f1, f2] = freqMap[sym];
        for (let i = 0; i < symbolSamples; i++) {
          if (idx >= data.length) break;
          const t = i / sampleRate;
          data[idx++] = 0.5 * Math.sin(2 * Math.PI * f1 * t) + 0.5 * Math.sin(2 * Math.PI * f2 * t);
        }
      } else {
        idx += symbolSamples;
      }
      for (let i = 0; i < gapSamples; i++) {
        if (idx >= data.length) break;
        data[idx++] = 0;
      }
    }

    const syncFreq = baseFreq + 1500;
    for (let i = 0; i < Math.floor(sampleRate * 0.2) && idx < data.length; i++) {
      data[idx++] = 0.5 * Math.sin(2 * Math.PI * syncFreq * (i / sampleRate));
    }

    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);
    source.start();
    source.stop(ctx.currentTime + totalSamples / sampleRate);

    // Backend para registro
    try {
      await fetch('/api/comms/ultrasonic-send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, freq_offset: offset }),
      });
    } catch {}

    setUltraLog(prev => [{
      time: new Date().toLocaleTimeString(),
      type: 'sent' as const,
      message: `"${message}" @ ${baseFreq} Hz (${symbols.length} símbolos)`
    }, ...prev].slice(0, 30));
    setIsSending(false);
  };

  // ---- Escuchar ultrasonidos ----
  const listenUltrasonic = async () => {
    setIsListening(true);
    setUltraLog(prev => [{
      time: new Date().toLocaleTimeString(),
      type: 'info' as const,
      message: 'Escuchando 6s...'
    }, ...prev]);

    try {
      const res = await fetch('/api/comms/ultrasonic-receive?duration=6', { method: 'POST' });
      const data = await res.json();
      if (data.message && !data.message.startsWith('❌')) {
        setUltraLog(prev => [{
          time: new Date().toLocaleTimeString(),
          type: 'received' as const,
          message: data.message
        }, ...prev].slice(0, 30));
      } else {
        setUltraLog(prev => [{
          time: new Date().toLocaleTimeString(),
          type: 'info' as const,
          message: data.message || data.error || 'Sin señal detectada'
        }, ...prev].slice(0, 30));
      }
    } catch (err: any) {
      setUltraLog(prev => [{
        time: new Date().toLocaleTimeString(),
        type: 'error' as const,
        message: err.message
      }, ...prev].slice(0, 30));
    }
    setIsListening(false);
  };

  const logColor = (type: string) => {
    switch (type) {
      case 'sent': return 'text-cyan-300';
      case 'received': return 'text-green-300';
      case 'error': return 'text-red-300';
      default: return 'text-gray-400';
    }
  };

  return (
    <div className="h-full w-full flex flex-col gap-3 font-mono">
      {/* FILA SUPERIOR: Topología + Cámaras */}
      <div className="flex-1 grid grid-cols-2 gap-3 min-h-0">
        {/* ── Topología ── */}
        <div className="bg-[var(--ss-bg-2)] border border-[var(--ss-border)] rounded-lg overflow-hidden flex flex-col">
          <div className="p-2 bg-[var(--ss-bg-3)] border-b border-[var(--ss-border)] flex items-center justify-between">
            <span className="text-xs text-cyan-400 flex items-center gap-2">
              <Wifi size={14} /> TOPOLOGÍA
              {loading && <span className="text-[9px] text-gray-500 animate-pulse">escaneando...</span>}
            </span>
            <button
              onClick={runTopology}
              disabled={loading}
              className="px-2 py-1 text-[10px] border border-cyan-500/30 text-cyan-300 rounded hover:bg-cyan-500/10 disabled:opacity-50 transition"
            >
              ↻ Escanear
            </button>
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
                  <div className="text-[9px] text-gray-500">Sin saltos detectados</div>
                ) : (
                  traceroute.hops.map((hop, i) => (
                    <div key={i} className="text-[9px] text-gray-400 flex gap-2">
                      <span className="text-cyan-500 w-4">{hop.hop}</span>
                      <span className="flex-1">{hop.ip || '*'}</span>
                      <span className="text-amber-400">{hop.rtt_avg_ms ? `${hop.rtt_avg_ms}ms` : '---'}</span>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
          {hosts.length > 0 && (
            <div className="border-t border-[var(--ss-border)] p-1 flex gap-1 overflow-x-auto">
              {hosts.slice(0, 10).map(h => (
                <button
                  key={h.ip}
                  onClick={() => { setSelectedIp(h.ip); runTraceroute(h.ip); }}
                  disabled={tracing}
                  className={`px-2 py-1 text-[9px] border rounded whitespace-nowrap transition disabled:opacity-50
                    ${selectedIp === h.ip
                      ? 'bg-cyan-500/20 border-cyan-400 text-cyan-200'
                      : 'border-[var(--ss-border)] text-gray-400 hover:border-cyan-500/50 hover:text-cyan-300'}`}
                >
                  {tracing && selectedIp === h.ip ? '⏳' : '🛤️'} {h.ip}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* ── Cámaras ── */}
        <div className="bg-[var(--ss-bg-2)] border border-[var(--ss-border)] rounded-lg overflow-hidden flex flex-col">
          <div className="p-2 bg-[var(--ss-bg-3)] border-b border-[var(--ss-border)] flex items-center justify-between">
            <span className="text-xs text-amber-400 flex items-center gap-2">
              <Camera size={14} /> CÁMARAS
              {camLoading && <span className="text-[9px] text-gray-500 animate-pulse">escaneando...</span>}
            </span>
            <button
              onClick={scanCameras}
              disabled={camLoading}
              className="px-2 py-1 text-[10px] border border-amber-500/30 text-amber-300 rounded hover:bg-amber-500/10 disabled:opacity-50 transition"
            >
              ↻ Escanear
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-2 grid grid-cols-2 gap-2 min-h-0">
            {cameras.map((cam) => (
              <div key={cam.ip} className="bg-[var(--ss-bg-3)] rounded border border-[var(--ss-border)] p-2">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-[10px] text-gray-300">{cam.ip}</span>
                  <span className="text-[8px] text-gray-500">{cam.brand || 'N/A'}</span>
                </div>
                <div className="aspect-video bg-black/50 rounded flex items-center justify-center overflow-hidden">
                  <img
                    src={`/api/iot/snapshot?ip=${cam.ip}&port=${cam.port || 80}&path=/snapshot.cgi&_t=${Date.now()}`}
                    className="w-full h-full object-contain"
                    onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                  />
                </div>
                <div className="flex gap-1 mt-1">
                  <button
                    onClick={() => window.open(`/api/iot/snapshot?ip=${cam.ip}&port=${cam.port || 80}&path=/snapshot.cgi`, '_blank')}
                    className="px-2 py-0.5 text-[9px] bg-cyan-600/30 border border-cyan-500/30 text-cyan-300 rounded hover:bg-cyan-600/50 transition"
                  >
                    📷 Snap
                  </button>
                  {cam.rtsp && (
                    <button
                      onClick={() => detectMotion(cam)}
                      disabled={motionLoading[cam.ip]}
                      className="px-2 py-0.5 text-[9px] bg-amber-600/30 border border-amber-500/30 text-amber-300 rounded hover:bg-amber-600/50 disabled:opacity-50 transition"
                    >
                      {motionLoading[cam.ip] ? '⏳' : '🔴'} Mov
                    </button>
                  )}
                </div>
                {motionStatus[cam.ip] && (
                  <div className="text-[9px] text-amber-300 mt-1">{motionStatus[cam.ip]}</div>
                )}
              </div>
            ))}
            {cameras.length === 0 && (
              <div className="col-span-2 text-gray-500 text-xs flex items-center justify-center h-full">
                {camLoading ? 'Escaneando...' : 'Escanea para ver cámaras'}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* FILA INFERIOR: Comms / Intel / Exploits / Traffic */}
      <div className="h-64 shrink-0">
        {/* Tabs */}
        <div className="flex gap-1 mb-2">
          <button
            onClick={() => setBottomView('comms')}
            className={`px-3 py-1 text-[10px] border rounded-t font-mono transition
              ${bottomView === 'comms' ? 'bg-cyan-500/20 border-cyan-400 text-cyan-200' : 'border-[var(--ss-border)] text-gray-400 hover:text-cyan-300'}`}
          >
            🦇 Ultrasonidos
          </button>
          <button
            onClick={() => setBottomView('intel')}
            className={`px-3 py-1 text-[10px] border rounded-t font-mono transition
              ${bottomView === 'intel' ? 'bg-cyan-500/20 border-cyan-400 text-cyan-200' : 'border-[var(--ss-border)] text-gray-400 hover:text-cyan-300'}`}
          >
            🌐 Threat Intel
          </button>
          <button
            onClick={() => setBottomView('recon')}
            className={`px-3 py-1 text-[10px] border rounded-t font-mono transition
              ${bottomView === 'recon' ? 'bg-purple-500/20 border-purple-400 text-purple-200' : 'border-[var(--ss-border)] text-gray-400 hover:text-purple-300'}`}
          >
            🔍 Recon OSINT
          </button>
          <button
            onClick={() => setBottomView('mirror')}
            className={`px-3 py-1 text-[10px] border rounded-t font-mono transition
              ${bottomView === 'mirror' ? 'bg-pink-500/20 border-pink-400 text-pink-200' : 'border-[var(--ss-border)] text-gray-400 hover:text-pink-300'}`}
          >
            🌑 Black Mirror
          </button>
        </div>

        {bottomView === 'comms' ? (
          <div className="h-56 bg-[var(--ss-bg-2)] border border-[var(--ss-border)] rounded-lg overflow-hidden flex flex-col">
            <div className="p-2 bg-[var(--ss-bg-3)] border-b border-[var(--ss-border)] flex items-center justify-between">
              <span className="text-xs text-cyan-400 flex items-center gap-2">
                <Radio size={14} /> COMUNICACIONES ULTRASÓNICAS
                <span className="text-[9px] text-gray-500">18-20 kHz · Web Audio API + Backend</span>
              </span>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <Sliders size={14} className="text-gray-400" />
                  <input
                    type="range" min="-2000" max="2000" step="100"
                    value={freqOffset}
                    onChange={e => setFreqOffset(parseInt(e.target.value))}
                    className="w-32 accent-cyan-500"
                  />
                  <span className="text-[10px] text-gray-400 w-20 text-right">
                    {(18000 + freqOffset).toLocaleString()} Hz
                  </span>
                </div>
                <button
                  onClick={listenUltrasonic}
                  disabled={isListening}
                  className="px-3 py-1 text-[10px] bg-green-600/30 border border-green-500/30 text-green-300 rounded hover:bg-green-600/50 disabled:opacity-50 transition flex items-center gap-1"
                >
                  <Mic size={12} /> {isListening ? 'Escuchando...' : 'Escuchar'}
                </button>
              </div>
            </div>
            <div className="flex-1 flex min-h-0">
              <div className="flex-1 p-3 flex flex-col gap-2">
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={ultraMsg}
                    onChange={e => setUltraMsg(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && sendUltrasonicBrowser(ultraMsg, freqOffset)}
                    placeholder="Mensaje a transmitir..."
                    maxLength={200}
                    className="flex-1 bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded px-3 py-2 text-xs text-gray-200 focus:border-cyan-500 focus:outline-none"
                  />
                  <button
                    onClick={() => sendUltrasonicBrowser(ultraMsg, freqOffset)}
                    disabled={isSending || !ultraMsg.trim()}
                    className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 rounded text-xs font-bold text-white disabled:opacity-50 transition flex items-center gap-2"
                  >
                    <Send size={14} /> Enviar
                  </button>
                </div>
                <div className="flex items-center gap-3 text-[9px] text-gray-500">
                  <span>Freq: <span className="text-cyan-400">{(18000 + freqOffset).toLocaleString()} Hz</span></span>
                  <span>·</span>
                  <span>Sync: <span className="text-amber-400">{(19500 + freqOffset).toLocaleString()} Hz</span></span>
                  <span>·</span>
                  <span className="text-green-400">{ultraLog.filter(l => l.type === 'sent').length} enviados · {ultraLog.filter(l => l.type === 'received').length} recibidos</span>
                </div>
              </div>
              <div className="w-80 p-2 border-l border-[var(--ss-border)] overflow-y-auto">
                <div className="text-[9px] uppercase tracking-widest text-gray-500 mb-1">Historial</div>
                {ultraLog.length === 0 ? (
                  <div className="text-[9px] text-gray-600">Esperando actividad...</div>
                ) : (
                  ultraLog.map((entry, i) => (
                    <div key={i} className={`text-[9px] py-0.5 border-b border-[var(--ss-border)] ${logColor(entry.type)}`}>
                      <span className="text-gray-600">[{entry.time}]</span> {entry.message}
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        ) : bottomView === 'intel' ? (
          <div className="h-56 grid grid-cols-3 gap-3">
            <IntelPanel />
            <ExploitMatrix />
            <TrafficMonitor />
          </div>
        ) : bottomView === 'recon' ? (
          <div className="h-56 grid grid-cols-2 gap-3">
            <OSINTPanel />
            <WiFiPanel />
          </div>
        ) : bottomView === 'mirror' ? (
          <div className="h-56 grid grid-cols-1 gap-3">
            <BlackMirrorPanel />
          </div>
        ) : null}
      </div>
    </div>
  );
}
