import { useEffect, useState } from 'react'
import { api, type SoarDag } from '../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Button } from '../components/ui/button'
import { Badge } from '../components/ui/badge'
import { Play, RefreshCw, Plus, ToggleLeft, ToggleRight, Zap } from 'lucide-react'

export default function SOAR() {
  const [dags, setDags]           = useState<SoarDag[]>([])
  const [dryResult, setDryResult] = useState<string[] | null>(null)
  const [loading, setLoading]     = useState(false)
  const [adding, setAdding]       = useState(false)
  const [form, setForm]           = useState({ name: '', description: '', trigger: 'schedule', interval_mins: 30, steps: '' })
  const [msg, setMsg]             = useState('')

  const load = async () => {
    setLoading(true)
    try { setDags(await api.getDags()) } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const dryRun = async () => {
    const r = await api.dryRun()
    setDryResult(r.steps)
    setMsg(`Dry run: ${r.count} pasos evaluados`)
    setTimeout(() => setMsg(''), 5000)
  }

  const saveDag = async () => {
    if (!form.name.trim()) return
    await api.saveDag({
      name: form.name, description: form.description,
      trigger: form.trigger as SoarDag['trigger'],
      interval_mins: form.interval_mins,
      steps: form.steps.split('\n').map(s => s.trim()).filter(Boolean),
      enabled: true,
    })
    setForm({ name: '', description: '', trigger: 'schedule', interval_mins: 30, steps: '' })
    setAdding(false)
    load()
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-xl font-bold">SOAR Engine</h2>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={dryRun}>
            <Zap className="h-3 w-3 mr-1" />Dry Run
          </Button>
          <Button size="sm" variant="outline" onClick={() => setAdding(!adding)}>
            <Plus className="h-3 w-3 mr-1" />Nuevo DAG
          </Button>
          <Button size="sm" variant="outline" onClick={load} disabled={loading}>
            <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {msg && <div className="text-sm text-green-400 bg-green-900/20 border border-green-800 rounded px-3 py-2">{msg}</div>}

      {dryResult && dryResult.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Play className="h-4 w-4 text-green-400" />Evaluación — {dryResult.length} pasos</CardTitle></CardHeader>
          <CardContent>
            <ol className="space-y-1">
              {dryResult.map((step, i) => (
                <li key={i} className="font-mono text-xs text-green-300 flex gap-2">
                  <span className="text-gray-500 w-4 shrink-0">{i + 1}.</span>
                  {step}
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      )}

      {adding && (
        <Card>
          <CardHeader><CardTitle>Nuevo DAG Playbook</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <input className="w-full bg-muted border border-border rounded px-2 py-1.5 text-sm"
              placeholder="Nombre del DAG" value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            <input className="w-full bg-muted border border-border rounded px-2 py-1.5 text-sm"
              placeholder="Descripción" value={form.description}
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
            <div className="flex gap-3">
              <select className="bg-muted border border-border rounded px-2 py-1.5 text-sm"
                value={form.trigger} onChange={e => setForm(f => ({ ...f, trigger: e.target.value }))}>
                <option value="schedule">Programado</option>
                <option value="manual">Manual</option>
              </select>
              {form.trigger === 'schedule' && (
                <input type="number" className="bg-muted border border-border rounded px-2 py-1.5 text-sm w-32"
                  placeholder="Intervalo (min)" value={form.interval_mins}
                  onChange={e => setForm(f => ({ ...f, interval_mins: +e.target.value }))} />
              )}
            </div>
            <textarea className="w-full bg-muted border border-border rounded px-2 py-1.5 text-sm font-mono h-24 resize-none"
              placeholder="Pasos (uno por línea)&#10;fetch_alerts&#10;correlate_iocs&#10;notify_slack"
              value={form.steps} onChange={e => setForm(f => ({ ...f, steps: e.target.value }))} />
            <div className="flex gap-2">
              <Button size="sm" onClick={saveDag}>Guardar DAG</Button>
              <Button size="sm" variant="ghost" onClick={() => setAdding(false)}>Cancelar</Button>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="space-y-2">
        {dags.map(dag => (
          <Card key={dag.id}>
            <CardContent className="py-3">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    {dag.enabled
                      ? <ToggleRight className="h-4 w-4 text-green-400" />
                      : <ToggleLeft  className="h-4 w-4 text-gray-400" />}
                    <span className="font-semibold text-sm">{dag.name}</span>
                    <Badge variant={dag.trigger === 'schedule' ? 'default' : 'outline'} className="text-[10px]">
                      {dag.trigger === 'schedule' ? `⏱ cada ${dag.interval_mins}m` : '▶ manual'}
                    </Badge>
                    {!dag.enabled && <Badge variant="secondary" className="text-[10px]">desactivado</Badge>}
                  </div>
                  {dag.description && <p className="text-xs text-muted-foreground">{dag.description}</p>}
                  <div className="flex gap-1 mt-2 flex-wrap">
                    {dag.steps.map((step, i) => (
                      <span key={i} className="text-[10px] bg-muted border border-border rounded px-1.5 py-0.5 font-mono">{step}</span>
                    ))}
                  </div>
                </div>
                {dag.last_run && (
                  <p className="text-[10px] text-muted-foreground shrink-0">
                    último: {new Date(dag.last_run).toLocaleString()}
                  </p>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
        {dags.length === 0 && !loading && (
          <p className="text-muted-foreground text-sm text-center py-8">Sin DAGs. Crea el primero para automatizar respuestas.</p>
        )}
      </div>
    </div>
  )
}
