import { useEffect, useState } from 'react'
import { invoke } from '@tauri-apps/api/tauri'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Save } from 'lucide-react'

interface Settings { api_url: string; interval: number }

export default function Settings() {
  const [s, setS] = useState<Settings>({ api_url: '', interval: 15 })
  const [saved, setSaved] = useState(false)

  useEffect(() => { invoke('get_settings').then(d => setS(d as Settings)) }, [])

  const save = async () => { await invoke('save_settings', { settings: s }); setSaved(true) }

  return (
    <div className="space-y-4 max-w-lg">
      <h2 className="text-xl font-bold">Settings</h2>
      <Card>
        <CardHeader><CardTitle>Backend</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div>
            <label className="text-xs text-muted-foreground block mb-1">API URL</label>
            <input
              className="w-full bg-muted border border-border rounded-md px-3 py-2 text-sm font-mono outline-none focus:ring-1 focus:ring-blue-500"
              value={s.api_url}
              onChange={e => { setS({ ...s, api_url: e.target.value }); setSaved(false) }}
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground block mb-1">Polling Interval (s)</label>
            <input
              type="number"
              className="w-full bg-muted border border-border rounded-md px-3 py-2 text-sm font-mono outline-none focus:ring-1 focus:ring-blue-500"
              value={s.interval}
              onChange={e => { setS({ ...s, interval: parseInt(e.target.value) }); setSaved(false) }}
            />
          </div>
          <Button onClick={save}><Save className="h-3 w-3 mr-1" />{saved ? 'Saved!' : 'Save'}</Button>
        </CardContent>
      </Card>
    </div>
  )
}
