import { useState, useEffect } from 'react';
import { Server, Globe, Cloud, Cpu, RefreshCw, Activity, Database, AlertTriangle } from 'lucide-react';

// URL del orquestador de federación — configurable via env o localhost:8080
const ORCHESTRATOR_URL = (import.meta as any).env?.VITE_ORCHESTRATOR_URL || 'http://127.0.0.1:8080';

export default function ControlTower() {
  const [nodes, setNodes] = useState<any[]>([]);
  const [health, setHealth] = useState<any>(null);
  const [syncLog, setSyncLog] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);

  const loadAll = async () => {
    try {
      const [nodesRes, healthRes, logRes] = await Promise.all([
        fetch(`${ORCHESTRATOR_URL}/nodes`),
        fetch(`${ORCHESTRATOR_URL}/health`),
        fetch(`${ORCHESTRATOR_URL}/sync/log?limit=10`),
      ]);
      if (nodesRes.ok) {
        const nd = await nodesRes.json();
        setNodes(nd.nodes || []);
      }
      if (healthRes.ok) setHealth(await healthRes.json());
      if (logRes.ok) {
        const lg = await logRes.json();
        setSyncLog(lg.logs || []);
      }
      setOffline(false);
    } catch (e) {
      setOffline(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
    const interval = setInterval(loadAll, 5000);
    return () => clearInterval(interval);
  }, []);

  const execTool = async (tool: string, args: string[] = []) => {
    try {
      const res = await fetch(`${ORCHESTRATOR_URL}/core/exec`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool, args, timeout: 60 }),
      });
      return await res.json();
    } catch (e) {
      console.error('Exec failed:', e);
    }
  };

  const syncNode = async (nodeId: string) => {
    try {
      await fetch(`${ORCHESTRATOR_URL}/sync/${nodeId}`, { method: 'POST' });
      loadAll();
    } catch (e) {
      console.error('Sync failed:', e);
    }
  };

  const statusColor = (status: string) => {
    switch (status) {
      case 'online': return 'text-green-400';
      case 'offline': return 'text-red-400';
      case 'stale': return 'text-amber-400';
      default: return 'text-slate-500';
    }
  };

  const nodeIcon = (nodeId: string) => {
    if (nodeId === 'frontend') return <Globe size={14} className="text-cyan-400" />;
    if (nodeId === 'threat_intel') return <Activity size={14} className="text-rose-400" />;
    return <Server size={14} className="text-slate-400" />;
  };

  // Estado: Orquestador offline
  if (offline && !loading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <Cloud size={18} className="text-cyan-400" />
              Control Tower
            </h2>
            <p className="text-xs text-slate-500">Federación de nodos</p>
          </div>
          <button onClick={loadAll} className="p-2 hover:bg-slate-800 rounded-lg text-slate-400">
            <RefreshCw size={14} />
          </button>
        </div>

        <div className="bg-slate-900/60 border border-amber-800/40 rounded-xl p-6 text-center">
          <AlertTriangle size={32} className="text-amber-500/60 mx-auto mb-3" />
          <h3 className="text-sm font-bold text-amber-400 mb-1">Orquestador no detectado</h3>
          <p className="text-xs text-slate-500 mb-4">
            El orquestador de federación no está corriendo en <span className="font-mono text-slate-300">{ORCHESTRATOR_URL}</span>
          </p>

          <div className="bg-slate-950/50 border border-slate-800 rounded-lg p-3 text-left max-w-md mx-auto">
            <p className="text-[10px] text-slate-400 mb-2 font-bold uppercase">Para iniciarlo en Termux:</p>
            <pre className="text-[10px] text-slate-300 font-mono whitespace-pre-wrap">
{`# Gateway Mesh separado para federar nodos
cd ~/Red-team-tauri
PORT=8080 python3 gateway/mesh_server.py &

# O usando el script:
bash gateway/start_gateway.sh &

# Verificar que responde
curl http://localhost:8080/health`}
            </pre>
          </div>

          <p className="text-[10px] text-slate-600 mt-4">
            Mientras tanto, todos los módulos del dashboard funcionan localmente sin federación.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Cloud size={18} className="text-cyan-400" />
            Control Tower
          </h2>
          <p className="text-xs text-slate-500">
            {health ? `${health.replit_nodes_online}/${health.replit_nodes_total} Replits online` : 'Conectando...'}
            {health?.tunnel && (
              <span className="ml-2 text-cyan-400">· {health.tunnel}</span>
            )}
          </p>
        </div>
        <button onClick={loadAll} className="p-2 hover:bg-slate-800 rounded-lg text-slate-400">
          <RefreshCw size={14} />
        </button>
      </div>

      {/* Master node status */}
      {health && (
        <div className="bg-slate-900/60 border border-cyan-800/50 rounded-xl p-4 flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-green-400 animate-pulse" />
            <span className="text-sm font-bold text-white">Termux Maestro</span>
          </div>
          <div className="flex gap-4 text-[10px] text-slate-400">
            <span>Role: <span className="text-cyan-400 font-mono">{health.role}</span></span>
            <span>DB: <span className="text-slate-300 font-mono">{health.db_path}</span></span>
          </div>
        </div>
      )}

      {/* Replit nodes */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {nodes.map((node) => (
          <div key={node.node_id} className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {nodeIcon(node.node_id)}
                <span className="text-sm font-bold text-white">{node.service || node.node_id}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className={`w-2 h-2 rounded-full ${node.status === 'online' ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`} />
                <span className={`text-[10px] font-mono ${statusColor(node.status)}`}>{node.status}</span>
              </div>
            </div>

            <div className="text-[10px] text-slate-500 space-y-1">
              <div>URL: <span className="text-slate-300 font-mono truncate block max-w-[200px]">{node.url}</span></div>
              {node.response_time_ms && (
                <div>Latencia: <span className="text-slate-300">{node.response_time_ms}ms</span></div>
              )}
              <div>Last check: <span className="text-slate-300">{node.last_check?.slice(11, 19) || 'never'}</span></div>
            </div>

            <button
              onClick={() => syncNode(node.node_id)}
              className="w-full px-2 py-1.5 bg-slate-800 hover:bg-slate-700 rounded text-[10px] text-slate-300 flex items-center justify-center gap-1"
            >
              <Database size={10} /> Sync DB
            </button>
          </div>
        ))}
      </div>

      {/* Core Services */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
        <h4 className="text-xs font-bold text-white mb-3 flex items-center gap-2">
          <Cpu size={12} className="text-cyan-400" /> Core Services (Termux)
        </h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {[
            { tool: 'nmap', label: 'Nmap Scan', args: ['-sV', '-p', '1-1000', 'localhost'] },
            { tool: 'tcpdump', label: 'TCP Dump', args: ['-c', '10'] },
            { tool: 'ffmpeg', label: 'FFmpeg', args: ['-version'] },
            { tool: 'airodump-ng', label: 'WiFi Scan', args: [] },
          ].map(svc => (
            <button
              key={svc.tool}
              onClick={() => execTool(svc.tool, svc.args)}
              className="px-3 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-[10px] text-slate-300 text-left"
            >
              <div className="font-bold">{svc.label}</div>
              <div className="text-[8px] text-slate-500 font-mono">{svc.tool}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Sync log */}
      {syncLog.length > 0 && (
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
          <h4 className="text-xs font-bold text-white mb-3">Sync Log</h4>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {syncLog.map((log, i) => (
              <div key={i} className="flex items-center gap-2 text-[10px] font-mono">
                <span className="text-slate-600">{log.timestamp?.slice(11, 19)}</span>
                <span className="text-slate-400">{log.node_id}</span>
                <span className="text-cyan-400">{log.action}</span>
                <span className={log.status === 'success' ? 'text-green-400' : 'text-red-400'}>{log.status}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {loading && (
        <div className="flex items-center justify-center h-32 text-slate-600">
          <RefreshCw size={20} className="animate-spin" />
        </div>
      )}
    </div>
  );
}
