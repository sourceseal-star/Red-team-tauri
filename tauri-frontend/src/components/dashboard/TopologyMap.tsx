// src/components/dashboard/TopologyMap.tsx
// Grafo interactivo de topología de red usando vis-network.
// Consume useScanStore (Zustand) vía useTopology — no hace fetch aparte.
// Doble-click en IP pública abre LeafletMap con geolocalización.
import { useEffect, useRef, useState } from 'react';
import { Network } from 'vis-network/standalone';
import { DataSet } from 'vis-data';
import { useTopology } from '../../hooks/useTopology';
import { useScanStore } from '../../hooks/useScanStore';
import { VisNode } from '../../types/topology';
import { LeafletMap } from '../LeafletMap';

export default function TopologyMap() {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);
  const { data, loading, error, refetch, selectHost } = useTopology();
  const [showMap, setShowMap] = useState(false);
  const [mapIp, setMapIp] = useState<string | null>(null);
  const selectedIp = useScanStore(s => s.selectedIp);
  const selectedHost = useScanStore(s => s.hosts.find(h => h.ip === selectedIp));

  // Inicializar o actualizar el grafo
  useEffect(() => {
    if (!containerRef.current || data.nodes.length === 0) return;

    if (networkRef.current) {
      networkRef.current.setData({
        nodes: new DataSet(data.nodes as any),
        edges: new DataSet(data.edges as any),
      });
      return;
    }

    const options = {
      layout: { improvedLayout: true, hierarchical: { enabled: false } },
      physics: {
        enabled: true,
        stabilization: { iterations: 100 },
        barnesHut: { gravitationalConstant: -3000, centralGravity: 0.3 },
      },
      interaction: {
        dragNodes: true,
        hover: true,
        zoomView: true,
        navigationButtons: false,
      },
      nodes: {
        font: {
          size: 14,
          face: 'JetBrains Mono, monospace',
          color: '#e8e8f0',
          strokeWidth: 2,
          strokeColor: '#08090d',
        },
        borderWidth: 2,
        shadow: { enabled: true, size: 5, color: 'rgba(0,229,255,0.15)' },
      },
      edges: {
        smooth: { type: 'continuous', roundness: 0.2 },
        font: { size: 10, align: 'middle', color: '#8a9ba8' },
        width: 2,
        color: { color: 'rgba(0,229,255,0.2)', highlight: '#00e5ff' },
      },
    };

    const network = new Network(
      containerRef.current,
      {
        nodes: new DataSet(data.nodes as any),
        edges: new DataSet(data.edges as any),
      },
      options as any,
    );

    // Click simple: seleccionar host (abre HostDetailDrawer)
    network.on('click', (params: any) => {
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0] as string;
        selectHost(nodeId);
        setShowMap(false);
      }
    });

    // Doble click: geolocalizar si es IP pública
    network.on('doubleClick', (params: any) => {
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0] as string;
        if (!nodeId.startsWith('192.168.') && !nodeId.startsWith('10.') && !nodeId.startsWith('172.')) {
          setMapIp(nodeId);
          setShowMap(true);
        }
      }
    });

    networkRef.current = network;

    return () => {
      if (networkRef.current) {
        networkRef.current.destroy();
        networkRef.current = null;
      }
    };
  }, [data, selectHost]);

  if (loading && data.nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-96 bg-[var(--ss-bg)] border border-[var(--ss-border)] rounded-lg">
        <div className="text-cyan-400 animate-pulse font-mono text-sm">
          🔍 Escaneando dispositivos en la red...
        </div>
      </div>
    );
  }

  if (error && data.nodes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-96 bg-[var(--ss-bg)] border border-red-500/30 rounded-lg space-y-3">
        <div className="text-red-400 font-mono text-sm">❌ {error}</div>
        <button onClick={refetch}
          className="px-4 py-2 border border-cyan-500/50 text-cyan-300 text-xs hover:bg-cyan-500/10 transition rounded">
          🔄 Reintentar
        </button>
      </div>
    );
  }

  if (data.nodes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-96 bg-[var(--ss-bg)] border border-[var(--ss-border)] rounded-lg space-y-3">
        <div className="text-gray-500 font-mono text-sm">📡 Sin dispositivos detectados</div>
        <button onClick={refetch}
          className="px-4 py-2 border border-cyan-500/50 text-cyan-300 text-xs hover:bg-cyan-500/10 transition rounded">
          🔄 Escanear ahora
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full w-full bg-[var(--ss-bg)] border border-[var(--ss-border)] rounded-lg overflow-hidden">
      {/* Barra superior SourceSeal */}
      <div className="flex justify-between items-center px-3 py-2 bg-[var(--ss-bg-2)] border-b border-[var(--ss-border)]">
        <span className="text-xs text-cyan-300 font-mono">
          🖥️ {data.nodes.length} dispositivos · {data.edges.length} conexiones
        </span>
        <div className="flex gap-2">
          {selectedHost && (
            <span className={`text-xs font-mono px-2 py-1 rounded ${
              selectedHost.risk === 'critical' ? 'bg-red-500/20 text-red-300' :
              selectedHost.risk === 'high' ? 'bg-orange-500/20 text-orange-300' :
              selectedHost.risk === 'medium' ? 'bg-amber-500/20 text-amber-300' :
              'bg-green-500/20 text-green-300'
            }`}>
              {selectedHost.risk.toUpperCase()}
            </span>
          )}
          <button onClick={refetch}
            className="px-3 py-1 text-xs bg-[var(--ss-bg-3)] hover:bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 rounded transition">
            🔄 Actualizar
          </button>
        </div>
      </div>

      {/* Grafo vis-network */}
      <div ref={containerRef} className="flex-1 w-full" style={{ minHeight: '400px', height: '60vh' }} />

      {/* Panel de detalles del nodo seleccionado */}
      {selectedHost && (
        <div className="px-4 py-3 bg-[var(--ss-bg-2)] border-t border-[var(--ss-border)] flex justify-between items-start">
          <div className="space-y-1">
            <h4 className="text-cyan-300 font-bold font-mono text-sm">{selectedHost.ip}</h4>
            <p className="text-gray-400 text-xs">Tipo: {selectedHost.type} · {selectedHost.vendor || 'desconocido'}</p>
            {selectedHost.ports.length > 0 && (
              <p className="text-gray-500 text-xs font-mono">
                Puertos: {selectedHost.ports.map(p => p.port).join(', ')}
              </p>
            )}
          </div>
          <div className="flex space-x-2">
            {selectedHost.ip && !selectedHost.ip.startsWith('192.168.') && !selectedHost.ip.startsWith('10.') && (
              <button onClick={() => { setMapIp(selectedHost.ip); setShowMap(!showMap); }}
                className="px-3 py-1 border border-green-500/50 text-green-300 text-xs hover:bg-green-500/10 transition rounded">
                {showMap ? 'Ocultar mapa' : '📍 Ubicación'}
              </button>
            )}
            <button onClick={() => selectHost(null)}
              className="px-3 py-1 border border-gray-600 text-gray-400 text-xs hover:bg-gray-700/30 transition rounded">
              ✕
            </button>
          </div>
        </div>
      )}

      {/* Mapa Leaflet (condicional) */}
      {showMap && mapIp && (
        <div className="p-3 bg-[var(--ss-bg)] border-t border-[var(--ss-border)]" style={{ height: '280px' }}>
          <LeafletMap ip={mapIp} />
        </div>
      )}
    </div>
  );
}
