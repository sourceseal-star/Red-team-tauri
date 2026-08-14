import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Badge } from '../components/ui/badge'
import { Shield } from 'lucide-react'

export default function About() {
  return (
    <div className="space-y-4 max-w-xl">
      <h2 className="text-xl font-bold">About</h2>
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <Shield className="h-8 w-8 text-blue-400" />
            <div>
              <CardTitle className="text-base">SourceSeal Console</CardTitle>
              <p className="text-xs text-muted-foreground">v0.1.0 — Tauri 2 + React</p>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <p className="text-muted-foreground">
            Centro de control para el Red Team Toolkit de SourceSeal. Gestiona servicios,
            visualiza reportes de auditoría, controla el motor SOAR, TIP, NDR, RASP y más.
          </p>
          <div className="flex flex-wrap gap-2">
            {['XDR', 'RASP', 'NDR', 'SOAR', 'TIP', 'Deception', 'ZTNA'].map(m => (
              <Badge key={m} variant="outline">{m}</Badge>
            ))}
          </div>
          <p className="text-xs text-muted-foreground border-t border-border pt-3">
            ⚠️ Solo para auditoría de infraestructura sobre la que tengas autorización escrita.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
