import { useCallback, useEffect, useState, type ReactNode } from 'react'
import {
  AlertCircle, CheckCircle2, ExternalLink, LocateFixed, MapPin,
  Navigation, Radar, RefreshCw, ScanLine, Shield, Smartphone, Wifi
} from 'lucide-react'

function authHeaders(json = false): Record<string, string> {
  const token = localStorage.getItem('api_token')
  const headers: Record<string, string> = {}
  if (json) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`
  return headers
}

function Card({ children, className = '' }: { children: ReactNode, className?: string }) {
  return <section className={`bg-slate-900/60 border border-slate-800 rounded-xl p-4 ${className}`}>{children}</section>
}

function Button({ children, onClick, disabled = false, tone = 'cyan' }: {
  children: ReactNode, onClick: () => void, disabled?: boolean, tone?: string
}) {
  const colors: Record<string, string> = {
    cyan: 'bg-cyan-600 hover:bg-cyan-500',
    green: 'bg-green-600 hover:bg-green-500',
    amber: 'bg-amber-600 hover:bg-amber-500',
    indigo: 'bg-indigo-600 hover:bg-indigo-500',
  }
  return <button onClick={onClick} disabled={disabled}
    className={`px-3 py-2 ${colors[tone] || colors.cyan} disabled:opacity-50 rounded-lg text-xs font-bold text-white flex items-center justify-center gap-1.5`}>
    {children}
  </button>
}

export default function AndroidFieldPanel() {
  const [status, setStatus] = useState<any>(null)
  const [location, setLocation] = useState<any>(null)
  const [locationLoading, setLocationLoading] = useState(false)
  const [lat, setLat] = useState('')
  const [lon, setLon] = useState('')
  const [label, setLabel] = useState('SourceSeal')
  const [wifi, setWifi] = useState<any>(null)
  const [wifiLoading, setWifiLoading] = useState(false)
  const [nearby, setNearby] = useState<any[]>([])
  const [interfaces, setInterfaces] = useState<any[]>([])
  const [selectedSubnet, setSelectedSubnet] = useState('')
  const [autoHosts, setAutoHosts] = useState<any[]>([])
  const [autoLoading, setAutoLoading] = useState(false)
  const [target, setTarget] = useState('')
  const [ports, setPorts] = useState('22,53,80,443,554,8000,8080,8443')
  const [manualConfirmed, setManualConfirmed] = useState(false)
  const [manualLoading, setManualLoading] = useState(false)
  const [manualResult, setManualResult] = useState<any>(null)
  const [message, setMessage] = useState<{ type: 'ok' | 'error' | 'info', text: string } | null>(null)

  const request = useCallback(async (url: string, init?: RequestInit) => {
    const response = await fetch(url, { ...init, headers: { ...authHeaders(Boolean(init?.body)), ...(init?.headers || {}) } })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.detail || data.error || `HTTP ${response.status}`)
    return data
  }, [])

  const loadStatus = useCallback(async () => {
    try { setStatus(await request('/api/android/status')) }
    catch (e: any) { setMessage({ type: 'error', text: `Android: ${e.message}` }) }
  }, [request])

  const loadInterfaces = useCallback(async () => {
    try {
      const data = await request('/api/network/interfaces')
      const usable = (Array.isArray(data) ? data : []).filter((iface: any) =>
        iface.network_cidr && iface.type_hint !== 'loopback' && iface.type_hint !== 'error' &&
        !String(iface.network_cidr).startsWith('127.')
      )
      setInterfaces(usable)
      if (!selectedSubnet) {
        const preferred = usable.find((iface: any) =>
          ['wifi', 'hotspot', 'mobile', 'ethernet', 'auto-detected'].includes(iface.type_hint)
        )
        if (preferred) setSelectedSubnet(preferred.network_cidr)
      }
    } catch (e: any) {
      setMessage({ type: 'error', text: `Interfaces: ${e.message}` })
    }
  }, [request, selectedSubnet])

  useEffect(() => { loadStatus(); loadInterfaces() }, [loadStatus, loadInterfaces])

  const readLocation = async () => {
    setLocationLoading(true); setMessage(null)
    try {
      const data = await request('/api/android/location')
      setLocation(data)
      if (data.latitude != null) setLat(String(data.latitude))
      if (data.longitude != null) setLon(String(data.longitude))
      setMessage({ type: 'ok', text: `Ubicación recibida mediante ${data.provider_requested || 'Termux:API'}.` })
    } catch (e: any) { setMessage({ type: 'error', text: e.message }) }
    finally { setLocationLoading(false) }
  }

  const openOsmand = async () => {
    setMessage(null)
    try {
      const data = await request('/api/android/open-osmand', {
        method: 'POST',
        body: JSON.stringify({ latitude: lat, longitude: lon, label })
      })
      setMessage({ type: 'ok', text: `OsmAnd abierto (${data.method}).` })
    } catch (e: any) { setMessage({ type: 'error', text: e.message }) }
  }

  const loadWifi = async () => {
    setWifiLoading(true); setMessage(null)
    try {
      const data = await request('/api/android/wifi')
      setWifi(data)
      setMessage({ type: 'ok', text: 'Estado de Wi‑Fi/hotspot actualizado.' })
    } catch (e: any) { setMessage({ type: 'error', text: e.message }) }
    finally { setWifiLoading(false) }
  }

  const scanNearby = async () => {
    setWifiLoading(true); setMessage(null)
    try {
      const data = await request('/api/wifi/scan')
      setNearby(data.networks || [])
      setMessage({ type: 'ok', text: `${data.networks?.length || 0} redes encontradas (${data.method || 'sin método'}).` })
    } catch (e: any) { setMessage({ type: 'error', text: e.message }) }
    finally { setWifiLoading(false) }
  }

  const openNetguard = async () => {
    try {
      const data = await request('/api/android/open-netguard', { method: 'POST' })
      setMessage({ type: 'ok', text: `NetGuard abierto (${data.package}).` })
    } catch (e: any) { setMessage({ type: 'error', text: e.message }) }
  }

  const automaticScan = async () => {
    const subnet = selectedSubnet.trim()
    if (!subnet) return setMessage({ type: 'error', text: 'Selecciona o escribe una red de campo antes de escanear.' })
    if (subnet.startsWith('127.')) return setMessage({ type: 'error', text: 'La red loopback no es una red de campo válida.' })
    setAutoLoading(true); setMessage(null)
    try {
      const data = await request(`/api/discover/network?subnet=${encodeURIComponent(subnet)}`)
      setAutoHosts(data.results || [])
      setMessage({ type: 'ok', text: `Escaneo automático: ${data.hosts_up || 0} hosts (${data.method || 'red local'}).` })
    } catch (e: any) { setMessage({ type: 'error', text: e.message }) }
    finally { setAutoLoading(false) }
  }

  const manualScan = async () => {
    if (!target.trim()) return setMessage({ type: 'error', text: 'Escribe una IP o CIDR antes de escanear.' })
    if (!manualConfirmed) return setMessage({ type: 'error', text: 'Confirma manualmente que tienes autorización sobre el objetivo.' })
    setManualLoading(true); setManualResult(null); setMessage(null)
    try {
      const data = await request('/api/android/port-scan', {
        method: 'POST',
        body: JSON.stringify({ target, ports, confirm_manual: true })
      })
      setManualResult(data)
      setMessage({ type: 'ok', text: `Escaneo terminado: ${data.open_ports || 0} puertos abiertos.` })
    } catch (e: any) { setMessage({ type: 'error', text: e.message }) }
    finally { setManualLoading(false) }
  }

  const inputClass = 'w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-600'
  const termuxReady = status?.termux_api?.location || status?.termux_api?.wifi_connection

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2"><Smartphone size={18} className="text-cyan-400" /> Android / Campo</h2>
          <p className="text-xs text-slate-500">GPS · OsmAnd · Wi‑Fi/hotspot · NetGuard · escaneo controlado</p>
        </div>
        <Button onClick={loadStatus} tone="cyan"><RefreshCw size={13} /> Actualizar estado</Button>
      </div>

      {message && (
        <div className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-xs ${
          message.type === 'ok' ? 'bg-green-950/40 border-green-800 text-green-400' :
          message.type === 'error' ? 'bg-red-950/40 border-red-800 text-red-400' :
          'bg-cyan-950/40 border-cyan-800 text-cyan-400'
        }`}>
          {message.type === 'ok' ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />} {message.text}
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {[
          ['Termux:API', termuxReady ? 'Disponible' : 'No detectado', termuxReady ? 'text-green-400' : 'text-amber-400'],
          ['OsmAnd', status?.osmand_package ? 'Instalado' : 'No detectado', status?.osmand_package ? 'text-green-400' : 'text-slate-500'],
          ['NetGuard', status?.netguard_package ? 'Instalado' : 'No detectado', status?.netguard_package ? 'text-green-400' : 'text-slate-500'],
          ['Corset', status?.scope?.configured ? 'Configurado' : 'Manual', status?.scope?.configured ? 'text-green-400' : 'text-amber-400'],
          ['Modo', 'Bajo demanda', 'text-cyan-400'],
        ].map(([name, value, color]) => (
          <div key={name} className="bg-slate-900/60 border border-slate-800 rounded-xl p-3">
            <span className="text-[10px] uppercase text-slate-500">{name}</span>
            <p className={`text-sm font-bold ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Card>
          <h3 className="text-sm font-bold text-cyan-400 mb-3 flex items-center gap-2"><LocateFixed size={15} /> GPS y OsmAnd</h3>
          <div className="flex gap-2 mb-3">
            <Button onClick={readLocation} disabled={locationLoading} tone="cyan">
              {locationLoading ? <RefreshCw size={13} className="animate-spin" /> : <LocateFixed size={13} />} Leer ubicación
            </Button>
            <Button onClick={openOsmand} disabled={!lat || !lon} tone="indigo"><Navigation size={13} /> Abrir en OsmAnd</Button>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <input className={inputClass} placeholder="Latitud" value={lat} onChange={e => setLat(e.target.value)} />
            <input className={inputClass} placeholder="Longitud" value={lon} onChange={e => setLon(e.target.value)} />
          </div>
          <input className={`${inputClass} mt-2`} placeholder="Etiqueta opcional" value={label} onChange={e => setLabel(e.target.value)} />
          {location && <p className="text-[10px] text-slate-500 mt-2 font-mono">Precisión: {location.accuracy ?? '—'} m · altitud: {location.altitude ?? '—'} m</p>}
          <p className="text-[10px] text-slate-600 mt-2">La lectura es puntual. Requiere Termux:API y permiso de ubicación.</p>
        </Card>

        <Card>
          <h3 className="text-sm font-bold text-green-400 mb-3 flex items-center gap-2"><Wifi size={15} /> Wi‑Fi y hotspot</h3>
          <div className="flex gap-2 mb-3 flex-wrap">
            <Button onClick={loadWifi} disabled={wifiLoading} tone="green"><Wifi size={13} /> Estado Wi‑Fi</Button>
            <Button onClick={scanNearby} disabled={wifiLoading} tone="green"><Radar size={13} /> Escaneo cercano</Button>
          </div>
          {wifi && (
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="bg-slate-950 rounded p-2"><span className="text-slate-500">SSID</span><p className="text-white truncate">{wifi.connection?.ssid || '—'}</p></div>
              <div className="bg-slate-950 rounded p-2"><span className="text-slate-500">IP</span><p className="text-white font-mono">{wifi.connection?.ip || '—'}</p></div>
              <div className="bg-slate-950 rounded p-2 col-span-2"><span className="text-slate-500">Hotspot</span><p className={wifi.hotspot?.detected ? 'text-green-400' : 'text-slate-400'}>{wifi.hotspot?.detected ? 'Interfaz detectada' : 'No confirmado por Android'}</p></div>
            </div>
          )}
          {nearby.length > 0 && <div className="mt-3 max-h-28 overflow-y-auto space-y-1">{nearby.map((net, i) => (
            <div key={i} className="flex gap-2 text-[10px] bg-slate-950 rounded px-2 py-1 text-slate-300">
              <span className="truncate flex-1">{net.ssid || 'Hidden'}</span><span>{net.signal ?? '—'} dBm</span><span className="text-slate-600">{net.channel ? `CH${net.channel}` : ''}</span>
            </div>
          ))}</div>}
        </Card>

        <Card>
          <h3 className="text-sm font-bold text-slate-300 mb-3 flex items-center gap-2"><Shield size={15} /> NetGuard</h3>
          <p className="text-xs text-slate-500 mb-3">Se detecta la instalación y se puede abrir. El cambio de reglas continúa bajo control directo de NetGuard.</p>
          <Button onClick={openNetguard} disabled={!status?.netguard_package} tone="indigo"><ExternalLink size={13} /> Abrir NetGuard</Button>
        </Card>

        <Card>
          <h3 className="text-sm font-bold text-amber-400 mb-3 flex items-center gap-2"><ScanLine size={15} /> Escaneo automático de red</h3>
          <p className="text-xs text-slate-500 mb-3">Elige la interfaz o introduce el CIDR. El escaneo solo comienza al pulsar el botón.</p>
          <div className="flex gap-2 mb-3 flex-wrap">
            <select value={selectedSubnet} onChange={e => setSelectedSubnet(e.target.value)}
              className={`${inputClass} flex-1 min-w-[12rem]`}>
              <option value="">Seleccionar interfaz...</option>
              {interfaces.map((iface, i) => (
                <option key={`${iface.name}-${i}`} value={iface.network_cidr}>
                  {iface.name} ({iface.type_hint}) — {iface.network_cidr}
                </option>
              ))}
            </select>
            <input className={`${inputClass} flex-1 min-w-[12rem]`} placeholder="o escribe 192.168.1.0/24"
              value={selectedSubnet} onChange={e => setSelectedSubnet(e.target.value)} />
          </div>
          <Button onClick={automaticScan} disabled={autoLoading} tone="amber">
            {autoLoading ? <RefreshCw size={13} className="animate-spin" /> : <Radar size={13} />} Ejecutar escaneo automático
          </Button>
          {autoHosts.length > 0 && <div className="mt-3 max-h-32 overflow-y-auto space-y-1">{autoHosts.map((host, i) => (
            <div key={i} className="flex items-center gap-2 bg-slate-950 rounded px-2 py-1 text-[10px]">
              <MapPin size={11} className="text-amber-400" /><span className="font-mono text-white">{host.ip}</span><span className="text-slate-500">{host.type || 'unknown'}</span><span className="ml-auto text-slate-600">{host.ports?.map((p: any) => p.port).join(', ')}</span>
            </div>
          ))}</div>}
        </Card>
      </div>

      <Card>
        <h3 className="text-sm font-bold text-red-400 mb-1 flex items-center gap-2"><ScanLine size={15} /> Escaneo manual de puertos</h3>
        <p className="text-[11px] text-slate-500 mb-3">TCP connect, solo IP/CIDR introducido manualmente. Máximo 256 hosts y 32 puertos; respeta el alcance Corset cuando está configurado.</p>
        <div className="grid grid-cols-1 md:grid-cols-[1fr_2fr_auto] gap-2 items-end">
          <label className="text-[10px] text-slate-500">Objetivo IP/CIDR<input className={`${inputClass} mt-1`} placeholder="192.168.1.1 o 192.168.1.0/24" value={target} onChange={e => setTarget(e.target.value)} /></label>
          <label className="text-[10px] text-slate-500">Puertos<input className={`${inputClass} mt-1`} value={ports} onChange={e => setPorts(e.target.value)} /></label>
          <Button onClick={manualScan} disabled={manualLoading || !manualConfirmed} tone="amber">
            {manualLoading ? <RefreshCw size={13} className="animate-spin" /> : <ScanLine size={13} />} Escanear
          </Button>
        </div>
        <label className="flex items-start gap-2 mt-3 text-[11px] text-slate-400 cursor-pointer">
          <input type="checkbox" className="mt-0.5 accent-amber-500" checked={manualConfirmed} onChange={e => setManualConfirmed(e.target.checked)} />
          Confirmo que tengo autorización para probar este objetivo y que el alcance introducido es correcto.
        </label>
        {manualResult && <pre className="mt-3 bg-black/50 rounded p-3 text-[10px] text-green-400 font-mono max-h-48 overflow-y-auto whitespace-pre-wrap">{JSON.stringify(manualResult, null, 2)}</pre>}
      </Card>
    </div>
  )
}