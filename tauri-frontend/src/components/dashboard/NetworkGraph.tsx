import { useMemo } from 'react';
import { useScanStore, Host } from '../../hooks/useScanStore';
import clsx from 'clsx';

const RISK_COLOR = {
  low: '#00ff88', medium: '#fbbf24', high: '#ff8c42', critical: '#ff3b5c',
};
const TYPE_ICON = { router: '📡', camera: '📹', iot: '🔌', unknown: '❓' };

export default function NetworkGraph() {
  const hosts = useScanStore(s => s.hosts);
  const selectedIp = useScanStore(s => s.selectedIp);
  const selectHost = useScanStore(s => s.selectHost);

  // Layout radial: router central, cámaras alrededor, IoT en anillo externo
  const nodes = useMemo(() => {
    const center = { x: 300, y: 200 };
    const routers = hosts.filter(h => h.type === 'router');
    const cams = hosts.filter(h => h.type === 'camera');
    const iot = hosts.filter(h => h.type !== 'router' && h.type !== 'camera');
    const place = (arr: Host[], radius: number) => arr.map((h, i) => {
      const a = (i / Math.max(arr.length, 1)) * Math.PI * 2 - Math.PI / 2;
      return { ...h, x: center.x + Math.cos(a) * radius, y: center.y + Math.sin(a) * radius };
    });
    return [
      ...place(routers, 0),
      ...place(cams, 120),
      ...place(iot, 180),
    ];
  }, [hosts]);

  if (hosts.length === 0) {
    return <div className="text-gray-500 text-xs p-4 text-center">Sin hosts — ejecuta un escaneo de topología</div>;
  }

  return (
    <div className="bg-[#08090d] border border-[var(--ss-border)] p-2 relative ss-hex-bg">
      <h3 className="text-[10px] uppercase tracking-widest text-amber-400 mb-1">Topología de Red</h3>
      <svg viewBox="0 0 600 400" className="w-full h-[340px]">
        {/* Líneas desde el router (primer nodo) al resto */}
        {nodes.slice(1).map((n, i) => (
          <line key={i} x1={300} y1={200} x2={n.x} y2={n.y}
                stroke="rgba(0,229,255,.2)" strokeWidth="1" strokeDasharray="3 3" />
        ))}
        {/* Nodos */}
        {nodes.map((n, i) => (
          <g key={i} className="cursor-pointer" onClick={() => selectHost(n.ip)}>
            <circle cx={n.x} cy={n.y} r={n.ip === selectedIp ? 22 : 16}
                    fill={RISK_COLOR[n.risk]} fillOpacity="0.15"
                    stroke={RISK_COLOR[n.risk]} strokeWidth={n.ip === selectedIp ? 2 : 1} />
            <text x={n.x} y={n.y + 4} textAnchor="middle" fontSize="12">{TYPE_ICON[n.type]}</text>
            <text x={n.x} y={n.y + 34} textAnchor="middle" fontSize="9" fill="#8ab">
              {n.ip.split('.').pop()}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}
