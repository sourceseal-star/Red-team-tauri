import { useState, useEffect, useRef } from 'react';
import { Activity, Play, StopCircle, AlertOctagon } from 'lucide-react';

export default function TrafficMonitor() {
  const [capturing, setCapturing] = useState(false);
  const [analysis, setAnalysis] = useState<any>(null);
  const [iface, setIface] = useState('any');
  const [countdown, setCountdown] = useState(0);
  const sessionIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (countdown > 0) {
      const t = setTimeout(() => setCountdown(c => c - 1), 1000);
      return () => clearTimeout(t);
    }
  }, [countdown]);

  const startCapture = async () => {
    setAnalysis(null);
    try {
      const res = await fetch(`/api/capture/start?interface=${iface}&duration=15`, { method: 'POST' });
      if (!res.ok) {
        const err = await res.json();
        alert(err.detail || `HTTP ${res.status}`);
        return;
      }
      const data = await res.json();
      sessionIdRef.current = data.session_id;
      setCapturing(true);
      setCountdown(17);
      // Auto-stop después de la duración + margen
      setTimeout(() => {
        if (sessionIdRef.current) {
          stopCapture(sessionIdRef.current);
        }
      }, 17000);
    } catch (e: any) {
      alert(`Error: ${e.message}`);
    }
  };

  const stopCapture = async (sid: string) => {
    try {
      const res = await fetch(`/api/capture/stop/${sid}`, { method: 'POST' });
      if (!res.ok) return;
      const data = await res.json();
      setAnalysis(data.analysis);
      setCapturing(false);
      setCountdown(0);
      sessionIdRef.current = null;
    } catch (e) {
      setCapturing(false);
    }
  };

  return (
    <div className="bg-[var(--ss-bg-2)] border border-[var(--ss-border)] rounded-lg p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
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
          Capturando paquetes en {iface}... ({countdown}s restantes)
        </div>
      )}

      {analysis && (
        <div className="flex-1 space-y-3 overflow-y-auto min-h-0">
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
            <div className="bg-[var(--ss-bg-3)] rounded p-2 text-center border border-[var(--ss-border)]">
              <div className="text-lg font-bold text-red-400">{analysis.anomalies?.length || 0}</div>
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
              <div className="text-[9px] uppercase tracking-widest text-gray-500 mb-1">Distribución de protocolos</div>
              {Object.entries(analysis.protocols).map(([proto, count]: [string, any]) => (
                <div key={proto} className="flex items-center justify-between text-[10px] font-mono">
                  <span className="text-gray-400">{proto}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-24 h-1.5 bg-[var(--ss-bg-3)] rounded-full overflow-hidden">
                      <div className="h-full bg-cyan-500 rounded-full"
                        style={{ width: `${Math.min(100, analysis.total_packets ? (count / analysis.total_packets) * 100 : 0)}%` }} />
                    </div>
                    <span className="text-gray-500 w-8 text-right">{count}</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {analysis.error && (
            <div className="text-[9px] text-amber-400 font-mono">⚠️ {analysis.error}</div>
          )}
        </div>
      )}

      {!analysis && !capturing && (
        <div className="flex-1 flex items-center justify-center text-gray-500 text-xs font-mono">
          Inicia una captura para analizar tráfico.
        </div>
      )}
    </div>
  );
}
