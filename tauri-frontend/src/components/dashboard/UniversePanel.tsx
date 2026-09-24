import { useCallback, useEffect, useState } from 'react'
    import { Activity, AlertTriangle, CheckCircle2, Network, Play, RefreshCw, ShieldCheck, Wifi } from 'lucide-react'

    type UniversePayload = { module?: string; state?: Record<string, unknown>; network_context?: Record<string, unknown> }
    const ACTIONS = [
    { id: 'topology_scan', label: 'Topología', icon: Network },
    { id: 'mesh_sync', label: 'Mesh sync', icon: Wifi },
    { id: 'purge_sockets', label: 'Purge sockets', icon: Activity },
    ] as const

    export default function UniversePanel() {
    const [status, setStatus] = useState<UniversePayload | null>(null)
    const [subnet, setSubnet] = useState('')
    const [loading, setLoading] = useState(true)
    const [running, setRunning] = useState<string | null>(null)
    const [message, setMessage] = useState('')
    const [error, setError] = useState('')
    const loadStatus = useCallback(async () => {
      setLoading(true); setError('')
      try {
        const response = await fetch('/api/universe/status', { cache: 'no-store' })
        if (!response.ok) throw new Error('HTTP ' + response.status)
        setStatus(await response.json())
      } catch (err) { setError(err instanceof Error ? err.message : 'No se pudo consultar Universe') }
      finally { setLoading(false) }
    }, [])
    useEffect(() => { void loadStatus() }, [loadStatus])
    const runAction = async (action: string) => {
      setRunning(action); setMessage(''); setError('')
      try {
        const response = await fetch('/api/universe/sync', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action, target_subnet: subnet.trim() }) })
        const body = await response.json()
        if (!response.ok) throw new Error(body.detail || 'HTTP ' + response.status)
        setMessage('✓ ' + body.action + ' programado · ' + (body.subnet || 'interfaces LAN autodetectadas'))
        await loadStatus()
      } catch (err) { setError(err instanceof Error ? err.message : 'No se pudo programar la sincronización') }
      finally { setRunning(null) }
    }
    const state = status?.state || {}
    const network = status?.network_context || {}
    return (
      <div className="min-h-full bg-slate-950 text-slate-100 p-4 md:p-6 space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><div className="flex items-center gap-2 text-fuchsia-300 text-xs uppercase tracking-[0.22em]"><ShieldCheck className="w-4 h-4" /> Universe · universe.py</div><h1 className="text-2xl font-semibold mt-1">Estado y sincronización protegida</h1><p className="text-slate-400 text-sm mt-1">Solo bajo demanda. No hay barridos automáticos.</p></div><button type="button" onClick={() => void loadStatus()} disabled={loading} className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-fuchsia-700/50 bg-fuchsia-950/30 text-fuchsia-200 text-sm hover:bg-fuchsia-900/40 disabled:opacity-50"><RefreshCw className={loading ? 'w-4 h-4 animate-spin' : 'w-4 h-4'} /> Actualizar estado</button></div>
        {error && <div className="rounded-lg border border-red-800/60 bg-red-950/30 p-3 text-red-200 text-sm flex gap-2"><AlertTriangle className="w-4 h-4 shrink-0" />{error}</div>}
        {message && <div className="rounded-lg border border-emerald-800/60 bg-emerald-950/30 p-3 text-emerald-200 text-sm flex gap-2"><CheckCircle2 className="w-4 h-4 shrink-0" />{message}</div>}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">{[['Estado', String(state.status || 'sin datos')], ['Modo', String(state.mode || 'protegido')], ['Nodos', String(state.nodes_tracked ?? '—')]].map(([label, value]) => <div key={label} className="rounded-xl border border-slate-800 bg-slate-900/70 p-4"><div className="text-[10px] uppercase tracking-widest text-slate-500">{label}</div><div className="text-lg mt-1">{value}</div></div>)}</div>
        <section className="rounded-xl border border-slate-800 bg-slate-900/70 p-4 space-y-4"><div className="flex items-center justify-between gap-2"><h2 className="font-medium">Sincronizaciones allowlisted</h2><span className="text-xs text-slate-500">POST /api/universe/sync</span></div><div className="flex flex-col md:flex-row gap-2"><input value={subnet} onChange={e => setSubnet(e.target.value)} placeholder="Subred opcional, ej. 192.168.1.0/24" className="flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none focus:border-fuchsia-500" /><span className="text-xs text-slate-500 self-center">Vacío = autodetección</span></div><div className="grid grid-cols-1 sm:grid-cols-3 gap-2">{ACTIONS.map(({ id, label, icon: Icon }) => <button key={id} type="button" onClick={() => void runAction(id)} disabled={running !== null} className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 hover:border-fuchsia-500 hover:text-fuchsia-200 disabled:opacity-50"><Icon className="w-4 h-4" />{running === id ? 'Programando…' : label}<Play className="w-3 h-3" /></button>)}</div></section>
        <section className="rounded-xl border border-slate-800 bg-slate-900/70 p-4"><h2 className="font-medium mb-3">Contexto del dispositivo</h2><div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm"><div><span className="text-slate-500">Host:</span> {String(network.hostname || '—')}</div><div><span className="text-slate-500">IP local:</span> {String(network.local_ip || '—')}</div><div><span className="text-slate-500">Stack:</span> {String(network.stack || '—')}</div><div><span className="text-slate-500">Privilegios:</span> {String(network.privilege || '—')}</div></div><p className="text-xs text-slate-500 mt-4">Última sincronización: {String(state.last_synchronization || 'todavía no')}</p></section>
      </div>
    )
    }
    