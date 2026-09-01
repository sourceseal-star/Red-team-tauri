import { useState, useEffect, useCallback } from 'react'
import { Radar, Wifi, Camera, Router as RouterIcon, Server, Cpu, Smartphone,
         RefreshCw, Globe, AlertCircle, MapPin, Radio, Zap } from 'lucide-react'

function authHGet(): Record<string, string> {
  const k = localStorage.getItem('api_token')
  return k ? { 'Authorization': `Bearer ${k}` } : {}
}

const TYPE_META: Record<string, { icon: any, color: string, label: string }> = {
  router: { icon: RouterIcon, color: '#3b82f6', label: 'Router' },
  camera: { icon: Camera, color: '#ef4444', label: 'Camara' },
  server: { icon: Server, color: '#8b5cf6', label: 'Server' },
  iot: { icon: Cpu, color: '#f59e0b', label: 'IoT' },
  phone: { icon: Smartphone, color: '#10b981', label: 'Movil' },
  unknown: { icon: Globe, color: '#64748b', label: '?' },
}
const RISK_COLOR: Record<string, string> = { low: '#10b981', medium: '#eab308', high: '#f97316', critical: '#ef4444' }
const PORT_NAMES: Record<number, string> = { 80:'HTTP',443:'HTTPS',554:'RTSP',22:'SSH',23:'Telnet',8080:'HTTP-Alt',8000:'HTTP-Alt',37777:'DVR-Hik',34567:'DVR-Dahua',53:'DNS',161:'SNMP',21:'FTP',9000:'Web' }

export default function NetworkMapPanel() {
  const [hosts, setHosts] = useState<any[]>([])
  const [wifiNets, setWifiNets] = useState<any[]>([])
  const [netInfo, setNetInfo] = useState<any>(null)
  const [interfaces, setInterfaces] = useState<any[]>([])
  const [selectedIface, setSelectedIface] = useState('')
  const [loading, setLoading] = useState(false)
  const [wifiLoading, setWifiLoading] = useState(false)
  const [errors, setErrors] = useState<string[]>([])
  const [selected, setSelected] = useState<any>(null)

  const loadNetInfo = useCallback(async () => {
    try {
      const [ni, ifaces] = await Promise.all([
        fetch('/api/network/info', { headers: authHGet() }).catch(() => null),
        fetch('/api/network/interfaces', { headers: authHGet() }).catch(() => null)
      ])
      if (ni?.ok) setNetInfo(await ni.json())
      if (ifaces?.ok) {
        const data = await ifaces.json()
        setInterfaces(data)
        const wifi = data.find((i: any) => i.type_hint === 'wifi' || i.type_hint === 'auto-detected')
        if (wifi) {
          setSelectedIface(wifi.network_cidr)
          setNetInfo((prev: any) => ({ ...prev, subnet: wifi.network_cidr, local_ip: wifi.ip_address }))
        }
      }
    } catch {}
  }, [])

  const discoverWithSubnet = useCallback(async (subnet: string) => {
    setLoading(true); setErrors([])
    try {
      const r = await fetch(`/api/discover/network?subnet=${encodeURIComponent(subnet)}`, { headers: authHGet() })
      const data = await r.json()
      setHosts(data.results || [])
      if (data.hosts_up <= 1) setErrors(['No se encontraron dispositivos en ' + subnet + '. Verifica estar conectado a esa red.'])
    } catch (e: any) { setErrors([`Error: ${e.message}`]) }
    finally { setLoading(false) }
  }, [])

  const discover = useCallback(async () => {
    setLoading(true); setErrors([])
    try {
      const r = await fetch('/api/discover/network', { headers: authHGet() })
      const data = await r.json()
      setHosts(data.results || [])
      if (data.hosts_up <= 1) setErrors(['No se encontraron dispositivos. Verifica estar en la misma red WiFi que las camaras/routers.'])
    } catch (e: any) { setErrors([`Error: ${e.message}`]) }
    finally { setLoading(false) }
  }, [])

  const scanWifi = useCallback(async () => {
    setWifiLoading(true)
    try {
      const r = await fetch('/api/discover/wifi', { headers: authHGet() })
      const data = await r.json()
      setWifiNets(data.networks || [])
      if (data.networks?.length === 0 && data.errors) setErrors(p => [...p, ...data.errors])
    } catch (e: any) { setErrors([`WiFi: ${e.message}`]) }
    finally { setWifiLoading(false) }
  }, [])

  useEffect(() => { loadNetInfo(); discover() }, [loadNetInfo, discover])

  const cameras = hosts.filter(h => h.type === 'camera')
  const routers = hosts.filter(h => h.type === 'router')
  const iotDev = hosts.filter(h => h.type === 'iot')

  const positions = () => {
    const cx=50, cy=50, r=35
    return hosts.map((_, i) => {
      if (i === 0) return { x: cx, y: cy }
      const a = ((i-1)/Math.max(1,hosts.length-1)) * 2 * Math.PI
      return { x: cx + r*Math.cos(a), y: cy + r*Math.sin(a) }
    })
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2 min-w-0">
        <div className="min-w-0">
          <h2 className="text-lg font-bold text-white flex items-center gap-2"><MapPin size={18} className="text-cyan-400 shrink-0" /> <span className="truncate">Mapa de Red</span></h2>
          <p className="text-xs text-slate-500">Descubrimiento ARP + TCP scan (sin root)</p>
        </div>
        <button onClick={() => { discover(); scanWifi() }} className="px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 rounded-lg text-xs font-bold text-white flex items-center gap-1 whitespace-nowrap">
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} /> Re-escanear
        </button>
      </div>

      {interfaces.length > 0 && (
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
          <h3 className="text-sm font-bold text-cyan-400 mb-2 flex items-center gap-2"><Radar size={14} /> Selector de Red</h3>
          <div className="flex gap-2 flex-wrap sm:flex-nowrap min-w-0">
            <select value={selectedIface} onChange={(e) => setSelectedIface(e.target.value)}
              className="flex-1 min-w-0 bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-xs text-white">
              {interfaces.map((iface, i) => (
                <option key={i} value={iface.network_cidr}>
                  {iface.name} ({iface.type_hint}) — {iface.ip_address} [{iface.network_cidr}]
                </option>
              ))}
            </select>
            <button onClick={() => { if (selectedIface) { discoverWithSubnet(selectedIface) } }}
              className="px-4 py-1.5 bg-cyan-600 hover:bg-cyan-500 rounded text-xs font-bold text-white whitespace-nowrap">
              Escanear
            </button>
          </div>
          {netInfo && (
            <div className="mt-2 flex items-center gap-4 text-xs">
              <span className="text-slate-500">IP: </span><span className="text-green-400 font-mono">{netInfo.local_ip || '---'}</span>
              <span className="text-slate-500">Subred: </span><span className="text-cyan-400 font-mono">{selectedIface || netInfo.subnet || '---'}</span>
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
        <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-2 text-center"><p className="text-lg font-bold text-white">{hosts.length}</p><p className="text-[9px] text-slate-500 uppercase">Dispositivos</p></div>
        <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-2 text-center"><p className="text-lg font-bold text-red-400">{cameras.length}</p><p className="text-[9px] text-slate-500 uppercase">Camaras</p></div>
        <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-2 text-center"><p className="text-lg font-bold text-blue-400">{routers.length}</p><p className="text-[9px] text-slate-500 uppercase">Routers</p></div>
        <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-2 text-center"><p className="text-lg font-bold text-amber-400">{iotDev.length}</p><p className="text-[9px] text-slate-500 uppercase">IoT</p></div>
        <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-2 text-center"><p className="text-lg font-bold text-green-400">{wifiNets.length}</p><p className="text-[9px] text-slate-500 uppercase">WiFi</p></div>
      </div>

      {errors.length > 0 && (
        <div className="bg-amber-900/30 border border-amber-800 rounded-lg p-3 space-y-1">
          {errors.map((e, i) => <div key={i} className="text-xs text-amber-400 flex items-start gap-2"><AlertCircle size={12} className="mt-0.5 shrink-0" /><span>{e}</span></div>)}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
          <h3 className="text-sm font-bold text-cyan-400 mb-3 flex items-center gap-2"><Radio size={14} /> Topologia</h3>
          {loading && hosts.length === 0 ? (
            <div className="flex items-center justify-center h-64 text-slate-600"><RefreshCw size={20} className="animate-spin" /></div>
          ) : hosts.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 text-slate-600 text-xs"><AlertCircle size={24} className="mb-2" /><p>No se encontraron dispositivos.</p><p className="mt-1">Estas en la misma red WiFi que las camaras?</p></div>
          ) : (
            <div className="relative w-full" style={{ height: '320px' }}>
              <svg viewBox="0 0 100 100" className="w-full h-full">
                {hosts.length > 1 && (() => {
                  const pos = positions(); const c = pos[0]
                  return pos.slice(1).map((p, i) => <line key={`l${i}`} x1={c.x} y1={c.y} x2={p.x} y2={p.y} stroke="rgba(0,229,255,0.2)" strokeWidth="0.3" />)
                })()}
                {hosts.map((h, i) => {
                  const pos = positions()[i]; const meta = TYPE_META[h.type] || TYPE_META.unknown; const rc = RISK_COLOR[h.risk] || '#64748b'
                  return (
                    <g key={h.ip} onClick={() => setSelected(h)} style={{ cursor: 'pointer' }}>
                      <circle cx={pos.x} cy={pos.y} r="4" fill={meta.color} fillOpacity="0.2" stroke={meta.color} strokeWidth="0.5" />
                      <circle cx={pos.x} cy={pos.y} r="1.5" fill={meta.color} />
                      {h.risk === 'critical' && <circle cx={pos.x} cy={pos.y} r="5" fill="none" stroke={rc} strokeWidth="0.3" strokeDasharray="1,1" className="animate-pulse" />}
                      <text x={pos.x} y={pos.y + 6} textAnchor="middle" fill="#94a3b8" fontSize="2.5" fontFamily="monospace">{h.ip.split('.').pop()}</text>
                    </g>
                  )
                })}
              </svg>
              <div className="absolute bottom-0 left-0 flex flex-wrap gap-2 text-[9px]">
                {Object.entries(TYPE_META).map(([k, v]) => <div key={k} className="flex items-center gap-1"><div className="w-2 h-2 rounded-full" style={{ background: v.color }} /><span className="text-slate-500">{v.label}</span></div>)}
              </div>
            </div>
          )}
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
          <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2"><Server size={14} /> Dispositivos ({hosts.length})</h3>
          <div className="space-y-1 max-h-72 overflow-y-auto">
            {hosts.map((h, i) => {
              const meta = TYPE_META[h.type] || TYPE_META.unknown; const Icon = meta.icon; const rc = RISK_COLOR[h.risk] || '#64748b'
              return (
                <div key={i} onClick={() => setSelected(h)} className={`flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer transition-colors ${selected?.ip === h.ip ? 'bg-slate-800' : 'hover:bg-slate-800/50'}`}>
                  <Icon size={14} style={{ color: meta.color }} />
                  <span className="font-mono text-xs text-white">{h.ip}</span>
                  <span className="text-[10px] text-slate-500">{meta.label}</span>
                  {h.mac && <span className="text-[9px] text-slate-600 hidden sm:inline">{h.mac}</span>}
                  <div className="ml-auto flex items-center gap-1">
                    {Array.isArray(h.ports) && h.ports.map((p: any, j: number) => <span key={j} className="text-[8px] px-1 rounded bg-slate-800 text-slate-400">{PORT_NAMES[p.port] || p.port}</span>)}
                    <div className="w-1.5 h-1.5 rounded-full" style={{ background: rc }} />
                  </div>
                </div>
              )
            })}
            {hosts.length === 0 && !loading && <p className="text-xs text-slate-600 text-center py-4">Sin dispositivos.</p>}
          </div>
        </div>
      </div>

      {selected && (
        <div className="bg-slate-900/60 border border-cyan-800 rounded-xl p-4">
          <h3 className="text-sm font-bold text-cyan-400 mb-2 flex items-center gap-2"><Zap size={14} /> Detalle: {selected.ip}</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <div><span className="text-slate-500">Tipo: </span><span className="text-white">{TYPE_META[selected.type]?.label || selected.type}</span></div>
            <div><span className="text-slate-500">MAC: </span><span className="text-white font-mono">{selected.mac || '---'}</span></div>
            <div><span className="text-slate-500">Riesgo: </span><span style={{ color: RISK_COLOR[selected.risk] }}>{selected.risk}</span></div>
            <div><span className="text-slate-500">Fuente: </span><span className="text-white">{selected.source}</span></div>
          </div>
          {selected.risk_reasons?.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {selected.risk_reasons.map((r: string, i: number) => <span key={i} className="text-[10px] px-2 py-0.5 rounded bg-red-900/30 text-red-400 border border-red-800">{r}</span>)}
            </div>
          )}
          {Array.isArray(selected.ports) && selected.ports.length > 0 && (
            <div className="mt-2"><span className="text-xs text-slate-500">Puertos: </span>
              <div className="flex flex-wrap gap-1 mt-1">
                {selected.ports.map((p: any, i: number) => <span key={i} className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-cyan-400">{p.port}/{PORT_NAMES[p.port] || p.service}</span>)}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
        <h3 className="text-sm font-bold text-green-400 mb-3 flex items-center gap-2"><Wifi size={14} /> Redes WiFi ({wifiNets.length})
          <button onClick={scanWifi} disabled={wifiLoading} className="ml-auto px-2 py-1 bg-green-700 hover:bg-green-600 disabled:opacity-50 rounded text-[10px] text-white flex items-center gap-1">
            {wifiLoading ? <RefreshCw size={10} className="animate-spin" /> : <Wifi size={10} />} Escanear
          </button>
        </h3>
        {wifiNets.length > 0 ? (
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {wifiNets.map((n, i) => (
              <div key={i} className="flex items-center gap-2 text-xs bg-slate-950/50 rounded px-2 py-1.5">
                <Wifi size={12} className={n.rssi > -60 ? 'text-green-400' : n.rssi > -80 ? 'text-yellow-400' : 'text-red-400'} />
                <span className="text-white font-mono truncate max-w-32">{n.ssid || 'Hidden'}</span>
                <span className="text-slate-600 font-mono text-[10px]">{n.bssid}</span>
                <span className="text-slate-500">CH{n.channel}</span>
                <div className="ml-auto flex items-center gap-2">
                  <span className="text-slate-500">{n.rssi}dBm</span>
                  <div className="w-12 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${Math.max(0, Math.min(100, n.rssi + 100))}%`, background: n.rssi > -60 ? '#10b981' : n.rssi > -80 ? '#eab308' : '#ef4444' }} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs text-slate-600 space-y-1">
            <p>Para escanear WiFi necesitas:</p>
            <p>1. App <span className="text-green-400">Termux:API</span> (F-Droid)</p>
            <p>2. Permiso <span className="text-green-400">Ubicacion</span> concedido</p>
            <p>3. <span className="text-green-400">GPS activado</span></p>
          </div>
        )}
      </div>
    </div>
  )
}
