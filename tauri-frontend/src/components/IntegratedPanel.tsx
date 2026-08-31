import { useCallback, useEffect, useState } from 'react'
import { Activity, Cpu, Radio, RefreshCw, Shield, Smartphone } from 'lucide-react'

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('api_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function stateLabel(item: any, fallback = 'No disponible') {
  if (!item) return fallback
  if (item.available === false) return 'No disponible'
  if (item.status === 'ok' || item.status === 'healthy' || item.status === 'operational' || item.available === true) return 'Online'
  return item.status || 'Disponible'
}

export default function IntegratedPanel() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const endpoints = [
        ['/api/integrated/health', 'integrated'],
        ['/api/commander/health', 'commander'],
        ['/api/commander/comlink/status', 'comlink'],
        ['/api/android/status', 'android'],
        ['/api/phantom/status', 'phantom'],
      ] as const
      const responses = await Promise.all(endpoints.map(async ([url, key]) => {
        const response = await fetch(url, { headers: authHeaders() }).catch(() => null)
        return [key, response?.ok ? await response.json() : { available: false }] as const
      }))
      setData(Object.fromEntries(responses))
      setError(null)
    } catch (e: any) {
      setError(e.message || 'No se pudo consultar la integración')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const integrated = data?.integrated
  const cards = [
    { label: 'ARTO AI', value: integrated?.arto, icon: Cpu, color: 'text-orange-300' },
    { label: 'SEAL Pack', value: integrated?.seal, icon: Shield, color: 'text-cyan-300' },
    { label: 'LEVIATHAN', value: integrated?.leviathan, icon: Shield, color: 'text-violet-300' },
    { label: 'COMMANDER', value: data?.commander, icon: Activity, color: 'text-green-300' },
    { label: 'COM-LINK', value: data?.comlink, icon: Radio, color: 'text-cyan-300' },
    { label: 'Android / Campo', value: data?.android, icon: Smartphone, color: 'text-amber-300' },
  ]

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2"><Activity size={18} className="text-violet-300" /> Integración del sistema</h2>
          <p className="text-xs text-slate-500">Vista única del estado de los módulos nuevos y sus adaptadores locales</p>
        </div>
        <button onClick={load} disabled={loading} className="p-2 hover:bg-slate-800 rounded-lg text-slate-400" title="Actualizar">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {error && <div className="bg-red-950/40 border border-red-800 rounded-lg p-3 text-xs text-red-300">{error}</div>}

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {cards.map(({ label, value, icon: Icon, color }) => {
          const labelValue = label === 'COM-LINK' && value?.available
            ? `${value.ready_count || 0}/${value.channels?.length || 7} listos`
            : stateLabel(value)
          const online = value?.available !== false && Boolean(value)
          return (
            <div key={label} className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <Icon size={15} className={color} />
                <span className="text-[10px] uppercase text-slate-500">{label}</span>
                <span className={`ml-auto w-1.5 h-1.5 rounded-full ${online ? 'bg-green-400' : 'bg-slate-600'}`} />
              </div>
              <p className={`text-sm font-bold ${online ? color : 'text-slate-600'}`}>{labelValue}</p>
            </div>
          )
        })}
      </div>

      <section className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
        <h3 className="text-sm font-bold text-violet-300 mb-3">Resumen de integración</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
          <div className="bg-slate-950/70 rounded-lg p-3"><span className="text-slate-500">Estado global</span><p className="text-green-400 font-bold mt-1">{integrated?.status || 'Sin respuesta'}</p></div>
          <div className="bg-slate-950/70 rounded-lg p-3"><span className="text-slate-500">Última consulta</span><p className="text-slate-300 font-mono mt-1">{integrated?.timestamp || '—'}</p></div>
        </div>
        <p className="text-[11px] text-slate-500 mt-3">Esta vista consulta salud y capacidades. Las operaciones de escaneo, campo y comunicación permanecen bajo demanda en sus módulos respectivos.</p>
      </section>
    </div>
  )
}