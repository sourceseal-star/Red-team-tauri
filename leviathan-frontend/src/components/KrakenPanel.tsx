import React, { useState } from 'react'
import { apiClient } from '../api'
import './Dashboard.css'

const KrakenPanel: React.FC = () => {
  const [target, setTarget] = useState('')
  const [module, setModule] = useState('hikvision_rce')
  const [result, setResult] = useState<any>(null)
  const [running, setRunning] = useState(false)

  const modules = [
    { id: 'hikvision_rce', label: 'Hikvision RCE' },
    { id: 'dahua_backdoor', label: 'Dahua Backdoor' },
    { id: 'generic_brute', label: 'Generic Brute' },
    { id: 'kraken_integration', label: 'KRAKEN Integration' },
    { id: 'exploit_chain', label: 'Exploit Chain' },
  ]

  const run = async () => {
    if (!target.trim()) return
    setRunning(true)
    try {
      const res = await apiClient.post('/api/leviathan/exploit', {
        target: target.trim(),
        module,
      })
      setResult(res.data)
    } catch (e: any) {
      setResult({ error: e.message })
    }
    setRunning(false)
  }

  return (
    <div className="kraken-panel">
      <h1>💥 KRAKEN — Panel de Explotación</h1>
      <div className="kraken-controls">
        <input
          type="text"
          placeholder="IP objetivo (ej: 192.168.1.100)"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          className="scan-input"
        />
        <select value={module} onChange={(e) => setModule(e.target.value)} className="filter-select">
          {modules.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
        </select>
        <button onClick={run} disabled={running || !target.trim()} className="scan-btn">
          {running ? '⏳ Ejecutando...' : '⚡ Ejecutar'}
        </button>
      </div>
      {result && (
        <div className="scan-result">
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}

export default KrakenPanel
