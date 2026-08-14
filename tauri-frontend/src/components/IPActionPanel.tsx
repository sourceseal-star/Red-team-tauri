import { useState, useRef, useEffect } from 'react'
import {
  api,
  authUrl,
  type IPGeolocationResponse,
  type IPVerificationResponse,
  type IPTrustScoreResponse,
  type CameraScanResult,
  type RadioScanResult,
  type VideoUrlsResponse,
  type VideoSource,
} from '../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from './ui/card'
import { Button } from './ui/button'
import { Badge } from './ui/badge'
import { Progress } from './ui/progress'
import {
  Loader2, MapPin, ShieldCheck, Gauge, Camera, Radio,
  CheckCircle2, XCircle, AlertTriangle, Globe, Server, Clock, Network, Eye,
  Video, Play, RefreshCw, ExternalLink,
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
 *   1. Geolocalización       -> ipwho.is
 *   2. Verificar origen      -> RDAP + reverse DNS
 *   3. Nivel de confianza    -> DNSBL reales (Spamhaus, abuse.ch, Tor)
 *   4. Escaneo de cámaras    -> TCP connect + banner RTSP/MJPEG/ONVIF + VIDEO STREAM
 *   5. Escaneo de radio      -> TCP connect + banner ICEcast/SHOUTcast/SIP
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

  // Video state
  const [videoSources, setVideoSources] = useState<VideoSource[]>([])
  const [activeVideo, setActiveVideo]   = useState<VideoSource | null>(null)
  const [videoLoading, setVideoLoading] = useState(false)
  const [snapshotUrl, setSnapshotUrl]   = useState<string | null>(null)
  const [snapshotLoading, setSnapshotLoading] = useState(false)
  const [camUser, setCamUser] = useState('')
  const [camPass, setCamPass] = useState('')
  const [showCreds, setShowCreds] = useState(false)
  const imgRef = useRef<HTMLImageElement>(null)

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

  // Cargar fuentes de video cuando se detectan cámaras
  const loadVideoSources = async () => {
    setVideoLoading(true)
    try {
      const r = await api.ipVideoUrls(ip, camUser || undefined, camPass || undefined)
      setVideoSources(r.video_sources || [])
    } catch (e: any) {
      setError(e?.message || 'Error detectando video')
    } finally {
      setVideoLoading(false)
    }
  }

  // Tomar snapshot de una fuente
  const takeSnapshot = (src: VideoSource) => {
    if (!src.snapshot_url) return
    setSnapshotLoading(true)
    setActiveVideo(null) // detener stream
    const url = authUrl(src.snapshot_url)
    setSnapshotUrl(url)
    setTimeout(() => setSnapshotLoading(false), 1500)
  }

  // Iniciar stream MJPEG
  const startStream = (src: VideoSource) => {
    if (!src.stream_url) return
    setSnapshotUrl(null)
    setActiveVideo(src)
  }

  // Detener stream
  const stopStream = () => {
    setActiveVideo(null)
    setSnapshotUrl(null)
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
        <CardTitle className="text-sm flex items-center gap-2">
          <Network className="h-4 w-4 text-blue-400" />
          IP: <span className="font-mono text-blue-300">{ip}</span>
        </CardTitle>
        <div className="flex gap-1">
          {onClose && <Button size="sm" variant="ghost" onClick={onClose}>✕</Button>}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Action selector */}
        <div className="flex flex-wrap gap-1">
          {(Object.keys(ACTION_META) as ActionType[]).map(a => (
            <Button key={a} size="sm" variant={action === a ? 'default' : 'outline'}
              onClick={() => run(a)} disabled={loading}
              className={`text-xs ${action === a ? '' : ACTION_META[a].color}`}>
              {(() => { const Icon = ACTION_META[a].icon; return <Icon className="h-3 w-3 mr-1" /> })()}
              {ACTION_META[a].label}
            </Button>
          ))}
        </div>

        {loading && <div className="flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Ejecutando…</div>}
        {error && <div className="text-xs text-red-400">{error}</div>}

        {/* ── Geolocate ─────────────────────────────────────────────── */}
        {action === 'geolocate' && geo && !loading && (
          <div className="space-y-2">
            {geo.error ? (
              <div className="text-xs text-red-400">Error: {geo.error}</div>
            ) : geo.private ? (
              <div className="text-xs text-muted-foreground bg-muted rounded p-2">
                <Globe className="h-4 w-4 inline mr-1" />{geo.note}
              </div>
            ) : (
              <>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div><Globe className="h-3 w-3 inline mr-1 text-blue-400" />{geo.country} {geo.city}</div>
                  <div><Server className="h-3 w-3 inline mr-1 text-purple-400" />{geo.isp}</div>
                  <div>AS: {geo.as}</div>
                  <div>Coord: {geo.lat?.toFixed(2)}, {geo.lon?.toFixed(2)}</div>
                  {geo.timezone && <div><Clock className="h-3 w-3 inline mr-1" />{geo.timezone}</div>}
                  <div className="flex gap-1 flex-wrap">
                    {geo.proxy && <Badge className="bg-yellow-600 text-xs">PROXY</Badge>}
                    {geo.hosting && <Badge className="bg-blue-600 text-xs">HOSTING</Badge>}
                    {geo.mobile && <Badge className="bg-green-600 text-xs">MÓVIL</Badge>}
                  </div>
                </div>
                {geo.lat != null && geo.lon != null && <WorldMap lat={geo.lat} lon={geo.lon} />}
              </>
            )}
          </div>
        )}

        {/* ── Verify source ─────────────────────────────────────────── */}
        {action === 'verify' && ver && !loading && (
          <div className="space-y-1 text-xs">
            <div className="flex justify-between"><span className="text-muted-foreground">rDNS:</span><span className="font-mono">{ver.rdns || '—'}</span></div>
            {ver.asn && <div className="flex justify-between"><span className="text-muted-foreground">ASN:</span><span>{ver.asn}</span></div>}
            {ver.org && <div className="flex justify-between"><span className="text-muted-foreground">Org:</span><span>{ver.org}</span></div>}
            {ver.abuse_contact && <div className="flex justify-between"><span className="text-muted-foreground">Abuse:</span><span>{ver.abuse_contact}</span></div>}
            {ver.network_name && <div className="flex justify-between"><span className="text-muted-foreground">Net:</span><span>{ver.network_name}</span></div>}
            {ver.country && <div className="flex justify-between"><span className="text-muted-foreground">País:</span><span>{ver.country}</span></div>}
          </div>
        )}

        {/* ── Trust score ────────────────────────────────────────────── */}
        {action === 'trust' && trust && !loading && (
          <div className="space-y-2">
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span>Score de riesgo</span>
                <span className={`font-bold ${trust.score > 60 ? 'text-red-400' : trust.score > 30 ? 'text-yellow-400' : 'text-emerald-400'}`}>
                  {trust.score}/100 · {trust.label}
                </span>
              </div>
              <Progress value={trust.score} className={`h-2 ${trust.score > 60 ? '[&>div]:bg-red-500' : trust.score > 30 ? '[&>div]:bg-yellow-500' : '[&>div]:bg-emerald-500'}`} />
            </div>
            <div className="space-y-1">
              {trust.breakdown?.map((b, i) => (
                <div key={i} className="flex justify-between text-xs bg-muted rounded px-2 py-1">
                  <span>{b.f}</span>
                  <span className={b.w > 0 ? 'text-red-400' : 'text-emerald-400'}>{b.w > 0 ? '+' : ''}{b.w}</span>
                </div>
              ))}
            </div>
            {trust.tls && (
              <div className="text-xs bg-muted rounded p-2">
                <div className="flex items-center gap-1 mb-1"><ShieldCheck className="h-3 w-3" /> TLS</div>
                <div>Issuer: {trust.tls.issuer || '—'}</div>
                <div>Self-signed: {trust.tls.self_signed ? '⚠️ SÍ' : 'No'}</div>
                <div>Valido hasta: {trust.tls.valid_to || '—'}</div>
              </div>
            )}
            {trust.note && <div className="text-[10px] text-muted-foreground">{trust.note}</div>}
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

                {/* ── Sección de VIDEO ─────────────────────────────────── */}
                <div className="border-t pt-2 space-y-2">
                  <div className="flex items-center gap-2">
                    <Video className="h-4 w-4 text-orange-400" />
                    <span className="text-xs font-medium">Video en vivo</span>
                    <Button size="sm" variant="outline" className="ml-auto text-xs h-7"
                      onClick={loadVideoSources} disabled={videoLoading}>
                      {videoLoading ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Play className="h-3 w-3 mr-1" />}
                      Detectar video
                    </Button>
                  </div>

                  {/* Credenciales opcionales */}
                  <details className="text-xs" onToggle={(e) => setShowCreds((e.target as HTMLDetailsElement).open)}>
                    <summary className="cursor-pointer text-muted-foreground">Credenciales (opcional)</summary>
                    <div className="mt-1 flex gap-2">
                      <input type="text" placeholder="user" value={camUser} onChange={e => setCamUser(e.target.value)}
                        className="bg-muted rounded px-2 py-1 text-xs flex-1 border border-border" />
                      <input type="password" placeholder="pass" value={camPass} onChange={e => setCamPass(e.target.value)}
                        className="bg-muted rounded px-2 py-1 text-xs flex-1 border border-border" />
                    </div>
                  </details>

                  {/* Fuentes de video detectadas */}
                  {videoSources.length > 0 && (
                    <div className="space-y-1">
                      <div className="text-[10px] text-muted-foreground">{videoSources.length} fuente(s) de video encontrada(s):</div>
                      {videoSources.map((v, i) => (
                        <div key={i} className="bg-muted rounded p-2 text-xs space-y-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <Badge className={v.type === 'rtsp' ? 'bg-purple-600' : v.type === 'mjpeg' ? 'bg-green-600' : 'bg-blue-600'}>
                              {v.type.toUpperCase()}
                            </Badge>
                            <Badge variant="outline">:{v.port}</Badge>
                            {v.vendor && <Badge variant="secondary">{v.vendor}</Badge>}
                            <span className="text-[10px] text-muted-foreground font-mono truncate">{v.path}</span>
                          </div>
                          <div className="flex gap-1 flex-wrap">
                            {v.snapshot_url && (
                              <Button size="sm" variant="outline" className="text-[10px] h-6"
                                onClick={() => takeSnapshot(v)} disabled={snapshotLoading}>
                                <Camera className="h-3 w-3 mr-1" />Snapshot
                              </Button>
                            )}
                            {v.stream_url && (
                              <Button size="sm" variant="outline" className="text-[10px] h-6"
                                onClick={() => startStream(v)}>
                                <Play className="h-3 w-3 mr-1" />Stream
                              </Button>
                            )}
                            {v.rtsp_url && (
                              <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                                <ExternalLink className="h-3 w-3" />{v.rtsp_url} (VLC)
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  {videoSources.length === 0 && !videoLoading && (
                    <div className="text-[10px] text-muted-foreground">
                      Clic en "Detectar video" para buscar streams MJPEG y snapshots de la cámara
                    </div>
                  )}

                  {/* Visor de video — Snapshot */}
                  {snapshotUrl && !activeVideo && (
                    <div className="space-y-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-muted-foreground flex items-center gap-1">
                          <Camera className="h-3 w-3" />Snapshot
                        </span>
                        <Button size="sm" variant="ghost" className="text-xs h-6" onClick={stopStream}>✕</Button>
                      </div>
                      {snapshotLoading ? (
                        <div className="flex items-center justify-center h-32 bg-muted rounded">
                          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                        </div>
                      ) : (
                        <img src={snapshotUrl} alt="Camera snapshot"
                          className="w-full rounded border border-border max-h-64 object-contain bg-black"
                          onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
                          ref={imgRef} />
                      )}
                      <Button size="sm" variant="outline" className="text-xs h-7" onClick={() => {
                        setSnapshotUrl(null)
                        setTimeout(() => takeSnapshot(activeVideo || videoSources[0]), 100)
                      }}>
                        <RefreshCw className="h-3 w-3 mr-1" />Actualizar
                      </Button>
                    </div>
                  )}

                  {/* Visor de video — Stream MJPEG en vivo */}
                  {activeVideo && activeVideo.stream_url && (
                    <div className="space-y-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-muted-foreground flex items-center gap-1">
                          <Video className="h-3 w-3" />Stream en vivo · {activeVideo.vendor}
                        </span>
                        <div className="flex gap-1">
                          <Button size="sm" variant="ghost" className="text-xs h-6" onClick={stopStream}>Detener</Button>
                        </div>
                      </div>
                      <div className="relative rounded border border-border overflow-hidden bg-black">
                        <img src={authUrl(activeVideo.stream_url)} alt="Live MJPEG stream"
                          className="w-full max-h-64 object-contain"
                          onError={(e) => {
                            const el = e.target as HTMLImageElement
                            el.style.display = 'none'
                            const parent = el.parentElement
                            if (parent && !parent.querySelector('.stream-error')) {
                              const div = document.createElement('div')
                              div.className = 'stream-error text-xs text-red-400 p-4 text-center'
                              div.textContent = 'Stream no disponible. La cámara puede no soportar MJPEG o requiere auth.'
                              parent.appendChild(div)
                            }
                          }} />
                        <div className="absolute top-1 right-1 flex items-center gap-1 bg-black/60 rounded px-1.5 py-0.5">
                          <span className="h-1.5 w-1.5 rounded-full bg-red-500 animate-pulse" />
                          <span className="text-[10px] text-white">LIVE</span>
                        </div>
                      </div>
                      <div className="text-[10px] text-muted-foreground">
                        {activeVideo.path} · :{activeVideo.port} · {activeVideo.content_type}
                      </div>
                    </div>
                  )}
                </div>

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
                          <Badge variant="outline">{f.protocol}</Badge>
                          {f.vendor && <Badge variant="secondary">{f.vendor}</Badge>}
                        </div>
                        <pre className="text-[10px] text-muted-foreground bg-background/40 rounded p-1 max-h-20 overflow-y-auto whitespace-pre-wrap break-all">{f.evidence.slice(0, 300)}</pre>
                      </div>
                    ))}
                  </div>
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

// ── WorldMap (inline) ───────────────────────────────────────────────────────
function WorldMap({ lat, lon }: { lat: number; lon: number }) {
  const W = 360, H = 180
  const x = ((lon + 180) / 360) * W
  const y = ((90 - lat) / 180) * H
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full rounded border border-border bg-card" style={{ maxHeight: 160 }}>
      <rect width={W} height={H} fill="hsl(217 30% 10%)" />
      <g fill="hsl(217 20% 22%)" stroke="hsl(217 15% 30%)" strokeWidth="0.3">
        {/* América */}
        <path d="M40,40 L80,35 L95,60 L90,90 L80,120 L70,140 L55,145 L45,130 L35,100 L30,70 Z" />
        {/* Europa/África */}
        <path d="M160,30 L195,30 L200,55 L195,80 L185,110 L175,135 L165,150 L155,130 L150,100 L155,75 L160,50 Z" />
        {/* Asia */}
        <path d="M210,25 L280,25 L310,40 L320,60 L315,85 L290,100 L260,95 L235,75 L215,55 Z" />
        {/* Oceanía */}
        <path d="M290,120 L320,115 L325,135 L305,140 L290,135 Z" />
      </g>
      <g stroke="hsl(217 20% 22%)" strokeWidth="0.3" fill="none">
        {[0, 45, 90, 135].map(l => <line key={`v${l}`} x1={l} y1={0} x2={l} y2={H} />)}
        {[0, 40, 80, 120].map(l => <line key={`h${l}`} x1={0} y1={l} x2={W} y2={l} />)}
      </g>
      <circle cx={x} cy={y} r="3" fill="hsl(0 90% 60%)" stroke="hsl(0 0% 100%)" strokeWidth="0.5">
        <animate attributeName="r" values="3;6;3" dur="2s" repeatCount="indefinite" />
      </circle>
      <circle cx={x} cy={y} r="1.5" fill="hsl(0 0% 100%)" />
    </svg>
  )
}
