import React from 'react'
import { useNavigate } from 'react-router-dom'

interface CameraCardProps {
  camera: any
  onClick?: () => void
  showActions?: boolean
}

const CameraCard: React.FC<CameraCardProps> = ({ camera, onClick, showActions = false }) => {
  const navigate = useNavigate()
  
  const getVendorColor = (vendor?: string) => {
    if (!vendor) return '#666'
    
    const vendorLower = vendor.toLowerCase()
    if (vendorLower.includes('hikvision')) return '#667eea'
    if (vendorLower.includes('dahua')) return '#764ba2'
    if (vendorLower.includes('axis')) return '#17a2b8'
    if (vendorLower.includes('uniview')) return '#28a745'
    return '#ffc107'
  }
  
  const handleClick = () => {
    if (onClick) {
      onClick()
    } else {
      navigate(`/camera/${camera.ip}`)
    }
  }
  
  const handleKrakenClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    navigate(`/kraken?target=${camera.ip}`)
  }
  
  const handleScanClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    navigate(`/scan?target=${camera.ip}`)
  }
  
  return (
    <div 
      className={`camera-card ${camera.is_accessible ? 'accessible' : ''} ${camera.is_vulnerable ? 'vulnerable' : ''}`}
      onClick={handleClick}
    >
      <div className="camera-header">
        <div className="camera-icon" style={{ backgroundColor: getVendorColor(camera.vendor) }}>
          {camera.vendor ? camera.vendor.charAt(0).toUpperCase() : '?'}
        </div>
        <div className="camera-status">
          {camera.is_accessible ? (
            <span className="status-badge accessible">🔓 Accesible</span>
          ) : (
            <span className="status-badge not-accessible">🔒 No Accesible</span>
          )}
          {camera.is_vulnerable && (
            <span className="status-badge vulnerable">⚠️ Vulnerable</span>
          )}
        </div>
      </div>
      
      <div className="camera-body">
        <h3 className="camera-vendor">{camera.vendor || 'Desconocido'}</h3>
        <p className="camera-model">{camera.model || 'Modelo desconocido'}</p>
        <p className="camera-ip">{camera.ip}:{camera.port}</p>
        
        {camera.credentials && (
          <p className="camera-credentials">
            <strong>Credenciales:</strong> {camera.credentials}
          </p>
        )}
      </div>
      
      <div className="camera-footer">
        <div className="camera-services">
          {camera.services?.map((service: any, index: number) => (
            <span key={index} className="service-tag">{service.service}</span>
          ))}
        </div>
      </div>
      
      {showActions && (
        <div className="camera-actions">
          <button 
            className="action-btn view"
            onClick={handleClick}
          >
            Ver
          </button>
          <button 
            className="action-btn kraken"
            onClick={handleKrakenClick}
          >
            KRAKEN
          </button>
          <button 
            className="action-btn scan"
            onClick={handleScanClick}
          >
            Escanear
          </button>
        </div>
      )}
    </div>
  )
}

export default CameraCard
