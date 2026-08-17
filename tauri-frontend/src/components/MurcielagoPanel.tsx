import React, { useState, useEffect, useRef } from 'react';

// Usa el mismo token que BiometricLogin.tsx guarda en localStorage.
// Sin esto, /api/murcielago/* devuelve 401 y el panel queda sin datos
// (estado del protocolo nunca carga, envios fallan en silencio).
const authHeaders = (): Record<string, string> => {
  const token = localStorage.getItem('api_token');
  return token ? { 'X-API-Key': token } : {};
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
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<MurcielagoStatus | null>(null);
  const [result, setResult] = useState<{ msg: string; type: 'info' | 'success' | 'error' } | null>(null);
  const [history, setHistory] = useState<{ msg: string; time: string; wav?: string }[]>([]);
  const audioRef = useRef<HTMLAudioElement>(null);

  // Cargar estado del protocolo
  useEffect(() => {
    fetch('/api/murcielago/status', { headers: authHeaders() })
      .then(r => r.json())
      // FIX: si el backend devuelve un error (401, 500...) el objeto no
      // tiene "capabilities" -> el render crasheaba con pagina en blanco
      // al leer status.capabilities.send. Se valida la forma antes de setear.
      .then(d => { if (d && d.capabilities) setStatus(d); })
      .catch(() => {});
  }, []);

  const send = async () => {
    if (!message.trim()) return;
    setLoading(true);
    setResult({ msg: 'Generando ultrasonido...', type: 'info' });
    try {
      const res = await fetch('/api/murcielago/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ message, repeat }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setResult({
        msg: `Enviado: ${data.symbols} · ${data.duration_sec}s · ${data.playing ? 'Reproduciendo' : 'WAV listo'}`,
        type: 'success',
      });
      setHistory(h => [{ msg: message, time: new Date().toLocaleTimeString(), wav: data.wav_url }, ...h].slice(0, 10));
    } catch (err: any) {
      setResult({ msg: `Error: ${err.message}`, type: 'error' });
    } finally {
      setLoading(false);
      setTimeout(() => setResult(null), 8000);
    }
  };

  const playWav = async (wavUrl: string) => {
    // /api/murcielago/download/* requiere auth y <audio src> no puede mandar
    // headers -> se descarga como blob con el token y se reproduce por object URL.
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
      setResult({ msg: `Error al reproducir: ${err.message}`, type: 'error' });
    }
  };

  const downloadWav = async () => {
    if (!message.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/murcielago/generate-wav?message=${encodeURIComponent(message)}&repeat=${repeat}`, { headers: authHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `murc_${Date.now()}.wav`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(link.href);
      setResult({ msg: 'WAV descargado', type: 'success' });
    } catch (err: any) {
      setResult({ msg: `Error: ${err.message}`, type: 'error' });
    } finally {
      setLoading(false);
      setTimeout(() => setResult(null), 6000);
    }
  };

  return (
    <div className="bg-[var(--ss-bg-2)] rounded-lg p-4 border border-[var(--ss-border)]">
      <audio ref={audioRef} className="hidden" />

      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">🦇</span>
        <h3 className="text-xs uppercase tracking-widest text-cyan-400 font-mono">Protocolo MURCIÉLAGO</h3>
        <span className="text-[9px] text-gray-600">Ultrasonidos 18-20 kHz</span>
      </div>
      <p className="text-[10px] text-gray-500 mb-3 font-mono">
        Comunicación sin red. Solo altavoz y micrófono. Inaudible para adultos.
      </p>

      {/* Estado del sistema */}
      {status && (
        <div className="flex gap-3 mb-3 text-[9px] font-mono">
          <span className={status.capabilities.send ? 'text-green-400' : 'text-red-400'}>
            ● Emisor: {status.capabilities.send ? 'OK' : 'NO'}
          </span>
          <span className={status.capabilities.receive ? 'text-green-400' : 'text-red-400'}>
            ● Receptor: {status.capabilities.receive ? 'OK' : 'NO'}
          </span>
          <span className="text-gray-500">Player: {status.capabilities.player || 'none'}</span>
        </div>
      )}

      {/* Input del mensaje */}
      <div className="flex gap-2 mb-2">
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
          className="px-4 py-2 bg-cyan-600 text-white text-xs rounded hover:bg-cyan-500 disabled:opacity-50 transition font-mono"
        >
          {loading ? '⏳' : '📢 Enviar'}
        </button>
      </div>

      {/* Controles */}
      <div className="flex items-center gap-3 mb-3">
        <label className="text-[9px] text-gray-500 font-mono">Repeticiones (Farol):</label>
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
        <button
          onClick={downloadWav}
          disabled={loading || !message.trim()}
          className="px-3 py-1 text-[9px] border border-amber-500/30 text-amber-300 rounded hover:bg-amber-500/10 disabled:opacity-50 transition font-mono"
        >
          ⬇ Descargar WAV
        </button>
      </div>

      {/* Resultado */}
      {result && (
        <div className={`mb-3 p-2 rounded text-[10px] font-mono border ${
          result.type === 'error' ? 'bg-red-500/10 border-red-500/30 text-red-300' :
          result.type === 'success' ? 'bg-green-500/10 border-green-500/30 text-green-300' :
          'bg-cyan-500/10 border-cyan-500/30 text-cyan-300'
        }`}>
          {result.msg}
        </div>
      )}

      {/* Historial */}
      {history.length > 0 && (
        <div className="border-t border-[var(--ss-border)] pt-2">
          <h4 className="text-[9px] uppercase tracking-widest text-gray-500 mb-1 font-mono">Historial</h4>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {history.map((h, i) => (
              <div key={i} className="flex items-center justify-between text-[9px] font-mono">
                <span className="text-gray-400 truncate flex-1">{h.msg}</span>
                <span className="text-gray-600 ml-2">{h.time}</span>
                {h.wav && (
                  <button
                    onClick={() => h.wav && playWav(h.wav)}
                    className="ml-2 text-cyan-400 hover:text-cyan-300"
                  >
                    ▶
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
