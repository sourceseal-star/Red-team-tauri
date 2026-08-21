import React, { useState, useEffect, useCallback } from 'react';
import { useLeviathanAPI } from '../../hooks/useLeviathan';
import '../../styles/widgets.css';

const CameraDetection = ({ onCameraSelect, initialNetwork = '192.168.0.0/24' }) => {
  const { scanCameras, isLoading, error, clearError } = useLeviathanAPI();
  const [network, setNetwork] = useState(initialNetwork);
  const [cameras, setCameras] = useState([]);
  const [isScanning, setIsScanning] = useState(false);
  const [scanProgress, setScanProgress] = useState(0);
  const [selectedCamera, setSelectedCamera] = useState(null);

  // Escanear cámaras
  const handleScan = useCallback(async () => {
    clearError();
    setIsScanning(true);
    setScanProgress(0);
    setCameras([]);

    try {
      // Simular progreso
      const progressInterval = setInterval(() => {
        setScanProgress(prev => Math.min(prev + 10, 90));
      }, 300);

      const result = await scanCameras(network);
      setCameras(result.cameras || []);
      setScanProgress(100);

      clearInterval(progressInterval);

      // Seleccionar primera cámara si hay resultados
      if (result.cameras && result.cameras.length > 0) {
        setSelectedCamera(result.cameras[0]);
        if (onCameraSelect) onCameraSelect(result.cameras[0]);
      }
    } catch (err) {
      console.error('Error scanning cameras:', err);
    } finally {
      setIsScanning(false);
    }
  }, [network, scanCameras, onCameraSelect, clearError]);

  // Contadores
  const totalCameras = cameras.length;
  const onlineCameras = cameras.filter(c => c.status === 'online').length;
  const vulnerableCameras = cameras.filter(c => c.vulnerabilities && c.vulnerabilities.length > 0).length;

  // Obtener color de estado
  const getStatusColor = (status) => {
    switch (status) {
      case 'online': return 'online';
      case 'offline': return 'offline';
      case 'vulnerable': return 'vulnerable';
      default: return 'offline';
    }
  };

  // Obtener icono de vendor
  const getVendorIcon = (vendor) => {
    const icons = {
      hikvision: '📹',
      dahua: '🎥',
      axis: '🌐',
      bosch: '🏢',
      unknown: '🔍'
    };
    return icons[vendor?.toLowerCase()] || icons.unknown;
  };

  // Formatear IP
  const formatIp = (ip) => {
    return ip || 'N/A';
  };

  return (
    <div className="widget camera-detection-widget">
      <div className="widget-header">
        <div className="widget-title">
          <span className="widget-icon">🎥</span>
          <span>Detección de Cámaras</span>
        </div>
        <div className="widget-actions">
          <button 
            className="widget-action-btn" 
            onClick={handleScan}
            disabled={isScanning || isLoading}
            title="Escanear"
          >
            {isScanning ? '⏳' : '🔍'}
          </button>
        </div>
      </div>

      {/* Controles de escaneo */}
      <div className="camera-scan-controls">
        <input
          type="text"
          className="camera-scan-input"
          value={network}
          onChange={(e) => setNetwork(e.target.value)}
          placeholder="Ej: 192.168.0.0/24"
        />
        <button 
          className="btn-primary btn-sm"
          onClick={handleScan}
          disabled={isScanning || isLoading}
        >
          {isScanning ? 'Escaneando...' : 'Escanear'}
        </button>
        <button 
          className="btn-info btn-sm"
          onClick={() => handleScan()}
          disabled={isScanning || isLoading}
          title="Escaneo rápido"
        >
          ⚡ Rápido
        </button>
      </div>

      {/* Barra de progreso */}
      {isScanning && (
        <div className="quick-scan-progress">
          <div 
            className="quick-scan-progress-bar" 
            style={{ width: `${scanProgress}%` }}
          />
        </div>
      )}

      {/* Estadísticas */}
      <div className="camera-stats">
        <div className="camera-stat">
          <div className="camera-stat-value">{totalCameras}</div>
          <div className="camera-stat-label">Total</div>
        </div>
        <div className="camera-stat">
          <div className="camera-stat-value text-success">{onlineCameras}</div>
          <div className="camera-stat-label">En línea</div>
        </div>
        <div className="camera-stat">
          <div className="camera-stat-value text-warning">{vulnerableCameras}</div>
          <div className="camera-stat-label">Vulnerables</div>
        </div>
        <div className="camera-stat">
          <div className="camera-stat-value text-danger">{totalCameras - onlineCameras}</div>
          <div className="camera-stat-label">Fuera de línea</div>
        </div>
      </div>

      {/* Resultados */}
      {error && (
        <div className="alert alert-danger mt-2">
          <span>❌ {error.error || 'Error al escanear cámaras'}</span>
        </div>
      )}

      {cameras.length > 0 ? (
        <div className="camera-results">
          {cameras.map((camera) => (
            <div
              key={`${camera.ip}-${camera.port}`}
              className={`camera-card ${selectedCamera?.ip === camera.ip ? 'selected' : ''}`}
              onClick={() => {
                setSelectedCamera(camera);
                if (onCameraSelect) onCameraSelect(camera);
              }}
              title={`Haz clic para seleccionar ${camera.ip}`}
            >
              <div className="camera-card-header">
                <div>
                  <div className="camera-card-ip">{formatIp(camera.ip)}:{camera.port}</div>
                  <div className="camera-card-vendor">
                    {getVendorIcon(camera.vendor)} {camera.vendor || 'Desconocido'}
                  </div>
                </div>
                <div className="camera-card-status">
                  <span className={`camera-status-dot ${getStatusColor(camera.status)}`} />
                  <span className="text-sm">{camera.status}</span>
                </div>
              </div>
              
              <div className="camera-card-body">
                {camera.model && (
                  <span className="camera-badge http">{camera.model}</span>
                )}
                {camera.protocols?.map(protocol => (
                  <span key={protocol} className={`camera-badge ${protocol}`}>
                    {protocol.toUpperCase()}
                  </span>
                ))}
              </div>

              {camera.thumbnail && (
                <div className="camera-thumbnail">
                  <img 
                    src={camera.thumbnail} 
                    alt={`Thumbnail ${camera.ip}`}
                    onError={(e) => {
                      e.target.style.display = 'none';
                    }}
                  />
                </div>
              )}

              {camera.vulnerabilities && camera.vulnerabilities.length > 0 && (
                <div className="mt-1">
                  {camera.vulnerabilities.slice(0, 2).map(vuln => (
                    <span key={vuln} className="camera-badge danger">
                      {vuln}
                    </span>
                  ))}
                  {camera.vulnerabilities.length > 2 && (
                    <span className="camera-badge warning">+{camera.vulnerabilities.length - 2} más</span>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        !isScanning && !isLoading && (
          <div className="text-center text-muted mt-4">
            <p>No se han detectado cámaras</p>
            <p className="text-sm">Presiona "Escanear" para buscar cámaras en la red</p>
          </div>
        )
      )}
    </div>
  );
};

export default CameraDetection;
