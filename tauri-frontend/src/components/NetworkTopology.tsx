import { useState, useEffect, useRef, useCallback } from 'react'
import { getApiKey } from '../lib/api'
import { Network, Scan, Filter, AlertCircle, Shield, Camera, Router as RouterIcon,
         Server, Cpu, Wifi, Eye, RefreshCw, ChevronDown, X, Play, Radio,
         Globe, Lock, Fingerprint, Activity, Crosshair, Zap, Radar } from 'lucide-react'

interface HostPort { port: number; service: string; state: string; banner: string }
interface Host {
  ip: string; mac: string | null; vendor: string | null
  ports: HostPort[]; type: string; status: string
  risk: 'low' | 'medium' | 'high' | 'critical'
  risk_reasons?: string[]
}
interface Camera {
  ip: string; port: number; brand: string; model: string
  vulnerable: boolean; credentials?: string
  snapshot_url?: string; rtsp_url?: string; onvif_url?: string
}

const GRID_THRESHOLD = 40
const RISK_COLORS: Record<string, string> = {
  low: '#22c55e', medium: '#eab308', high: '#f97316', critical: '#ef4444', unknown: '#64748b'
}
const RISK_LABELS: Record<string, string> = {
  low: 'Bajo', medium: 'Medio', high: 'Alto', critical: 'Crítico', unknown: '—'
}
const TYPE_ICONS: Record<string, typeof Camera> = {
  camera: Camera, router: RouterIcon, server: Server, iot: Cpu, phone: Radio, unknown: Globe
}
const SERVICE_NAMES: Record<number, string> = {
  80: 'HTTP', 443: 'HTTPS', 554: 'RTSP', 22: 'SSH', 23: 'Telnet', 21: 'FTP',
  3389: 'RDP', 5900: 'VNC', 8080: 'HTTP-Alt', 8000: 'HTTP-Alt', 37777: 'DVR',
  8554: 'RTSP-Alt', 53: 'DNS', 161: 'SNMP', 1900: 'SSDP', 5000: 'UPnP', 9000: 'Web',
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

// ─── World map silhouette (simplified continents path) ──────────────
const WORLD_MAP_PATH = "M150,120 C160,110 175,108 190,115 L210,110 C225,105 240,112 250,120 L270,115 C285,110 300,118 310,125 L330,120 C345,115 360,122 370,130 L390,125 C400,120 415,128 420,135 L440,130 C455,125 470,132 480,140 L500,135 C515,130 525,138 530,145 L545,140 C555,135 565,142 570,150 L580,145 C590,140 600,148 605,155 L620,150 C630,145 640,152 645,160 L660,155 C670,150 680,157 685,165 L690,160 C695,155 700,162 705,170 L700,180 C705,190 700,200 695,210 L690,220 C685,230 675,235 665,240 L650,245 C640,250 625,248 615,255 L600,260 C590,265 575,263 565,270 L550,275 C540,280 525,278 515,285 L500,290 C490,295 475,293 465,300 L450,305 C440,310 425,308 415,315 L400,320 C390,325 375,323 365,330 L350,335 C340,340 325,338 315,345 L300,350 C290,355 275,353 265,360 L250,365 C240,370 225,368 215,375 L200,380 C190,385 175,383 165,390 L150,395 C140,400 125,398 115,390 L100,385 C90,380 75,375 65,365 L50,355 C40,345 30,330 25,315 L20,300 C15,285 20,270 25,255 L30,240 C35,225 45,215 55,205 L60,190 C55,175 65,160 75,150 L80,135 C90,125 105,120 120,125 L135,120 C140,118 145,119 150,120 Z"

// ─── Position nodes on the map based on IP ───────────────────────────
function positionOnMap(hosts: Host[], width: number, height: number) {
  if (hosts.length === 0) return []
  const cx = width / 2, cy = height / 2
  const mapW = width * 0.75, mapH = height * 0.6
  return hosts.map((h, i) => {
    // Use IP last octets for pseudo-geographic positioning
    const octets = h.ip.split('.').map(Number)
    const lastOct = octets[3] || (i + 1)
    const thirdOct = octets[2] || 1
    // Map to lat/long-like coordinates
    const angle = (i / Math.max(hosts.length, 1)) * 2 * Math.PI
    const spread = 0.35 + (lastOct / 255) * 0.15
    const xOff = Math.cos(angle) * mapW * spread + (thirdOct - 128) * 0.5
    const yOff = Math.sin(angle) * mapH * spread + (lastOct - 128) * 0.3
    return {
      ...h,
      x: cx + xOff,
      y: cy + yOff,
      angle,
    }
  })
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
  const [hoveredHost, setHoveredHost] = useState<Host | null>(null)
  const [filterRisk, setFilterRisk] = useState('all')
  const [filterType, setFilterType] = useState('all')
  const [filterPort, setFilterPort] = useState('')
  const [logs, setLogs] = useState<string[]>([])
  const [view, setView] = useState<'topology' | 'cameras' | 'list'>('topology')
  const [showAll, setShowAll] = useState(false)
  const [videoUrls, setVideoUrls] = useState<any[]>([])
  const [videoLoading, setVideoLoading] = useState(false)
  const [radarSweep, setRadarSweep] = useState(0)
  const svgRef = useRef<SVGSVGElement>(null)

  const addLog = (msg: string) => setLogs(prev => [`[${new Date().toLocaleTimeString()}] ${msg}`, ...prev].slice(0, 30))

  // ─── Radar sweep animation ──────────────────────────────────────────
  useEffect(() => {
    if (!scanning) return
    const interval = setInterval(() => {
      setRadarSweep(prev => (prev + 2) % 360)
    }, 16)
    return () => clearInterval(interval)
  }, [scanning])

  useEffect(() => { loadCameras() }, [])

  const loadCameras = async () => {
    try {
      const r = await fetch('/api/enhanced/cameras', { headers: authHeadersGet() })
      const data = await r.json()
      setCameras(data.cameras || [])
    } catch { /* sin cámaras */ }
  }

  const runScan = async () => {
    setScanning(true); setSelectedHost(null); setScanError(null)
    addLog('Iniciando escaneo de topologia...')
    try {
      const r = await fetch('/api/scan/topology', { method: 'POST', headers: authHeaders() })
      if (!r.ok) {
        const errData = await r.json().catch(() => ({}))
        const msg = errData.error || `HTTP ${r.status}: ${r.statusText}`
        addLog(`Error: ${msg}`); setScanError(msg); return
      }
      const data = await r.json()
      if (data.error) { addLog(`Error: ${data.error}`); setScanError(data.error); return }
      setHosts(data.results || []); setSubnet(data.subnet || '')
      setLocalIp(data.local_ip || ''); setLocalHostname(data.local_hostname || '')
      addLog(`Topologia: ${data.hosts_up} hosts en ${data.subnet}`)
      addLog('Buscando camaras ONVIF/RTSP...')
      const camRes = await fetch('/api/scan/cameras', { method: 'POST', headers: authHeaders() })
      const camData = await camRes.json()
      setCameras(camData.cameras || camData.results || [])
      addLog(`Camaras encontradas: ${camData.cameras?.length || camData.results?.length || 0}`)
    } catch (e: any) { addLog(`Error: ${e.message}`) }
    finally { setScanning(false) }
  }

  const discoverAll = async () => {
    setScanning(true); addLog('Descubrimiento completo (ONVIF + SSDP + SNMP)...')
    try {
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
    } catch (e: any) { addLog(`Error: ${e.message}`) }
    finally { setScanning(false) }
  }

  const filteredHosts = hosts.filter(h => {
    if (filterRisk !== 'all' && h.risk !== filterRisk) return false
    if (filterType !== 'all' && h.type !== filterType) return false
    if (filterPort && !h.ports.some(p => p.port === parseInt(filterPort))) return false
    return true
  })

  const detectVideo = async (ip: string) => {
    setVideoLoading(true); setVideoUrls([])
    try {
      const r = await fetch(`/api/scan/video-urls?ip=${ip}`, { headers: authHeadersGet() })
      const data = await r.json()
      setVideoUrls(data.video_sources || [])
      addLog(`Video en ${ip}: ${data.video_sources?.length || 0} fuentes`)
    } catch (e: any) { addLog(`Error video: ${e.message}`) }
    finally { setVideoLoading(false) }
  }

  useEffect(() => {
    if (selectedHost) detectVideo(selectedHost.ip)
    else setVideoUrls([])
  }, [selectedHost])

  const MAP_W = 800, MAP_H = 500
  const positionedNodes = positionOnMap(filteredHosts, MAP_W, MAP_H)
  const typeCounts = hosts.reduce((acc, h) => { acc[h.type] = (acc[h.type] || 0) + 1; return acc }, {} as Record<string, number>)

  const riskStats = hosts.reduce((acc, h) => {
    acc[h.risk] = (acc[h.risk] || 0) + 1; return acc
  }, {} as Record<string, number>)

  return (
    <div className="space-y-4">
      {/* ═══ HEADER + CONTROLES ═══ */}
      <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
            <Radar size={20} className="text-cyan-400" />
            Global Network Map
            {subnet && <span className="text-xs text-slate-500 font-mono ml-2">{subnet}</span>}
          </h2>
          <div className="flex items-center gap-2">
            <button onClick={runScan} disabled={scanning} className="px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white text-xs rounded-lg flex items-center gap-1.5 disabled:opacity-50 transition-colors">
              {scanning ? <RefreshCw size={12} className="animate-spin" /> : <Scan size={12} />}
              {scanning ? 'Escaneando...' : 'Escanear Red'}
            </button>
            <button onClick={discoverAll} disabled={scanning} className="px-3 py-1.5 bg-red-600/80 hover:bg-red-500 text-white text-xs rounded-lg flex items-center gap-1.5 disabled:opacity-50 transition-colors">
              <Camera size={12} /> Descubrir Camaras
            </button>
          </div>
        </div>

        <div className="flex gap-1 mb-3">
          {([['topology', 'Mapa Global', Radar], ['cameras', `Camaras (${cameras.length})`, Camera], ['list', `Lista (${filteredHosts.length})`, Shield]] as const).map(([id, label, Icon]) => (
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

      {/* ═══ STATS BAR ═══ */}
      {hosts.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-2">
          <div className="bg-slate-950 border border-slate-800 rounded-lg p-2 text-center">
            <div className="text-[10px] text-slate-500">HOSTS</div>
            <div className="text-lg font-bold text-cyan-400">{hosts.length}</div>
          </div>
          <div className="bg-slate-950 border border-slate-800 rounded-lg p-2 text-center">
            <div className="text-[10px] text-slate-500">CAMARAS</div>
            <div className="text-lg font-bold text-blue-400">{cameras.length}</div>
          </div>
          {(['critical', 'high', 'medium', 'low'] as const).map(r => (
            <div key={r} className="bg-slate-950 border border-slate-800 rounded-lg p-2 text-center">
              <div className="text-[10px] text-slate-500">{RISK_LABELS[r].toUpperCase()}</div>
              <div className="text-lg font-bold" style={{ color: RISK_COLORS[r] }}>{riskStats[r] || 0}</div>
            </div>
          ))}
        </div>
      )}

      {/* ═══ MAPA + PANEL ═══ */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Vista principal */}
        <div className="lg:col-span-2 bg-slate-950 border border-slate-800 rounded-xl overflow-hidden">
          {scanError && hosts.length === 0 && (
            <div className="mb-3 p-3 rounded-lg border border-red-500/40 bg-red-500/10 text-red-300 text-sm flex items-center gap-2">
              <AlertCircle size={16} className="shrink-0" />
              <span>{scanError}</span>
              <button onClick={() => setScanError(null)} className="ml-auto text-red-400 hover:text-red-200"><X size={14} /></button>
            </div>
          )}

          {view === 'topology' && (
            <div className="relative bg-slate-900/30" style={{ minHeight: '520px' }}>
              {positionedNodes.length > GRID_THRESHOLD ? (
                <div className="p-4 overflow-y-auto" style={{ maxHeight: '560px' }}>
                  <div className="text-[10px] text-slate-500 mb-3 flex items-center gap-1.5">
                    <Fingerprint size={11} />
                    Red grande ({positionedNodes.length} hosts) — vista de cuadricula
                  </div>
                  <div className="grid gap-1.5" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(58px, 1fr))' }}>
                    {positionedNodes.map((n, i) => {
                      const color = RISK_COLORS[n.risk] || RISK_COLORS.unknown
                      const isSel = selectedHost?.ip === n.ip
                      const Icon = TYPE_ICONS[n.type] || Globe
                      return (
                        <button key={`g-${i}`} onClick={() => { setSelectedHost(n); setShowAll(false) }}
                          className="flex flex-col items-center gap-1 p-1.5 rounded-lg border transition-all hover:scale-105"
                          style={{ backgroundColor: isSel ? `${color}30` : `${color}12`, borderColor: color, borderWidth: isSel ? 2 : 1 }}
                          title={`${n.ip}\nTipo: ${n.type}\nRiesgo: ${RISK_LABELS[n.risk] || n.risk}\nPuertos: ${n.ports.map((p: any) => p.port).join(', ') || 'Ninguno'}`}>
                          <Icon size={13} color={color} />
                          <span className="font-mono text-[9px] leading-none" style={{ color }}>{n.ip.split('.').pop()}</span>
                          {n.ports.length > 0 && <span className="text-[7px] text-slate-500 leading-none">{n.ports.length}p</span>}
                        </button>
                      )
                    })}
                  </div>
                </div>
              ) : (
                <>
              {/* ═══ WORLD MAP SVG ═══ */}
              <svg ref={svgRef} className="w-full h-full" viewBox={`0 0 ${MAP_W} ${MAP_H}`} style={{ minHeight: '520px' }}>
                <defs>
                  {/* Gradients */}
                  <radialGradient id="centerGlow" cx="50%" cy="50%">
                    <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.25" />
                    <stop offset="100%" stopColor="#06b6d4" stopOpacity="0" />
                  </radialGradient>
                  <radialGradient id="radarSweep" cx="50%" cy="50%">
                    <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.4" />
                    <stop offset="70%" stopColor="#06b6d4" stopOpacity="0.05" />
                    <stop offset="100%" stopColor="#06b6d4" stopOpacity="0" />
                  </radialGradient>
                  <filter id="nodeGlow"><feGaussianBlur stdDeviation="3" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
                  <filter id="threatGlow"><feGaussianBlur stdDeviation="4" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
                  {/* Grid pattern */}
                  <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                    <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1a2a3a" strokeWidth="0.5" opacity="0.5" />
                  </pattern>
                  <pattern id="dots" width="20" height="20" patternUnits="userSpaceOnUse">
                    <circle cx="10" cy="10" r="0.8" fill="#1e3a5a" opacity="0.4" />
                  </pattern>
                  {/* Flowing line animation */}
                  <linearGradient id="flowLine">
                    <stop offset="0%" stopColor="#06b6d4" stopOpacity="0" />
                    <stop offset="50%" stopColor="#06b6d4" stopOpacity="0.8" />
                    <stop offset="100%" stopColor="#06b6d4" stopOpacity="0" />
                  </linearGradient>
                </defs>

                {/* Background layers */}
                <rect width={MAP_W} height={MAP_H} fill="#0a0e1a" />
                <rect width={MAP_W} height={MAP_H} fill="url(#dots)" />
                <rect width={MAP_W} height={MAP_H} fill="url(#grid)" />

                {/* World map silhouette */}
                <g opacity="0.08" fill="#06b6d4">
                  <path d={WORLD_MAP_PATH} transform={`translate(${MAP_W * 0.1}, ${MAP_H * 0.15}) scale(${MAP_W * 0.008}, ${MAP_H * 0.006})`} />
                  {/* Continent blobs */}
                  <ellipse cx={MAP_W * 0.3} cy={MAP_H * 0.35} rx={70} ry={50} />
                  <ellipse cx={MAP_W * 0.5} cy={MAP_H * 0.3} rx={60} ry={45} />
                  <ellipse cx={MAP_W * 0.65} cy={MAP_H * 0.4} rx={80} ry={55} />
                  <ellipse cx={MAP_W * 0.8} cy={MAP_H * 0.55} rx={50} ry={35} />
                  <ellipse cx={MAP_W * 0.25} cy={MAP_H * 0.6} rx={40} ry={30} />
                </g>

                {/* Latitude/longitude lines */}
                {[0.2, 0.4, 0.6, 0.8].map((v, i) => (
                  <line key={`lat-${i}`} x1={0} y1={MAP_H * v} x2={MAP_W} y2={MAP_H * v} stroke="#0f1e2e" strokeWidth="0.5" strokeDasharray="2 8" opacity="0.3" />
                ))}
                {[0.2, 0.4, 0.6, 0.8].map((v, i) => (
                  <line key={`lon-${i}`} x1={MAP_W * v} y1={0} x2={MAP_W * v} y2={MAP_H} stroke="#0f1e2e" strokeWidth="0.5" strokeDasharray="2 8" opacity="0.3" />
                ))}

                {/* Radar sweep (when scanning) */}
                {scanning && (
                  <g transform={`translate(${MAP_W / 2}, ${MAP_H / 2}) rotate(${radarSweep})`}>
                    <path d={`M 0 0 L 200 0 A 200 200 0 0 0 173 -100 Z`} fill="url(#radarSweep)" opacity="0.5" />
                  </g>
                )}

                {/* Center — this device */}
                <circle cx={MAP_W / 2} cy={MAP_H / 2} r={80} fill="url(#centerGlow)" />
                {/* Pulse rings */}
                <circle cx={MAP_W / 2} cy={MAP_H / 2} r={30} fill="none" stroke="#06b6d4" strokeWidth="1" opacity="0.3">
                  <animate attributeName="r" values="30;50;30" dur="3s" repeatCount="indefinite" />
                  <animate attributeName="opacity" values="0.5;0;0.5" dur="3s" repeatCount="indefinite" />
                </circle>
                <circle cx={MAP_W / 2} cy={MAP_H / 2} r={30} fill="none" stroke="#06b6d4" strokeWidth="1" opacity="0.2">
                  <animate attributeName="r" values="30;70;30" dur="3s" repeatCount="indefinite" begin="1s" />
                  <animate attributeName="opacity" values="0.3;0;0.3" dur="3s" repeatCount="indefinite" begin="1s" />
                </circle>
                {/* Center node */}
                <circle cx={MAP_W / 2} cy={MAP_H / 2} r={22} fill="#0c1e2e" stroke="#06b6d4" strokeWidth="2" filter="url(#nodeGlow)" />
                <foreignObject x={MAP_W / 2 - 14} y={MAP_H / 2 - 14} width="28" height="28">
                  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', width: '100%', height: '100%' }}>
                    <Crosshair size={16} color="#06b6d4" />
                  </div>
                </foreignObject>
                <text x={MAP_W / 2} y={MAP_H / 2 + 38} textAnchor="middle" fill="#e2e8f0" fontSize="10" fontWeight="bold" fontFamily="monospace">
                  {localHostname ? localHostname.toUpperCase() : 'ESTE DISPOSITIVO'}
                </text>
                <text x={MAP_W / 2} y={MAP_H / 2 + 50} textAnchor="middle" fill="#64748b" fontSize="9" fontFamily="monospace">
                  {localIp || `${subnet || '192.168.1'}.x`}
                </text>

                {/* Connection lines to center */}
                {positionedNodes.map((n, i) => {
                  const color = RISK_COLORS[n.risk] || RISK_COLORS.unknown
                  const isSel = selectedHost?.ip === n.ip
                  const isHover = hoveredHost?.ip === n.ip
                  const highlight = isSel || isHover
                  return (
                    <g key={`line-${i}`}>
                      {/* Base line */}
                      <line x1={MAP_W / 2} y1={MAP_H / 2} x2={n.x} y2={n.y}
                        stroke={highlight ? color : '#1a2a3e'} strokeWidth={highlight ? 1.5 : 0.8}
                        strokeDasharray={highlight ? '0' : '3 3'} opacity={highlight ? 0.7 : 0.3} />
                      {/* Animated flow dot on selected/highlighted */}
                      {highlight && (
                        <circle r="2" fill={color} opacity="0.8">
                          <animateMotion dur="2s" repeatCount="indefinite" path={`M ${MAP_W / 2},${MAP_H / 2} L ${n.x},${n.y}`} />
                        </circle>
                      )}
                    </g>
                  )
                })}

                {/* Inter-node connections (for critical/high risk) */}
                {positionedNodes.map((n, i) => {
                  if (n.risk !== 'critical' && n.risk !== 'high') return null
                  const color = RISK_COLORS[n.risk]
                  return positionedNodes.slice(i + 1).map((n2, j) => {
                    if (n2.risk !== 'critical' && n2.risk !== 'high') return null
                    const dist = Math.hypot(n.x - n2.x, n.y - n2.y)
                    if (dist > 200) return null
                    return (
                      <line key={`xl-${i}-${j}`} x1={n.x} y1={n.y} x2={n2.x} y2={n2.y}
                        stroke="#ef4444" strokeWidth="0.5" strokeDasharray="2 4" opacity="0.15" />
                    )
                  })
                })}

                {/* Nodes */}
                {positionedNodes.map((n, i) => {
                  const color = RISK_COLORS[n.risk] || RISK_COLORS.unknown
                  const isSel = selectedHost?.ip === n.ip
                  const isHover = hoveredHost?.ip === n.ip
                  const Icon = TYPE_ICONS[n.type] || Globe
                  const isThreat = n.risk === 'critical' || n.risk === 'high'
                  const nodeRadius = isSel ? 18 : isHover ? 16 : 14

                  return (
                    <g key={`node-${i}`} className="cursor-pointer"
                      onClick={() => { setSelectedHost(n); setShowAll(false) }}
                      onMouseEnter={() => setHoveredHost(n)}
                      onMouseLeave={() => setHoveredHost(null)}>
                      {/* Threat pulse */}
                      {isThreat && (
                        <circle cx={n.x} cy={n.y} r={nodeRadius} fill="none" stroke={color} strokeWidth="1" opacity="0.4">
                          <animate attributeName="r" values={`${nodeRadius};${nodeRadius + 10};${nodeRadius}`} dur="2s" repeatCount="indefinite" />
                          <animate attributeName="opacity" values="0.5;0;0.5" dur="2s" repeatCount="indefinite" />
                        </circle>
                      )}
                      {/* Node circle */}
                      <circle cx={n.x} cy={n.y} r={nodeRadius}
                        fill={isSel ? `${color}30` : '#0a0e1a'}
                        stroke={color} strokeWidth={isSel ? 2.5 : 1.5}
                        filter={isThreat ? 'url(#threatGlow)' : 'url(#nodeGlow)'} />
                      {/* Node icon */}
                      <foreignObject x={n.x - 10} y={n.y - 10} width="20" height="20">
                        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', width: '100%', height: '100%' }}>
                          <Icon size={12} color={color} />
                        </div>
                      </foreignObject>
                      {/* IP label (last octet) */}
                      <text x={n.x} y={n.y + nodeRadius + 10} textAnchor="middle"
                        fill={isSel || isHover ? '#e2e8f0' : '#64748b'}
                        fontSize="9" fontFamily="monospace" fontWeight={isSel ? 'bold' : 'normal'}>
                        {n.ip.split('.').pop()}
                      </text>
                      {/* Ports count badge */}
                      {n.ports.length > 0 && (
                        <text x={n.x + nodeRadius - 2} y={n.y - nodeRadius + 2} textAnchor="middle"
                          fill={color} fontSize="7" fontFamily="monospace" fontWeight="bold">
                          {n.ports.length}
                        </text>
                      )}
                      {/* Tooltip on hover */}
                      {isHover && !isSel && (
                        <g transform={`translate(${n.x}, ${n.y - nodeRadius - 10})`}>
                          <rect x={-60} y={-22} width="120" height="18" rx="4" fill="#0a0e1a" stroke="#1a2a3e" strokeWidth="0.5" opacity="0.95" />
                          <text x={0} y={-9} textAnchor="middle" fill="#06b6d4" fontSize="8" fontFamily="monospace">{n.ip}</text>
                        </g>
                      )}
                    </g>
                  )
                })}

                {/* Corner decorations — tactical */}
                {/* Top-left */}
                <path d={`M 0 20 L 0 0 L 20 0`} fill="none" stroke="#1a3a5e" strokeWidth="2" opacity="0.5" />
                {/* Top-right */}
                <path d={`M ${MAP_W} 20 L ${MAP_W} 0 L ${MAP_W - 20} 0`} fill="none" stroke="#1a3a5e" strokeWidth="2" opacity="0.5" />
                {/* Bottom-left */}
                <path d={`M 0 ${MAP_H - 20} L 0 ${MAP_H} L 20 ${MAP_H}`} fill="none" stroke="#1a3a5e" strokeWidth="2" opacity="0.5" />
                {/* Bottom-right */}
                <path d={`M ${MAP_W} ${MAP_H - 20} L ${MAP_W} ${MAP_H} L ${MAP_W - 20} ${MAP_H}`} fill="none" stroke="#1a3a5e" strokeWidth="2" opacity="0.5" />

                {/* Status text */}
                <text x={10} y={15} fill="#1e3a5e" fontSize="8" fontFamily="monospace">SECTOR: {subnet || '---'}</text>
                <text x={MAP_W - 10} y={15} textAnchor="end" fill="#1e3a5e" fontSize="8" fontFamily="monospace">
                  {scanning ? '● SCANNING' : hosts.length > 0 ? `● ${hosts.length} HOSTS` : '○ STANDBY'}
                </text>
              </svg>

              {/* Legend overlay */}
              <div className="absolute top-3 right-3 bg-slate-900/80 backdrop-blur border border-slate-700 rounded-lg p-2 space-y-1">
                <div className="text-[10px] text-slate-500 font-bold mb-1 flex items-center gap-1"><Radar size={10} /> RIESGO</div>
                {Object.entries(RISK_COLORS).map(([k, v]) => (
                  <div key={k} className="flex items-center gap-1.5 text-[10px]">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: v }} />
                    <span className="text-slate-400">{RISK_LABELS[k]}</span>
                  </div>
                ))}
              </div>

              {/* Type legend */}
              <div className="absolute bottom-3 left-3 bg-slate-900/80 backdrop-blur border border-slate-700 rounded-lg p-2">
                <div className="text-[10px] text-slate-500 font-bold mb-1 flex items-center gap-1"><Activity size={10} /> DISPOSITIVOS</div>
                <div className="flex flex-wrap gap-2 max-w-[200px]">
                  {Object.entries(typeCounts).map(([t, c]) => (
                    <div key={t} className="flex items-center gap-1 text-[10px]">
                      <span className="text-slate-400 capitalize">{t}</span>
                      <span className="text-cyan-400 font-bold">{c}</span>
                    </div>
                  ))}
                </div>
              </div>

              {positionedNodes.length === 0 && !scanning && (
                <div className="absolute inset-0 flex items-center justify-center flex-col gap-2 text-slate-600">
                  <Radar size={32} className="opacity-30" />
                  <span className="text-sm">{scanError ? `Error: ${scanError}` : 'Sin datos. Ejecuta un escaneo para ver el mapa global.'}</span>
                </div>
              )}
            </>
              )}
            </div>
          )}

          {view === 'cameras' && (
            <div className="p-4 grid grid-cols-1 sm:grid-cols-2 gap-3" style={{ minHeight: '520px' }}>
              {cameras.map((cam, i) => (
                <div key={i} className="p-3 rounded-lg border bg-slate-900 border-slate-700 hover:border-slate-600 transition-colors">
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
            <div className="p-2 overflow-y-auto" style={{ minHeight: '520px', maxHeight: '600px' }}>
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

        {/* ═══ PANEL LATERAL ═══ */}
        <div className="space-y-3">
          {selectedHost ? (
            <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2"><Crosshair size={14} className="text-cyan-400" />{selectedHost.ip}</h3>
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
                  <div className="text-[10px] text-red-500 font-bold mb-1 flex items-center gap-1"><Zap size={10} /> RAZONES DE RIESGO</div>
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
                <div key={i} onClick={() => { setSelectedHost(h); setShowAll(false) }} className="p-2 bg-slate-900 border border-slate-700 rounded-lg cursor-pointer hover:border-slate-600 flex items-center gap-2 transition-colors">
                  <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: RISK_COLORS[h.risk] || RISK_COLORS.unknown }} />
                  <span className="font-mono text-xs text-cyan-400">{h.ip}</span>
                  <span className="text-[10px] text-slate-500 capitalize">{h.type}</span>
                  <span className="text-[10px] text-slate-600 ml-auto">{h.ports.length}p</span>
                </div>
              ))}
              {filteredHosts.length === 0 && <div className="text-center text-slate-600 text-sm py-4">Sin hosts. Escanea la red.</div>}
            </div>
          ) : (
            /* Default panel — mission status */
            <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-3">
              <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2"><Radar size={14} className="text-cyan-400" /> Estado de Mision</h3>
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-slate-900 rounded-lg p-3">
                  <div className="text-[10px] text-slate-500 mb-1">SUBRED</div>
                  <div className="text-xs font-mono text-cyan-400">{subnet || '—'}</div>
                </div>
                <div className="bg-slate-900 rounded-lg p-3">
                  <div className="text-[10px] text-slate-500 mb-1">HOST LOCAL</div>
                  <div className="text-xs font-mono text-slate-300">{localIp || '—'}</div>
                  <div className="text-[10px] text-slate-500">{localHostname || ''}</div>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div className="bg-slate-900 rounded-lg p-2 text-center">
                  <div className="text-[10px] text-slate-500">HOSTS</div>
                  <div className="text-lg font-bold text-cyan-400">{hosts.length}</div>
                </div>
                <div className="bg-slate-900 rounded-lg p-2 text-center">
                  <div className="text-[10px] text-slate-500">CAMARAS</div>
                  <div className="text-lg font-bold text-blue-400">{cameras.length}</div>
                </div>
                <div className="bg-slate-900 rounded-lg p-2 text-center">
                  <div className="text-[10px] text-slate-500">AMENAZAS</div>
                  <div className="text-lg font-bold text-red-400">{(riskStats.critical || 0) + (riskStats.high || 0)}</div>
                </div>
              </div>
              {/* Log feed */}
              <div className="bg-slate-900 rounded-lg p-2">
                <div className="text-[10px] text-slate-500 mb-1 flex items-center gap-1"><Activity size={10} /> LOG</div>
                <div className="space-y-0.5 max-h-[200px] overflow-y-auto">
                  {logs.length === 0 && <div className="text-[10px] text-slate-600">Esperando actividad...</div>}
                  {logs.map((l, i) => <div key={i} className="text-[10px] text-slate-400 font-mono">{l}</div>)}
                </div>
              </div>
              {/* Device type breakdown */}
              {Object.keys(typeCounts).length > 0 && (
                <div className="bg-slate-900 rounded-lg p-2">
                  <div className="text-[10px] text-slate-500 mb-1 flex items-center gap-1"><Server size={10} /> DISPOSITIVOS</div>
                  <div className="space-y-1">
                    {Object.entries(typeCounts).map(([t, c]) => (
                      <div key={t} className="flex items-center gap-2">
                        <span className="text-[10px] text-slate-400 capitalize w-16">{t}</span>
                        <div className="flex-1 bg-slate-800 rounded-full h-1.5 overflow-hidden">
                          <div className="h-full bg-cyan-500 rounded-full" style={{ width: `${(c / hosts.length) * 100}%` }} />
                        </div>
                        <span className="text-[10px] text-cyan-400 font-bold w-6 text-right">{c}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
