import React, { useState, useCallback, useEffect, useRef, createContext, useContext } from 'react';

const WebSocketContext = createContext(null);

export const useWebSocket = (url = null, options = {}) => {
  const {
    onMessage: onMessageCallback,
    reconnectInterval = 3000,
    maxReconnectAttempts = 10,
    autoConnect = true
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const [lastError, setLastError] = useState(null);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const [subscriptions, setSubscriptions] = useState(new Set());
  const socketRef = useRef(null);
  const reconnectTimerRef = useRef(null);

  const defaultUrl = url || `ws://${window.location.hostname}:8001/ws`;

  const connect = useCallback((wsUrl) => {
    const targetUrl = wsUrl || defaultUrl;
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) return;

    try {
      const newSocket = new WebSocket(targetUrl);
      socketRef.current = newSocket;

      newSocket.onopen = () => {
        setIsConnected(true);
        setReconnectAttempts(0);
        setLastError(null);
        console.log('[LEVIATHAN WS] Conectado');
      };

      newSocket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setLastMessage(data);
          if (onMessageCallback) onMessageCallback(data);
        } catch (error) {
          console.error('[LEVIATHAN WS] Error parsing message:', error);
          setLastMessage({ raw: event.data });
        }
      };

      newSocket.onerror = (error) => {
        console.error('[LEVIATHAN WS] Error:', error);
        setLastError(error);
      };

      newSocket.onclose = () => {
        setIsConnected(false);
        socketRef.current = null;
        if (reconnectAttempts < maxReconnectAttempts) {
          setReconnectAttempts(prev => prev + 1);
          reconnectTimerRef.current = setTimeout(() => connect(targetUrl), reconnectInterval);
        }
      };
    } catch (error) {
      console.error('[LEVIATHAN WS] Connection error:', error);
      setLastError(error);
    }
  }, [defaultUrl, reconnectInterval, maxReconnectAttempts, onMessageCallback]);

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const sendMessage = useCallback((message) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(typeof message === 'string' ? message : JSON.stringify(message));
      return true;
    }
    return false;
  }, []);

  const subscribe = useCallback((channel) => {
    setSubscriptions(prev => new Set([...prev, channel]));
    sendMessage({ type: 'subscribe', channel });
  }, [sendMessage]);

  const unsubscribe = useCallback((channel) => {
    setSubscriptions(prev => {
      const next = new Set(prev);
      next.delete(channel);
      return next;
    });
    sendMessage({ type: 'unsubscribe', channel });
  }, [sendMessage]);

  useEffect(() => {
    if (autoConnect) connect();
    return () => disconnect();
  }, [autoConnect, connect, disconnect]);

  return {
    isConnected,
    lastMessage,
    lastError,
    reconnectAttempts,
    connect,
    disconnect,
    sendMessage,
    subscribe,
    unsubscribe
  };
};

export const WebSocketProvider = ({ children }) => {
  const wsState = useWebSocket();
  return React.createElement(WebSocketContext.Provider, { value: wsState }, children);
};

export const useWebSocketContext = () => {
  const ctx = useContext(WebSocketContext);
  return ctx || useWebSocket();
};

export default useWebSocket;
