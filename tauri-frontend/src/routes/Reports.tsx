import { useEffect, useState } from 'react'
import { invoke } from '@tauri-apps/api/tauri'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Download, RefreshCw } from 'lucide-react'

interface ReportMeta { id: string; date: string; findings: number; critical: number }

export default function Reports() {
  const [reports, setReports] = useState<ReportMeta[]>([])
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    const data = await invoke('get_report_list') as ReportMeta[]
    setReports(data)
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Reports</h2>
        <Button size="sm" variant="outline" onClick={load} disabled={loading}>
          <RefreshCw className={`h-3 w-3 mr-1 ${loading ? 'animate-spin' : ''}`} />Refresh
        </Button>
      </div>
      <div className="space-y-2">
        {reports.map(r => (
          <Card key={r.id}>
            <CardContent className="flex items-center justify-between py-3">
              <div>
                <p className="font-mono text-sm">{r.id}</p>
                <p className="text-xs text-muted-foreground">{r.date}</p>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-sm">{r.findings} findings</span>
                {r.critical > 0 && <Badge variant="destructive">{r.critical} critical</Badge>}
                <Button size="sm" variant="ghost" onClick={() => invoke('export_reports', { id: r.id })}>
                  <Download className="h-3 w-3" />
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
        {reports.length === 0 && !loading && (
          <p className="text-muted-foreground text-sm text-center py-8">No reports found.</p>
        )}
      </div>
    </div>
  )
}
