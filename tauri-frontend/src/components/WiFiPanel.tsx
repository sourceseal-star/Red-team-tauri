import { useState, useEffect } from 'react';
import { Wifi, Lock, Unlock, Radio, Play, Key, Trash2, AlertCircle } from 'lucide-react';

export default function WiFiPanel() {
  const [networks, setNetworks] = useState<any[]>([]);
  const [scanning, setScanning] = useState(false);
  const [capturing, setCapturing] = useState<string | null>(null);
  const [crackResult, setCrackResult] = useState<any>(null);
  const [captures, setCaptures] = useState<any[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [method, setMethod] = useState<string>('');

  const scanWiFi = async () => {
    setScanning(true);
    setStatus(null);
    try {
      const res = await fetch('/api/wifi/scan');
      const data = await res.json();
      setNetworks(data.networks || []);
      setMethod(data.method || 'none');
      if (data.note) setStatus(data.note);
    } catch (e: any) {
      setStatus(`Error: ${e.message}`);
    } finally {
      setScanning(false);
    }
  };

  const captureHandshake = async (net: any) => {
    setCapturing(net.bssid);
    setStatus(`Capturando handshake de ${net.ssid}...`);
    try {
      const res = await fetch(
        `/api/wifi/capture/${encodeURIComponent(net.bssid)}?ssid=${encodeURIComponent(net.ssid)}&channel=${net.channel}&duration=30`,
        { method: 'POST' }
      );
      const data = await res.json();
      if (data.error) {
        setStatus(`${data.error} — Fix: ${data.fix}`);
      } else {
        setStatus(data.status === 'handshake_captured'
          ? `✅ Handshake capturado: ${data.capture_file}`
          : '⚠️ No se capturó handshake. Intenta cuando haya clientes conectados.');
      }
      loadCaptures();
    } catch (e: any) {
      setStatus(`Error: ${e.message}`);
    } finally {
      setCapturing(null);
      setTimeout(() => setStatus(null), 8000);
    }
  };

  const crackWiFi = async (bssid: string) => {
    setStatus('Crackeando... (puede tardar minutos)');
    try {
      const res = await fetch(`/api/wifi/crack/${encodeURIComponent(bssid)}`, { method: 'POST' });
      const data = await res.json();
      setCrackResult(data);
      setStatus(null);
    } catch (e: any) {
      setStatus(`Error: ${e.message}`);
    }
  };

  const loadCaptures = async () => {
    try {
      const res = await fetch('/api/wifi/captures');
      const data = await res.json();
      setCaptures(data.captures || []);
    } catch {}
  };

  const deleteCapture = async (filename: string) => {
    try {
      await fetch(`/api/wifi/captures/${filename}`, { method: 'DELETE' });
      loadCaptures();
    } catch {}
  };

  useEffect(() => { loadCaptures(); }, []);

  const signalColor = (signal: number) => {
    if (signal > -50) return 'text-green-400 bg-green-500/20';
    if (signal > -70) return 'text-amber-400 bg-amber-500/20';
    return 'text-red-400 bg-red-500/20';
  };

  return (
    <div className="bg-[var(--ss-bg-2)] border border-[var(--ss-border)] rounded-lg p-3 h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs uppercase tracking-widest text-green-400 flex items-center gap-2">
          <Wifi size={14} /> WiFi Scanner
        </h3>
        <button
          onClick={scanWiFi}
          disabled={scanning}
          className="px-3 py-1 text-[10px] border border-green-500/30 text-green-300 rounded hover:bg-green-500/10 disabled:opacity-50 transition font-mono flex items-center gap-1"
        >
          <Radio size={12} /> {scanning ? 'Escaneando...' : 'Escanear'}
        </button>
      </div>

      {status && (
        <div className="mb-2 text-[10px] text-green-300 font-mono bg-green-500/10 border border-green-500/20 rounded p-1.5">
          {status}
        </div>
      )}

      {method && method !== 'none' && networks.length > 0 && (
        <div className="mb-2 text-[9px] text-gray-500 font-mono">Método: {method}</div>
      )}

      <div className="flex-1 overflow-y-auto space-y-1.5 min-h-0">
        {networks.map((net, i) => (
          <div key={i} className="bg-[var(--ss-bg-3)] rounded p-2 border border-[var(--ss-border)]">
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-2 min-w-0">
                {net.encryption?.includes('Open') || net.encryption === 'Open'
                  ? <Unlock size={12} className="text-green-400 shrink-0" />
                  : <Lock size={12} className="text-red-400 shrink-0" />}
                <span className="font-mono text-xs text-gray-200 truncate">{net.ssid || 'Hidden'}</span>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <span className="text-[8px] px-1.5 py-0.5 rounded bg-[var(--ss-border)] text-gray-400 font-mono">Ch {net.channel}</span>
                <span className={`text-[8px] px-1.5 py-0.5 rounded font-mono ${signalColor(net.signal)}`}>{net.signal}dBm</span>
              </div>
            </div>

            <div className="flex items-center justify-between text-[9px] text-gray-500 font-mono mb-1.5">
              <span>{net.bssid}</span>
              <span>{net.encryption || 'Unknown'}</span>
            </div>

            {!(net.encryption?.includes('Open') || net.encryption === 'Open') && (
              <div className="flex gap-1">
                <button
                  onClick={() => captureHandshake(net)}
                  disabled={capturing === net.bssid}
                  className="flex-1 px-2 py-1 text-[9px] border border-amber-500/30 text-amber-300 rounded hover:bg-amber-500/10 disabled:opacity-50 transition font-mono flex items-center justify-center gap-1"
                >
                  <Play size={9} /> {capturing === net.bssid ? 'Capturando...' : 'Handshake'}
                </button>
                <button
                  onClick={() => crackWiFi(net.bssid)}
                  className="px-2 py-1 text-[9px] border border-red-500/30 text-red-300 rounded hover:bg-red-500/10 transition font-mono flex items-center gap-1"
                >
                  <Key size={9} /> Crack
                </button>
              </div>
            )}
          </div>
        ))}

        {networks.length === 0 && !scanning && (
          <div className="text-gray-500 text-xs text-center py-4 font-mono flex flex-col items-center gap-2">
            <AlertCircle size={16} className="opacity-50" />
            <span>Presiona Escanear para detectar redes WiFi.</span>
            <span className="text-[9px] text-gray-600 max-w-xs text-center">
              Termux: requiere termux-api + permisos de ubicación. Kali: iw o airodump-ng (root + modo monitor).
            </span>
          </div>
        )}
      </div>

      {/* Capturas */}
      {captures.length > 0 && (
        <div className="mt-2 pt-2 border-t border-[var(--ss-border)]">
          <h4 className="text-[10px] font-bold text-gray-500 mb-1 uppercase tracking-widest">Capturas ({captures.length})</h4>
          <div className="space-y-0.5 max-h-20 overflow-y-auto">
            {captures.map((cap, i) => (
              <div key={i} className="flex items-center justify-between bg-[var(--ss-bg-3)] rounded p-1.5 text-[9px] border border-[var(--ss-border)]">
                <span className="font-mono text-gray-400 truncate max-w-[150px]">{cap.file}</span>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-gray-600">{(cap.size / 1024).toFixed(1)}KB</span>
                  <button onClick={() => deleteCapture(cap.file)} className="text-red-400 hover:text-red-300">
                    <Trash2 size={10} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Resultado de crackeo */}
      {crackResult && (
        <div className={`mt-2 p-2 rounded border ${
          crackResult.status === 'cracked'
            ? 'bg-green-500/10 border-green-500/30'
            : 'bg-red-500/10 border-red-500/30'
        }`}>
          <div className="text-[10px] font-bold mb-1 font-mono">
            {crackResult.status === 'cracked' ? (
              <span className="text-green-400 flex items-center gap-1"><Key size={11} /> KEY CRACKEADA</span>
            ) : (
              <span className="text-red-400">Crackeo fallido</span>
            )}
          </div>
          {crackResult.key && (
            <div className="font-mono text-sm text-white bg-black/50 rounded p-2 text-center tracking-widest">
              {crackResult.key}
            </div>
          )}
          {crackResult.reason && <div className="text-[9px] text-gray-400 mt-1">{crackResult.reason}</div>}
          {crackResult.message && <div className="text-[9px] text-amber-400 mt-1">{crackResult.message}</div>}
        </div>
      )}
    </div>
  );
}
