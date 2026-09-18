import { useState, useEffect, useRef, useCallback } from 'react'
import { Activity, Crosshair, Play, FileDown, RefreshCw, Shield, AlertTriangle, CheckCircle, Loader2, Zap } from 'lucide-react'

// ==========================================
// TACTICAL PANEL — Auditoría táctica integral
// ==========================================

// Formas REALES que devuelve /api/tactical/status/{job_id} (sin cosmética)
interface JobProgress {
  current: number
  total: number
  subnet?: string
  percent: number
}

interface SubnetReport {
  subnet: string
  hosts_found: number
  cameras: number
  credentials_found: number
  report: string
}

interface ScanSummary {
  status: string
  subnets_done: SubnetReport[]
  reports: Array<{ subnet?: string; filename: string; hash: string }>
  hosts_found: number
  ports_open: number
  cameras_identified: number
  credentials_found: number
  findings: Array<{
    host: string
    ports: string
    vendor: string
    credentials: string
  }>
}

interface LogEntry {
  timestamp: string
  message: string
  level: 'info' | 'success' | 'warning' | 'error'
}

export default function TacticalPanel() {
  const [scanning, setScanning] = useState(false)
  const [subnet, setSubnet] = useState('')
  const [result, setResult] = useState<ScanSummary | null>(null)
  const [progress, setProgress] = useState<JobProgress | null>(null)
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [credentials, setCredentials] = useState<Record<string, number> | null>(null)
  const [ports, setPorts] = useState<Array<{ port: number; service: string; vendor: string }> | null>(null)
  const logRef = useRef<HTMLDivElement>(null)

  // Auto-scroll logs
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [logs])

  const addLog = useCallback((message: string, level: LogEntry['level'] = 'info') => {
    setLogs(prev => [...prev, {
      timestamp: new Date().toLocaleTimeString(),
      message,
      level
    }])
  }, [])

  // Cargar diccionario de credenciales y puertos al montar
  useEffect(() => {
    fetch('/api/tactical/credentials')
      .then(async r => {
        if (!r.ok) return null
        const data = await r.json()
        const counts = data?.counts ?? data
        return counts && typeof counts === 'object' && !Array.isArray(counts)
          ? counts as Record<string, number>
          : null
      })
      .then(data => { if (data) setCredentials(data) })
      .catch(() => {})

    fetch('/api/tactical/ports')
      .then(async r => {
        if (!r.ok) return null
        const data = await r.json()
        const availablePorts = data?.ports ?? data
        return Array.isArray(availablePorts) ? availablePorts : null
      })
      .then(data => { if (data) setPorts(data) })
      .catch(() => {})
  }, [])

  // Ejecutar auditoría ASÍNCRONA multi-subred + polling cada 3s (patrón LEVIATHAN)
  const runScan = async () => {
    setScanning(true)
    setResult(null)
    setProgress(null)
    setLogs([])
    addLog('🚀 Iniciando auditoría táctica (asíncrona)...', 'info')
    const subnets = subnet.split(/[\s,]+/).map(s => s.trim()).filter(Boolean)
    addLog(`📡 Subredes: ${subnets.length ? subnets.join(', ') : 'auto-detectar'}`, 'info')

    try {
      const resp = await fetch('/api/tactical/scan/async', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(subnets.length ? { subnets } : {})
      })

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: 'Error desconocido' }))
        addLog(`❌ Error: ${err.error || err.detail}`, 'error')
        setScanning(false)
        return
      }

      const { job_id: jobId } = await resp.json()
      addLog(`🎫 Job aceptado: ${jobId} — polling cada 3s`, 'info')

      await new Promise<void>((resolve) => {
        const iv = setInterval(async () => {
          try {
            const r = await fetch(`/api/tactical/status/${jobId}`)
            const job = await r.json()
            if (job.progress) setProgress(job.progress)
            if (job.status === 'completed') {
              clearInterval(iv)
              const agg = job.results || {}
              const findings = (agg.cameras || []).map((c: any) => ({
                host: c.ip || '-',
                ports: (c.ports || []).join(', '),
                vendor: c.vendor || 'unknown',
                credentials: c.credentials ? `${c.credentials.user}:${c.credentials.password}` : ''
              }))
              const portsOpen = (agg.hosts || []).reduce(
                (n: number, h: any) => n + (h.ports || []).length, 0)
              setResult({
                status: 'completed',
                subnets_done: job.subnets_done || [],
                reports: job.reports || [],
                hosts_found: agg.hosts_scanned || 0,
                ports_open: portsOpen,
                cameras_identified: (agg.cameras || []).length,
                credentials_found: (agg.credentials_found || []).length,
                findings
              })
              addLog('✅ Auditoría completada', 'success')
              for (const s of job.subnets_done || []) {
                addLog(`🌐 ${s.subnet}: ${s.hosts_found} hosts · ${s.cameras} cámaras · ${s.credentials_found} creds → ${s.report}`, 'info')
              }
              if (job.errors?.length) {
                for (const e of job.errors) addLog(`❌ ${e.subnet}: ${e.error}`, 'error')
              }
              setScanning(false)
              resolve()
            }
          } catch { /* reintenta en el próximo tick */ }
        }, 3000)
      })
    } catch (err) {
      addLog(`❌ Error de conexión: ${err}`, 'error')
      setScanning(false)
    }
  }

  // Descargar reporte
  const downloadReport = (filename: string) => {
    window.open(`/api/tactical/report/${filename}`, '_blank')
  }

  return (
    <div className="min-h-full bg-slate-950 text-slate-200 p-4 space-y-4">
      {/* HEADER */}
      <div className="flex items-center gap-3 mb-2">
        <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-red-600 to-orange-600 flex items-center justify-center">
          <Crosshair className="w-7 h-7 text-white" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-slate-100">Auditoría Táctica</h1>
          <p className="text-xs text-slate-500">Motor de ejecución integral: descubrir → escanear → credenciales → CVEs → reporte sellado</p>
        </div>
      </div>

      {/* CONTROL PANEL */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1">
            <label className="text-xs text-slate-400 mb-1 block">Subredes / CIDR (separadas por coma = multi-red, vacío = auto-detectar)</label>
            <input
              type="text"
              value={subnet}
              onChange={e => setSubnet(e.target.value)}
              placeholder="192.168.1.0/24, 192.168.0.0/24"
              disabled={scanning}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-200 placeholder-slate-600 focus:border-orange-500 focus:outline-none disabled:opacity-50"
            />
          </div>
          <button
            onClick={runScan}
            disabled={scanning}
            className="px-6 py-2 bg-gradient-to-r from-red-600 to-orange-600 hover:from-red-500 hover:to-orange-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold rounded-lg flex items-center gap-2 transition-all"
          >
            {scanning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            {scanning ? 'Escaneando...' : 'Ejecutar Auditoría'}
          </button>
        </div>

        {/* Quick stats bar */}
        <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-800">
          {credentials && Object.entries(credentials).map(([vendor, count]) => (
            <span key={vendor} className="px-2 py-1 bg-slate-800 border border-slate-700 rounded text-xs text-slate-400">
              {vendor}: <span className="text-orange-400 font-mono">{count}</span> creds
            </span>
          ))}
          {ports && ports.map(p => (
            <span key={p.port} className="px-2 py-1 bg-slate-800 border border-slate-700 rounded text-xs text-slate-400">
              :{p.port} <span className="text-cyan-400">{p.service}</span>
            </span>
          ))}
        </div>
      </div>

      {/* BARRA DE PROGRESO (async multi-subred) */}
      {scanning && progress && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
            <span>Subred {progress.current}/{progress.total}: {progress.subnet || 'auto'}</span>
            <span className="font-mono text-orange-400">{progress.percent}%</span>
          </div>
          <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-red-600 to-orange-600 rounded-full transition-all duration-500"
              style={{ width: `${progress.percent}%` }}
            />
          </div>
        </div>
      )}

      {/* LIVE LOG */}
      {logs.length > 0 && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-3">
          <div className="flex items-center gap-2 mb-2">
            <Zap className="w-4 h-4 text-yellow-400" />
            <span className="text-sm font-semibold text-slate-300">Log en vivo</span>
          </div>
          <div ref={logRef} className="max-h-48 overflow-y-auto space-y-1 font-mono text-xs">
            {logs.map((log, i) => (
              <div key={i} className={`flex gap-2 ${
                log.level === 'success' ? 'text-emerald-400' :
                log.level === 'warning' ? 'text-amber-400' :
                log.level === 'error' ? 'text-red-400' :
                'text-slate-400'
              }`}>
                <span className="text-slate-600 shrink-0">[{log.timestamp}]</span>
                <span>{log.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* RESULTADOS */}
      {result && (
        <div className="space-y-3">
          {/* Summary cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard label="Hosts" value={result.hosts_found || 0} icon={Shield} color="text-cyan-400" />
            <StatCard label="Puertos abiertos" value={result.ports_open || 0} icon={Activity} color="text-blue-400" />
            <StatCard label="Cámaras" value={result.cameras_identified || 0} icon={Crosshair} color="text-orange-400" />
            <StatCard label="Creds válidas" value={result.credentials_found || 0} icon={AlertTriangle} color="text-red-400" />
          </div>

          {/* Findings table */}
          {result.findings && result.findings.length > 0 && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
              <div className="px-4 py-2 border-b border-slate-800 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <span className="text-sm font-semibold text-slate-300">Hallazgos ({result.findings.length})</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-800">
                      <th className="px-3 py-2 text-left text-xs text-slate-500 font-medium">Host</th>
                      <th className="px-3 py-2 text-left text-xs text-slate-500 font-medium">Puertos</th>
                      <th className="px-3 py-2 text-left text-xs text-slate-500 font-medium">Vendor</th>
                      <th className="px-3 py-2 text-left text-xs text-slate-500 font-medium">Credenciales</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.findings.map((f, i) => (
                      <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                        <td className="px-3 py-2 font-mono text-cyan-400">{f.host}</td>
                        <td className="px-3 py-2 font-mono text-slate-400">{f.ports}</td>
                        <td className="px-3 py-2 text-orange-400">{f.vendor}</td>
                        <td className="px-3 py-2">
                          {f.credentials ? (
                            <span className="text-red-400 font-mono text-xs">{f.credentials}</span>
                          ) : (
                            <CheckCircle className="w-4 h-4 text-emerald-400" />
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Reportes sellados (uno por subred) */}
          {result.reports && result.reports.length > 0 && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-3">
                <FileDown className="w-4 h-4 text-emerald-400" />
                <span className="text-sm font-semibold text-slate-300">Reportes Sellados ({result.reports.length})</span>
              </div>
              <div className="space-y-3">
                {result.reports.map((r, i) => (
                  <div key={i} className="space-y-1">
                    <button
                      onClick={() => downloadReport(r.filename)}
                      className="flex items-center gap-2 px-3 py-2 bg-emerald-600/20 border border-emerald-600/30 rounded-lg text-sm text-emerald-400 hover:bg-emerald-600/30 transition-colors"
                    >
                      <FileDown className="w-4 h-4" />
                      {r.subnet ? `${r.subnet}: ` : ''}Descargar {r.filename}
                    </button>
                    <div className="text-xs text-slate-500">
                      SHA-256: <span className="font-mono text-emerald-400">{r.hash?.substring(0, 32)}...</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Empty state */}
      {!scanning && !result && logs.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-slate-600">
          <Crosshair className="w-16 h-16 mb-4 opacity-20" />
          <p className="text-sm">Configura la subnet y ejecuta la auditoría táctica</p>
          <p className="text-xs text-slate-700 mt-1">El motor descubrirá hosts, escaneará puertos, identificará cámaras, probará credenciales y generará un reporte sellado</p>
        </div>
      )}
    </div>
  )
}

// Stat card component
function StatCard({ label, value, icon: Icon, color }: {
  label: string
  value: number
  icon: React.ComponentType<{ className?: string }>
  color: string
}) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-3">
      <div className="flex items-center gap-2 mb-1">
        <Icon className={`w-3.5 h-3.5 ${color}`} />
        <span className="text-xs text-slate-500">{label}</span>
      </div>
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
    </div>
  )
}
