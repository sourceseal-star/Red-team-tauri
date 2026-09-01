import { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Radio, Lock, Volume2, Repeat, Clock, Activity, Trash2, Eye } from 'lucide-react';

// ═══════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════

interface UltraLogEntry {
  time: string;
  type: 'sent' | 'received' | 'error' | 'info';
  message: string;
  freq?: number;
  symbols?: number;
  encrypted?: boolean;
}

interface SavedMessage {
  id: string;
  text: string;
  time: string;
  freq: number;
  symbols: number;
  encrypted: boolean;
}

// ═══════════════════════════════════════════════════════════
// CHANNEL PRESETS
// ═══════════════════════════════════════════════════════════

const CHANNELS = [
  { id: 0, label: 'CH-0 Base', offset: 0, color: 'text-cyan-400' },
  { id: 1, label: 'CH-1 +500Hz', offset: 500, color: 'text-green-400' },
  { id: 2, label: 'CH-2 +1kHz', offset: 1000, color: 'text-amber-400' },
  { id: 3, label: 'CH-3 +1.5kHz', offset: 1500, color: 'text-orange-400' },
  { id: 4, label: 'CH-4 +2kHz', offset: 2000, color: 'text-red-400' },
];

// ═══════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════

function getToken(): string | null {
  return localStorage.getItem('api_token');
}

function authHeaders(json = true): Record<string, string> {
  const t = getToken();
  const h: Record<string, string> = {};
  if (t) h['Authorization'] = `Bearer ${t}`;
  if (json) h['Content-Type'] = 'application/json';
  return h;
}

// XOR cipher con passphrase — simple pero efectivo para comms covertas
function xorEncrypt(text: string, passphrase: string): string {
  if (!passphrase) return text;
  const key = passphrase.repeat(Math.ceil(text.length / passphrase.length));
  let result = '';
  for (let i = 0; i < text.length; i++) {
    result += String.fromCharCode(text.charCodeAt(i) ^ key.charCodeAt(i));
  }
  // Base64 para que sea传输 seguro
  return btoa(result);
}

function xorDecrypt(b64: string, passphrase: string): string {
  if (!passphrase) return b64;
  try {
    const text = atob(b64);
    const key = passphrase.repeat(Math.ceil(text.length / passphrase.length));
    let result = '';
    for (let i = 0; i < text.length; i++) {
      result += String.fromCharCode(text.charCodeAt(i) ^ key.charCodeAt(i));
    }
    return result;
  } catch {
    return b64;
  }
}

// Calcular tiempo estimado de transmisión
function estimateDuration(msgLen: number, repeat: number): number {
  // Cada byte = 2 hex chars + checksum (2 chars) + separador (1) = ~(2*len + 3) símbolos
  // Cada símbolo = 80ms tone + 25ms silence = 105ms
  // + 300ms sync + 50ms gap + 200ms sync final = 550ms overhead
  const symbols = msgLen * 2 + 3;
  const symbolTime = 0.08 + 0.025; // 105ms
  const overhead = 0.3 + 0.05 + 0.2; // 550ms
  return (symbols * symbolTime + overhead) * repeat;
}

// ═══════════════════════════════════════════════════════════
// SPECTRUM ANALYZER (canvas + Web Audio API)
// ═══════════════════════════════════════════════════════════

function SpectrumAnalyzer({ listening }: { listening: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    if (!listening) {
      // Detener
      if (animRef.current) cancelAnimationFrame(animRef.current);
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop());
        streamRef.current = null;
      }
      if (audioCtxRef.current && audioCtxRef.current.state !== 'closed') {
        audioCtxRef.current.close().catch(() => {});
      }
      // Limpiar canvas
      const canvas = canvasRef.current;
      if (canvas) {
        const ctx = canvas.getContext('2d');
        if (ctx) {
          ctx.clearRect(0, 0, canvas.width, canvas.height);
        }
      }
      return;
    }

    let cancelled = false;

    const start = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: false,
            noiseSuppression: false,
            autoGainControl: false,
          }
        });
        if (cancelled) {
          stream.getTracks().forEach(t => t.stop());
          return;
        }
        streamRef.current = stream;

        const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
        audioCtxRef.current = ctx;

        const source = ctx.createMediaStreamSource(stream);
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 4096;
        analyser.smoothingTimeConstant = 0.7;
        source.connect(analyser);
        analyserRef.current = analyser;

        const bufferLen = analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLen);

        const draw = () => {
          if (cancelled) return;
          const canvas = canvasRef.current;
          if (!canvas) return;
          const ctx2d = canvas.getContext('2d');
          if (!ctx2d) return;

          const W = canvas.width;
          const H = canvas.height;

          // Fondo
          ctx2d.fillStyle = '#0a0e12';
          ctx2d.fillRect(0, 0, W, H);

          analyser.getByteFrequencyData(dataArray);

          // Nos interesa 15kHz - 21kHz (ultrasonido)
          const sr = ctx.sampleRate;
          const binHz = sr / 2 / bufferLen;
          const startBin = Math.floor(15000 / binHz);
          const endBin = Math.floor(21000 / binHz);

          // Dibujar espectro
          const barWidth = W / (endBin - startBin);
          for (let i = startBin; i < endBin; i++) {
            const val = dataArray[i];
            const barHeight = (val / 255) * H;
            const x = (i - startBin) * barWidth;
            const y = H - barHeight;

            // Color basado en intensidad
            const intensity = val / 255;
            if (intensity > 0.6) {
              ctx2d.fillStyle = `rgba(0, 212, 255, ${intensity})`;
            } else if (intensity > 0.3) {
              ctx2d.fillStyle = `rgba(201, 162, 39, ${intensity})`;
            } else {
              ctx2d.fillStyle = `rgba(100, 100, 100, ${intensity * 0.5})`;
            }
            ctx2d.fillRect(x, y, barWidth - 1, barHeight);
          }

          // Líneas de referencia para frecuencias clave
          ctx2d.strokeStyle = 'rgba(0, 212, 255, 0.2)';
          ctx2d.lineWidth = 1;
          ctx2d.setLineDash([2, 4]);
          [18000, 18500, 19000, 19500, 20000].forEach(freq => {
            const x = ((freq - 15000) / 6000) * W;
            ctx2d.beginPath();
            ctx2d.moveTo(x, 0);
            ctx2d.lineTo(x, H);
            ctx2d.stroke();
          });
          ctx2d.setLineDash([]);

          // Etiquetas de frecuencia
          ctx2d.fillStyle = 'rgba(150, 150, 150, 0.6)';
          ctx2d.font = '9px monospace';
          ctx2d.fillText('15k', 2, H - 4);
          ctx2d.fillText('18k', ((18000 - 15000) / 6000) * W - 8, H - 4);
          ctx2d.fillText('20k', ((20000 - 15000) / 6000) * W - 8, H - 4);
          ctx2d.fillText('21k', W - 20, H - 4);

          animRef.current = requestAnimationFrame(draw);
        };

        draw();
      } catch (e) {
        // Sin micrófono — mostrar mensaje
        const canvas = canvasRef.current;
        if (canvas) {
          const ctx2d = canvas.getContext('2d');
          if (ctx2d) {
            ctx2d.fillStyle = '#0a0e12';
            ctx2d.fillRect(0, 0, canvas.width, canvas.height);
            ctx2d.fillStyle = 'rgba(200, 100, 100, 0.8)';
            ctx2d.font = '10px monospace';
            ctx2d.fillText('Micrófono no disponible', 10, canvas.height / 2);
          }
        }
      }
    };

    start();

    return () => {
      cancelled = true;
      if (animRef.current) cancelAnimationFrame(animRef.current);
      if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop());
      if (audioCtxRef.current && audioCtxRef.current.state !== 'closed') {
        audioCtxRef.current.close().catch(() => {});
      }
    };
  }, [listening]);

  return (
    <canvas
      ref={canvasRef}
      width={400}
      height={60}
      className="w-full h-16 bg-[#0a0e12] rounded border border-pink-500/20"
    />
  );
}

// ═══════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════

export default function UltrasonicPanel() {
  const [message, setMessage] = useState('');
  const [passphrase, setPassphrase] = useState('');
  const [encrypted, setEncrypted] = useState(false);
  const [channel, setChannel] = useState(0);
  const [repeat, setRepeat] = useState(1);
  const [volume, setVolume] = useState(80);
  const [isSending, setIsSending] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [ultraLog, setUltraLog] = useState<UltraLogEntry[]>([]);
  const [savedMsgs, setSavedMsgs] = useState<SavedMessage[]>([]);
  const [showSpectrum, setShowSpectrum] = useState(false);
  const audioCtxRef = useRef<AudioContext | null>(null);

  const freqBase = 18000 + CHANNELS[channel].offset;
  const estTime = estimateDuration(message.length || 1, repeat);

  // Cargar mensajes guardados
  useEffect(() => {
    try {
      const saved = localStorage.getItem('ultra_history');
      if (saved) setSavedMsgs(JSON.parse(saved));
    } catch {}
  }, []);

  // Guardar mensaje
  const saveMessage = (text: string, freq: number, symbols: number, enc: boolean) => {
    const msg: SavedMessage = {
      id: Date.now().toString(),
      text, freq, symbols, encrypted: enc,
      time: new Date().toLocaleTimeString(),
    };
    setSavedMsgs(prev => {
      const next = [msg, ...prev].slice(0, 20);
      localStorage.setItem('ultra_history', JSON.stringify(next));
      return next;
    });
  };

  // ── Enviar (Web Audio API) ──
  const send = async () => {
    if (!message.trim()) return;
    setIsSending(true);

    let payload = message;
    let wasEncrypted = false;
    if (encrypted && passphrase) {
      payload = xorEncrypt(message, passphrase);
      wasEncrypted = true;
    }

    if (!audioCtxRef.current) {
      audioCtxRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
    }
    const ctx = audioCtxRef.current;
    const baseFreq = freqBase;

    // Tabla de frecuencias con offset de canal
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

    const duration = 0.08;
    const sampleRate = ctx.sampleRate;
    const symbolSamples = Math.floor(sampleRate * duration);
    const gapSamples = Math.floor(sampleRate * 0.025);
    const msgBytes = new TextEncoder().encode(payload);
    const checksum = msgBytes.reduce((a, b) => a + b, 0) % 256;
    const hexStr = Array.from(msgBytes).map(b => b.toString(16).padStart(2, '0').toUpperCase()).join('');
    const symbols = (hexStr + '*' + checksum.toString(16).padStart(2, '0').toUpperCase()).split('');

    // Función para enviar una repetición
    const sendOnce = (repIdx: number) => {
      const syncSamples = Math.floor(sampleRate * 0.3);
      const totalSamples = syncSamples + Math.floor(sampleRate * 0.05) + symbols.length * (symbolSamples + gapSamples) + Math.floor(sampleRate * 0.2);
      const buffer = ctx.createBuffer(1, totalSamples, sampleRate);
      const data = buffer.getChannelData(0);
      const vol = volume / 100;
      let idx = 0;

      // Sync inicial
      for (let i = 0; i < syncSamples; i++)
        data[idx++] = vol * 0.5 * Math.sin(2 * Math.PI * (baseFreq + 1500) * (i / sampleRate));
      for (let i = 0; i < Math.floor(sampleRate * 0.05); i++) data[idx++] = 0;

      // Símbolos
      for (const sym of symbols) {
        if (freqMap[sym]) {
          const [f1, f2] = freqMap[sym];
          for (let i = 0; i < symbolSamples && idx < data.length; i++) {
            const t = i / sampleRate;
            data[idx++] = vol * (0.5 * Math.sin(2 * Math.PI * f1 * t) + 0.5 * Math.sin(2 * Math.PI * f2 * t));
          }
        } else { idx += symbolSamples; }
        for (let i = 0; i < gapSamples && idx < data.length; i++) data[idx++] = 0;
      }

      // Sync final
      for (let i = 0; i < Math.floor(sampleRate * 0.2) && idx < data.length; i++)
        data[idx++] = vol * 0.5 * Math.sin(2 * Math.PI * (baseFreq + 1500) * (i / sampleRate));

      const source = ctx.createBufferSource();
      const gain = ctx.createGain();
      gain.gain.value = vol;
      source.buffer = buffer;
      source.connect(gain);
      gain.connect(ctx.destination);
      source.start();
      return source;
    };

    // Enviar repeticiones con delay
    for (let r = 0; r < repeat; r++) {
      const source = sendOnce(r);
      if (r < repeat - 1) {
        await new Promise(resolve => {
          source.onended = () => {
            setTimeout(resolve, 200); // 200ms entre repeticiones
          };
        });
      }
    }

    // Registrar en backend
    try {
      await fetch('/api/comms/ultrasonic-send', {
        method: 'POST', headers: authHeaders(),
        body: JSON.stringify({ message: payload, freq_offset: CHANNELS[channel].offset }),
      });
    } catch {}

    const logEntry: UltraLogEntry = {
      time: new Date().toLocaleTimeString(),
      type: 'sent',
      message: `"${message}" @ ${baseFreq}Hz`,
      freq: baseFreq,
      symbols: symbols.length,
      encrypted: wasEncrypted,
    };
    setUltraLog(prev => [logEntry, ...prev].slice(0, 50));
    saveMessage(message, baseFreq, symbols.length, wasEncrypted);
    setIsSending(false);
  };

  // ── Escuchar ──
  const listen = async (duration = 6) => {
    setIsListening(true);
    setShowSpectrum(true);
    setUltraLog(prev => [{
      time: new Date().toLocaleTimeString(), type: 'info',
      message: `🎙️ Escuchando ${duration}s en ${freqBase}Hz...`,
    }, ...prev].slice(0, 50));

    try {
      const res = await fetch(`/api/comms/ultrasonic-receive?duration=${duration}`, {
        method: 'POST', headers: authHeaders(),
      });
      const data = await res.json();

      if (data.message && !data.message.startsWith('❌')) {
        let displayMsg = data.message;
        // Intentar descifrar si está cifrado y hay passphrase
        if (encrypted && passphrase) {
          try {
            displayMsg = xorDecrypt(data.message, passphrase);
          } catch {}
        }
        setUltraLog(prev => [{
          time: new Date().toLocaleTimeString(),
          type: 'received',
          message: displayMsg,
          freq: freqBase,
        }, ...prev].slice(0, 50));
      } else {
        setUltraLog(prev => [{
          time: new Date().toLocaleTimeString(),
          type: 'info',
          message: data.message || data.error || 'Sin señal detectada',
        }, ...prev].slice(0, 50));
      }
    } catch (err: any) {
      setUltraLog(prev => [{
        time: new Date().toLocaleTimeString(),
        type: 'error',
        message: err.message,
      }, ...prev].slice(0, 50));
    }
    setIsListening(false);
  };

  // ── Replay mensaje guardado ──
  const replay = (msg: SavedMessage) => {
    setMessage(msg.text);
    const ch = CHANNELS.find(c => c.offset === msg.freq - 18000);
    if (ch) setChannel(ch.id);
    if (msg.encrypted) setEncrypted(true);
  };

  const logColor = (type: string) => ({
    sent: 'text-cyan-300', received: 'text-green-300', error: 'text-red-300',
  }[type] || 'text-gray-400');

  return (
    <div className="flex flex-col gap-2 h-full">
      {/* ── Fila 1: Mensaje + Enviar ── */}
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={message}
          onChange={e => setMessage(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') send(); }}
          placeholder="Mensaje a transmitir..."
          className="flex-1 bg-[var(--ss-bg-3)] border border-[var(--ss-border)] text-pink-300 px-2 py-1 rounded text-xs focus:border-pink-500 focus:outline-none"
        />
        <button onClick={send} disabled={isSending || !message.trim()}
          className="flex items-center gap-1 px-3 py-1 text-xs bg-pink-600/30 border border-pink-500/30 text-pink-300 rounded hover:bg-pink-600/50 disabled:opacity-50 transition">
          <Send size={11} /> Enviar
        </button>
        <button onClick={() => listen(6)} disabled={isListening}
          className="flex items-center gap-1 px-3 py-1 text-xs bg-cyan-600/30 border border-cyan-500/30 text-cyan-300 rounded hover:bg-cyan-600/50 disabled:opacity-50 transition">
          <Radio size={11} /> {isListening ? '...' : 'Escuchar'}
        </button>
      </div>

      {/* ── Fila 2: Controles avanzados ── */}
      <div className="flex items-center gap-3 flex-wrap text-xs">
        {/* Canal */}
        <div className="flex items-center gap-1">
          <span className="text-gray-500 text-[10px]">Canal:</span>
          {CHANNELS.map(ch => (
            <button key={ch.id} onClick={() => setChannel(ch.id)}
              className={`px-1.5 py-0.5 text-[9px] rounded border transition
                ${channel === ch.id ? `${ch.color} border-current bg-current/10` : 'text-gray-500 border-gray-700 hover:text-gray-300'}`}>
              {ch.label}
            </button>
          ))}
        </div>

        {/* Volumen */}
        <div className="flex items-center gap-1">
          <Volume2 size={11} className="text-gray-500" />
          <input type="range" min="10" max="100" value={volume}
            onChange={e => setVolume(Number(e.target.value))}
            className="w-16" />
          <span className="text-[9px] text-gray-500">{volume}%</span>
        </div>

        {/* Repetición */}
        <div className="flex items-center gap-1">
          <Repeat size={11} className="text-gray-500" />
          <button onClick={() => setRepeat(Math.max(1, repeat - 1))} className="text-[10px] text-gray-500 hover:text-gray-300">−</button>
          <span className="text-[9px] text-gray-400 w-4 text-center">{repeat}x</span>
          <button onClick={() => setRepeat(Math.min(10, repeat + 1))} className="text-[10px] text-gray-500 hover:text-gray-300">+</button>
        </div>

        {/* Cifrado */}
        <button onClick={() => setEncrypted(!encrypted)}
          className={`flex items-center gap-1 px-1.5 py-0.5 text-[9px] rounded border transition
            ${encrypted ? 'text-amber-400 border-amber-500/40 bg-amber-500/10' : 'text-gray-500 border-gray-700'}`}>
          <Lock size={10} /> {encrypted ? 'CIFRADO' : ' plano'}
        </button>
        {encrypted && (
          <input type="password" value={passphrase}
            onChange={e => setPassphrase(e.target.value)}
            placeholder="clave"
            className="w-16 bg-[var(--ss-bg-3)] border border-amber-500/30 text-amber-300 px-1 py-0.5 rounded text-[9px] focus:outline-none" />
        )}

        {/* Tiempo estimado */}
        <span className="flex items-center gap-1 text-[9px] text-gray-500 ml-auto">
          <Clock size={10} /> ~{estTime.toFixed(1)}s
        </span>
      </div>

      {/* ── Fila 3: Spectrum analyzer (toggle) ── */}
      <div>
        <button onClick={() => setShowSpectrum(!showSpectrum)}
          className="flex items-center gap-1 text-[9px] text-gray-500 hover:text-cyan-400 mb-1">
          <Activity size={10} /> {showSpectrum ? 'Ocultar' : 'Mostrar'} espectro
        </button>
        {showSpectrum && <SpectrumAnalyzer listening={isListening || showSpectrum} />}
      </div>

      {/* ── Fila 4: Log + Historial ── */}
      <div className="flex-1 flex gap-2 min-h-0">
        {/* Log */}
        <div className="flex-1 overflow-y-auto space-y-0.5">
          {ultraLog.length === 0 ? (
            <div className="text-gray-600 text-xs">Sin actividad. Envía o escucha un mensaje.</div>
          ) : ultraLog.map((entry, i) => (
            <div key={i} className={`text-xs ${logColor(entry.type)}`}>
              <span className="text-gray-600 text-[10px]">[{entry.time}]</span>
              {' '}
              {entry.type === 'sent' && <span className="text-[9px] px-1 rounded bg-pink-500/10 text-pink-400">TX</span>}
              {entry.type === 'received' && <span className="text-[9px] px-1 rounded bg-green-500/10 text-green-400">RX</span>}
              {' '}
              {entry.encrypted && <Lock size={9} className="inline text-amber-400" />}
              {' '}
              {entry.message}
              {entry.freq && <span className="text-[9px] text-gray-600 ml-1">@{entry.freq}Hz</span>}
              {entry.symbols && <span className="text-[9px] text-gray-600 ml-1">{entry.symbols}sym</span>}
            </div>
          ))}
        </div>

        {/* Historial */}
        {savedMsgs.length > 0 && (
          <div className="w-32 border-l border-[var(--ss-border)] pl-2 overflow-y-auto">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[9px] text-gray-500">Historial</span>
              <button onClick={() => { setSavedMsgs([]); localStorage.removeItem('ultra_history'); }}
                className="text-[9px] text-gray-600 hover:text-red-400">
                <Trash2 size={9} />
              </button>
            </div>
            {savedMsgs.map(msg => (
              <button key={msg.id} onClick={() => replay(msg)}
                className="block w-full text-left p-1 rounded hover:bg-pink-500/10 mb-0.5 transition">
                <div className="text-[9px] text-gray-300 truncate">
                  {msg.encrypted && <Lock size={8} className="inline text-amber-400 mr-1" />}
                  {msg.text.slice(0, 20)}{msg.text.length > 20 ? '...' : ''}
                </div>
                <div className="text-[8px] text-gray-600">
                  {msg.time} · {msg.freq}Hz · {msg.symbols}sym
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
