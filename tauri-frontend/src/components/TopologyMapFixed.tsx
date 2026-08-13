import { useState, useMemo } from 'react';
import { Network, Filter, AlertCircle, Shield } from 'lucide-react';

interface Node {
  id: string;
  ip: string;
  label: string;
  risk: 'low' | 'medium' | 'high' | 'critical';
  risk_reasons?: string[];
  ports?: number[];
  type?: string;
  x?: number;
  y?: number;
}

export default function TopologyMapFixed({ nodes: rawNodes }: { nodes: Node[] }) {
  const [filterRisk, setFilterRisk] = useState<string>('all');
  const [filterType, setFilterType] = useState<string>('all');
  const [filterPort, setFilterPort] = useState<string>('');

  // NO recalcular riesgo. Respetar lo que manda el backend.
  const nodes = useMemo(() => {
    return rawNodes.filter(n => {
      if (filterRisk !== 'all' && n.risk !== filterRisk) return false;
      if (filterType !== 'all' && n.type !== filterType) return false;
      if (filterPort && !n.ports?.includes(parseInt(filterPort))) return false;
      return true;
    });
  }, [rawNodes, filterRisk, filterType, filterPort]);

  const riskColors = {
    low: '#22c55e',      // green-500
    medium: '#eab308',   // yellow-500
    high: '#f97316',     // orange-500
    critical: '#ef4444'  // red-500
  };

  const riskLabels = {
    low: 'Bajo',
    medium: 'Medio',
    high: 'Alto',
    critical: 'Crítico'
  };

  return (
    <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-3">
        <h3 className="text-lg font-bold text-slate-100 flex items-center gap-2">
          <Network size={18} className="text-cyan-400" />
          Topología de Red
        </h3>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">{nodes.length} nodos</span>
        </div>
      </div>

      {/* Filtros */}
      <div className="flex flex-wrap gap-2 mb-3">
        <div className="flex items-center gap-1 bg-slate-900 rounded-lg px-2 py-1 border border-slate-700">
          <Filter size={10} className="text-slate-500" />
          <select 
            value={filterRisk} 
            onChange={e => setFilterRisk(e.target.value)}
            className="bg-transparent text-xs text-slate-300 outline-none"
          >
            <option value="all">Todos los riesgos</option>
            <option value="critical">🔴 Crítico</option>
            <option value="high">🟠 Alto</option>
            <option value="medium">🟡 Medio</option>
            <option value="low">🟢 Bajo</option>
          </select>
        </div>

        <div className="flex items-center gap-1 bg-slate-900 rounded-lg px-2 py-1 border border-slate-700">
          <Shield size={10} className="text-slate-500" />
          <select 
            value={filterType} 
            onChange={e => setFilterType(e.target.value)}
            className="bg-transparent text-xs text-slate-300 outline-none"
          >
            <option value="all">Todos los tipos</option>
            <option value="camera">Cámara</option>
            <option value="router">Router</option>
            <option value="iot">IoT</option>
            <option value="server">Servidor</option>
          </select>
        </div>

        <input
          value={filterPort}
          onChange={e => setFilterPort(e.target.value)}
          placeholder="Filtrar por puerto..."
          className="bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 text-xs text-slate-300 w-32 font-mono"
        />
      </div>

      {/* Leyenda */}
      <div className="flex gap-3 mb-3 text-[10px]">
        {(Object.keys(riskColors) as Array<keyof typeof riskColors>).map(r => (
          <div key={r} className="flex items-center gap-1">
            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: riskColors[r] }} />
            <span className="text-slate-400">{riskLabels[r]}</span>
          </div>
        ))}
      </div>

      {/* Grafo SVG simplificado pero profesional */}
      <div className="flex-1 bg-slate-900/50 rounded-lg border border-slate-800 relative overflow-hidden">
        <svg className="w-full h-full" viewBox="0 0 800 400">
          {/* Conexiones */}
          {nodes.map((n, i) => {
            if (i === 0) return null;
            const prev = nodes[i-1];
            return (
              <line 
                key={`line-${i}`}
                x1={(prev.x || 50 + i * 30)} y1={(prev.y || 200)}
                x2={(n.x || 50 + (i+1) * 30)} y2={(n.y || 200)}
                stroke="#334155" strokeWidth="1"
              />
            );
          })}
          
          {/* Nodos */}
          {nodes.map((n, i) => {
            const x = n.x || 50 + (i % 10) * 75;
            const y = n.y || 50 + Math.floor(i / 10) * 80;
            const color = riskColors[n.risk] || '#64748b';
            
            return (
              <g key={n.id} transform={`translate(${x},${y})`}>
                <circle r="20" fill={color} fillOpacity="0.2" stroke={color} strokeWidth="2" />
                <text y="4" textAnchor="middle" fill="#e2e8f0" fontSize="10" fontFamily="monospace">
                  {n.ip.split('.').pop()}
                </text>
                {n.ports && n.ports.length > 0 && (
                  <g transform="translate(12, -12)">
                    <rect x="0" y="0" width="16" height="12" rx="2" fill="#1e293b" stroke={color} strokeWidth="0.5" />
                    <text x="8" y="9" textAnchor="middle" fill={color} fontSize="8" fontFamily="monospace">
                      {n.ports.length}
                    </text>
                  </g>
                )}
                {/* Tooltip hover */}
                <title>{`${n.ip}\nRiesgo: ${riskLabels[n.risk]}\nPuertos: ${n.ports?.join(', ') || 'Ninguno'}\n${n.risk_reasons?.join('\n') || ''}`}</title>
              </g>
            );
          })}
        </svg>

        {nodes.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-slate-600 text-sm">
            <AlertCircle size={16} className="mr-2" /> No hay nodos con los filtros aplicados
          </div>
        )}
      </div>
    </div>
  );
}
