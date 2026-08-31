import { useState, useEffect, useCallback } from 'react';
import { Camera, Scan, Shield, AlertTriangle, Play, Key, Save, Wifi,
         RefreshCw, Globe, Video, Link2, Lock, Unlock, Server, Eye } from 'lucide-react';
import { getApiKey } from '../lib/api';

function ccHeaders(json = false): Record<string, string> {
  const key = getApiKey()
  const h: Record<string, string> = {}
  if (key) h['Authorization'] = `Bearer ${key}`
  if (json) h['Content-Type'] = 'application/json'
  return h
}

export default function CameraCommandCenter() {
  const [network, setNetwork] = useState('192.168.1')
  const [customPorts, setCustomPorts] = useState('')
  const [scanning, setScanning] = useState(false)
  const [cameras, setCameras] = useState<any[]>([])
  const [hosts, setHosts] = useState<any[]>([])
  const [onvifDetails, setOnvifDetails] = useState<any[]>([])
  const [ssdpDetails, setSsdpDetails] = useState<any[]>([])
  const [selectedCam, setSelectedCam] = useState<any>(null)
  const [logs, setLogs] = useState<string[]>([])
  const [videoUrls, setVideoUrls] = useState<any[]>([])
  const [loadingUrls, setLoadingUrls] = useState(false)
  const [batchResults, setBatchResults] = useState<any[]>([])
  const [batchScanning, setBatchScanning] = useState(false)
  const [batchSummary, setBatchSummary] = useState<any>(null)

  const addLog = (msg: string) => setLogs(prev => [msg, ...prev].slice(0, 50))

  // Auto-detectar la subred REAL del dispositivo al montar
  useEffect(() => {
    fetch('/api/network/info', { headers: ccHeaders() })
      .then(r => r.json())
      .then(data => {
        if (data.subnet) {
          const prefix = data.subnet.split('/')[0].split('.').slice(0, 3).join('.')
          if (prefix) setNetwork(prefix)
        }
      })
      .catch(() => {})
  }, [])

  const loadSaved = useCallback(async () => {
    try {
      const res = await fetch('/api/enhanced/cameras', { headers: ccHeaders() })
      const data = await res.json()
      setCameras(data.cameras || [])
    } catch (e) { console.error(e) }
  }, [])

  useEffect(() => { loadSaved() }, [loadSaved])

  // Cuando se selecciona una camara, cargar sus URLs de video detalladas
  useEffect(() => {
    if (!selectedCam) { setVideoUrls([]); return }
    setLoadingUrls(true)
    setVideoUrls([])
    fetch(`/api/iot/video-urls?ip=${selectedCam.ip}&port=${selectedCam.port || 80}`, { headers: ccHeaders() })
      .then(r => r.json())
      .then(data => { setVideoUrls(data.sources || []); })
      .catch(() => {})
      .finally(() => setLoadingUrls(false))
  }, [selectedCam])

  const runDiscovery = async () => {
    setScanning(true)
    setCameras([])
    setHosts([])
    setOnvifDetails([])
    setSsdpDetails([])
    addLog(`Iniciando descubrimiento en ${network}.0/24${customPorts ? ' + puertos: ' + customPorts : ''}...`)
    try {
      // Escaneo batch: procesa TODAS las cámaras de la red
  const scanAll = async () => {
    setBatchScanning(true)
    setBatchResults([])
    setBatchSummary(null)
    addLog('Iniciando escaneo batch de red completa...')
    try {
      const cidr = network.includes('.') && !network.includes('/') 
        ? network + '.0/24' 
        : network.includes('/') ? network : '192.168.1.0/24'
      const res = await fetch('/api/iot/auto-access-batch', {
        method: 'POST',
        headers: ccHeaders(),
        body: JSON.stringify({ cidr })
      })
      const data = await res.json()
      setBatchResults(data.cameras || [])
      setBatchSummary(data.summary || null)
      addLog(`Batch completo: ${data.cameras_found} cámaras encontradas, ${data.summary?.full_access || 0} con acceso completo`)
    } catch (e) {
      addLog('Error en batch scan: ' + String(e))
    } finally {
      setBatchScanning(false)
    }
  }

  const res = await fetch('/api/enhanced/discover/all', {
        method: 'POST',
        headers: ccHeaders(true),
        body: JSON.stringify({ network, custom_ports: customPorts || undefined })
      })
      const data = await res.json()
      setCameras(data.cameras || [])
      setHosts(data.hosts || [])
      setOnvifDetails(data.onvif_details || [])
      setSsdpDetails(data.ssdp_details || [])
      addLog(`ONVIF: ${data.onvif_found} | SSDP: ${data.ssdp_found} | Camaras: ${data.cameras?.length || 0} | Hosts: ${data.hosts?.length || 0}`)
    } catch (e: any) {
      addLog(`Error: ${e.message || e}`)
    } finally {
      setScanning(false)
    }
  }

  const copyCam = () => {
    if (selectedCam) navigator.clipboard.writeText(JSON.stringify(selectedCam, null, 2))
  }

  const renderUrlRow = (url: string, label: string, icon: React.ReactNode, clickable = true) => {
    if (!url) return null
    return (
      <div className="flex items-center gap-2 text-[10px] font-mono py-1 px-2 rounded hover:bg-slate-800/50 transition" key={label}>
        {icon}
        <span className="text-slate-500 shrink-0 w-16">{label}</span>
        <span className="text-cyan-400 truncate flex-1">{url}</span>
        {clickable && (
          <a href={url} target="_blank" rel="noopener noreferrer"
             className="text-slate-500 hover:text-cyan-400 transition shrink-0">
            <Link2 size={10} />
          </a>
        )}
        <button
          onClick={() => navigator.clipboard.writeText(url)}
          className="text-slate-600 hover:text-cyan-400 transition shrink-0"
          title="Copiar URL"
        >
          <Save size={9} />
        </button>
      </div>
    )
  }

  // Recolectar todas las URLs relevantes de la camara seleccionada
  const allUrls: {url: string, label: string, icon: React.ReactNode}[] = []
  if (selectedCam) {
    // URLs del descubrimiento enhanced
    if (selectedCam.rtsp_working)
      allUrls.push({url: selectedCam.rtsp_working, label: 'RTSP', icon: <Video size={11} className="text-cyan-400 shrink-0" />})
    if (selectedCam.snapshot_url)
      allUrls.push({url: selectedCam.snapshot_url, label: 'Snapshot', icon: <Camera size={11} className="text-amber-400 shrink-0" />})
    // accessible_urls del enhanced recon
    if (selectedCam.accessible_urls) {
      for (const u of selectedCam.accessible_urls) {
        if (typeof u === 'string') {
          allUrls.push({url: u, label: 'Feed', icon: <Link2 size={11} className="text-green-400 shrink-0" />})
        } else if (u?.url) {
          allUrls.push({url: u.url, label: u.type || 'Feed', icon: <Link2 size={11} className="text-green-400 shrink-0" />})
        }
      }
    }
    // ONVIF
    if (selectedCam.onvif_url || (selectedCam.port && [80, 8000, 8080].includes(selectedCam.port)))
      allUrls.push({url: `http://${selectedCam.ip}:${selectedCam.port || 80}/onvif/device_service`, label: 'ONVIF', icon: <Globe size={11} className="text-purple-400 shrink-0" />})
    // HTTP
    allUrls.push({url: `http://${selectedCam.ip}:${selectedCam.port || 80}`, label: 'HTTP', icon: <Globe size={11} className="text-slate-400 shrink-0" />})
  }

  // Agregar URLs del endpoint /api/iot/video-urls
  for (const src of videoUrls) {
    if (src.snapshot_url)
      allUrls.push({url: src.snapshot_url, label: `Snapshot (${src.type})`, icon: <Camera size={11} className="text-amber-400 shrink-0" />})
    if (src.stream_url)
      allUrls.push({url: src.stream_url, label: `MJPEG (${src.type})`, icon: <Video size={11} className="text-green-400 shrink-0" />})
    if (src.rtsp_url && !allUrls.some(u => u.url === src.rtsp_url))
      allUrls.push({url: src.rtsp_url, label: 'RTSP', icon: <Video size={11} className="text-cyan-400 shrink-0" />})
  }

  return (
    <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-3 flex-wrap gap-2 min-w-0">
        <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2 w-full sm:w-auto min-w-0">
          <Camera size={18} className="text-red-400" />
          <span className="truncate">Camera Command Center</span>
        </h2>
        <div className="flex items-center gap-2 flex-wrap w-full sm:w-auto min-w-0">
          <input
            value={network}
            onChange={e => setNetwork(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded px-3 py-1.5 text-xs text-slate-200 font-mono w-28 max-w-full"
            placeholder="192.168.1"
            title="Prefijo de red (ej: 192.168.1)"
          />
          <input
            value={customPorts}
            onChange={e => setCustomPorts(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded px-3 py-1.5 text-xs text-slate-200 font-mono w-36 max-w-full"
            placeholder="Puertos extra (ej: 554,9999)"
            title="Puertos adicionales separados por coma. Ej: 554,8554,37777,9999"
          />
          <button
            onClick={runDiscovery}
            disabled={scanning}
            className="px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white text-xs rounded-lg flex items-center gap-1.5 disabled:opacity-50 whitespace-nowrap"
          >
            {scanning ? <RefreshCw size={12} className="animate-spin" /> : <Scan size={12} />}
            {scanning ? 'Escaneando...' : 'Descubrir Todo'}
          </button>
          <button
            onClick={loadSaved}
            className="px-2 py-1.5 border border-slate-700 text-slate-400 hover:text-cyan-400 text-xs rounded-lg flex items-center gap-1"
            title="Recargar camaras guardadas"
          >
            <RefreshCw size={12} />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 flex-1 min-h-0">
        {/* Lista de camaras y hosts */}
        <div className="space-y-2 overflow-y-auto">
          {/* Camaras */}
          {cameras.length > 0 && (
            <div>
              <div className="text-[9px] uppercase tracking-widest text-red-400 font-mono mb-1 flex items-center gap-1">
                <Camera size={10} /> Camaras ({cameras.length})
              </div>
              {cameras.map((cam, i) => (
                <div
                  key={`cam-${i}`}
                  onClick={() => setSelectedCam(cam)}
                  className={`p-2.5 rounded-lg border cursor-pointer transition-all mb-1.5 ${
                    selectedCam?.ip === cam.ip
                      ? 'bg-red-900/20 border-red-600'
                      : 'bg-slate-900 border-slate-700 hover:border-slate-600'
                  }`}
                >
                  <div className="flex items-center justify-between mb-0.5">
                    <span className="font-mono text-xs text-slate-200">{cam.ip}:{cam.port || 554}</span>
                    {cam.working_credentials && (
                      <span className="text-[9px] bg-amber-600/30 border border-amber-500/40 text-amber-200 px-1.5 py-0.5 rounded flex items-center gap-0.5">
                        <Unlock size={8} /> {cam.working_credentials}
                      </span>
                    )}
                    {!cam.working_credentials && cam.rtsp_working && (
                      <span className="text-[9px] bg-green-600/20 border border-green-500/30 text-green-300 px-1.5 py-0.5 rounded">
                        RTSP
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-[9px] text-slate-500">
                    <span className="text-slate-400">{cam.brand || 'generic'}</span>
                    {cam.source && <span className="text-slate-600">via {cam.source}</span>}
                    {cam.accessible_urls && cam.accessible_urls.length > 0 && (
                      <span className="text-cyan-500">{cam.accessible_urls.length} URLs</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Hosts con puertos abiertos */}
          {hosts.length > 0 && (
            <div className="mt-3">
              <div className="text-[9px] uppercase tracking-widest text-slate-400 font-mono mb-1 flex items-center gap-1">
                <Server size={10} /> Hosts ({hosts.length})
              </div>
              {hosts.slice(0, 20).map((h, i) => (
                <div key={`host-${i}`} className="p-2 rounded border border-slate-800 bg-slate-900/50 mb-1">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[10px] text-slate-300">{h.ip}</span>
                    <span className="text-[9px] text-slate-500">{h.open_ports?.join(', ')}</span>
                  </div>
                  {h.snmp && <span className="text-[8px] text-purple-400">SNMP: {h.snmp.sysname || 'OK'}</span>}
                  {h.netbios && <span className="text-[8px] text-green-400"> NetBIOS: {h.netbios.hostname || 'OK'}</span>}
                </div>
              ))}
              {hosts.length > 20 && <div className="text-[8px] text-slate-600 text-center">+{hosts.length - 20} mas...</div>}
            </div>
          )}

          {/* ONVIF details */}
          {onvifDetails.length > 0 && (
            <div className="mt-3">
              <div className="text-[9px] uppercase tracking-widest text-purple-400 font-mono mb-1">ONVIF ({onvifDetails.length})</div>
              {onvifDetails.map((d, i) => (
                <div key={`onvif-${i}`} className="p-2 rounded border border-purple-500/20 bg-purple-500/5 mb-1">
                  <div className="font-mono text-[10px] text-purple-300">{d.address || d.ip}</div>
                  {d.hardware && <div className="text-[8px] text-slate-400">{d.hardware}</div>}
                </div>
              ))}
            </div>
          )}

          {cameras.length === 0 && hosts.length === 0 && !scanning && (
            <div className="text-center text-slate-600 text-sm py-8">
              <Camera size={24} className="mx-auto mb-2 opacity-30" />
              No hay dispositivos descubiertos.
              <div className="text-[10px] mt-1">Ajusta la red y pulsa Descubrir Todo.</div>
            </div>
          )}
        </div>

        {/* Panel de detalles de la camara seleccionada */}
        <div className="lg:col-span-2 space-y-3 overflow-y-auto">
          {selectedCam ? (
            <>
              {/* Preview */}
              <div className="bg-black rounded-lg border border-slate-700 overflow-hidden aspect-video relative">
                {selectedCam.snapshot_url ? (
                  <img
                    src={selectedCam.snapshot_url}
                    alt="Camera Preview"
                    className="w-full h-full object-contain"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = 'none'
                    }}
                  />
                ) : (
                  <div className="flex items-center justify-center h-full text-slate-600 text-sm flex-col gap-2">
                    <Camera size={32} className="opacity-20" />
                    Sin feed disponible — verifica credenciales
                  </div>
                )}
                {selectedCam.working_credentials && (
                  <div className="absolute top-2 right-2 bg-red-600 text-white text-[10px] px-2 py-1 rounded flex items-center gap-1">
                    <AlertTriangle size={10} /> CREDENCIALES: {selectedCam.working_credentials}
                  </div>
                )}
                {scanning && (
                  <div className="absolute inset-0 bg-slate-900/50 flex items-center justify-center">
                    <RefreshCw size={24} className="text-cyan-400 animate-spin" />
                  </div>
                )}
              </div>

              {/* Datos basicos */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                <div className="bg-slate-900 rounded p-2 border border-slate-700">
                  <div className="text-slate-500 mb-0.5 text-[9px] uppercase tracking-wider">IP</div>
                  <div className="font-mono text-slate-200">{selectedCam.ip}</div>
                </div>
                <div className="bg-slate-900 rounded p-2 border border-slate-700">
                  <div className="text-slate-500 mb-0.5 text-[9px] uppercase tracking-wider">Puerto</div>
                  <div className="font-mono text-slate-200">{selectedCam.port || 80}</div>
                </div>
                <div className="bg-slate-900 rounded p-2 border border-slate-700">
                  <div className="text-slate-500 mb-0.5 text-[9px] uppercase tracking-wider">Marca</div>
                  <div className="text-slate-200">{selectedCam.brand || 'generic'}</div>
                </div>
                <div className="bg-slate-900 rounded p-2 border border-slate-700">
                  <div className="text-slate-500 mb-0.5 text-[9px] uppercase tracking-wider">Credenciales</div>
                  <div className={`font-mono ${selectedCam.working_credentials ? 'text-red-400' : 'text-slate-600'}`}>
                    {selectedCam.working_credentials || 'No detectadas'}
                  </div>
                </div>
              </div>

              {/* Todas las URLs y feeds */}
              <div className="bg-slate-900 rounded-lg border border-slate-700 p-2">
                <div className="text-[9px] uppercase tracking-widest text-cyan-400 font-mono mb-1.5 flex items-center gap-1.5">
                  <Link2 size={11} /> URLs y Feeds
                  {loadingUrls && <RefreshCw size={10} className="animate-spin text-slate-500" />}
                  {allUrls.length > 0 && <span className="text-slate-600">({allUrls.length})</span>}
                </div>
                {allUrls.length > 0 ? (
                  <div className="space-y-0.5">
                    {allUrls.map((u, idx) => renderUrlRow(u.url, u.label, u.icon, true))}
                  </div>
                ) : (
                  <div className="text-[10px] text-slate-600 py-2 text-center">
                    {loadingUrls ? 'Cargando URLs...' : 'Sin URLs detectadas'}
                  </div>
                )}
              </div>

              {/* Puertos abiertos */}
              {selectedCam.ports_open && selectedCam.ports_open.length > 0 && (
                <div className="bg-slate-900 rounded-lg border border-slate-700 p-2">
                  <div className="text-[9px] uppercase tracking-widest text-amber-400 font-mono mb-1.5 flex items-center gap-1.5">
                    <Server size={11} /> Puertos Abiertos ({selectedCam.ports_open.length})
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedCam.ports_open.map((p: string, i: number) => (
                      <span key={i} className="text-[10px] font-mono bg-amber-500/10 border border-amber-500/30 text-amber-300 px-2 py-0.5 rounded">
                        {p}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Banner/evidence */}
              {selectedCam.banner && (
                <div className="bg-slate-900 rounded-lg border border-slate-700 p-2">
                  <div className="text-[9px] uppercase tracking-widest text-slate-400 font-mono mb-1">Banner</div>
                  <div className="text-[10px] font-mono text-slate-400 break-all">{selectedCam.banner}</div>
                </div>
              )}

              {/* Botones de accion */}
              <div className="flex gap-2 flex-wrap">
                {selectedCam.rtsp_working && (
                  <a href={selectedCam.rtsp_working} target="_blank" rel="noopener noreferrer"
                     className="flex-1 py-2 bg-cyan-600 hover:bg-cyan-500 text-white text-xs rounded-lg flex items-center justify-center gap-1 min-w-[140px]">
                    <Play size={12} /> Ver Stream RTSP
                  </a>
                )}
                {selectedCam.snapshot_url && (
                  <a href={selectedCam.snapshot_url} target="_blank" rel="noopener noreferrer"
                     className="px-3 py-2 bg-amber-600/40 hover:bg-amber-600/60 border border-amber-500/40 text-amber-200 text-xs rounded-lg flex items-center gap-1">
                    <Eye size={12} /> Snapshot
                  </a>
                )}
                <button
                  onClick={copyCam}
                  className="px-3 py-2 bg-slate-700 hover:bg-slate-600 text-white text-xs rounded-lg flex items-center gap-1"
                  title="Copiar todos los datos de la camara"
                >
                  <Save size={12} /> Copiar JSON
                </button>
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center h-full text-slate-600 text-sm border border-slate-800 rounded-lg border-dashed min-h-[200px]">
              <div className="text-center">
                <Camera size={32} className="mx-auto mb-2 opacity-20" />
                Selecciona una camara para ver todos sus datos, URLs y feeds
              </div>
            </div>
          )}

          {/* Logs */}
          {logs.length > 0 && (
            <div className="bg-slate-900 rounded-lg border border-slate-800 p-2 max-h-32 overflow-y-auto">
              <div className="text-[10px] text-slate-500 font-bold mb-1 flex items-center gap-1">
                <Wifi size={10} /> LOGS
              </div>
              {logs.map((log, i) => (
                <div key={i} className="text-[10px] font-mono text-slate-400">{log}</div>
              ))}
            </div>
          )}
        {/* Grilla de Resultados Batch */}
        {(batchResults.length > 0 || batchScanning) && (
          <div className="mt-4">
            <div className="flex items-center gap-2 mb-3">
              <Scan size={16} className="text-purple-400" />
              <h3 className="text-sm font-bold text-slate-200">Grilla de Cámaras ({batchResults.length})</h3>
              {batchSummary && (
                <div className="flex gap-2 ml-auto">
                  <span className="px-2 py-0.5 bg-green-900/50 text-green-400 text-[10px] rounded-full">
                    Full: {batchSummary.full_access}
                  </span>
                  <span className="px-2 py-0.5 bg-yellow-900/50 text-yellow-400 text-[10px] rounded-full">
                    Partial: {batchSummary.partial_access}
                  </span>
                  <span className="px-2 py-0.5 bg-red-900/50 text-red-400 text-[10px] rounded-full">
                    No Access: {batchSummary.no_access}
                  </span>
                  {batchSummary.vendors_detected?.length > 0 && (
                    <span className="px-2 py-0.5 bg-slate-800 text-slate-400 text-[10px] rounded-full">
                      {batchSummary.vendors_detected.join(', ')}
                    </span>
                  )}
                </div>
              )}
            </div>
            
            {batchScanning && batchResults.length === 0 && (
              <div className="flex items-center justify-center py-12 text-slate-500">
                <RefreshCw size={20} className="animate-spin mr-2" />
                <span className="text-sm">Escaneando red completa...</span>
              </div>
            )}
            
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
              {batchResults.map((cam, i) => (
                <div
                  key={i}
                  className={`rounded-lg border overflow-hidden cursor-pointer transition-all hover:scale-105 ${
                    cam.access_level === 'full' ? 'border-green-600/50 bg-green-950/20' :
                    cam.access_level === 'partial' ? 'border-yellow-600/50 bg-yellow-950/20' :
                    'border-red-600/30 bg-red-950/10'
                  }`}
                  onClick={() => setSelectedCam(cam)}
                >
                  {/* Thumbnail */}
                  <div className="aspect-video bg-black relative overflow-hidden">
                    {cam.snapshot?.available ? (
                      <img
                        src={cam.snapshot.url}
                        alt={cam.ip}
                        className="w-full h-full object-cover"
                        onError={(e) => {
                          (e.target as HTMLImageElement).src = cam.stream_url || ''
                        }}
                      />
                    ) : (
                      <div className="flex items-center justify-center h-full">
                        <Camera size={20} className="opacity-30 text-slate-600" />
                      </div>
                    )}
                    {/* Badge de acceso */}
                    <div className="absolute top-1 right-1">
                      <span className={`px-1.5 py-0.5 text-[8px] rounded-full font-bold ${
                        cam.access_level === 'full' ? 'bg-green-600 text-white' :
                        cam.access_level === 'partial' ? 'bg-yellow-600 text-black' :
                        'bg-red-600 text-white'
                      }`}>
                        {cam.access_level === 'full' ? 'LIVE' : cam.access_level === 'partial' ? 'DATA' : 'OFF'}
                      </span>
                    </div>
                  </div>
                  {/* Info */}
                  <div className="p-2">
                    <div className="text-[10px] font-mono text-cyan-400 truncate">{cam.ip}:{cam.port}</div>
                    <div className="text-[10px] text-slate-400 truncate">{cam.vendor}</div>
                    {cam.credentials && (
                      <div className="text-[9px] text-green-400 font-mono mt-0.5">
                        {cam.credentials.user}:{cam.credentials.pwd}
                      </div>
                    )}
                    {cam.cves?.length > 0 && (
                      <div className="flex gap-0.5 flex-wrap mt-1">
                        {cam.cves.slice(0, 2).map((cve: any) => (
                          <span key={cve.cve} className="px-1 py-0.5 bg-red-900/60 text-red-400 text-[7px] rounded font-mono">
                            {cve.cve.replace('CVE-', '')}
                          </span>
                        ))}
                        {cam.cves.length > 2 && (
                          <span className="text-[7px] text-slate-500">+{cam.cves.length - 2}</span>
                        )}
                      </div>
                    )}
                    {cam.snapshot?.available && (
                      <a
                        href={cam.stream_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="mt-1 inline-flex items-center gap-1 text-[9px] text-cyan-400 hover:text-cyan-300"
                      >
                        <Play size={8} /> Stream
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        
        </div>
      </div>
    </div>
  )
}
