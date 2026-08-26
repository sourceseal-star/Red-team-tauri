import React, { useState } from "react";
import { Download, FileJson, FileSpreadsheet, FileCode, FileText, Loader2 } from "lucide-react";
import { getApiKey, getBaseUrl } from "../lib/api";

export default function ExportPanel() {
  const [loading, setLoading] = useState<"json" | "csv" | "pcap" | "pdf" | null>(null);
  // Antes: hardcodeado a "http://localhost:8001" via window.__API__ (nunca
  // definida) -- rompia si el dashboard se abre por la IP de WiFi en vez de
  // localhost, y ademas NUNCA mandaba el header Authorization, asi que el
  // middleware de auth devolvia 401 en todos los exports. Usar la misma
  // base URL relativa + Bearer token que el resto de paneles (AlertsPanel,
  // IoTCameras, TopologyPanel).
  const API = getBaseUrl();

  const authHeaders = (): Record<string, string> => {
    const key = getApiKey();
    return key ? { Authorization: `Bearer ${key}` } : {};
  };

  const download = async (format: "json" | "csv" | "pcap") => {
    setLoading(format);
    try {
      const res = await fetch(`${API}/export/${format}`, { headers: authHeaders() });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.error || `Export failed (HTTP ${res.status})`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const ext = format === "pcap" ? "pcap" : format;
      a.download = `export_${format}_${new Date().toISOString().slice(0, 10)}.${ext}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert("Error al exportar: " + (e as Error).message);
    }
    setLoading(null);
  };

  const generateReport = async () => {
    setLoading("pdf");
    try {
      const res = await fetch(`${API}/reports/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ type: "executive" }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.error || `HTTP ${res.status}`);
      }
      const data = await res.json();
      if (data.report) {
        const blob = new Blob([JSON.stringify(data.report, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `report_executive_${new Date().toISOString().slice(0, 10)}.json`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch (e) {
      alert("Error al generar reporte: " + (e as Error).message);
    }
    setLoading(null);
  };

  const cards = [
    {
      format: "json" as const,
      icon: FileJson,
      title: "Exportar JSON",
      desc: "Todos los hosts, alertas y cámaras en formato JSON estructurado.",
      color: "text-cyan-400",
      bg: "bg-cyan-500/10 border-cyan-500/20",
    },
    {
      format: "csv" as const,
      icon: FileSpreadsheet,
      title: "Exportar CSV",
      desc: "Tabla de hosts compatible con Excel, LibreOffice, análisis forense.",
      color: "text-emerald-400",
      bg: "bg-emerald-500/10 border-emerald-500/20",
    },
    {
      format: "pcap" as const,
      icon: FileCode,
      title: "Exportar PCAP",
      desc: "Placeholder para captura de paquetes. En producción requiere scapy.",
      color: "text-amber-400",
      bg: "bg-amber-500/10 border-amber-500/20",
    },
  ];

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold flex items-center gap-2">
        <Download className="w-5 h-5 text-emerald-400" />
        Exportar Datos
      </h2>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {cards.map((c) => {
          const Icon = c.icon;
          const isLoading = loading === c.format;
          return (
            <button
              key={c.format}
              onClick={() => download(c.format)}
              disabled={!!loading}
              className={`text-left rounded-lg border p-4 transition hover:brightness-110 ${c.bg} disabled:opacity-50`}
            >
              <div className="flex items-center gap-2 mb-2">
                {isLoading ? (
                  <Loader2 className={`w-5 h-5 ${c.color} animate-spin`} />
                ) : (
                  <Icon className={`w-5 h-5 ${c.color}`} />
                )}
                <span className="font-bold text-slate-200">{c.title}</span>
              </div>
              <p className="text-xs text-slate-400">{c.desc}</p>
            </button>
          );
        })}
      </div>

      <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
        <h3 className="text-sm font-bold text-slate-300 mb-3 flex items-center gap-2">
          <FileText className="w-4 h-4 text-pink-400" />
          Generar Reporte Ejecutivo
        </h3>
        <p className="text-xs text-slate-500 mb-3">
          Genera un reporte consolidado con hosts, alertas, cámaras e IOCs detectados.
          Incluye resumen estadístico y timeline de eventos.
        </p>
        <button
          onClick={generateReport}
          disabled={!!loading}
          className="px-4 py-2 rounded bg-pink-600 hover:bg-pink-500 text-white text-sm font-medium transition disabled:opacity-50 flex items-center gap-2"
        >
          {loading === "pdf" ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <FileText className="w-4 h-4" />
          )}
          Generar Reporte
        </button>
      </div>
    </div>
  );
}
