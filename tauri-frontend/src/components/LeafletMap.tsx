// src/components/LeafletMap.tsx
// Geolocalización de IP pública en mapa Leaflet.
// Usa el endpoint /api/geo del backend (no axios — fetch directo).
import { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix para iconos de Leaflet en Vite/bundlers
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

interface GeoData {
  lat: number;
  lon: number;
  country: string;
  city: string;
  isp: string;
  ip: string;
}

interface LeafletMapProps {
  ip: string;
}

// Centrar el mapa cuando llega la ubicación
function ChangeMapView({ center }: { center: [number, number] }) {
  const map = useMap();
  useEffect(() => { map.setView(center, 10); }, [center, map]);
  return null;
}

export function LeafletMap({ ip }: LeafletMapProps) {
  const [geo, setGeo] = useState<GeoData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ip) return;
    setLoading(true);
    setError(null);
    fetch(`/api/geo?ip=${encodeURIComponent(ip)}`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(d => {
        if (d && d.lat != null && d.lon != null) {
          setGeo({ lat: d.lat, lon: d.lon, country: d.country || '—', city: d.city || '—', isp: d.isp || d.org || '—', ip: d.ip || ip });
        } else {
          setError(d.error || d.note || 'No se pudo geolocalizar esta IP');
        }
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [ip]);

  if (loading) {
    return <div className="text-cyan-400 font-mono text-xs p-4 animate-pulse">🌍 Obteniendo ubicación...</div>;
  }
  if (error || !geo) {
    return <div className="text-red-400 font-mono text-xs p-4">❌ {error || 'Ubicación no disponible'}</div>;
  }

  const position: [number, number] = [geo.lat, geo.lon];

  return (
    <MapContainer
      center={position}
      zoom={10}
      style={{ height: '100%', width: '100%', borderRadius: '8px', background: '#0d1117' }}
      zoomControl={false}
    >
      <TileLayer
        attribution='&copy; OpenStreetMap'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <ChangeMapView center={position} />
      <Marker position={position}>
        <Popup>
          <div style={{ color: '#1a1a2e' }}>
            <strong>{geo.city}, {geo.country}</strong><br />
            <span style={{ fontSize: '12px' }}>{geo.isp}</span><br />
            <span style={{ fontSize: '11px', color: '#666' }}>IP: {geo.ip}</span>
          </div>
        </Popup>
      </Marker>
    </MapContainer>
  );
}
