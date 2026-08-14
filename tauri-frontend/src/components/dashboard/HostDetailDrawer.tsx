import { useScanStore } from '../../hooks/useScanStore';

export default function HostDetailDrawer({ onShodan }: { onShodan: (ip: string) => void }) {
  const selectedIp = useScanStore(s => s.selectedIp);
  const selectHost = useScanStore(s => s.selectHost);
  const host = useScanStore(s => s.hosts.find(h => h.ip === selectedIp));

  if (!host) return null;

  return (
    <div className="fixed right-0 top-0 h-full w-80 bg-[var(--ss-bg-2)] border-l border-cyan-500/30 ss-glow z-40 p-4 overflow-y-auto">
      <div className="flex justify-between items-center mb-3">
        <h3 className="text-sm text-cyan-300 font-bold">HOST {host.ip}</h3>
        <button onClick={() => selectHost(null)} className="text-gray-400 hover:text-white">✕</button>
      </div>
      <div className="space-y-3 text-xs">
        <div>
          <div className="text-gray-500 uppercase tracking-wider mb-1">Tipo</div>
          <div className="text-gray-200">{host.type} · {host.vendor || 'desconocido'}</div>
        </div>
        <div>
          <div className="text-gray-500 uppercase tracking-wider mb-1">MAC</div>
          <div className="font-mono text-gray-200">{host.mac || '—'}</div>
        </div>
        <div>
          <div className="text-gray-500 uppercase tracking-wider mb-1">Puertos abiertos</div>
          <ul className="space-y-1">
            {host.ports.map((p, i) => (
              <li key={i} className="font-mono text-gray-300 bg-black/30 px-2 py-1 border-l-2 border-cyan-500/50">
                {p.port} · {p.service}
                {p.banner && <span className="text-gray-500 ml-2">({p.banner.slice(0, 30)})</span>}
              </li>
            ))}
          </ul>
        </div>
        <div className="pt-3 border-t border-[var(--ss-border)] space-y-2">
          <button onClick={() => onShodan(host.ip)}
                  className="w-full px-3 py-2 border border-cyan-500/50 text-cyan-300 text-xs hover:bg-cyan-500/10 transition">
            🔍 Enriquecer con Shodan
          </button>
          <button onClick={() => alert('Sellando con SourceSeal...')}
                  className="w-full px-3 py-2 border border-amber-500/50 text-amber-300 text-xs hover:bg-amber-500/10 transition">
            🛡️ Sellar host con SourceSeal
          </button>
        </div>
      </div>
    </div>
  );
}
