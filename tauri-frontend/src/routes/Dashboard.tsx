import { useEffect, useState } from 'react'
import { useServiceStore } from '../stores/serviceStore'
import { ServiceCard } from '../components/ServiceCard'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Progress } from '../components/ui/progress'
import { useResourceStore } from '../stores/resourceStore'
import { NetworkScanner } from '../components/NetworkScanner'
import { CanarySVG } from '../components/CanarySVG'
import { Server, Activity, AlertTriangle, Cpu, HardDrive } from 'lucide-react'

export default function Dashboard() {
  const { services, loading: servicesLoading, fetchStatus } = useServiceStore()
  const { cpu, memory, fetchResources } = useResourceStore()
  const [initialLoading, setInitialLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const [backendOk, setBackendOk] = useState<boolean | null>(null)

  const loadData = async () => {
    try {
      await Promise.all([fetchStatus(), fetchResources()])
      setBackendOk(true)
      setLastUpdated(new Date())
    } catch {
      setBackendOk(false)
    } finally {
      setInitialLoading(false)
    }
  }

  useEffect(() => {
    loadData()
    const id = setInterval(loadData, 10000)
    return () => clearInterval(id)
  }, [])

  const running = services.filter(s => s.status === 'running').length
  const errored = services.filter(s => s.status === 'error').length
  const memPct = memory.total > 0 ? (memory.used / memory.total) * 100 : 0
  const hasServiceData = services.length > 0
  const hasResourceData = cpu > 0 || memory.total > 0

  return (
    <div className="space-y-6">
      {/* Header with status bar and timestamp */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-bold">Dashboard</h2>
          {hasServiceData && (
            <span className="text-xs px-2.5 py-1 rounded-full bg-muted border border-border font-medium flex items-center gap-1.5">
              <Server className="h-3 w-3 text-blue-400" />
              <span className="font-bold text-foreground">{services.length}</span> {services.length === 1 ? 'servicio' : 'servicios registrados'}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3 text-xs">
          {/* Status bar showing connection status to backend */}
          <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded border font-medium ${
            backendOk === null
              ? 'bg-muted text-muted-foreground border-border'
              : backendOk
              ? 'bg-green-950/30 text-green-400 border-green-800/50'
              : 'bg-red-950/30 text-red-400 border-red-800/50'
          }`}>
            <span className={`h-2 w-2 rounded-full ${
              backendOk === null ? 'bg-muted-foreground' : backendOk ? 'bg-green-400' : 'bg-red-400 animate-pulse'
            }`} />
            <span>{backendOk === null ? 'Conectando...' : backendOk ? 'Backend Conectado' : 'Sin Conexión'}</span>
          </div>

          {/* Last updated timestamp */}
          {lastUpdated && (
            <span className="text-muted-foreground">
              Última actualización: <span className="font-mono text-foreground">{lastUpdated.toLocaleTimeString()}</span>
            </span>
          )}
        </div>
      </div>

      {/* Stats row */}
      {initialLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[1, 2, 3, 4].map(i => (
            <Card key={i} className="animate-pulse">
              <CardHeader className="pb-2">
                <div className="h-4 bg-muted rounded w-24" />
              </CardHeader>
              <CardContent>
                <div className="h-8 bg-muted rounded w-16 mb-2" />
                <div className="h-2 bg-muted rounded w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
                <Activity className="h-3.5 w-3.5 text-green-400" />
                Services Running
              </CardTitle>
            </CardHeader>
            <CardContent>
              {hasServiceData ? (
                <div>
                  <p className="text-2xl font-bold text-green-400 font-mono">
                    {running} <span className="text-xs text-muted-foreground font-normal">/ {services.length}</span>
                  </p>
                  <p className="text-[11px] text-muted-foreground mt-1">
                    {services.length - running} detenidos
                  </p>
                </div>
              ) : (
                <p className="text-2xl font-bold text-muted-foreground font-mono">N/A</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
                <AlertTriangle className="h-3.5 w-3.5 text-red-400" />
                Errors
              </CardTitle>
            </CardHeader>
            <CardContent>
              {hasServiceData ? (
                <p className={`text-2xl font-bold font-mono ${errored > 0 ? 'text-red-400' : 'text-foreground'}`}>
                  {errored}
                </p>
              ) : (
                <p className="text-2xl font-bold text-muted-foreground font-mono">N/A</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
                <Cpu className="h-3.5 w-3.5 text-blue-400" />
                CPU
              </CardTitle>
            </CardHeader>
            <CardContent>
              {backendOk && (cpu > 0 || hasResourceData) ? (
                <>
                  <p className="text-2xl font-bold font-mono">{cpu.toFixed(1)}%</p>
                  <Progress value={cpu} className="mt-2" />
                </>
              ) : (
                <p className="text-2xl font-bold text-muted-foreground font-mono">N/A</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
                <HardDrive className="h-3.5 w-3.5 text-purple-400" />
                RAM
              </CardTitle>
            </CardHeader>
            <CardContent>
              {backendOk && memory.total > 0 ? (
                <>
                  <p className="text-2xl font-bold font-mono">{(memory.used / 1024 / 1024).toFixed(0)} MB</p>
                  <Progress value={memPct} className="mt-2" />
                </>
              ) : (
                <p className="text-2xl font-bold text-muted-foreground font-mono">N/A</p>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Service cards */}
      {initialLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {[1, 2, 3].map(i => (
            <Card key={i} className="animate-pulse h-36 bg-muted/40 border border-border" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {services.map(service => (
            <ServiceCard key={service.name} service={service} />
          ))}
          {services.length === 0 && (
            <div className="col-span-full py-8 text-center text-muted-foreground text-sm bg-card border border-border rounded-lg">
              No se encontraron servicios configurados.
            </div>
          )}
        </div>
      )}

      {/* ── Escaneo de red CCTV ────────────────────────────────────────── */}
      <div>
        <h3 className="text-sm font-semibold mb-2">Escaneo de red - Camaras IP / CCTV</h3>
        <NetworkScanner />
      </div>

      {/* ── SVG Canary Tokens ───────────────────────────────────────────── */}
      <div>
        <h3 className="text-sm font-semibold mb-2">SVG Canary - Tokens Camuflados</h3>
        <CanarySVG />
      </div>
    </div>
  )
}
