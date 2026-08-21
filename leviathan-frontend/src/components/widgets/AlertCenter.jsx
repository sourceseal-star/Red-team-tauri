import React, { useState, useEffect, useCallback } from 'react';
import { useLeviathanAPI } from '../../hooks/useLeviathan';
import { useWebSocket } from '../../hooks/useWebSocket';
import '../../styles/widgets.css';

const AlertCenter = ({ onAlertSelect }) => {
  const { getAlerts, isLoading, error } = useLeviathanAPI();
  const [alerts, setAlerts] = useState([]);
  const [activeTab, setActiveTab] = useState('all');
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Pestañas de alertas
  const tabs = [
    { id: 'all', label: 'Todas' },
    { id: 'critical', label: 'Críticas' },
    { id: 'high', label: 'Altas' },
    { id: 'medium', label: 'Medias' },
    { id: 'low', label: 'Bajas' }
  ];

  // Obtener alertas
  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        setIsRefreshing(true);
        const data = await getAlerts();
        setAlerts(data.alerts || []);
      } catch (err) {
        console.error('Error fetching alerts:', err);
      } finally {
        setIsRefreshing(false);
      }
    };
    
    fetchAlerts();
    
    // Actualizar cada 30 segundos
    const interval = setInterval(fetchAlerts, 30000);
    
    return () => clearInterval(interval);
  }, [getAlerts]);

  // Filtrar alertas por pestaña
  const getFilteredAlerts = useCallback(() => {
    if (activeTab === 'all') return alerts;
    return alerts.filter(alert => alert.severity === activeTab);
  }, [alerts, activeTab]);

  // Obtener color por severidad
  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'critical': return 'critical';
      case 'high': return 'high';
      case 'medium': return 'medium';
      case 'low': return 'low';
      default: return 'low';
    }
  };

  // Obtener icono por severidad
  const getSeverityIcon = (severity) => {
    switch (severity) {
      case 'critical': return '💣';
      case 'high': return '⚠️';
      case 'medium': return 'ℹ️';
      case 'low': return '✓';
      default: return '•';
    }
  };

  // Formatear tiempo
  const formatTime = (timestamp) => {
    if (!timestamp) return 'N/A';
    
    const date = new Date(timestamp);
    const now = new Date();
    const diff = Math.floor((now - date) / 1000);
    
    if (diff < 60) return `${diff}s`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
    return date.toLocaleDateString();
  };

  // Contadores por severidad
  const getSeverityCounts = () => {
    return alerts.reduce((acc, alert) => {
      const severity = alert.severity || 'low';
      acc[severity] = (acc[severity] || 0) + 1;
      return acc;
    }, {});
  };

  const severityCounts = getSeverityCounts();
  const filteredAlerts = getFilteredAlerts();

  return (
    <div className="widget alert-center-widget">
      <div className="widget-header">
        <div className="widget-title">
          <span className="widget-icon">🔔</span>
          <span>Centro de Alertas</span>
        </div>
        <div className="widget-actions">
          <button 
            className="widget-action-btn" 
            onClick={() => {
              getAlerts().then(data => setAlerts(data.alerts || []));
            }}
            disabled={isLoading || isRefreshing}
            title="Actualizar"
          >
            {isRefreshing ? '⏳' : '🔄'}
          </button>
        </div>
      </div>

      {/* Pestañas */}
      <div className="alert-center-tabs">
        {tabs.map(tab => (
          <button
            key={tab.id}
            className={`alert-center-tab ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label} {tab.id !== 'all' && severityCounts[tab.id] > 0 && (
              <span className="notification-badge">{severityCounts[tab.id]}</span>
            )}
          </button>
        ))}
      </div>

      {/* Lista de alertas */}
      <div className="alert-center-list">
        {filteredAlerts.length > 0 ? (
          filteredAlerts.map((alert, index) => (
            <div
              key={alert.id || index}
              className={`alert-center-item ${getSeverityColor(alert.severity)}`}
              onClick={() => {
                if (onAlertSelect) onAlertSelect(alert);
              }}
            >
              <div className="alert-center-icon">
                {getSeverityIcon(alert.severity)}
              </div>
              <div className="alert-center-content">
                <div className="alert-center-title">{alert.title}</div>
                <div className="alert-center-message">{alert.message}</div>
              </div>
              <div className="alert-center-time">
                {formatTime(alert.timestamp)}
              </div>
            </div>
          ))
        ) : (
          <div className="alert-center-empty">
            <div className="alert-center-empty-icon">📬</div>
            <p>No hay alertas {activeTab !== 'all' ? `de ${activeTab}` : ''}</p>
          </div>
        )}
      </div>

      {/* Contadores */}
      <div className="mt-2" style={{ 
        display: 'flex', 
        gap: 'var(--spacing-sm)',
        justifyContent: 'space-around'
      }}>
        <div style={{ textAlign: 'center' }}>
          <div className="text-lg font-bold text-danger">{severityCounts.critical || 0}</div>
          <div className="text-xs text-muted">Críticas</div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div className="text-lg font-bold text-warning">{severityCounts.high || 0}</div>
          <div className="text-xs text-muted">Altas</div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div className="text-lg font-bold text-info">{severityCounts.medium || 0}</div>
          <div className="text-xs text-muted">Medias</div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div className="text-lg font-bold text-success">{severityCounts.low || 0}</div>
          <div className="text-xs text-muted">Bajas</div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="alert alert-danger mt-2">
          <span>❌ Error al cargar alertas</span>
        </div>
      )}
    </div>
  );
};

export default AlertCenter;
