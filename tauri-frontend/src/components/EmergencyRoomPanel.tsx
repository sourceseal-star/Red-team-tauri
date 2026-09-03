import { useCallback, useEffect, useState } from 'react'
import {
  AlertTriangle, Battery, CheckCircle2, Clock, Crosshair, MapPin,
  Radio, RefreshCw, Send, Siren, Smartphone, Wifi, Zap
} from 'lucide-react'

type Channel = {
  id: string
  ready?: boolean
  reason?: string
  requires?: string[]
}

type EmergencyReport = {
  timestamp?: string
  message_hash?: string
  ready_channels?: string[]
  results?: Array<{ contact?: string; channel: string; ok?: boolean; error?: string }>
}

type QuickStatus = {
  ready_count: number
  ready_channels: string[]
  channels: Record<string, Channel>
  environment: string
  queue_stats?: Record<string, number>
  last_emergency?: EmergencyReport | null
}

function headers(json = false): Record<string, string> {
  const token = localStorage.getItem('api_token')
  const result: Record<string, string> = {}
  if (json) result['Content-Type'] = 'application/json'
  if (token) result.Authorization = `Bearer ${token}`
  return result
}

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <section className={`bg-slate-900/60 border border-slate-800 rounded-xl p-4 ${className}`}>{children}</section>
}

const CHANNEL_ICONS: Record<string, typeof Radio> = {
  sms: Smartphone,
  telegram: Send,
  voip: Radio,
  mesh_wifi: Wifi,
  mesh_bluetooth: Radio,
  radio: Radio,
  satellite: Radio,
}

const CHANNEL_LABELS: Record<string, string> = {
  sms: 'SMS',
  telegram: 'Telegram',
  voip: 'VoIP',
  mesh_wifi: 'Mesh WiFi',
  mesh_bluetooth: 'Mesh BT',
  radio: 'Radio',
  satellite: 'Satélite',
}

export default function EmergencyRoomPanel() {
  const [status, setStatus] = useState<QuickStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [sosMessage, setSosMessage] = useState('')
  const [sosSending, setSosSending] = useState(false)
  const [sosConfirmed, setSosConfirmed] = useState(false)
  const [sosResult, setSosResult] = useState<any>(null)
  const [lastEmergency, setLastEmergency] = useState<EmergencyReport | null>(null)
  const [contacts, setContacts] = useState<Record<string, any>>({})
  const [quickSendChannel, setQuickSendChannel] = useState('sms')
  const [quickSendDest, setQuickSendDest] = useState('')
  const [quickSendMsg, setQuickSendMsg] = useState('')
  const [quickSending, setQuickSending] = useState(false)
  const [quickResult, setQuickResult] = useState<any>(null)

  const fetchStatus = useCallback(async () => {
    setLoading(true)
    try {
      const [statusRes, contactsRes, dataRes] = await Promise.all([
        fetch('/api/commander/comlink/status', { headers: headers() }),
        fetch('/api/commander/comlink/contacts', { headers: headers() }),
        fetch('/api/commander/comlink/data', { headers: headers() }),
      ])
      if (statusRes.ok) {
        const s = await statusRes.json()
        setStatus(s)
      }
      if (contactsRes.ok) {
        const c = await contactsRes.json()
        setContacts(c.contacts || {})
      }
      if (dataRes.ok) {
        const d = await dataRes.json()
        setLastEmergency(d.last_emergency || null)
      }
    } catch {
      // offline
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStatus()
    const id = setInterval(fetchStatus, 15000)
    return () => clearInterval(id)
  }, [fetchStatus])

  const sendSOS = async () => {
    if (!sosConfirmed) return
    if (!sosMessage.trim()) return
    setSosSending(true)
    setSosResult(null)
    try {
      const trustedContacts = Object.entries(contacts).filter(([, c]: any) => c.trusted !== false)
      const contactId = trustedContacts[0]?.[0] || ''
      if (!contactId) {
        setSosResult({ error: 'No hay contactos de confianza configurados' })
        setSosSending(false)
        return
      }
      const res = await fetch('/api/commander/comlink/emergency', {
        method: 'POST',
        headers: headers(true),
        body: JSON.stringify({
          contact: contactId,
          message: sosMessage,
          confirm: true,
          include_location: true,
        }),
      })
      const data = await res.json()
      setSosResult(data)
      if (data.ok) {
        setSosMessage('')
        setSosConfirmed(false)
        fetchStatus()
      }
    } catch (e: any) {
      setSosResult({ error: e.message })
    } finally {
      setSosSending(false)
    }
  }

  const quickSend = async () => {
    if (!quickSendDest.trim() || !quickSendMsg.trim()) return
    setQuickSending(true)
    setQuickResult(null)
    try {
      const res = await fetch('/api/commander/comlink/send', {
        method: 'POST',
        headers: headers(true),
        body: JSON.stringify({
          channel: quickSendChannel,
          destination: quickSendDest,
          message: quickSendMsg,
          confirm: true,
        }),
      })
      const data = await res.json()
      setQuickResult(data)
      if (data.ok) {
        setQuickSendMsg('')
      }
    } catch (e: any) {
      setQuickResult({ error: e.message })
    } finally {
      setQuickSending(false)
    }
  }

  const readyCount = status?.ready_count || 0
  const channels = status?.channels || {}
  const trustedContacts = Object.entries(contacts).filter(([, c]: any) => c.trusted !== false)

  return (
    <div className="space-y-4 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-red-500/10 border border-red-500/30">
            <Siren className="w-6 h-6 text-red-400" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">Emergency Room</h2>
            <p className="text-xs text-slate-400">Centro de emergencia multicanal — operación crítica</p>
          </div>
        </div>
        <button
          onClick={fetchStatus}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Actualizar
        </button>
      </div>

      {/* Status overview */}
      <Card className={`border ${readyCount > 0 ? 'border-green-500/30' : 'border-red-500/30'}`}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${readyCount > 0 ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
            <span className="text-sm font-semibold text-slate-200">
              {readyCount > 0 ? `${readyCount}/7 canales listos` : 'Sin canales disponibles'}
            </span>
          </div>
          <span className="text-xs text-slate-500">
            Entorno: {status?.environment || '?'}
          </span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
          {Object.entries(channels).map(([id, ch]) => {
            const Icon = CHANNEL_ICONS[id] || Radio
            const label = CHANNEL_LABELS[id] || id
            return (
              <div
                key={id}
                className={`flex flex-col items-center gap-1 p-2 rounded-lg border ${
                  ch.ready
                    ? 'border-green-500/30 bg-green-500/5'
                    : 'border-slate-700/50 bg-slate-800/30'
                }`}
                title={ch.reason}
              >
                <Icon className={`w-4 h-4 ${ch.ready ? 'text-green-400' : 'text-slate-500'}`} />
                <span className={`text-[10px] ${ch.ready ? 'text-green-300' : 'text-slate-500'}`}>
                  {label}
                </span>
                <span className={`text-[9px] ${ch.ready ? 'text-green-400' : 'text-slate-600'}`}>
                  {ch.ready ? '●' : '○'}
                </span>
              </div>
            )
          })}
        </div>
      </Card>

      {/* SOS Broadcast */}
      <Card className="border-red-500/20">
        <div className="flex items-center gap-2 mb-3">
          <AlertTriangle className="w-5 h-5 text-red-400" />
          <h3 className="text-sm font-semibold text-red-300">SOS — Broadcast de Emergencia</h3>
        </div>
        <p className="text-xs text-slate-400 mb-3">
          Envía un mensaje a todos los contactos de confianza usando todos los canales disponibles.
          Incluye tu ubicación GPS automáticamente.
        </p>
        <div className="space-y-3">
          <input
            type="text"
            value={sosMessage}
            onChange={(e) => setSosMessage(e.target.value)}
            placeholder="Mensaje de emergencia (ej: 'Necesito ayuda urgente')"
            className="w-full px-3 py-2 text-sm rounded-lg bg-slate-800 border border-slate-700 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-red-500/50"
          />
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-xs text-slate-400 cursor-pointer">
              <input
                type="checkbox"
                checked={sosConfirmed}
                onChange={(e) => setSosConfirmed(e.target.checked)}
                className="rounded"
              />
              Confirmo transmisión real
            </label>
            <button
              onClick={sendSOS}
              disabled={!sosConfirmed || !sosMessage.trim() || sosSending || trustedContacts.length === 0}
              className="flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg bg-red-600 hover:bg-red-500 text-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            >
              {sosSending ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Siren className="w-4 h-4" />
              )}
              {sosSending ? 'Enviando...' : 'ENVIAR SOS'}
            </button>
          </div>
          {trustedContacts.length === 0 && (
            <p className="text-xs text-amber-400">
              ⚠ No hay contactos de confianza. Configúralos en COM-LINK.
            </p>
          )}
          {sosResult && (
            <div className={`text-xs p-3 rounded-lg ${sosResult.ok ? 'bg-green-500/10 text-green-300' : 'bg-red-500/10 text-red-300'}`}>
              {sosResult.ok ? (
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4" />
                  SOS enviado — {sosResult.results?.length || 0} intentos
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4" />
                  {sosResult.error || 'Error en SOS'}
                </div>
              )}
            </div>
          )}
        </div>
      </Card>

      {/* Quick send */}
      <Card>
        <div className="flex items-center gap-2 mb-3">
          <Send className="w-5 h-5 text-cyan-400" />
          <h3 className="text-sm font-semibold text-slate-200">Envío Rápido por Canal</h3>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <select
            value={quickSendChannel}
            onChange={(e) => setQuickSendChannel(e.target.value)}
            className="px-3 py-2 text-sm rounded-lg bg-slate-800 border border-slate-700 text-slate-200 focus:outline-none focus:border-cyan-500/50"
          >
            <option value="sms">SMS</option>
            <option value="telegram">Telegram</option>
            <option value="voip">VoIP (Llamada)</option>
            <option value="mesh_wifi">Mesh WiFi</option>
          </select>
          <input
            type="text"
            value={quickSendDest}
            onChange={(e) => setQuickSendDest(e.target.value)}
            placeholder={quickSendChannel === 'sms' ? '+573001234567' : quickSendChannel === 'telegram' ? 'chat_id' : '192.168.1.10'}
            className="px-3 py-2 text-sm rounded-lg bg-slate-800 border border-slate-700 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
          />
          <input
            type="text"
            value={quickSendMsg}
            onChange={(e) => setQuickSendMsg(e.target.value)}
            placeholder="Mensaje"
            className="px-3 py-2 text-sm rounded-lg bg-slate-800 border border-slate-700 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
          />
        </div>
        <div className="flex justify-end mt-3">
          <button
            onClick={quickSend}
            disabled={!quickSendDest.trim() || !quickSendMsg.trim() || quickSending}
            className="flex items-center gap-2 px-4 py-2 text-sm rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white transition-colors disabled:opacity-30"
          >
            {quickSending ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            Enviar
          </button>
        </div>
        {quickResult && (
          <div className={`text-xs p-3 mt-3 rounded-lg ${quickResult.ok ? 'bg-green-500/10 text-green-300' : 'bg-red-500/10 text-red-300'}`}>
            {quickResult.ok ? '✓ Enviado correctamente' : quickResult.error || 'Error'}
          </div>
        )}
      </Card>

      {/* Last emergency + Queue */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Last emergency */}
        <Card>
          <div className="flex items-center gap-2 mb-3">
            <Clock className="w-5 h-5 text-amber-400" />
            <h3 className="text-sm font-semibold text-slate-200">Última Emergencia</h3>
          </div>
          {lastEmergency ? (
            <div className="space-y-2 text-xs">
              <div className="text-slate-400">
                <span className="text-slate-500">Tiempo:</span> {lastEmergency.timestamp || 'N/A'}
              </div>
              <div className="text-slate-400">
                <span className="text-slate-500">Canales usados:</span> {lastEmergency.ready_channels?.join(', ') || 'N/A'}
              </div>
              <div className="text-slate-400">
                <span className="text-slate-500">Hash mensaje:</span>{' '}
                <code className="text-slate-300 text-[10px]">{lastEmergency.message_hash?.slice(0, 16)}...</code>
              </div>
              {lastEmergency.results && lastEmergency.results.length > 0 && (
                <div className="space-y-1">
                  {lastEmergency.results.map((r, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <span className={r.ok ? 'text-green-400' : 'text-red-400'}>
                        {r.ok ? '✓' : '✗'}
                      </span>
                      <span className="text-slate-400">
                        {r.channel} {r.contact ? `→ ${r.contact}` : ''}
                      </span>
                      {r.error && <span className="text-red-400 text-[10px]">{r.error}</span>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <p className="text-xs text-slate-500">Sin emergencias registradas</p>
          )}
        </Card>

        {/* Queue stats */}
        <Card>
          <div className="flex items-center gap-2 mb-3">
            <Zap className="w-5 h-5 text-yellow-400" />
            <h3 className="text-sm font-semibold text-slate-200">Cola de Mensajes</h3>
          </div>
          <div className="grid grid-cols-4 gap-3">
            {(['pending', 'processing', 'sent', 'failed'] as const).map((state) => {
              const count = status?.queue_stats?.[state] || 0
              const colors: Record<string, string> = {
                pending: 'text-yellow-400',
                processing: 'text-blue-400',
                sent: 'text-green-400',
                failed: 'text-red-400',
              }
              return (
                <div key={state} className="text-center">
                  <div className={`text-2xl font-bold ${colors[state]}`}>{count}</div>
                  <div className="text-[10px] text-slate-500 capitalize">{state}</div>
                </div>
              )
            })}
          </div>
          {status?.queue_stats?.pending > 0 && (
            <p className="text-xs text-amber-400 mt-2">
              ⚠ Hay mensajes pendientes en la cola — se enviarán cuando los canales estén disponibles
            </p>
          )}
        </Card>
      </div>

      {/* Trusted contacts quick view */}
      <Card>
        <div className="flex items-center gap-2 mb-3">
          <Crosshair className="w-5 h-5 text-cyan-400" />
          <h3 className="text-sm font-semibold text-slate-200">Contactos de Confianza</h3>
        </div>
        {trustedContacts.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {trustedContacts.map(([id, c]: any) => (
              <div key={id} className="flex items-center gap-2 p-2 rounded-lg bg-slate-800/50 border border-slate-700/50">
                <CheckCircle2 className="w-4 h-4 text-green-400 shrink-0" />
                <div className="min-w-0">
                  <div className="text-xs text-slate-200 truncate">{c.name}</div>
                  <div className="text-[10px] text-slate-500 truncate">
                    {c.phone || c.telegram_chat_id || c.mesh_wifi_ip || 'sin destino'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-500">
            No hay contactos de confianza. Configúralos en COM-LINK → Contactos.
          </p>
        )}
      </Card>
    </div>
  )
}
