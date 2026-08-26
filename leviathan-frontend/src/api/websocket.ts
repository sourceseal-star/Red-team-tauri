import React, { createContext, useContext, useEffect, useRef, useState } from 'react'

interface WSContextType {
  connected: boolean
  alerts: any[]
}

const WebSocketContext = createContext<WSContextType>({ connected: false, alerts: [] })

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [connected, setConnected] = useState(false)
  const [alerts, setAlerts] = useState<any[]>([])
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${proto}//${window.location.host}/ws`
    
    try {
      wsRef.current = new WebSocket(wsUrl)
      wsRef.current.onopen = () => setConnected(true)
      wsRef.current.onclose = () => {
        setConnected(false)
        setTimeout(() => wsRef.current?.close(), 100)
      }
      wsRef.current.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data)
          if (msg.type === 'alert') setAlerts(prev => [...prev, msg.data])
        } catch {}
      }
    } catch {}

    return () => wsRef.current?.close()
  }, [])

  return (
    <WebSocketContext.Provider value={{ connected, alerts }}>
      {children}
    </WebSocketContext.Provider>
  )
}

export const useWSContext = () => useContext(WebSocketContext)
export default WebSocketProvider
