import React, { useEffect, useState } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { Provider, useDispatch } from 'react-redux'
import { store } from './store'
import { setTheme } from './store/slices/ui'
import { WebSocketProvider } from './api/websocket'
import Dashboard from './components/Dashboard'
import LiveGrid from './components/LiveGrid'
import ThreatMap from './components/ThreatMap'
import CameraViewer from './components/CameraViewer'
import KrakenPanel from './components/KrakenPanel'
import AlertCenter from './components/AlertCenter'
import Sidebar from './components/Sidebar'
import Navbar from './components/Navbar'
import { AlertToast } from './components/AlertToast'
import { useWebSocket } from './hooks/useWebSocket'
import './App.css'

const AppContent: React.FC = () => {
  const dispatch = useDispatch()
  const [isSidebarOpen, setIsSidebarOpen] = useState(true)
  const [activeAlerts, setActiveAlerts] = useState<any[]>([])

  useEffect(() => {
    const savedTheme = (localStorage.getItem('theme') as 'dark' | 'light') || 'dark'
    dispatch(setTheme(savedTheme))
  }, [dispatch])

  const handleAlert = (alert: any) => {
    setActiveAlerts(prev => [...prev, alert])
    if (alert.severity === 'critical' || alert.severity === 'high') {
      if (Notification.permission === 'granted') {
        new Notification(alert.title, { body: alert.description })
      }
    }
  }

  const { connect, disconnect } = useWebSocket({ onAlert: handleAlert })

  useEffect(() => {
    connect()
    return () => disconnect()
  }, [connect, disconnect])

  const toggleSidebar = () => setIsSidebarOpen(!isSidebarOpen)

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
              <Route path="/scan" element={<Dashboard />} />
              <Route path="/alerts" element={<AlertCenter alerts={activeAlerts} />} />
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </main>
        </div>
        <AlertToast alerts={activeAlerts} onDismiss={() => setActiveAlerts([])} />
      </div>
    </WebSocketProvider>
  )
}

const App: React.FC = () => (
  <Provider store={store}>
    <AppContent />
  </Provider>
)

export default App
