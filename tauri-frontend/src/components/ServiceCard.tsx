import { useState } from 'react'
import { useServiceStore } from '../stores/serviceStore'
import { type Service } from '../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from './ui/card'
import { Button } from './ui/button'
import { Play, Square, RotateCcw, Loader2, CheckCircle2, AlertCircle } from 'lucide-react'

type ServiceStatus = 'running' | 'stopped' | 'error'

const statusColor: Record<ServiceStatus, string> = {
  running: 'text-green-400',
  stopped: 'text-muted-foreground',
  error:   'text-red-400',
}

const statusDot: Record<ServiceStatus, string> = {
  running: 'bg-green-400',
  stopped: 'bg-muted-foreground',
  error:   'bg-red-400',
}

export function ServiceCard({ service }: { service: Service }) {
  const { startService, stopService, restartService } = useServiceStore()
  const status = (service.status as ServiceStatus) ?? 'stopped'

  const [loadingAction, setLoadingAction] = useState<'start' | 'stop' | 'restart' | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const handleAction = async (action: 'start' | 'stop' | 'restart') => {
    setLoadingAction(action)
    setErrorMsg(null)
    setSuccessMsg(null)
    try {
      if (action === 'start') await startService(service.name)
      else if (action === 'stop') await stopService(service.name)
      else if (action === 'restart') await restartService(service.name)

      const label = action === 'start' ? 'iniciado' : action === 'stop' ? 'detenido' : 'reiniciado'
      setSuccessMsg(`Servicio ${label} correctamente`)
      setTimeout(() => setSuccessMsg(null), 3000)
    } catch (err: any) {
      setErrorMsg(err?.message || `Error al ${action} el servicio`)
      setTimeout(() => setErrorMsg(null), 4000)
    } finally {
      setLoadingAction(null)
    }
  }

  const isOperating = loadingAction !== null

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="font-mono text-xs">{service.name}</CardTitle>
          <span className={`flex items-center gap-1 text-xs ${statusColor[status]}`}>
            <span className={`h-2 w-2 rounded-full ${statusDot[status]}`} />
            {service.status}
          </span>
        </div>
      </CardHeader>
      <CardContent>
        {service.pid && (
          <p className="text-xs text-muted-foreground mb-1">
            PID: {service.pid} · up {service.uptime}
          </p>
        )}
        {service.lastLogs && service.lastLogs.length > 0 && (
          <pre className="text-xs bg-muted rounded p-1 mb-2 overflow-hidden max-h-12 truncate text-muted-foreground font-mono">
            {service.lastLogs[service.lastLogs.length - 1]}
          </pre>
        )}
        <div className="flex gap-1 mt-2">
          <Button
            size="sm"
            variant="outline"
            className="h-7 px-2 text-xs"
            disabled={isOperating}
            onClick={() => handleAction('start')}
          >
            {loadingAction === 'start' ? (
              <Loader2 className="h-3 w-3 mr-1 animate-spin text-green-400" />
            ) : (
              <Play className="h-3 w-3 mr-1" />
            )}
            Start
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="h-7 px-2 text-xs"
            disabled={isOperating}
            onClick={() => handleAction('stop')}
          >
            {loadingAction === 'stop' ? (
              <Loader2 className="h-3 w-3 mr-1 animate-spin text-yellow-400" />
            ) : (
              <Square className="h-3 w-3 mr-1" />
            )}
            Stop
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="h-7 px-2 text-xs"
            disabled={isOperating}
            onClick={() => handleAction('restart')}
          >
            {loadingAction === 'restart' ? (
              <Loader2 className="h-3 w-3 mr-1 animate-spin text-blue-400" />
            ) : (
              <RotateCcw className="h-3 w-3 mr-1" />
            )}
            Restart
          </Button>
        </div>

        {successMsg && (
          <p className="text-[11px] text-green-400 mt-2 flex items-center gap-1 bg-green-950/30 border border-green-800/50 rounded px-2 py-0.5">
            <CheckCircle2 className="h-3 w-3 shrink-0" />
            {successMsg}
          </p>
        )}

        {errorMsg && (
          <p className="text-[11px] text-red-400 mt-2 flex items-center gap-1 bg-red-950/30 border border-red-800/50 rounded px-2 py-0.5">
            <AlertCircle className="h-3 w-3 shrink-0" />
            {errorMsg}
          </p>
        )}

        {service.description && (
          <p className="text-xs text-muted-foreground mt-2">{service.description}</p>
        )}
      </CardContent>
    </Card>
  )
}
