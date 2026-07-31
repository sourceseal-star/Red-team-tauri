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
import RASP from './routes/RASP'
import Terminal from './routes/Terminal'
import Settings from './routes/Settings'
import About from './routes/About'

function App() {
  return (
    <BrowserRouter>
      <div className="flex flex-col h-screen">
        <TopBar />
        <div className="flex flex-1 overflow-hidden">
          <Sidebar />
          <main className="flex-1 overflow-y-auto p-4 bg-background">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/config" element={<ConfigEditor />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/honeypot" element={<Honeypot />} />
              <Route path="/soar" element={<SOAR />} />
              <Route path="/tip" element={<ThreatIntel />} />
              <Route path="/rasp" element={<RASP />} />
              <Route path="/terminal" element={<Terminal />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/about" element={<About />} />
            </Routes>
          </main>
        </div>
        <BottomStatus />
      </div>
    </BrowserRouter>
  )
}

export default App