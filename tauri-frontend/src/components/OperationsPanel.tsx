import { useCallback, useEffect, useState } from 'react'
import { Activity, CheckCircle2, GitBranch, RefreshCw, ShieldCheck, XCircle } from 'lucide-react'

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('api_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function value(value: unknown, fallback = '—') {
  return value === undefined || value === null || value === '' ? fallback : String(value)
}

export default function OperationsPanel() {
  const [status, setStatus] = useState<any>(null)
  const [audit, setAudit] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [statusResponse, auditResponse] = await Promise.all([
        fetch('/api/operations/status', { headers: authHeaders() }),
        fetch('/api/operations/audit?limit=20', { headers: authHeaders() }),
      ])
      const statusData = await statusResponse.json().catch(() => ({}))
      const auditData = await auditResponse.json().catch(() => ({}))
      if (!statusResponse.ok) throw new Error(statusData.detail || statusData.error || `HTTP ${statusResponse.status}`)
      setStatus(statusData)
      setAudit(auditResponse.ok ? auditData : { events: [] })
      setError(null)
    } catch (e: any) {
      setError(e.message || 'No se pudo cargar el monitor')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const capabilities = status?.capabilities || {}
  const repos = Object.values(status?.repos || {}) as any[]
  const system = status?.system || {}

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2"><Activity size={18} className="text-emerald-400" /> Operaciones seguras</h2>
          <p className="text-xs text-slate-500">Métricas locales · Git de solo lectura · ledger de auditoría SHA-256</p>
        </div>
        <button onClick={load} disabled={loading} className="p-2 hover:bg-slate-800 rounded-lg text-slate-400" title="Actualizar">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {error && <div className="bg-red-950/40 border border-red-800 rounded-lg p-3 text-xs text-red-300">{error}</div>}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          ['Monitor', status?.status || '—', status?.status === 'operational' ? 'text-green-400' : 'text-amber-400'],
          ['CPU', system.available ? `${value(system.cpu_percent, '0')}%` : '—', 'text-cyan-300'],
          ['RAM', system.available ? `${value(system.memory_percent, '0')}%` : '—', 'text-purple-300'],
          ['Eventos', value(status?.audit?.total_events, '0'), 'text-amber-300'],
        ].map(([label, text, color]) => (
          <div key={label} className="bg-slate-900/60 border border-slate-800 rounded-xl p-3">
            <span className="text-[10px] uppercase text-slate-500">{label}</span>
            <p className={`text-sm font-bold truncate ${color}`}>{text}</p>
          </div>
        ))}
      </div>

      <section className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
        <h3 className="text-sm font-bold text-emerald-300 flex items-center gap-2 mb-3"><ShieldCheck size={14} /> Capacidades y límites</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {Object.entries(capabilities).map(([name, enabled]) => (
            <div key={name} className="flex items-center gap-2 bg-slate-950/70 rounded-lg px-3 py-2 text-xs">
              {enabled ? <CheckCircle2 size={13} className="text-green-400" /> : <XCircle size={13} className="text-slate-600" />}
              <span className={enabled ? 'text-slate-200' : 'text-slate-500'}>{name.replace(/_/g, ' ')}</span>
              <span className={`ml-auto text-[10px] uppercase ${enabled ? 'text-green-400' : 'text-slate-600'}`}>{enabled ? 'activo' : 'desactivado'}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
        <h3 className="text-sm font-bold text-cyan-300 flex items-center gap-2 mb-3"><GitBranch size={14} /> Repositorios observados</h3>
        <div className="space-y-2">
          {repos.length ? repos.map(repo => (
            <div key={repo.name} className="bg-slate-950/70 border border-slate-800 rounded-lg p-3">
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${repo.available && repo.clean ? 'bg-green-400' : 'bg-amber-400'}`} />
                <span className="text-xs font-bold text-slate-200">{repo.name}</span>
                <span className="text-[10px] text-slate-500">{value(repo.branch, 'detached')}</span>
                <span className="ml-auto text-[10px] font-mono text-cyan-300">{value(repo.head)}</span>
              </div>
              <p className="text-[10px] text-slate-500 mt-1">{repo.clean ? 'Sin cambios locales' : `${value(repo.change_count, '0')} cambio(s) local(es)`}</p>
            </div>
          )) : <p className="text-xs text-slate-600">No hay repositorios disponibles para observar.</p>}
        </div>
      </section>

      <section className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-bold text-slate-200">Auditoría local reciente</h3>
          <span className="text-[10px] text-slate-500">Integridad: {value(audit?.summary?.integrity, '—')}</span>
        </div>
        <div className="space-y-1.5 max-h-64 overflow-y-auto">
          {(audit?.events || []).length ? audit.events.slice().reverse().map((event: any, index: number) => (
            <div key={`${event.timestamp}-${index}`} className="bg-slate-950/70 rounded-lg px-3 py-2">
              <div className="flex items-center gap-2 text-[10px]">
                <span className="text-emerald-300 font-bold">{event.event_type}</span>
                <span className="text-slate-600">{event.actor}</span>
                <span className="ml-auto text-slate-600">{value(event.timestamp)}</span>
              </div>
              <p className="text-[9px] text-slate-600 font-mono truncate mt-1">hash: {value(event.chain_hash)}</p>
            </div>
          )) : <p className="text-xs text-slate-600">No hay eventos registrados todavía.</p>}
        </div>
      </section>
    </div>
  )
}