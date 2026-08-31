import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertCircle, CheckCircle2, Radio, RefreshCw, Send, ShieldCheck } from 'lucide-react'

type Channel = {
  id: string
  ready?: boolean
  reason?: string
  requires?: string[]
}

function headers(json = false): Record<string, string> {
  const token = localStorage.getItem('api_token')
  const result: Record<string, string> = {}
  if (json) result['Content-Type'] = 'application/json'
  if (token) result.Authorization = `Bearer ${token}`
  return result
}

function Card({ children, className = '' }: { children: React.ReactNode, className?: string }) {
  return <section className={`bg-slate-900/60 border border-slate-800 rounded-xl p-4 ${className}`}>{children}</section>
}

export default function ComlinkPanel() {
  const [status, setStatus] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [channel, setChannel] = useState('sms')
  const [destination, setDestination] = useState('')
  const [message, setMessage] = useState('')
  const [sending, setSending] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [emergencyContact, setEmergencyContact] = useState('')
  const [emergencyMessage, setEmergencyMessage] = useState('')
  const [includeLocation, setIncludeLocation] = useState(true)
  const [emergencyLoading, setEmergencyLoading] = useState(false)
  const [notice, setNotice] = useState<{ type: 'ok' | 'error', text: string } | null>(null)

  const channels: Channel[] = Array.isArray(status?.channels) ? status.channels : []
  const readyChannels = useMemo(() => channels.filter(item => item.ready), [channels])
  const selected = channels.find(item => item.id === channel)
  const canSend = Boolean(status?.available && selected?.ready)

  const loadStatus = useCallback(async () => {
    setLoading(true)
    try {
      const response = await fetch('/api/commander/comlink/status', { headers: headers() })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`)
      setStatus(data)
      if (data.ready_channels?.length && !data.ready_channels.includes(channel)) {
        setChannel(data.ready_channels[0])
      }
      setNotice(null)
    } catch (error: any) {
      setStatus({ available: false, channels: [] })
      setNotice({ type: 'error', text: error.message || 'COM-LINK no disponible' })
    } finally {
      setLoading(false)
    }
  }, [channel])

  useEffect(() => { loadStatus() }, [loadStatus])

  const sendMessage = async () => {
    if (!message.trim() || !canSend) return
    setSending(true); setResult(null); setNotice(null)
    try {
      const response = await fetch('/api/commander/comlink/send', {
        method: 'POST',
        headers: headers(true),
        body: JSON.stringify({ channel, destination: destination.trim(), message: message.trim() }),
      })
      const data = await response.json().catch(() => ({}))
      setResult(data)
      setNotice({
        type: response.ok && data.ok ? 'ok' : 'error',
        text: response.ok && data.ok
          ? 'Solicitud entregada al adaptador; la entrega final no se confirma desde aquí.'
          : data.error || 'El adaptador no pudo enviar el mensaje.',
      })
    } catch (error: any) {
      setNotice({ type: 'error', text: error.message || 'Error de conexión' })
    } finally {
      setSending(false)
    }
  }

  const previewEmergency = async () => {
    if (!emergencyContact.trim() || !emergencyMessage.trim()) return
    setEmergencyLoading(true); setResult(null); setNotice(null)
    try {
      const response = await fetch('/api/commander/comlink/emergency', {
        method: 'POST',
        headers: headers(true),
        body: JSON.stringify({
          contact: emergencyContact.trim(),
          message: emergencyMessage.trim(),
          dry_run: true,
          confirm: false,
          include_location: includeLocation,
        }),
      })
      const data = await response.json().catch(() => ({}))
      setResult(data)
      setNotice({
        type: response.ok && data.ok ? 'ok' : 'error',
        text: response.ok && data.ok ? 'Previsualización generada; no se transmitió ningún mensaje.' : data.error || 'No se pudo generar la previsualización.',
      })
    } catch (error: any) {
      setNotice({ type: 'error', text: error.message || 'Error de conexión' })
    } finally {
      setEmergencyLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Radio size={18} className="text-cyan-300" /> COM-LINK
          </h2>
          <p className="text-xs text-slate-500">Comunicación multicanal explícita · estado real · sin activación automática</p>
        </div>
        <button onClick={loadStatus} disabled={loading} className="p-2 hover:bg-slate-800 rounded-lg text-slate-400" title="Actualizar estado">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {notice && (
        <div className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-xs ${
          notice.type === 'ok' ? 'bg-green-950/40 border-green-800 text-green-400' : 'bg-red-950/40 border-red-800 text-red-400'
        }`}>
          {notice.type === 'ok' ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
          {notice.text}
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          ['Núcleo', status?.core_ready ? 'Listo' : 'No disponible', status?.core_ready ? 'text-green-400' : 'text-red-400'],
          ['Canales', `${readyChannels.length}/${channels.length || 7}`, readyChannels.length ? 'text-cyan-300' : 'text-amber-400'],
          ['Versión', status?.version || '—', 'text-slate-300'],
          ['Dispositivo', status?.device?.name || '—', 'text-slate-300'],
        ].map(([label, value, color]) => (
          <div key={label} className="bg-slate-900/60 border border-slate-800 rounded-xl p-3">
            <span className="text-[10px] uppercase text-slate-500">{label}</span>
            <p className={`text-sm font-bold truncate ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      <Card>
        <div className="flex items-start justify-between gap-3 mb-3">
          <div>
            <h3 className="text-sm font-bold text-cyan-300 flex items-center gap-2"><Send size={14} /> Enviar por canal</h3>
            <p className="text-[11px] text-slate-500 mt-1">Solo se ejecuta al pulsar Enviar. COM-LINK informa preparación, no entrega confirmada.</p>
          </div>
          <span className={`text-[10px] uppercase font-bold ${canSend ? 'text-green-400' : 'text-amber-400'}`}>
            {canSend ? 'Canal listo' : 'Selecciona un canal listo'}
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mb-2">
          <select value={channel} onChange={event => setChannel(event.target.value)} disabled={!channels.length || sending}
            className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white">
            {channels.map(item => <option key={item.id} value={item.id}>{item.id}{item.ready ? ' — listo' : ' — no listo'}</option>)}
            {!channels.length && <option value="sms">sms — sin estado</option>}
          </select>
          <input value={destination} onChange={event => setDestination(event.target.value)}
            placeholder="Destino opcional" disabled={!canSend || sending}
            className="md:col-span-2 bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white placeholder:text-slate-600" />
        </div>
        <div className="flex flex-col sm:flex-row gap-2">
          <textarea value={message} onChange={event => setMessage(event.target.value)} rows={3}
            placeholder="Mensaje que enviará el canal seleccionado..." disabled={!canSend || sending}
            className="flex-1 resize-y bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white placeholder:text-slate-600" />
          <button onClick={sendMessage} disabled={!canSend || sending || !message.trim()}
            className="sm:self-stretch px-4 py-2 bg-cyan-700 hover:bg-cyan-600 disabled:opacity-50 rounded-lg text-xs font-bold text-white flex items-center justify-center gap-1.5">
            {sending ? <RefreshCw size={12} className="animate-spin" /> : <Send size={12} />} Enviar
          </button>
        </div>
      </Card>

      <Card className="border-amber-900/60">
        <div className="flex items-start gap-2 mb-3">
          <ShieldCheck size={16} className="text-amber-400 mt-0.5" />
          <div>
            <h3 className="text-sm font-bold text-amber-300">Previsualización de emergencia</h3>
            <p className="text-[11px] text-slate-500 mt-1">Siempre inicia en modo simulación. La vista previa no transmite ni envía comandos remotos.</p>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          <input value={emergencyContact} onChange={event => setEmergencyContact(event.target.value)}
            placeholder="Contacto configurado" className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white placeholder:text-slate-600" />
          <input value={emergencyMessage} onChange={event => setEmergencyMessage(event.target.value)}
            placeholder="Mensaje de emergencia" className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white placeholder:text-slate-600" />
        </div>
        <div className="flex flex-wrap items-center gap-3 mt-3">
          <label className="flex items-center gap-2 text-[11px] text-slate-400">
            <input type="checkbox" checked={includeLocation} onChange={event => setIncludeLocation(event.target.checked)} className="accent-amber-500" />
            Incluir ubicación si está disponible
          </label>
          <button onClick={previewEmergency} disabled={emergencyLoading || !emergencyContact.trim() || !emergencyMessage.trim()}
            className="px-3 py-2 bg-amber-700 hover:bg-amber-600 disabled:opacity-50 rounded-lg text-xs font-bold text-white flex items-center gap-1.5">
            {emergencyLoading ? <RefreshCw size={12} className="animate-spin" /> : <ShieldCheck size={12} />} Previsualizar
          </button>
        </div>
      </Card>

      {channels.length > 0 && (
        <Card>
          <h3 className="text-sm font-bold text-slate-200 mb-3">Estado por canal</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {channels.map(item => (
              <div key={item.id} className="bg-slate-950/70 border border-slate-800 rounded-lg p-3">
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full ${item.ready ? 'bg-green-400' : 'bg-slate-600'}`} />
                  <span className="text-xs font-bold text-slate-200">{item.id}</span>
                  <span className={`ml-auto text-[10px] uppercase ${item.ready ? 'text-green-400' : 'text-slate-600'}`}>{item.ready ? 'listo' : 'no listo'}</span>
                </div>
                <p className="text-[10px] text-slate-500 mt-1">{item.ready ? 'Requisitos locales presentes.' : item.reason || 'Requisitos pendientes.'}</p>
                {item.requires?.length ? <p className="text-[9px] text-slate-600 mt-1">Requiere: {item.requires.join(' · ')}</p> : null}
              </div>
            ))}
          </div>
        </Card>
      )}

      {result && <pre className="bg-black/50 border border-slate-800 rounded-lg p-3 text-[10px] text-cyan-300 font-mono max-h-56 overflow-y-auto whitespace-pre-wrap">{JSON.stringify(result, null, 2)}</pre>}
    </div>
  )
}