import React, { useState, useEffect, useRef } from "react";
import {
  Bell, AlertTriangle, AlertCircle, Info, CheckCircle2,
  X, Filter, RefreshCw, Clock, ShieldAlert
} from "lucide-react";
import { getApiKey, getBaseUrl } from '../lib/api';

interface Alert {
  id: number;
  severity: "critical" | "warning" | "info";
  title: string;
  message: string;
  source: string;
  timestamp: number;
  acknowledged: number;
  metadata: Record<string, any>;
}

const severityConfig = {
  critical: { icon: ShieldAlert, color: "text-red-400", bg: "bg-red-500/10 border-red-500/20", label: "CRÍTICO" },
  warning: { icon: AlertTriangle, color: "text-amber-400", bg: "bg-amber-500/10 border-amber-500/20", label: "ADVERTENCIA" },
  info: { icon: Info, color: "text-cyan-400", bg: "bg-cyan-500/10 border-cyan-500/20", label: "INFO" },
};

export default function AlertsPanel() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [filter, setFilter] = useState<"all" | "critical" | "warning" | "info">("all");
  const [connected, setConnected] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const eventSourceRef = useRef<EventSource | null>(null);
  // Antes: hardcodeado a "http://localhost:8001" -- rompia si el dashboard
  // se abre por la IP de WiFi (ej. http://192.168.1.50:8001) en vez de
  // localhost, porque "localhost" en el navegador del OTRO dispositivo no
  // apunta al telefono. Usar la misma base URL relativa que el resto de
  // paneles (getBaseUrl() = '/api', mismo origen siempre).
  const API = getBaseUrl();

  useEffect(() => {
    fetchAlerts();
    connectSSE();
    return () => {
      eventSourceRef.current?.close();
    };
  }, []);

  const fetchAlerts = async () => {
    try {
      const key = getApiKey();
      const res = await fetch(`${API}/alerts?limit=100`, {
        headers: key ? { 'Authorization': `Bearer ${key}` } : {}
      });
      const data = await res.json();
      setAlerts(data.alerts || []);
      setUnreadCount((data.alerts || []).filter((a: Alert) => !a.acknowledged).length);
    } catch (e) {
      console.error("Failed to fetch alerts", e);
    }
  };

  const connectSSE = () => {
    try {
      // EventSource nativo del navegador NO soporta headers custom (no hay
      // forma de mandar Authorization). El backend acepta el token por
      // query string SOLO para paths que terminan en /stream (ver
      // security_middleware en dashboard_server.py).
      const key = getApiKey();
      const url = `${API}/alerts/stream${key ? `?token=${encodeURIComponent(key)}` : ''}`;
      const es = new EventSource(url);
      eventSourceRef.current = es;

      es.onopen = () => setConnected(true);
      es.onerror = () => setConnected(false);

      es.onmessage = (event) => {
        try {
          const alert: Alert = JSON.parse(event.data);
          setAlerts((prev) => {
            if (prev.some((a) => a.id === alert.id)) return prev;
            return [alert, ...prev].slice(0, 200);
          });
          if (!alert.acknowledged) {
            setUnreadCount((c) => c + 1);
          }
        } catch (e) {
          // heartbeat
        }
      };
    } catch (e) {
      console.error("SSE failed", e);
    }
  };

  const filteredAlerts = alerts.filter((a) =>
    filter === "all" ? true : a.severity === filter
  );

  const acknowledge = async (id: number) => {
    // Backend no tiene PATCH, solo visual
    setAlerts((prev) =>
      prev.map((a) => (a.id === id ? { ...a, acknowledged: 1 } : a))
    );
    setUnreadCount((c) => Math.max(0, c - 1));
  };

  const clearAll = () => {
    setAlerts([]);
    setUnreadCount(0);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Bell className="w-5 h-5 text-amber-400" />
            Alertas en Tiempo Real
            {unreadCount > 0 && (
              <span className="px-2 py-0.5 rounded-full bg-red-500 text-white text-xs font-bold">
                {unreadCount}
              </span>
            )}
          </h2>
          <span
            className={`px-2 py-0.5 rounded text-xs font-medium ${
              connected
                ? "bg-emerald-500/20 text-emerald-300"
                : "bg-red-500/20 text-red-300"
            }`}
          >
            {connected ? "SSE Conectado" : "SSE Desconectado"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchAlerts}
            className="p-2 rounded bg-slate-700 hover:bg-slate-600 text-white transition"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <button
            onClick={clearAll}
            className="px-3 py-1.5 rounded bg-slate-700 hover:bg-red-600 text-xs text-white transition"
          >
            Limpiar
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        {(["all", "critical", "warning", "info"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1 rounded text-xs font-medium transition ${
              filter === f
                ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30"
                : "bg-slate-800 text-slate-400 border border-slate-700 hover:text-white"
            }`}
          >
            {f === "all" ? "Todas" : severityConfig[f].label}
            {f !== "all" && (
              <span className="ml-1.5 text-slate-500">
                {alerts.filter((a) => a.severity === f).length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Alerts list */}
      <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
        {filteredAlerts.map((alert) => {
          const cfg = severityConfig[alert.severity] || severityConfig.info;
          const Icon = cfg.icon;

          return (
            <div
              key={alert.id}
              className={`rounded-lg border p-3 transition hover:brightness-110 ${cfg.bg} ${
                alert.acknowledged ? "opacity-50" : ""
              }`}
            >
              <div className="flex items-start gap-3">
                <Icon className={`w-5 h-5 mt-0.5 ${cfg.color}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-bold ${cfg.color}`}>
                      {cfg.label}
                    </span>
                    <span className="text-xs text-slate-500">
                      {alert.source}
                    </span>
                    <span className="text-xs text-slate-600 ml-auto flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {new Date(alert.timestamp * 1000).toLocaleTimeString()}
                    </span>
                  </div>
                  <div className="text-sm font-medium text-slate-200 mt-0.5">
                    {alert.title}
                  </div>
                  {alert.message && (
                    <div className="text-xs text-slate-400 mt-1">{alert.message}</div>
                  )}
                  {alert.metadata && Object.keys(alert.metadata).length > 0 && (
                    <div className="mt-2 p-1.5 bg-slate-900/40 rounded text-xs font-mono text-slate-400 overflow-x-auto">
                      {JSON.stringify(alert.metadata)}
                    </div>
                  )}
                </div>
                {!alert.acknowledged && (
                  <button
                    onClick={() => acknowledge(alert.id)}
                    className="p-1 rounded hover:bg-slate-700/50 text-slate-500 hover:text-emerald-400 transition"
                    title="Acknowledge"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          );
        })}

        {filteredAlerts.length === 0 && (
          <div className="text-center p-8 text-slate-500 text-sm">
            No hay alertas {filter !== "all" ? `de tipo ${filter}` : ""}.
          </div>
        )}
      </div>
    </div>
  );
}
