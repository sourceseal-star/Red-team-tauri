import { useEffect, useRef, useCallback } from 'react'

interface WSOptions {
  onAlert?: (alert: any) => void
  onCameraUpdate?: () => void
}

export function useWebSocket(options: WSOptions = {}) {
  const wsRef = useRef<WebSocket | null>(null)
  const [connected, setConnected] = useState(false)

  const connect = useCallback(() => {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${proto}//${window.location.host}/ws`
    try {
      wsRef.current = new WebSocket(wsUrl)
      wsRef.current.onopen = () => setConnected(true)
      wsRef.current.onclose = () => setConnected(false)
      wsRef.current.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data)
          if (msg.type === 'alert' && options.onAlert) options.onAlert(msg.data)
          if (msg.type === 'camera_update' && options.onCameraUpdate) options.onCameraUpdate()
        } catch {}
      }
    } catch {}
  }, [])

  const disconnect = useCallback(() => {
    wsRef.current?.close()
  }, [])

  useEffect(() => {
    return () => wsRef.current?.close()
  }, [])

  return { connected, connect, disconnect }
}

import { useState } from 'react'
export default useWebSocket
