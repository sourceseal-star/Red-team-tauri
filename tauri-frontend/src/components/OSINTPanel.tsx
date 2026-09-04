import { useState } from 'react';
import { Globe, Search, Mail, Server, Clock, FileText } from 'lucide-react';

export default function OSINTPanel() {
  const [target, setTarget] = useState('');
  const [loading, setLoading] = useState<string | null>(null);
  const [subdomains, setSubdomains] = useState<any[]>([]);
  const [emails, setEmails] = useState<any[]>([]);
  const [whois, setWhois] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [status, setStatus] = useState<string | null>(null);

  const runOSINT = async (type: string) => {
    if (!target.trim()) return;
    setLoading(type);
    setStatus(null);
    try {
      if (type === 'subdomains') {
        setStatus('Consultando crt.sh + brute force...');
        const res = await fetch(`/api/osint/subdomains/${target}?brute=true`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setSubdomains(data.subdomains || []);
        setStatus(`${data.subdomains?.length || 0} subdominios encontrados${data.cached ? ' (cache)' : ''}`);
      } else if (type === 'emails') {
        setStatus('Buscando emails...');
        const res = await fetch(`/api/osint/emails/${target}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setEmails(data.emails || []);
        setStatus(`${data.emails?.length || 0} emails encontrados`);
      } else if (type === 'whois') {
        setStatus('Consultando WHOIS...');
        const res = await fetch(`/api/osint/whois/${target}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setWhois(data);
        setStatus('WHOIS obtenido');
      }

      const histRes = await fetch(`/api/osint/history/${target}`);
      const histData = await histRes.json();
      setHistory(histData.history || []);
    } catch (e: any) {
      setStatus(`Error: ${e.message}`);
    } finally {
      setLoading(null);
      setTimeout(() => setStatus(null), 6000);
    }
  };

  return (
    <div className="bg-[var(--ss-bg-2)] border border-[var(--ss-border)] rounded-lg p-3 h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs uppercase tracking-widest text-purple-400 flex items-center gap-2">
          <Globe size={14} /> OSINT Engine
        </h3>
      </div>

      <div className="flex gap-1.5 mb-3">
        <input
          type="text"
          value={target}
          onChange={e => setTarget(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && runOSINT('subdomains')}
          placeholder="ejemplo.com"
          className="flex-1 bg-[var(--ss-bg-3)] border border-[var(--ss-border)] rounded px-2 py-1.5 text-xs text-gray-200 font-mono focus:border-purple-500 focus:outline-none"
        />
        <button
          onClick={() => runOSINT('subdomains')}
          disabled={loading === 'subdomains' || !target.trim()}
          className="px-2 py-1.5 text-[10px] border border-purple-500/30 text-purple-300 rounded hover:bg-purple-500/10 disabled:opacity-50 transition font-mono flex items-center gap-1"
        >
          <Server size={11} /> {loading === 'subdomains' ? '...' : 'Subs'}
        </button>
        <button
          onClick={() => runOSINT('emails')}
          disabled={loading === 'emails' || !target.trim()}
          className="px-2 py-1.5 text-[10px] border border-amber-500/30 text-amber-300 rounded hover:bg-amber-500/10 disabled:opacity-50 transition font-mono flex items-center gap-1"
        >
          <Mail size={11} /> {loading === 'emails' ? '...' : 'Emails'}
        </button>
        <button
          onClick={() => runOSINT('whois')}
          disabled={loading === 'whois' || !target.trim()}
          className="px-2 py-1.5 text-[10px] border border-cyan-500/30 text-cyan-300 rounded hover:bg-cyan-500/10 disabled:opacity-50 transition font-mono flex items-center gap-1"
        >
          <FileText size={11} /> {loading === 'whois' ? '...' : 'WHOIS'}
        </button>
      </div>

      {status && (
        <div className="mb-2 text-[10px] text-purple-300 font-mono bg-purple-500/10 border border-purple-500/20 rounded p-1.5">
          {status}
        </div>
      )}

      <div className="flex-1 overflow-y-auto space-y-3 min-h-0">
        {/* Subdominios */}
        {subdomains.length > 0 && (
          <div>
            <h4 className="text-[10px] font-bold text-purple-400 mb-1.5 flex items-center gap-1 uppercase tracking-widest">
              <Server size={10} /> Subdominios ({subdomains.length})
            </h4>
            <div className="space-y-1">
              {subdomains.slice(0, 30).map((s, i) => (
                <div key={i} className="flex items-center justify-between bg-[var(--ss-bg-3)] rounded p-1.5 text-[10px] border border-[var(--ss-border)]">
                  <span className="font-mono text-gray-300 truncate">{s.subdomain}</span>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {s.ip && <span className="text-cyan-400 font-mono">{s.ip}</span>}
                    <span className="text-[8px] px-1 py-0.5 rounded bg-[var(--ss-border)] text-gray-400">{s.source}</span>
                  </div>
                </div>
              ))}
              {subdomains.length > 30 && <div className="text-[9px] text-gray-500 text-center">+{subdomains.length - 30} más...</div>}
            </div>
          </div>
        )}

        {/* Emails */}
        {emails.length > 0 && (
          <div>
            <h4 className="text-[10px] font-bold text-amber-400 mb-1.5 flex items-center gap-1 uppercase tracking-widest">
              <Mail size={10} /> Emails ({emails.length})
            </h4>
            <div className="space-y-1">
              {emails.map((e, i) => (
                <div key={i} className="flex items-center justify-between bg-[var(--ss-bg-3)] rounded p-1.5 text-[10px] border border-[var(--ss-border)]">
                  <span className="font-mono text-gray-300">{e.email}</span>
                  <span className="text-[9px] text-gray-500">{e.source}{e.confidence && ` (${e.confidence}%)`}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* WHOIS */}
        {whois && (
          <div>
            <h4 className="text-[10px] font-bold text-cyan-400 mb-1.5 flex items-center gap-1 uppercase tracking-widest">
              <FileText size={10} /> WHOIS — {whois.domain}
            </h4>
            <div className="bg-[var(--ss-bg-3)] rounded p-2 text-[9px] font-mono text-gray-400 max-h-32 overflow-y-auto border border-[var(--ss-border)]">
              {whois.parsed && Object.entries(whois.parsed).slice(0, 20).map(([k, v]: [string, any]) => (
                <div key={k} className="mb-0.5">
                  <span className="text-gray-500">{k}:</span> <span className="text-gray-300">{v}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Historial */}
        {history.length > 0 && (
          <div>
            <h4 className="text-[10px] font-bold text-gray-500 mb-1.5 flex items-center gap-1 uppercase tracking-widest">
              <Clock size={10} /> Historial ({history.length})
            </h4>
            <div className="space-y-0.5">
              {history.slice(0, 5).map((h, i) => (
                <div key={i} className="text-[9px] text-gray-500 font-mono">
                  [{new Date(h.timestamp).toLocaleTimeString()}] {h.type}
                </div>
              ))}
            </div>
          </div>
        )}

        {!subdomains.length && !emails.length && !whois && !loading && (
          <div className="text-gray-500 text-xs text-center py-4 font-mono">
            Ingresa un dominio y selecciona una herramienta.
          </div>
        )}
      </div>
    </div>
  );
}
