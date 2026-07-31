import { useEffect, useState } from 'react'
import { invoke } from '@tauri-apps/api/tauri'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Play, Save } from 'lucide-react'

export default function SOAR() {
  const [dags, setDags] = useState<string[]>([])
  const [dryRunResult, setDryRunResult] = useState<string | null>(null)

  useEffect(() => { invoke('get_soar_dags').then(d => setDags(d as string[])) }, [])

  const dryRun = async () => {
    const r = await invoke('dry_run_soar') as { ok: boolean; steps: string[] }
    setDryRunResult(r.ok ? `OK — ${r.steps.length} steps` : 'Error')
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">SOAR Engine</h2>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={dryRun}><Play className="h-3 w-3 mr-1" />Dry Run</Button>
        </div>
      </div>
      {dryRunResult && (
        <Card>
          <CardContent className="py-3">
            <p className="font-mono text-sm text-green-400">{dryRunResult}</p>
          </CardContent>
        </Card>
      )}
      <Card>
        <CardHeader><CardTitle>DAG Playbooks</CardTitle></CardHeader>
        <CardContent>
          {dags.length === 0
            ? <p className="text-muted-foreground text-sm">No DAGs loaded. Import a playbook to get started.</p>
            : dags.map((d, i) => <p key={i} className="font-mono text-xs py-1">{d}</p>)
          }
        </CardContent>
      </Card>
    </div>
  )
}
