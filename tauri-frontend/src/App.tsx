import { useState } from 'react';
// El import de api.ts activa el interceptor global de fetch (injecta Bearer token)
import './lib/api';
import AppShell from './components/AppShell';
import WarRoom from './components/WarRoom';
import BiometricLogin from './components/BiometricLogin';
import CameraCommandCenter from './components/CameraCommandCenter';
import IntelPanel from './components/IntelPanel';
import ExploitMatrix from './components/ExploitMatrix';
import TrafficMonitor from './components/TrafficMonitor';
import OSINTPanel from './components/OSINTPanel';
import WiFiPanel from './components/WiFiPanel';
import BlackMirrorPanel from './components/BlackMirrorPanel';
import ControlTower from './components/ControlTower';
import ServiceControlPanel from './components/ServiceControlPanel';
import SystemSettings from './components/SystemSettings';
import { MurcielagoPanel } from './components/MurcielagoPanel';
import NetworkTopology from './components/NetworkTopology';
import Terminal from './routes/Terminal';
import OSINTAdvancedPanel from './components/OSINTAdvancedPanel';
import InterceptorAdvancedPanel from './components/InterceptorAdvancedPanel';
import { LanguageProvider } from './i18n/LanguageContext';

function App() {
  const [token, setToken] = useState(localStorage.getItem('api_token'));
  const [module, setModule] = useState('warroom');

  if (!token) return <BiometricLogin onLogin={setToken} />;

  return (
    <LanguageProvider>
    <AppShell activeModule={module} onNavigate={setModule}>
      {module === 'warroom' && <WarRoom />}
      {module === 'cameras' && <CameraCommandCenter />}
      {module === 'threat' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <IntelPanel />
          <ExploitMatrix />
          <TrafficMonitor />
        </div>
      )}
      {module === 'osint' && <OSINTPanel />}
      {module === 'wifi' && <WiFiPanel />}
      {module === 'ultra' && <MurcielagoPanel />}
      {module === 'blackmirror' && <BlackMirrorPanel />}
      {module === 'services' && <ServiceControlPanel />}
      {module === 'terminal' && <Terminal />}
      {module === 'tower' && <ControlTower />}
      {module === 'topology' && <NetworkTopology />}
      {module === 'settings' && <SystemSettings />}
      {module === 'osint_adv' && <OSINTAdvancedPanel />}
      {module === 'interceptor' && <InterceptorAdvancedPanel />}
    </AppShell>
    </LanguageProvider>
  );
}

export default App
