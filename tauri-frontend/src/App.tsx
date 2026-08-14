import { useState } from 'react';
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
import MotorMetricsDashboard from './components/MotorMetricsDashboard';
import MotorPanel from './components/MotorPanel';
import ControlTower from './components/ControlTower';
import ServiceControlPanel from './components/ServiceControlPanel';
import ConfigEditor from './routes/ConfigEditor';
import { MurcielagoPanel } from './components/MurcielagoPanel';
import NetworkTopology from './components/NetworkTopology';

function App() {
  const [token, setToken] = useState(localStorage.getItem('api_token'));
  const [module, setModule] = useState('warroom');

  if (!token) return <BiometricLogin onLogin={setToken} />;

  return (
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
      {module === 'motor' && <MotorPanel />}
      {module === 'services' && <ServiceControlPanel />}
      {module === 'terminal' && (
        <div className="bg-black rounded-xl border border-slate-800 p-4 font-mono text-xs text-green-400 h-[70vh]">
          $ <span className="animate-pulse">_</span>
        </div>
      )}
      {module === 'tower' && <ControlTower />}
      {module === 'topology' && <NetworkTopology />}
      {module === 'settings' && <ConfigEditor />}
    </AppShell>
  );
}

export default App
