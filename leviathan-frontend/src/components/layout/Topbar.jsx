import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useLeviathanAPI } from '../../hooks/useLeviathan';
import './layout.css';

const Topbar = ({ onMenuClick, onThemeClick, currentTheme }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { getStatus, getStats } = useLeviathanAPI();
  const [status, setStatus] = useState(null);
  const [stats, setStats] = useState(null);
  const [alertCount, setAlertCount] = useState(0);
  const [notificationCount, setNotificationCount] = useState(0);

  // Obtener estado y estadísticas
  useEffect(() => {
    const fetchData = async () => {
      try {
        const statusResult = await getStatus();
        setStatus(statusResult);
        
        const statsResult = await getStats();
        setStats(statsResult);
        
        // Simular contadores (en producción, obtener de API)
        setAlertCount(statsResult?.alerts?.critical || 0);
        setNotificationCount(statsResult?.notifications?.unread || 0);
      } catch (error) {
        console.error('Error fetching data:', error);
      }
    };
    
    fetchData();
    
    // Actualizar cada 30 segundos
    const interval = setInterval(fetchData, 30000);
    
    return () => clearInterval(interval);
  }, [getStatus, getStats]);

  // Pestañas rápidas
  const tabs = [
    { path: '/', name: 'Dashboard', icon: '📊' },
    { path: '/detection', name: 'Detección', icon: '🎯' },
    { path: '/analysis', name: 'Análisis', icon: '🔬' },
    { path: '/exploit', name: 'Explotar', icon: '⚡' },
    { path: '/reports', name: 'Reportes', icon: '📋' }
  ];

  const isActive = (path) => {
    return location.pathname.startsWith(path);
  };

  return (
    <header className="topbar">
      <div className="topbar-left">
        {/* Botón de menú (mobile) */}
        <button className="menu-toggle" onClick={onMenuClick}>
          <span>☰</span>
        </button>

        {/* Logo */}
        <div className="topbar-logo">
          <span className="logo-icon">🦑</span>
          <span className="logo-text">LEVIATHAN</span>
        </div>

        {/* Pestañas rápidas */}
        <nav className="topbar-tabs">
          {tabs.map((tab) => (
            <button
              key={tab.path}
              className={`tab ${isActive(tab.path) ? 'active' : ''}`}
              onClick={() => navigate(tab.path)}
            >
              <span>{tab.icon}</span>
              <span>{tab.name}</span>
            </button>
          ))}
        </nav>
      </div>

      <div className="topbar-right">
        {/* Estado del sistema */}
        <div className="system-status">
          <span className={`status-dot ${status?.leviathan === 'active' ? '' : 'inactive'}`} />
          <span>LEVIATHAN</span>
          <span className="text-muted">|</span>
          <span className={`status-dot ${status?.commander === 'active' ? '' : 'inactive'}`} />
          <span>Commander</span>
        </div>

        {/* Botón de notificaciones */}
        <button className="notifications-toggle">
          <span>🔔</span>
          {notificationCount > 0 && (
            <span className="notification-badge">{notificationCount}</span>
          )}
        </button>

        {/* Botón de alertas */}
        <button className="alerts-toggle">
          <span>⚠️</span>
          {alertCount > 0 && (
            <span className="notification-badge">{alertCount}</span>
          )}
        </button>

        {/* Botón de tema */}
        <button className="theme-toggle" onClick={onThemeClick}>
          <span>{currentTheme === 'leviathan' ? '🌙' : currentTheme === 'light' ? '☀️' : '🌙'}</span>
        </button>

        {/* Botón de usuario */}
        <button className="user-toggle">
          <span>👤</span>
        </button>
      </div>
    </header>
  );
};

export default Topbar;
