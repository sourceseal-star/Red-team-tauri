import { useState } from 'react'
import {
  api,
  type IPGeolocationResponse,
  type IPVerificationResponse,
  type IPTrustScoreResponse,
  type CameraScanResult,
  type RadioScanResult,
} from '../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from './ui/card'
import { Button } from './ui/button'
import { Badge } from './ui/badge'
import { Progress } from './ui/progress'
import {
  Loader2, MapPin, ShieldCheck, Gauge, Camera, Radio,
  CheckCircle2, XCircle, AlertTriangle, Globe, Server, Clock, Network, Eye
} from 'lucide-react'

type ActionType = 'geolocate' | 'verify' | 'trust' | 'cameras' | 'radio'

const ACTION_META: Record<ActionType, { label: string; icon: any; color: string }> = {
  geolocate: { label: 'Geolocalización', icon: MapPin,        color: 'text-blue-400'   },
  verify:    { label: 'Verificar origen', icon: ShieldCheck,  color: 'text-purple-400' },
  trust:     { label: 'Nivel de confianza', icon: Gauge,      color: 'text-emerald-400'},
  cameras:   { label: 'Escaneo cámaras IP', icon: Camera,      color: 'text-orange-400' },
  radio:     { label: 'Escaneo radio IP', icon: Radio,         color: 'text-cyan-400'   },
}

interface Props {
  ip: string
  defaultAction?: ActionType
  compact?: boolean
  onClose?: () => void
}

/**
 * Componente único que ejecuta las 5 acciones REALES sobre una IP:
 *   1. Geolocalización       -> ip-api.com
 *   2. Verificar origen      -> RDAP + reverse DNS
 *   3. Nivel de confianza    -> DNSBL reales (Spamhaus, abuse.ch, Tor)
 *   4. Escaneo de cámaras    -> TCP connect + banner RTSP/MJPEG/ONVIF
 *   5. Escaneo de radio      -> TCP connect + banner ICEcast/SHOUTcast/SIP
 *
 * Cada acción es ejecutable individualmente. Ningún dato es simulado.
 */
export function IPActionPanel({ ip, defaultAction = 'geolocate', compact = false, onClose }: Props) {
  const [action, setAction]   = useState<ActionType>(defaultAction)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState<string | null>(null)
  const [geo, setGeo]         = useState<IPGeolocationResponse | null>(null)
  const [ver, setVer]         = useState<IPVerificationResponse | null>(null)
  const [trust, setTrust]     = useState<IPTrustScoreResponse | null>(null)
  const [cam, setCam]         = useState<CameraScanResult | null>(null)
  const [rad, setRad]         = useState<RadioScanResult | null>(null)

  const run = async (a: ActionType) => {
    setAction(a); setError(null); setLoading(true)
    try {
      if (a === 'geolocate') setGeo(await api.ipGeolocate(ip))
      if (a === 'verify')    setVer(await api.ipVerifySource(ip))
      if (a === 'trust')     setTrust(await api.ipTrustScore(ip))
      if (a === 'cameras')   setCam(await api.ipScanCameras(ip))
      if (a === 'radio')     setRad(await api.ipScanRadio(ip))
    } catch (e: any) {
      setError(e?.message || 'Error ejecutando acción')
    } finally {
      setLoading(false)
    }
  }

  const verdictColor: Record<string, string> = {
    trusted:    'text-emerald-400 bg-emerald-950 border-emerald-800',
    neutral:    'text-yellow-400 bg-yellow-950 border-yellow-800',
    suspicious: 'text-orange-400 bg-orange-950 border-orange-800',
    malicious:  'text-red-400 bg-red-950 border-red-800',
  }

  return (
    <Card className={compact ? '' : 'border-blue-900/40'}>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="font-mono text-sm flex items-center gap-2">
          <Network className="h-4 w-4 text-blue-400" />
          IP: <span className="text-blue-300">{ip}</span>
        </CardTitle>
        {onClose && (
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground text-xs">
            ✕ cerrar
          </button>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Action tabs */}
        <div className="flex flex-wrap gap-1">
          {(Object.keys(ACTION_META) as ActionType[]).map(a => {
            const meta = ACTION_META[a]
            const Icon = meta.icon
            const active = action === a
            return (
              <Button
                key={a}
                size="sm"
                variant={active ? 'default' : 'outline'}
                className={`h-7 px-2 text-xs ${active ? '' : meta.color}`}
                onClick={() => run(a)}
                disabled={loading}
              >
                <Icon className="h-3 w-3 mr-1" />
                {meta.label}
              </Button>
            )
          })}
        </div>

        {loading && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground py-4">
            <Loader2 className="h-4 w-4 animate-spin" />
            Ejecutando acción real sobre {ip}…
          </div>
        )}

        {error && (
          <div className="text-xs text-red-400 bg-red-950/30 border border-red-900 rounded p-2 flex items-center gap-2">
            <XCircle className="h-3 w-3" /> {error}
          </div>
        )}

        {/* ── Geolocalización ──────────────────────────────────────────── */}
        {action === 'geolocate' && geo && !loading && (
          <div className="space-y-2">
            {!geo.ok ? (
              <div className="text-xs text-red-400">{geo.error || 'Sin datos'}</div>
            ) : geo.geolocation && (
              <>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="bg-muted rounded p-2">
                    <div className="text-muted-foreground flex items-center gap-1"><Globe className="h-3 w-3" /> País</div>
                    <div className="font-mono text-sm">{geo.geolocation.country}</div>
                  </div>
                  <div className="bg-muted rounded p-2">
                    <div className="text-muted-foreground">Región</div>
                    <div className="font-mono text-sm">{geo.geolocation.region}</div>
                  </div>
                  <div className="bg-muted rounded p-2">
                    <div className="text-muted-foreground">Ciudad</div>
                    <div className="font-mono text-sm">{geo.geolocation.city}</div>
                  </div>
                  <div className="bg-muted rounded p-2">
                    <div className="text-muted-foreground">CP</div>
                    <div className="font-mono text-sm">{geo.geolocation.zip}</div>
                  </div>
                  <div className="bg-muted rounded p-2">
                    <div className="text-muted-foreground">Coords</div>
                    <div className="font-mono text-sm">{geo.geolocation.lat.toFixed(4)}, {geo.geolocation.lon.toFixed(4)}</div>
                  </div>
                  <div className="bg-muted rounded p-2">
                    <div className="text-muted-foreground">TZ</div>
                    <div className="font-mono text-sm">{geo.geolocation.timezone}</div>
                  </div>
                </div>
                <div className="bg-muted rounded p-2 text-xs space-y-1">
                  <div className="flex items-center gap-1 text-muted-foreground">
                    <Server className="h-3 w-3" /> ISP / ASN
                  </div>
                  <div className="font-mono">{geo.geolocation.isp}</div>
                  <div className="font-mono text-muted-foreground">{geo.geolocation.org}</div>
                  <div className="font-mono text-muted-foreground">{geo.geolocation.asn}</div>
                </div>
                {/* Mapa visual SVG basado en lat/lon (sin libs externas) */}
                <div className="bg-muted rounded p-2">
                  <div className="text-xs text-muted-foreground mb-1 flex items-center gap-1">
                    <MapPin className="h-3 w-3" /> Posición global (proyección equirectangular)
                  </div>
                  <WorldDot lat={geo.geolocation.lat} lon={geo.geolocation.lon} />
                </div>
                <div className="text-[10px] text-muted-foreground">
                  Fuente: {geo.source} · {geo.geolocation.fetched_at}
                </div>
              </>
            )}
          </div>
        )}

        {/* ── Verificar origen ────────────────────────────────────────── */}
        {action === 'verify' && ver && !loading && (
          <div className="space-y-2">
            {!ver.ok ? (
              <div className="text-xs text-red-400">{ver.error}</div>
            ) : ver.verification && (
              <>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <KV k="Reverse DNS" v={ver.verification.reverse_dns || '—'} mono />
                  <KV k="Forward match" v={ver.verification.forward_dns_match ? <CheckCircle2 className="h-3 w-3 text-emerald-400" /> : <XCircle className="h-3 w-3 text-red-400" />} />
                  <KV k="RDAP handle"   v={ver.verification.rdap_handle || '—'} mono />
                  <KV k="RDAP org"      v={ver.verification.rdap_organization || '—'} mono />
                  <KV k="RDAP net"      v={ver.verification.rdap_network || '—'} mono />
                  <KV k="RDAP country"  v={ver.verification.rdap_country || '—'} />
                  <KV k="ASN"           v={ver.verification.asn || '—'} mono />
                  <KV k="ASN name"      v={ver.verification.asn_name || '—'} mono />
                  <KV k="Abuse contact" v={ver.verification.abuse_contact || '—'} mono />
                  <KV k="Tipo" v={
                    <span className="flex gap-1">
                      {ver.verification.is_private && <Badge variant="secondary">private</Badge>}
                      {ver.verification.is_loopback && <Badge variant="secondary">loopback</Badge>}
                      {ver.verification.is_multicast && <Badge variant="secondary">multicast</Badge>}
                      {!ver.verification.is_private && !ver.verification.is_loopback && !ver.verification.is_multicast && <Badge>público</Badge>}
                    </span>
                  } />
                </div>
                {ver.verification.rdap_error && (
                  <div className="text-[10px] text-yellow-400">RDAP: {ver.verification.rdap_error}</div>
                )}
                {ver.verification.reverse_dns_error && (
                  <div className="text-[10px] text-yellow-400">{ver.verification.reverse_dns_error}</div>
                )}
                <div className="text-[10px] text-muted-foreground">
                  Fuentes: {ver.verification.sources.join(' · ')} · {ver.verification.verified_at}
                </div>
              </>
            )}
          </div>
        )}

        {/* ── Trust score ─────────────────────────────────────────────── */}
        {action === 'trust' && trust && !loading && (
          <div className="space-y-2">
            {!trust.ok ? (
              <div className="text-xs text-red-400">{trust.error}</div>
            ) : trust.trust && (
              <>
                <div className={`rounded border p-3 ${verdictColor[trust.trust.verdict] || 'text-foreground bg-muted border-border'}`}>
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs uppercase tracking-wide opacity-80">Verdict</div>
                      <div className="text-lg font-bold uppercase">{trust.trust.verdict}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs opacity-80">Score</div>
                      <div className="text-2xl font-mono font-bold">{trust.trust.score}/100</div>
                    </div>
                  </div>
                  <Progress value={trust.trust.score} className="mt-2" />
                </div>
                {trust.trust.flags.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {trust.trust.flags.map(f => (
                      <Badge key={f} variant={f.startsWith('listed:') || f === 'tor_exit_node' ? 'destructive' : 'secondary'} className="text-[10px]">
                        {f}
                      </Badge>
                    ))}
                  </div>
                )}
                {trust.trust.evidence.length > 0 && (
                  <div className="bg-muted rounded p-2 text-xs space-y-1 max-h-32 overflow-y-auto">
                    <div className="text-muted-foreground flex items-center gap-1"><Eye className="h-3 w-3" /> Evidencia</div>
                    {trust.trust.evidence.map((e, i) => (
                      <div key={i} className="text-foreground/90 border-l-2 border-border pl-2">{e}</div>
                    ))}
                  </div>
                )}
                <div className="text-[10px] text-muted-foreground">
                  Fuentes: {trust.trust.sources_checked.join(' · ')}
                </div>
                <div className="text-[10px] text-muted-foreground">{trust.trust.checked_at}</div>
              </>
            )}
          </div>
        )}

        {/* ── Scan cameras ────────────────────────────────────────────── */}
        {action === 'cameras' && cam && !loading && (
          <div className="space-y-2">
            {!cam.ok ? (
              <div className="text-xs text-red-400">{cam.error}</div>
            ) : (
              <>
                <div className={`rounded border p-2 text-xs flex items-center gap-2 ${
                  cam.is_camera_exposed
                    ? 'bg-red-950 border-red-800 text-red-300'
                    : 'bg-muted border-border text-muted-foreground'
                }`}>
                  {cam.is_camera_exposed ? <AlertTriangle className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
                  {cam.is_camera_exposed
                    ? '⚠️ CÁMARA IP DETECTADA'
                    : 'No se detectó cámara IP expuesta'}
                  <span className="ml-auto text-[10px] text-muted-foreground">{cam.ports_scanned} puertos escaneados</span>
                </div>
                {cam.findings.length > 0 && (
                  <div className="space-y-1">
                    {cam.findings.map((f, i) => (
                      <div key={i} className="bg-muted rounded p-2 text-xs space-y-1">
                        <div className="flex items-center gap-2">
                          <Badge className="bg-orange-600">:{f.port}</Badge>
                          <Badge variant="outline">{f.protocol}</Badge>
                          {f.vendor && <Badge variant="secondary">{f.vendor}</Badge>}
                        </div>
                        <pre className="text-[10px] text-muted-foreground bg-background/40 rounded p-1 max-h-20 overflow-y-auto whitespace-pre-wrap break-all">{f.evidence.slice(0, 300)}</pre>
                      </div>
                    ))}
                  </div>
                )}
                {cam.open_ports.length > 0 && (
                  <details className="text-xs">
                    <summary className="cursor-pointer text-muted-foreground">Puertos abiertos ({cam.open_ports.length})</summary>
                    <div className="mt-1 grid grid-cols-2 gap-1">
                      {cam.open_ports.map((p, i) => (
                        <div key={i} className="bg-muted rounded p-1 font-mono text-[10px]">
                          :{p.port} {p.banner_preview && <span className="text-muted-foreground">— {p.banner_preview.slice(0, 40)}</span>}
                        </div>
                      ))}
                    </div>
                  </details>
                )}
                <div className="text-[10px] text-muted-foreground">
                  <Clock className="h-3 w-3 inline" /> {cam.scanned_at}
                </div>
              </>
            )}
          </div>
        )}

        {/* ── Scan radio ──────────────────────────────────────────────── */}
        {action === 'radio' && rad && !loading && (
          <div className="space-y-2">
            {!rad.ok ? (
              <div className="text-xs text-red-400">{rad.error}</div>
            ) : (
              <>
                <div className={`rounded border p-2 text-xs flex items-center gap-2 ${
                  rad.is_radio_exposed
                    ? 'bg-cyan-950 border-cyan-800 text-cyan-300'
                    : 'bg-muted border-border text-muted-foreground'
                }`}>
                  {rad.is_radio_exposed ? <AlertTriangle className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
                  {rad.is_radio_exposed
                    ? '📡 RADIO / STREAMING IP DETECTADO'
                    : 'No se detectó radio/streaming IP expuesta'}
                  <span className="ml-auto text-[10px] text-muted-foreground">{rad.ports_scanned} puertos escaneados</span>
                </div>
                {rad.findings.length > 0 && (
                  <div className="space-y-1">
                    {rad.findings.map((f, i) => (
                      <div key={i} className="bg-muted rounded p-2 text-xs space-y-1">
                        <div className="flex items-center gap-2">
                          <Badge className="bg-cyan-600">:{f.port}</Badge>
                          <Badge variant="outline">{f.kind}</Badge>
                        </div>
                        <pre className="text-[10px] text-muted-foreground bg-background/40 rounded p-1 max-h-20 overflow-y-auto whitespace-pre-wrap break-all">{f.evidence.slice(0, 300)}</pre>
                      </div>
                    ))}
                  </div>
                )}
                {rad.open_ports.length > 0 && (
                  <details className="text-xs">
                    <summary className="cursor-pointer text-muted-foreground">Puertos abiertos ({rad.open_ports.length})</summary>
                    <div className="mt-1 grid grid-cols-2 gap-1">
                      {rad.open_ports.map((p, i) => (
                        <div key={i} className="bg-muted rounded p-1 font-mono text-[10px]">
                          :{p.port} {p.banner_preview && <span className="text-muted-foreground">— {p.banner_preview.slice(0, 40)}</span>}
                        </div>
                      ))}
                    </div>
                  </details>
                )}
                <div className="text-[10px] text-muted-foreground">
                  <Clock className="h-3 w-3 inline" /> {rad.scanned_at}
                </div>
              </>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function KV({ k, v, mono = false }: { k: string; v: any; mono?: boolean }) {
  return (
    <div className="bg-muted rounded p-2">
      <div className="text-muted-foreground text-[10px] uppercase tracking-wide">{k}</div>
      <div className={`text-sm ${mono ? 'font-mono' : ''} break-all`}>{v}</div>
    </div>
  )
}

/**
 * Punto geográfico renderizado sobre un mapamundi minimalista.
 * Sin librerías externas (cumple restricción de Replit).
 * Proyección equirectangular: lon [-180,180] -> x [0,W], lat [-90,90] -> y [H,0]
 */
function WorldDot({ lat, lon }: { lat: number; lon: number }) {
  const W = 360, H = 160
  const x = ((lon + 180) / 360) * W
  const y = ((90 - lat) / 180) * H
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-24 bg-background/40 rounded border border-border">
      {/* Continentes aproximados (paths simplificados) */}
      <g fill="hsl(217 30% 30%)" opacity="0.5">
        {/* América */}
        <path d="M40,30 L60,30 L70,45 L65,60 L75,70 L80,95 L60,110 L50,130 L40,140 L30,130 L25,100 L30,75 Z" />
        {/* Europa/África */}
        <path d="M160,30 L195,30 L200,55 L195,80 L185,110 L175,135 L165,150 L155,130 L150,100 L155,75 L160,50 Z" />
        {/* Asia */}
        <path d="M210,25 L280,25 L310,40 L320,60 L315,85 L290,100 L260,95 L235,75 L215,55 Z" />
        {/* Oceanía */}
        <path d="M290,120 L320,115 L325,135 L305,140 L290,135 Z" />
      </g>
      {/* Líneas de latitud/longitud */}
      <g stroke="hsl(217 20% 22%)" strokeWidth="0.3" fill="none">
        {[0, 45, 90, 135].map(l => <line key={`v${l}`} x1={l} y1={0} x2={l} y2={H} />)}
        {[0, 40, 80, 120].map(l => <line key={`h${l}`} x1={0} y1={l} x2={W} y2={l} />)}
      </g>
      {/* Punto IP */}
      <circle cx={x} cy={y} r="3" fill="hsl(0 90% 60%)" stroke="hsl(0 0% 100%)" strokeWidth="0.5">
        <animate attributeName="r" values="3;6;3" dur="2s" repeatCount="indefinite" />
      </circle>
      <circle cx={x} cy={y} r="1.5" fill="hsl(0 0% 100%)" />
    </svg>
  )
}