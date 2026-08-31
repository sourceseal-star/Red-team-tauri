import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertCircle, CheckCircle2, Edit3, FileCog, Radio, RefreshCw, Send, ShieldCheck, Trash2, Wrench } from 'lucide-react'

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
  const [emergencyConfirmed, setEmergencyConfirmed] = useState(false)
  const [sendConfirmed, setSendConfirmed] = useState(false)
  const [notice, setNotice] = useState<{ type: 'ok' | 'error', text: string } | null>(null)
  const [data, setData] = useState<any>(null)
  const [configForm, setConfigForm] = useState({
    deviceName: '', deviceId: '', retryAttempts: 3, retryDelay: 5,
    fallbackOrder: '', encryption: true, autoDelete: false, autoDeleteDays: 30,
  })
  const [configSaving, setConfigSaving] = useState(false)
  const [contactForm, setContactForm] = useState({
    id: '', name: '', phone: '', telegram_chat_id: '', sip_address: '',
    mesh_wifi_ip: '', mesh_bluetooth_mac: '', priority: 5, trusted: true,
  })
  const [editingContact, setEditingContact] = useState<string | null>(null)
  const [contactSaving, setContactSaving] = useState(false)
  const [dataLoading, setDataLoading] = useState(false)
  const [dataConfirm, setDataConfirm] = useState(false)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [actionResult, setActionResult] = useState<any>(null)
  const [queueChannel, setQueueChannel] = useState('')
  const [cleanDays, setCleanDays] = useState(30)

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

  const loadData = useCallback(async () => {
    setDataLoading(true)
    try {
      const response = await fetch('/api/commander/comlink/data', { headers: headers() })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`)
      setData(payload)
      const config = payload.config || {}
      setConfigForm({
        deviceName: config.device?.name || '',
        deviceId: config.device?.id || '',
        retryAttempts: Number(config.network?.retry_attempts ?? 3),
        retryDelay: Number(config.network?.retry_delay ?? 5),
        fallbackOrder: Array.isArray(config.network?.fallback_order) ? config.network.fallback_order.join(', ') : '',
        encryption: config.security?.encryption !== false,
        autoDelete: config.security?.auto_delete === true,
        autoDeleteDays: Number(config.security?.auto_delete_days ?? 30),
      })
    } catch (error: any) {
      setNotice({ type: 'error', text: error.message || 'No se pudieron cargar los datos de COM-LINK' })
    } finally {
      setDataLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const sendMessage = async () => {
    if (!message.trim() || !canSend || !sendConfirmed) return
    setSending(true); setResult(null); setNotice(null)
    try {
      const response = await fetch('/api/commander/comlink/send', {
        method: 'POST',
        headers: headers(true),
        body: JSON.stringify({
          channel,
          destination: destination.trim(),
          message: message.trim(),
          confirm: sendConfirmed,
        }),
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

  const transmitEmergency = async () => {
    if (!emergencyContact.trim() || !emergencyMessage.trim() || !emergencyConfirmed) return
    setEmergencyLoading(true); setResult(null); setNotice(null)
    try {
      const response = await fetch('/api/commander/comlink/emergency', {
        method: 'POST',
        headers: headers(true),
        body: JSON.stringify({
          contact: emergencyContact.trim(),
          message: emergencyMessage.trim(),
          dry_run: false,
          confirm: emergencyConfirmed,
          include_location: includeLocation,
        }),
      })
      const payload = await response.json().catch(() => ({}))
      setResult(payload)
      setNotice({
        type: response.ok && payload.ok ? 'ok' : 'error',
        text: response.ok && payload.ok ? 'Alerta transmitida al adaptador y registrada.' : payload.error || 'La alerta no pudo transmitirse.',
      })
      await loadData()
    } catch (error: any) {
      setNotice({ type: 'error', text: error.message || 'Error de conexión' })
    } finally {
      setEmergencyLoading(false)
    }
  }

  const saveConfig = async () => {
    setConfigSaving(true); setNotice(null)
    try {
      const response = await fetch('/api/commander/comlink/config', {
        method: 'PUT',
        headers: headers(true),
        body: JSON.stringify({
          config: {
            device: { name: configForm.deviceName.trim(), id: configForm.deviceId.trim() },
            network: {
              retry_attempts: Number(configForm.retryAttempts),
              retry_delay: Number(configForm.retryDelay),
              fallback_order: configForm.fallbackOrder.split(',').map(item => item.trim()).filter(Boolean),
            },
            security: {
              encryption: configForm.encryption,
              auto_delete: configForm.autoDelete,
              auto_delete_days: Number(configForm.autoDeleteDays),
            },
          },
        }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(payload.error || payload.details?.join(', ') || `HTTP ${response.status}`)
      setData((current: any) => ({ ...current, config: payload.config }))
      setNotice({ type: 'ok', text: 'Configuración de COM-LINK actualizada.' })
    } catch (error: any) {
      setNotice({ type: 'error', text: error.message || 'No se pudo guardar la configuración' })
    } finally {
      setConfigSaving(false)
    }
  }

  const resetContactForm = () => {
    setEditingContact(null)
    setContactForm({
      id: '', name: '', phone: '', telegram_chat_id: '', sip_address: '',
      mesh_wifi_ip: '', mesh_bluetooth_mac: '', priority: 5, trusted: true,
    })
  }

  const editContact = (id: string, contact: any) => {
    setEditingContact(id)
    setContactForm({
      id,
      name: contact.name || '',
      phone: contact.phone || '',
      telegram_chat_id: contact.telegram_chat_id || '',
      sip_address: contact.sip_address || '',
      mesh_wifi_ip: contact.mesh_wifi_ip || '',
      mesh_bluetooth_mac: contact.mesh_bluetooth_mac || '',
      priority: Number(contact.priority ?? 5),
      trusted: contact.trusted !== false,
    })
  }

  const saveContact = async () => {
    if (!dataConfirm || !contactForm.name.trim() || (!editingContact && !contactForm.id.trim())) return
    setContactSaving(true); setNotice(null)
    try {
      const path = editingContact
        ? `/api/commander/comlink/contacts/${encodeURIComponent(editingContact)}`
        : '/api/commander/comlink/contacts'
      const response = await fetch(path, {
        method: editingContact ? 'PUT' : 'POST',
        headers: headers(true),
        body: JSON.stringify({ ...contactForm, id: contactForm.id.trim(), confirm: true }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`)
      await loadData()
      resetContactForm()
      setDataConfirm(false)
      setNotice({ type: 'ok', text: editingContact ? 'Contacto actualizado.' : 'Contacto creado.' })
    } catch (error: any) {
      setNotice({ type: 'error', text: error.message || 'No se pudo guardar el contacto' })
    } finally {
      setContactSaving(false)
    }
  }

  const deleteContact = async (id: string) => {
    if (!dataConfirm) return
    try {
      const response = await fetch(`/api/commander/comlink/contacts/${encodeURIComponent(id)}`, {
        method: 'DELETE', headers: headers(true), body: JSON.stringify({ confirm: true }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`)
      await loadData()
      if (editingContact === id) resetContactForm()
      setDataConfirm(false)
      setNotice({ type: 'ok', text: 'Contacto eliminado.' })
    } catch (error: any) {
      setNotice({ type: 'error', text: error.message || 'No se pudo eliminar el contacto' })
    }
  }

  const runAction = async (action: string, extra: Record<string, any> = {}, confirm = false) => {
    if (confirm && !dataConfirm) return
    setActionLoading(action); setActionResult(null); setNotice(null)
    try {
      const response = await fetch('/api/commander/comlink/action', {
        method: 'POST',
        headers: headers(true),
        body: JSON.stringify({ action, ...extra, ...(confirm ? { confirm: true } : {}) }),
      })
      const payload = await response.json().catch(() => ({}))
      setActionResult(payload)
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`)
      if (payload.data) setData(payload.data)
      setNotice({ type: 'ok', text: `Acción ejecutada: ${action}.` })
      if (!payload.data) await loadData()
      setDataConfirm(false)
    } catch (error: any) {
      setNotice({ type: 'error', text: error.message || 'La acción no pudo ejecutarse' })
    } finally {
      setActionLoading(null)
    }
  }

  const contacts = data?.contacts && typeof data.contacts === 'object' ? data.contacts : {}
  const queue = Array.isArray(data?.queue) ? data.queue : []
  const queueStats = data?.queue_stats || {}

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
          <div className="flex flex-col gap-2 sm:w-36">
            <label className="flex items-start gap-1.5 text-[10px] text-amber-300">
              <input type="checkbox" checked={sendConfirmed} onChange={event => setSendConfirmed(event.target.checked)} className="mt-0.5 accent-amber-500" />
              Confirmo que deseo transmitir este mensaje
            </label>
            <button onClick={sendMessage} disabled={!canSend || sending || !message.trim() || !sendConfirmed}
              className="flex-1 px-4 py-2 bg-cyan-700 hover:bg-cyan-600 disabled:opacity-50 rounded-lg text-xs font-bold text-white flex items-center justify-center gap-1.5">
              {sending ? <RefreshCw size={12} className="animate-spin" /> : <Send size={12} />} Enviar
            </button>
          </div>
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
          <label className="flex items-center gap-2 text-[10px] text-red-300">
            <input type="checkbox" checked={emergencyConfirmed} onChange={event => setEmergencyConfirmed(event.target.checked)} className="accent-red-500" />
            Confirmo transmitir la alerta
          </label>
          <button onClick={transmitEmergency} disabled={emergencyLoading || !emergencyContact.trim() || !emergencyMessage.trim() || !emergencyConfirmed}
            className="px-3 py-2 bg-red-700 hover:bg-red-600 disabled:opacity-50 rounded-lg text-xs font-bold text-white flex items-center gap-1.5">
            {emergencyLoading ? <RefreshCw size={12} className="animate-spin" /> : <ShieldCheck size={12} />} Transmitir
          </button>
        </div>
      </Card>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Card>
          <div className="flex items-start justify-between gap-3 mb-3">
            <div>
              <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2"><FileCog size={14} className="text-cyan-300" /> Configuración operativa</h3>
              <p className="text-[11px] text-slate-500 mt-1">Modifica datos no sensibles del dispositivo, fallback y seguridad.</p>
            </div>
            <button onClick={loadData} disabled={dataLoading} className="text-[10px] text-cyan-400 hover:text-cyan-300">
              {dataLoading ? 'Cargando…' : 'Recargar datos'}
            </button>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-[10px] text-slate-500">Nombre del dispositivo
              <input value={configForm.deviceName} onChange={event => setConfigForm(current => ({ ...current, deviceName: event.target.value }))}
                className="mt-1 w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-2 text-xs text-white" />
            </label>
            <label className="text-[10px] text-slate-500">ID del dispositivo
              <input value={configForm.deviceId} onChange={event => setConfigForm(current => ({ ...current, deviceId: event.target.value }))}
                className="mt-1 w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-2 text-xs text-white" />
            </label>
            <label className="text-[10px] text-slate-500">Reintentos
              <input type="number" min={1} max={10} value={configForm.retryAttempts} onChange={event => setConfigForm(current => ({ ...current, retryAttempts: Number(event.target.value) }))}
                className="mt-1 w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-2 text-xs text-white" />
            </label>
            <label className="text-[10px] text-slate-500">Espera entre reintentos (s)
              <input type="number" min={0} max={3600} value={configForm.retryDelay} onChange={event => setConfigForm(current => ({ ...current, retryDelay: Number(event.target.value) }))}
                className="mt-1 w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-2 text-xs text-white" />
            </label>
          </div>
          <label className="block text-[10px] text-slate-500 mt-2">Orden de fallback (separado por comas)
            <input value={configForm.fallbackOrder} onChange={event => setConfigForm(current => ({ ...current, fallbackOrder: event.target.value }))}
              placeholder="sms, telegram, mesh_wifi"
              className="mt-1 w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-2 text-xs text-white" />
          </label>
          <div className="flex flex-wrap gap-4 mt-3">
            <label className="flex items-center gap-2 text-[10px] text-slate-400"><input type="checkbox" checked={configForm.encryption} onChange={event => setConfigForm(current => ({ ...current, encryption: event.target.checked }))} className="accent-cyan-500" /> Cifrado activo</label>
            <label className="flex items-center gap-2 text-[10px] text-slate-400"><input type="checkbox" checked={configForm.autoDelete} onChange={event => setConfigForm(current => ({ ...current, autoDelete: event.target.checked }))} className="accent-cyan-500" /> Auto-eliminar</label>
            <label className="flex items-center gap-2 text-[10px] text-slate-400">Días <input type="number" min={1} max={3650} value={configForm.autoDeleteDays} onChange={event => setConfigForm(current => ({ ...current, autoDeleteDays: Number(event.target.value) }))} className="w-16 bg-slate-950 border border-slate-800 rounded px-2 py-1 text-xs text-white" /></label>
          </div>
          <button onClick={saveConfig} disabled={configSaving}
            className="mt-3 px-3 py-2 bg-cyan-700 hover:bg-cyan-600 disabled:opacity-50 rounded-lg text-xs font-bold text-white">
            {configSaving ? 'Guardando…' : 'Guardar configuración'}
          </button>
        </Card>

        <Card>
          <h3 className="text-sm font-bold text-amber-300 flex items-center gap-2 mb-1"><Wrench size={14} /> Funciones del dispositivo y cola</h3>
          <p className="text-[11px] text-slate-500 mb-3">Ejecuta funciones COM-LINK existentes sin abrir el menú interactivo.</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {[
              ['device_info', 'Dispositivo'],
              ['battery_status', 'Batería'],
              ['location_status', 'Ubicación'],
            ].map(([action, label]) => (
              <button key={action} onClick={() => runAction(action)} disabled={actionLoading === action}
                className="px-2 py-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 rounded-lg text-[10px] font-bold text-slate-200">
                {actionLoading === action ? 'Ejecutando…' : label}
              </button>
            ))}
          </div>
          <div className="border-t border-slate-800 mt-3 pt-3">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-center mb-3">
              {['pending', 'processing', 'sent', 'failed'].map(statusName => (
                <div key={statusName} className="bg-slate-950/70 rounded p-2">
                  <div className="text-[9px] uppercase text-slate-600">{statusName}</div>
                  <div className="text-sm font-bold text-white">{queueStats[statusName] ?? 0}</div>
                </div>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              <select value={queueChannel} onChange={event => setQueueChannel(event.target.value)}
                className="bg-slate-950 border border-slate-800 rounded px-2 py-2 text-[10px] text-white">
                <option value="">Toda la cola</option>
                {channels.map(item => <option key={item.id} value={item.id}>{item.id}</option>)}
              </select>
              <button onClick={() => runAction('queue_process', { channel: queueChannel }, true)} disabled={!!actionLoading || !dataConfirm}
                className="px-2 py-2 bg-green-700 hover:bg-green-600 disabled:opacity-50 rounded text-[10px] font-bold text-white">Procesar cola</button>
              <button onClick={() => runAction('queue_retry_failed', {}, true)} disabled={!!actionLoading || !dataConfirm}
                className="px-2 py-2 bg-amber-700 hover:bg-amber-600 disabled:opacity-50 rounded text-[10px] font-bold text-white">Reintentar fallidos</button>
              <input type="number" min={0} max={3650} value={cleanDays} onChange={event => setCleanDays(Number(event.target.value))}
                className="w-16 bg-slate-950 border border-slate-800 rounded px-2 py-2 text-[10px] text-white" title="Días a conservar" />
              <button onClick={() => runAction('queue_clean', { days: cleanDays }, true)} disabled={!!actionLoading || !dataConfirm}
                className="px-2 py-2 bg-red-800 hover:bg-red-700 disabled:opacity-50 rounded text-[10px] font-bold text-white">Limpiar</button>
            </div>
          </div>
          <label className="flex items-center gap-2 mt-3 text-[10px] text-amber-300">
            <input type="checkbox" checked={dataConfirm} onChange={event => setDataConfirm(event.target.checked)} className="accent-amber-500" />
            Confirmo modificaciones, limpieza o ejecución de acciones operativas
          </label>
        </Card>
      </div>

      <Card>
        <div className="flex items-start justify-between gap-3 mb-3">
          <div>
            <h3 className="text-sm font-bold text-green-300 flex items-center gap-2"><Edit3 size={14} /> Contactos y destinos</h3>
            <p className="text-[11px] text-slate-500 mt-1">Crea, edita y elimina destinos usados por los canales y alertas.</p>
          </div>
          {editingContact && <button onClick={resetContactForm} className="text-[10px] text-slate-400 hover:text-white">Nuevo contacto</button>}
        </div>
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <div className="space-y-1.5 max-h-64 overflow-y-auto">
            {Object.keys(contacts).length === 0 && <p className="text-xs text-slate-600">No hay contactos.</p>}
            {Object.entries(contacts).map(([id, contact]: [string, any]) => (
              <div key={id} className="bg-slate-950/70 border border-slate-800 rounded-lg p-2.5">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-white">{id}</span>
                  <span className="text-xs text-slate-300 truncate">{contact.name || 'Sin nombre'}</span>
                  <span className="ml-auto text-[9px] text-slate-600">P{contact.priority ?? 5}</span>
                  <button onClick={() => editContact(id, contact)} className="text-cyan-400 hover:text-cyan-300" title="Editar"><Edit3 size={12} /></button>
                  <button onClick={() => deleteContact(id)} disabled={!dataConfirm} className="text-red-400 hover:text-red-300 disabled:opacity-30" title="Eliminar"><Trash2 size={12} /></button>
                </div>
                <div className="text-[9px] text-slate-600 mt-1 truncate">{contact.phone || contact.telegram_chat_id || contact.sip_address || 'Sin destino configurado'}</div>
              </div>
            ))}
          </div>
          <div className="bg-slate-950/50 rounded-lg p-3">
            <div className="grid grid-cols-2 gap-2">
              <label className="text-[10px] text-slate-500">ID
                <input value={contactForm.id} disabled={!!editingContact} onChange={event => setContactForm(current => ({ ...current, id: event.target.value }))}
                  className="mt-1 w-full bg-slate-900 border border-slate-800 rounded px-2 py-2 text-xs text-white disabled:opacity-60" />
              </label>
              <label className="text-[10px] text-slate-500">Nombre
                <input value={contactForm.name} onChange={event => setContactForm(current => ({ ...current, name: event.target.value }))}
                  className="mt-1 w-full bg-slate-900 border border-slate-800 rounded px-2 py-2 text-xs text-white" />
              </label>
              {(['phone', 'telegram_chat_id', 'sip_address', 'mesh_wifi_ip', 'mesh_bluetooth_mac'] as const).map(field => (
                <label key={field} className="text-[10px] text-slate-500">{field}
                  <input value={contactForm[field]} onChange={event => setContactForm(current => ({ ...current, [field]: event.target.value }))}
                    className="mt-1 w-full bg-slate-900 border border-slate-800 rounded px-2 py-2 text-xs text-white" />
                </label>
              ))}
              <label className="text-[10px] text-slate-500">Prioridad
                <input type="number" min={1} max={10} value={contactForm.priority} onChange={event => setContactForm(current => ({ ...current, priority: Number(event.target.value) }))}
                  className="mt-1 w-full bg-slate-900 border border-slate-800 rounded px-2 py-2 text-xs text-white" />
              </label>
              <label className="flex items-center gap-2 self-end text-[10px] text-slate-400 pb-2"><input type="checkbox" checked={contactForm.trusted} onChange={event => setContactForm(current => ({ ...current, trusted: event.target.checked }))} className="accent-green-500" /> De confianza</label>
            </div>
            <div className="flex items-center gap-2 mt-3">
              <button onClick={saveContact} disabled={contactSaving || !dataConfirm || !contactForm.name.trim() || (!editingContact && !contactForm.id.trim())}
                className="px-3 py-2 bg-green-700 hover:bg-green-600 disabled:opacity-50 rounded text-[10px] font-bold text-white">
                {contactSaving ? 'Guardando…' : editingContact ? 'Actualizar contacto' : 'Crear contacto'}
              </button>
              <span className="text-[9px] text-slate-600">Requiere la confirmación de cambios.</span>
            </div>
          </div>
        </div>
      </Card>

      <Card>
        <h3 className="text-sm font-bold text-purple-300 flex items-center gap-2 mb-2"><Radio size={14} /> Enviar ubicación</h3>
        <div className="flex flex-wrap items-center gap-2">
          <select value={emergencyContact} onChange={event => setEmergencyContact(event.target.value)}
            className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white">
            <option value="">Selecciona un contacto</option>
            {Object.entries(contacts).map(([id, contact]: [string, any]) => <option key={id} value={id}>{id} — {contact.name || 'sin nombre'}</option>)}
          </select>
          <button onClick={() => runAction('send_location', { contact: emergencyContact }, true)}
            disabled={!!actionLoading || !emergencyContact || !dataConfirm}
            className="px-3 py-2 bg-purple-700 hover:bg-purple-600 disabled:opacity-50 rounded-lg text-xs font-bold text-white">
            {actionLoading === 'send_location' ? 'Enviando…' : 'Enviar ubicación por fallback'}
          </button>
          <span className="text-[10px] text-slate-600">Transmite al contacto seleccionado y requiere confirmación.</span>
        </div>
      </Card>

      {actionResult && <pre className="bg-black/50 border border-slate-800 rounded-lg p-3 text-[10px] text-amber-300 font-mono max-h-56 overflow-y-auto whitespace-pre-wrap">{JSON.stringify(actionResult, null, 2)}</pre>}

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