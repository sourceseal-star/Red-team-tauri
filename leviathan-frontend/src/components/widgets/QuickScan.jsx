import React, { useState, useCallback } from 'react';
import { useLeviathanAPI } from '../../hooks/useLeviathan';
import '../../styles/widgets.css';

const QuickScan = ({ onResultSelect }) => {
  const { quickScan, isLoading, error, clearError } = useLeviathanAPI();
  const [target, setTarget] = useState('');
  const [results, setResults] = useState([]);
  const [isScanning, setIsScanning] = useState(false);
  const [scanType, setScanType] = useState('quick');

  // Tipos de escaneo
  const scanTypes = [
    { value: 'quick', label: 'Rápido', icon: '⚡' },
    { value: 'deep', label: 'Profundo', icon: '🔍' },
    { value: 'stealth', label: 'Sigiloso', icon: '👤' }
  ];

  // Escanear
  const handleScan = useCallback(async () => {
    if (!target) return;
    
    clearError();
    setIsScanning(true);
    setResults([]);

    try {
      const result = await quickScan(target);
      setResults(result.results || result.cameras || []);
      
      // Si hay resultados y onResultSelect, seleccionar el primero
      if (result.results?.length > 0 && onResultSelect) {
        onResultSelect(result.results[0]);
      } else if (result.cameras?.length > 0 && onResultSelect) {
        onResultSelect(result.cameras[0]);
      }
    } catch (err) {
      console.error('Error in quick scan:', err);
    } finally {
      setIsScanning(false);
    }
  }, [target, scanType, quickScan, onResultSelect, clearError]);

  // Obtener icono de servicio
  const getServiceIcon = (service) => {
    const icons = {
      http: '🌐',
      https: '🔒',
      rtsp: '🎥',
      onvif: '📹',
      ftp: '📁',
      ssh: '🔑',
      telnet: '📞',
      unknown: '❓'
    };
    return icons[service?.toLowerCase()] || icons.unknown;
  };

  // Obtener color de estado
  const getStatusColor = (status) => {
    switch (status) {
      case 'open': return 'text-success';
      case 'closed': return 'text-muted';
      case 'vulnerable': return 'text-warning';
      case 'exploitable': return 'text-danger';
      default: return 'text-secondary';
    }
  };

  // Manejar tecla Enter
  const handleKeyPress = useCallback((e) => {
    if (e.key === 'Enter' && target) {
      handleScan();
    }
  }, [target, handleScan]);

  return (
    <div className="widget quick-scan-widget">
      <div className="widget-header">
        <div className="widget-title">
          <span className="widget-icon">⚡</span>
          <span>Escaneo Rápido</span>
        </div>
      </div>

      {/* Controles */}
      <div className="quick-scan-form">
        <input
          type="text"
          className="quick-scan-input"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="IP, dominio o red (ej: 192.168.0.1)"
          disabled={isScanning || isLoading}
        />
        
        <select
          className="quick-scan-input"
          value={scanType}
          onChange={(e) => setScanType(e.target.value)}
          disabled={isScanning || isLoading}
        >
          {scanTypes.map(type => (
            <option key={type.value} value={type.value}>
              {type.icon} {type.label}
            </option>
          ))}
        </select>
        
        <button
          className="btn-primary btn-sm"
          onClick={handleScan}
          disabled={!target || isScanning || isLoading}
        >
          {isScanning ? 'Escaneando...' : 'Escanear'}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="alert alert-danger mt-2">
          <span>❌ {error.error || 'Error en el escaneo'}</span>
        </div>
      )}

      {/* Resultados */}
      {results.length > 0 && (
        <div className="quick-scan-results">
          {results.map((result, index) => (
            <div
              key={`${result.ip || result.target}-${index}`}
              className="quick-scan-result"
              onClick={() => onResultSelect && onResultSelect(result)}
            >
              <div className="quick-scan-result-icon">
                {getServiceIcon(result.service || result.type)}
              </div>
              <div className="quick-scan-result-info">
                <div className="quick-scan-result-name">
                  {result.name || result.vendor || result.service || 'Desconocido'}
                </div>
                <div className="quick-scan-result-ip">
                  {result.ip || result.target || result.address}
                  {result.port && `:${result.port}`}
                </div>
              </div>
              <div className={`quick-scan-result-status ${getStatusColor(result.status || result.state)}`}>
                {result.status || result.state || 'N/A'}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Mensaje vacío */}
      {results.length === 0 && !isScanning && target && !error && (
        <div className="text-center text-muted mt-2">
          <p className="text-sm">No se encontraron resultados</p>
        </div>
      )}
    </div>
  );
};

export default QuickScan;
