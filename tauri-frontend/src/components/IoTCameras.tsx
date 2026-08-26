import React, { useState, useEffect } from "react";
import {
  Camera, RefreshCw, ShieldAlert, ShieldCheck, Key, Eye,
  Download, Loader2, Wifi, Lock, Unlock
} from "lucide-react";
import { getApiKey } from "../lib/api";

interface CameraData {
  id: number;
  ip: string;
  port: number;
  vendor: string;
  model: string;
  snapshot_url: string;
  credentials_tested: number;
  credentials_found: Array<{ user: string; pass: string; status: number }>;
  last_seen: number;
}

function authHeaders(): Record<string, string> {
  const key = getApiKey();
  return key ? { Authorization: `Bearer ${key}` } : {};
}

export default function IoTCameras() {
  const [cameras, setCameras] = useState<CameraData[]>([]);
  const [loading, setLoading] = useState(false);
  const [brutingId, setBrutingId] = useState<number | null>(null);
  const [snapshotUrls, setSnapshotUrls] = useState<Record<number, string>>({});

  useEffect(() => {
    fetchCameras();
  }, []);

  const fetchCameras = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/enhanced/cameras", { headers: authHeaders() });
      const data = await res.json();
      setCameras(data.cameras || []);
    } catch (e) {
      console.error("Failed to fetch cameras", e);
    }
    setLoading(false);
  };

  const loadSnapshot = async (cam: CameraData) => {
    try {
      const res = await fetch(`/api/iot/snapshot?ip=${cam.ip}&port=${cam.port || 80}`, { headers: authHeaders() });
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        setSnapshotUrls((prev) => ({ ...prev, [cam.id]: url }));
      }
    } catch (e) {
      console.error("Snapshot failed", e);
    }
  };

  const bruteForce = async (cam: CameraData) => {
    setBrutingId(cam.id);
    try {
      const res = await fetch(`/api/enhanced/discover/all`, {
        method: "POST",
        headers: authHeaders()
      });
      const data = await res.json();
      // Refresh camera list
      await fetchCameras();
    } catch (e) {
      console.error("Brute force failed", e);
    }
    setBrutingId(null);
  };

  const downloadSnapshot = (cam: CameraData) => {
    const url = snapshotUrls[cam.id];
    if (!url) return;
    const a = document.createElement("a");
    a.href = url;
    a.download = `snapshot_${cam.ip}_${Date.now()}.jpg`;
    a.click();
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold flex items-center gap-2">
          <Camera className="w-5 h-5 text-pink-400" />
          Cámaras IoT Descubiertas
        </h2>
        <button
          onClick={fetchCameras}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-slate-700 hover:bg-slate-600 text-sm text-white transition"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          Actualizar
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {cameras.map((cam) => {
          const hasCreds = cam.credentials_found && cam.credentials_found.length > 0;
          const snapUrl = snapshotUrls[cam.id];

          return (
            <div
              key={cam.id}
              className="bg-slate-800/60 border border-slate-700 rounded-lg overflow-hidden hover:border-slate-500 transition"
            >
              {/* Snapshot area */}
              <div className="relative h-48 bg-slate-900 flex items-center justify-center group">
                {snapUrl ? (
                  <img
                    src={snapUrl}
                    alt={`Snapshot ${cam.ip}`}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="text-slate-600 flex flex-col items-center gap-2">
                    <Camera className="w-10 h-10" />
                    <span className="text-xs">Sin snapshot</span>
                  </div>
                )}
                <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition">
                  <button
                    onClick={() => loadSnapshot(cam)}
                    className="p-1.5 rounded bg-slate-800/80 text-white hover:bg-cyan-600 transition"
                    title="Cargar snapshot"
                  >
                    <Eye className="w-4 h-4" />
                  </button>
                  {snapUrl && (
                    <button
                      onClick={() => downloadSnapshot(cam)}
                      className="p-1.5 rounded bg-slate-800/80 text-white hover:bg-emerald-600 transition"
                      title="Descargar"
                    >
                      <Download className="w-4 h-4" />
                    </button>
                  )}
                </div>
                <div className="absolute top-2 left-2">
                  <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                    hasCreds ? "bg-red-500/20 text-red-300" : "bg-slate-700/80 text-slate-300"
                  }`}>
                    {hasCreds ? "CREDS EXPUESTAS" : "SIN TESTEAR"}
                  </span>
                </div>
              </div>

              {/* Info */}
              <div className="p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-sm text-cyan-300">{cam.ip}:{cam.port}</span>
                  <span className="text-xs text-slate-500">
                    {cam.last_seen ? new Date(cam.last_seen * 1000).toLocaleDateString() : "—"}
                  </span>
                </div>
                <div className="text-xs text-slate-400">
                  {cam.vendor} {cam.model}
                </div>

                {/* Credentials */}
                {hasCreds ? (
                  <div className="bg-red-500/10 border border-red-500/20 rounded p-2 space-y-1">
                    <div className="flex items-center gap-1.5 text-red-300 text-xs font-bold">
                      <Unlock className="w-3.5 h-3.5" />
                      Credenciales encontradas:
                    </div>
                    {cam.credentials_found.map((c, i) => (
                      <div key={i} className="font-mono text-xs text-red-200">
                        {c.user} / {c.pass}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-xs text-slate-500">
                    Testeado: {cam.credentials_tested} combinaciones
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-2 pt-1">
                  <button
                    onClick={() => loadSnapshot(cam)}
                    disabled={!!snapUrl}
                    className="flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded bg-slate-700 hover:bg-slate-600 text-xs text-white transition disabled:opacity-50"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    {snapUrl ? "Snapshot OK" : "Snapshot"}
                  </button>
                  <button
                    onClick={() => bruteForce(cam)}
                    disabled={brutingId === cam.id || hasCreds}
                    className="flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded bg-slate-700 hover:bg-amber-600 text-xs text-white transition disabled:opacity-50"
                  >
                    {brutingId === cam.id ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Key className="w-3.5 h-3.5" />
                    )}
                    {hasCreds ? "Ya testeado" : "Test Creds"}
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {cameras.length === 0 && !loading && (
        <div className="text-center p-8 text-slate-500 text-sm">
          No se encontraron cámaras. Ejecuta un escaneo de red primero.
        </div>
      )}
    </div>
  );
}
