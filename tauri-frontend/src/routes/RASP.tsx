import { useEffect, useState } from 'react'
import { invoke } from '@tauri-apps/api/tauri'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { ShieldOff, RefreshCw } from 'lucide-react'

interface Device { id: string; name: string; platform: string; attestation: string; last_seen: string }

export default function RASP() {
  const [devices, setDevices] = useState<Device[]>([])

  const load = async () => { setDevices(await invoke('get_rasp_devices') as Device[]) }
  useEffect(() => { load() }, [])

  const revoke = async (id: string) => { await invoke('revoke_device', { id }); load() }

  const attColor = (a: string) => a === 'passed' ? 'default' : 'destructive' as const

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">RASP — Device Attestation</h2>
        <Button size="sm" variant="outline" onClick={load}><RefreshCw className="h-3 w-3" /></Button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {devices.map(d => (
          <Card key={d.id}>
            <CardHeader>
              <div className="flex justify-between items-start">
                <CardTitle>{d.name}</CardTitle>
                <Badge variant={attColor(d.attestation)}>{d.attestation}</Badge>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground">Platform: {d.platform}</p>
              <p className="text-xs text-muted-foreground">Last seen: {d.last_seen}</p>
              {d.attestation !== 'passed' && (
                <Button size="sm" variant="destructive" className="mt-2 w-full" onClick={() => revoke(d.id)}>
                  <ShieldOff className="h-3 w-3 mr-1" />Revoke
                </Button>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
