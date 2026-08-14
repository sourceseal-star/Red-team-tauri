import { useState, useCallback } from 'react'
import { api, authUrl, getApiKey, setApiKey } from '../lib/api'
import { Button } from './ui/button'
import { Badge } from './ui/badge'
import { Loader2, Wifi, ScanLine, Camera, ChevronRight, Key, X } from 'lucide-react'

interface Device {
  ip: string
  type: string
  vendor: string | null
  ports_open: string[]
  evidence?: any[]
}

export function NetworkScanner() {
  const [cidr, setCidr] = useState('')
  const [scanning, setScanning] = useState(false)
  const [results, setResults] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null)
  const [videoSources, setVideoSources] = useState<any[]>([])
  const [videoLoading, setVideoLoading] = useState(false)
  const [showKey, setShowKey] = useState(false)
  const [keyInput, setKeyInput] = useState(getApiKey() || '')

  const doScan = useCallback(async (target?: string) => {
    const network = target || cidr
    if (!network) return
    setScanning(true)
    setError(null)
    setResults(null)
    setSelectedDevice(null)
    setVideoSources([])
    try {
      const r = await api.scanNetwork(network)
      setResults(r)
    } catch (e: any) {
      setError(e?.message || 'Error escaneando red')
    } finally {
      setScanning(false)
    }
  }, [cidr])

  const doScanLocal = useCallback(async () => {
    setScanning(true)
    setError(null)
    setResults(null)
    setSelectedDevice(null)
    setVideoSources([])
    try {
      const r = await api.scanLocal()
      setResults(r)
      setCidr(r.detected_cidr || '')
    } catch (e: any) {
      setError(e?.message || 'Error escaneando red local')
    } finally {
      setScanning(false)
    }
  }, [])

  const detectVideo = useCallback(async (ip: string) => {
    setVideoLoading(true)
    setVideoSources([])
    try {
      const r = await api.ipVideoUrls(ip)
      setVideoSources(r.video_sources || [])
    } catch (e: any) {
      setError(e?.message || 'Error detectando video')
    } finally {
      setVideoLoading(false)
    }
  }, [])

  const saveKey = () => {
    setApiKey(keyInput.trim())
    setShowKey(false)
  }

  const cameras = results?.cameras || []
  const allDevices = results?.all_devices || []
  const hasKey = !!getApiKey()

  return (
    <div className="space-y-3">
      {/* API Key input */}
      {!hasKey && (
        <div className="bg-amber-950/30 border border-amber-800 rounded p-2 space-y-2">
          <div className="text-xs text-amber-400 flex items-center gap-1">
            <Key className="h-3 w-3" /> Se requiere API key del backend
          </div>
          <div className="flex gap-2">
            <input type="password" placeholder="REDTEAM_API_KEY"
              value={keyInput} onChange={e => setKeyInput(e.target.value)}
              className="bg-muted rounded px-2 py-1 text-xs flex-1 border border-border" />
            <Button size="sm" onClick={saveKey}>Guardar</Button>
          </div>
        </div>
      )}

      {/* Input de red */}
      <div className="flex gap-2 flex-wrap items-end">
        <div className="flex-1 min-w-[200px]">
          <label className="text-[10px] text-muted-foreground uppercase tracking-wider">Red a escanear (CIDR)</label>
          <input
            type="text"
            placeholder="192.168.1.0/24"
            value={cidr}
            onChange={e => setCidr(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && doScan()}
            className="bg-muted rounded px-3 py-2 text-sm w-full border border-border font-mono"
          />
        </div>
        <Button size="sm" onClick={() => doScan()} disabled={scanning || !cidr || !hasKey}>
          {scanning ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <ScanLine className="h-4 w-4 mr-1" />}
          Escanear
        </Button>
        <Button size="sm" variant="outline" onClick={doScanLocal} disabled={scanning || !hasKey}>
          <Wifi className="h-4 w-4 mr-1" />
          Auto-detectar
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setShowKey(!showKey)} className="px-2">
          <Key className="h-4 w-4" />
        </Button>
      </div>

      {/* Key editor */}
      {showKey && (
        <div className="flex gap-2 items-center bg-muted rounded p-2">
          <input type="password" placeholder="API key"
            value={keyInput} onChange={e => setKeyInput(e.target.value)}
            className="bg-background rounded px-2 py-1 text-xs flex-1 border border-border" />
          <Button size="sm" onClick={saveKey}>OK</Button>
          <Button size="sm" variant="ghost" onClick={() => setShowKey(false)}>
            <X className="h-3 w-3" />
          </Button>
        </div>
      )}

      {/* Sugerencias rápidas */}
      <div className="flex gap-1 flex-wrap">
        {['192.168.0.0/24', '192.168.1.0/24', '10.0.0.0/24', '172.16.0.0/24'].map(c => (
          <button key={c} onClick={() => { setCidr(c); doScan(c) }}
            className="text-[10px] text-muted-foreground hover:text-foreground bg-muted rounded px-2 py-1 border border-border"
            disabled={scanning || !hasKey}>
            {c}
          </button>
        ))}
      </div>

      {/* Error */}
      {error && <div className="text-xs text-red-400 bg-red-950 rounded p-2 border border-red-800">{error}</div>}

      {/* Scanning indicator */}
      {scanning && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Escaneando red... (puede tardar 30-90s para /24)
        </div>
      )}

      {/* Resultados */}
      {results && !scanning && (
        <div className="space-y-2">
          {/* Resumen */}
          <div className="grid grid-cols-4 gap-2">
            <div className="bg-muted rounded p-2 text-center">
              <div className="text-lg font-bold">{results.total_ips || results.total_scanned}</div>
              <div className="text-[10px] text-muted-foreground">IPs</div>
            </div>
            <div className="bg-muted rounded p-2 text-center">
              <div className="text-lg font-bold text-green-400">{results.devices_with_open_ports}</div>
              <div className="text-[10px] text-muted-foreground">Dispositivos</div>
            </div>
            <div className="bg-muted rounded p-2 text-center">
              <div className="text-lg font-bold text-orange-400">{results.cameras_found}</div>
              <div className="text-[10px] text-muted-foreground">Cámaras</div>
            </div>
            <div className="bg-muted rounded p-2 text-center">
              <div className="text-lg font-bold text-cyan-400">{cameras.filter((c: Device) => c.type === 'radio/voip' || c.type === 'radio').length}</div>
              <div className="text-[10px] text-muted-foreground">Radio/VoIP</div>
            </div>
          </div>

          {/* Info de red detectada */}
          {results.detected_cidr && (
            <div className="text-[10px] text-muted-foreground">
              Red detectada: <span className="font-mono">{results.detected_cidr}</span> (IP: {results.detected_ip})
            </div>
          )}

          {/* Cámaras detectadas */}
          {cameras.length > 0 && (
            <div className="space-y-1">
              <div className="text-xs font-medium text-orange-400 flex items-center gap-1">
                <Camera className="h-3 w-3" /> Cámaras IP encontradas ({cameras.length})
              </div>
              {cameras.map((cam: Device, i: number) => (
                <div key={i} className="bg-muted rounded border border-orange-800/30 p-2 space-y-1">
                  <div className="flex items-center gap-2 text-xs">
                    <span className="font-mono font-bold">{cam.ip}</span>
                    {cam.vendor && <Badge variant="secondary">{cam.vendor}</Badge>}
                    <Badge variant="outline">{cam.type}</Badge>
                    <Button size="sm" variant="ghost" className="ml-auto h-6 text-[10px]"
                      onClick={() => { setSelectedDevice(cam); detectVideo(cam.ip) }} disabled={videoLoading}>
                      <Camera className="h-3 w-3 mr-1" />Video
                    </Button>
                  </div>
                  <div className="flex gap-1 flex-wrap">
                    {cam.ports_open?.map((p: string, j: number) => (
                      <Badge key={j} className="bg-orange-600/50 text-[10px]">{p}</Badge>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Todos los dispositivos con puertos abiertos */}
          {allDevices.length > 0 && (
            <details className="text-xs">
              <summary className="cursor-pointer text-muted-foreground">
                Todos los dispositivos ({allDevices.length})
              </summary>
              <div className="mt-1 space-y-1">
                {allDevices.map((dev: Device, i: number) => (
                  <div key={i} className="bg-muted rounded p-1.5 flex items-center gap-2">
                    <span className="font-mono text-xs">{dev.ip}</span>
                    {dev.vendor && <Badge variant="secondary" className="text-[9px]">{dev.vendor}</Badge>}
                    <Badge variant="outline" className="text-[9px]">{dev.type}</Badge>
                    <div className="ml-auto flex gap-1">
                      {dev.ports_open?.slice(0, 5).map((p: string, j: number) => (
                        <span key={j} className="text-[9px] font-mono text-muted-foreground">{p}</span>
                      ))}
                      {dev.ports_open?.length > 5 && <span className="text-[9px] text-muted-foreground">+{dev.ports_open.length - 5}</span>}
                    </div>
                    <Button size="sm" variant="ghost" className="h-5 text-[9px] px-1"
                      onClick={() => { setSelectedDevice(dev); detectVideo(dev.ip) }} disabled={videoLoading}>
                      <ChevronRight className="h-3 w-3" />
                    </Button>
                  </div>
                ))}
              </div>
            </details>
          )}

          {/* Sin resultados */}
          {cameras.length === 0 && allDevices.length === 0 && (
            <div className="text-xs text-muted-foreground bg-muted rounded p-3 text-center">
              No se encontraron dispositivos con puertos abiertos.
              <br />
              <span className="text-[10px]">Intenta con otro rango o usa "Auto-detectar". Verifica que el backend esté en la misma red que las cámaras.</span>
            </div>
          )}
        </div>
      )}

      {/* Panel de video del dispositivo seleccionado */}
      {selectedDevice && (
        <div className="border rounded p-3 space-y-2">
          <div className="flex items-center gap-2">
            <Camera className="h-4 w-4 text-orange-400" />
            <span className="text-xs font-medium font-mono">{selectedDevice.ip}</span>
            <Button size="sm" variant="ghost" className="ml-auto h-6 text-[10px]" onClick={() => { setSelectedDevice(null); setVideoSources([]) }}>
              <X className="h-3 w-3" />
            </Button>
          </div>

          {videoLoading && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Probando 429 combinaciones (39 paths × 11 puertos)...
            </div>
          )}

          {videoSources.length > 0 && (
            <div className="space-y-1">
              <div className="text-[10px] text-green-400">{videoSources.length} fuente(s) de video encontrada(s)</div>
              {videoSources.map((v, i) => (
                <div key={i} className="bg-muted rounded p-2 text-xs space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge className={v.type === 'rtsp' ? 'bg-purple-600' : v.type === 'mjpeg' ? 'bg-green-600' : 'bg-blue-600'}>
                      {v.type?.toUpperCase()}
                    </Badge>
                    <Badge variant="outline">:{v.port}</Badge>
                    {v.vendor && <Badge variant="secondary">{v.vendor}</Badge>}
                    <span className="text-[10px] text-muted-foreground font-mono truncate">{v.path}</span>
                  </div>
                  <div className="flex gap-1 flex-wrap">
                    {v.snapshot_url && (
                      <a href={authUrl(v.snapshot_url)} target="_blank" rel="noopener noreferrer">
                        <Button size="sm" variant="outline" className="text-[10px] h-6">
                          Ver snapshot
                        </Button>
                      </a>
                    )}
                    {v.stream_url && (
                      <a href={authUrl(v.stream_url)} target="_blank" rel="noopener noreferrer">
                        <Button size="sm" variant="outline" className="text-[10px] h-6">
                          Ver stream
                        </Button>
                      </a>
                    )}
                    {v.rtsp_url && (
                      <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                        {v.rtsp_url} (VLC)
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {!videoLoading && videoSources.length === 0 && (
            <div className="text-[10px] text-muted-foreground">
              No se detectaron fuentes de video HTTP en {selectedDevice.ip}.
              <br />
              Si la cámara tiene RTSP, prueba abrir rtsp://{selectedDevice.ip}:554/ en VLC.
            </div>
          )}
        </div>
      )}
    </div>
  )
}
