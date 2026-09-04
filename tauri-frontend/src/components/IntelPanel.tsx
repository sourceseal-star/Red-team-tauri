import { useState } from 'react';
import { Globe, Shield, AlertTriangle } from 'lucide-react';
import { useScanStore } from '../hooks/useScanStore';

export default function IntelPanel() {
  const [ips, setIps] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const hosts = useScanStore(s => s.hosts);

  const scanReputation = async () => {
    setLoading(true);
    setStatus(null);

    // IPs públicas de los hosts escaneados
    const publicIps = hosts
      .map(h => h.ip)
      .filter(ip => !ip.startsWith('127.') && !ip.startsWith('192.168.') &&
                     !ip.startsWith('10.') && !ip.startsWith('172.'));

    if (publicIps.length === 0) {
      setStatus('No hay IPs públicas. Escanea la red primero.');
      setLoading(false);
      return;
    }

    try {
      const res = await fetch('/api/intel/bulk-check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(publicIps.slice(0, 20)),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setIps(data.results || []);
      setStatus(`${data.total} IPs verificadas · ${data.malicious} maliciosas`);
    } catch (e: any) {
      setStatus(`Error: ${e.message}`);
    } finally {
      setLoading(false);
      setTimeout(() => setStatus(null), 8000);
    }
  };

  const verdictColor = (v: string) => {
    if (v === 'MALICIOUS') return 'border-red-500/40 bg-red-500/10 text-red-300';
    if (v === 'SUSPICIOUS') return 'border-amber-500/40 bg-amber-500/10 text-amber-300';
    return 'border-green-500/40 bg-green-500/10 text-green-300';
  };

  return (
    <div className="bg-[var(--ss-bg-2)] border border-[var(--ss-border)] rounded-lg p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs uppercase tracking-widest text-cyan-400 flex items-center gap-2">
          <Globe size={14} /> Threat Intel
        </h3>
        <button
          onClick={scanReputation}
          disabled={loading}
          className="px-3 py-1 text-[10px] border border-cyan-500/30 text-cyan-300 rounded hover:bg-cyan-500/10 disabled:opacity-50 transition font-mono"
        >
          {loading ? 'Analizando...' : 'Verificar Reputación'}
        </button>
      </div>

      {status && (
        <div className="mb-2 text-[10px] text-cyan-300 font-mono bg-cyan-500/10 border border-cyan-500/20 rounded p-1.5">
          {status}
        </div>
      )}

      <div className="flex-1 overflow-y-auto space-y-1.5 min-h-0">
        {ips.map((ip: any, idx: number) => (
          <div key={idx} className={`p-2 rounded border ${verdictColor(ip.verdict || 'UNKNOWN')}`}>
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs">{ip.ip}</span>
              <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${
                ip.verdict === 'MALICIOUS' ? 'bg-red-500/30 text-red-200' :
                ip.verdict === 'SUSPICIOUS' ? 'bg-amber-500/30 text-amber-200' :
                'bg-green-500/30 text-green-200'
              }`}>{ip.verdict || 'UNKNOWN'}</span>
            </div>
            {ip.abuse_score > 0 && (
              <div className="mt-1 text-[9px] text-gray-400 font-mono">
                Score: {ip.abuse_score}/100 · Reports: {ip.total_reports} · {ip.isp || 'N/A'}
              </div>
            )}
            {ip.is_tor && <span className="text-[9px] text-purple-400 block mt-0.5">🧅 Nodo TOR</span>}
            {ip.error && <span className="text-[9px] text-red-400 block mt-0.5">{ip.error}</span>}
          </div>
        ))}
        {ips.length === 0 && !loading && (
          <div className="text-gray-500 text-xs text-center py-4 font-mono">
            Escanea la red y verifica reputación de IPs públicas.
          </div>
        )}
      </div>
    </div>
  );
}
