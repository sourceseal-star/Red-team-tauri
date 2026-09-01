import { useCallback, useEffect, useState, type ReactNode } from 'react'
import {
  Activity, Battery, CheckCircle2, ChevronRight, Cpu, Crosshair,
  LocateFixed, MessageSquare, Radio, RefreshCw, Search, Send,
  Shield, Smartphone, Terminal, Users, Wifi, XCircle,
} from 'lucide-react'

type HubProps = {
  onNavigate?: (module: string) => void
}

type ServiceState = {
  available?: boolean
  status?: string
  ready_count?: number
  channels?: Array<{ id?: string; ready?: boolean; reason?: string } | string>
  capabilities?: string[]
  error?: string
  [key: string]: any
}

type Output = {
  ok: boolean
  title: string
  detail: string
  data?: any
}

const CHANNELS = ['sms', 'telegram', 'voip', 'mesh_wifi', 'mesh_bluetooth', 'radio', 'satellite']

function authHeaders(json = false): Record<string, string> {
  const token = localStorage.getItem('api_token')
  const headers: Record<string, string> = {}
  if (json) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`
  return headers
}

async function request(url: string, init?: RequestInit) {
  const response = await fetch(url, {
    ...init,
    headers: { ...authHeaders(Boolean(init?.body)), ...(init?.headers || {}) },
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail || data.error || `HTTP ${response.status}`)
  return data
}

function Panel({ children, className = '' }: { children: ReactNode, className?: string }) {
  return (
    <section className={`rounded-xl border border-slate-800 bg-slate-900/70 p-4 ${className}`}>
      {children}
    </section>
  )
}

function StatusDot({ online }: { online: boolean }) {
  return <span className={`h-2 w-2 shrink-0 rounded-full ${online ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,.65)]' : 'bg-slate-600'}`} />
}

function StatCard({
  label, value, icon: Icon, tone = 'text-cyan-300', online = true,
}: {
  label: string, value: string, icon: typeof Activity, tone?: string, online?: boolean
}) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-3">
      <div className="mb-2 flex items-center gap-2">
        <Icon size={14} className={tone} />
        <span className="text-[10px] uppercase tracking-wider text-slate-500">{label}</span>
        <span className="ml-auto"><StatusDot online={online} /></span>
      </div>
      <p className={`truncate text-sm font-bold ${online ? tone : 'text-slate-600'}`}>{value}</p>
    </div>
  )
}

export default function UnifiedCommandHub({ onNavigate }: HubProps) {
  const [services, setServices] = useState<Record<string, ServiceState>>({})
  const [loading, setLoading] = useState(false)
  const [notice, setNotice] = useState<Output | null>(null)
  const [running, setRunning] = useState<string | null>(null)
  const [scopeConfirmed, setScopeConfirmed] = useState(false)
  const [target, setTarget] = useState('')
  const [reconMode, setReconMode] = useState('network')
  const [reconEmail, setReconEmail] = useState('')
  const [channel, setChannel] = useState('sms')
  const [destination, setDestination] = useState('')
  const [message, setMessage] = useState('')
  const [sendConfirmed, setSendConfirmed] = useState(false)

  const loadServices = useCallback(async () => {
    setLoading(true)
    const endpoints: Array<[string, string]> = [
      ['backend', '/api/health'],
      ['commander', '/api/commander/health'],
      ['commanderStatus', '/api/commander/status'],
      ['comlink', '/api/commander/comlink/status'],
      ['android', '/api/android/status'],
      ['operations', '/api/operations/status'],
    ]
    const entries = await Promise.all(endpoints.map(async ([key, url]) => {
      try {
        return [key, await request(url)] as const
      } catch (error: any) {
        return [key, { available: false, error: error.message }] as const
      }
    }))
    setServices(Object.fromEntries(entries))
    setLoading(false)
  }, [])

  useEffect(() => { loadServices() }, [loadServices])

  const executeComlink = async (
    action: string,
    payload: Record<string, unknown> = {},
    requiresConfirmation = false,
  ) => {
    if (requiresConfirmation && !scopeConfirmed) {
      setNotice({ ok: false, title: 'Confirmación requerida', detail: 'Marca la confirmación operativa antes de modificar o procesar datos.' })
      return
    }
    setRunning(action)
    setNotice(null)
    try {
      const data = await request('/api/commander/comlink/action', {
        method: 'POST',
        body: JSON.stringify({ action, ...payload, confirm: requiresConfirmation ? true : undefined }),
      })
      setNotice({ ok: Boolean(data.ok), title: `COM-LINK · ${action}`, detail: data.ok ? 'Acción ejecutada correctamente.' : 'El adaptador devolvió un resultado no satisfactorio.', data })
      if (requiresConfirmation) await loadServices()
    } catch (error: any) {
      setNotice({ ok: false, title: `COM-LINK · ${action}`, detail: error.message || 'No se pudo ejecutar la acción.' })
    } finally {
      setRunning(null)
    }
  }

  const executeRecon = async () => {
    const cleanTarget = target.trim()
    if (!cleanTarget || !scopeConfirmed) {
      setNotice({ ok: false, title: 'Reconocimiento bloqueado', detail: 'Indica un objetivo y confirma que está dentro del alcance autorizado.' })
      return
    }
    const endpoint = reconMode === 'network'
      ? '/api/commander/scan/network'
      : reconMode === 'cameras'
        ? '/api/commander/scan/cameras'
        : '/api/commander/audit'
    setRunning(`recon-${reconMode}`)
    setNotice(null)
    try {
      const data = await request(endpoint, {
        method: 'POST',
        body: JSON.stringify({
          target: cleanTarget,
          email: reconEmail.trim(),
          authorized: true,
        }),
      })
      setNotice({
        ok: true,
        title: `COMMANDER · ${reconMode}`,
        detail: 'Solicitud aceptada y registrada. Revisa el detalle en COMMANDER.',
        data,
      })
      await loadServices()
    } catch (error: any) {
      setNotice({ ok: false, title: `COMMANDER · ${reconMode}`, detail: error.message || 'No se pudo iniciar la operación.' })
    } finally {
      setRunning(null)
    }
  }

  const sendComlink = async () => {
    if (!channel || !message.trim() || !sendConfirmed) {
      setNotice({ ok: false, title: 'Transmisión bloqueada', detail: 'Selecciona canal, escribe el mensaje y confirma la transmisión explícita.' })
      return
    }
    setRunning('send')
    setNotice(null)
    try {
      const data = await request('/api/commander/comlink/send', {
        method: 'POST',
        body: JSON.stringify({
          channel,
          destination: destination.trim(),
          message: message.trim(),
          confirm: true,
        }),
      })
      setNotice({
        ok: Boolean(data.ok),
        title: `COM-LINK · ${channel}`,
        detail: data.ok
          ? 'Solicitud entregada al adaptador; la entrega final depende del canal.'
          : 'El canal devolvió un error. Consulta la salida técnica.',
        data,
      })
    } catch (error: any) {
      setNotice({ ok: false, title: 'COM-LINK · transmisión', detail: error.message || 'No se pudo contactar el adaptador.' })
    } finally {
      setRunning(null)
    }
  }

  const commandCards = [
    { action: 'device_info', label: 'Dispositivo', description: 'Identidad y capacidades locales', icon: Smartphone },
    { action: 'battery_status', label: 'Batería', description: 'Estado energético del nodo', icon: Battery },
    { action: 'location_status', label: 'Ubicación', description: 'Consulta de ubicación bajo demanda', icon: LocateFixed },
  ]

  const serviceCards = [
    ['COMMANDER', services.commander, 'text-emerald-300', Terminal],
    ['COM-LINK', services.comlink, 'text-cyan-300', Radio],
    ['Android / Campo', services.android, 'text-amber-300', Smartphone],
    ['Operaciones', services.operations, 'text-violet-300', Shield],
  ] as const

  const channelItems = Array.isArray(services.comlink?.channels) ? services.comlink.channels : []
  const readyChannels = channelItems.filter(item => typeof item === 'string' || item.ready).length
  const comlinkOnline = Boolean(services.comlink?.available || services.comlink?.core_ready)

  return (
    <div className="space-y-4">
      <Panel className="border-cyan-900/70 bg-gradient-to-br from-cyan-950/40 via-slate-900/80 to-slate-950">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="mb-1 flex items-center gap-2">
              <div className="rounded-lg bg-cyan-500/10 p-2"><Cpu size={18} className="text-cyan-300" /></div>
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[.2em] text-cyan-400">SourceSeal Mission Control</p>
                <h2 className="text-lg font-bold text-white">Centro de Mando Unificado</h2>
              </div>
            </div>
            <p className="max-w-2xl text-xs text-slate-400">
              COM-LINK, COMMANDER y las integraciones de campo operan desde un solo lugar.
              Las acciones sensibles permanecen bajo demanda, con alcance y confirmación visibles.
            </p>
          </div>
          <button onClick={loadServices} disabled={loading}
            className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900/80 px-3 py-2 text-xs font-bold text-slate-300 hover:border-cyan-700 hover:text-white disabled:opacity-50">
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} /> Actualizar estado
          </button>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2 lg:grid-cols-4">
          {serviceCards.map(([label, service, tone, Icon]) => (
            <div key={label} className="rounded-lg border border-slate-800 bg-slate-950/70 p-3">
              <div className="mb-1 flex items-center gap-2">
                <Icon size={14} className={tone} />
                <span className="text-[10px] uppercase tracking-wider text-slate-500">{label}</span>
                <StatusDot online={label === 'COM-LINK' ? comlinkOnline : service?.available !== false && Boolean(service)} />
              </div>
              <p className={`text-xs font-bold ${label === 'COM-LINK' ? (comlinkOnline ? tone : 'text-slate-600') : service?.available !== false && service ? tone : 'text-slate-600'}`}>
                {label === 'COM-LINK' && service?.available
                  ? `${service.ready_count ?? readyChannels}/${service.channels?.length ?? CHANNELS.length} canales listos`
                  : label === 'COM-LINK' && comlinkOnline
                    ? `Núcleo online · ${service.ready_count ?? readyChannels} canales listos`
                    : service?.available !== false && service ? 'Online' : 'No disponible'}
              </p>
            </div>
          ))}
        </div>
      </Panel>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Panel className="xl:col-span-1">
          <div className="mb-3 flex items-start justify-between gap-2">
            <div>
              <h3 className="flex items-center gap-2 text-sm font-bold text-amber-300"><Terminal size={15} /> Comandos permitidos</h3>
              <p className="mt-1 text-[10px] text-slate-500">Acciones fijas del adaptador COM-LINK. No se acepta shell arbitrario.</p>
            </div>
            <span className="rounded bg-emerald-950/60 px-1.5 py-1 text-[9px] font-bold uppercase text-emerald-400">Auditado</span>
          </div>
          <div className="space-y-2">
            {commandCards.map(({ action, label, description, icon: Icon }) => (
              <button key={action} onClick={() => executeComlink(action)} disabled={Boolean(running)}
                className="flex w-full items-center gap-3 rounded-lg border border-slate-800 bg-slate-950/70 p-3 text-left hover:border-cyan-800 hover:bg-slate-900 disabled:opacity-50">
                <Icon size={16} className="text-cyan-300" />
                <span className="min-w-0 flex-1">
                  <span className="block text-xs font-bold text-slate-200">{label}</span>
                  <span className="block truncate text-[10px] text-slate-600">{description}</span>
                </span>
                {running === action ? <RefreshCw size={13} className="animate-spin text-cyan-300" /> : <ChevronRight size={13} className="text-slate-600" />}
              </button>
            ))}
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <button onClick={() => executeComlink('queue_process', {}, true)} disabled={Boolean(running)}
              className="rounded-lg bg-emerald-700/80 px-2 py-2 text-[10px] font-bold text-white hover:bg-emerald-600 disabled:opacity-50">
              {running === 'queue_process' ? 'Procesando…' : 'Procesar cola'}
            </button>
            <button onClick={() => executeComlink('queue_retry_failed', {}, true)} disabled={Boolean(running)}
              className="rounded-lg bg-amber-700/80 px-2 py-2 text-[10px] font-bold text-white hover:bg-amber-600 disabled:opacity-50">
              {running === 'queue_retry_failed' ? 'Reintentando…' : 'Reintentar fallidos'}
            </button>
          </div>
          <label className="mt-3 flex items-start gap-2 text-[10px] text-amber-300">
            <input type="checkbox" checked={scopeConfirmed} onChange={event => setScopeConfirmed(event.target.checked)} className="mt-0.5 accent-amber-500" />
            <span>Confirmo que las acciones de cola y reconocimiento corresponden a un entorno autorizado.</span>
          </label>
        </Panel>

        <Panel className="xl:col-span-1">
          <div className="mb-3 flex items-start justify-between gap-2">
            <div>
              <h3 className="flex items-center gap-2 text-sm font-bold text-emerald-300"><Crosshair size={15} /> COMMANDER · ejecución</h3>
              <p className="mt-1 text-[10px] text-slate-500">Reconocimiento autorizado, cámaras o auditoría completa.</p>
            </div>
            <Search size={15} className="text-emerald-400" />
          </div>
          <div className="space-y-2">
            <select value={reconMode} onChange={event => setReconMode(event.target.value)}
              className="w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-white">
              <option value="network">Escaneo de red</option>
              <option value="cameras">Detectar cámaras</option>
              <option value="audit">Auditoría completa</option>
            </select>
            <input value={target} onChange={event => setTarget(event.target.value)}
              placeholder="Objetivo autorizado · 192.168.1.0/24"
              className="w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-white placeholder:text-slate-600" />
            {reconMode === 'audit' && (
              <input value={reconEmail} onChange={event => setReconEmail(event.target.value)}
                placeholder="Email opcional para el informe"
                className="w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-white placeholder:text-slate-600" />
            )}
            <button onClick={executeRecon} disabled={Boolean(running)}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-700 px-3 py-2 text-xs font-bold text-white hover:bg-emerald-600 disabled:opacity-50">
              {running === `recon-${reconMode}` ? <RefreshCw size={13} className="animate-spin" /> : <Crosshair size={13} />}
              Ejecutar {reconMode === 'audit' ? 'auditoría' : reconMode === 'cameras' ? 'detección' : 'escaneo'}
            </button>
          </div>
          <div className="mt-3 rounded-lg border border-amber-900/60 bg-amber-950/20 p-2.5 text-[10px] text-amber-200">
            <strong>Control de alcance:</strong> el backend rechaza la operación sin <code className="font-mono">authorized=true</code> y esta confirmación.
          </div>
        </Panel>

        <Panel className="xl:col-span-1">
          <div className="mb-3 flex items-start justify-between gap-2">
            <div>
              <h3 className="flex items-center gap-2 text-sm font-bold text-cyan-300"><MessageSquare size={15} /> COM-LINK · transmisión</h3>
              <p className="mt-1 text-[10px] text-slate-500">Envío explícito por un canal disponible.</p>
            </div>
            <Radio size={15} className="text-cyan-400" />
          </div>
          <div className="space-y-2">
            <div className="grid grid-cols-2 gap-2">
              <select value={channel} onChange={event => setChannel(event.target.value)}
                className="rounded-lg border border-slate-800 bg-slate-950 px-2 py-2 text-xs text-white">
                {CHANNELS.map(item => <option key={item} value={item}>{item}</option>)}
              </select>
              <input value={destination} onChange={event => setDestination(event.target.value)}
                placeholder="Destino opcional"
                className="min-w-0 rounded-lg border border-slate-800 bg-slate-950 px-2 py-2 text-xs text-white placeholder:text-slate-600" />
            </div>
            <textarea value={message} onChange={event => setMessage(event.target.value)} rows={4}
              placeholder="Mensaje que se enviará al adaptador seleccionado…"
              className="w-full resize-none rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-white placeholder:text-slate-600" />
            <button onClick={sendComlink} disabled={running === 'send'}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-cyan-700 px-3 py-2 text-xs font-bold text-white hover:bg-cyan-600 disabled:opacity-50">
              {running === 'send' ? <RefreshCw size={13} className="animate-spin" /> : <Send size={13} />}
              Transmitir mensaje
            </button>
            <label className="flex items-start gap-2 text-[10px] text-cyan-200">
              <input type="checkbox" checked={sendConfirmed} onChange={event => setSendConfirmed(event.target.checked)} className="mt-0.5 accent-cyan-500" />
              <span>Confirmo la transmisión y el destino antes de enviarla.</span>
            </label>
          </div>
          <div className="mt-3 flex items-center justify-between text-[10px] text-slate-500">
            <span>{readyChannels || services.comlink?.ready_count || 0} canales listos</span>
            <button onClick={() => onNavigate?.('comlink')} className="flex items-center gap-1 text-cyan-400 hover:text-cyan-300">
              Abrir COM-LINK completo <ChevronRight size={12} />
            </button>
          </div>
        </Panel>
      </div>

      {notice && (
        <Panel className={notice.ok ? 'border-emerald-900/70' : 'border-red-900/70'}>
          <div className="flex items-start gap-3">
            {notice.ok ? <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-emerald-400" /> : <XCircle size={16} className="mt-0.5 shrink-0 text-red-400" />}
            <div className="min-w-0 flex-1">
              <p className={`text-xs font-bold ${notice.ok ? 'text-emerald-300' : 'text-red-300'}`}>{notice.title}</p>
              <p className="mt-1 text-[11px] text-slate-400">{notice.detail}</p>
              {notice.data && <pre className="mt-2 max-h-36 overflow-auto rounded bg-black/50 p-2 text-[9px] text-slate-400">{JSON.stringify(notice.data, null, 2)}</pre>}
            </div>
            <button onClick={() => setNotice(null)} className="text-[10px] text-slate-600 hover:text-slate-300">Cerrar</button>
          </div>
        </Panel>
      )}

      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2">
        <span className="mr-1 text-[10px] uppercase tracking-wider text-slate-600">Vistas operativas</span>
        {[
          ['commander', 'COMMANDER', Terminal],
          ['comlink', 'COM-LINK', Radio],
          ['android', 'Android / Campo', Smartphone],
          ['operations', 'Auditoría', Shield],
          ['integrated', 'Integración', Activity],
        ].map(([module, label, Icon]) => (
          <button key={module as string} onClick={() => onNavigate?.(module as string)}
            className="flex items-center gap-1.5 rounded-md border border-slate-800 px-2.5 py-1.5 text-[10px] font-bold text-slate-400 hover:border-cyan-800 hover:text-white">
            <Icon size={12} /> {label}
          </button>
        ))}
      </div>
    </div>
  )
}