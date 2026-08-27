import { useState, useEffect, useRef } from 'react';
import { Activity, Play, StopCircle, AlertOctagon, ArrowUpRight, ArrowDownLeft, Server, Wifi } from 'lucide-react';
import { getApiKey } from '../lib/api';

function trafficHeaders(): Record<string, string> {
  const key = getApiKey()
  return key ? { 'Authorization': `Bearer ${key}` } : {}
}

const PROTO_COLORS: Record<string, string> = {
  'HTTPS/TLS': '#06b6d4', HTTP: '#f59e0b', DNS: '#a78bfa', ARP: '#64748b',
  ICMP: '#f97316', TCP: '#22c55e', UDP: '#3b82f6', OTHER: '#475569',
};

function protoColor(name: string) {
  return PROTO_COLORS[name] || '#475569';
}

export default function TrafficMonitor() {
  const [capturing, setCapturing] = useState(false);
  const [analysis, setAnalysis] = useState<any>(null);
  const [iface, setIface] = useState('any');
  const [duration, setDuration] = useState(15);
  const [countdown, setCountdown] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const sessionIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (countdown > 0) {
      const t = setTimeout(() => setCountdown(c => c - 1), 1000);
      return () => clearTimeout(t);
    }
  }, [countdown]);

  const startCapture = async () => {
    setAnalysis(null);
    setError(null);
    try {
      const res = await fetch(`/api/capture/start?interface=${iface}&duration=${duration}`, { method: 'POST', headers: trafficHeaders() });
      if (!res.ok) {
        const err = await res.json();
        setError(err.detail || `HTTP ${res.status}`);
        return;
      }
      const data = await res.json();
      sessionIdRef.current = data.session_id;
      setCapturing(true);
      setCountdown(duration + 2);
      setTimeout(() => {
        if (sessionIdRef.current) stopCapture(sessionIdRef.current);
      }, (duration + 2) * 1000);
    } catch (e: any) {
      setError(`Error: ${e.message}`);
    }
  };

  const stopCapture = async (sid: string) => {
    try {
      const res = await fetch(`/api/capture/stop/${sid}`, { method: 'POST', headers: trafficHeaders() });
      if (!res.ok) { setCapturing(false); return; }
      const data = await res.json();
      setAnalysis(data.analysis);
      setCapturing(false);
      setCountdown(0);
      sessionIdRef.current = null;
    } catch {
      setCapturing(false);
    }
  };

  const totalProtoPackets = analysis?.protocols
    ? Object.values(analysis.protocols as Record<string, number>).reduce((a, b) => a + b, 0)
    : 0;

  return (
    <div className="bg-[var(--ss-bg-2)] border border-[var(--ss-border)] rounded-lg p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <h3 className="text-xs uppercase tracking-widest text-green-400 flex items-center gap-2">
          <Activity size={14} /> Traffic Analyzer
        </h3>
        <div className="flex items-center gap-2">
          <select
            value={iface}
            onChange={e => setIface(e.target.value)}
            disabled={capturing}
            className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] text-[10px] text-gray-300 rounded px-2 py-1 font-mono disabled:opacity-50"
          >
            <option value="any">any</option>
            <option value="wlan0">wlan0</option>
            <option value="eth0">eth0</option>
            <option value="wlan1">wlan1</option>
          </select>
          <select
            value={duration}
            onChange={e => setDuration(Number(e.target.value))}
            disabled={capturing}
            className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] text-[10px] text-gray-300 rounded px-2 py-1 font-mono disabled:opacity-50"
          >
            <option value={10}>10s</option>
            <option value={15}>15s</option>
            <option value={30}>30s</option>
            <option value={60}>60s</option>
          </select>
          <button
            onClick={startCapture}
            disabled={capturing}
            className={`px-3 py-1 text-[10px] text-white rounded flex items-center gap-1 font-mono transition disabled:opacity-50
              ${capturing ? 'bg-gray-600' : 'bg-green-600/40 border border-green-500/40 hover:bg-green-600/60'}`}
          >
            {capturing ? <><StopCircle size={12} /> {countdown}s</> : <><Play size={12} /> Capturar</>}
          </button>
        </div>
      </div>

      {capturing && (
        <div className="flex items-center gap-2 text-amber-400 text-[10px] mb-3 font-mono">
          <div className="w-2 h-2 bg-amber-400 rounded-full animate-pulse" />
          Capturando paquetes en <span className="text-gray-300">{iface}</span>... ({countdown}s restantes)
        </div>
      )}

      {error && (
        <div className="text-[10px] text-red-400 font-mono mb-3 bg-red-500/10 border border-red-500/30 rounded p-2">
          ⚠️ {error}
        </div>
      )}

      {analysis && (
        <div className="flex-1 space-y-4 overflow-y-auto min-h-0 pr-1">
          {/* Stats grid */}
          <div className="grid grid-cols-3 gap-2">
            <div className="bg-[var(--ss-bg-3)] rounded p-2 text-center border border-[var(--ss-border)]">
              <div className="text-lg font-bold text-gray-200">{analysis.total_packets}</div>
              <div className="text-[8px] text-gray-500 tracking-wider">PAQUETES</div>
            </div>
            <div className="bg-[var(--ss-bg-3)] rounded p-2 text-center border border-[var(--ss-border)]">
              <div className="text-lg font-bold text-cyan-400">{analysis.protocols ? Object.keys(analysis.protocols).length : 0}</div>
              <div className="text-[8px] text-gray-500 tracking-wider">PROTOCOLOS</div>
            </div>
            <div className={`bg-[var(--ss-bg-3)] rounded p-2 text-center border ${analysis.anomalies?.length ? 'border-red-500/40' : 'border-[var(--ss-border)]'}`}>
              <div className={`text-lg font-bold ${analysis.anomalies?.length ? 'text-red-400' : 'text-gray-500'}`}>{analysis.anomalies?.length || 0}</div>
              <div className="text-[8px] text-gray-500 tracking-wider">ANOMALÍAS</div>
            </div>
          </div>

          {/* Anomalías */}
          {analysis.anomalies?.length > 0 && (
            <div className="space-y-1.5">
              {analysis.anomalies.map((a: any, idx: number) => (
                <div key={idx} className="bg-red-500/10 border border-red-500/30 rounded p-2 flex items-start gap-2">
                  <AlertOctagon size={12} className="text-red-400 mt-0.5 shrink-0" />
                  <div>
                    <div className="text-[10px] font-bold text-red-400 font-mono">{a.type} ({a.severity})</div>
                    <div className="text-[9px] text-gray-400">{a.description}</div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Protocolos */}
          {analysis.protocols && Object.keys(analysis.protocols).length > 0 && (
            <div className="space-y-1">
              <div className="text-[9px] uppercase tracking-widest text-gray-500 mb-1.5">Distribución de protocolos</div>
              {Object.entries(analysis.protocols)
                .sort((a: any, b: any) => b[1] - a[1])
                .map(([proto, count]: [string, any]) => (
                <div key={proto} className="flex items-center justify-between text-[10px] font-mono">
                  <span className="text-gray-400 flex items-center gap-1.5 w-24 shrink-0">
                    <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: protoColor(proto) }} />
                    {proto}
                  </span>
                  <div className="flex items-center gap-2 flex-1">
                    <div className="flex-1 h-1.5 bg-[var(--ss-bg-3)] rounded-full overflow-hidden">
                      <div className="h-full rounded-full"
                        style={{ width: `${Math.min(100, totalProtoPackets ? (count / totalProtoPackets) * 100 : 0)}%`, backgroundColor: protoColor(proto) }} />
                    </div>
                    <span className="text-gray-500 w-8 text-right">{count}</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Top talkers / destinos / servicios */}
          {(analysis.top_talkers?.length > 0 || analysis.top_destinations?.length > 0 || analysis.top_services?.length > 0) && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              {analysis.top_talkers?.length > 0 && (
                <div className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded p-2">
                  <div className="text-[8px] uppercase tracking-widest text-gray-500 mb-1.5 flex items-center gap-1">
                    <ArrowUpRight size={10} className="text-amber-400" /> Origen (top)
                  </div>
                  {analysis.top_talkers.map((t: any, i: number) => (
                    <div key={i} className="flex items-center justify-between text-[9px] font-mono py-0.5">
                      <span className="text-gray-300 truncate">{t.ip}</span>
                      <span className="text-gray-500 shrink-0 ml-1">{t.packets}</span>
                    </div>
                  ))}
                </div>
              )}
              {analysis.top_destinations?.length > 0 && (
                <div className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded p-2">
                  <div className="text-[8px] uppercase tracking-widest text-gray-500 mb-1.5 flex items-center gap-1">
                    <ArrowDownLeft size={10} className="text-cyan-400" /> Destino (top)
                  </div>
                  {analysis.top_destinations.map((t: any, i: number) => (
                    <div key={i} className="flex items-center justify-between text-[9px] font-mono py-0.5">
                      <span className="text-gray-300 truncate">{t.ip}</span>
                      <span className="text-gray-500 shrink-0 ml-1">{t.packets}</span>
                    </div>
                  ))}
                </div>
              )}
              {analysis.top_services?.length > 0 && (
                <div className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded p-2">
                  <div className="text-[8px] uppercase tracking-widest text-gray-500 mb-1.5 flex items-center gap-1">
                    <Server size={10} className="text-green-400" /> Servicios (top)
                  </div>
                  {analysis.top_services.map((t: any, i: number) => (
                    <div key={i} className="flex items-center justify-between text-[9px] font-mono py-0.5">
                      <span className="text-gray-300 truncate">{t.service}</span>
                      <span className="text-gray-500 shrink-0 ml-1">{t.packets}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {analysis.error && (
            <div className="text-[9px] text-amber-400 font-mono">⚠️ {analysis.error}</div>
          )}
        </div>
      )}

      {!analysis && !capturing && !error && (
        <div className="flex-1 flex flex-col items-center justify-center text-gray-500 text-xs font-mono gap-2">
          <Wifi size={22} className="opacity-30" />
          Inicia una captura para analizar tráfico.
        </div>
      )}
    </div>
  );
}
