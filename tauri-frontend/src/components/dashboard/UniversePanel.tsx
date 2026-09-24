import { useCallback, useEffect, useRef, useState } from 'react'
import { Activity, HardDrive, Image as ImageIcon, RefreshCw, Send, Upload, Video, Wifi, X } from 'lucide-react'

type NetContext = { local_ip?: string; stack?: string; privilege?: string; fd_count?: number }
type UniverseStatus = {
  started?: string; net?: NetContext | null; nodes?: Record<string, { online?: boolean; addr?: string; port?: number }>;
  fd_count?: number; fd_now?: number; last_purge?: string | null; purges?: number;
  media?: { count?: number; bytes?: number; last_index?: string | null };
  last_action?: string; last_mesh?: string;
}
type MediaItem = { filename: string; type: string; size_bytes: number; modified: string }

// FIX 2026-09-24: /api/* exige Bearer — antes este panel llamaba sin token
// y el middleware respondía 401, por eso siempre mostraba "sin datos".
const authHeaders = (): Record<string, string> => {
  const token = localStorage.getItem('api_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

const fmtBytes = (n: number) => n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : n >= 1024 ? `${(n / 1024).toFixed(1)} KB` : `${n} B`
const fmtDate = (iso?: string | null) => iso ? new Date(iso).toLocaleString() : '—'

const ACTIONS = [
  { id: 'health_check', label: 'Health check', icon: Activity },
  { id: 'net_inspect', label: 'Inspección red', icon: Wifi },
  { id: 'purge_sockets', label: 'Purga de sockets', icon: HardDrive },
  { id: 'media_index', label: 'Reindexar medios', icon: ImageIcon },
  { id: 'mesh_sync', label: 'Mesh sync', icon: Send },
] as const

export default function UniversePanel() {
  const [status, setStatus] = useState<UniverseStatus | null>(null)
  const [media, setMedia] = useState<MediaItem[]>([])
  const [previews, setPreviews] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [uploading, setUploading] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  const previewsRef = useRef<Record<string, string>>({})

  const loadStatus = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const response = await fetch('/api/universe/status', { cache: 'no-store', headers: authHeaders() })
      const body = await response.json().catch(() => ({}))
      if (response.status === 401) throw new Error('Sesión no autenticada (401): ingresa el token del War Room')
      if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`)
      setStatus(body)
    } catch (err) { setError(err instanceof Error ? err.message : 'No se pudo consultar Universe') }
    finally { setLoading(false) }
  }, [])

  // Cada preview se descarga CON token y se sirve como blob local:
  // el <img>/<video> nunca necesita una URL sin autenticación.
  const loadPreview = useCallback(async (filename: string) => {
    if (previewsRef.current[filename]) return
    try {
      const response = await fetch(`/api/universe/media/view/${encodeURIComponent(filename)}`, { headers: authHeaders() })
      if (!response.ok) return
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      previewsRef.current[filename] = url
      setPreviews({ ...previewsRef.current })
    } catch { /* preview opcional: fallo silencioso */ }
  }, [])

  const loadMedia = useCallback(async () => {
    try {
      const response = await fetch('/api/universe/media/list', { cache: 'no-store', headers: authHeaders() })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`)
      setMedia(Array.isArray(body.media) ? body.media : [])
      body.media?.forEach?.((item: MediaItem) => { void loadPreview(item.filename) })
    } catch (err) { setError(err instanceof Error ? err.message : 'No se pudo listar medios') }
  }, [loadPreview])

  useEffect(() => {
    void loadStatus(); void loadMedia()
    const urls = previewsRef.current
    return () => { Object.values(urls).forEach(u => URL.revokeObjectURL(u)) }
  }, [loadStatus, loadMedia])

  const runAction = async (action: string) => {
    setBusy(action); setMessage(''); setError('')
    try {
      const response = await fetch('/api/universe/sync', {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      })
      const body = await response.json().catch(() => ({}))
      if (response.status === 401) throw new Error('Sesión no autenticada (401)')
      if (!response.ok) throw new Error(body.detail?.[0]?.msg || body.detail || `HTTP ${response.status}`)
      setMessage(`✓ ${action} ejecutado con datos reales`)
      await loadStatus()
      if (action === 'media_index') await loadMedia()
    } catch (err) { setError(err instanceof Error ? err.message : 'No se pudo ejecutar la acción') }
    finally { setBusy(null) }
  }

  const uploadFiles = async (files: FileList | null) => {
    if (!files?.length) return
    setUploading(true); setMessage(''); setError('')
    for (const file of Array.from(files)) {
      try {
        const form = new FormData()
        form.append('file', file)
        const response = await fetch('/api/universe/media/upload', { method: 'POST', headers: authHeaders(), body: form })
        const body = await response.json().catch(() => ({}))
        if (!response.ok) throw new Error(body.detail || `HTTP ${response.status} (${file.name})`)
      } catch (err) {
        setError(err instanceof Error ? err.message : `No se pudo subir ${file.name}`)
        break
      }
    }
    setUploading(false)
    if (fileInput.current) fileInput.current.value = ''
    await loadMedia(); await loadStatus()
    if (!error) setMessage('✓ Medios subidos y guardados en ~/warroom/media')
  }

  const net = status?.net || null
  const nodesOnline = Object.values(status?.nodes || {}).filter(n => n.online).length
  const nodesTotal = Object.keys(status?.nodes || {}).length

  return (
    <div className="min-h-full bg-slate-950 text-slate-100 p-4 md:p-6 space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-fuchsia-300 text-xs uppercase tracking-[0.22em]"><Activity className="w-4 h-4" /> Universe v4 · universe.py</div>
          <h1 className="text-2xl font-semibold mt-1">Estado real del universo</h1>
          <p className="text-slate-400 text-sm mt-1">Red userland sin root · health-check · medios de la videollamada de Sol 🌌</p>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={() => { void loadStatus(); void loadMedia() }} disabled={loading}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-fuchsia-700/50 bg-fuchsia-950/30 text-fuchsia-200 text-sm hover:bg-fuchsia-900/40 disabled:opacity-50">
            <RefreshCw className={loading ? 'w-4 h-4 animate-spin' : 'w-4 h-4'} /> Actualizar
          </button>
        </div>
      </div>

      {error && <div className="rounded-lg border border-red-800/60 bg-red-950/30 p-3 text-red-200 text-sm">{error}</div>}
      {message && <div className="rounded-lg border border-emerald-800/60 bg-emerald-950/30 p-3 text-emerald-200 text-sm">{message}</div>}

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {[
          ['IP local real', net?.local_ip || 'sin datos'],
          ['Sockets (fd)', String(status?.fd_now ?? '—')],
          ['Nodos online', `${nodesOnline}/${nodesTotal}`],
          ['Purgas', String(status?.purges ?? 0)],
          ['Medios', `${status?.media?.count ?? 0} · ${fmtBytes(status?.media?.bytes ?? 0)}`],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
            <div className="text-[10px] uppercase tracking-widest text-slate-500">{label}</div>
            <div className="text-lg mt-1 font-mono truncate" title={value}>{value}</div>
          </div>
        ))}
      </div>

      <section className="rounded-xl border border-slate-800 bg-slate-900/70 p-4 space-y-3">
        <div className="flex items-center justify-between gap-2">
          <h2 className="font-medium">Acciones con datos reales</h2>
          <span className="text-xs text-slate-500">POST /api/universe/sync</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">
          {ACTIONS.map(({ id, label, icon: Icon }) => (
            <button key={id} type="button" onClick={() => void runAction(id)} disabled={busy !== null}
              className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 hover:border-fuchsia-500 hover:text-fuchsia-200 disabled:opacity-50">
              <Icon className="w-4 h-4" /> {busy === id ? 'Ejecutando…' : label}
            </button>
          ))}
        </div>
        <div className="text-xs text-slate-500 grid grid-cols-1 sm:grid-cols-2 gap-1">
          <div>Privilegios: {net?.privilege || '—'} · Stack: {net?.stack || '—'}</div>
          <div>Iniciado: {fmtDate(status?.started)} · Última acción: {status?.last_action || '—'}</div>
        </div>
      </section>

      <section className="rounded-xl border border-slate-800 bg-slate-900/70 p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-medium flex items-center gap-2"><ImageIcon className="w-4 h-4" /> Galería de medios</h2>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">{media.length} archivo(s) en ~/warroom/media</span>
            <input ref={fileInput} type="file" accept="image/*,video/*" multiple hidden
              onChange={e => void uploadFiles(e.target.files)} />
            <button type="button" onClick={() => fileInput.current?.click()} disabled={uploading}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-fuchsia-700/50 bg-fuchsia-950/30 text-fuchsia-200 text-sm hover:bg-fuchsia-900/40 disabled:opacity-50">
              {uploading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
              {uploading ? 'Subiendo…' : 'Subir imagen/video'}
            </button>
          </div>
        </div>
        {media.length === 0 ? (
          <p className="text-sm text-slate-500">Todavía no hay medios. Sube capturas de la videollamada de Sol o cualquier imagen/video del ecosistema.</p>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {media.map(item => (
              <div key={item.filename} className="rounded-lg border border-slate-800 bg-slate-950 overflow-hidden">
                <div className="aspect-video bg-black/50 flex items-center justify-center">
                  {previews[item.filename] && item.type === 'image' && (
                    <img src={previews[item.filename]} alt={item.filename} className="w-full h-full object-contain" />
                  )}
                  {previews[item.filename] && item.type === 'video' && (
                    <video src={previews[item.filename]} controls className="w-full h-full object-contain" />
                  )}
                  {!previews[item.filename] && <Video className="w-8 h-8 text-slate-600" />}
                </div>
                <div className="p-2">
                  <p className="text-xs truncate text-slate-300" title={item.filename}>{item.filename}</p>
                  <p className="text-[10px] text-slate-500">{fmtBytes(item.size_bytes)} · {item.type === 'video' ? <Video className="inline w-3 h-3" /> : <ImageIcon className="inline w-3 h-3" />} {item.type}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
