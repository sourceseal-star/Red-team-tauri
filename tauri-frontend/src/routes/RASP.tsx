import { useEffect, useState } from 'react'
import { api, type Device } from '../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { ShieldOff, RefreshCw, Plus, Smartphone, CheckCircle2, XCircle, Clock } from 'lucide-react'

const ATT_ICON = {
  passed:  <CheckCircle2 className="h-4 w-4 text-green-400" />,
  failed:  <XCircle      className="h-4 w-4 text-red-400" />,
  revoked: <ShieldOff    className="h-4 w-4 text-gray-400" />,
  pending: <Clock        className="h-4 w-4 text-yellow-400" />,
}
const ATT_BADGE: Record<string, 'default' | 'destructive' | 'secondary' | 'outline'> = {
  passed: 'default', failed: 'destructive', revoked: 'secondary', pending: 'outline',
}

export default function RASP() {
  const [devices, setDevices] = useState<Device[]>([])
  const [loading, setLoading] = useState(false)
  const [adding, setAdding]   = useState(false)
  const [form, setForm]       = useState({ name: '', platform: 'android' })
  const [msg, setMsg]         = useState('')

  const load = async () => {
    setLoading(true)
    try { setDevices(await api.getDevices()) } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const revoke = async (id: string) => {
    await api.revokeDevice(id)
    setMsg('Dispositivo revocado')
    setTimeout(() => setMsg(''), 3000)
    load()
  }

  const enroll = async () => {
    if (!form.name.trim()) return
    await api.enrollDevice({ name: form.name, platform: form.platform })
    setForm({ name: '', platform: 'android' })
    setAdding(false)
    load()
  }

  const passed  = devices.filter(d => d.attestation === 'passed').length
  const failed  = devices.filter(d => d.attestation === 'failed').length
  const revoked = devices.filter(d => d.attestation === 'revoked').length

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-xl font-bold">RASP — Device Attestation</h2>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => setAdding(!adding)}><Plus className="h-3 w-3 mr-1" />Enroll</Button>
          <Button size="sm" variant="outline" onClick={load} disabled={loading}><RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} /></Button>
        </div>
      </div>

      {msg && <div className="text-sm text-yellow-400 bg-yellow-900/20 border border-yellow-800 rounded px-3 py-2">{msg}</div>}

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3">
        <Card><CardContent className="py-3 text-center">
          <p className="text-2xl font-bold text-green-400">{passed}</p>
          <p className="text-xs text-muted-foreground">Atestiguados</p>
        </CardContent></Card>
        <Card><CardContent className="py-3 text-center">
          <p className="text-2xl font-bold text-red-400">{failed}</p>
          <p className="text-xs text-muted-foreground">Fallidos</p>
        </CardContent></Card>
        <Card><CardContent className="py-3 text-center">
          <p className="text-2xl font-bold text-gray-400">{revoked}</p>
          <p className="text-xs text-muted-foreground">Revocados</p>
        </CardContent></Card>
      </div>

      {adding && (
        <Card>
          <CardHeader><CardTitle>Enroll nuevo dispositivo</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <input className="w-full bg-muted border border-border rounded px-2 py-1.5 text-sm"
              placeholder="Nombre del dispositivo"
              value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            <select className="w-full bg-muted border border-border rounded px-2 py-1.5 text-sm"
              value={form.platform} onChange={e => setForm(f => ({ ...f, platform: e.target.value }))}>
              <option value="android">Android</option>
              <option value="ios">iOS</option>
            </select>
            <div className="flex gap-2">
              <Button size="sm" onClick={enroll}>Enroll</Button>
              <Button size="sm" variant="ghost" onClick={() => setAdding(false)}>Cancelar</Button>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {devices.map(d => (
          <Card key={d.id} className={d.attestation === 'revoked' ? 'opacity-60' : ''}>
            <CardHeader>
              <div className="flex justify-between items-start">
                <div className="flex items-center gap-2">
                  <Smartphone className="h-4 w-4 text-muted-foreground" />
                  <CardTitle className="text-sm">{d.name}</CardTitle>
                </div>
                <Badge variant={ATT_BADGE[d.attestation] ?? 'outline'} className="flex items-center gap-1">
                  {ATT_ICON[d.attestation as keyof typeof ATT_ICON]}
                  {d.attestation}
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground">Plataforma: <span className="text-foreground capitalize">{d.platform}</span></p>
              <p className="text-xs text-muted-foreground">Último visto: <span className="text-foreground">{d.last_seen}</span></p>
              {d.revoked_at && <p className="text-xs text-red-400 mt-1">Revocado: {new Date(d.revoked_at).toLocaleString()}</p>}
              {d.attestation !== 'revoked' && d.attestation === 'failed' && (
                <Button size="sm" variant="destructive" className="mt-2 w-full" onClick={() => revoke(d.id)}>
                  <ShieldOff className="h-3 w-3 mr-1" />Revocar acceso
                </Button>
              )}
            </CardContent>
          </Card>
        ))}
        {devices.length === 0 && !loading && (
          <p className="col-span-3 text-muted-foreground text-sm text-center py-8">Sin dispositivos enrollados.</p>
        )}
      </div>
    </div>
  )
}
