import { useEffect, useState } from 'react';

export function useWebSocket(path: string) {
  const [ws, setWs] = useState<WebSocket | null>(null);

  useEffect(() => {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${proto}//${window.location.host}${path}`;
    let socket: WebSocket | null = null;
    let retry: ReturnType<typeof setTimeout>;

    const connect = () => {
      try {
        socket = new WebSocket(url);
        socket.onopen = () => console.log(`[WS] ${path} connected`);
        socket.onclose = () => {
          console.log(`[WS] ${path} closed, retrying in 5s...`);
          retry = setTimeout(connect, 5000);
        };
        socket.onerror = () => socket?.close();
        setWs(socket);
      } catch {
        retry = setTimeout(connect, 5000);
      }
    };

    connect();

    return () => {
      clearTimeout(retry);
      socket?.close();
    };
  }, [path]);

  return ws;
}
