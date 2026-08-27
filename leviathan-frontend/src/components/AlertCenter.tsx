import React from 'react'

interface Alert {
  id: number
  severity: string
  title: string
  description: string
  source: string
  created_at: string
}

interface Props {
  alerts: Alert[]
  showAllLink?: boolean
}

const AlertCenter: React.FC<Props> = ({ alerts, showAllLink }) => {
  const getSeverityIcon = (s: string) => {
    switch (s) {
      case 'critical': return '🔴'
      case 'high': return '🟠'
      case 'medium': return '🟡'
      case 'low': return '🟢'
      default: return '⚪'
    }
  }

  return (
    <div className="alert-center">
      {alerts.map(alert => (
        <div key={alert.id} className={`alert-item severity-${alert.severity}`}>
          <span className="alert-icon">{getSeverityIcon(alert.severity)}</span>
          <div className="alert-content">
            <div className="alert-title">{alert.title}</div>
            <div className="alert-desc">{alert.description}</div>
            <div className="alert-meta">
              <span className="alert-source">{alert.source}</span>
              <span className="alert-time">{new Date(alert.created_at).toLocaleString('es-CO')}</span>
            </div>
          </div>
        </div>
      ))}
      {alerts.length === 0 && (
        <div className="alert-empty">No hay alertas activas</div>
      )}
    </div>
  )
}

export default AlertCenter
