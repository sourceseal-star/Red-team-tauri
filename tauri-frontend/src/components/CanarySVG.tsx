import { useState, useCallback, useEffect } from 'react'
import { api, getApiKey, setApiKey } from '../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from './ui/card'
import { Button } from './ui/button'
import { Badge } from './ui/badge'
import { Loader2, Shield, FileImage, Download, AlertTriangle, Eye, Trash2, Plus, Bug } from 'lucide-react'

interface CanaryAlert {
  type: string
  severity: string
  token: string
  filename?: string
  triggered_by_ip?: string
  user_agent?: string
  referer?: string
  vector?: string
  timestamp: string
  hostname?: string | null
  canary_path?: string
  elapsed?: number
}

interface CanaryToken {
  token: string
  filename: string
  path: string
  created: string
  callback_url: string
  sha256?: string
  size?: number
}

export function CanarySVG() {
  const [tokens, setTokens] = useState<CanaryToken[]>([])
  const [alerts, setAlerts] = useState<CanaryAlert[]>([])
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filename, setFilename] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [keyInput, setKeyInput] = useState(getApiKey() || '')

  const fetchAll = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const r = await fetch('/api/canary/svg/list', {
        headers: { 'Authorization': `Bearer ${getApiKey() || ''}` }
      })
      if (r.ok) {
        const data = await r.json()
        setTokens(Object.values(data.tokens || {}))
        setAlerts(data.alerts || [])
      } else if (r.status === 401) {
        setError('API key requerida — presiona el botón de la llave')
      } else {
        setError(`Error ${r.status}`)
      }
    } catch (e: any) {
      setError(e?.message || 'Error cargando datos')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchAll() }, [fetchAll])

  const generate = async () => {
    setGenerating(true)
    setError(null)
    try {
      const r = await fetch('/api/canary/svg/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${getApiKey() || ''}` },
        body: JSON.stringify({
          filename: filename || `canary_${Date.now()}.svg`,
          callback_host: window.location.host,
        })
      })
      if (r.ok) {
        setFilename('')
        await fetchAll()
      } else {
        const d = await r.json().catch(() => ({}))
        setError(d.error || `Error ${r.status}`)
      }
    } catch (e: any) {
      setError(e?.message || 'Error generando SVG')
    } finally {
      setGenerating(false)
    }
  }

  const deploySet = async () => {
    setGenerating(true)
    try {
      const r = await fetch('/api/canary/svg/deploy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${getApiKey() || ''}` },
        body: JSON.stringify({ count: 5, callback_host: window.location.host })
      })
      if (r.ok) await fetchAll()
    } catch (e: any) {
      setError(e?.message || 'Error desplegando decoys')
    } finally {
      setGenerating(false)
    }
  }

  const clearAlerts = async () => {
    try {
      await fetch('/api/canary/svg/clear', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${getApiKey() || ''}` },
        body: '{}'
      })
      await fetchAll()
    } catch {}
  }

  const download = (fname: string) => {
    window.open(`/api/canary/svg/download?filename=${encodeURIComponent(fname)}`, '_blank')
  }

  return (
    <Card className="border-orange-900/30">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <Bug className="h-4 w-4 text-orange-400" />
          SVG Canary — Tokens Camuflados
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* API Key */}
        <div className="flex gap-2 items-center">
          <Button size="sm" variant="ghost" onClick={() => setShowKey(!showKey)} className="px-2">
            <Shield className="h-3 w-3" />
          </Button>
          {showKey && (
            <div className="flex gap-1 flex-1">
              <input type="password" placeholder="API key" value={keyInput}
                onChange={e => setKeyInput(e.target.value)}
                className="bg-muted rounded px-2 py-1 text-xs flex-1 border border-border" />
              <Button size="sm" onClick={() => { setApiKey(keyInput.trim()); setShowKey(false) }}>OK</Button>
            </div>
          )}
        </div>

        {/* Generar */}
        <div className="flex gap-2 flex-wrap items-end">
          <div className="flex-1 min-w-[200px]">
            <label className="text-[10px] text-muted-foreground uppercase tracking-wider">Nombre del archivo SVG</label>
            <input type="text" placeholder="photo_decoy.svg" value={filename}
              onChange={e => setFilename(e.target.value)}
              className="bg-muted rounded px-3 py-2 text-sm w-full border border-border font-mono" />
          </div>
          <Button size="sm" onClick={generate} disabled={generating}>
            {generating ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Plus className="h-4 w-4 mr-1" />}
            Generar SVG
          </Button>
          <Button size="sm" variant="outline" onClick={deploySet} disabled={generating}>
            <FileImage className="h-4 w-4 mr-1" />
            Desplegar 5 decoys
          </Button>
        </div>

        {error && <div className="text-xs text-red-400 bg-red-950 rounded p-2 border border-red-800">{error}</div>}

        {/* Alertas */}
        {alerts.length > 0 && (
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <div className="text-xs font-medium text-red-400 flex items-center gap-1">
                <AlertTriangle className="h-3 w-3" />
                Alertas de Canary ({alerts.length})
              </div>
              <Button size="sm" variant="ghost" className="h-5 text-[10px] px-1" onClick={clearAlerts}>
                <Trash2 className="h-3 w-3" /> Limpiar
              </Button>
            </div>
            {alerts.slice(-10).reverse().map((a, i) => (
              <div key={i} className="bg-red-950/50 border border-red-800/40 rounded p-2 text-xs space-y-1">
                <div className="flex items-center gap-2">
                  <Badge variant="destructive" className="text-[9px]">{a.severity}</Badge>
                  <span className="font-mono">{a.triggered_by_ip}</span>
                  {a.hostname && <span className="text-muted-foreground">({a.hostname})</span>}
                  <Badge variant="outline" className="text-[9px] ml-auto">vector: {a.vector || '?'}</Badge>
                </div>
                <div className="text-muted-foreground">
                  {a.filename && <span>📎 {a.filename} · </span>}
                  UA: <span className="font-mono">{(a.user_agent || '').slice(0, 60)}</span>
                </div>
                <div className="text-[10px] text-muted-foreground">{new Date(a.timestamp).toLocaleString()}</div>
              </div>
            ))}
          </div>
        )}

        {/* Tokens */}
        {tokens.length > 0 && (
          <div className="space-y-1">
            <div className="text-xs font-medium text-orange-400 flex items-center gap-1">
              <Eye className="h-3 w-3" />
              Tokens Activos ({tokens.length})
            </div>
            {tokens.map((t, i) => (
              <div key={i} className="bg-muted rounded border border-orange-800/20 p-2 text-xs space-y-1">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-orange-300">{t.filename}</span>
                  <Badge variant="secondary" className="text-[9px]">{t.size} bytes</Badge>
                  <Button size="sm" variant="ghost" className="h-5 ml-auto text-[10px] px-1"
                    onClick={() => download(t.filename)}>
                    <Download className="h-3 w-3 mr-1" />Descargar
                  </Button>
                </div>
                <div className="text-[10px] text-muted-foreground font-mono truncate">
                  Token: {t.token}
                </div>
                <div className="text-[10px] text-muted-foreground">
                  Creado: {new Date(t.created).toLocaleString()}
                </div>
              </div>
            ))}
          </div>
        )}

        {loading && <div className="flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Cargando…</div>}

        {!loading && tokens.length === 0 && alerts.length === 0 && (
          <div className="text-xs text-muted-foreground text-center py-4">
            No hay SVG canary activos. Genera uno arriba para empezar.
          </div>
        )}
      </CardContent>
    </Card>
  )
}
