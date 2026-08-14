import { useState, useEffect } from 'react';
import { Activity, Server, Wifi, Radio, Globe, Cpu, HardDrive, Thermometer, RefreshCw } from 'lucide-react';

const GATEWAY_URL = 'http://localhost:8080';

export default function ControlTower() {
  const [nodes, setNodes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [wsConnected, setWsConnected] = useState(false);

  const loadNodes = async () => {
    try {
      const res = await fetch(`${GATEWAY_URL}/nodes`);
      if (res.ok) {
        const data = await res.json();
        setNodes(data.nodes || []);
      }
    } catch (e) {
      console.error('Gateway offline:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadNodes();
    const interval = setInterval(loadNodes, 5000);
    return () => clearInterval(interval);
  }, []);

  const sendCommand = async (nodeId: string, action: string, payload: any = {}) => {
    // Enviar via WS o HTTP
    try {
      const res = await fetch(`${GATEWAY_URL}/nodes/${nodeId}/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, ...payload }),
      });
      return await res.json();
    } catch (e) {
      console.error('Command failed:', e);
    }
  };

  const statusColor = (status: string) => {
    switch (status) {
      case 'online': return 'text-green-400';
      case 'stale': return 'text-amber-400';
      case 'offline': return 'text-red-400';
      default: return 'text-slate-500';
    }
  };

  const typeIcon = (type: string) => {
    switch (type) {
      case 'termux': return <Server size={14} className="text-cyan-400" />;
      case 'replit': return <Globe size={14} className="text-purple-400" />;
      default: return <Activity size={14} className="text-slate-400" />;
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Radio size={18} className="text-cyan-400" />
            Control Tower
          </h2>
          <p className="text-xs text-slate-500">Mesh de nodos distribuidos — {nodes.length} nodos registrados</p>
        </div>
        <button onClick={loadNodes} className="p-2 hover:bg-slate-800 rounded-lg text-slate-400">
          <RefreshCw size={14} />
        </button>
      </div>

      {/* Grid de nodos */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {nodes.map((node) => (
          <div key={node.id} className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-3">
            {/* Node header */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {typeIcon(node.type)}
                <span className="text-sm font-bold text-white">{node.name || node.id}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className={`w-2 h-2 rounded-full ${node.status === 'online' ? 'bg-green-400 animate-pulse' : node.status === 'stale' ? 'bg-amber-400' : 'bg-red-400'}`} />
                <span className={`text-[10px] font-mono ${statusColor(node.status)}`}>{node.status}</span>
              </div>
            </div>

            {/* Node info */}
            <div className="text-[10px] text-slate-500 space-y-1">
              <div>ID: <span className="text-slate-300 font-mono">{node.id}</span></div>
              <div>Location: <span className="text-slate-300">{node.location || 'unknown'}</span></div>
              <div>Last HB: <span className="text-slate-300">{node.last_heartbeat?.slice(11, 19) || 'never'}</span></div>
            </div>

            {/* Capabilities */}
            {node.capabilities?.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {node.capabilities.map((cap: string) => (
                  <span key={cap} className="px-1.5 py-0.5 bg-slate-800 rounded text-[9px] text-slate-400 font-mono">{cap}</span>
                ))}
              </div>
            )}

            {/* Telemetry */}
            {node.telemetry && (
              <div className="grid grid-cols-3 gap-2 pt-2 border-t border-slate-800">
                <div className="text-center">
                  <Cpu size={10} className="text-cyan-400 mx-auto mb-0.5" />
                  <div className="text-[8px] text-slate-500">CPU</div>
                  <div className="text-[9px] text-slate-300 truncate">{node.telemetry.load_avg?.split(' ')[0] || 'n/a'}</div>
                </div>
                <div className="text-center">
                  <HardDrive size={10} className="text-purple-400 mx-auto mb-0.5" />
                  <div className="text-[8px] text-slate-500">DISK</div>
                  <div className="text-[9px] text-slate-300 truncate">{node.telemetry.disk?.split(/\s+/)[4] || 'n/a'}</div>
                </div>
                <div className="text-center">
                  <Wifi size={10} className="text-green-400 mx-auto mb-0.5" />
                  <div className="text-[8px] text-slate-500">NET</div>
                  <div className="text-[9px] text-slate-300">{node.status === 'online' ? 'OK' : 'DOWN'}</div>
                </div>
              </div>
            )}

            {/* Quick actions */}
            <div className="flex gap-1 pt-1">
              <button
                onClick={() => sendCommand(node.id, 'ping')}
                className="flex-1 px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded text-[9px] text-slate-300"
              >
                Ping
              </button>
              <button
                onClick={() => sendCommand(node.id, 'run_scan', { target: 'localhost' })}
                className="flex-1 px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded text-[9px] text-slate-300"
              >
                Scan
              </button>
              <button
                onClick={() => sendCommand(node.id, 'network_monitor')}
                className="flex-1 px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded text-[9px] text-slate-300"
              >
                Monitor
              </button>
            </div>
          </div>
        ))}

        {nodes.length === 0 && !loading && (
          <div className="col-span-full flex flex-col items-center justify-center h-48 text-slate-600">
            <Radio size={32} className="mb-2 opacity-50" />
            <p className="text-sm">Sin nodos registrados</p>
            <p className="text-xs mt-1">Ejecuta <code className="text-slate-400">python node_client.py</code> en un nodo</p>
          </div>
        )}

        {loading && (
          <div className="col-span-full flex items-center justify-center h-48 text-slate-600">
            <RefreshCw size={20} className="animate-spin" />
          </div>
        )}
      </div>
    </div>
  );
}
