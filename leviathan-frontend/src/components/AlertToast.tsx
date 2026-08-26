import React from 'react'

interface Alert {
  id: number
  severity: string
  title: string
  description: string
}

interface Props {
  alerts: Alert[]
  onDismiss: () => void
}

export const AlertToast: React.FC<Props> = ({ alerts, onDismiss }) => {
  if (!alerts.length) return null
  return (
    <div className="alert-toast-container">
      {alerts.slice(-3).map(alert => (
        <div key={alert.id} className={`alert-toast severity-${alert.severity}`} onClick={onDismiss}>
          <span className="toast-title">{alert.title}</span>
          <span className="toast-desc">{alert.description}</span>
          <span className="toast-close">✕</span>
        </div>
      ))}
    </div>
  )
}

export default AlertToast
