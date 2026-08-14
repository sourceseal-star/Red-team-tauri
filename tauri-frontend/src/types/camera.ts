// src/types/camera.ts
// Tipos para el visor de cámaras en vivo (MJPEG, RTSP→HLS, Snapshot).

export interface VideoSource {
  type: 'mjpeg' | 'rtsp' | 'snapshot' | 'onvif' | 'html';
  url: string;
  stream_url?: string;   // Para MJPEG — URL del stream directo
  rtsp_url?: string;     // Para RTSP — URL rtsp://
  snapshot_url?: string; // Para snapshot — URL del JPEG
  vendor?: string;
  available?: boolean;
  path?: string;
  port?: number;
  content_type?: string;
}

export interface CameraWithSnapshot {
  ip: string;
  rtsp?: string;
  ports?: Record<string, string | null>;
  type: string;
  first_seen?: string;
  sources?: VideoSource[]; // Resultado de /api/iot/video-urls
}
