import React, { useState, useEffect } from 'react';
import { useLeviathanAPI } from '../hooks/useLeviathan';
import CameraDetection from '../components/widgets/CameraDetection';
import QuickScan from '../components/widgets/QuickScan';
import ExploitWidget from '../components/widgets/ExploitWidget';
import AIAnalysis from '../components/widgets/AIAnalysis';
import ThreatMap from '../components/widgets/ThreatMap';
import StatsWidget from '../components/widgets/StatsWidget';
import AlertCenter from '../components/widgets/AlertCenter';
import '../styles/widgets.css';

const Dashboard = () => {
  const { getStatus, getStats } = useLeviathanAPI();
  const [status, setStatus] = useState(null);
  const [stats, setStats] = useState(null);
  const [selectedCamera, setSelectedCamera] = useState(null);
  const [selectedAlert, setSelectedAlert] = useState(null);

  // Obtener estado y estadísticas
  useEffect(() => {
    const fetchData = async () => {
      try {
        const statusData = await getStatus();
        setStatus(statusData);
        
        const statsData = await getStats();
        setStats(statsData);
      } catch (err) {
        console.error('Error fetching dashboard data:', err);
      }
    };
    
    fetchData();
  }, [getStatus, getStats]);

  // Widgets a mostrar
  const widgets = [
    { 
      id: 'stats', 
      component: StatsWidget, 
      title: 'Estadísticas',
      visible: true 
    },
    { 
      id: 'camera', 
      component: CameraDetection, 
      title: 'Detección de Cámaras',
      visible: true 
    },
    { 
      id: 'quickScan', 
      component: QuickScan, 
      title: 'Escaneo Rápido',
      visible: true 
    },
    { 
      id: 'exploit', 
      component: ExploitWidget, 
      title: 'Explotación Rápida',
      visible: true 
    },
    { 
      id: 'ai', 
      component: AIAnalysis, 
      title: 'Análisis con IA',
      visible: true 
    },
    { 
      id: 'threatMap', 
      component: ThreatMap, 
      title: 'Mapa de Amenazas',
      visible: true 
    },
    { 
      id: 'alerts', 
      component: AlertCenter, 
      title: 'Centro de Alertas',
      visible: true 
    }
  ];

  return (
    <div className="dashboard">
      {/* Header */}
      <div className="dashboard-header mb-4">
        <h1 className="text-2xl font-bold">
          <span>🦑 </span>
          LEVIATHAN Dashboard
        </h1>
        <p className="text-secondary mt-1">
          Sistema de Red Team Automatizado - Visión General
        </p>
      </div>

      {/* Estado del Sistema */}
      <div className="system-status-card card mb-4">
        <div className="flex justify-between align-center">
          <div>
            <h3 className="text-lg font-semibold">Estado del Sistema</h3>
            <p className="text-secondary text-sm">
              Todos los módulos operativos
            </p>
          </div>
          <div className="flex gap-3">
            {status && (
              <>
                <div className={`system-status-item ${status.leviathan === 'active' ? 'active' : 'inactive'}`}>
                  <span className="status-dot" />
                  <span>LEVIATHAN</span>
                </div>
                <div className={`system-status-item ${status.commander === 'active' ? 'active' : 'inactive'}`}>
                  <span className="status-dot" />
                  <span>Commander</span>
                </div>
                <div className={`system-status-item ${status.arto === 'active' ? 'active' : 'inactive'}`}>
                  <span className="status-dot" />
                  <span>ARTO</span>
                </div>
                <div className={`system-status-item ${status.seal === 'active' ? 'active' : 'inactive'}`}>
                  <span className="status-dot" />
                  <span>SEAL</span>
                </div>
                <div className={`system-status-item ${status.kraken === 'active' ? 'active' : 'inactive'}`}>
                  <span className="status-dot" />
                  <span>KRAKEN</span>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Grid de Widgets */}
      <div className="widgets-grid">
        {widgets.map((widget) => (
          widget.visible && (
            <div key={widget.id} className="widget-container">
              {React.createElement(widget.component, {
                onCameraSelect: widget.id === 'camera' ? setSelectedCamera : undefined,
                onAlertSelect: widget.id === 'alerts' ? setSelectedAlert : undefined,
                target: selectedCamera?.ip
              })}
            </div>
          )
        ))}
      </div>

      {/* CSS para el dashboard */}
      <style jsx>{`
        .dashboard {
          padding: var(--spacing-lg);
          animation: fadeIn 0.5s ease-out;
        }

        .dashboard-header {
          text-align: center;
        }

        .system-status-card {
          background: var(--gradient-card);
          border: 1px solid var(--border);
        }

        .system-status-item {
          display: flex;
          align-items: center;
          gap: var(--spacing-xs);
          padding: var(--spacing-xs) var(--spacing-md);
          background: var(--bg-secondary);
          border-radius: var(--radius-sm);
          font-size: 0.8rem;
        }

        .system-status-item.active .status-dot {
          background: var(--success);
        }

        .system-status-item.inactive .status-dot {
          background: var(--danger);
        }

        .widgets-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
          gap: var(--spacing-lg);
        }

        .widget-container {
          min-height: 300px;
        }

        @media (max-width: 1200px) {
          .widgets-grid {
            grid-template-columns: repeat(2, 1fr);
          }
        }

        @media (max-width: 768px) {
          .dashboard {
            padding: var(--spacing-sm);
          }
          
          .widgets-grid {
            grid-template-columns: 1fr;
          }
          
          .system-status-card {
            flex-direction: column;
            gap: var(--spacing-md);
          }
          
          .system-status-card .flex.justify-between {
            flex-direction: column;
          }
          
          .system-status-card .flex.gap-3 {
            flex-wrap: wrap;
          }
        }
      `}</style>
    </div>
  );
};

export default Dashboard;
