import { useEffect, useState } from 'react'
import { api, type Report, type Finding } from '../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { RefreshCw, Play, ChevronDown, ChevronRight, AlertTriangle, Shield } from 'lucide-react'

const SEV_COLOR: Record<string, string> = {
  critical: 'text-red-500',
  high:     'text-orange-400',
  medium:   'text-yellow-400',
  low:      'text-blue-400',
  info:     'text-gray-400',
}
const SEV_BADGE: Record<string, 'destructive' | 'default' | 'secondary' | 'outline'> = {
  critical: 'destructive', high: 'destructive', medium: 'default', low: 'secondary', info: 'outline',
}

export default function Reports() {
  const [history, setHistory]   = useState<Report[]>([])
  const [latest, setLatest]     = useState<Report | null>(null)
  const [scanStatus, setScan]   = useState<{ running: boolean; progress: string }>({ running: false, progress: '' })
  const [expanded, setExpanded] = useState<string | null>(null)
  const [loading, setLoading]   = useState(false)

  const loadAll = async () => {
    setLoading(true)
    try {
      const [h, l, s] = await Promise.all([api.getHistory(), api.getLatestReport(), api.getScanStatus()])
      setHistory(h)
      setLatest(l)
      setScan({ running: s.running, progress: s.progress })
    } finally {
      setLoading(false)
    }
  }

  const [scanTarget, setScanTarget] = useState('')

  const runScan = async () => {
    setScan({ running: true, progress: 'Iniciando...' })
    await api.startScan(scanTarget || undefined)
    const poll = setInterval(async () => {
      const s = await api.getScanStatus()
      setScan({ running: s.running, progress: s.progress })
      if (!s.running) { clearInterval(poll); loadAll() }
    }, 2000)
  }

  useEffect(() => { loadAll() }, [])

  const bySev = latest?.by_severity

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Reports</h2>
        <div className="flex gap-2">
          <div className="flex items-center gap-2">
            <input
              className="bg-muted border border-border rounded px-2 py-1.5 text-sm font-mono w-64"
              placeholder="Target (ej: https://midominio.com)"
              value={scanTarget}
              onChange={e => setScanTarget(e.target.value)}
              disabled={scanStatus.running}
            />
            <Button size="sm" onClick={runScan} disabled={scanStatus.running} className="bg-blue-600 hover:bg-blue-700">
              <Play className={`h-3 w-3 mr-1 ${scanStatus.running ? 'animate-spin' : ''}`} />
              {scanStatus.running ? scanStatus.progress || 'Escaneando…' : 'Ejecutar escaneo'}
            </Button>
          </div>
          <Button size="sm" variant="outline" onClick={loadAll} disabled={loading}>
            <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {/* Último reporte — resumen de severidad */}
      {latest && (
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Shield className="h-4 w-4" />Último reporte — {latest.total_findings} findings</CardTitle></CardHeader>
          <CardContent>
            <div className="flex gap-4 flex-wrap">
              {Object.entries(bySev ?? {}).map(([sev, count]) => (
                <div key={sev} className="text-center">
                  <p className={`text-2xl font-bold font-mono ${SEV_COLOR[sev]}`}>{count as number}</p>
                  <p className="text-xs text-muted-foreground capitalize">{sev}</p>
                </div>
              ))}
            </div>
            {latest.message && <p className="text-sm text-muted-foreground mt-3">{latest.message}</p>}
          </CardContent>
        </Card>
      )}

      {/* Findings del último reporte */}
      {latest?.findings && latest.findings.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><AlertTriangle className="h-4 w-4 text-yellow-400" />Findings detallados</CardTitle></CardHeader>
          <CardContent className="p-0">
            {latest.findings.map((f: Finding, i: number) => (
              <div key={i} className="border-b border-border/50 last:border-0">
                <button
                  className="w-full text-left px-4 py-2 flex items-center gap-3 hover:bg-muted/30 transition-colors"
                  onClick={() => setExpanded(expanded === `f${i}` ? null : `f${i}`)}
                >
                  {expanded === `f${i}` ? <ChevronDown className="h-3 w-3 shrink-0" /> : <ChevronRight className="h-3 w-3 shrink-0" />}
                  <Badge variant={SEV_BADGE[f.severity] ?? 'outline'} className="shrink-0 text-xs">{f.severity}</Badge>
                  <span className="text-sm font-medium truncate">{f.title}</span>
                  <span className="ml-auto text-xs text-muted-foreground shrink-0 font-mono">{f.scenario}</span>
                </button>
                {expanded === `f${i}` && (
                  <div className="px-4 pb-3 space-y-2 bg-muted/10">
                    <p className="text-xs text-muted-foreground">{f.description}</p>
                    {f.remediation && <p className="text-xs text-green-400">✓ Remediación: {f.remediation}</p>}
                    {f.evidence_path && <p className="text-xs font-mono text-muted-foreground">{f.evidence_path}</p>}
                  </div>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Historial */}
      <h3 className="text-sm font-semibold text-muted-foreground">Historial de escaneos</h3>
      <div className="space-y-2">
        {history.map((r, i) => (
          <Card key={i}>
            <CardContent className="flex items-center justify-between py-3">
              <div>
                <p className="font-mono text-xs">{r.file ?? r.id ?? `Reporte ${i + 1}`}</p>
                <p className="text-xs text-muted-foreground">{r.finished_at ? new Date(r.finished_at).toLocaleString() : ''}</p>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-sm font-mono">{r.total_findings} findings</span>
                {(r.by_severity?.critical ?? 0) > 0 && (
                  <Badge variant="destructive">{r.by_severity.critical} critical</Badge>
                )}
                {r.elapsed_seconds && <span className="text-xs text-muted-foreground">{r.elapsed_seconds}s</span>}
              </div>
            </CardContent>
          </Card>
        ))}
        {history.length === 0 && !loading && (
          <p className="text-muted-foreground text-sm text-center py-8">Sin reportes — ejecuta tu primer escaneo.</p>
        )}
      </div>
    </div>
  )
}
