import { useEffect, useState } from 'react'
import { invoke } from '@tauri-apps/api/tauri'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Upload, RefreshCw } from 'lucide-react'

interface IOC { id: string; type: string; value: string; confidence: number; tags: string[] }

export default function ThreatIntel() {
  const [iocs, setIocs] = useState<IOC[]>([])

  const load = async () => { setIocs(await invoke('get_tip_iocs') as IOC[]) }
  useEffect(() => { load() }, [])

  const confColor = (c: number) => c >= 90 ? 'text-red-400' : c >= 70 ? 'text-yellow-400' : 'text-muted-foreground'

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Threat Intelligence</h2>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => invoke('import_stix').then(load)}>
            <Upload className="h-3 w-3 mr-1" />Import STIX
          </Button>
          <Button size="sm" variant="outline" onClick={load}><RefreshCw className="h-3 w-3" /></Button>
        </div>
      </div>
      <Card>
        <CardHeader><CardTitle>IOC Feed — {iocs.length} indicators</CardTitle></CardHeader>
        <CardContent>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-muted-foreground border-b border-border">
                <th className="text-left py-1 pr-3">Type</th>
                <th className="text-left py-1 pr-3">Value</th>
                <th className="text-left py-1 pr-3">Confidence</th>
                <th className="text-left py-1">Tags</th>
              </tr>
            </thead>
            <tbody>
              {iocs.map(ioc => (
                <tr key={ioc.id} className="border-b border-border/50 hover:bg-muted/30">
                  <td className="py-1.5 pr-3 font-mono">{ioc.type}</td>
                  <td className="py-1.5 pr-3 font-mono">{ioc.value}</td>
                  <td className={`py-1.5 pr-3 font-mono ${confColor(ioc.confidence)}`}>{ioc.confidence}%</td>
                  <td className="py-1.5 flex gap-1 flex-wrap">
                    {ioc.tags.map(t => <Badge key={t} variant="outline">{t}</Badge>)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  )
}
