import { useState, useEffect, useCallback } from 'react'
import { Radar, Search, Camera, Wifi, Terminal, Radio, Crosshair,
         Activity, Globe, Shield, Cpu, Server, Zap, RefreshCw, AlertCircle } from 'lucide-react'

function authH(): Record<string, string> {
  const k = localStorage.getItem('api_token')
  const h: Record<string, string> = { 'Content-Type': 'application/json' }
  if (k) h['Authorization'] = `Bearer ${k}`
  return h
}
function authHGet(): Record<string, string> {
  const k = localStorage.getItem('api_token')
  return k ? { 'Authorization': `Bearer ${k}` } : {}
}

export default function CommanderPanel() {
  const [cmdHealth, setCmdHealth] = useState<any>(null)
  const [rtHealth, setRtHealth] = useState<any>(null)
  const [phantomStatus, setPhantomStatus] = useState<any>(null)
  const [comlink, setComlink] = useState<any>(null)
  const [comlinkChannel, setComlinkChannel] = useState('sms')
  const [comlinkDestination, setComlinkDestination] = useState('')
  const [comlinkMessage, setComlinkMessage] = useState('')
  const [comlinkSending, setComlinkSending] = useState(false)
  const [comlinkResult, setComlinkResult] = useState<string>('')
  const [comlinkSuccess, setComlinkSuccess] = useState<boolean | null>(null)
  const [scanTarget, setScanTarget] = useState('')
  const [scanResult, setScanResult] = useState<string>('')
  const [scanning, setScanning] = useState(false)
  const [osintType, setOsintType] = useState('ip')
  const [osintQuery, setOsintQuery] = useState('')
  const [osintResult, setOsintResult] = useState<string>('')
  const [osintLoading, setOsintLoading] = useState(false)
  const [netInfo, setNetInfo] = useState<any>(null)
  const [wifiNets, setWifiNets] = useState<any[]>([])
  const [wifiLoading, setWifiLoading] = useState(false)
  const [huntQuery, setHuntQuery] = useState('')
  const [huntPlaybook, setHuntPlaybook] = useState('generic')
  const [huntResult, setHuntResult] = useState<string>('')
  const [huntLoading, setHuntLoading] = useState(false)
  const [topoHosts, setTopoHosts] = useState<any[]>([])
  const [topoLoading, setTopoLoading] = useState(false)
  const [topoSubnet, setTopoSubnet] = useState('')

  const comlinkChannels = (Array.isArray(comlink?.channels) ? comlink.channels : []).map((channel: any) =>
    typeof channel === 'string' ? { id: channel, ready: true, reason: '' } : channel
  )
  const selectedComlinkChannel = comlinkChannels.find((channel: any) => channel.id === comlinkChannel)
  const comlinkCanSend = Boolean(selectedComlinkChannel?.ready)

  const refresh = useCallback(async () => {
    try {
      const [cmd, rt, ph, cl, ni] = await Promise.all([
        fetch('/api/commander/health', { headers: authHGet() }).catch(() => null),
        fetch('/api/redteam/health', { headers: authHGet() }).catch(() => null),
        fetch('/api/phantom/status', { headers: authHGet() }).catch(() => null),
        fetch('/api/commander/comlink/status', { headers: authHGet() }).catch(() => null),
        fetch('/api/network/info', { headers: authHGet() }).catch(() => null),
      ])
      if (cmd?.ok) setCmdHealth(await cmd.json())
      else setCmdHealth({ available: false })
      if (rt?.ok) setRtHealth(await rt.json())
      else setRtHealth({ available: false })
      if (ph?.ok) setPhantomStatus(await ph.json())
      else setPhantomStatus({ available: false })
      if (cl?.ok) setComlink(await cl.json())
      else setComlink({ available: false })
      if (ni?.ok) {
        const niData = await ni.json()
        setNetInfo(niData)
        if (niData.subnet) setTopoSubnet(niData.subnet)
      }
    } catch (e) { console.error('refresh error:', e) }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  // ── Auto-escanear topología al cargar si hay subnet ──
  const runTopology = async () => {
    if (!topoSubnet) return
    setTopoLoading(true)
    setScanResult('')
    try {
      const r = await fetch(`/api/scan/topology?subnet=${encodeURIComponent(topoSubnet)}`, {
        method: 'POST', headers: authH()
      })
      const data = await r.json()
      setTopoHosts(data.results || [])
      setScanResult(`Topología: ${data.hosts_up || 0} hosts en ${data.subnet} (${data.method || 'nmap'})`)
    } catch (e: any) {
      setScanResult(`Error: ${e.message}`)
    } finally { setTopoLoading(false) }
  }

  // ── Escaneo de red COMMANDER (nmap via commander.py) ──
  const runScan = async () => {
    if (!scanTarget) return
    setScanning(true)
    setScanResult('')
    try {
      const r = await fetch('/api/commander/scan/network', {
        method: 'POST', headers: authH(),
        body: JSON.stringify({ target: scanTarget })
      })
      const data = await r.json()
      setScanResult(JSON.stringify(data, null, 2).substring(0, 3000))
    } catch (e: any) {
      setScanResult(`Error: ${e.message}`)
    } finally { setScanning(false) }
  }

  // ── OSINT ──
  const runOSINT = async () => {
    if (!osintQuery) return
    setOsintLoading(true)
    setOsintResult('')
    try {
      const r = await fetch('/api/commander/osint', {
        method: 'POST', headers: authH(),
        body: JSON.stringify({ type: osintType, query: osintQuery })
      })
      const data = await r.json()
      setOsintResult(JSON.stringify(data, null, 2).substring(0, 3000))
    } catch (e: any) {
      setOsintResult(`Error: ${e.message}`)
    } finally { setOsintLoading(false) }
  }

  // ── COM-LINK: envío bajo demanda en el mismo entorno del dashboard ──
  const runComlinkSend = async () => {
    if (!comlinkMessage.trim()) return
    setComlinkSending(true)
    setComlinkResult('')
    setComlinkSuccess(null)
    try {
      const r = await fetch('/api/commander/comlink/send', {
        method: 'POST',
        headers: authH(),
        body: JSON.stringify({
          channel: comlinkChannel,
          destination: comlinkDestination.trim(),
          message: comlinkMessage.trim(),
        }),
      })
      const data = await r.json()
      setComlinkSuccess(r.ok && data.ok !== false && data.returncode === 0)
      setComlinkResult(JSON.stringify(data, null, 2).substring(0, 3000))
    } catch (e: any) {
      setComlinkSuccess(false)
      setComlinkResult(`Error de conexión: ${e.message}`)
    } finally { setComlinkSending(false) }
  }

  // ── WiFi Scan ──
  const runWifi = async () => {
    setWifiLoading(true)
    try {
      const r = await fetch('/api/wifi/scan', { headers: authHGet() })
      const data = await r.json()
      setWifiNets(data.networks || [])
    } catch (e: any) {
      setWifiNets([])
    } finally { setWifiLoading(false) }
  }

  // ── PHANTOM Hunt ──
  const runHunt = async () => {
    if (!huntQuery) return
    setHuntLoading(true)
    setHuntResult('')
    try {
      const r = await fetch('/api/phantom/hunt', {
        method: 'POST', headers: authH(),
        body: JSON.stringify({ query: huntQuery, playbook: huntPlaybook, max_results: 50 })
      })
      const data = await r.json()
      setHuntResult(JSON.stringify(data, null, 2).substring(0, 2000))
    } catch (e: any) {
      setHuntResult(`Error: ${e.message}`)
    } finally { setHuntLoading(false) }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Terminal size={18} className="text-green-400" />
            COMMANDER
          </h2>
          <p className="text-xs text-slate-500">Auditoría de red · OSINT · IoT · PHANTOM · COM-LINK</p>
        </div>
        <button onClick={refresh} className="p-2 hover:bg-slate-800 rounded-lg text-slate-400">
          <RefreshCw size={14} className={scanning ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* Estado de servicios */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3">
          <div className="flex items-center gap-2 mb-1">
            <Terminal size={14} className={cmdHealth?.available ? 'text-green-400' : 'text-red-400'} />
            <span className="text-[10px] text-slate-500 uppercase">COMMANDER</span>
          </div>
          <p className="text-sm font-bold text-white">{cmdHealth?.available ? 'OK' : 'No disponible'}</p>
        </div>
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3">
          <div className="flex items-center gap-2 mb-1">
            <Server size={14} className={rtHealth?.available ? 'text-green-400' : 'text-red-400'} />
            <span className="text-[10px] text-slate-500 uppercase">Red-team</span>
          </div>
          <p className="text-sm font-bold text-white">{rtHealth?.available ? 'OK' : 'Offline'}</p>
        </div>
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3">
          <div className="flex items-center gap-2 mb-1">
            <Crosshair size={14} className={phantomStatus?.available ? 'text-green-400' : 'text-amber-400'} />
            <span className="text-[10px] text-slate-500 uppercase">PHANTOM</span>
          </div>
          <p className="text-sm font-bold text-white">{phantomStatus?.available ? `${phantomStatus?.status?.active_nodes || 0} nodos` : 'Inactivo'}</p>
        </div>
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3">
          <div className="flex items-center gap-2 mb-1">
            <Radio size={14} className={comlink?.ready_count > 0 ? 'text-green-400' : 'text-amber-400'} />
            <span className="text-[10px] text-slate-500 uppercase">COM-LINK</span>
          </div>
          <p className="text-sm font-bold text-white">
            {comlink?.available ? `${comlink?.ready_count || 0}/${comlinkChannels.length || 7} listos` : 'No disponible'}
          </p>
        </div>
      </div>

      {/* COM-LINK — operación explícita, sin activación automática */}
      <div className="bg-slate-900/60 border border-cyan-900/60 rounded-xl p-4">
        <div className="flex items-start justify-between gap-3 mb-3">
          <div>
            <h3 className="text-sm font-bold text-cyan-300 mb-1 flex items-center gap-2">
              <Radio size={14} /> COM-LINK — Envío de mensaje
            </h3>
            <p className="text-[11px] text-slate-500">
              Ejecuta el canal configurado en el mismo entorno que el dashboard solo al pulsar “Enviar”.
              El dashboard debe estar iniciado en Termux para usar APIs y hardware del teléfono.
            </p>
          </div>
          <span className={`text-[10px] uppercase font-semibold ${comlink?.ready_count > 0 ? 'text-green-400' : 'text-amber-400'}`}>
            {comlink?.available ? `${comlink?.ready_count || 0} listo(s)` : 'No disponible'}
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mb-2">
          <select
            value={comlinkChannel}
            onChange={e => setComlinkChannel(e.target.value)}
            disabled={!comlink?.available || !comlinkCanSend || comlinkSending}
            className="bg-slate-950 border border-slate-800 rounded px-3 py-2 text-xs text-white"
          >
            {comlinkChannels.map((channel: any) => (
              <option key={channel.id} value={channel.id}>
                {channel.id}{channel.ready ? ' — listo' : ' — no listo'}
              </option>
            ))}
          </select>
          <input
            type="text"
            value={comlinkDestination}
            onChange={e => setComlinkDestination(e.target.value)}
            placeholder="Destino (teléfono, chat ID, SIP, host...)"
            disabled={!comlink?.available || !comlinkCanSend || comlinkSending}
            className="md:col-span-2 bg-slate-950 border border-slate-800 rounded px-3 py-2 text-xs text-white"
          />
        </div>
        <div className="flex gap-2">
          <textarea
            value={comlinkMessage}
            onChange={e => setComlinkMessage(e.target.value)}
            placeholder="Mensaje que enviará COM-LINK..."
            rows={2}
            disabled={!comlink?.available || comlinkSending}
            className="flex-1 resize-y bg-slate-950 border border-slate-800 rounded px-3 py-2 text-xs text-white"
          />
          <button
            onClick={runComlinkSend}
            disabled={!comlink?.available || !comlinkCanSend || comlinkSending || !comlinkMessage.trim()}
            className="self-stretch px-4 bg-cyan-700 hover:bg-cyan-600 disabled:opacity-50 rounded text-xs font-bold text-white flex items-center gap-1"
          >
            {comlinkSending ? <RefreshCw size={12} className="animate-spin" /> : <Radio size={12} />}
            Enviar
          </button>
        </div>
        {comlinkResult && (
          <div className={`mt-3 rounded p-2 border ${comlinkSuccess === false ? 'border-red-900/70 bg-red-950/20' : comlinkSuccess === true ? 'border-green-900/70 bg-green-950/20' : 'border-slate-800 bg-black/50'}`}>
            {comlinkSuccess !== null && (
              <div className={`text-[10px] uppercase font-bold mb-1 ${comlinkSuccess ? 'text-green-400' : 'text-red-400'}`}>
                {comlinkSuccess ? 'Envío completado' : 'Envío fallido'}
              </div>
            )}
            <pre className={`text-xs font-mono max-h-40 overflow-y-auto whitespace-pre-wrap ${comlinkSuccess === false ? 'text-red-300' : 'text-cyan-300'}`}>{comlinkResult}</pre>
          </div>
        )}
      </div>

      {/* Info de red local */}
      {netInfo && (
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3 flex items-center gap-3">
          <Radar size={16} className="text-cyan-400" />
          <div className="flex-1">
            <span className="text-xs text-slate-500">Tu red: </span>
            <span className="text-xs text-cyan-400 font-mono">{netInfo.subnet || '—'}</span>
            <span className="text-xs text-slate-600 ml-2">IP: {netInfo.local_ip || '—'}</span>
          </div>
        </div>
      )}

      {/* Descubrimiento de red — Topología */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
        <h3 className="text-sm font-bold text-cyan-400 mb-3 flex items-center gap-2">
          <Radar size={14} /> Descubrimiento de Red
        </h3>
        <div className="flex gap-2 mb-3">
          <input
            type="text" value={topoSubnet} onChange={e => setTopoSubnet(e.target.value)}
            placeholder="192.168.1.0/24"
            className="flex-1 bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-xs text-white"
          />
          <button onClick={runTopology} disabled={topoLoading}
            className="px-4 py-1.5 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 rounded text-xs font-bold text-white flex items-center gap-1">
            {topoLoading ? <RefreshCw size={12} className="animate-spin" /> : <Radar size={12} />}
            Escanear
          </button>
        </div>
        {scanResult && <div className="text-xs text-slate-400 mb-2">{scanResult}</div>}
        {topoHosts.length > 0 && (
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {topoHosts.map((h, i) => (
              <div key={i} className="flex items-center gap-2 text-xs bg-slate-950/50 rounded px-2 py-1">
                <div className={`w-1.5 h-1.5 rounded-full ${
                  h.risk === 'critical' ? 'bg-red-400' : h.risk === 'high' ? 'bg-orange-400' :
                  h.risk === 'medium' ? 'bg-yellow-400' : 'bg-green-400'
                }`} />
                <span className="font-mono text-white">{h.ip}</span>
                <span className="text-slate-500">{h.type}</span>
                {h.vendor && <span className="text-slate-600">{h.vendor}</span>}
                <span className="text-slate-600 ml-auto">
                  {Array.isArray(h.ports) ? h.ports.map((p: any) => p.port).join(', ') : ''}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* WiFi cercanas */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
        <h3 className="text-sm font-bold text-green-400 mb-3 flex items-center gap-2">
          <Wifi size={14} /> Redes WiFi Cercanas
        </h3>
        <button onClick={runWifi} disabled={wifiLoading}
          className="px-4 py-1.5 bg-green-600 hover:bg-green-500 disabled:opacity-50 rounded text-xs font-bold text-white flex items-center gap-1 mb-3">
          {wifiLoading ? <RefreshCw size={12} className="animate-spin" /> : <Wifi size={12} />}
          Escanear WiFi
        </button>
        {wifiNets.length > 0 && (
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {wifiNets.map((n, i) => (
              <div key={i} className="flex items-center gap-2 text-xs bg-slate-950/50 rounded px-2 py-1">
                <span className="text-white font-mono">{n.ssid || 'Hidden'}</span>
                <span className="text-slate-500 font-mono">{n.bssid}</span>
                <span className="text-slate-600">CH{n.channel}</span>
                <span className="text-slate-600">RSSI:{n.signal}</span>
                <span className="text-slate-600 ml-auto truncate max-w-32">{n.encryption}</span>
              </div>
            ))}
          </div>
        )}
        {wifiNets.length === 0 && !wifiLoading && (
          <p className="text-xs text-slate-600">Presiona "Escanear WiFi" (requiere termux-api)</p>
        )}
      </div>

      {/* Escaneo de red COMMANDER */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
        <h3 className="text-sm font-bold text-amber-400 mb-3 flex items-center gap-2">
          <Terminal size={14} /> Auditoría de Red (nmap)
        </h3>
        <div className="flex gap-2 mb-3">
          <input
            type="text" value={scanTarget} onChange={e => setScanTarget(e.target.value)}
            placeholder={topoSubnet || "192.168.1.0/24"}
            className="flex-1 bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-xs text-white"
          />
          <button onClick={runScan} disabled={scanning}
            className="px-4 py-1.5 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 rounded text-xs font-bold text-white flex items-center gap-1">
            {scanning ? <RefreshCw size={12} className="animate-spin" /> : <Search size={12} />}
            Auditar
          </button>
        </div>
        {scanResult && (
          <pre className="text-xs text-green-400 font-mono bg-black/50 rounded p-2 max-h-48 overflow-y-auto whitespace-pre-wrap">{scanResult}</pre>
        )}
      </div>

      {/* OSINT */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
        <h3 className="text-sm font-bold text-indigo-400 mb-3 flex items-center gap-2">
          <Globe size={14} /> OSINT
        </h3>
        <div className="flex gap-2 mb-2">
          <select value={osintType} onChange={e => setOsintType(e.target.value)}
            className="bg-slate-950 border border-slate-800 rounded px-2 py-1.5 text-xs text-white">
            <option value="ip">IP</option>
            <option value="domain">Dominio</option>
            <option value="email">Email</option>
          </select>
          <input
            type="text" value={osintQuery} onChange={e => setOsintQuery(e.target.value)}
            placeholder="8.8.8.8" className="flex-1 bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-xs text-white"
          />
          <button onClick={runOSINT} disabled={osintLoading}
            className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 rounded text-xs font-bold text-white flex items-center gap-1">
            {osintLoading ? <RefreshCw size={12} className="animate-spin" /> : <Search size={12} />}
            Analizar
          </button>
        </div>
        {osintResult && (
          <pre className="text-xs text-indigo-400 font-mono bg-black/50 rounded p-2 max-h-48 overflow-y-auto whitespace-pre-wrap">{osintResult}</pre>
        )}
      </div>

      {/* PHANTOM Hunt */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
        <h3 className="text-sm font-bold text-purple-400 mb-3 flex items-center gap-2">
          <Crosshair size={14} /> GHOST PHANTOM — Caza
        </h3>
        <div className="flex gap-2 mb-2">
          <input
            type="text" value={huntQuery} onChange={e => setHuntQuery(e.target.value)}
            placeholder={topoSubnet || "192.168.1.0/24"} className="flex-1 bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-xs text-white"
          />
          <select value={huntPlaybook} onChange={e => setHuntPlaybook(e.target.value)}
            className="bg-slate-950 border border-slate-800 rounded px-2 py-1.5 text-xs text-white">
            <option value="generic">Genérico</option>
            <option value="hikvision">Hikvision</option>
            <option value="dahua">Dahua</option>
            <option value="router">Router</option>
          </select>
          <button onClick={runHunt} disabled={huntLoading}
            className="px-4 py-1.5 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 rounded text-xs font-bold text-white flex items-center gap-1">
            {huntLoading ? <RefreshCw size={12} className="animate-spin" /> : <Crosshair size={12} />}
            Cazar
          </button>
        </div>
        {huntResult && (
          <pre className="text-xs text-purple-400 font-mono bg-black/50 rounded p-2 max-h-48 overflow-y-auto whitespace-pre-wrap">{huntResult}</pre>
        )}
      </div>
    </div>
  )
}
