import React, { useEffect, useState } from 'react'
import { useSelector, useDispatch } from 'react-redux'
import { RootState, AppDispatch } from '../store'
import { fetchCameras } from '../store/slices/cameras'
import CameraCard from './CameraCard'
import CameraViewer from './CameraViewer'
import { useWebSocket } from '../hooks/useWebSocket'

const LiveGrid: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>()
  const { cameras, loading } = useSelector((state: RootState) => state.cameras)
  const [selectedCamera, setSelectedCamera] = useState<any>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [filterVendor, setFilterVendor] = useState<string>('all')
  const [filterAccessible, setFilterAccessible] = useState<string>('all')
  
  // Cargar cámaras
  useEffect(() => {
    dispatch(fetchCameras())
  }, [dispatch])
  
  // WebSocket para actualizaciones en tiempo real
  useWebSocket({
    onCameraUpdate: () => {
      dispatch(fetchCameras())
    }
  })
  
  // Filtrar cámaras
  const filteredCameras = cameras.filter(camera => {
    const matchesSearch = 
      camera.ip.toLowerCase().includes(searchTerm.toLowerCase()) ||
      camera.vendor?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      camera.model?.toLowerCase().includes(searchTerm.toLowerCase())
    
    const matchesVendor = filterVendor === 'all' || 
      camera.vendor?.toLowerCase().includes(filterVendor.toLowerCase())
    
    const matchesAccessible = filterAccessible === 'all' || 
      (filterAccessible === 'accessible' && camera.is_accessible) ||
      (filterAccessible === 'not_accessible' && !camera.is_accessible)
    
    return matchesSearch && matchesVendor && matchesAccessible
  })
  
  // Obtener vendors únicos
  const vendors = Array.from(new Set(
    cameras.map(c => c.vendor).filter(v => v) as string[]
  ))
  
  return (
    <div className="live-grid">
      <div className="live-grid-header">
        <h1>🎥 Cámaras en Vivo</h1>
        <p className="live-grid-subtitle">
          Visualización en tiempo real de cámaras IP detectadas
        </p>
      </div>
      
      {/* Controles de filtro */}
      <div className="filters">
        <div className="filter-group">
          <input
            type="text"
            placeholder="Buscar por IP, vendor o modelo..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="filter-input"
          />
        </div>
        
        <div className="filter-group">
          <select
            value={filterVendor}
            onChange={(e) => setFilterVendor(e.target.value)}
            className="filter-select"
          >
            <option value="all">Todos los Vendors</option>
            {vendors.map(vendor => (
              <option key={vendor} value={vendor}>{vendor}</option>
            ))}
          </select>
        </div>
        
        <div className="filter-group">
          <select
            value={filterAccessible}
            onChange={(e) => setFilterAccessible(e.target.value)}
            className="filter-select"
          >
            <option value="all">Todos</option>
            <option value="accessible">Accesibles</option>
            <option value="not_accessible">No Accesibles</option>
          </select>
        </div>
      </div>
      
      {/* Estadísticas */}
      <div className="live-stats">
        <div className="stat">
          <span className="stat-number">{filteredCameras.length}</span>
          <span className="stat-label">Cámaras Filtradas</span>
        </div>
        <div className="stat">
          <span className="stat-number">{cameras.filter(c => c.is_accessible).length}</span>
          <span className="stat-label">Accesibles</span>
        </div>
        <div className="stat">
          <span className="stat-number">{cameras.filter(c => c.is_vulnerable).length}</span>
          <span className="stat-label">Vulnerables</span>
        </div>
      </div>
      
      {/* Grid de cámaras */}
      {loading ? (
        <div className="loading">Cargando cámaras...</div>
      ) : filteredCameras.length > 0 ? (
        <div className="camera-grid">
          {filteredCameras.map(camera => (
            <CameraCard 
              key={`${camera.ip}-${camera.port}`} 
              camera={camera} 
              onClick={() => setSelectedCamera(camera)}
              showActions={true}
            />
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <p>No se encontraron cámaras con los filtros actuales.</p>
        </div>
      )}
      
      {/* Visualizador de cámara seleccionada */}
      {selectedCamera && (
        <div className="camera-modal">
          <div className="camera-modal-content">
            <button 
              className="modal-close" 
              onClick={() => setSelectedCamera(null)}
            >
              ✕
            </button>
            <CameraViewer camera={selectedCamera} />
          </div>
        </div>
      )}
    </div>
  )
}

export default LiveGrid
