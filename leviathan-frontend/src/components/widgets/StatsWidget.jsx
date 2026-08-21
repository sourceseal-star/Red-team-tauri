import React, { useState, useEffect, useCallback } from 'react';
import { useLeviathanAPI } from '../../hooks/useLeviathan';
import '../../styles/widgets.css';

const StatsWidget = () => {
  const { getStats, getHistory, isLoading, error } = useLeviathanAPI();
  const [stats, setStats] = useState(null);
  const [history, setHistory] = useState([]);
  const [timeRange, setTimeRange] = useState('today');
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Rangos de tiempo
  const timeRanges = [
    { value: 'today', label: 'Hoy' },
    { value: 'week', label: 'Semana' },
    { value: 'month', label: 'Mes' },
    { value: 'all', label: 'Todo' }
  ];

  // Obtener estadísticas
  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsRefreshing(true);
        const statsData = await getStats();
        setStats(statsData);
        
        const historyData = await getHistory();
        setHistory(historyData.operations || []);
      } catch (err) {
        console.error('Error fetching stats:', err);
      } finally {
        setIsRefreshing(false);
      }
    };
    
    fetchData();
    
    // Actualizar cada 60 segundos
    const interval = setInterval(fetchData, 60000);
    
    return () => clearInterval(interval);
  }, [getStats, getHistory]);

  // Filtrar historial por rango de tiempo
  const getFilteredHistory = useCallback(() => {
    if (!history.length) return [];
    
    const now = new Date();
    let startDate;
    
    switch (timeRange) {
      case 'today':
        startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        break;
      case 'week':
        startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        break;
      case 'month':
        startDate = new Date(now.getFullYear(), now.getMonth() - 1, now.getDate());
        break;
      default:
        return history;
    }
    
    return history.filter(op => new Date(op.timestamp) >= startDate);
  }, [history, timeRange]);

  // Calcular estadísticas del historial
  const getHistoryStats = () => {
    const filtered = getFilteredHistory();
    
    const stats = {
      total: filtered.length,
      successful: filtered.filter(op => op.status === 'success').length,
      failed: filtered.filter(op => op.status === 'failed' || op.status === 'error').length,
      byType: filtered.reduce((acc, op) => {
        const type = op.type || 'unknown';
        acc[type] = (acc[type] || 0) + 1;
        return acc;
      }, {})
    };
    
    return stats;
  };

  // Formatear número
  const formatNumber = (num) => {
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num;
  };

  // Calcular porcentaje
  const calculatePercentage = (part, total) => {
    if (total === 0) return 0;
    return Math.round((part / total) * 100);
  };

  const historyStats = getHistoryStats();

  return (
    <div className="widget stats-widget">
      <div className="widget-header">
        <div className="widget-title">
          <span className="widget-icon">📈</span>
          <span>Estadísticas</span>
        </div>
        <div className="widget-actions">
          <select
            className="form-control form-control-sm"
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            disabled={isLoading || isRefreshing}
          >
            {timeRanges.map(range => (
              <option key={range.value} value={range.value}>
                {range.label}
              </option>
            ))}
          </select>
          <button 
            className="widget-action-btn" 
            onClick={() => {
              getStats().then(setStats);
              getHistory().then(data => setHistory(data.operations || []));
            }}
            disabled={isLoading || isRefreshing}
            title="Actualizar"
          >
            {isRefreshing ? '⏳' : '🔄'}
          </button>
        </div>
      </div>

      {/* Estadísticas principales */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-card-icon">🎯</div>
          <div className="stat-card-value">{formatNumber(stats?.total_cameras || 0)}</div>
          <div className="stat-card-label">Cámaras</div>
        </div>
        
        <div className="stat-card">
          <div className="stat-card-icon">⚡</div>
          <div className="stat-card-value">{formatNumber(stats?.total_scans || 0)}</div>
          <div className="stat-card-label">Escaneos</div>
        </div>
        
        <div className="stat-card">
          <div className="stat-card-icon">💥</div>
          <div className="stat-card-value">{formatNumber(stats?.total_exploits || 0)}</div>
          <div className="stat-card-label">Exploits</div>
        </div>
        
        <div className="stat-card">
          <div className="stat-card-icon">⚠️</div>
          <div className="stat-card-value">{formatNumber(stats?.total_alerts || 0)}</div>
          <div className="stat-card-label">Alertas</div>
        </div>
      </div>

      {/* Estadísticas de historial */}
      <div className="stats-chart mt-3">
        <h4 className="text-sm font-semibold mb-2">Operaciones Recientes ({timeRange === 'all' ? 'Todo' : timeRange === 'today' ? 'Hoy' : timeRange === 'week' ? 'Esta semana' : 'Este mes'})</h4>
        
        <div style={{ display: 'flex', gap: 'var(--spacing-sm)', marginBottom: 'var(--spacing-sm)' }}>
          <div className="stat-card" style={{ flex: 1, background: 'var(--bg-secondary)' }}>
            <div className="stat-card-icon">✓</div>
            <div className="stat-card-value text-success">{formatNumber(historyStats.successful)}</div>
            <div className="stat-card-label">Éxito</div>
          </div>
          <div className="stat-card" style={{ flex: 1, background: 'var(--bg-secondary)' }}>
            <div className="stat-card-icon">✗</div>
            <div className="stat-card-value text-danger">{formatNumber(historyStats.failed)}</div>
            <div className="stat-card-label">Error</div>
          </div>
          <div className="stat-card" style={{ flex: 1, background: 'var(--bg-secondary)' }}>
            <div className="stat-card-icon">📊</div>
            <div className="stat-card-value">{calculatePercentage(historyStats.successful, historyStats.total)}%</div>
            <div className="stat-card-label">Tasa Éxito</div>
          </div>
        </div>

        {/* Gráfico de barras (simulado) */}
        <div className="stats-chart-container" style={{
          display: 'flex',
          alignItems: 'flex-end',
          gap: 'var(--spacing-xs)',
          height: '100%',
          padding: 'var(--spacing-sm)'
        }}>
          {Object.entries(historyStats.byType).map(([type, count]) => {
            const percentage = calculatePercentage(count, historyStats.total);
            return (
              <div 
                key={type} 
                style={{
                  flex: 1,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 'var(--spacing-xs)'
                }}
              >
                <div 
                  style={{
                    width: '100%',
                    height: `${percentage}%`,
                    background: 'var(--gradient-button)',
                    borderRadius: 'var(--radius-sm)',
                    transition: 'height 0.5s ease'
                  }}
                />
                <span className="text-xs truncate">{type}</span>
                <span className="text-xs">{count}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="alert alert-danger mt-2">
          <span>❌ Error al cargar estadísticas</span>
        </div>
      )}
    </div>
  );
};

export default StatsWidget;
