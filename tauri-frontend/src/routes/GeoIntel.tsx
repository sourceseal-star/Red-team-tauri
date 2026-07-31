import { useState } from 'react'
import { api } from '../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Search, MapPin, Shield, Wifi } from 'lucide-react'

interface GeoResult {
  ip: string; country: string; city: string; lat: number; lon: number
  isp: string; as: string | number; proxy: boolean; hosting: boolean; mobile: boolean
  private?: boolean; error?: string; note?: string
}
interface IntelResult {
  ip: string; score: number; label: string; rdns: string | null; blocklist: boolean
  breakdown: {f: string; w: number}[]; flags: GeoResult; note: string; private?: boolean
  error?: string
}

function scoreColor(s: number) {
  if (s <= 20) return 'text-green-400'
  if (s <= 50) return 'text-yellow-400'
  if (s <= 80) return 'text-orange-400'
  return 'text-red-400'
}
function scoreBar(s: number) {
  if (s <= 20) return 'bg-green-500'
  if (s <= 50) return 'bg-yellow-500'
  if (s <= 80) return 'bg-orange-500'
  return 'bg-red-500'
}

export default function GeoIntel() {
  const [ip, setIp] = useState('')
  const [geo, setGeo] = useState<GeoResult | null>(null)
  const [intel, setIntel] = useState<IntelResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState<Array<{ip:string; score:number; country:string; isp:string; label:string}>>([])

  const lookup = async (target?: string) => {
    const q = (target || ip).trim()
    if (!q) return
    setIp(q); setLoading(true); setGeo(null); setIntel(null)
    try {
      const [g, i] = await Promise.all([
        api.getGeo(q),
        api.getIntel(q),
      ])
      setGeo(g as GeoResult)
      setIntel(i as IntelResult)
      if (!(g as GeoResult).error) {
        setHistory(prev => [{
          ip: q,
          score: (i as IntelResult).score ?? 0,
          country: (g as GeoResult).country ?? '—',
          isp: (g as GeoResult).isp ?? '—',
          label: (i as IntelResult).label ?? '—',
        }, ...prev.filter(x => x.ip !== q)].slice(0, 10))
      }
    } catch (e: unknown) {
      setGeo({ ip: q, country:'—', city:'—', lat:0, lon:0, isp:'—', as:'—',
               proxy:false, hosting:false, mobile:false,
               error: e instanceof Error ? e.message : 'Error de conexión' })
    } finally { setLoading(false) }
  }

  const flagEmoji = (country: string) => {
    if (!country || country === '—') return ''
    // No usamos emojis de bandera — solo texto
    return ''
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Geo + Threat Intel</h2>
        <Badge variant="outline" className="text-xs">ipwho.is · abuse.ch · stdlib</Badge>
      </div>

      {/* Búsqueda */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex gap-2">
            <input
              className="flex-1 bg-muted border border-border rounded px-3 py-2 text-sm font-mono"
              placeholder="IP a consultar (ej: 8.8.8.8, 45.33.32.156)"
              value={ip}
              onChange={e => setIp(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && lookup()}
            />
            <Button onClick={() => lookup()} disabled={loading || !ip.trim()}>
              <Search className="h-4 w-4 mr-1" />
              {loading ? 'Consultando…' : 'Consultar'}
            </Button>
          </div>
          {/* Quick test IPs */}
          <div className="flex gap-2 mt-2 flex-wrap">
            {['8.8.8.8','1.1.1.1','45.33.32.156','104.131.0.1'].map(q => (
              <button key={q} className="text-xs text-muted-foreground hover:text-foreground font-mono border border-border/40 rounded px-2 py-0.5"
                onClick={() => lookup(q)}>{q}</button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Resultado Geo + Intel */}
      {(geo || intel) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Geo */}
          {geo && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <MapPin className="h-4 w-4 text-blue-400" />
                  Geolocalización
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                {geo.error ? (
                  <p className="text-red-400 font-mono">{geo.error}</p>
                ) : geo.private ? (
                  <p className="text-muted-foreground">{geo.note}</p>
                ) : (<>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                    <span className="text-muted-foreground">IP</span>
                    <span className="font-mono text-blue-400">{geo.ip}</span>
                    <span className="text-muted-foreground">País</span>
                    <span>{geo.country}</span>
                    <span className="text-muted-foreground">Ciudad</span>
                    <span>{geo.city}</span>
                    <span className="text-muted-foreground">ISP</span>
                    <span className="truncate">{geo.isp}</span>
                    <span className="text-muted-foreground">AS</span>
                    <span className="font-mono">AS{geo.as}</span>
                    <span className="text-muted-foreground">Lat / Lon</span>
                    <span className="font-mono text-xs">{geo.lat?.toFixed(4)}, {geo.lon?.toFixed(4)}</span>
                  </div>
                  <div className="flex gap-2 pt-1 flex-wrap">
                    {geo.proxy   && <Badge variant="destructive" className="text-xs">Proxy/VPN</Badge>}
                    {geo.hosting && <Badge variant="outline" className="text-xs text-yellow-400 border-yellow-600">Hosting/Cloud</Badge>}
                    {geo.mobile  && <Badge variant="outline" className="text-xs text-blue-400 border-blue-600">Móvil</Badge>}
                    {!geo.proxy && !geo.hosting && !geo.mobile && (
                      <Badge variant="outline" className="text-xs text-green-400 border-green-600">Residencial</Badge>
                    )}
                  </div>
                </>)}
              </CardContent>
            </Card>
          )}

          {/* Intel */}
          {intel && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Shield className="h-4 w-4 text-purple-400" />
                  Threat Intelligence
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                {intel.error ? (
                  <p className="text-red-400 font-mono">{intel.error}</p>
                ) : intel.private ? (
                  <p className="text-muted-foreground">IP privada — confianza N/A</p>
                ) : (<>
                  {/* Score bar */}
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-muted-foreground text-xs">Score de riesgo</span>
                      <span className={`font-bold font-mono text-lg ${scoreColor(intel.score)}`}>{intel.score}<span className="text-xs text-muted-foreground">/100</span></span>
                    </div>
                    <div className="w-full bg-muted rounded-full h-2">
                      <div className={`h-2 rounded-full transition-all ${scoreBar(intel.score)}`}
                        style={{ width: `${intel.score}%` }} />
                    </div>
                    <p className={`text-xs font-semibold mt-1 ${scoreColor(intel.score)}`}>{intel.label}</p>
                  </div>

                  <div className="grid grid-cols-2 gap-x-4 gap-y-1 pt-1">
                    <span className="text-muted-foreground">rDNS</span>
                    <span className="font-mono text-xs truncate">{intel.rdns ?? '—'}</span>
                    <span className="text-muted-foreground">Blocklist</span>
                    <span className={intel.blocklist ? 'text-green-400' : 'text-muted-foreground'}>
                      {intel.blocklist ? '✅ verificada' : '⚠️ no disponible'}
                    </span>
                    <span className="text-muted-foreground">Nota</span>
                    <span className="text-xs">{intel.note}</span>
                  </div>

                  {/* Desglose */}
                  {intel.breakdown.length > 0 ? (
                    <div className="mt-2 border-t border-border pt-2">
                      <p className="text-xs text-muted-foreground mb-1">Desglose de penalizaciones:</p>
                      {intel.breakdown.map((b, i) => (
                        <div key={i} className="flex justify-between text-xs font-mono">
                          <span className="text-muted-foreground">{b.f}</span>
                          <span className={b.w > 0 ? 'text-red-400' : 'text-green-400'}>
                            {b.w > 0 ? '+' : ''}{b.w}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-green-400 border-t border-border pt-2">✅ Sin penalizaciones — host limpio</p>
                  )}

                  {/* JSON crudo */}
                  <details className="mt-2">
                    <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">Ver JSON crudo del backend</summary>
                    <pre className="mt-1 text-[10px] bg-muted rounded p-2 overflow-auto max-h-48 font-mono">
                      {JSON.stringify(intel, null, 2)}
                    </pre>
                  </details>
                </>)}
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Historial */}
      {history.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Wifi className="h-4 w-4" /> Historial de consultas
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-muted-foreground border-b border-border">
                  <th className="px-4 py-2 text-left">IP</th>
                  <th className="px-4 py-2 text-left">País</th>
                  <th className="px-4 py-2 text-left">ISP</th>
                  <th className="px-4 py-2 text-left">Score</th>
                  <th className="px-4 py-2 text-left">Nivel</th>
                </tr>
              </thead>
              <tbody>
                {history.map(h => (
                  <tr key={h.ip} className="border-b border-border/40 hover:bg-muted/20 cursor-pointer"
                    onClick={() => lookup(h.ip)}>
                    <td className="px-4 py-2 font-mono text-blue-400">{h.ip}</td>
                    <td className="px-4 py-2">{h.country}</td>
                    <td className="px-4 py-2 truncate max-w-[120px]">{h.isp}</td>
                    <td className={`px-4 py-2 font-bold font-mono ${scoreColor(h.score)}`}>{h.score}</td>
                    <td className={`px-4 py-2 ${scoreColor(h.score)}`}>{h.label}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
