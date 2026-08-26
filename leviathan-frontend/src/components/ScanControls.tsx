import React, { useState } from 'react'
import { apiClient } from '../api'
import './Dashboard.css'

const ScanControls: React.FC = () => {
  const [target, setTarget] = useState('')
  const [modules, setModules] = useState<string[]>([])
  const [scanning, setScanning] = useState(false)
  const [result, setResult] = useState<any>(null)

  const availableModules = [
    'network_scanner', 'rtsp_scanner', 'onvif_scanner',
    'http_fingerprint', 'camera_detector', 'service_scanner'
  ]

  const toggleModule = (m: string) => {
    setModules(prev => prev.includes(m) ? prev.filter(x => x !== m) : [...prev, m])
  }

  const startScan = async () => {
    if (!target.trim()) return
    setScanning(true)
    try {
      const res = await apiClient.post('/api/leviathan/scan', {
        target: target.trim(),
        modules: modules.length > 0 ? modules : null,
      })
      setResult(res.data)
    } catch (e: any) {
      setResult({ error: e.message })
    }
    setScanning(false)
  }

  return (
    <div className="scan-controls">
      <div className="scan-input-row">
        <input
          type="text"
          placeholder="Red o IP (ej: 192.168.1.0/24)"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          className="scan-input"
        />
        <button onClick={startScan} disabled={scanning || !target.trim()} className="scan-btn">
          {scanning ? '⏳ Escaneando...' : '🚀 Iniciar Escaneo'}
        </button>
      </div>
      <div className="module-selector">
        <p className="module-label">Módulos (vacío = todos):</p>
        {availableModules.map(m => (
          <label key={m} className={`module-chip ${modules.includes(m) ? 'active' : ''}`}>
            <input type="checkbox" checked={modules.includes(m)} onChange={() => toggleModule(m)} />
            {m}
          </label>
        ))}
      </div>
      {result && (
        <div className="scan-result">
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}

export default ScanControls
