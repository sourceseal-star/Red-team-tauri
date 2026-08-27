import React, { useEffect, useState } from 'react';
import { CameraViewer } from './CameraViewer';
import { CameraWithSnapshot, VideoSource } from '../types/camera';

// Transformar datos de /api/scan/cameras + /api/iot/video-urls a VideoSource[]
function getVideoSources(cam: CameraWithSnapshot): VideoSource[] {
  const sources: VideoSource[] = [];

  // Si ya tenemos sources de video-urls, usarlos
  if (cam.sources && cam.sources.length > 0) {
    for (const s of cam.sources) {
      if (s.type === 'mjpeg' && s.stream_url) {
        sources.push({ type: 'mjpeg', url: s.stream_url, stream_url: s.stream_url });
      }
      if (s.rtsp_url) {
        sources.push({ type: 'rtsp', url: s.rtsp_url, rtsp_url: s.rtsp_url });
      }
      if (s.type === 'snapshot' && s.available && s.snapshot_url) {
        sources.push({ type: 'snapshot', url: s.snapshot_url, snapshot_url: s.snapshot_url });
      }
    }
  }

  // Si no hay sources pero hay banner RTSP, asumir RTSP
  if (sources.length === 0 && cam.rtsp) {
    sources.push({ type: 'rtsp', url: `rtsp://${cam.ip}:554`, rtsp_url: `rtsp://${cam.ip}:554` });
  }

  return sources;
}

interface CameraGridProps {
  cameras: CameraWithSnapshot[];
  onRefresh?: () => void;
}

export default function CameraGrid({ cameras, onRefresh }: CameraGridProps) {
  const [enrichedCameras, setEnrichedCameras] = useState<CameraWithSnapshot[]>(cameras);

  // Enriquecer cámaras con video-urls
  useEffect(() => {
    if (!cameras || cameras.length === 0) {
      setEnrichedCameras([]);
      return;
    }

    let cancelled = false;
    (async () => {
      const enriched = await Promise.all(
        cameras.map(async (cam) => {
          try {
            // Probar puerto 80 primero, luego 8080, luego 8000
            const ports = cam.ports ? Object.keys(cam.ports).filter(p => cam.ports![p] !== null) : ['80'];
            const port = ports.find(p => ['80', '8080', '8000', '443'].includes(p)) || ports[0] || '80';
            const res = await fetch(`/api/iot/video-urls?ip=${cam.ip}&port=${port}`);
            if (!res.ok) return cam;
            const data = await res.json();
            return { ...cam, sources: data.video_sources || [] };
          } catch {
            return cam;
          }
        })
      );
      if (!cancelled) setEnrichedCameras(enriched);
    })();

    return () => { cancelled = true; };
  }, [cameras]);

  if (enrichedCameras.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-gray-500 font-mono">
        <div className="text-4xl mb-3 opacity-30">📹</div>
        <div className="text-sm">No se detectaron cámaras</div>
        <div className="text-xs text-gray-600 mt-1">Ejecuta un escaneo de cámaras para ver resultados</div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-xs uppercase tracking-widest text-cyan-400 font-mono">
          📹 Visor de cámaras · {enrichedCameras.length} detectadas
        </h2>
        {onRefresh && (
          <button
            onClick={onRefresh}
            className="px-2 py-1 text-[10px] border border-cyan-500/30 text-cyan-300 rounded hover:bg-cyan-500/10 transition font-mono"
          >
            ↻ Actualizar
          </button>
        )}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {enrichedCameras.map((cam) => {
          const sources = getVideoSources(cam);
          const hasMjpeg = sources.some(s => s.type === 'mjpeg');
          const hasRtsp = sources.some(s => s.type === 'rtsp');
          const hasSnapshot = sources.some(s => s.type === 'snapshot');

          return (
            <div key={cam.ip} className="bg-[var(--ss-bg-2)] rounded-lg overflow-hidden border border-[var(--ss-border)]">
              <CameraViewer sources={sources} ip={cam.ip} />
              <div className="p-2 flex items-center justify-between text-[10px] text-gray-400 font-mono">
                <span>{cam.ip}</span>
                <div className="flex gap-1">
                  {hasMjpeg && <span className="text-green-400">● MJPEG</span>}
                  {hasRtsp && <span className="text-cyan-400">● RTSP</span>}
                  {hasSnapshot && <span className="text-amber-400">● SNAP</span>}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
