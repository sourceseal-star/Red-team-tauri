import { useState, useEffect } from 'react';
// El import de api.ts activa el interceptor global de fetch (injecta Bearer token)
import './lib/api';
import AppShell from './components/AppShell';
import WarRoom from './components/WarRoom';
import BiometricLogin from './components/BiometricLogin';
import CameraCommandCenter from './components/CameraCommandCenter';
import IntelPanel from './components/IntelPanel';
import ExploitMatrix from './components/ExploitMatrix';
import TrafficMonitor from './components/TrafficMonitor';
import KrakenPanel from './components/KrakenPanel';
import WiFiPanel from './components/WiFiPanel';
import BlackMirrorPanel from './components/BlackMirrorPanel';
import ControlTower from './components/ControlTower';
import ServiceControlPanel from './components/ServiceControlPanel';
import SystemSettings from './components/SystemSettings';
import { MurcielagoPanel } from './components/MurcielagoPanel';
import TopologyPanel from './components/TopologyPanel';
import IoTCameras from './components/IoTCameras';
import AlertsPanel from './components/AlertsPanel';
import ExportPanel from './components/ExportPanel';
// NetworkTopology reemplazado por TopologyPanel (v4 merge)
import Terminal from './routes/Terminal';
import OSINTAdvancedPanel from './components/OSINTAdvancedPanel';
import InterceptorAdvancedPanel from './components/InterceptorAdvancedPanel';
import { LanguageProvider } from './i18n/LanguageContext';
import { ARTOProvider } from './components/ARTOProvider';
import ARTOPanel from './components/ARTOPanel';
import SealPanel from './components/SealPanel';
import LeviathanPanel from './components/LeviathanPanel';
import CommanderPanel from './components/CommanderPanel';
import NetworkMapPanel from './components/NetworkMapPanel';
import AndroidFieldPanel from './components/AndroidFieldPanel';
import NexusPanel from './components/NexusPanel';
import ComlinkPanel from './components/ComlinkPanel';
import EmergencyRoomPanel from './components/EmergencyRoomPanel';
import OperationsPanel from './components/OperationsPanel';
import IntegratedPanel from './components/IntegratedPanel';
import TacticalPanel from './components/TacticalPanel';
import { FloatingSol } from './components/FloatingSol';

function App() {
  const [token, setToken] = useState(localStorage.getItem('api_token'));
  const [module, setModule] = useState('warroom');

  // Si nos llegaron directo por /sol.html o /sol (link viejo, marcador,
  // sidebar cacheado), abrimos la videollamada de Sol automaticamente
  // en vez de mostrar el War Room. No hay pagina de Sol aparte -- Sol
  // vive encima de todo el dashboard vía FloatingSol.
  useEffect(() => {
    const path = window.location.pathname;
    if (path === '/sol.html' || path === '/sol') {
      window.history.replaceState({}, '', '/');
      const fire = () => window.dispatchEvent(new CustomEvent('sol-expand'));
      setTimeout(fire, 300);
    }
  }, []);

  if (!token) return <BiometricLogin onLogin={setToken} />;

  return (
    <LanguageProvider>
    <ARTOProvider>
    <AppShell activeModule={module} onNavigate={setModule}>
      {module === 'warroom' && <WarRoom onNavigate={setModule} />}
      {module === 'cameras' && <CameraCommandCenter />}
      {module === 'threat' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <IntelPanel />
          <ExploitMatrix />
          <TrafficMonitor />
        </div>
      )}
      {module === 'osint' && <KrakenPanel />}
      {module === 'wifi' && <WiFiPanel />}
      {module === 'ultra' && <MurcielagoPanel />}
      {module === 'blackmirror' && <BlackMirrorPanel />}
      {module === 'services' && <ServiceControlPanel />}
      {module === 'terminal' && <Terminal />}
      {module === 'tower' && <ControlTower />}
      {module === 'topology' && <TopologyPanel />}
      {module === 'iot' && <IoTCameras />}
      {module === 'alerts' && <AlertsPanel />}
      {module === 'export' && <ExportPanel />}
      {module === 'settings' && <SystemSettings />}
      {module === 'osint_adv' && <OSINTAdvancedPanel />}
      {module === 'interceptor' && <InterceptorAdvancedPanel />}
      {module === 'arto' && <ARTOPanel />}
      {module === 'seal' && <SealPanel />}
      {module === 'leviathan' && <LeviathanPanel />}
      {module === 'commander' && <CommanderPanel />}
      {module === 'comlink' && <ComlinkPanel />}
      {module === 'emergency' && <EmergencyRoomPanel />}
      {module === 'netmap' && <NetworkMapPanel />}
      {module === 'nexus' && <NexusPanel />}
      {module === 'integrated' && <IntegratedPanel />}
      {module === 'operations' && <OperationsPanel />}
      {module === 'android' && <AndroidFieldPanel />}
      {module === 'tactical' && <TacticalPanel />}
    </AppShell>
    <FloatingSol />
    </ARTOProvider>
    </LanguageProvider>
  );
}

export default App
