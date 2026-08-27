import React, { useState, useEffect, useMemo } from "react";
import {
  Search, Filter, Shield, ShieldAlert, ShieldCheck, Wifi, Server,
  Activity, Download, Eye, ChevronDown, ChevronUp, Network
} from "lucide-react";

interface Host {
  id: number;
  ip: string;
  hostname: string;
  mac: string;
  os_guess: string;
  risk_score: number;
  first_seen: number;
  last_seen: number;
  ports: number[];
  tags: string[];
  metadata: Record<string, any>;
}

interface GraphNode {
  id: string;
  label: string;
  group: string;
  value: number;
  color: string;
  title?: string;
}

interface GraphEdge {
  from: string;
  to: string;
}

export default function TopologyPanel() {
  const [hosts, setHosts] = useState<Host[]>([]);
  const [graph, setGraph] = useState<{ nodes: GraphNode[]; edges: GraphEdge[] }>({ nodes: [], edges: [] });
  const [search, setSearch] = useState("");
  const [riskMin, setRiskMin] = useState(0);
  const [riskMax, setRiskMax] = useState(100);
  const [selectedTag, setSelectedTag] = useState("");
  const [expandedHost, setExpandedHost] = useState<number | null>(null);
  const [viewMode, setViewMode] = useState<"table" | "graph">("table");
  const [loading, setLoading] = useState(false);


  useEffect(() => {
    fetchHosts();
    fetchGraph();
  }, []);

  const fetchHosts = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/v2/topology/hosts?limit=2000");
      const data = await res.json();
      setHosts(data.hosts || []);
    } catch (e) {
      console.error("Failed to fetch hosts", e);
    }
    setLoading(false);
  };

  const fetchGraph = async () => {
    try {
      const res = await fetch("/api/v2/topology/graph");
      const data = await res.json();
      setGraph(data);
    } catch (e) {
      console.error("Failed to fetch graph", e);
    }
  };

  const filteredHosts = useMemo(() => {
    return hosts.filter((h) => {
      const matchSearch =
        !search ||
        h.ip.toLowerCase().includes(search.toLowerCase()) ||
        (h.hostname && h.hostname.toLowerCase().includes(search.toLowerCase())) ||
        (h.os_guess && h.os_guess.toLowerCase().includes(search.toLowerCase()));
      const matchRisk = h.risk_score >= riskMin && h.risk_score <= riskMax;
      const matchTag = !selectedTag || (h.tags && h.tags.includes(selectedTag));
      return matchSearch && matchRisk && matchTag;
    });
  }, [hosts, search, riskMin, riskMax, selectedTag]);

  const allTags = useMemo(() => {
    const tags = new Set<string>();
    hosts.forEach((h) => (h.tags || []).forEach((t) => tags.add(t)));
    return Array.from(tags);
  }, [hosts]);

  const riskColor = (score: number) => {
    if (score >= 70) return "text-red-500";
    if (score >= 40) return "text-amber-500";
    return "text-emerald-500";
  };

  const riskBg = (score: number) => {
    if (score >= 70) return "bg-red-500/10 border-red-500/30";
    if (score >= 40) return "bg-amber-500/10 border-amber-500/30";
    return "bg-emerald-500/10 border-emerald-500/30";
  };

  const exportCSV = () => {
    const headers = ["IP", "Hostname", "MAC", "OS", "Risk", "Ports", "Tags"];
    const rows = filteredHosts.map((h) => [
      h.ip,
      h.hostname || "",
      h.mac || "",
      h.os_guess || "",
      h.risk_score,
      (h.ports || []).join(";"),
      (h.tags || []).join(";"),
    ]);
    const csv = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `topology_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold flex items-center gap-2">
          <Network className="w-5 h-5 text-cyan-400" />
          Topología de Red
        </h2>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setViewMode("table")}
            className={`px-3 py-1.5 rounded text-sm font-medium transition ${
              viewMode === "table" ? "bg-cyan-500/20 text-cyan-300" : "text-slate-400 hover:text-white"
            }`}
          >
            Tabla
          </button>
          <button
            onClick={() => setViewMode("graph")}
            className={`px-3 py-1.5 rounded text-sm font-medium transition ${
              viewMode === "graph" ? "bg-cyan-500/20 text-cyan-300" : "text-slate-400 hover:text-white"
            }`}
          >
            Grafo
          </button>
          <button
            onClick={exportCSV}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-slate-700 hover:bg-slate-600 text-sm text-white transition"
          >
            <Download className="w-4 h-4" /> CSV
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-3">
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3">
          <div className="text-slate-400 text-xs uppercase tracking-wider">Hosts</div>
          <div className="text-2xl font-bold text-white">{hosts.length}</div>
        </div>
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3">
          <div className="text-slate-400 text-xs uppercase tracking-wider">Alto Riesgo</div>
          <div className="text-2xl font-bold text-red-400">
            {hosts.filter((h) => h.risk_score >= 70).length}
          </div>
        </div>
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3">
          <div className="text-slate-400 text-xs uppercase tracking-wider">Puertos Únicos</div>
          <div className="text-2xl font-bold text-cyan-400">
            {new Set(hosts.flatMap((h) => h.ports || [])).size}
          </div>
        </div>
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3">
          <div className="text-slate-400 text-xs uppercase tracking-wider">Filtrados</div>
          <div className="text-2xl font-bold text-emerald-400">{filteredHosts.length}</div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 flex-1 min-w-[200px]">
          <Search className="w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Buscar IP, hostname, OS..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-transparent text-sm text-white placeholder-slate-500 outline-none w-full"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <span className="text-xs text-slate-400">Riesgo:</span>
          <input
            type="range"
            min={0}
            max={100}
            value={riskMin}
            onChange={(e) => setRiskMin(Number(e.target.value))}
            className="w-20 accent-cyan-500"
          />
          <span className="text-xs text-slate-300 w-8">{riskMin}</span>
          <span className="text-slate-500">-</span>
          <input
            type="range"
            min={0}
            max={100}
            value={riskMax}
            onChange={(e) => setRiskMax(Number(e.target.value))}
            className="w-20 accent-cyan-500"
          />
          <span className="text-xs text-slate-300 w-8">{riskMax}</span>
        </div>
        {allTags.length > 0 && (
          <select
            value={selectedTag}
            onChange={(e) => setSelectedTag(e.target.value)}
            className="bg-slate-700 border border-slate-600 rounded px-2 py-1 text-xs text-white"
          >
            <option value="">Todos los tags</option>
            {allTags.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Content */}
      {viewMode === "table" ? (
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-900/50 text-slate-400 text-xs uppercase">
                <tr>
                  <th className="px-4 py-2 text-left">IP</th>
                  <th className="px-4 py-2 text-left">Hostname</th>
                  <th className="px-4 py-2 text-left">OS</th>
                  <th className="px-4 py-2 text-center">Riesgo</th>
                  <th className="px-4 py-2 text-center">Puertos</th>
                  <th className="px-4 py-2 text-center">Acción</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/50">
                {filteredHosts.map((host) => (
                  <React.Fragment key={host.id}>
                    <tr
                      className={`hover:bg-slate-700/30 transition cursor-pointer ${riskBg(host.risk_score)}`}
                      onClick={() => setExpandedHost(expandedHost === host.id ? null : host.id)}
                    >
                      <td className="px-4 py-2.5 font-mono text-cyan-300">{host.ip}</td>
                      <td className="px-4 py-2.5 text-slate-200">{host.hostname || "—"}</td>
                      <td className="px-4 py-2.5 text-slate-400 text-xs">{host.os_guess || "—"}</td>
                      <td className="px-4 py-2.5 text-center">
                        <span className={`font-bold ${riskColor(host.risk_score)}`}>
                          {host.risk_score}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-center">
                        <div className="flex flex-wrap justify-center gap-1">
                          {(host.ports || []).slice(0, 5).map((p) => (
                            <span key={p} className="px-1.5 py-0.5 bg-slate-700 rounded text-xs text-slate-300">
                              {p}
                            </span>
                          ))}
                          {(host.ports || []).length > 5 && (
                            <span className="text-xs text-slate-500">+{(host.ports || []).length - 5}</span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-2.5 text-center">
                        {expandedHost === host.id ? (
                          <ChevronUp className="w-4 h-4 text-slate-400 mx-auto" />
                        ) : (
                          <ChevronDown className="w-4 h-4 text-slate-400 mx-auto" />
                        )}
                      </td>
                    </tr>
                    {expandedHost === host.id && (
                      <tr>
                        <td colSpan={6} className="px-4 py-3 bg-slate-900/30">
                          <div className="grid grid-cols-2 gap-4 text-xs">
                            <div>
                              <span className="text-slate-500">MAC:</span>{" "}
                              <span className="font-mono text-slate-300">{host.mac || "—"}</span>
                            </div>
                            <div>
                              <span className="text-slate-500">Tags:</span>{" "}
                              {(host.tags || []).map((t) => (
                                <span key={t} className="inline-block px-1.5 py-0.5 bg-cyan-500/10 text-cyan-300 rounded mr-1">
                                  {t}
                                </span>
                              )) || "—"}
                            </div>
                            <div>
                              <span className="text-slate-500">First seen:</span>{" "}
                              {host.first_seen ? new Date(host.first_seen * 1000).toLocaleString() : "—"}
                            </div>
                            <div>
                              <span className="text-slate-500">Last seen:</span>{" "}
                              {host.last_seen ? new Date(host.last_seen * 1000).toLocaleString() : "—"}
                            </div>
                            <div className="col-span-2">
                              <span className="text-slate-500">All ports:</span>{" "}
                              <div className="flex flex-wrap gap-1 mt-1">
                                {(host.ports || []).map((p) => (
                                  <span key={p} className="px-2 py-0.5 bg-slate-700 rounded text-slate-300 font-mono">
                                    {p}
                                  </span>
                                ))}
                              </div>
                            </div>
                            {host.metadata && Object.keys(host.metadata).length > 0 && (
                              <div className="col-span-2">
                                <span className="text-slate-500">Metadata:</span>
                                <pre className="mt-1 p-2 bg-slate-800 rounded text-slate-300 overflow-x-auto">
                                  {JSON.stringify(host.metadata, null, 2)}
                                </pre>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
          {filteredHosts.length === 0 && !loading && (
            <div className="p-8 text-center text-slate-500 text-sm">No se encontraron hosts con los filtros aplicados.</div>
          )}
          {loading && (
            <div className="p-8 text-center text-slate-500 text-sm">Cargando...</div>
          )}
        </div>
      ) : (
        <GraphView nodes={graph.nodes} edges={graph.edges} />
      )}
    </div>
  );
}

// Sub-componente: Vista de grafo simplificada con SVG
function GraphView({ nodes, edges }: { nodes: GraphNode[]; edges: GraphEdge[] }) {
  const width = 800;
  const height = 500;

  // Layout simple: hosts en círculo, puertos alrededor
  const hostNodes = nodes.filter((n) => n.group === "host");
  const otherNodes = nodes.filter((n) => n.group !== "host");
  const radius = 180;
  const cx = width / 2;
  const cy = height / 2;

  const positioned = useMemo(() => {
    const map = new Map<string, { x: number; y: number }>();
    hostNodes.forEach((n, i) => {
      const angle = (i / Math.max(hostNodes.length, 1)) * Math.PI * 2 - Math.PI / 2;
      map.set(n.id, {
        x: cx + Math.cos(angle) * radius,
        y: cy + Math.sin(angle) * radius,
      });
    });
    otherNodes.forEach((n, i) => {
      const angle = (i / Math.max(otherNodes.length, 1)) * Math.PI * 2 - Math.PI / 2;
      map.set(n.id, {
        x: cx + Math.cos(angle) * (radius + 80),
        y: cy + Math.sin(angle) * (radius + 80),
      });
    });
    return map;
  }, [nodes]);

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 overflow-auto">
      <svg width={width} height={height} className="mx-auto">
        {edges.map((e, i) => {
          const a = positioned.get(e.from);
          const b = positioned.get(e.to);
          if (!a || !b) return null;
          return (
            <line
              key={i}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke="#475569"
              strokeWidth={1}
              opacity={0.6}
            />
          );
        })}
        {nodes.map((n) => {
          const pos = positioned.get(n.id);
          if (!pos) return null;
          const r = n.group === "host" ? 8 + n.value / 5 : 5;
          return (
            <g key={n.id}>
              <circle cx={pos.x} cy={pos.y} r={r} fill={n.color} stroke="#1e293b" strokeWidth={2} />
              <text
                x={pos.x}
                y={pos.y + r + 14}
                textAnchor="middle"
                fill="#94a3b8"
                fontSize={10}
                fontFamily="monospace"
              >
                {n.label}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="text-center text-xs text-slate-500 mt-2">
        {nodes.length} nodos · {edges.length} conexiones
      </div>
    </div>
  );
}
