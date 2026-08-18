import { useState, useEffect, useRef, useCallback } from 'react'
import { getApiKey } from '../lib/api'
import { Network, Scan, Filter, AlertCircle, Shield, Camera, Router as RouterIcon,
         Server, Cpu, Wifi, Eye, RefreshCw, ChevronDown, X, Play, Radio,
         Globe, Lock, Fingerprint, Activity } from 'lucide-react'

interface HostPort {
  port: number
  service: string
  state: string
  banner: string
}

interface Host {
  ip: string
  mac: string | null
  vendor: string | null
  ports: HostPort[]
  type: string
  status: string
  risk: 'low' | 'medium' | 'high' | 'critical'
  risk_reasons?: string[]
}

interface Camera {
  ip: string
  port: number
  brand: string
  model: string
  vulnerable: boolean
  credentials?: string
  snapshot_url?: string
  rtsp_url?: string
  onvif_url?: string
}

const RISK_COLORS: Record<string, string> = {
  low: '#22c55e',
  medium: '#eab308',
  high: '#f97316',
  critical: '#ef4444',
  unknown: '#64748b',
}

const RISK_LABELS: Record<string, string> = {
  low: 'Bajo',
  medium: 'Medio',
  high: 'Alto',
  critical: 'Crítico',
  unknown: '—',
}

const TYPE_ICONS: Record<string, typeof Camera> = {
  camera: Camera,
  router: RouterIcon,
  server: Server,
  iot: Cpu,
  phone: Radio,
  unknown: Globe,
}

const SERVICE_NAMES: Record<number, string> = {
  80: 'HTTP', 443: 'HTTPS', 554: 'RTSP', 22: 'SSH', 23: 'Telnet',
  21: 'FTP', 3389: 'RDP', 5900: 'VNC', 8080: 'HTTP-Alt',
  8000: 'HTTP-Alt', 37777: 'DVR', 8554: 'RTSP-Alt', 53: 'DNS',
  161: 'SNMP', 1900: 'SSDP', 5000: 'UPnP', 9000: 'Web',
}


function authHeaders(): Record<string, string> {
  const key = getApiKey()
  const h: Record<string, string> = { 'Content-Type': 'application/json' }
  if (key) h['Authorization'] = `Bearer ${key}`
  return h
}

function authHeadersGet(): Record<string, string> {
  const key = getApiKey()
  return key ? { 'Authorization': `Bearer ${key}` } : {}
}

export default function NetworkTopology() {
  const [hosts, setHosts] = useState<Host[]>([])
  const [cameras, setCameras] = useState<Camera[]>([])
  const [scanning, setScanning] = useState(false)
  const [scanError, setScanError] = useState<string | null>(null)
  const [subnet, setSubnet] = useState('')
  const [localIp, setLocalIp] = useState('')
  const [localHostname, setLocalHostname] = useState('')
  const [selectedHost, setSelectedHost] = useState<Host | null>(null)
  const [filterRisk, setFilterRisk] = useState('all')
  const [filterType, setFilterType] = useState('all')
  const [filterPort, setFilterPort] = useState('')
  const [logs, setLogs] = useState<string[]>([])
  const [view, setView] = useState<'topology' | 'cameras' | 'list'>('topology')
  const [showAll, setShowAll] = useState(false)
  const [videoUrls, setVideoUrls] = useState<any[]>([])
  const [videoLoading, setVideoLoading] = useState(false)
  const svgRef = useRef<SVGSVGElement>(null)

  const addLog = (msg: string) => setLogs(prev => [`[${new Date().toLocaleTimeString()}] ${msg}`, ...prev].slice(0, 30))

  useEffect(() => {
    loadCameras()
  }, [])

  const loadCameras = async () => {
    try {
      const r = await fetch('/api/enhanced/cameras', { headers: authHeadersGet() })
      const data = await r.json()
      setCameras(data.cameras || [])
    } catch (e) { /* sin cámaras */ }
  }

  const runScan = async () => {
    setScanning(true)
    setSelectedHost(null)
    setScanError(null)
    addLog('Iniciando escaneo de topologia...')
    try {
      const r = await fetch('/api/scan/topology', { method: 'POST', headers: authHeaders() })
      if (!r.ok) {
        const errData = await r.json().catch(() => ({}))
        const msg = errData.error || `HTTP ${r.status}: ${r.statusText}`
        addLog(`Error: ${msg}`)
        setScanError(msg)
        return
      }
      const data = await r.json()
      if (data.error) { addLog(`Error: ${data.error}`); setScanError(data.error); return }
      setHosts(data.results || [])
      setSubnet(data.subnet || '')
      setLocalIp(data.local_ip || '')
      setLocalHostname(data.local_hostname || '')
      addLog(`Topologia: ${data.hosts_up} hosts en ${data.subnet}`)
      addLog('Buscando camaras ONVIF/RTSP...')
      const camRes = await fetch('/api/scan/cameras', { method: 'POST', headers: authHeaders() })
      const camData = await camRes.json()
      setCameras(camData.cameras || camData.results || [])
      addLog(`Camaras encontradas: ${camData.cameras?.length || camData.results?.length || 0}`)
    } catch (e: any) {
      addLog(`Error: ${e.message}`)
    } finally {
      setScanning(false)
    }
  }

  const discoverAll = async () => {
    setScanning(true)
    addLog('Descubrimiento completo (ONVIF + SSDP + SNMP)...')
    try {
      // Si aun no se corrio 'Escanear Red', subnet esta vacio -- antes esto
      // caia a un '192.168.1' hardcodeado que casi nunca es la red real
      // (hotspots Android suelen usar otro rango), por eso ONVIF/SSDP/
      // camaras siempre salian en 0. Ahora se pide la subred real al backend.
      let net = subnet.split('.').slice(0, 3).join('.')
      if (!net) {
        try {
          const infoRes = await fetch('/api/network/info', { headers: authHeadersGet() })
          const info = await infoRes.json()
          net = (info.subnet || '').split('/')[0].split('.').slice(0, 3).join('.') || '192.168.1'
          setSubnet(info.subnet || '')
        } catch { net = '192.168.1' }
      }
      const r = await fetch('/api/enhanced/discover/all', { method: 'POST', headers: authHeaders(), body: JSON.stringify({ network: net }) })
      const data = await r.json()
      setCameras(data.cameras || [])
      addLog(`ONVIF: ${data.onvif_found || 0} | SSDP: ${data.ssdp_found || 0} | Camaras: ${data.cameras?.length || 0}`)
    } catch (e: any) {
      addLog(`Error: ${e.message}`)
    } finally {
      setScanning(false)
    }
  }

  const filteredHosts = hosts.filter(h => {
    if (filterRisk !== 'all' && h.risk !== filterRisk) return false
    if (filterType !== 'all' && h.type !== filterType) return false
    if (filterPort && !h.ports.some(p => p.port === parseInt(filterPort))) return false
    return true
  })

  const detectVideo = async (ip: string) => {
    setVideoLoading(true)
    setVideoUrls([])
    try {
      const r = await fetch(`/api/scan/video-urls?ip=${ip}`, { headers: authHeadersGet() })
      const data = await r.json()
      setVideoUrls(data.video_sources || [])
      addLog(`Video en ${ip}: ${data.video_sources?.length || 0} fuentes`)
    } catch (e: any) {
      addLog(`Error video: ${e.message}`)
    } finally {
      setVideoLoading(false)
    }
  }

  useEffect(() => {
    if (selectedHost) detectVideo(selectedHost.ip)
    else setVideoUrls([])
  }, [selectedHost])

  const nodes = useCallback(() => {
    const total = filteredHosts.length
    if (total === 0) return []
    const cx = 400, cy = 250
    const radius = Math.min(180, 60 + total * 8)
    return filteredHosts.map((h, i) => {
      const angle = (i / total) * 2 * Math.PI - Math.PI / 2
      return { ...h, x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) }
    })
  }, [filteredHosts])

  const positionedNodes = nodes()
  const typeCounts = hosts.reduce((acc, h) => { acc[h.type] = (acc[h.type] || 0) + 1; return acc }, {} as Record<string, number>)

  return (
    <div className="space-y-4">
      <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
            <Network size={20} className="text-cyan-400" />
            Topologia de Red
            {subnet && <span className="text-xs text-slate-500 font-mono ml-2">{subnet}/24</span>}
          </h2>
          <div className="flex items-center gap-2">
            <button onClick={runScan} disabled={scanning} className="px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white text-xs rounded-lg flex items-center gap-1.5 disabled:opacity-50">
              {scanning ? <RefreshCw size={12} className="animate-spin" /> : <Scan size={12} />}
              {scanning ? 'Escaneando...' : 'Escanear Red'}
            </button>
            <button onClick={discoverAll} disabled={scanning} className="px-3 py-1.5 bg-red-600/80 hover:bg-red-500 text-white text-xs rounded-lg flex items-center gap-1.5 disabled:opacity-50">
              <Camera size={12} /> Descubrir Camaras
            </button>
          </div>
        </div>

        <div className="flex gap-1 mb-3">
          {([['topology', 'Topologia', Network], ['cameras', `Camaras (${cameras.length})`, Camera], ['list', `Lista (${filteredHosts.length})`, Shield]] as const).map(([id, label, Icon]) => (
            <button key={id} onClick={() => setView(id)} className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all ${view === id ? 'bg-slate-800 text-cyan-400 border border-cyan-700/50' : 'text-slate-500 hover:text-slate-300 border border-transparent'}`}>
              <Icon size={12} /> {label}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap gap-2">
          <div className="flex items-center gap-1 bg-slate-900 rounded-lg px-2 py-1 border border-slate-700">
            <Filter size={10} className="text-slate-500" />
            <select value={filterRisk} onChange={e => setFilterRisk(e.target.value)} className="bg-transparent text-xs text-slate-300 outline-none">
              <option value="all">Todos los riesgos</option>
              <option value="critical">Critico</option>
              <option value="high">Alto</option>
              <option value="medium">Medio</option>
              <option value="low">Bajo</option>
            </select>
          </div>
          <div className="flex items-center gap-1 bg-slate-900 rounded-lg px-2 py-1 border border-slate-700">
            <Shield size={10} className="text-slate-500" />
            <select value={filterType} onChange={e => setFilterType(e.target.value)} className="bg-transparent text-xs text-slate-300 outline-none">
              <option value="all">Todos los tipos</option>
              <option value="camera">Camara</option>
              <option value="router">Router</option>
              <option value="iot">IoT</option>
              <option value="server">Servidor</option>
              <option value="phone">Telefono</option>
              <option value="unknown">Desconocido</option>
            </select>
          </div>
          <input value={filterPort} onChange={e => setFilterPort(e.target.value)} placeholder="Puerto..." className="bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 text-xs text-slate-300 w-28 font-mono" />
          <button onClick={() => { setFilterRisk('all'); setFilterType('all'); setFilterPort('') }} className="px-2 py-1 text-xs text-slate-500 hover:text-slate-300">Limpiar</button>
          <button onClick={() => { setShowAll(true); setSelectedHost(null) }} className="px-2 py-1 text-xs bg-slate-800 border border-slate-700 rounded-lg text-cyan-400 hover:bg-slate-700">Ver todos ({hosts.length})</button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Vista principal */}
        <div className="lg:col-span-2 bg-slate-950 border border-slate-800 rounded-xl overflow-hidden">
          {scanError && hosts.length === 0 && (
            <div className="mb-3 p-3 rounded-lg border border-red-500/40 bg-red-500/10 text-red-300 text-sm flex items-center gap-2">
              <AlertCircle size={16} className="shrink-0" />
              <span>{scanError}</span>
              <button onClick={() => setScanError(null)} className="ml-auto text-red-400 hover:text-red-200">
                <X size={14} />
              </button>
            </div>
          )}
          {view === 'topology' && (
            <div className="relative bg-slate-900/30" style={{ minHeight: '500px' }}>
              <svg ref={svgRef} className="w-full h-full" viewBox="0 0 800 500" style={{ minHeight: '500px' }}>
                <defs>
                  <radialGradient id="centerGlow">
                    <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.3" />
                    <stop offset="100%" stopColor="#06b6d4" stopOpacity="0" />
                  </radialGradient>
                  <filter id="nodeGlow">
                    <feGaussianBlur stdDeviation="2" result="coloredBlur" />
                    <feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge>
                  </filter>
                </defs>

                {/* Centro — este dispositivo (host local) */}
                <circle cx={400} cy={250} r={64} fill="url(#centerGlow)">
                  {scanning && <animate attributeName="r" values="60;70;60" dur="2s" repeatCount="indefinite" />}
                </circle>
                <circle cx={400} cy={250} r={30} fill="none" stroke="#06b6d4" strokeWidth="1" opacity="0.35">
                  <animate attributeName="r" values="30;40;30" dur="2.5s" repeatCount="indefinite" />
                  <animate attributeName="opacity" values="0.4;0;0.4" dur="2.5s" repeatCount="indefinite" />
                </circle>
                <circle cx={400} cy={250} r={26} fill="#0c1e2e" stroke="#06b6d4" strokeWidth="2" filter="url(#nodeGlow)" />
                <foreignObject x={385} y={235} width="30" height="30">
                  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', width: '100%', height: '100%' }}>
                    <Server size={16} color="#06b6d4" />
                  </div>
                </foreignObject>
                <text x={400} y={293} textAnchor="middle" fill="#e2e8f0" fontSize="10" fontWeight="bold" fontFamily="monospace">{localHostname ? localHostname.toUpperCase() : 'ESTE DISPOSITIVO'}</text>
                <text x={400} y={306} textAnchor="middle" fill="#64748b" fontSize="9" fontFamily="monospace">{localIp || `${subnet || '192.168.1'}.x`}</text>

                {/* Lineas — hilos */}
                {positionedNodes.map((n, i) => {
                  const color = RISK_COLORS[n.risk] || RISK_COLORS.unknown
                  const isSel = selectedHost?.ip === n.ip
                  return (
                    <line key={`l-${i}`} x1={400} y1={250} x2={n.x} y2={n.y}
                      stroke={isSel ? color : '#1e293b'} strokeWidth={isSel ? 2 : 1}
                      strokeDasharray={isSel ? '0' : '4 2'} opacity={isSel ? 0.8 : 0.4}>
                      {scanning && <animate attributeName="stroke-dashoffset" from="0" to="-12" dur="0.5s" repeatCount="indefinite" />}
                    </line>
                  )
                })}

                {/* Nodos */}
                {positionedNodes.map((n, i) => {
                  const color = RISK_COLORS[n.risk] || RISK_COLORS.unknown
                  const isSel = selectedHost?.ip === n.ip
                  const Icon = TYPE_ICONS[n.type] || Globe
                  const r = isSel ? 24 : 18
                  return (
                    <g key={`n-${i}`} transform={`translate(${n.x},${n.y})`} onClick={() => { setSelectedHost(n); setShowAll(false) }} style={{ cursor: 'pointer' }}>
                      {isSel && (
                        <circle r={r + 8} fill="none" stroke={color} strokeWidth="1" opacity="0.4">
                          <animate attributeName="r" from={r} to={r + 12} dur="1s" repeatCount="indefinite" />
                          <animate attributeName="opacity" from="0.6" to="0" dur="1s" repeatCount="indefinite" />
                        </circle>
                      )}
                      <circle r={r} fill={color} fillOpacity={isSel ? 0.3 : 0.15} stroke={color} strokeWidth={isSel ? 2.5 : 1.5} filter="url(#nodeGlow)" />
                      <foreignObject x={-8} y={-8} width="16" height="16">
                        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', width: '100%', height: '100%' }}>
                          <Icon size={12} color={color} />
                        </div>
                      </foreignObject>
                      <text y={r + 12} textAnchor="middle" fill={isSel ? '#e2e8f0' : '#94a3b8'} fontSize="10" fontFamily="monospace" fontWeight={isSel ? 'bold' : 'normal'}>
                        {n.ip.split('.').pop()}
                      </text>
                      {n.ports.length > 0 && (
                        <g transform={`translate(${r - 4}, -${r + 2})`}>
                          <rect x="0" y="0" width="18" height="12" rx="3" fill="#0f172a" stroke={color} strokeWidth="0.5" />
                          <text x="9" y="9" textAnchor="middle" fill={color} fontSize="8" fontFamily="monospace" fontWeight="bold">{n.ports.length}</text>
                        </g>
                      )}
                      <title>{`${n.ip}\nTipo: ${n.type}\nRiesgo: ${RISK_LABELS[n.risk] || n.risk}\nPuertos: ${n.ports.map((p: any) => p.port).join(', ') || 'Ninguno'}\nMAC: ${n.mac || 'N/D'}\nVendor: ${n.vendor || 'N/D'}`}</title>
                    </g>
                  )
                })}

                {scanning && <text x={400} y={480} textAnchor="middle" fill="#06b6d4" fontSize="11" fontFamily="monospace">Escaneando red...</text>}
              </svg>

              {/* Leyenda */}
              <div className="absolute top-3 right-3 bg-slate-900/80 backdrop-blur border border-slate-700 rounded-lg p-2 space-y-1">
                <div className="text-[10px] text-slate-500 font-bold mb-1">RIESGO</div>
                {Object.entries(RISK_COLORS).map(([k, v]) => (
                  <div key={k} className="flex items-center gap-1.5 text-[10px]">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: v }} />
                    <span className="text-slate-400">{RISK_LABELS[k]}</span>
                  </div>
                ))}
              </div>

              {positionedNodes.length === 0 && !scanning && (
                <div className="absolute inset-0 flex items-center justify-center flex-col gap-2 text-slate-600">
                  <Network size={32} className="opacity-30" />
                  <span className="text-sm">{scanError ? `Error: ${scanError}` : 'Sin datos. Ejecuta un escaneo para ver la topologia.'}</span>
                </div>
              )}
            </div>
          )}

          {view === 'cameras' && (
            <div className="p-4 grid grid-cols-1 sm:grid-cols-2 gap-3" style={{ minHeight: '500px' }}>
              {cameras.map((cam, i) => (
                <div key={i} className="p-3 rounded-lg border bg-slate-900 border-slate-700 hover:border-slate-600">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-sm text-slate-200">{cam.ip}:{cam.port}</span>
                    {cam.vulnerable && <span className="text-[10px] bg-red-600 text-white px-1.5 py-0.5 rounded flex items-center gap-1"><Lock size={8} /> vulnerable</span>}
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-slate-500">
                    <span className="text-slate-400">{cam.brand || 'Unknown'}</span>
                    {cam.credentials && <span className="text-amber-400">🔓 {cam.credentials}</span>}
                  </div>
                  {cam.rtsp_url && <div className="mt-1 text-[9px] text-cyan-500 font-mono truncate">{cam.rtsp_url}</div>}
                </div>
              ))}
              {cameras.length === 0 && (
                <div className="col-span-full flex items-center justify-center text-slate-600 text-sm py-12">
                  <Camera size={24} className="mr-2 opacity-30" /> No hay camaras descubiertas. Usa "Descubrir Camaras".
                </div>
              )}
            </div>
          )}

          {view === 'list' && (
            <div className="p-2 overflow-y-auto" style={{ minHeight: '500px', maxHeight: '600px' }}>
              <table className="w-full text-xs">
                <thead className="text-slate-500 border-b border-slate-800">
                  <tr>
                    <th className="text-left px-2 py-2 font-medium">IP</th>
                    <th className="text-left px-2 py-2 font-medium">Tipo</th>
                    <th className="text-left px-2 py-2 font-medium">Riesgo</th>
                    <th className="text-left px-2 py-2 font-medium">Puertos</th>
                    <th className="text-left px-2 py-2 font-medium">MAC/Vendor</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredHosts.map((h, i) => (
                    <tr key={i} onClick={() => { setSelectedHost(h); setShowAll(false) }} className={`border-b border-slate-800/50 cursor-pointer hover:bg-slate-800/30 ${selectedHost?.ip === h.ip ? 'bg-slate-800/50' : ''}`}>
                      <td className="px-2 py-2 font-mono text-cyan-400">{h.ip}</td>
                      <td className="px-2 py-2 text-slate-300 capitalize">{h.type}</td>
                      <td className="px-2 py-2"><span className="px-1.5 py-0.5 rounded text-[10px] font-bold" style={{ backgroundColor: `${RISK_COLORS[h.risk] || RISK_COLORS.unknown}20`, color: RISK_COLORS[h.risk] || RISK_COLORS.unknown }}>{RISK_LABELS[h.risk] || h.risk}</span></td>
                      <td className="px-2 py-2 font-mono text-slate-400">{h.ports.map((p: any) => p.port).join(', ') || '—'}</td>
                      <td className="px-2 py-2 text-slate-500 font-mono text-[10px]">{h.mac || '—'}<br />{h.vendor && <span className="text-slate-400">{h.vendor}</span>}</td>
                    </tr>
                  ))}
                  {filteredHosts.length === 0 && <tr><td colSpan={5} className="text-center text-slate-600 py-8">Sin resultados. Escanea la red primero.</td></tr>}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Panel lateral */}
        <div className="space-y-3">
          {selectedHost ? (
            <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2"><Fingerprint size={14} className="text-cyan-400" />{selectedHost.ip}</h3>
                <button onClick={() => setSelectedHost(null)} className="text-slate-600 hover:text-slate-300"><X size={14} /></button>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-slate-900 rounded-lg p-2"><div className="text-[10px] text-slate-500 mb-1">TIPO</div><div className="text-sm text-slate-200 capitalize">{selectedHost.type}</div></div>
                <div className="bg-slate-900 rounded-lg p-2"><div className="text-[10px] text-slate-500 mb-1">RIESGO</div><div className="text-sm font-bold" style={{ color: RISK_COLORS[selectedHost.risk] || RISK_COLORS.unknown }}>{RISK_LABELS[selectedHost.risk] || selectedHost.risk}</div></div>
              </div>
              <div className="bg-slate-900 rounded-lg p-2 space-y-1">
                <div className="text-[10px] text-slate-500">MAC</div><div className="text-xs font-mono text-slate-300">{selectedHost.mac || 'No detectada'}</div>
                {selectedHost.vendor && <><div className="text-[10px] text-slate-500 mt-1">VENDOR</div><div className="text-xs text-slate-300">{selectedHost.vendor}</div></>}
              </div>
              <div className="bg-slate-900 rounded-lg p-2 space-y-1">
                <div className="text-[10px] text-slate-500 mb-1">PUERTOS ABIERTOS ({selectedHost.ports.length})</div>
                {selectedHost.ports.length > 0 ? (
                  <div className="flex flex-wrap gap-1">
                    {selectedHost.ports.map((p, i) => (
                      <a key={i} href={`http://${selectedHost.ip}:${p.port}`} target="_blank" rel="noopener noreferrer" className="px-2 py-1 bg-slate-800 border border-slate-700 rounded text-[10px] font-mono text-cyan-400 hover:bg-slate-700" title={p.banner || p.service}>{p.port} · {SERVICE_NAMES[p.port] || p.service}</a>
                    ))}
                  </div>
                ) : <span className="text-xs text-slate-600">Sin puertos abiertos</span>}
              </div>
              {videoLoading && <div className="text-xs text-slate-500 flex items-center gap-1"><RefreshCw size={10} className="animate-spin" /> Detectando video...</div>}
              {videoUrls.length > 0 && (
                <div className="bg-slate-900 rounded-lg p-2 space-y-1">
                  <div className="text-[10px] text-slate-500 mb-1">FUENTES DE VIDEO</div>
                  {videoUrls.map((v, i) => <a key={i} href={v.url} target="_blank" rel="noopener noreferrer" className="block text-[10px] font-mono text-cyan-400 hover:underline truncate" title={v.url}><Play size={8} className="inline mr-1" />{v.url}</a>)}
                </div>
              )}
              {selectedHost.risk_reasons && selectedHost.risk_reasons.length > 0 && (
                <div className="bg-red-950/20 border border-red-900/50 rounded-lg p-2 space-y-1">
                  <div className="text-[10px] text-red-500 font-bold mb-1">RAZONES DE RIESGO</div>
                  {selectedHost.risk_reasons.map((r, i) => <div key={i} className="text-[10px] text-slate-400 flex items-start gap-1"><span className="text-red-500">•</span> {r}</div>)}
                </div>
              )}
              <div className="flex flex-wrap gap-1">
                <a href={`http://${selectedHost.ip}`} target="_blank" rel="noopener noreferrer" className="px-2 py-1 bg-slate-800 border border-slate-700 rounded text-[10px] text-slate-300 hover:bg-slate-700 flex items-center gap-1"><Globe size={10} /> Abrir HTTP</a>
                <a href={`rtsp://${selectedHost.ip}:554`} className="px-2 py-1 bg-slate-800 border border-slate-700 rounded text-[10px] text-slate-300 hover:bg-slate-700 flex items-center gap-1"><Camera size={10} /> RTSP</a>
                <a href={`http://${selectedHost.ip}:8080`} target="_blank" rel="noopener noreferrer" className="px-2 py-1 bg-slate-800 border border-slate-700 rounded text-[10px] text-slate-300 hover:bg-slate-700 flex items-center gap-1"><Globe size={10} /> :8080</a>
              </div>
            </div>
          ) : showAll ? (
            <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-2 max-h-[600px] overflow-y-auto">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2 mb-2">
                <h3 className="text-sm font-bold text-slate-100">Todos los hosts ({filteredHosts.length})</h3>
                <button onClick={() => setShowAll(false)} className="text-slate-600 hover:text-slate-300"><X size={14} /></button>
              </div>
              {filteredHosts.map((h, i) => (
                <div key={i} onClick={() => { setSelectedHost(h); setShowAll(false) }} className="p-2 bg-slate-900 border border-slate-700 rounded-lg cursor-pointer hover:border-slate-600 flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: RISK_COLORS[h.risk] || RISK_COLORS.unknown }} />
                  <span className="font-mono text-xs text-cyan-400">{h.ip}</span>
                  <span className="text-[10px] text-slate-500 capitalize">{h.type}</span>
                  <span className="text-[10px] text-slate-600 ml-auto">{h.ports.length} puertos</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-3">
              <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2"><Activity size={14} className="text-cyan-400" /> Resumen de Red</h3>
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-slate-900 rounded-lg p-3 text-center"><div className="text-2xl font-bold text-cyan-400">{hosts.length}</div><div className="text-[10px] text-slate-500">HOSTS</div></div>
                <div className="bg-slate-900 rounded-lg p-3 text-center"><div className="text-2xl font-bold text-red-400">{cameras.length}</div><div className="text-[10px] text-slate-500">CAMARAS</div></div>
                <div className="bg-slate-900 rounded-lg p-3 text-center"><div className="text-2xl font-bold text-amber-400">{hosts.filter(h => h.risk === 'high' || h.risk === 'critical').length}</div><div className="text-[10px] text-slate-500">ALTO RIESGO</div></div>
                <div className="bg-slate-900 rounded-lg p-3 text-center"><div className="text-2xl font-bold text-green-400">{hosts.filter(h => h.risk === 'low').length}</div><div className="text-[10px] text-slate-500">SEGUROS</div></div>
              </div>
              <div className="space-y-1">
                <div className="text-[10px] text-slate-500 font-bold">DISPOSITIVOS POR TIPO</div>
                {Object.entries(typeCounts).map(([type, count]) => (
                  <div key={type} className="flex items-center gap-2">
                    <div className="text-xs text-slate-400 capitalize w-20">{type}</div>
                    <div className="flex-1 bg-slate-800 rounded-full h-2 overflow-hidden"><div className="h-full bg-cyan-500 rounded-full" style={{ width: `${(count / hosts.length) * 100}%` }} /></div>
                    <div className="text-xs text-slate-300 w-6 text-right">{count}</div>
                  </div>
                ))}
                {Object.keys(typeCounts).length === 0 && <div className="text-xs text-slate-600">Sin datos. Escanea la red.</div>}
              </div>
              <div className="text-[10px] text-slate-600 pt-2 border-t border-slate-800">Click en un nodo para ver detalles · "Ver todos" para lista completa</div>
            </div>
          )}
        </div>
      </div>

      {logs.length > 0 && (
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-3">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-[10px] font-bold text-slate-500 uppercase">Log de Actividad</h3>
            <button onClick={() => setLogs([])} className="text-[10px] text-slate-600 hover:text-slate-400">Limpiar</button>
          </div>
          <div className="space-y-0.5 max-h-32 overflow-y-auto font-mono text-[10px]">
            {logs.map((log, i) => <div key={i} className={log.includes('Error') ? 'text-red-400' : 'text-slate-400'}>{log}</div>)}
          </div>
        </div>
      )}
    </div>
  )
}
