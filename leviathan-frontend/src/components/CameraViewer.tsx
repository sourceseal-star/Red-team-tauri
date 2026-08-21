import React, { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { RootState } from '../store'
import videojs from 'video.js'
import 'video.js/dist/video-js.css'

interface CameraViewerProps {
  camera?: any
}

const CameraViewer: React.FC<CameraViewerProps> = ({ camera: propCamera }) => {
  const { ip } = useParams<{ ip: string }>()
  const { cameras } = useSelector((state: RootState) => state.cameras)
  const videoRef = useRef<HTMLVideoElement>(null)
  const playerRef = useRef<any>(null)
  const [camera, setCamera] = useState<any>(propCamera || null)
  const [streamUrl, setStreamUrl] = useState<string>('')
  const [isPlaying, setIsPlaying] = useState(false)
  const [error, setError] = useState<string>('')
  const [capturing, setCapturing] = useState(false)
  const [snapshot, setSnapshot] = useState<string>('')
  
  // Obtener cámara si no se pasó como prop
  useEffect(() => {
    if (!propCamera && ip) {
      const foundCamera = cameras.find(c => c.ip === ip)
      setCamera(foundCamera || null)
    }
  }, [ip, cameras, propCamera])
  
  // Configurar stream
  useEffect(() => {
    if (camera) {
      // Intentar obtener URL RTSP o HTTP
      let url = ''
      
      // Si hay URL RTSP
      if (camera.rtsp_url) {
        // Convertir RTSP a HLS para reproducción en navegador
        // En producción, usar un proxy RTSP-to-HLS
        url = `/api/proxy/rtsp?url=${encodeURIComponent(camera.rtsp_url)}`
      }
      // Si hay URL HTTP
      else if (camera.http_url) {
        url = camera.http_url
      }
      // Construir URL HTTP genérica
      else {
        const protocol = camera.port === 443 ? 'https' : 'http'
        url = `${protocol}://${camera.ip}:${camera.port}`
      }
      
      setStreamUrl(url)
    }
  }, [camera])
  
  // Inicializar reproductor de video
  useEffect(() => {
    if (videoRef.current && streamUrl) {
      // Limpiar player anterior
      if (playerRef.current) {
        playerRef.current.dispose()
      }
      
      // Configurar opciones del player
      const options = {
        techOrder: ['html5'],
        autoplay: true,
        controls: true,
        sources: [{
          src: streamUrl,
          type: streamUrl.includes('.m3u8') ? 'application/x-mpegURL' : 
                streamUrl.includes('rtsp') ? 'rtsp/mp4' : 
                'video/mp4'
        }]
      }
      
      try {
        playerRef.current = videojs(videoRef.current, options)
        
        playerRef.current.on('play', () => setIsPlaying(true))
        playerRef.current.on('pause', () => setIsPlaying(false))
        playerRef.current.on('error', () => {
          setError('Error al cargar el stream. La cámara puede no ser accesible o el formato no es compatible.')
        })
        
        return () => {
          if (playerRef.current) {
            playerRef.current.dispose()
          }
        }
      } catch (err) {
        setError('Error al inicializar el reproductor')
      }
    }
  }, [streamUrl])
  
  // Capturar frame
  const captureFrame = async () => {
    if (!videoRef.current) return
    
    setCapturing(true)
    try {
      const canvas = document.createElement('canvas')
      const video = videoRef.current
      
      canvas.width = video.videoWidth || 640
      canvas.height = video.videoHeight || 480
      
      const ctx = canvas.getContext('2d')
      if (ctx) {
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
        const dataUrl = canvas.toDataURL('image/png')
        setSnapshot(dataUrl)
      }
    } catch (err) {
      setError('Error al capturar el frame')
    } finally {
      setCapturing(false)
    }
  }
  
  // Descargar snapshot
  const downloadSnapshot = () => {
    if (snapshot) {
      const link = document.createElement('a')
      link.href = snapshot
      link.download = `camera_${camera?.ip}_${new Date().getTime()}.png`
      link.click()
    }
  }
  
  if (!camera) {
    return (
      <div className="camera-viewer">
        <div className="error-state">
          <h3>Cámara no encontrada</h3>
          <p>No se encontró la cámara con IP {ip}</p>
        </div>
      </div>
    )
  }
  
  return (
    <div className="camera-viewer">
      <div className="viewer-header">
        <h2>🎥 {camera.vendor} {camera.model}</h2>
        <p className="viewer-ip">{camera.ip}:{camera.port}</p>
        
        <div className="viewer-status">
          <span className={`status-indicator ${isPlaying ? 'playing' : 'stopped'}`}>
            {isPlaying ? '▶️ Reproduciendo' : '⏸️ Detenido'}
          </span>
          {camera.is_accessible && (
            <span className="status-indicator accessible">🔓 Accesible</span>
          )}
          {camera.is_vulnerable && (
            <span className="status-indicator vulnerable">⚠️ Vulnerable</span>
          )}
        </div>
      </div>
      
      {error ? (
        <div className="error-message">{error}</div>
      ) : (
        <>
          <div className="video-container">
            <video 
              ref={videoRef} 
              className="video-js vjs-default-skin"
              controls
              autoPlay
              playsInline
              muted
            >
              <p className="vjs-no-js">
                Para ver este video, por favor habilita JavaScript o considera 
                <a href="https://videojs.com/html5-video-support/" target="_blank">
                  actualizar tu navegador
                </a>
              </p>
            </video>
          </div>
          
          <div className="viewer-controls">
            <button 
              className="control-btn capture"
              onClick={captureFrame}
              disabled={capturing}
            >
              {capturing ? 'Capturando...' : '📸 Capturar Frame'}
            </button>
            
            {snapshot && (
              <button 
                className="control-btn download"
                onClick={downloadSnapshot}
              >
                💾 Descargar Snapshot
              </button>
            )}
          </div>
          
          {snapshot && (
            <div className="snapshot-preview">
              <h4>Vista Previa:</h4>
              <img src={snapshot} alt="Snapshot" className="snapshot-image" />
            </div>
          )}
          
          <div className="camera-details">
            <h3>Detalles de la Cámara</h3>
            <div className="details-grid">
              <div className="detail-item">
                <span className="detail-label">Vendor:</span>
                <span className="detail-value">{camera.vendor || 'Desconocido'}</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Modelo:</span>
                <span className="detail-value">{camera.model || 'Desconocido'}</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">IP:</span>
                <span className="detail-value">{camera.ip}</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Puerto:</span>
                <span className="detail-value">{camera.port}</span>
              </div>
              {camera.firmware_version && (
                <div className="detail-item">
                  <span className="detail-label">Firmware:</span>
                  <span className="detail-value">{camera.firmware_version}</span>
                </div>
              )}
              {camera.serial_number && (
                <div className="detail-item">
                  <span className="detail-label">Número de Serie:</span>
                  <span className="detail-value">{camera.serial_number}</span>
                </div>
              )}
              {camera.credentials && (
                <div className="detail-item">
                  <span className="detail-label">Credenciales:</span>
                  <span className="detail-value">{camera.credentials}</span>
                </div>
              )}
            </div>
            
            {camera.services && camera.services.length > 0 && (
              <div className="services-section">
                <h4>Servicios Detectados:</h4>
                <div className="services-tags">
                  {camera.services.map((service: any, index: number) => (
                    <span key={index} className="service-tag">
                      {service.service} (Puerto: {service.port})
                    </span>
                  ))}
                </div>
              </div>
            )}
            
            {camera.vulnerabilities && camera.vulnerabilities.length > 0 && (
              <div className="vulnerabilities-section">
                <h4>Vulnerabilidades Conocidas:</h4>
                <ul className="vulnerabilities-list">
                  {camera.vulnerabilities.map((vuln: string, index: number) => (
                    <li key={index}>{vuln}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}

export default CameraViewer
