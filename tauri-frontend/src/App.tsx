import { BrowserRouter, Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import AppShell from './components/AppShell'

// ── Módulos "oficiales" del War Room completo (reconectados 2026-09-06) ──
import WarRoom from './components/dashboard/WarRoom'
import ControlTower from './components/ControlTower'
import OperationsPanel from './components/OperationsPanel'
import ServiceControlPanel from './components/ServiceControlPanel'
import NetworkMapPanel from './components/NetworkMapPanel'
import TopologyPanel from './components/TopologyPanel'
import WiFiPanel from './components/WiFiPanel'
import IoTCameras from './components/IoTCameras'
import NexusPanel from './components/NexusPanel'
import OSINTAdvancedPanel from './components/OSINTAdvancedPanel'
import InterceptorAdvancedPanel from './components/InterceptorAdvancedPanel'
import ARTOPanel from './components/ARTOPanel'
import { ARTOProvider } from './components/ARTOProvider'
import BlackMirrorPanel from './components/BlackMirrorPanel'
import KrakenPanel from './components/KrakenPanel'
import LeviathanPanel from './components/LeviathanPanel'
import InterceptorSealPanel from './components/SealPanel'
import CommanderPanel from './components/CommanderPanel'
import ComlinkPanel from './components/ComlinkPanel'
import EmergencyRoomPanel from './components/EmergencyRoomPanel'
import AndroidFieldPanel from './components/AndroidFieldPanel'
import TacticalPanel from './components/TacticalPanel'
import IntegratedPanel from './components/IntegratedPanel'
import AlertsPanel from './components/AlertsPanel'
import ExportPanel from './components/ExportPanel'
import CameraCommandCenter from './components/CameraCommandCenter'
import dashboardUltrasonicPanel from './components/dashboard/UltrasonicPanel'

// ── Rutas que YA existían y funcionaban — se conservan tal cual, ──
// ── ahora dentro del mismo War Room en vez de un sidebar aparte.  ──
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
import SalesCommandCenter from './routes/SalesCommandCenter'

// Mapa id (sidebar de AppShell) → ruta URL real.
// Los ids vienen de MODULES en components/AppShell.tsx — NINGUNO se quitó,
// solo se les asignó una página real detrás.
const ID_TO_PATH: Record<string, string> = {
  warroom: '/', cameras: '/cameras', threat: '/tip', osint: '/kraken',
  wifi: '/wifi', ultra: '/ultra', blackmirror: '/blackmirror',
  services: '/services', terminal: '/terminal', tower: '/tower',
  commander: '/commander', comlink: '/comlink', emergency: '/emergency',
  netmap: '/netmap', nexus: '/nexus', integrated: '/integrated',
  operations: '/operations', android: '/android', tactical: '/tactical',
  topology: '/topology', iot: '/iot', alerts: '/alerts', export: '/export',
  settings: '/config', osint_adv: '/osint-adv', interceptor: '/interceptor',
  arto: '/arto', seal: '/seal', leviathan: '/leviathan',
  reports: '/reports', deception: '/honeypot', soar: '/soar', geo: '/geo',
  rasp: '/rasp', ventas: '/ventas', sysconfig: '/settings', about: '/about',
};
const PATH_TO_ID: Record<string, string> = Object.fromEntries(
  Object.entries(ID_TO_PATH).map(([id, path]) => [path, id])
);

function Shell() {
  const navigate = useNavigate();
  const location = useLocation();
  const activeModule = PATH_TO_ID[location.pathname] || 'warroom';

  return (
    <AppShell activeModule={activeModule} onNavigate={(id) => navigate(ID_TO_PATH[id] || '/')}>
      <Routes>
        {/* ── War Room completo — 29 módulos originales ── */}
        <Route path="/" element={<WarRoom />} />
        <Route path="/cameras" element={<CameraCommandCenter />} />
        <Route path="/tip" element={<ThreatIntel />} />
        <Route path="/kraken" element={<KrakenPanel />} />
        <Route path="/wifi" element={<WiFiPanel />} />
        <Route path="/ultra" element={<dashboardUltrasonicPanel />} />
        <Route path="/blackmirror" element={<BlackMirrorPanel />} />
        <Route path="/services" element={<ServiceControlPanel />} />
        <Route path="/terminal" element={<Terminal />} />
        <Route path="/tower" element={<ControlTower />} />
        <Route path="/commander" element={<CommanderPanel />} />
        <Route path="/comlink" element={<ComlinkPanel />} />
        <Route path="/emergency" element={<EmergencyRoomPanel />} />
        <Route path="/netmap" element={<NetworkMapPanel />} />
        <Route path="/nexus" element={<NexusPanel />} />
        <Route path="/integrated" element={<IntegratedPanel />} />
        <Route path="/operations" element={<OperationsPanel />} />
        <Route path="/android" element={<AndroidFieldPanel />} />
        <Route path="/tactical" element={<TacticalPanel />} />
        <Route path="/topology" element={<TopologyPanel />} />
        <Route path="/iot" element={<IoTCameras />} />
        <Route path="/alerts" element={<AlertsPanel />} />
        <Route path="/export" element={<ExportPanel />} />
        <Route path="/config" element={<ConfigEditor />} />
        <Route path="/osint-adv" element={<OSINTAdvancedPanel />} />
        <Route path="/interceptor" element={<InterceptorAdvancedPanel />} />
        <Route path="/arto" element={<ARTOProvider><ARTOPanel /></ARTOProvider>} />
        <Route path="/seal" element={<InterceptorSealPanel />} />
        <Route path="/leviathan" element={<LeviathanPanel />} />

        {/* ── Rutas ya existentes — conservadas, ahora sumadas al menú ── */}
        <Route path="/reports" element={<Reports />} />
        <Route path="/honeypot" element={<Honeypot />} />
        <Route path="/soar" element={<SOAR />} />
        <Route path="/geo" element={<GeoIntel />} />
        <Route path="/rasp" element={<RASP />} />
        <Route path="/ventas" element={<SalesCommandCenter />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/about" element={<About />} />

        {/* Dashboard simple original — se conserva en su propia ruta, no se borra */}
        <Route path="/dashboard-simple" element={<Dashboard />} />
      </Routes>
    </AppShell>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Shell />
    </BrowserRouter>
  )
}

export default App
