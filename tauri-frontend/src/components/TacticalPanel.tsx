import { useState, useEffect, useRef, useCallback } from 'react'
import { Crosshair, Play, FileDown, RefreshCw, Shield, AlertTriangle, CheckCircle, Loader2, Zap } from 'lucide-react'

// ==========================================
// TACTICAL PANEL — Auditoría táctica integral
// ==========================================

interface ScanResult {
  status: string
  target?: string
  hosts_found?: number
  ports_scanned?: number
  cameras_identified?: number
  credentials_tested?: number
  credentials_found?: number
  cves_found?: number
  report_id?: string
  report_sha256?: string
  report_files?: string[]
  error?: string
  findings?: Array<{
    host: string
    port: number
    service: string
    vendor: string
    credentials: string
    cves: string[]
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
  const [result, setResult] = useState<ScanResult | null>(null)
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
      .then(r => r.json())
      .then(data => setCredentials(data.counts || data))
      .catch(() => {})

    fetch('/api/tactical/ports')
      .then(r => r.json())
      .then(data => setPorts(data.ports || data))
      .catch(() => {})
  }, [])

  // Ejecutar scan con WebSocket para progreso en vivo
  const runScan = async () => {
    setScanning(true)
    setResult(null)
    setLogs([])
    addLog('🚀 Iniciando auditoría táctica...', 'info')
    addLog(`📡 Subnet: ${subnet || 'auto-detectar'}`, 'info')

    try {
      // Lanzar scan con POST
      const resp = await fetch('/api/tactical/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(subnet ? { subnet } : {})
      })

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: 'Error desconocido' }))
        addLog(`❌ Error: ${err.detail}`, 'error')
        setScanning(false)
        return
      }

      const data: ScanResult = await resp.json()
      setResult(data)

      if (data.status === 'completed' || data.status === 'success') {
        addLog(`✅ Auditoría completada`, 'success')
        if (data.hosts_found) addLog(`📦 Hosts encontrados: ${data.hosts_found}`, 'info')
        if (data.ports_scanned) addLog(`🔌 Puertos escaneados: ${data.ports_scanned}`, 'info')
        if (data.cameras_identified) addLog(`📷 Cámaras identificadas: ${data.cameras_identified}`, 'info')
        if (data.credentials_tested) addLog(`🔑 Credenciales probadas: ${data.credentials_tested}`, 'info')
        if (data.credentials_found) addLog(`⚠️ Credenciales encontradas: ${data.credentials_found}`, 'warning')
        if (data.cves_found) addLog(`🛡️ CVEs encontrados: ${data.cves_found}`, 'warning')
        if (data.report_id) addLog(`📄 Reporte: ${data.report_id}`, 'success')
        if (data.report_sha256) addLog(`🔐 Sello SHA-256: ${data.report_sha256.substring(0, 16)}...`, 'success')
      } else if (data.error) {
        addLog(`❌ ${data.error}`, 'error')
      }
    } catch (err) {
      addLog(`❌ Error de conexión: ${err}`, 'error')
    } finally {
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
            <label className="text-xs text-slate-400 mb-1 block">Subnet / CIDR (vacío = auto-detectar)</label>
            <input
              type="text"
              value={subnet}
              onChange={e => setSubnet(e.target.value)}
              placeholder="192.168.1.0/24"
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
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            <StatCard label="Hosts" value={result.hosts_found || 0} icon={Shield} color="text-cyan-400" />
            <StatCard label="Puertos" value={result.ports_scanned || 0} icon={Activity} color="text-blue-400" />
            <StatCard label="Cámaras" value={result.cameras_identified || 0} icon={Crosshair} color="text-orange-400" />
            <StatCard label="Creds Probadas" value={result.credentials_tested || 0} icon={Shield} color="text-slate-400" />
            <StatCard label="Creds Encontradas" value={result.credentials_found || 0} icon={AlertTriangle} color="text-red-400" />
            <StatCard label="CVEs" value={result.cves_found || 0} icon={AlertTriangle} color="text-red-400" />
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
                      <th className="px-3 py-2 text-left text-xs text-slate-500 font-medium">Port</th>
                      <th className="px-3 py-2 text-left text-xs text-slate-500 font-medium">Servicio</th>
                      <th className="px-3 py-2 text-left text-xs text-slate-500 font-medium">Vendor</th>
                      <th className="px-3 py-2 text-left text-xs text-slate-500 font-medium">Credenciales</th>
                      <th className="px-3 py-2 text-left text-xs text-slate-500 font-medium">CVEs</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.findings.map((f, i) => (
                      <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                        <td className="px-3 py-2 font-mono text-cyan-400">{f.host}</td>
                        <td className="px-3 py-2 font-mono text-slate-400">{f.port}</td>
                        <td className="px-3 py-2 text-slate-300">{f.service}</td>
                        <td className="px-3 py-2 text-orange-400">{f.vendor}</td>
                        <td className="px-3 py-2">
                          {f.credentials ? (
                            <span className="text-red-400 font-mono text-xs">{f.credentials}</span>
                          ) : (
                            <CheckCircle className="w-4 h-4 text-emerald-400" />
                          )}
                        </td>
                        <td className="px-3 py-2">
                          {f.cves?.length > 0 ? (
                            <span className="text-amber-400 font-mono text-xs">{f.cves.join(', ')}</span>
                          ) : (
                            <span className="text-slate-600 text-xs">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Reporte sellado */}
          {result.report_files && result.report_files.length > 0 && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-3">
                <FileDown className="w-4 h-4 text-emerald-400" />
                <span className="text-sm font-semibold text-slate-300">Reporte Sellado</span>
              </div>
              <div className="space-y-2">
                {result.report_id && (
                  <div className="text-xs text-slate-500">
                    Report ID: <span className="font-mono text-slate-300">{result.report_id}</span>
                  </div>
                )}
                {result.report_sha256 && (
                  <div className="text-xs text-slate-500">
                    SHA-256: <span className="font-mono text-emerald-400">{result.report_sha256}</span>
                  </div>
                )}
                {result.report_files.map((file, i) => (
                  <button
                    key={i}
                    onClick={() => downloadReport(file.split('/').pop() || file)}
                    className="flex items-center gap-2 px-3 py-2 bg-emerald-600/20 border border-emerald-600/30 rounded-lg text-sm text-emerald-400 hover:bg-emerald-600/30 transition-colors"
                  >
                    <FileDown className="w-4 h-4" />
                    Descargar {file.split('/').pop()}
                  </button>
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
