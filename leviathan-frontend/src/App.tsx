import React, { useEffect, useState } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useDispatch } from 'react-redux'
import { WebSocketProvider } from './api/websocket'
import Dashboard from './components/Dashboard'
import LiveGrid from './components/LiveGrid'
import ThreatMap from './components/ThreatMap'
import CameraViewer from './components/CameraViewer'
import KrakenPanel from './components/KrakenPanel'
import ScanControls from './components/ScanControls'
import AlertCenter from './components/AlertCenter'
import Sidebar from './components/Sidebar'
import Navbar from './components/Navbar'
import { AlertToast } from './components/AlertToast'
import { setTheme } from './store/slices/ui'
import { useWebSocket } from './hooks/useWebSocket'
import './App.css'

const App: React.FC = () => {
  const dispatch = useDispatch()
  const [isSidebarOpen, setIsSidebarOpen] = useState(true)
  const [activeAlerts, setActiveAlerts] = useState<any[]>([])
  
  // Cargar tema desde localStorage
  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') || 'dark'
    dispatch(setTheme(savedTheme))
  }, [dispatch])
  
  // Manejar alertas desde WebSocket
  const handleAlert = (alert: any) => {
    setActiveAlerts(prev => [...prev, alert])
    
    // Mostrar notificación toast
    if (alert.severity === 'critical' || alert.severity === 'high') {
      // En producción, usar notificación del navegador
      if (Notification.permission === 'granted') {
        new Notification(alert.title, {
          body: alert.description,
          icon: '/favicon.ico'
        })
      }
    }
  }
  
  // Conectar WebSocket
  const { connect, disconnect } = useWebSocket({
    onAlert: handleAlert
  })
  
  useEffect(() => {
    connect()
    return () => disconnect()
  }, [connect, disconnect])
  
  const toggleSidebar = () => {
    setIsSidebarOpen(!isSidebarOpen)
  }
  
  return (
    <WebSocketProvider>
      <div className="app-container">
        <Navbar toggleSidebar={toggleSidebar} />
        
        <div className="main-content">
          <Sidebar isOpen={isSidebarOpen} />
          
          <main className={`content ${isSidebarOpen ? 'sidebar-open' : 'sidebar-closed'}`}>
            <Routes>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/live" element={<LiveGrid />} />
              <Route path="/map" element={<ThreatMap />} />
              <Route path="/camera/:ip" element={<CameraViewer />} />
              <Route path="/kraken" element={<KrakenPanel />} />
              <Route path="/scan" element={<ScanControls />} />
              <Route path="/alerts" element={<AlertCenter alerts={activeAlerts} />} />
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </main>
        </div>
        
        {/* Toast de alertas */}
        <AlertToast alerts={activeAlerts} onDismiss={() => setActiveAlerts([])} />
      </div>
    </WebSocketProvider>
  )
}

export default App
