import { useState, useEffect, useCallback } from 'react'
import { Cpu, Play, Square, RefreshCw, ExternalLink, Activity, AlertCircle, Zap,
         MapPin, Navigation, Download, Satellite, ShieldAlert, Radio, Radar, Link2 } from 'lucide-react'

function authHGet(): Record<string, string> {
  const k = localStorage.getItem('api_token')
  return k ? { 'Authorization': `Bearer ${k}` } : {}
}

const TYPE_ICON: Record<string, string> = {
  router: '📡', camera: '📷', dvr: '🎥', desktop: '🖥️',
  phone: '📱', iot: '🔌', unknown: '❓',
}

export default function NexusPanel() {
  const [tab, setTab] = useState<'mapa' | 'motor'>('mapa')
  const [health, setHealth] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [map, setMap] = useState<any>(null)
  const [gpsLoading, setGpsLoading] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [gpsMsg, setGpsMsg] = useState('')
  const [netguardLog, setNetguardLog] = useState('')
  const [netguardMsg, setNetguardMsg] = useState<any>(null)
  const [manualGps, setManualGps] = useState('')
  const nexusPort = health?.port || 8004

  const checkHealth = useCallback(async () => {
    try {
      const r = await fetch('/api/nexus/health', { headers: authHGet() })
      setHealth(await r.json())
    } catch { setHealth({ available: false }) }
  }, [])

  const loadMap = useCallback(async () => {
    try {
      const r = await fetch('/api/nexus/map', { headers: authHGet() })
      if (r.ok) setMap(await r.json())
    } catch { /* el mapa se recarga en el próximo ciclo */ }
  }, [])

  useEffect(() => {
    checkHealth(); loadMap()
    const i = setInterval(checkHealth, 5000)
    const j = setInterval(loadMap, 15000)
    return () => { clearInterval(i); clearInterval(j) }
  }, [checkHealth, loadMap])

  const startNexus = async () => {
    setLoading(true)
    try { await fetch('/api/services/start?name=nexus-omni', { method: 'POST', headers: authHGet() }) } catch {}
    setTimeout(() => { checkHealth(); setLoading(false) }, 3000)
  }

  const stopNexus = async () => {
    setLoading(true)
    try { await fetch('/api/services/stop?name=nexus-omni', { method: 'POST', headers: authHGet() }) } catch {}
    setTimeout(() => { checkHealth(); setLoading(false) }, 2000)
  }

  const updateGps = async () => {
    setGpsLoading(true); setGpsMsg('')
    try {
      const r = await fetch('/api/nexus/map/gps', { method: 'POST', headers: authHGet(), body: '{}' })
      const d = await r.json()
      if (d.ok) setGpsMsg(`📍 GPS vía ${d.source}`)
      else setGpsMsg('⚠️ ' + (d.hint || 'sin GPS'))
      await loadMap()
    } catch { setGpsMsg('⚠️ error consultando GPS') }
    setGpsLoading(false)
  }

  const sendManualGps = async () => {
    // acepta "lat, lon" (copiado de GPS Test u OsmAnd)
    const m = manualGps.match(/(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)/)
    if (!m) { setGpsMsg('⚠️ formato: 4.7110, -74.0721'); return }
    setGpsLoading(true)
    try {
      const r = await fetch('/api/nexus/map/gps', {
        method: 'POST', headers: { ...authHGet(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ lat: parseFloat(m[1]), lon: parseFloat(m[2]), note: 'GPS Test (manual)' }),
      })
      const d = await r.json()
      if (d.ok) { setGpsMsg('📍 Coordenadas manuales guardadas'); setManualGps('') }
      await loadMap()
    } catch { setGpsMsg('⚠️ error') }
    setGpsLoading(false)
  }

  const scanNetwork = async () => {
    setScanning(true)
    try {
      await fetch('/api/scan/topology', { method: 'POST', headers: { ...authHGet(), 'Content-Type': 'application/json' }, body: '{}' })
      await loadMap()
    } catch { /* el mapa muestra el último escaneo igual */ }
    setScanning(false)
  }

  const openLinks = async (ip: string) => {
    try {
      const r = await fetch(`/api/nexus/map/links?ip=${encodeURIComponent(ip)}`, { headers: authHGet() })
      if (r.ok) {
        const d = await r.json()
        if (d.osmand) window.open(d.osmand, '_blank')
      }
    } catch { /* OsmAnd no instalado → el enlace no abre */ }
  }

  const parseNetguard = async () => {
    if (!netguardLog.trim()) return
    setNetguardMsg('Procesando…')
    try {
      const r = await fetch('/api/nexus/map/netguard', {
        method: 'POST', headers: { ...authHGet(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ log: netguardLog }),
      })
      setNetguardMsg(await r.json())
    } catch { setNetguardMsg({ error: 'sin respuesta' }) }
  }

  const gps = map?.gps
  const devices = map?.devices || []

  return (
    <div className="space-y-4 min-w-0">
      {/* encabezado */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="min-w-0">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Navigation size={18} className="text-purple-400" /> NEXUS 10.0
          </h2>
          <p className="text-xs text-slate-500">Mapa de IA · topología real + GPS + OsmAnd · motor OMNI :{nexusPort}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setTab('mapa')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1 ${tab === 'mapa' ? 'bg-purple-600 text-white' : 'bg-slate-800 text-slate-300'}`}>
            <MapPin size={12} /> MAPA IA
          </button>
          <button onClick={() => setTab('motor')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1 ${tab === 'motor' ? 'bg-purple-600 text-white' : 'bg-slate-800 text-slate-300'}`}>
            <Cpu size={12} /> Motor OMNI
          </button>
        </div>
      </div>

      {tab === 'mapa' ? (
        <div className="space-y-3 min-w-0">
          {/* estado GPS */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3">
            <div className="flex items-center gap-3 flex-wrap">
              <Satellite size={16} className={gps ? 'text-green-400' : 'text-slate-600'} />
              {gps ? (
                <>
                  <span className="text-xs font-mono text-green-300">
                    {gps.lat.toFixed(5)}, {gps.lon.toFixed(5)}
                  </span>
                  <span className="text-[10px] text-slate-500">
                    {gps.source}{gps.satellites ? ` · ${gps.satellites} sat` : ''}
                    {gps.accuracy ? ` · ±${Math.round(gps.accuracy)}m` : ''}
                  </span>
                </>
              ) : (
                <span className="text-xs text-slate-500">Sin GPS — actívalo o pega coordenadas de GPS Test</span>
              )}
              <div className="ml-auto flex gap-2 flex-wrap">
                <button onClick={updateGps} disabled={gpsLoading}
                  className="px-3 py-1.5 bg-green-600 hover:bg-green-500 disabled:opacity-50 rounded-lg text-xs font-bold text-white flex items-center gap-1">
                  {gpsLoading ? <RefreshCw size={12} className="animate-spin" /> : <Satellite size={12} />} GPS
                </button>
                <button onClick={scanNetwork} disabled={scanning}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 rounded-lg text-xs font-bold text-slate-200 flex items-center gap-1">
                  {scanning ? <RefreshCw size={12} className="animate-spin" /> : <Radar size={12} />} Escanear red
                </button>
              </div>
            </div>
            {/* entrada manual GPS Test */}
            <div className="flex gap-2 mt-2 flex-wrap">
              <input value={manualGps} onChange={(e) => setManualGps(e.target.value)}
                placeholder="4.7110, -74.0721  (GPS Test)"
                className="flex-1 min-w-[180px] bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-xs text-slate-200" />
              <button onClick={sendManualGps} disabled={gpsLoading}
                className="px-3 py-1 bg-slate-800 hover:bg-slate-700 rounded-lg text-xs text-slate-300">Guardar manual</button>
            </div>
            {gpsMsg && <p className="text-[11px] text-slate-400 mt-1">{gpsMsg}</p>}
          </div>

          {/* exportes OsmAnd */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3 flex items-center gap-3 flex-wrap">
            <Download size={14} className="text-amber-400" />
            <span className="text-xs text-slate-400">Llevar el mapa a OsmAnd:</span>
            <a href="/api/nexus/map/gpx" className="px-2.5 py-1 bg-amber-600 hover:bg-amber-500 rounded-lg text-[11px] font-bold text-white">GPX</a>
            <a href="/api/nexus/map/kml" className="px-2.5 py-1 bg-amber-700 hover:bg-amber-600 rounded-lg text-[11px] font-bold text-white">KML</a>
            {gps && (
              <a href={`https://osmand.net/go?lat=${gps.lat}&lon=${gps.lon}&z=19`} target="_blank" rel="noopener"
                className="px-2.5 py-1 bg-green-700 hover:bg-green-600 rounded-lg text-[11px] font-bold text-white flex items-center gap-1">
                <Link2 size={11} /> Abrir mi posición
              </a>
            )}
          </div>

          {/* dispositivos */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3">
            <div className="flex items-center gap-2 mb-2">
              <Radio size={14} className="text-purple-400" />
              <span className="text-xs font-bold text-slate-300">
                {devices.length} dispositivos en el mapa
              </span>
              {map?.topology?.saved_at && (
                <span className="text-[10px] text-slate-600 ml-auto">
                  último escaneo: {new Date(map.topology.saved_at).toLocaleString()}
                </span>
              )}
            </div>
            {devices.length === 0 ? (
              <div className="flex flex-col items-center py-6">
                <AlertCircle size={28} className="text-slate-600 mb-2" />
                <p className="text-xs text-slate-500">Sin escaneo todavía — pulsa "Escanear red".</p>
              </div>
            ) : (
              <div className="space-y-1.5">
                {devices.map((d: any) => (
                  <div key={d.ip} className="flex items-center gap-2 bg-slate-950/60 border border-slate-800/60 rounded-lg px-2.5 py-1.5 flex-wrap">
                    <span className="text-sm">{TYPE_ICON[d.type] || '❓'}</span>
                    <span className="text-xs font-mono text-slate-200">{d.ip}</span>
                    <span className="text-xs text-slate-400">{d.hostname || d.vendor || ''}</span>
                    <span className="text-[10px] px-1.5 py-0.5 bg-slate-800 rounded text-slate-400">{d.type}</span>
                    {d.risk === 'high' && <span className="text-[10px] px-1.5 py-0.5 bg-red-900/60 rounded text-red-300">riesgo alto</span>}
                    {(d.sources || []).map((s: string) => (
                      <span key={s} className="text-[9px] px-1 py-0.5 bg-purple-950/60 rounded text-purple-300">{s}</span>
                    ))}
                    {gps && (
                      <button onClick={() => openLinks(d.ip)}
                        className="ml-auto text-[10px] text-amber-400 hover:text-amber-300 flex items-center gap-1">
                        <MapPin size={10} /> OsmAnd
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* NetGuard */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3">
            <div className="flex items-center gap-2 mb-2">
              <ShieldAlert size={14} className="text-red-400" />
              <span className="text-xs font-bold text-slate-300">NetGuard — pegar log exportado</span>
            </div>
            <textarea value={netguardLog} onChange={(e) => setNetguardLog(e.target.value)}
              placeholder="NetGuard → tres puntos → Export log… pega aquí"
              className="w-full h-20 bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5 text-[11px] font-mono text-slate-300" />
            <button onClick={parseNetguard}
              className="mt-2 px-3 py-1.5 bg-red-900 hover:bg-red-800 rounded-lg text-xs font-bold text-red-100">
              Analizar tráfico
            </button>
            {netguardMsg?.summary && (
              <div className="mt-2 text-[11px] text-slate-400 space-y-1">
                <p>IPs: {netguardMsg.summary.unique_ips} · permitidos: {netguardMsg.summary.total_allowed} · bloqueados: {netguardMsg.summary.total_blocked}</p>
                {netguardMsg.summary.ips.slice(0, 5).map(([ip, c]: any) => (
                  <p key={ip} className="font-mono">
                    <span className="text-slate-300">{ip}</span>
                    {c.blocked > 0 && <span className="text-red-400"> · {c.blocked} bloqueos</span>}
                    {c.allowed > 0 && <span className="text-green-500"> · {c.allowed} permitidos</span>}
                  </p>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="space-y-4 min-w-0">
          {/* ── pestaña Motor OMNI (v9 intacto) ── */}
          <div className="flex gap-2 flex-wrap">
            {health?.available ? (
              <button onClick={stopNexus} disabled={loading}
                className="px-3 py-1.5 bg-red-600 hover:bg-red-500 disabled:opacity-50 rounded-lg text-xs font-bold text-white flex items-center gap-1">
                <Square size={12} /> Detener
              </button>
            ) : (
              <button onClick={startNexus} disabled={loading}
                className="px-3 py-1.5 bg-green-600 hover:bg-green-500 disabled:opacity-50 rounded-lg text-xs font-bold text-white flex items-center gap-1">
                {loading ? <RefreshCw size={12} className="animate-spin" /> : <Play size={12} />} Iniciar
              </button>
            )}
            <button onClick={checkHealth}
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-xs text-slate-300 flex items-center gap-1">
              <RefreshCw size={12} /> Estado
            </button>
            {health?.available && (
              <a href="/api/nexus/ui" target="_blank" rel="noopener"
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-xs text-purple-300 flex items-center gap-1">
                <ExternalLink size={12} /> Abrir UI
              </a>
            )}
          </div>

          {health?.available ? (
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden">
              <div className="px-3 py-2 border-b border-slate-800 flex items-center gap-2">
                <Activity size={14} className="text-purple-400" />
                <span className="text-xs text-slate-400">NEXUS OMNI v9 — Motor cognitivo activo</span>
                <Zap size={12} className="text-amber-400 ml-auto" />
              </div>
              <iframe src="/api/nexus/ui" className="w-full" style={{ height: '600px', border: 'none' }}
                title="NEXUS OMNI" />
            </div>
          ) : (
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-8 flex flex-col items-center">
              <AlertCircle size={32} className="text-slate-600 mb-3" />
              <p className="text-sm text-slate-500">NEXUS OMNI no está corriendo.</p>
              <p className="text-xs text-slate-600 mt-1">Presiona "Iniciar" para arrancar el motor en :{nexusPort}.</p>
            </div>
          )}

          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {[
              { label: 'Predictivo', icon: Zap, color: 'text-amber-400', desc: 'Predice amenazas por cambios históricos' },
              { label: 'Adaptativo', icon: Activity, color: 'text-cyan-400', desc: 'Modos passive/stealth/active/frenzy' },
              { label: 'Auto-Reparable', icon: RefreshCw, color: 'text-green-400', desc: 'Watchdog evita cuelgues' },
              { label: 'Vectores', icon: Cpu, color: 'text-purple-400', desc: 'Visualiza vectores de ataque' },
            ].map((m, i) => {
              const Icon = m.icon
              return (
                <div key={i} className="bg-slate-900/60 border border-slate-800 rounded-lg p-3">
                  <Icon size={14} className={m.color} />
                  <p className="text-xs font-bold text-white mt-1">{m.label}</p>
                  <p className="text-[10px] text-slate-600 mt-0.5">{m.desc}</p>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
