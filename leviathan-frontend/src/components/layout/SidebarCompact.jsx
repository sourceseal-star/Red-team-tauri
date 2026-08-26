import React, { useState, useEffect } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { useLeviathanAPI } from '../../hooks/useLeviathan';
import './layout.css';

const SidebarCompact = ({ isOpen, onToggle, isMobile }) => {
  const location = useLocation();
  const { getStatus } = useLeviathanAPI();
  const [status, setStatus] = useState(null);
  const [activeSection, setActiveSection] = useState(null);
  
  // Obtener estado de LEVIATHAN
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const result = await getStatus();
        setStatus(result);
      } catch (error) {
        console.error('Error fetching LEVIATHAN status:', error);
      }
    };
    fetchStatus();
  }, [getStatus]);
  
  // Secciones del sidebar
  const sections = [
    {
      id: 'detection',
      name: 'DETECCIÓN',
      icon: '🎯',
      color: '#667eea',
      items: [
        { path: '/detection/network', name: 'Red', icon: '🔍' },
        { path: '/detection/cameras', name: 'Cámaras', icon: '🎥' },
        { path: '/detection/ports', name: 'Puertos', icon: '📡' },
        { path: '/detection/osint', name: 'OSINT', icon: '🌐' }
      ]
    },
    {
      id: 'analysis',
      name: 'ANÁLISIS',
      icon: '🔬',
      color: '#764ba2',
      items: [
        { path: '/', name: 'Dashboard', icon: '📊' },
        { path: '/analysis/threat-map', name: 'Mapa Amenazas', icon: '🗺️' },
        { path: '/analysis/ai', name: 'IA', icon: '🤖' },
        { path: '/analysis/stats', name: 'Estadísticas', icon: '📈' }
      ]
    },
    {
      id: 'exploit',
      name: 'EXPLOTAR',
      icon: '⚡',
      color: '#ffc107',
      items: [
        { path: '/exploit/kraken', name: 'KRAKEN', icon: '💥' },
        { path: '/exploit/auto', name: 'Automático', icon: '🎯' },
        { path: '/exploit/access', name: 'Acceso', icon: '🔓' }
      ]
    },
    {
      id: 'reports',
      name: 'REPORTES',
      icon: '📋',
      color: '#17a2b8',
      items: [
        { path: '/reports/generate', name: 'Generar', icon: '📄' },
        { path: '/reports/export', name: 'Exportar', icon: '📥' },
        { path: '/reports/history', name: 'Historial', icon: '📬' }
      ]
    },
    {
      id: 'system',
      name: 'SISTEMA',
      icon: '⚙️',
      color: '#6c757d',
      items: [
        { path: '/system/services', name: 'Servicios', icon: '🖥️' },
        { path: '/system/config', name: 'Configuración', icon: '⚙️' },
        { path: '/system/terminal', name: 'Terminal', icon: '📡' },
        { path: '/system/update', name: 'Actualizar', icon: '🔄' }
      ]
    }
  ];
  
  // Módulos Externos (ARTO, SEAL, KRAKEN)
  const externalModules = [
    { path: '/arto', name: 'ARTO AI', icon: '🤖', category: 'system' },
    { path: '/seal', name: 'SEAL Pack', icon: '🛡️', category: 'system' },
    { path: '/kraken-full', name: 'KRAKEN Full', icon: '💣', category: 'exploit' }
  ];
  
  // Contadores de ejemplo (en producción, obtener de API)
  const cameraCount = 3;
  const alertCount = 5;
  const scanCount = 12;
  
  return (
    <>
      {/* Sidebar para Desktop */}
      <aside className={`sidebar-compact ${isOpen ? 'open' : 'closed'} ${isMobile ? 'mobile' : ''}`}>
        {/* Header del Sidebar */}
        <div className="sidebar-header">
          <div className="logo">
            <span className="logo-icon">🦑</span>
            {isOpen && !isMobile && <span className="logo-text">LEVIATHAN</span>}
          </div>
        </div>
        
        {/* Navegación */}
        <nav className="sidebar-nav">
          {sections.map((section) => (
            <div key={section.id} className="sidebar-section">
              {/* Header de Sección */}
              <div 
                className={`section-header ${activeSection === section.id ? 'active' : ''}`}
                onClick={() => setActiveSection(activeSection === section.id ? null : section.id)}
                style={{ borderLeft: `3px solid ${section.color}` }}
              >
                <span className="section-icon">{section.icon}</span>
                {isOpen && <span className="section-name">{section.name}</span>}
                {isOpen && activeSection === section.id && (
                  <span className="section-chevron">▼</span>
                )}
              </div>
              
              {/* Items de la Sección */}
              {isOpen && activeSection === section.id && (
                <ul className="section-items">
                  {section.items.map((item) => (
                    <li key={item.path}>
                      <NavLink 
                        to={item.path} 
                        className={`nav-item ${location.pathname === item.path ? 'active' : ''}`}
                        onClick={() => {
                          setActiveSection(null);
                          if (isMobile) onToggle();
                        }}
                      >
                        <span className="nav-icon">{item.icon}</span>
                        <span className="nav-name">{item.name}</span>
                        
                        {/* Badges para notificaciones */}
                        {item.path.includes('cameras') && cameraCount > 0 && (
                          <span className="nav-badge">{cameraCount}</span>
                        )}
                        {item.path.includes('alerts') && alertCount > 0 && (
                          <span className="nav-badge alert">{alertCount}</span>
                        )}
                        {item.path.includes('network') && scanCount > 0 && (
                          <span className="nav-badge info">{scanCount}</span>
                        )}
                      </NavLink>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
          
          {/* Módulos Externos */}
          {isOpen && (
            <div className="sidebar-section external">
              <div className="section-header" style={{ borderLeft: '3px solid #6c757d' }}>
                <span className="section-icon">🔗</span>
                {isOpen && <span className="section-name">MÓDULOS</span>}
              </div>
              <ul className="section-items">
                {externalModules.map((module) => (
                  <li key={module.path}>
                    <NavLink 
                      to={module.path} 
                      className={`nav-item ${location.pathname === module.path ? 'active' : ''}`}
                      onClick={() => isMobile && onToggle()}
                    >
                      <span className="nav-icon">{module.icon}</span>
                      <span className="nav-name">{module.name}</span>
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </nav>
        
        {/* Footer del Sidebar */}
        {isOpen && !isMobile && (
          <div className="sidebar-footer">
            <div className="footer-info">
              {status && (
                <>
                  <div className="footer-status">
                    <span className={`status-dot ${status.status}`}></span>
                    <span>{status.modules?.total || 0} módulos</span>
                  </div>
                  <div className="footer-version">v{status.version || '3.0.0'}</div>
                </>
              )}
            </div>
          </div>
        )}
      </aside>
      
      {/* Overlay para Mobile */}
      {isOpen && isMobile && (
        <div className="sidebar-overlay" onClick={onToggle} />
      )}
    </>
  );
};

export default SidebarCompact;
