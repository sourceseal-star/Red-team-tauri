import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Radio, Send, Download, Play, Mic, Activity, Settings,
         Volume2, Zap, Clock, Cpu, Trash2 } from 'lucide-react';

// Usa el mismo token que BiometricLogin.tsx guarda en localStorage.
const authHeaders = (json = false): Record<string, string> => {
  const token = localStorage.getItem('api_token');
  const h: Record<string, string> = {};
  if (token) h['X-API-Key'] = token;
  if (json) h['Content-Type'] = 'application/json';
  return h;
};

interface MurcielagoStatus {
  protocol: string;
  frequency_range: string;
  capabilities: { send: boolean; receive: boolean; player: string | null; numpy: boolean };
  cached_wavs: number;
  sample_rate: number;
  symbol_duration_ms: number;
}

export const MurcielagoPanel: React.FC = () => {
  const [message, setMessage] = useState('');
  const [repeat, setRepeat] = useState(1);
  const [freqOffset, setFreqOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [receiving, setReceiving] = useState(false);
  const [status, setStatus] = useState<MurcielagoStatus | null>(null);
  const [result, setResult] = useState<{ msg: string; type: 'info' | 'success' | 'error' } | null>(null);
  const [history, setHistory] = useState<{ msg: string; time: string; wav?: string; freq?: number }[]>([]);
  const [receivedMsg, setReceivedMsg] = useState<string | null>(null);
  const [showConfig, setShowConfig] = useState(false);
  const audioRef = useRef<HTMLAudioElement>(null);

  const showMsg = (msg: string, type: 'info' | 'success' | 'error' = 'info', timeout = 8000) => {
    setResult({ msg, type });
    if (timeout > 0) setTimeout(() => setResult(null), timeout);
  };

  // Cargar estado del protocolo al montar
  const loadStatus = useCallback(() => {
    fetch('/api/murcielago/status', { headers: authHeaders() })
      .then(r => r.json())
      .then(d => { if (d && d.capabilities) setStatus(d); })
      .catch(() => {});
  }, []);

  useEffect(() => { loadStatus(); }, [loadStatus]);

  const freqBase = 18000 + freqOffset;

  const send = async () => {
    if (!message.trim()) return;
    setLoading(true);
    showMsg('Generando ultrasonido...', 'info', 0);
    try {
      // Usar el endpoint con offset de frecuencia si freqOffset != 0
      const endpoint = freqOffset !== 0 ? '/api/comms/ultrasonic-send' : '/api/murcielago/send';
      const body = freqOffset !== 0
        ? JSON.stringify({ message, freq_offset: freqOffset })
        : JSON.stringify({ message, repeat });
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: authHeaders(true),
        body,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      showMsg(
        `Enviado: ${data.symbols || ''} | ${data.duration_sec}s | ${data.freq_base || freqBase} Hz | ${data.playing ? 'Reproduciendo' : 'WAV listo'}`,
        'success'
      );
      setHistory(h => [{
        msg: message,
        time: new Date().toLocaleTimeString(),
        wav: data.wav_url,
        freq: data.freq_base || freqBase,
      }, ...h].slice(0, 10));
    } catch (err: any) {
      showMsg(`Error: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const playWav = async (wavUrl: string) => {
    try {
      const res = await fetch(wavUrl, { headers: authHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const objUrl = URL.createObjectURL(blob);
      if (audioRef.current) {
        audioRef.current.src = objUrl;
        audioRef.current.play().catch(() => {});
      }
    } catch (err: any) {
      showMsg(`Error al reproducir: ${err.message}`, 'error');
    }
  };

  const downloadWav = async () => {
    if (!message.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(
        `/api/murcielago/generate-wav?message=${encodeURIComponent(message)}&repeat=${repeat}`,
        { headers: authHeaders() }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `murc_${Date.now()}.wav`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(link.href);
      showMsg('WAV descargado', 'success', 6000);
    } catch (err: any) {
      showMsg(`Error: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const receive = async () => {
    setReceiving(true);
    setReceivedMsg(null);
    showMsg('Escuchando ultrasonidos... (puede tardar varios segundos)', 'info', 0);
    try {
      const res = await fetch('/api/comms/ultrasonic-receive', {
        method: 'POST',
        headers: authHeaders(true),
        body: JSON.stringify({ duration: 5 }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (data.message && data.message.trim()) {
        setReceivedMsg(data.message);
        showMsg(`Recibido: "${data.message}" | Confianza: ${data.confidence || 'N/A'}`, 'success', 12000);
      } else {
        showMsg(data.error || 'No se detecto senal ultrasonica', 'info', 8000);
      }
    } catch (err: any) {
      showMsg(`Error: ${err.message}`, 'error');
    } finally {
      setReceiving(false);
    }
  };

  const testTone = async () => {
    setLoading(true);
    showMsg('Reproduciendo tono de prueba...', 'info', 0);
    try {
      const res = await fetch('/api/comms/ultrasonic-send', {
        method: 'POST',
        headers: authHeaders(true),
        body: JSON.stringify({ message: 'TEST', freq_offset: freqOffset }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      showMsg(`Tono de prueba @ ${data.freq_base || freqBase} Hz | ${data.duration_sec}s`, 'success', 6000);
    } catch (err: any) {
      showMsg(`Error: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const clearHistory = () => {
    setHistory([]);
    showMsg('Historial limpiado', 'info', 3000);
  };

  return (
    <div className="bg-[var(--ss-bg-2)] rounded-lg p-4 border border-[var(--ss-border)] space-y-3">
      <audio ref={audioRef} className="hidden" />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-lg">BAT</span>
          <h3 className="text-xs uppercase tracking-widest text-cyan-400 font-mono">Protocolo MURCIELAGO</h3>
          <span className="text-[9px] text-gray-600">Ultrasonidos 18-20 kHz</span>
        </div>
        <button
          onClick={() => setShowConfig(s => !s)}
          className="p-1.5 rounded border border-[var(--ss-border)] text-gray-400 hover:text-cyan-400 hover:border-cyan-500/30 transition"
          title="Configuracion"
        >
          <Settings size={14} />
        </button>
      </div>

      <p className="text-[10px] text-gray-500 font-mono">
        Comunicacion sin red. Solo altavoz y microfono. Inaudible para adultos.
      </p>

      {/* Estado del sistema — tarjetas de info */}
      {status ? (
        <div className="grid grid-cols-2 gap-2">
          <div className={`bg-[var(--ss-bg-3)] rounded-lg p-2 border ${status.capabilities.send ? 'border-green-500/30' : 'border-red-500/30'}`}>
            <div className="flex items-center gap-1.5">
              <Volume2 size={11} className={status.capabilities.send ? 'text-green-400' : 'text-red-400'} />
              <span className="text-[9px] uppercase tracking-wider text-gray-500">Emisor</span>
            </div>
            <div className={`text-sm font-bold ${status.capabilities.send ? 'text-green-400' : 'text-red-400'}`}>
              {status.capabilities.send ? 'OK' : 'NO DISPONIBLE'}
            </div>
            <div className="text-[8px] text-gray-600 font-mono">{status.capabilities.player || 'sin player'}</div>
          </div>

          <div className={`bg-[var(--ss-bg-3)] rounded-lg p-2 border ${status.capabilities.receive ? 'border-green-500/30' : 'border-red-500/30'}`}>
            <div className="flex items-center gap-1.5">
              <Mic size={11} className={status.capabilities.receive ? 'text-green-400' : 'text-red-400'} />
              <span className="text-[9px] uppercase tracking-wider text-gray-500">Receptor</span>
            </div>
            <div className={`text-sm font-bold ${status.capabilities.receive ? 'text-green-400' : 'text-red-400'}`}>
              {status.capabilities.receive ? 'OK' : 'NO DISPONIBLE'}
            </div>
            <div className="text-[8px] text-gray-600 font-mono">{status.capabilities.numpy ? 'numpy OK' : 'sin numpy'}</div>
          </div>

          <div className="bg-[var(--ss-bg-3)] rounded-lg p-2 border border-[var(--ss-border)]">
            <div className="flex items-center gap-1.5">
              <Radio size={11} className="text-cyan-400" />
              <span className="text-[9px] uppercase tracking-wider text-gray-500">Frecuencia</span>
            </div>
            <div className="text-sm font-bold text-cyan-400 font-mono">{status.frequency_range}</div>
            <div className="text-[8px] text-gray-600 font-mono">Base: {freqBase} Hz</div>
          </div>

          <div className="bg-[var(--ss-bg-3)] rounded-lg p-2 border border-[var(--ss-border)]">
            <div className="flex items-center gap-1.5">
              <Activity size={11} className="text-amber-400" />
              <span className="text-[9px] uppercase tracking-wider text-gray-500">Audio</span>
            </div>
            <div className="text-sm font-bold text-amber-400 font-mono">{(status.sample_rate / 1000).toFixed(1)} kHz</div>
            <div className="text-[8px] text-gray-600 font-mono">{status.symbol_duration_ms}ms/simbolo</div>
          </div>
        </div>
      ) : (
        <div className="text-[10px] text-gray-600 text-center py-4 font-mono">
          Cargando estado del protocolo...
        </div>
      )}

      {/* Panel de configuracion (colapsable) */}
      {showConfig && (
        <div className="bg-[var(--ss-bg-3)] rounded-lg p-3 border border-cyan-500/20 space-y-3">
          <div className="text-[9px] uppercase tracking-widest text-cyan-400 font-mono flex items-center gap-1.5">
            <Settings size={11} /> Configuracion
          </div>

          {/* Offset de frecuencia */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-[9px] text-gray-500 font-mono">Offset de frecuencia</label>
              <span className="text-[10px] text-cyan-400 font-mono">{freqOffset > 0 ? '+' : ''}{freqOffset} Hz | Base: {freqBase} Hz</span>
            </div>
            <input
              type="range"
              min={-2000}
              max={2000}
              step={100}
              value={freqOffset}
              onChange={e => setFreqOffset(Number(e.target.value))}
              className="w-full accent-cyan-500"
            />
            <div className="flex justify-between text-[7px] text-gray-600 font-mono mt-0.5">
              <span>-2000 Hz</span>
              <span>0</span>
              <span>+2000 Hz</span>
            </div>
          </div>

          {/* Info del protocolo */}
          {status && (
            <div className="grid grid-cols-3 gap-1 text-[8px] font-mono">
              <div className="bg-[var(--ss-bg-2)] rounded p-1.5 text-center">
                <div className="text-gray-500">WAVs cache</div>
                <div className="text-cyan-400 font-bold">{status.cached_wavs}</div>
              </div>
              <div className="bg-[var(--ss-bg-2)] rounded p-1.5 text-center">
                <div className="text-gray-500">Sample rate</div>
                <div className="text-cyan-400 font-bold">{status.sample_rate}</div>
              </div>
              <div className="bg-[var(--ss-bg-2)] rounded p-1.5 text-center">
                <div className="text-gray-500">Simbolo</div>
                <div className="text-cyan-400 font-bold">{status.symbol_duration_ms}ms</div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Resultado */}
      {result && (
        <div className={`p-2 rounded text-[10px] font-mono border ${
          result.type === 'error' ? 'bg-red-500/10 border-red-500/30 text-red-300' :
          result.type === 'success' ? 'bg-green-500/10 border-green-500/30 text-green-300' :
          'bg-cyan-500/10 border-cyan-500/30 text-cyan-300'
        }`}>
          {result.msg}
        </div>
      )}

      {/* Mensaje recibido */}
      {receivedMsg && (
        <div className="p-2 rounded border border-purple-500/30 bg-purple-500/10">
          <div className="text-[9px] uppercase tracking-widest text-purple-400 font-mono mb-1">Mensaje Recibido</div>
          <div className="text-sm font-mono text-purple-200 break-all">{receivedMsg}</div>
        </div>
      )}

      {/* Input del mensaje */}
      <div className="flex gap-2">
        <input
          type="text"
          value={message}
          onChange={e => setMessage(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && send()}
          placeholder="Mensaje a transmitir..."
          maxLength={200}
          className="flex-1 bg-[var(--ss-bg-3)] border border-[var(--ss-border)] text-gray-200 text-xs px-3 py-2 rounded font-mono focus:border-cyan-500 focus:outline-none"
        />
        <button
          onClick={send}
          disabled={loading || !message.trim()}
          className="px-4 py-2 bg-cyan-600 text-white text-xs rounded hover:bg-cyan-500 disabled:opacity-50 transition font-mono flex items-center gap-1.5"
        >
          {loading ? <Activity size={12} className="animate-pulse" /> : <Send size={12} />}
          {loading ? '' : 'Enviar'}
        </button>
      </div>

      {/* Controles */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1.5">
          <label className="text-[9px] text-gray-500 font-mono">Rep:</label>
          <select
            value={repeat}
            onChange={e => setRepeat(Number(e.target.value))}
            className="bg-[var(--ss-bg-3)] border border-[var(--ss-border)] text-gray-300 text-[10px] px-2 py-1 rounded font-mono"
          >
            <option value={1}>x1</option>
            <option value={2}>x2</option>
            <option value={3}>x3 (Farol)</option>
            <option value={5}>x5</option>
          </select>
        </div>

        <button
          onClick={downloadWav}
          disabled={loading || !message.trim()}
          className="px-3 py-1.5 text-[9px] border border-amber-500/30 text-amber-300 rounded hover:bg-amber-500/10 disabled:opacity-50 transition font-mono flex items-center gap-1"
        >
          <Download size={11} /> WAV
        </button>

        <button
          onClick={testTone}
          disabled={loading}
          className="px-3 py-1.5 text-[9px] border border-cyan-500/30 text-cyan-300 rounded hover:bg-cyan-500/10 disabled:opacity-50 transition font-mono flex items-center gap-1"
        >
          <Zap size={11} /> Test
        </button>

        <button
          onClick={receive}
          disabled={receiving}
          className="px-3 py-1.5 text-[9px] border border-purple-500/30 text-purple-300 rounded hover:bg-purple-500/10 disabled:opacity-50 transition font-mono flex items-center gap-1"
        >
          {receiving ? <Activity size={11} className="animate-pulse" /> : <Mic size={11} />}
          {receiving ? 'Escuchando...' : 'Recibir'}
        </button>

        <button
          onClick={loadStatus}
          className="px-3 py-1.5 text-[9px] border border-[var(--ss-border)] text-gray-400 rounded hover:text-cyan-400 transition font-mono flex items-center gap-1"
        >
          <Activity size={11} /> Refresh
        </button>
      </div>

      {/* Historial */}
      {history.length > 0 && (
        <div className="border-t border-[var(--ss-border)] pt-2">
          <div className="flex items-center justify-between mb-1">
            <h4 className="text-[9px] uppercase tracking-widest text-gray-500 font-mono">Historial ({history.length})</h4>
            <button onClick={clearHistory} className="text-gray-600 hover:text-red-400 transition">
              <Trash2 size={11} />
            </button>
          </div>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {history.map((h, i) => (
              <div key={i} className="flex items-center justify-between text-[9px] font-mono bg-[var(--ss-bg-3)] rounded px-2 py-1">
                <span className="text-gray-300 truncate flex-1">{h.msg}</span>
                {h.freq && <span className="text-cyan-400 ml-2">{h.freq}Hz</span>}
                <span className="text-gray-600 ml-2">{h.time}</span>
                {h.wav && (
                  <button
                    onClick={() => h.wav && playWav(h.wav)}
                    className="ml-2 text-cyan-400 hover:text-cyan-300"
                  >
                    <Play size={10} />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default MurcielagoPanel;
