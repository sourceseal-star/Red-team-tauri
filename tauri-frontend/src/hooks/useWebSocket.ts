import { useEffect, useRef, useState, useCallback } from 'react';

export function useWebSocket(url: string) {
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<any>(null);
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    const socket = new WebSocket(url);
    ws.current = socket;

    socket.onopen = () => setConnected(true);
    socket.onclose = () => setConnected(false);
    socket.onmessage = (event) => {
      try { setLastMessage(JSON.parse(event.data)); } 
      catch { setLastMessage(event.data); }
    };

    return () => socket.close();
  }, [url]);

  const send = useCallback((data: any) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(typeof data === 'string' ? data : JSON.stringify(data));
    }
  }, []);

  return { connected, lastMessage, send };
}
