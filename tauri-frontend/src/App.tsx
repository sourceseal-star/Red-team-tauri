import { useState } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Sidebar } from './components/Sidebar'
import { TopBar } from './components/TopBar'
import { BottomStatus } from './components/BottomStatus'
import Dashboard from './routes/Dashboard'
import ConfigEditor from './routes/ConfigEditor'
import Reports from './routes/Reports'
import Honeypot from './routes/Honeypot'
import SOAR from './routes/SOAR'
import ThreatIntel from './routes/ThreatIntel'
import GeoIntel from './routes/GeoIntel'
import RASP from './routes/RASP'
import Terminal from './routes/Terminal'
import Settings from './routes/Settings'
import About from './routes/About'
import CameraCommandCenter from './components/CameraCommandCenter'
import TopologyMapFixed from './components/TopologyMapFixed'
import SalesCommandCenter from './routes/SalesCommandCenter'

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <BrowserRouter>
      <div className="flex flex-col h-screen">
        <TopBar onMenuClick={() => setSidebarOpen(true)} />
        <div className="flex flex-1 overflow-hidden">
          <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
          <main className="flex-1 overflow-y-auto p-2 sm:p-4 bg-background">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/config" element={<ConfigEditor />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/honeypot" element={<Honeypot />} />
              <Route path="/soar" element={<SOAR />} />
              <Route path="/tip" element={<ThreatIntel />} />
        <Route path="/geo" element={<GeoIntel />} />
              <Route path="/rasp" element={<RASP />} />
              <Route path="/terminal" element={<Terminal />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/about" element={<About />} />
              <Route path="/cameras" element={<CameraCommandCenter />} />
              <Route path="/topology" element={<TopologyMapFixed nodes={[]} />} />
              {/* Motor de Cierre — independiente */}
              <Route path="/ventas" element={<SalesCommandCenter />} />
            </Routes>
          </main>
        </div>
        <BottomStatus />
      </div>
    </BrowserRouter>
  )
}

export default App
