import React, { useEffect, useState } from 'react'
import { useSelector, useDispatch } from 'react-redux'
import { RootState, AppDispatch } from '../store'
import { fetchCameras } from '../store/slices/cameras'
import { fetchScans } from '../store/slices/scans'
import { fetchAlerts } from '../store/slices/alerts'
import { useWebSocket } from '../hooks/useWebSocket'
import CameraCard from './CameraCard'
import ThreatCard from './ThreatCard'
import AlertCenter from './AlertCenter'
import ScanControls from './ScanControls'
import Chart from 'chart.js/auto'
import { Doughnut, Bar, Line } from 'react-chartjs-2'

const Dashboard: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>()
  const { cameras, loading: camerasLoading } = useSelector((state: RootState) => state.cameras)
  const { scans, loading: scansLoading } = useSelector((state: RootState) => state.scans)
  const { alerts, loading: alertsLoading } = useSelector((state: RootState) => state.alerts)
  const { theme } = useSelector((state: RootState) => state.ui)
  
  const [stats, setStats] = useState({
    totalCameras: 0,
    accessibleCameras: 0,
    vulnerableCameras: 0,
    totalScans: 0,
    activeScans: 0,
    totalAlerts: 0,
    criticalAlerts: 0
  })
  
  // Cargar datos al montar
  useEffect(() => {
    dispatch(fetchCameras())
    dispatch(fetchScans())
    dispatch(fetchAlerts())
  }, [dispatch])
  
  // Actualizar estadísticas
  useEffect(() => {
    setStats({
      totalCameras: cameras.length,
      accessibleCameras: cameras.filter(c => c.is_accessible).length,
      vulnerableCameras: cameras.filter(c => c.is_vulnerable).length,
      totalScans: scans.length,
      activeScans: scans.filter(s => s.status === 'running').length,
      totalAlerts: alerts.length,
      criticalAlerts: alerts.filter(a => a.severity === 'critical').length
    })
  }, [cameras, scans, alerts])
  
  // Configuración de gráficos
  const getChartColors = () => ({
    primary: theme === 'dark' ? '#667eea' : '#667eea',
    secondary: theme === 'dark' ? '#764ba2' : '#764ba2',
    success: theme === 'dark' ? '#28a745' : '#28a745',
    danger: theme === 'dark' ? '#dc3545' : '#dc3545',
    warning: theme === 'dark' ? '#ffc107' : '#ffc107',
    info: theme === 'dark' ? '#17a2b8' : '#17a2b8'
  })
  
  // Datos para gráficos
  const cameraStatusData = {
    labels: ['Accesibles', 'No Accesibles', 'Vulnerables'],
    datasets: [{
      data: [
        stats.accessibleCameras,
        stats.totalCameras - stats.accessibleCameras,
        stats.vulnerableCameras
      ],
      backgroundColor: [
        getChartColors().success,
        getChartColors().warning,
        getChartColors().danger
      ],
      borderWidth: 0
    }]
  }
  
  const severityData = {
    labels: ['Crítico', 'Alto', 'Medio', 'Bajo'],
    datasets: [{
      label: 'Alertas por Severidad',
      data: [
        alerts.filter(a => a.severity === 'critical').length,
        alerts.filter(a => a.severity === 'high').length,
        alerts.filter(a => a.severity === 'medium').length,
        alerts.filter(a => a.severity === 'low').length
      ],
      backgroundColor: [
        getChartColors().danger,
        getChartColors().warning,
        getChartColors().info,
        getChartColors().success
      ]
    }]
  }
  
  const vendorData = {
    labels: ['Hikvision', 'Dahua', 'Axis', 'Otros'],
    datasets: [{
      label: 'Cámaras por Vendor',
      data: [
        cameras.filter(c => c.vendor?.toLowerCase().includes('hikvision')).length,
        cameras.filter(c => c.vendor?.toLowerCase().includes('dahua')).length,
        cameras.filter(c => c.vendor?.toLowerCase().includes('axis')).length,
        cameras.filter(c => !['hikvision', 'dahua', 'axis'].some(v => c.vendor?.toLowerCase().includes(v))).length
      ],
      backgroundColor: [
        getChartColors().primary,
        getChartColors().secondary,
        getChartColors().info,
        getChartColors().warning
      ]
    }]
  }
  
  // Opciones de gráficos
  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'bottom' as const,
        labels: {
          color: theme === 'dark' ? '#e0e0e0' : '#333'
        }
      }
    },
    scales: {
      y: {
        beginAtZero: true,
        ticks: {
          color: theme === 'dark' ? '#e0e0e0' : '#333'
        },
        grid: {
          color: theme === 'dark' ? '#404040' : '#ddd'
        }
      },
      x: {
        ticks: {
          color: theme === 'dark' ? '#e0e0e0' : '#333'
        },
        grid: {
          color: theme === 'dark' ? '#404040' : '#ddd'
        }
      }
    }
  }
  
  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1>🎯 Dashboard de LEVIATHAN</h1>
        <p className="dashboard-subtitle">
          Sistema de Red Team Automatizado - Visión General
        </p>
      </div>
      
      {/* Estadísticas principales */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon camera">🎥</div>
          <div className="stat-info">
            <span className="stat-number">{stats.totalCameras}</span>
            <span className="stat-label">Cámaras Detectadas</span>
          </div>
        </div>
        
        <div className="stat-card">
          <div className="stat-icon accessible">🔓</div>
          <div className="stat-info">
            <span className="stat-number">{stats.accessibleCameras}</span>
            <span className="stat-label">Accesibles</span>
          </div>
        </div>
        
        <div className="stat-card">
          <div className="stat-icon vulnerable">⚠️</div>
          <div className="stat-info">
            <span className="stat-number">{stats.vulnerableCameras}</span>
            <span className="stat-label">Vulnerables</span>
          </div>
        </div>
        
        <div className="stat-card">
          <div className="stat-icon alerts">🔔</div>
          <div className="stat-info">
            <span className="stat-number">{stats.totalAlerts}</span>
            <span className="stat-label">Alertas Activas</span>
          </div>
        </div>
        
        <div className="stat-card">
          <div className="stat-icon scans">🔍</div>
          <div className="stat-info">
            <span className="stat-number">{stats.activeScans}</span>
            <span className="stat-label">Escaneos Activos</span>
          </div>
        </div>
      </div>
      
      {/* Gráficos */}
      <div className="charts-row">
        <div className="chart-card">
          <h3>📊 Estado de Cámaras</h3>
          <div className="chart-container doughnut">
            <Doughnut data={cameraStatusData} options={chartOptions} />
          </div>
        </div>
        
        <div className="chart-card">
          <h3>⚠️ Alertas por Severidad</h3>
          <div className="chart-container bar">
            <Bar data={severityData} options={chartOptions} />
          </div>
        </div>
      </div>
      
      <div className="charts-row">
        <div className="chart-card">
          <h3>🏭 Cámaras por Vendor</h3>
          <div className="chart-container doughnut">
            <Doughnut data={vendorData} options={chartOptions} />
          </div>
        </div>
      </div>
      
      {/* Controles de escaneo */}
      <div className="section">
        <h2>🚀 Controles de Escaneo</h2>
        <ScanControls />
      </div>
      
      {/* Últimas cámaras detectadas */}
      <div className="section">
        <h2>🎥 Últimas Cámaras Detectadas</h2>
        {camerasLoading ? (
          <div className="loading">Cargando cámaras...</div>
        ) : cameras.length > 0 ? (
          <div className="camera-grid">
            {cameras.slice(0, 6).map(camera => (
              <CameraCard key={`${camera.ip}-${camera.port}`} camera={camera} />
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <p>No se han detectado cámaras aún.</p>
            <p>Ejecuta un escaneo para comenzar.</p>
          </div>
        )}
      </div>
      
      {/* Últimas alertas */}
      <div className="section">
        <h2>🔔 Últimas Alertas</h2>
        {alertsLoading ? (
          <div className="loading">Cargando alertas...</div>
        ) : alerts.length > 0 ? (
          <AlertCenter alerts={alerts.slice(0, 5)} showAllLink={true} />
        ) : (
          <div className="empty-state">
            <p>No hay alertas activas.</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default Dashboard
