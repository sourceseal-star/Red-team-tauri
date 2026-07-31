import { useEffect, useState } from 'react'
import { invoke } from '@tauri-apps/api/tauri'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Badge } from '../components/ui/badge'
import { RotateCcw, Power } from 'lucide-react'

interface HoneypotStatus { active: boolean; tokens_deployed: number; triggers_today: number }

export default function Honeypot() {
  const [status, setStatus] = useState<HoneypotStatus | null>(null)

  const load = async () => {
    const s = await invoke('get_honeypot_status') as HoneypotStatus
    setStatus(s)
  }

  useEffect(() => { load() }, [])

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">Deception / Honeypot</h2>
      {status && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <Card>
            <CardHeader><CardTitle>Status</CardTitle></CardHeader>
            <CardContent>
              <Badge variant={status.active ? 'default' : 'secondary'}>
                {status.active ? '● Active' : '○ Inactive'}
              </Badge>
              <Button size="sm" variant="outline" className="mt-3 w-full" onClick={() => invoke('toggle_honeypot').then(load)}>
                <Power className="h-3 w-3 mr-1" />{status.active ? 'Deactivate' : 'Activate'}
              </Button>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Tokens Deployed</CardTitle></CardHeader>
            <CardContent>
              <p className="text-3xl font-bold font-mono">{status.tokens_deployed}</p>
              <Button size="sm" variant="outline" className="mt-3 w-full" onClick={() => invoke('rotate_tokens').then(load)}>
                <RotateCcw className="h-3 w-3 mr-1" />Rotate Tokens
              </Button>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Triggers Today</CardTitle></CardHeader>
            <CardContent>
              <p className={`text-3xl font-bold font-mono ${status.triggers_today > 0 ? 'text-red-400' : 'text-green-400'}`}>
                {status.triggers_today}
              </p>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
