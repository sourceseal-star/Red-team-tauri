import React, { useEffect, useState, useRef } from 'react'
import { useSelector } from 'react-redux'
import { RootState } from '../store'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

// Fix para iconos de Leaflet (requerido cuando se usa con React)
const defaultIcon = L.icon({
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
})

L.Marker.prototype.options.icon = defaultIcon

// Iconos personalizados por severidad
const createCustomIcon = (severity: string) => {
  const colors = {
    critical: '#dc3545',
    high: '#fd7e14',
    medium: '#ffc107',
    low: '#28a745'
  }
  
  return L.divIcon({
    className: 'camera-marker',
    html: `
      <div style="
        width: 30px;
        height: 30px;
        border-radius: 50%;
        background: ${colors[severity as keyof typeof colors] || '#667eea'};
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: bold;
        box-shadow: 0 2px 10px rgba(0,0,0,0.3);
      ">
        🎥
      </div>
    `,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
    popupAnchor: [0, -15]
  })
}

const ThreatMap: React.FC = () => {
  const { cameras } = useSelector((state: RootState) => state.cameras)
  const { alerts } = useSelector((state: RootState) => state.alerts)
  const mapRef = useRef<L.Map | null>(null)
  const [mapReady, setMapReady] = useState(false)
  const [center, setCenter] = useState<[number, number]>([0, 0])
  const [zoom, setZoom] = useState<number>(2)
  
  // Coordenadas de ejemplo para cámaras (en producción, usar geolocalización real)
  const getCameraCoordinates = (camera: any): [number, number] => {
    // Si la cámara tiene coordenadas guardadas
    if (camera.latitude && camera.longitude) {
      return [camera.latitude, camera.longitude]
    }
    
    // Coordenadas de ejemplo para IPs locales
    const exampleCoords: Record<string, [number, number]> = {
      '192.168.0.1': [4.6097, -74.0817],  // Bogotá
      '192.168.0.7': [4.6097, -74.0817],  // Bogotá
      '192.168.0.2': [4.6097, -74.0817],  // Bogotá
      '10.0.0.1': [6.2442, -75.5812],    // Medellín
      '10.0.0.2': [6.2442, -75.5812],    // Medellín
    }
    
    return exampleCoords[camera.ip] || [center[0] + (Math.random() * 0.01 - 0.005), center[1] + (Math.random() * 0.01 - 0.005)]
  }
  
  // Determinar severidad de cámara
  const getCameraSeverity = (camera: any): string => {
    if (camera.is_vulnerable) return 'critical'
    if (camera.is_accessible) return 'high'
    return 'medium'
  }
  
  // Inicializar mapa
  useEffect(() => {
    if (!mapRef.current) {
      // Crear mapa centrado en Colombia
      const map = L.map('threat-map').setView([4.6097, -74.0817], 6)
      
      // Agregar capa de OpenStreetMap
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      }).addTo(map)
      
      mapRef.current = map
      setMapReady(true)
      setCenter([4.6097, -74.0817])
      setZoom(6)
    }
    
    return () => {
      if (mapRef.current) {
        mapRef.current.remove()
        mapRef.current = null
      }
    }
  }, [])
  
  // Actualizar marcadores cuando cambian las cámaras
  useEffect(() => {
    if (!mapReady || !mapRef.current) return
    
    // Limpiar marcadores existentes
    mapRef.current.eachLayer(layer => {
      if (layer instanceof L.Marker) {
        mapRef.current?.removeLayer(layer)
      }
    })
    
    // Agregar nuevos marcadores
    cameras.forEach(camera => {
      const coords = getCameraCoordinates(camera)
      const severity = getCameraSeverity(camera)
      
      const marker = L.marker(coords, {
        icon: createCustomIcon(severity),
        title: `${camera.vendor} ${camera.model} (${camera.ip})`
      }).addTo(mapRef.current!)
      
      // Popup con información
      const popupContent = `
        <div class="map-popup">
          <h4>${camera.vendor || 'Cámara'} ${camera.model || 'IP'}</h4>
          <p><strong>IP:</strong> ${camera.ip}:${camera.port}</p>
          <p><strong>Estado:</strong> ${camera.is_accessible ? '🔓 Accesible' : '🔒 No accesible'}</p>
          <p><strong>Severidad:</strong> <span style="color: ${severity === 'critical' ? '#dc3545' : severity === 'high' ? '#fd7e14' : '#ffc107'}">${severity}</span></p>
          ${camera.credentials ? `<p><strong>Credenciales:</strong> ${camera.credentials}</p>` : ''}
        </div>
      `
      
      marker.bindPopup(popupContent)
    })
    
    // Ajustar vista al primer marcador si hay cámaras
    if (cameras.length > 0 && center === [0, 0]) {
      const firstCoords = getCameraCoordinates(cameras[0])
      setCenter(firstCoords)
      setZoom(12)
      mapRef.current?.setView(firstCoords, 12)
    }
    
  }, [cameras, mapReady, center])
  
  // Agregar marcadores de alertas
  useEffect(() => {
    if (!mapReady || !mapRef.current) return
    
    alerts.forEach(alert => {
      // Coordenadas de ejemplo para alertas
      const alertCoords: Record<string, [number, number]> = {
        '192.168.0.1': [4.6097, -74.0817],
        '192.168.0.7': [4.6097, -74.0817],
        '192.168.0.2': [4.6097, -74.0817],
      }
      
      const target = alert.target || ''
      if (alertCoords[target]) {
        const coords = alertCoords[target]
        
        const alertIcon = L.divIcon({
          className: 'alert-marker',
          html: `
            <div style="
              width: 25px;
              height: 25px;
              border-radius: 50%;
              background: ${alert.severity === 'critical' ? '#dc3545' : alert.severity === 'high' ? '#fd7e14' : '#ffc107'};
              display: flex;
              align-items: center;
              justify-content: center;
              color: white;
              font-weight: bold;
              box-shadow: 0 2px 10px rgba(0,0,0,0.3);
              animation: pulse 2s infinite;
            ">
              🔔
            </div>
          `,
          iconSize: [25, 25],
          iconAnchor: [12.5, 12.5],
          popupAnchor: [0, -12.5]
        })
        
        const marker = L.marker(coords, {
          icon: alertIcon,
          title: alert.title
        }).addTo(mapRef.current)
        
        const popupContent = `
          <div class="map-popup alert">
            <h4>⚠️ ${alert.title}</h4>
            <p><strong>Tipo:</strong> ${alert.alert_type}</p>
            <p><strong>Severidad:</strong> <span style="color: ${alert.severity === 'critical' ? '#dc3545' : alert.severity === 'high' ? '#fd7e14' : '#ffc107'}">${alert.severity}</span></p>
            <p><strong>Descripción:</strong> ${alert.description}</p>
            <p><strong>Objetivo:</strong> ${alert.target}</p>
            <p><strong>Fecha:</strong> ${new Date(alert.timestamp).toLocaleString()}</p>
          </div>
        `
        
        marker.bindPopup(popupContent)
      }
    })
  }, [alerts, mapReady])
  
  return (
    <div className="threat-map">
      <div className="map-header">
        <h1>🗺️ Mapa de Amenazas</h1>
        <p className="map-subtitle">
          Visualización geográfica de cámaras y alertas
        </p>
      </div>
      
      <div className="map-stats">
        <div className="stat">
          <span className="stat-number">{cameras.length}</span>
          <span className="stat-label">Cámaras</span>
        </div>
        <div className="stat">
          <span className="stat-number">{cameras.filter(c => c.is_accessible).length}</span>
          <span className="stat-label">Accesibles</span>
        </div>
        <div className="stat">
          <span className="stat-number">{cameras.filter(c => c.is_vulnerable).length}</span>
          <span className="stat-label">Vulnerables</span>
        </div>
        <div className="stat">
          <span className="stat-number">{alerts.length}</span>
          <span className="stat-label">Alertas</span>
        </div>
      </div>
      
      <div className="map-legend">
        <h4>Leyenda:</h4>
        <div className="legend-items">
          <div className="legend-item">
            <span className="legend-color critical"></span>
            <span>Crítico</span>
          </div>
          <div className="legend-item">
            <span className="legend-color high"></span>
            <span>Alto</span>
          </div>
          <div className="legend-item">
            <span className="legend-color medium"></span>
            <span>Medio</span>
          </div>
          <div className="legend-item">
            <span className="legend-color low"></span>
            <span>Bajo</span>
          </div>
          <div className="legend-item">
            <span className="legend-color alert"></span>
            <span>Alerta</span>
          </div>
        </div>
      </div>
      
      <div 
        id="threat-map" 
        className="map-container"
      ></div>
    </div>
  )
}

export default ThreatMap
