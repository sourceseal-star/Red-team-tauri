import { useScanStore } from '../../hooks/useScanStore';

export default function RiskPanel() {
  const hosts = useScanStore(s => s.hosts);
  const counts = {
    critical: hosts.filter(h => h.risk === 'critical').length,
    high: hosts.filter(h => h.risk === 'high').length,
    medium: hosts.filter(h => h.risk === 'medium').length,
    low: hosts.filter(h => h.risk === 'low').length,
  };
  const total = hosts.length || 1;
  const score = Math.round(
    ((counts.critical * 10 + counts.high * 5 + counts.medium * 2) / (total * 10)) * 100
  );

  const items = [
    { label: 'CRÍTICO', color: 'var(--ss-red)', n: counts.critical },
    { label: 'ALTO',    color: '#ff8c42',      n: counts.high },
    { label: 'MEDIO',   color: 'var(--ss-amber)', n: counts.medium },
    { label: 'BAJO',    color: 'var(--ss-green)', n: counts.low },
  ];

  return (
    <div className="bg-[var(--ss-bg-2)] border border-[var(--ss-border)] p-4 ss-glow">
      <div className="flex items-baseline justify-between mb-2">
        <h3 className="text-xs uppercase tracking-widest text-amber-400">Score de Riesgo</h3>
        <span className="text-2xl font-bold text-cyan-300">{score}%</span>
      </div>
      <div className="h-1.5 bg-gray-800 mb-3 overflow-hidden">
        <div className="h-full bg-gradient-to-r from-green-400 via-amber-400 to-red-500"
             style={{ width: `${score}%` }} />
      </div>
      <div className="grid grid-cols-4 gap-2">
        {items.map(it => (
          <div key={it.label} className="text-center">
            <div className="text-lg font-bold" style={{ color: it.color }}>{it.n}</div>
            <div className="text-[9px] text-gray-400 tracking-widest">{it.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
