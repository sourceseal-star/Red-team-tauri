import React, { useState, useEffect, useCallback } from 'react';
import { useLeviathanAPI } from '../../hooks/useLeviathan';
import '../../styles/widgets.css';

const ThreatMap = ({ onMarkerSelect }) => {
  const { getThreatMap, getStats, isLoading, error } = useLeviathanAPI();
  const [threatData, setThreatData] = useState(null);
  const [stats, setStats] = useState(null);
  const [selectedMarker, setSelectedMarker] = useState(null);
  const [zoomLevel, setZoomLevel] = useState(12);
  const [center, setCenter] = useState({ lat: 0, lng: 0 });

  // Obtener datos del mapa de amenazas
  useEffect(() => {
    const fetchData = async () => {
      try {
        const mapData = await getThreatMap();
        setThreatData(mapData);
        
        const statsData = await getStats();
        setStats(statsData);
        
        // Centrar en el primer marcador si existe
        if (mapData?.markers?.length > 0) {
          setCenter(mapData.markers[0]);
        }
      } catch (err) {
        console.error('Error fetching threat map:', err);
      }
    };
    
    fetchData();
  }, [getThreatMap, getStats]);

  // Obtener color por nivel de amenaza
  const getThreatColor = (level) => {
    switch (level) {
      case 'critical': return '#dc3545';
      case 'high': return '#ffc107';
      case 'medium': return '#17a2b8';
      case 'low': return '#28a745';
      default: return '#6c757d';
    }
  };

  // Obtener icono por nivel de amenaza
  const getThreatIcon = (level) => {
    switch (level) {
      case 'critical': return '💣';
      case 'high': return '⚠️';
      case 'medium': return 'ℹ️';
      case 'low': return '✓';
      default: return '•';
    }
  };

  // Manejar clic en marcador
  const handleMarkerClick = useCallback((marker) => {
    setSelectedMarker(marker);
    if (onMarkerSelect) {
      onMarkerSelect(marker);
    }
  }, [onMarkerSelect]);

  // Simular mapa (en producción usar Leaflet o Google Maps)
  const renderMap = () => {
    if (!threatData?.markers?.length) {
      return (
        <div className="threat-map-container" style={{ 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          color: 'var(--text-muted)'
        }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '2rem', marginBottom: '10px' }}>🗺️</div>
            <p>No hay datos de amenazas disponibles</p>
          </div>
        </div>
      );
    }

    // Coordenadas aproximadas para visualización
    const markers = threatData.markers.map((marker, index) => ({
      ...marker,
      x: (marker.lng + 180) * 100 / 360,
      y: (90 - marker.lat) * 100 / 180
    }));

    return (
      <div 
        className="threat-map-container" 
        style={{
          position: 'relative',
          background: 'linear-gradient(to bottom right, #1a1a30, #0a0a1a)',
          overflow: 'hidden'
        }}
      >
        {/* Mapa simulado */}
        <svg 
          className="threat-map" 
          viewBox="0 0 100 100" 
          preserveAspectRatio="xMidYMid meet"
        >
          {/* Fondo */}
          <rect width="100" height="100" fill="url(#mapGradient)" />
          
          {/* Grid */}
          <defs>
            <linearGradient id="mapGradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" style={{ stopColor: '#1a1a30' }} />
              <stop offset="100%" style={{ stopColor: '#0a0a1a' }} />
            </linearGradient>
            <pattern id="grid" width="10" height="10" patternUnits="userSpaceOnUse">
              <path d="M 10 0 L 0 0 0 10" fill="none" stroke="#303040" strokeWidth="0.5" />
            </pattern>
          </defs>
          
          <rect width="100" height="100" fill="url(#grid)" opacity="0.3" />
          
          {/* Marcadores */}
          {markers.map((marker, index) => (
            <g 
              key={index}
              onClick={() => handleMarkerClick(marker)}
              style={{ cursor: 'pointer' }}
            >
              <circle
                cx={marker.x}
                cy={marker.y}
                r={selectedMarker?.ip === marker.ip ? 8 : 6}
                fill={getThreatColor(marker.level || 'low')}
                stroke="white"
                strokeWidth={selectedMarker?.ip === marker.ip ? 2 : 1}
                opacity={0.9}
              />
              <text
                x={marker.x}
                y={marker.y}
                textAnchor="middle"
                dominantBaseline="central"
                fill="white"
                fontSize="4"
                fontWeight="bold"
              >
                {getThreatIcon(marker.level || 'low')}
              </text>
              
              {/* Tooltip */}
              {selectedMarker?.ip === marker.ip && (
                <foreignObject 
                  x={marker.x - 15} 
                  y={marker.y - 25} 
                  width="30" 
                  height="20"
                >
                  <div style={{
                    background: 'var(--bg-card)',
                    padding: '4px 8px',
                    borderRadius: '4px',
                    fontSize: '8px',
                    color: 'var(--text-primary)',
                    border: '1px solid var(--border)',
                    whiteSpace: 'nowrap'
                  }}>
                    {marker.ip}
                  </div>
                </foreignObject>
              )}
            </g>
          ))}
        </svg>

        {/* Controles del mapa */}
        <div className="threat-map-controls">
          <button 
            className="threat-map-control-btn" 
            onClick={() => setZoomLevel(z => Math.min(z + 1, 18))}
            title="Acercar"
          >
            +
          </button>
          <button 
            className="threat-map-control-btn" 
            onClick={() => setZoomLevel(z => Math.max(z - 1, 1))}
            title="Alejar"
          >
            -
          </button>
        </div>

        {/* Información del mapa */}
        <div className="threat-map-info">
          <span>📍 {threatData.markers.length} Dispositivos</span>
        </div>
      </div>
    );
  };

  // Calcular estadísticas por nivel
  const getStatsByLevel = () => {
    if (!threatData?.markers) return {};
    
    return threatData.markers.reduce((acc, marker) => {
      const level = marker.level || 'low';
      acc[level] = (acc[level] || 0) + 1;
      return acc;
    }, {});
  };

  const threatStats = getStatsByLevel();

  return (
    <div className="widget threat-map-widget">
      <div className="widget-header">
        <div className="widget-title">
          <span className="widget-icon">🗺️</span>
          <span>Mapa de Amenazas</span>
        </div>
        <div className="widget-actions">
          <button 
            className="widget-action-btn" 
            onClick={() => {
              // Recargar datos
              getThreatMap().then(setThreatData);
              getStats().then(setStats);
            }}
            title="Actualizar"
          >
            🔄
          </button>
        </div>
      </div>

      {/* Mapa */}
      {renderMap()}

      {/* Estadísticas */}
      <div className="threat-map-stats">
        <div className="threat-map-stat">
          <div className="threat-map-stat-value text-danger">
            {threatStats.critical || 0}
          </div>
          <div className="threat-map-stat-label">Crítico</div>
        </div>
        <div className="threat-map-stat">
          <div className="threat-map-stat-value text-warning">
            {threatStats.high || 0}
          </div>
          <div className="threat-map-stat-label">Alto</div>
        </div>
        <div className="threat-map-stat">
          <div className="threat-map-stat-value text-info">
            {threatStats.medium || 0}
          </div>
          <div className="threat-map-stat-label">Medio</div>
        </div>
        <div className="threat-map-stat">
          <div className="threat-map-stat-value text-success">
            {threatStats.low || 0}
          </div>
          <div className="threat-map-stat-label">Bajo</div>
        </div>
      </div>

      {/* Información del marcador seleccionado */}
      {selectedMarker && (
        <div className="mt-2" style={{ 
          background: 'var(--bg-secondary)', 
          padding: 'var(--spacing-sm)', 
          borderRadius: 'var(--radius-sm)',
          border: '1px solid var(--border)'
        }}>
          <h4 className="text-sm font-semibold mb-1">Dispositivo Seleccionado</h4>
          <p className="text-xs text-muted">
            <strong>IP:</strong> {selectedMarker.ip}<br />
            <strong>Nivel:</strong> {selectedMarker.level?.toUpperCase() || 'N/A'}<br />
            <strong>Vendor:</strong> {selectedMarker.vendor || 'Desconocido'}<br />
            <strong>Modelo:</strong> {selectedMarker.model || 'N/A'}
          </p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="alert alert-danger mt-2">
          <span>❌ Error al cargar el mapa de amenazas</span>
        </div>
      )}
    </div>
  );
};

export default ThreatMap;
