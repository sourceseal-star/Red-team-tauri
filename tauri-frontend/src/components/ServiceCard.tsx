import { invoke } from '@tauri-apps/api/tauri'
import { useServiceStore, type Service } from '../stores/serviceStore'
import { Card, CardContent, CardHeader, CardTitle } from './ui/card'
import { Button } from './ui/button'
import { Badge } from './ui/badge'
import { Play, Square, RotateCcw } from 'lucide-react'

const statusColor = {
  running: 'text-green-400',
  stopped: 'text-muted-foreground',
  error: 'text-red-400',
}

const statusDot = {
  running: 'bg-green-400',
  stopped: 'bg-muted-foreground',
  error: 'bg-red-400',
}

export function ServiceCard({ service }: { service: Service }) {
  const { startService, stopService, restartService } = useServiceStore()

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="font-mono text-xs">{service.name}</CardTitle>
          <span className={`flex items-center gap-1 text-xs ${statusColor[service.status]}`}>
            <span className={`h-2 w-2 rounded-full ${statusDot[service.status]}`} />
            {service.status}
          </span>
        </div>
      </CardHeader>
      <CardContent>
        {service.pid && <p className="text-xs text-muted-foreground mb-1">PID: {service.pid} · up {service.uptime}</p>}
        {service.lastLogs.length > 0 && (
          <pre className="text-xs bg-muted rounded p-1 mb-2 overflow-hidden max-h-12 truncate text-muted-foreground">
            {service.lastLogs[service.lastLogs.length - 1]}
          </pre>
        )}
        <div className="flex gap-1 mt-2">
          <Button size="sm" variant="outline" onClick={() => startService(service.name)}><Play className="h-3 w-3" /></Button>
          <Button size="sm" variant="outline" onClick={() => stopService(service.name)}><Square className="h-3 w-3" /></Button>
          <Button size="sm" variant="outline" onClick={() => restartService(service.name)}><RotateCcw className="h-3 w-3" /></Button>
        </div>
      </CardContent>
    </Card>
  )
}
