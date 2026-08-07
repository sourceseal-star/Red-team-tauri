import { useEffect, useState } from 'react'
import { api, type Settings } from '../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Save, RefreshCw, Trash2 } from 'lucide-react'

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings>({ api_url: '', interval: 15 })
  const [loading, setLoading]   = useState(false)
  const [msg, setMsg]           = useState('')

  const load = async () => {
    setLoading(true)
    try { setSettings(await api.getSettings()) } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const save = async () => {
    await api.saveSettings(settings)
    setMsg('✓ Configuración guardada')
    setTimeout(() => setMsg(''), 3000)
  }

  const reset = async () => {
    if (!confirm('¿Resetear configuración a valores por defecto?')) return
    const defaults: Settings = { api_url: '', interval: 15, scan_on_startup: false, notify_slack: false, slack_webhook: '' }
    await api.saveSettings(defaults)
    setSettings(defaults)
    setMsg('✓ Configuración reseteada')
    setTimeout(() => setMsg(''), 3000)
  }

  return (
    <div className="space-y-4 max-w-lg">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Settings</h2>
        <Button size="sm" variant="outline" onClick={load} disabled={loading}>
          <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {msg && <div className="text-sm text-green-400 bg-green-900/20 border border-green-800 rounded px-3 py-2">{msg}</div>}

      <Card>
        <CardHeader><CardTitle>Conexión al backend</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div>
            <label className="text-xs text-muted-foreground">Target URL (dominio a escanear — ej: https://midominio.com)</label>
            <input className="mt-1 w-full bg-muted border border-border rounded px-2 py-1.5 text-sm font-mono"
              value={settings.api_url ?? ''}
              onChange={e => setSettings(s => ({ ...s, api_url: e.target.value }))} />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">Intervalo de polling (segundos)</label>
            <input type="number" min="5" max="300"
              className="mt-1 w-full bg-muted border border-border rounded px-2 py-1.5 text-sm"
              value={settings.interval ?? 15}
              onChange={e => setSettings(s => ({ ...s, interval: +e.target.value }))} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Escaneo</CardTitle></CardHeader>
        <CardContent>
          <label className="flex items-center gap-3 cursor-pointer">
            <input type="checkbox"
              checked={settings.scan_on_startup ?? false}
              onChange={e => setSettings(s => ({ ...s, scan_on_startup: e.target.checked }))}
              className="h-4 w-4 rounded" />
            <span className="text-sm">Ejecutar escaneo automáticamente al iniciar</span>
          </label>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Notificaciones</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <label className="flex items-center gap-3 cursor-pointer">
            <input type="checkbox"
              checked={settings.notify_slack ?? false}
              onChange={e => setSettings(s => ({ ...s, notify_slack: e.target.checked }))}
              className="h-4 w-4 rounded" />
            <span className="text-sm">Enviar alertas a Slack</span>
          </label>
          {settings.notify_slack && (
            <div>
              <label className="text-xs text-muted-foreground">Slack Webhook URL</label>
              <input className="mt-1 w-full bg-muted border border-border rounded px-2 py-1.5 text-sm font-mono"
                placeholder="https://hooks.slack.com/services/..."
                value={settings.slack_webhook ?? ''}
                onChange={e => setSettings(s => ({ ...s, slack_webhook: e.target.value }))} />
            </div>
          )}
        </CardContent>
      </Card>

      <div className="flex gap-2">
        <Button onClick={save} className="flex-1">
          <Save className="h-4 w-4 mr-2" />Guardar
        </Button>
        <Button variant="outline" onClick={reset}>
          <Trash2 className="h-4 w-4 mr-1" />Reset
        </Button>
      </div>
    </div>
  )
}
