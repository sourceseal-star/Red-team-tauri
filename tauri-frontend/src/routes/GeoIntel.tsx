import { useState } from 'react'
import { api } from '../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Search, MapPin, Shield, Wifi, Camera, Radio, AlertTriangle } from 'lucide-react'

// ─── Tipos ────────────────────────────────────────────────────────────────────
interface GeoResult {
  ip?: string; country?: string; city?: string; lat?: number | null; lon?: number | null
  isp?: string; as?: string | number | null; proxy?: boolean; hosting?: boolean; mobile?: boolean
  private?: boolean; error?: string; note?: string
}
interface IntelResult {
  ip?: string; score?: number; label?: string; rdns?: string | null; blocklist?: boolean
  breakdown?: {f: string; w: number}[]; flags?: GeoResult; note?: string; private?: boolean
  error?: string
}

interface CamService {
  port: number; proto: string; open: boolean; type: string
  banner?: string; rtsp?: boolean; status?: number
}
interface CamResult {
  host: string; is_camera: boolean; brand?: string | null
  services: CamService[]; open_ports: number[]
  scanned_at?: string; error?: string
}
interface CamScanResponse {
  target: string; mode: string; hosts_with_services: number
  cameras_found: number; elapsed_seconds: number
  results: CamResult[]; scanner: string; note: string
  scanned_at: string; error?: string
}

interface RadioStream {
  port: number; proto: string; open: boolean
  server?: string; content_type?: string; icy_name?: string; icy_genre?: string
  type: string; is_stream: boolean
}
interface RadioResult {
  host: string; is_radio: boolean; stream_name?: string
  streams: RadioStream[]; open_ports: number[]
  scanned_at?: string; error?: string
}
interface RadioScanResponse {
  target: string; mode: string; hosts_with_streams: number
  radios_found: number; elapsed_seconds: number
  results: RadioResult[]; scanner: string; note: string
  scanned_at: string; error?: string
}

// ─── Utilidades de color ──────────────────────────────────────────────────────
function scoreColor(s: number | undefined): string {
  const v = s ?? 0
  if (v <= 20) return 'text-green-400'
  if (v <= 50) return 'text-yellow-400'
  if (v <= 80) return 'text-orange-400'
  return 'text-red-400'
}
function scoreBar(s: number | undefined): string {
  const v = s ?? 0
  if (v <= 20) return 'bg-green-500'
  if (v <= 50) return 'bg-yellow-500'
  if (v <= 80) return 'bg-orange-500'
  return 'bg-red-500'
}

// ─── Componente principal ─────────────────────────────────────────────────────
export default function GeoIntel() {
  // Geo / Intel
  const [ip, setIp] = useState('')
  const [geo, setGeo] = useState<GeoResult | null>(null)
  const [intel, setIntel] = useState<IntelResult | null>(null)
  const [geoLoading, setGeoLoading] = useState(false)
  const [geoErr, setGeoErr] = useState('')
  const [history, setHistory] = useState<Array<{ip:string; score:number; country:string; isp:string; label:string}>>([])

  // API Key compartida para escaneos de red
  const [netApiKey, setNetApiKey] = useState('')

  // Cámaras
  const [camTarget, setCamTarget] = useState('')
  const [camResult, setCamResult] = useState<CamScanResponse | null>(null)
  const [camLoading, setCamLoading] = useState(false)
  const [camErr, setCamErr] = useState('')
  const [camTimeout, setCamTimeout] = useState('2')

  // Radio
  const [radioTarget, setRadioTarget] = useState('')
  const [radioResult, setRadioResult] = useState<RadioScanResponse | null>(null)
  const [radioLoading, setRadioLoading] = useState(false)
  const [radioErr, setRadioErr] = useState('')
  const [radioTimeout, setRadioTimeout] = useState('2')

  // ── Geo lookup ──────────────────────────────────────────────────────────────
  const lookup = async (target?: string) => {
    const q = (target || ip).trim()
    if (!q) return
    setIp(q); setGeoLoading(true); setGeo(null); setIntel(null); setGeoErr('')
    try {
      let g: GeoResult = {}
      let i: IntelResult = {}
      try { g = await api.getGeo(q) as GeoResult }
      catch (e: unknown) { g = { ip: q, error: e instanceof Error ? e.message : 'Error de conexión' } }
      try { i = await api.getIntel(q) as IntelResult }
      catch (e: unknown) { i = { ip: q, error: e instanceof Error ? e.message : 'Error de conexión' } }
      setGeo(g); setIntel(i)
      if (!g.error && !g.private) {
        setHistory(prev => [{
          ip: q, score: i.score ?? 0, country: g.country ?? '—',
          isp: g.isp ?? '—', label: i.label ?? '—',
        }, ...prev.filter(x => x.ip !== q)].slice(0, 10))
      }
    } catch (e: unknown) {
      setGeoErr(e instanceof Error ? e.message : 'Error desconocido')
    } finally { setGeoLoading(false) }
  }

  // ── Camera scan ─────────────────────────────────────────────────────────────
  const scanCameras = async () => {
    const t = camTarget.trim()
    if (!t) return
    if (!netApiKey.trim()) { setCamErr('Introduce el REDTEAM_API_KEY antes de escanear.'); return }
    setCamLoading(true); setCamResult(null); setCamErr('')
    try {
      const res = await api.scanCameras(t, netApiKey.trim(), parseFloat(camTimeout) || 2) as CamScanResponse
      if ((res as {error?: string}).error) { setCamErr((res as {error: string}).error); }
      else setCamResult(res)
    } catch (e: unknown) {
      setCamErr(e instanceof Error ? e.message : 'Error de conexión con el backend')
    } finally { setCamLoading(false) }
  }

  // ── Radio scan ──────────────────────────────────────────────────────────────
  const scanRadio = async () => {
    const t = radioTarget.trim()
    if (!t) return
    if (!netApiKey.trim()) { setRadioErr('Introduce el REDTEAM_API_KEY antes de escanear.'); return }
    setRadioLoading(true); setRadioResult(null); setRadioErr('')
    try {
      const res = await api.scanRadio(t, netApiKey.trim(), parseFloat(radioTimeout) || 2) as RadioScanResponse
      if ((res as {error?: string}).error) { setRadioErr((res as {error: string}).error); }
      else setRadioResult(res)
    } catch (e: unknown) {
      setRadioErr(e instanceof Error ? e.message : 'Error de conexión con el backend')
    } finally { setRadioLoading(false) }
  }

  // ─────────────────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Geo + Intel · Cámaras IP · Radio</h2>
        <Badge variant="outline" className="text-xs">ipwho.is · abuse.ch · RTSP · Icecast</Badge>
      </div>

      {/* ══════════════════════════════════════════════════════════════════════
          SECCIÓN 1: GEOLOCALIZACIÓN + THREAT INTEL
      ══════════════════════════════════════════════════════════════════════ */}
      <div className="border-b border-border pb-1">
        <p className="text-xs text-muted-foreground flex items-center gap-1 mb-2">
          <MapPin className="h-3 w-3" /> Geolocalización &amp; Threat Intelligence
        </p>
      </div>

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
            <Button onClick={() => lookup()} disabled={geoLoading || !ip.trim()}>
              <Search className="h-4 w-4 mr-1" />
              {geoLoading ? 'Consultando…' : 'Consultar'}
            </Button>
          </div>
          <div className="flex gap-2 mt-2 flex-wrap">
            {['8.8.8.8','1.1.1.1','45.33.32.156','104.131.0.1'].map(q => (
              <button key={q}
                className="text-xs text-muted-foreground hover:text-foreground font-mono border border-border/40 rounded px-2 py-0.5"
                onClick={() => lookup(q)}>{q}</button>
            ))}
          </div>
          {geoErr && <p className="text-red-400 text-sm mt-2 font-mono">{geoErr}</p>}
        </CardContent>
      </Card>

      {(geo || intel) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {geo && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <MapPin className="h-4 w-4 text-blue-400" /> Geolocalización
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                {geo.error ? (
                  <p className="text-red-400 font-mono text-xs">{geo.error}</p>
                ) : geo.private ? (
                  <p className="text-muted-foreground text-xs">{geo.note ?? 'IP privada — sin geolocalización pública'}</p>
                ) : (
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                    <span className="text-muted-foreground">IP</span>
                    <span className="font-mono text-blue-400">{geo.ip ?? '—'}</span>
                    <span className="text-muted-foreground">País</span>
                    <span>{geo.country ?? '—'}</span>
                    <span className="text-muted-foreground">Ciudad</span>
                    <span>{geo.city ?? '—'}</span>
                    <span className="text-muted-foreground">ISP</span>
                    <span className="truncate">{geo.isp ?? '—'}</span>
                    <span className="text-muted-foreground">AS</span>
                    <span className="font-mono">AS{geo.as ?? '—'}</span>
                    <span className="text-muted-foreground">Lat / Lon</span>
                    <span className="font-mono text-xs">
                      {geo.lat != null ? geo.lat.toFixed(4) : '—'}, {geo.lon != null ? geo.lon.toFixed(4) : '—'}
                    </span>
                  </div>
                )}
                {!geo.error && !geo.private && (
                  <div className="flex gap-2 pt-1 flex-wrap">
                    {geo.proxy   && <Badge variant="destructive" className="text-xs">Proxy/VPN</Badge>}
                    {geo.hosting && <Badge variant="outline" className="text-xs text-yellow-400 border-yellow-600">Hosting/Cloud</Badge>}
                    {geo.mobile  && <Badge variant="outline" className="text-xs text-blue-400 border-blue-600">Móvil</Badge>}
                    {!geo.proxy && !geo.hosting && !geo.mobile && (
                      <Badge variant="outline" className="text-xs text-green-400 border-green-600">Residencial</Badge>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {intel && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Shield className="h-4 w-4 text-purple-400" /> Threat Intelligence
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                {intel.error ? (
                  <p className="text-red-400 font-mono text-xs">{intel.error}</p>
                ) : intel.private ? (
                  <p className="text-muted-foreground text-xs">IP privada — confianza N/A</p>
                ) : (
                  <>
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-muted-foreground text-xs">Score de riesgo</span>
                        <span className={`font-bold font-mono text-lg ${scoreColor(intel.score)}`}>
                          {intel.score ?? 0}<span className="text-xs text-muted-foreground">/100</span>
                        </span>
                      </div>
                      <div className="w-full bg-muted rounded-full h-2">
                        <div className={`h-2 rounded-full transition-all ${scoreBar(intel.score)}`}
                          style={{ width: `${intel.score ?? 0}%` }} />
                      </div>
                      <p className={`text-xs font-semibold mt-1 ${scoreColor(intel.score)}`}>{intel.label ?? '—'}</p>
                    </div>
                    <div className="grid grid-cols-2 gap-x-4 gap-y-1 pt-1">
                      <span className="text-muted-foreground">rDNS</span>
                      <span className="font-mono text-xs truncate">{intel.rdns ?? '—'}</span>
                      <span className="text-muted-foreground">Blocklist</span>
                      <span className={intel.blocklist ? 'text-green-400' : 'text-muted-foreground'}>
                        {intel.blocklist ? '✅ verificada' : '⚠️ no disponible'}
                      </span>
                      <span className="text-muted-foreground">Nota</span>
                      <span className="text-xs">{intel.note ?? '—'}</span>
                    </div>
                    {intel.breakdown && intel.breakdown.length > 0 ? (
                      <div className="mt-2 border-t border-border pt-2">
                        <p className="text-xs text-muted-foreground mb-1">Desglose:</p>
                        {intel.breakdown.map((b, idx) => (
                          <div key={idx} className="flex justify-between text-xs font-mono">
                            <span className="text-muted-foreground">{b.f}</span>
                            <span className={b.w > 0 ? 'text-red-400' : 'text-green-400'}>
                              {b.w > 0 ? '+' : ''}{b.w}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-green-400 border-t border-border pt-2">
                        ✅ Sin penalizaciones — host limpio
                      </p>
                    )}
                    <details className="mt-2">
                      <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">
                        Ver JSON crudo
                      </summary>
                      <pre className="mt-1 text-[10px] bg-muted rounded p-2 overflow-auto max-h-40 font-mono">
                        {JSON.stringify(intel, null, 2)}
                      </pre>
                    </details>
                  </>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      )}

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
                  <tr key={h.ip}
                    className="border-b border-border/40 hover:bg-muted/20 cursor-pointer"
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

      {/* ══════════════════════════════════════════════════════════════════════
          SECCIÓN 2: ESCANEO DE CÁMARAS IP (REAL)
      ══════════════════════════════════════════════════════════════════════ */}
      <div className="border-b border-border pb-1 mt-6">
        <p className="text-xs text-muted-foreground flex items-center gap-1 mb-2">
          <Camera className="h-3 w-3" /> Escáner de Cámaras IP — REAL (RTSP · ONVIF · HTTP · Dahua · Axis · Hikvision…)
        </p>
      </div>

      {/* API Key — compartida para ambos escáneres de red */}
      <Card className="border-yellow-700/40 bg-yellow-950/10">
        <CardContent className="pt-4">
          <div className="flex items-center gap-2 flex-wrap">
            <Shield className="h-4 w-4 text-yellow-400 shrink-0" />
            <span className="text-xs text-yellow-300 font-semibold">REDTEAM_API_KEY</span>
            <span className="text-xs text-muted-foreground">— requerida para los escáneres de red</span>
            <input
              type="password"
              className="flex-1 min-w-[200px] bg-muted border border-yellow-700/60 rounded px-3 py-2 text-sm font-mono"
              placeholder="Pega tu REDTEAM_API_KEY aquí"
              value={netApiKey}
              onChange={e => setNetApiKey(e.target.value)}
              autoComplete="off"
            />
            {netApiKey && (
              <Badge variant="outline" className="text-xs text-green-400 border-green-700">
                ✓ configurado
              </Badge>
            )}
          </div>
          <p className="text-[10px] text-muted-foreground mt-1 pl-6">
            El key se envía como header <span className="font-mono">X-Api-Key</span> y nunca se almacena en el cliente.
            Configura <span className="font-mono">REDTEAM_API_KEY</span> como variable de entorno en el servidor.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Camera className="h-4 w-4 text-cyan-400" /> Escaneo de Cámaras IP
            <Badge variant="outline" className="text-xs text-cyan-400 border-cyan-600 ml-auto">
              Puertos: 80 443 554 8080 8554 8899 37777 34567 2020
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2 flex-wrap">
            <input
              className="flex-1 min-w-[200px] bg-muted border border-border rounded px-3 py-2 text-sm font-mono"
              placeholder="IP (192.168.1.10) o subred (192.168.1.0/24)"
              value={camTarget}
              onChange={e => setCamTarget(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && scanCameras()}
            />
            <select
              className="bg-muted border border-border rounded px-2 py-2 text-sm text-muted-foreground"
              value={camTimeout}
              onChange={e => setCamTimeout(e.target.value)}
            >
              <option value="1">Timeout: 1s</option>
              <option value="2">Timeout: 2s</option>
              <option value="3">Timeout: 3s</option>
              <option value="5">Timeout: 5s</option>
            </select>
            <Button onClick={scanCameras} disabled={camLoading || !camTarget.trim()}
              className="bg-cyan-700 hover:bg-cyan-600">
              <Camera className="h-4 w-4 mr-1" />
              {camLoading ? 'Escaneando…' : 'Escanear'}
            </Button>
          </div>

          {/* Ejemplos rápidos */}
          <div className="flex gap-2 flex-wrap">
            {['192.168.1.1','192.168.0.1','10.0.0.1','192.168.1.0/24'].map(q => (
              <button key={q}
                className="text-xs text-muted-foreground hover:text-foreground font-mono border border-border/40 rounded px-2 py-0.5"
                onClick={() => { setCamTarget(q) }}>
                {q}
              </button>
            ))}
          </div>

          {camLoading && (
            <div className="flex items-center gap-2 text-sm text-cyan-400 animate-pulse">
              <Camera className="h-4 w-4" />
              Escaneando {camTarget} en tiempo real — conectando a puertos de cámara…
            </div>
          )}
          {camErr && (
            <div className="flex items-start gap-2 text-red-400 text-sm bg-red-900/20 rounded p-2">
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
              {camErr}
            </div>
          )}

          {camResult && !camErr && (
            <div className="space-y-3">
              {/* Resumen */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                <div className="bg-muted rounded p-2 text-center">
                  <p className="text-2xl font-bold text-cyan-400">{camResult.cameras_found}</p>
                  <p className="text-xs text-muted-foreground">Cámaras detectadas</p>
                </div>
                <div className="bg-muted rounded p-2 text-center">
                  <p className="text-2xl font-bold text-blue-400">{camResult.hosts_with_services}</p>
                  <p className="text-xs text-muted-foreground">Hosts con servicios</p>
                </div>
                <div className="bg-muted rounded p-2 text-center">
                  <p className="text-2xl font-bold font-mono">{camResult.elapsed_seconds}s</p>
                  <p className="text-xs text-muted-foreground">Tiempo escaneo</p>
                </div>
                <div className="bg-muted rounded p-2 text-center">
                  <p className="text-xs font-mono text-muted-foreground mt-1">{camResult.scanner}</p>
                  <p className="text-xs text-green-400">{camResult.note}</p>
                </div>
              </div>

              {/* Resultados por host */}
              {camResult.results.filter(r => r.services?.length > 0).map((r, idx) => (
                <div key={idx} className={`border rounded p-3 ${r.is_camera ? 'border-cyan-600/50 bg-cyan-950/20' : 'border-border'}`}>
                  <div className="flex items-center gap-2 mb-2">
                    <Camera className={`h-4 w-4 ${r.is_camera ? 'text-cyan-400' : 'text-muted-foreground'}`} />
                    <span className="font-mono font-bold text-sm">{r.host}</span>
                    {r.is_camera && (
                      <Badge className="text-xs bg-cyan-700 text-white">
                        📷 CÁMARA {r.brand ? `— ${r.brand}` : ''}
                      </Badge>
                    )}
                    <span className="text-xs text-muted-foreground ml-auto">
                      Puertos: {r.open_ports.join(', ')}
                    </span>
                  </div>
                  <div className="space-y-1">
                    {r.services.map((svc, si) => (
                      <div key={si} className="flex items-center gap-2 text-xs font-mono pl-6">
                        <span className="text-green-400">●</span>
                        <span className="text-yellow-400 w-12">{svc.port}</span>
                        <span className="text-muted-foreground w-20">{svc.proto}</span>
                        <span className={svc.rtsp ? 'text-cyan-400' : 'text-foreground'}>{svc.type}</span>
                        {svc.banner && (
                          <span className="text-muted-foreground truncate max-w-[200px]">— {svc.banner}</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}

              {camResult.cameras_found === 0 && camResult.hosts_with_services === 0 && (
                <p className="text-muted-foreground text-sm text-center py-4">
                  No se detectaron cámaras ni servicios de red en {camResult.target}
                </p>
              )}

              <details className="mt-2">
                <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">
                  Ver JSON completo del escaneo
                </summary>
                <pre className="mt-1 text-[10px] bg-muted rounded p-2 overflow-auto max-h-48 font-mono">
                  {JSON.stringify(camResult, null, 2)}
                </pre>
              </details>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ══════════════════════════════════════════════════════════════════════
          SECCIÓN 3: ESCANEO DE RADIO / STREAMING (REAL)
      ══════════════════════════════════════════════════════════════════════ */}
      <div className="border-b border-border pb-1 mt-6">
        <p className="text-xs text-muted-foreground flex items-center gap-1 mb-2">
          <Radio className="h-3 w-3" /> Escáner de Radio / Streaming — REAL (Icecast · ShoutCast · RTSP-audio · RTMP…)
        </p>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Radio className="h-4 w-4 text-purple-400" /> Escaneo de Radio &amp; Audio Streaming
            <Badge variant="outline" className="text-xs text-purple-400 border-purple-600 ml-auto">
              Puertos: 8000 8001 8080 1755 554 3000 9000
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2 flex-wrap">
            <input
              className="flex-1 min-w-[200px] bg-muted border border-border rounded px-3 py-2 text-sm font-mono"
              placeholder="IP (192.168.1.10) o subred (192.168.1.0/24)"
              value={radioTarget}
              onChange={e => setRadioTarget(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && scanRadio()}
            />
            <select
              className="bg-muted border border-border rounded px-2 py-2 text-sm text-muted-foreground"
              value={radioTimeout}
              onChange={e => setRadioTimeout(e.target.value)}
            >
              <option value="1">Timeout: 1s</option>
              <option value="2">Timeout: 2s</option>
              <option value="3">Timeout: 3s</option>
              <option value="5">Timeout: 5s</option>
            </select>
            <Button onClick={scanRadio} disabled={radioLoading || !radioTarget.trim()}
              className="bg-purple-700 hover:bg-purple-600">
              <Radio className="h-4 w-4 mr-1" />
              {radioLoading ? 'Escaneando…' : 'Escanear'}
            </Button>
          </div>

          <div className="flex gap-2 flex-wrap">
            {['192.168.1.1','192.168.0.1','10.0.0.1','192.168.1.0/24'].map(q => (
              <button key={q}
                className="text-xs text-muted-foreground hover:text-foreground font-mono border border-border/40 rounded px-2 py-0.5"
                onClick={() => { setRadioTarget(q) }}>
                {q}
              </button>
            ))}
          </div>

          {radioLoading && (
            <div className="flex items-center gap-2 text-sm text-purple-400 animate-pulse">
              <Radio className="h-4 w-4" />
              Escaneando {radioTarget} — buscando streams Icecast, ShoutCast, RTSP…
            </div>
          )}
          {radioErr && (
            <div className="flex items-start gap-2 text-red-400 text-sm bg-red-900/20 rounded p-2">
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
              {radioErr}
            </div>
          )}

          {radioResult && !radioErr && (
            <div className="space-y-3">
              {/* Resumen */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                <div className="bg-muted rounded p-2 text-center">
                  <p className="text-2xl font-bold text-purple-400">{radioResult.radios_found}</p>
                  <p className="text-xs text-muted-foreground">Radios/Streams</p>
                </div>
                <div className="bg-muted rounded p-2 text-center">
                  <p className="text-2xl font-bold text-blue-400">{radioResult.hosts_with_streams}</p>
                  <p className="text-xs text-muted-foreground">Hosts con puertos</p>
                </div>
                <div className="bg-muted rounded p-2 text-center">
                  <p className="text-2xl font-bold font-mono">{radioResult.elapsed_seconds}s</p>
                  <p className="text-xs text-muted-foreground">Tiempo escaneo</p>
                </div>
                <div className="bg-muted rounded p-2 text-center">
                  <p className="text-xs font-mono text-muted-foreground mt-1">{radioResult.scanner}</p>
                  <p className="text-xs text-green-400">{radioResult.note}</p>
                </div>
              </div>

              {/* Resultados por host */}
              {radioResult.results.filter(r => r.streams?.length > 0).map((r, idx) => (
                <div key={idx} className={`border rounded p-3 ${r.is_radio ? 'border-purple-600/50 bg-purple-950/20' : 'border-border'}`}>
                  <div className="flex items-center gap-2 mb-2">
                    <Radio className={`h-4 w-4 ${r.is_radio ? 'text-purple-400' : 'text-muted-foreground'}`} />
                    <span className="font-mono font-bold text-sm">{r.host}</span>
                    {r.is_radio && (
                      <Badge className="text-xs bg-purple-700 text-white">
                        📻 RADIO{r.stream_name ? ` — ${r.stream_name}` : ''}
                      </Badge>
                    )}
                    <span className="text-xs text-muted-foreground ml-auto">
                      Puertos: {r.open_ports.join(', ')}
                    </span>
                  </div>
                  <div className="space-y-1">
                    {r.streams.map((s, si) => (
                      <div key={si} className="flex items-center gap-2 text-xs font-mono pl-6 flex-wrap">
                        <span className={s.is_stream ? 'text-purple-400' : 'text-green-400'}>●</span>
                        <span className="text-yellow-400 w-12">{s.port}</span>
                        <span className="text-muted-foreground w-24">{s.proto}</span>
                        <span className={s.is_stream ? 'text-purple-300 font-semibold' : 'text-foreground'}>{s.type}</span>
                        {s.server && (
                          <span className="text-muted-foreground">— {s.server}</span>
                        )}
                        {s.icy_name && (
                          <Badge variant="outline" className="text-xs text-purple-400 border-purple-700">
                            🎵 {s.icy_name}
                          </Badge>
                        )}
                        {s.icy_genre && (
                          <span className="text-muted-foreground text-[10px]">[{s.icy_genre}]</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}

              {radioResult.radios_found === 0 && radioResult.hosts_with_streams === 0 && (
                <p className="text-muted-foreground text-sm text-center py-4">
                  No se detectaron servidores de radio/streaming en {radioResult.target}
                </p>
              )}

              <details className="mt-2">
                <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">
                  Ver JSON completo del escaneo
                </summary>
                <pre className="mt-1 text-[10px] bg-muted rounded p-2 overflow-auto max-h-48 font-mono">
                  {JSON.stringify(radioResult, null, 2)}
                </pre>
              </details>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
