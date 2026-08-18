import { useState, useEffect } from 'react';
import { Camera, Scan, Shield, AlertTriangle, Play, Key, Save, Wifi } from 'lucide-react';
import { getApiKey } from '../lib/api';

function ccHeaders(): Record<string, string> {
  const key = getApiKey()
  return key ? { 'Authorization': `Bearer ${key}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' }
}

export default function CameraCommandCenter() {
  const [network, setNetwork] = useState('192.168.1');
  const [scanning, setScanning] = useState(false);
  const [cameras, setCameras] = useState<any[]>([]);
  const [selectedCam, setSelectedCam] = useState<any>(null);
  const [logs, setLogs] = useState<string[]>([]);

  const addLog = (msg: string) => setLogs(prev => [msg, ...prev].slice(0, 50));

  // Auto-detectar la subred REAL del dispositivo al montar -- antes el
  // campo quedaba fijo en '192.168.1' y si tu red real es otra (comun en
  // hotspots Android: 192.168.43.x, 192.168.49.x, etc.) el escaneo siempre
  // apuntaba a una red vacia y por eso nunca aparecian camaras/routers.
  useEffect(() => {
    fetch('/api/network/info', { headers: ccHeaders() })
      .then(r => r.json())
      .then(data => {
        if (data.subnet) {
          const prefix = data.subnet.split('/')[0].split('.').slice(0, 3).join('.');
          if (prefix) setNetwork(prefix);
        }
      })
      .catch(() => {});
  }, []);

  const runDiscovery = async () => {
    setScanning(true);
    setCameras([]);
    addLog(`🔍 Iniciando descubrimiento completo en ${network}.0/24...`);
    try {
      const res = await fetch('/api/enhanced/discover/all', {
        method: 'POST',
        headers: ccHeaders(),
        body: JSON.stringify({ network })
      });
      const data = await res.json();
      setCameras(data.cameras || []);
      addLog(`✅ ONVIF: ${data.onvif_found} | SSDP: ${data.ssdp_found} | Cámaras: ${data.cameras?.length}`);
    } catch (e) {
      addLog(`❌ Error: ${e}`);
    } finally {
      setScanning(false);
    }
  };

  const loadSaved = async () => {
    try {
      const res = await fetch('/api/enhanced/cameras', { headers: ccHeaders() });
      const data = await res.json();
      setCameras(data.cameras || []);
    } catch (e) { console.error(e); }
  };

  useEffect(() => { loadSaved(); }, []);

  return (
    <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 h-full">
      <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-3">
        <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
          <Camera size={18} className="text-red-400" />
          Camera Command Center
        </h2>
        <div className="flex items-center gap-2">
          <input 
            value={network} 
            onChange={e => setNetwork(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded px-3 py-1.5 text-xs text-slate-200 font-mono w-32"
            placeholder="192.168.1"
          />
          <button 
            onClick={runDiscovery}
            disabled={scanning}
            className="px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white text-xs rounded-lg flex items-center gap-1.5 disabled:opacity-50"
          >
            <Scan size={12} /> {scanning ? 'Escaneando...' : 'Descubrir Todo'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 h-[calc(100%-60px)]">
        {/* Lista de cámaras */}
        <div className="space-y-2 overflow-y-auto max-h-full">
          {cameras.map((cam, i) => (
            <div 
              key={i} 
              onClick={() => setSelectedCam(cam)}
              className={`p-3 rounded-lg border cursor-pointer transition-all ${
                selectedCam?.ip === cam.ip 
                  ? 'bg-red-900/20 border-red-600' 
                  : 'bg-slate-900 border-slate-700 hover:border-slate-600'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono text-sm text-slate-200">{cam.ip}:{cam.port}</span>
                {cam.vulnerable && (
                  <span className="text-[10px] bg-red-600 text-white px-1.5 py-0.5 rounded flex items-center gap-1">
                    <Key size={8} /> vulnerable
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2 text-[10px] text-slate-500">
                <span className="text-slate-400">{cam.brand || 'Unknown'}</span>
                {cam.credentials && <span className="text-amber-400">🔓 {cam.credentials}</span>}
              </div>
            </div>
          ))}
          {cameras.length === 0 && !scanning && (
            <div className="text-center text-slate-600 text-sm py-8">
              <Camera size={24} className="mx-auto mb-2 opacity-30" />
              No hay cámaras descubiertas.
            </div>
          )}
        </div>

        {/* Preview y detalles */}
        <div className="lg:col-span-2 space-y-3">
          {selectedCam ? (
            <>
              <div className="bg-black rounded-lg border border-slate-700 overflow-hidden aspect-video relative">
                {selectedCam.snapshot_url ? (
                  <img 
                    src={selectedCam.snapshot_url} 
                    alt="Camera Preview"
                    className="w-full h-full object-contain"
                    onError={(e) => {
                      (e.target as HTMLImageElement).src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">📷</text></svg>';
                    }}
                  />
                ) : (
                  <div className="flex items-center justify-center h-full text-slate-600 text-sm">
                    Sin snapshot disponible
                  </div>
                )}
                {selectedCam.vulnerable && (
                  <div className="absolute top-2 right-2 bg-red-600 text-white text-[10px] px-2 py-1 rounded flex items-center gap-1">
                    <AlertTriangle size={10} /> CREDENCIALES EXPUESTAS
                  </div>
                )}
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="bg-slate-900 rounded p-2 border border-slate-700">
                  <div className="text-slate-500 mb-1">IP / Puerto</div>
                  <div className="font-mono text-slate-200">{selectedCam.ip}:{selectedCam.port}</div>
                </div>
                <div className="bg-slate-900 rounded p-2 border border-slate-700">
                  <div className="text-slate-500 mb-1">Marca</div>
                  <div className="text-slate-200">{selectedCam.brand || 'Unknown'}</div>
                </div>
                <div className="bg-slate-900 rounded p-2 border border-slate-700">
                  <div className="text-slate-500 mb-1">RTSP</div>
                  <div className="font-mono text-cyan-400 truncate">{selectedCam.rtsp_url || 'N/A'}</div>
                </div>
                <div className="bg-slate-900 rounded p-2 border border-slate-700">
                  <div className="text-slate-500 mb-1">Credenciales</div>
                  <div className={`font-mono ${selectedCam.credentials ? 'text-red-400' : 'text-slate-600'}`}>
                    {selectedCam.credentials || 'No detectadas'}
                  </div>
                </div>
              </div>

              <div className="flex gap-2">
                {selectedCam.rtsp_url && (
                  <button className="flex-1 py-2 bg-cyan-600 hover:bg-cyan-500 text-white text-xs rounded-lg flex items-center justify-center gap-1">
                    <Play size={12} /> Ver Stream RTSP
                  </button>
                )}
                <button 
                  onClick={() => navigator.clipboard.writeText(JSON.stringify(selectedCam, null, 2))}
                  className="px-3 py-2 bg-slate-700 hover:bg-slate-600 text-white text-xs rounded-lg"
                >
                  <Save size={12} />
                </button>
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center h-64 text-slate-600 text-sm border border-slate-800 rounded-lg border-dashed">
              Selecciona una cámara para ver detalles
            </div>
          )}

          {/* Logs */}
          <div className="bg-slate-900 rounded-lg border border-slate-800 p-2 max-h-32 overflow-y-auto">
            <div className="text-[10px] text-slate-500 font-bold mb-1 flex items-center gap-1">
              <Wifi size={10} /> LOGS
            </div>
            {logs.map((log, i) => (
              <div key={i} className="text-[10px] font-mono text-slate-400">{log}</div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
