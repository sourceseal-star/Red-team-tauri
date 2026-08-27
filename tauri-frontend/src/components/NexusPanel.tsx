import { useState, useEffect, useCallback } from 'react'
import { Cpu, Play, Square, RefreshCw, ExternalLink, Activity, AlertCircle, Zap } from 'lucide-react'

function authHGet(): Record<string, string> {
  const k = localStorage.getItem('api_token')
  return k ? { 'Authorization': `Bearer ${k}` } : {}
}

export default function NexusPanel() {
  const [health, setHealth] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  const checkHealth = useCallback(async () => {
    try {
      const r = await fetch('/api/nexus/health', { headers: authHGet() })
      setHealth(await r.json())
    } catch { setHealth({ available: false }) }
  }, [])

  useEffect(() => { checkHealth(); const i = setInterval(checkHealth, 5000); return () => clearInterval(i) }, [checkHealth])

  const startNexus = async () => {
    setLoading(true)
    try { await fetch('/api/services/start?name=nexus-omni', { method: 'POST', headers: authHGet() }) }
    catch {}
    setTimeout(() => { checkHealth(); setLoading(false) }, 3000)
  }

  const stopNexus = async () => {
    setLoading(true)
    try { await fetch('/api/services/stop?name=nexus-omni', { method: 'POST', headers: authHGet() }) }
    catch {}
    setTimeout(() => { checkHealth(); setLoading(false) }, 2000)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Cpu size={18} className="text-purple-400" /> NEXUS OMNI v9.0
          </h2>
          <p className="text-xs text-slate-500">IA predictiva · adaptativa · auto-reparable · :8002</p>
        </div>
        <div className="flex gap-2">
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
        </div>
      </div>

      {/* Estado */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3 flex items-center gap-4">
        <div className={`w-2 h-2 rounded-full ${health?.available ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`} />
        <span className="text-xs text-slate-500">Estado:</span>
        <span className={`text-xs font-bold ${health?.available ? 'text-green-400' : 'text-red-400'}`}>
          {health?.available ? 'ONLINE (:8002)' : 'OFFLINE'}
        </span>
        {health?.available && (
          <a href="http://localhost:8002" target="_blank" rel="noopener"
            className="ml-auto text-xs text-purple-400 hover:text-purple-300 flex items-center gap-1">
            <ExternalLink size={12} /> Abrir en pestaña nueva
          </a>
        )}
      </div>

      {/* NEXUS UI embebida */}
      {health?.available ? (
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden">
          <div className="px-3 py-2 border-b border-slate-800 flex items-center gap-2">
            <Activity size={14} className="text-purple-400" />
            <span className="text-xs text-slate-400">NEXUS OMNI — Motor cognitivo activo</span>
            <Zap size={12} className="text-amber-400 ml-auto" />
          </div>
          <iframe src="http://localhost:8002" className="w-full" style={{ height: '600px', border: 'none' }}
            title="NEXUS OMNI" />
        </div>
      ) : (
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-8 flex flex-col items-center">
          <AlertCircle size={32} className="text-slate-600 mb-3" />
          <p className="text-sm text-slate-500">NEXUS OMNI no está corriendo.</p>
          <p className="text-xs text-slate-600 mt-1">Presiona "Iniciar" para arrancar el motor en :8002.</p>
          <p className="text-xs text-slate-700 mt-2">Necesita aiohttp: pip install aiohttp</p>
        </div>
      )}

      {/* Info módulos */}
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
  )
}
