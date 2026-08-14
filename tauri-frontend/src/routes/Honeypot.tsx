import { useEffect, useState } from 'react'
import { api, type HoneypotStatus } from '../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Badge } from '../components/ui/badge'
import { RotateCcw, Power, RefreshCw, AlertTriangle } from 'lucide-react'

export default function Honeypot() {
  const [status, setStatus]   = useState<HoneypotStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [msg, setMsg]         = useState('')

  const load = async () => {
    setLoading(true)
    try { setStatus(await api.getHoneypot()) } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const toggle = async () => {
    const s = await api.toggleHoneypot()
    setStatus(s)
    setMsg(s.active ? '✓ Honeypot activado' : '○ Honeypot desactivado')
    setTimeout(() => setMsg(''), 3000)
  }

  const rotate = async () => {
    const r = await api.rotateTokens()
    setMsg(`✓ ${r.tokens_deployed} tokens rotados`)
    setTimeout(() => setMsg(''), 3000)
    load()
  }

  if (!status && !loading) return <p className="text-muted-foreground text-sm">Cargando…</p>

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Deception / Honeypot</h2>
        <Button size="sm" variant="outline" onClick={load} disabled={loading}>
          <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {msg && <div className="text-sm text-green-400 bg-green-900/20 border border-green-800 rounded px-3 py-2">{msg}</div>}

      {status && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {/* Estado */}
            <Card>
              <CardHeader><CardTitle>Estado</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <Badge variant={status.active ? 'default' : 'secondary'} className="text-sm px-3 py-1">
                  {status.active ? '● Activo' : '○ Inactivo'}
                </Badge>
                <Button size="sm" variant={status.active ? 'destructive' : 'default'} className="w-full" onClick={toggle}>
                  <Power className="h-3 w-3 mr-1" />
                  {status.active ? 'Desactivar' : 'Activar'}
                </Button>
              </CardContent>
            </Card>

            {/* Tokens */}
            <Card>
              <CardHeader><CardTitle>Canary Tokens</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <p className="text-3xl font-bold font-mono">{status.tokens_deployed}</p>
                <p className="text-xs text-muted-foreground">
                  Rotados: {status.token_rotated_at
                    ? new Date(status.token_rotated_at).toLocaleString()
                    : 'nunca'}
                </p>
                <Button size="sm" variant="outline" className="w-full" onClick={rotate}>
                  <RotateCcw className="h-3 w-3 mr-1" />Rotar tokens
                </Button>
              </CardContent>
            </Card>

            {/* Triggers */}
            <Card>
              <CardHeader><CardTitle>Alertas</CardTitle></CardHeader>
              <CardContent className="space-y-2">
                <div>
                  <p className={`text-3xl font-bold font-mono ${status.triggers_today > 0 ? 'text-red-400' : 'text-green-400'}`}>
                    {status.triggers_today}
                  </p>
                  <p className="text-xs text-muted-foreground">hoy</p>
                </div>
                <div>
                  <p className="text-xl font-bold font-mono text-muted-foreground">{status.triggers_total ?? 0}</p>
                  <p className="text-xs text-muted-foreground">total</p>
                </div>
                {status.last_trigger && (
                  <p className="text-xs text-red-400 flex items-center gap-1">
                    <AlertTriangle className="h-3 w-3" />
                    {new Date(status.last_trigger).toLocaleString()}
                  </p>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Info */}
          <Card>
            <CardHeader><CardTitle>¿Cómo funciona?</CardTitle></CardHeader>
            <CardContent className="text-xs text-muted-foreground space-y-1">
              <p>• Los <strong className="text-foreground">Canary Tokens</strong> son URLs, archivos y credenciales falsas distribuidas en el entorno.</p>
              <p>• Si un atacante accede a uno, el sistema registra la alerta automáticamente.</p>
              <p>• Rotarlos invalida los tokens existentes y genera nuevos, minimizando exposición.</p>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
