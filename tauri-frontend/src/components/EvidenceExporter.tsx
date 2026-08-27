import React, { useState } from 'react';

export const EvidenceExporter: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [loadingAction, setLoadingAction] = useState<string | null>(null);
  const [status, setStatus] = useState<{ message: string; type: 'info' | 'success' | 'error' } | null>(null);
  const [lastHash, setLastHash] = useState<string | null>(null);

  const download = async (url: string, filename: string, actionId: string) => {
    setLoading(true);
    setLoadingAction(actionId);
    setStatus({ message: `Descargando ${filename}...`, type: 'info' });
    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`Error ${response.status}`);
      const blob = await response.blob();
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(link.href);

      const hash = response.headers.get('X-Evidence-Hash');
      if (hash) {
        setLastHash(hash);
        setStatus({
          message: `Descargado. Hash: ${hash.slice(0, 16)}... (verifica en blockchain)`,
          type: 'success'
        });
      } else {
        setStatus({ message: 'Descarga completada', type: 'success' });
      }
    } catch (err: any) {
      setStatus({ message: `Error: ${err.message}`, type: 'error' });
    } finally {
      setLoading(false);
      setLoadingAction(null);
      setTimeout(() => setStatus(null), 10000);
    }
  };

  const verifyHash = async (hash: string) => {
    setLoading(true);
    setLoadingAction('verify');
    try {
      const res = await fetch(`/api/export/verify/${hash}`);
      const data = await res.json();
      if (data.verified) {
        setStatus({ message: `Hash verificado en blockchain: ${data.data?.tx || 'confirmado'}`, type: 'success' });
      } else {
        setStatus({ message: data.message || 'No verificado', type: 'error' });
      }
    } catch (err: any) {
      setStatus({ message: `Error al verificar: ${err.message}`, type: 'error' });
    } finally {
      setLoading(false);
      setLoadingAction(null);
      setTimeout(() => setStatus(null), 8000);
    }
  };

  const processPending = async () => {
    setLoading(true);
    setLoadingAction('pending');
    try {
      const res = await fetch('/api/export/process-pending', { method: 'POST' });
      const data = await res.json();
      if (data.status === 'no_pending') {
        setStatus({ message: 'No hay sellos pendientes', type: 'info' });
      } else {
        setStatus({
          message: `Sellos pendientes: ${data.processed} procesados, ${data.still_pending} aun pendientes.`,
          type: 'info'
        });
      }
    } catch (err: any) {
      setStatus({ message: `Error: ${err.message}`, type: 'error' });
    } finally {
      setLoading(false);
      setLoadingAction(null);
      setTimeout(() => setStatus(null), 8000);
    }
  };

  const buttons = [
    { id: 'json', icon: 'DOC', label: 'JSON sellado', desc: 'Hash + blockchain', url: '/api/export/sealed-json', color: 'cyan' },
    { id: 'csv', icon: 'CSV', label: 'CSV + Hash', desc: 'Datos tabulares', url: '/api/export/sealed-csv', color: 'cyan' },
    { id: 'pdf', icon: 'PDF', label: 'PDF con QR', desc: 'Evidencia fisica', url: '/api/export/paper-evidence', color: 'amber' },
  ];

  return (
    <div className="bg-[var(--ss-bg-2)] rounded-lg p-4 border border-[var(--ss-border)]">
      <div className="flex items-center gap-2 mb-2">
        <h3 className="text-xs uppercase tracking-widest text-cyan-400 font-mono">Evidencia Blindada</h3>
        <span className="text-[9px] text-gray-600">SHA-256 + Blockchain + QR</span>
      </div>
      <p className="text-[10px] text-gray-500 mb-3 font-mono">
        Descarga datos con sello criptografico. Cada archivo incluye hash SHA-256 para verificar integridad.
      </p>

      <div className="grid grid-cols-3 gap-2">
        {buttons.map(btn => (
          <button
            key={btn.id}
            onClick={() => download(btn.url, `${btn.id}_${Date.now()}`, btn.id)}
            disabled={loading}
            className={`p-3 rounded border transition font-mono disabled:opacity-50
              ${btn.color === 'amber'
                ? 'bg-amber-500/10 border-amber-500/30 text-amber-300 hover:bg-amber-500/20 hover:border-amber-400'
                : 'bg-[var(--ss-bg-3)] border-cyan-500/30 text-cyan-300 hover:bg-cyan-500/10 hover:border-cyan-400'
              }`}
          >
            <div className="text-xs font-bold mb-1">{btn.icon}</div>
            <div className="text-[10px]">{btn.label}</div>
            <div className="text-[8px] text-gray-500 mt-0.5">{btn.desc}</div>
            {loadingAction === btn.id && <div className="text-[8px] text-cyan-400 animate-pulse mt-1">...</div>}
          </button>
        ))}
      </div>

      {lastHash && (
        <div className="mt-3 flex items-center gap-2 p-2 bg-[var(--ss-bg-3)] rounded border border-[var(--ss-border)]">
          <span className="text-[9px] text-gray-500 truncate font-mono">SHA-256: {lastHash}</span>
          <button
            onClick={() => verifyHash(lastHash)}
            disabled={loading}
            className="px-2 py-1 text-[9px] border border-cyan-500/30 text-cyan-300 rounded hover:bg-cyan-500/10 transition font-mono"
          >
            {loadingAction === 'verify' ? '...' : 'Verificar'}
          </button>
        </div>
      )}

      {status && (
        <div className={`mt-3 p-2 rounded text-[10px] font-mono border ${
          status.type === 'error' ? 'bg-red-500/10 border-red-500/30 text-red-300' :
          status.type === 'success' ? 'bg-green-500/10 border-green-500/30 text-green-300' :
          'bg-cyan-500/10 border-cyan-500/30 text-cyan-300'
        }`}>
          {status.message}
        </div>
      )}

      <div className="mt-3 flex justify-between items-center border-t border-[var(--ss-border)] pt-2">
        <span className="text-[9px] text-gray-600 font-mono">
          Si no hay internet, sellos se guardan localmente
        </span>
        <button
          onClick={processPending}
          disabled={loading}
          className="px-2 py-1 text-[9px] border border-amber-500/30 text-amber-300 rounded hover:bg-amber-500/10 transition font-mono"
        >
          {loadingAction === 'pending' ? '...' : 'Procesar pendientes'}
        </button>
      </div>
    </div>
  );
};
