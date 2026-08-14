import React, { useEffect, useRef, useState } from 'react';
import Hls from 'hls.js';

interface VideoSource {
  type: 'mjpeg' | 'rtsp' | 'snapshot' | 'onvif' | 'html';
  url: string;
  stream_url?: string;
  rtsp_url?: string;
  snapshot_url?: string;
}

interface CameraViewerProps {
  sources: VideoSource[];
  ip: string;
}

export const CameraViewer: React.FC<CameraViewerProps> = ({ sources, ip }) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const hlsRef = useRef<Hls | null>(null);
  const [hlsUrl, setHlsUrl] = useState<string | null>(null);
  const [isHlsStarted, setIsHlsStarted] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Limpiar recursos al desmontar
  useEffect(() => {
    return () => {
      if (sessionId) {
        fetch(`/api/iot/rtsp-stop/${sessionId}`, { method: 'DELETE' }).catch(() => {});
      }
      if (hlsRef.current) {
        hlsRef.current.destroy();
        hlsRef.current = null;
      }
    };
  }, [sessionId]);

  // Iniciar RTSP → HLS
  const startRTSP = async (rtspUrl: string) => {
    setError(null);
    try {
      const res = await fetch(`/api/iot/rtsp-to-hls?rtsp_url=${encodeURIComponent(rtspUrl)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      if (data.stream_url) {
        setHlsUrl(data.stream_url);
        setSessionId(data.session_id);
        setIsHlsStarted(true);

        // Inicializar hls.js
        if (videoRef.current && Hls.isSupported()) {
          if (hlsRef.current) hlsRef.current.destroy();
          const hls = new Hls({
            enableWorker: true,
            lowLatencyMode: true,
          });
          hlsRef.current = hls;
          hls.loadSource(data.stream_url);
          hls.attachMedia(videoRef.current);
          hls.on(Hls.Events.MANIFEST_PARSED, () => {
            videoRef.current?.play().catch(() => {});
          });
          hls.on(Hls.Events.ERROR, (_event, data) => {
            if (data.fatal) {
              setError(`Error HLS: ${data.type}`);
              hls.destroy();
              hlsRef.current = null;
            }
          });
        } else if (videoRef.current?.canPlayType('application/vnd.apple.mpegurl')) {
          // Safari nativo
          videoRef.current.src = data.stream_url;
          videoRef.current.play().catch(() => {});
        } else {
          setError('HLS no soportado en este navegador');
        }
      }
    } catch (err: any) {
      setError(err.message || 'Error iniciando stream RTSP');
    }
  };

  // Detener stream RTSP
  const stopRTSP = () => {
    if (sessionId) {
      fetch(`/api/iot/rtsp-stop/${sessionId}`, { method: 'DELETE' }).catch(() => {});
      setSessionId(null);
    }
    if (hlsRef.current) {
      hlsRef.current.destroy();
      hlsRef.current = null;
    }
    setIsHlsStarted(false);
    setHlsUrl(null);
  };

  // Encontrar el tipo de fuente principal
  const mjpegSource = sources.find(s => s.type === 'mjpeg');
  const rtspSource = sources.find(s => s.type === 'rtsp');
  const snapshotSource = sources.find(s => s.type === 'snapshot');

  // Si hay MJPEG, mostrarlo directamente en un <img>
  if (mjpegSource && mjpegSource.stream_url) {
    return (
      <div className="relative bg-black rounded-lg overflow-hidden aspect-video">
        <img
          ref={imgRef}
          src={`/api/iot/mjpeg-proxy?url=${encodeURIComponent(mjpegSource.stream_url)}`}
          alt={`Stream ${ip}`}
          className="w-full h-full object-contain"
          onError={() => setError('Error cargando stream MJPEG')}
        />
        <div className="absolute bottom-2 left-2 bg-black/60 text-white text-xs px-2 py-1 rounded flex items-center gap-1">
          <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
          MJPEG en vivo · {ip}
        </div>
      </div>
    );
  }

  // Si hay RTSP, ofrecer botón para convertirlo a HLS
  if (rtspSource && rtspSource.rtsp_url) {
    if (isHlsStarted && hlsUrl) {
      return (
        <div className="relative bg-black rounded-lg overflow-hidden aspect-video">
          <video
            ref={videoRef}
            className="w-full h-full object-contain"
            controls
            autoPlay
            muted
          />
          <div className="absolute bottom-2 left-2 bg-black/60 text-white text-xs px-2 py-1 rounded flex items-center gap-1">
            <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            RTSP→HLS en vivo · {ip}
          </div>
          <button
            onClick={stopRTSP}
            className="absolute top-2 right-2 bg-red-600 text-white px-2 py-1 text-xs rounded hover:bg-red-500 transition"
          >
            ⏹ Detener
          </button>
          {error && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/80">
              <div className="text-red-400 text-sm">{error}</div>
            </div>
          )}
        </div>
      );
    }

    return (
      <div className="relative bg-black rounded-lg overflow-hidden aspect-video flex flex-col items-center justify-center">
        <div className="text-gray-400 text-sm mb-3">📹 RTSP detectado · {ip}</div>
        <button
          onClick={() => startRTSP(rtspSource.rtsp_url!)}
          className="px-4 py-2 bg-cyan-600 text-white rounded hover:bg-cyan-500 text-sm font-mono transition"
        >
          ▶ Ver en vivo
        </button>
        <div className="text-gray-500 text-xs mt-2">Latencia ~3s · HLS</div>
        {error && (
          <div className="text-red-400 text-xs mt-2">{error}</div>
        )}
      </div>
    );
  }

  // Fallback: snapshot
  if (snapshotSource && snapshotSource.snapshot_url) {
    return (
      <div className="relative bg-black rounded-lg overflow-hidden aspect-video">
        <img
          src={snapshotSource.snapshot_url}
          alt={`Snapshot ${ip}`}
          className="w-full h-full object-contain"
          onError={() => setError('Error cargando snapshot')}
        />
        <div className="absolute bottom-2 left-2 bg-black/60 text-white text-xs px-2 py-1 rounded">
          📷 Snapshot · {ip}
        </div>
        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/80">
            <div className="text-red-400 text-sm">{error}</div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="bg-black rounded-lg overflow-hidden aspect-video flex items-center justify-center text-gray-500 text-sm font-mono">
      No hay fuente de video disponible
    </div>
  );
};
