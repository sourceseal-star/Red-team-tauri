import { useEffect, useState } from 'react'
import { api, type IOC } from '../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { RefreshCw, Plus, Trash2, Upload, Download } from 'lucide-react'

const TYPE_COLOR: Record<string, string> = {
  domain: 'text-purple-400', ip: 'text-blue-400',
  hash:   'text-yellow-400', url: 'text-orange-400', stix: 'text-gray-400',
}

export default function ThreatIntel() {
  const [iocs, setIocs]       = useState<IOC[]>([])
  const [loading, setLoading] = useState(false)
  const [updating, setUpdating] = useState(false)
  const [adding, setAdding]   = useState(false)
  const [form, setForm]       = useState({ type: 'domain', value: '', confidence: 80, tags: '' })
  const [msg, setMsg]         = useState('')

  const load = async () => {
    setLoading(true)
    try { setIocs(await api.getIocs()) } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const updateFromFeeds = async () => {
    setUpdating(true)
    setMsg('Descargando IOCs de feeds...')
    try {
      const r = await api.updateFromFeeds()
      setMsg(`✓ ${r.iocs_loaded} IOCs cargados de feeds reales`)
      setTimeout(() => setMsg(''), 5000)
      load()
    } catch {
      setMsg('Error conectando a feeds')
      setTimeout(() => setMsg(''), 3000)
    } finally {
      setUpdating(false)
    }
  }

  const addIoc = async () => {
    if (!form.value.trim()) return
    await api.addIoc({
      type: form.type, value: form.value.trim(),
      confidence: form.confidence,
      tags: form.tags.split(',').map(t => t.trim()).filter(Boolean),
    })
    setForm({ type: 'domain', value: '', confidence: 80, tags: '' })
    setAdding(false)
    load()
  }

  const deleteIoc = async (id: string) => {
    await api.deleteIoc(id)
    load()
  }

  const importStix = async () => {
    const bundle = {
      type: 'bundle', id: `bundle--${crypto.randomUUID()}`,
      objects: [
        { type: 'indicator', id: `indicator--${crypto.randomUUID()}`,
          pattern: "[domain-name:value = 'malware-c2-demo.example.com']",
          confidence: 88, labels: ['malicious-activity'] },
        { type: 'indicator', id: `indicator--${crypto.randomUUID()}`,
          pattern: "[ipv4-addr:value = '203.0.113.99']",
          confidence: 72, labels: ['scanner'] },
      ]
    }
    const r = await api.importStix(bundle)
    setMsg(`✓ Importados ${r.imported} indicadores STIX2`)
    setTimeout(() => setMsg(''), 4000)
    load()
  }

  const confColor = (c: number) =>
    c >= 90 ? 'text-red-400' : c >= 70 ? 'text-yellow-400' : 'text-gray-400'

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-xl font-bold">Threat Intelligence</h2>
        <div className="flex gap-2">
          <Button size="sm" variant="default" onClick={updateFromFeeds} disabled={updating}>
            <Download className={`h-3 w-3 mr-1 ${updating ? 'animate-spin' : ''}`} />
            {updating ? 'Actualizando...' : 'Feeds reales'}
          </Button>
          <Button size="sm" variant="outline" onClick={importStix}><Upload className="h-3 w-3 mr-1" />STIX2</Button>
          <Button size="sm" variant="outline" onClick={() => setAdding(!adding)}><Plus className="h-3 w-3 mr-1" />IOC</Button>
          <Button size="sm" variant="outline" onClick={load} disabled={loading}><RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} /></Button>
        </div>
      </div>

      {msg && <div className="text-sm text-green-400 bg-green-900/20 border border-green-800 rounded px-3 py-2">{msg}</div>}

      {adding && (
        <Card>
          <CardHeader><CardTitle>Nuevo IOC</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <select className="bg-muted border border-border rounded px-2 py-1.5 text-sm" value={form.type}
                onChange={e => setForm(f => ({ ...f, type: e.target.value }))}>
                {['domain','ip','hash','url','email'].map(t => <option key={t} value={t}>{t}</option>)}
              </select>
              <input className="bg-muted border border-border rounded px-2 py-1.5 text-sm font-mono"
                placeholder="Valor del indicador"
                value={form.value} onChange={e => setForm(f => ({ ...f, value: e.target.value }))} />
            </div>
            <div className="flex gap-3 items-center">
              <label className="text-xs text-muted-foreground">Confianza: {form.confidence}%</label>
              <input type="range" min="0" max="100" value={form.confidence}
                onChange={e => setForm(f => ({ ...f, confidence: +e.target.value }))} className="flex-1" />
            </div>
            <input className="w-full bg-muted border border-border rounded px-2 py-1.5 text-sm"
              placeholder="Tags (separados por coma)"
              value={form.tags} onChange={e => setForm(f => ({ ...f, tags: e.target.value }))} />
            <div className="flex gap-2">
              <Button size="sm" onClick={addIoc}>Guardar</Button>
              <Button size="sm" variant="ghost" onClick={() => setAdding(false)}>Cancelar</Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle>IOC Feed — {iocs.length} indicadores</CardTitle></CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-muted-foreground border-b border-border text-left">
                  <th className="px-4 py-2">Tipo</th>
                  <th className="px-4 py-2">Valor</th>
                  <th className="px-4 py-2">Confianza</th>
                  <th className="px-4 py-2">Tags</th>
                  <th className="px-4 py-2">Añadido</th>
                  <th className="px-4 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {iocs.map(ioc => (
                  <tr key={ioc.id} className="border-b border-border/40 hover:bg-muted/20">
                    <td className={`px-4 py-2 font-mono font-bold ${TYPE_COLOR[ioc.type] ?? 'text-gray-300'}`}>{ioc.type}</td>
                    <td className="px-4 py-2 font-mono max-w-[200px] truncate">{ioc.value}</td>
                    <td className={`px-4 py-2 font-mono ${confColor(ioc.confidence)}`}>{ioc.confidence}%</td>
                    <td className="px-4 py-2">
                      <div className="flex gap-1 flex-wrap">
                        {ioc.tags.map(t => <Badge key={t} variant="outline" className="text-[10px]">{t}</Badge>)}
                      </div>
                    </td>
                    <td className="px-4 py-2 text-muted-foreground">
                      {ioc.added ? new Date(ioc.added).toLocaleDateString() : '—'}
                    </td>
                    <td className="px-4 py-2">
                      <Button size="sm" variant="ghost" onClick={() => deleteIoc(ioc.id)}>
                        <Trash2 className="h-3 w-3 text-red-400" />
                      </Button>
                    </td>
                  </tr>
                ))}
                {iocs.length === 0 && (
                  <tr><td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                    Sin indicadores. Presiona "Feeds reales" para descargar IOCs de AlienVault, abuse.ch, Tor e IPsum.
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
