/**
 * WebSocket Client - Cliente WebSocket para ARTO
 * ==============================================
 * Proporciona conexión en tiempo real con el backend ARTO.
 */

import { WebSocketEvent, WebSocketEventType } from '../types/arto';

export type WebSocketMessageHandler = (event: WebSocketEvent) => void;
export type WebSocketErrorHandler = (error: Event) => void;
export type WebSocketCloseHandler = (event: CloseEvent) => void;

export interface WebSocketConfig {
  url?: string;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

class ARTOWebSocketClient {
  private socket: WebSocket | null = null;
  private url: string;
  private reconnectInterval: number;
  private maxReconnectAttempts: number;
  private reconnectAttempts: number = 0;
  private isConnected: boolean = false;
  private messageHandlers: WebSocketMessageHandler[] = [];
  private errorHandlers: WebSocketErrorHandler[] = [];
  private closeHandlers: WebSocketCloseHandler[] = [];
  private reconnectTimeout: ReturnType<typeof setInterval> | null = null;

  constructor(config: WebSocketConfig = {}) {
    this.url = config.url || (() => {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const base = localStorage.getItem('backend_base_url') || '';
      // Si hay URL custom, extraer host de ahi; si no, usar el actual
      if (base) {
        try {
          const u = new URL(base);
          return `${proto}//${u.host}/ws`;
        } catch { /* fallback abajo */ }
      }
      return `${proto}//${window.location.host}/ws`;
    })();
    this.reconnectInterval = config.reconnectInterval || 5000; // 5 segundos
    this.maxReconnectAttempts = config.maxReconnectAttempts || 10;
  }

  // ============================================
  // MÉTODOS DE CONEXIÓN
  // ============================================

  /** Conecta al WebSocket */
  connect(): void {
    if (this.isConnected || this.socket) {
      return;
    }

    try {
      this.socket = new WebSocket(this.url);
      this.setupEventHandlers();
    } catch (error) {
      this.handleConnectionError(error as Event);
    }
  }

  /** Desconecta el WebSocket */
  disconnect(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }

    this.isConnected = false;
    this.reconnectAttempts = 0;
  }

  /** Reconecta el WebSocket */
  reconnect(): void {
    this.disconnect();
    this.connect();
  }

  // ============================================
  // CONFIGURACIÓN DE EVENTOS
  // ============================================

  private setupEventHandlers(): void {
    if (!this.socket) return;

    this.socket.onopen = () => {
      this.isConnected = true;
      this.reconnectAttempts = 0;
      console.log('✅ WebSocket conectado a ARTO');
      
      // Suscribirse a eventos
      this.send({ action: 'subscribe' });
    };

    this.socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const webSocketEvent: WebSocketEvent = {
          type: data.type as WebSocketEventType,
          data: data.data
        };
        
        this.messageHandlers.forEach(handler => handler(webSocketEvent));
      } catch (error) {
        console.error('❌ Error al procesar mensaje WebSocket:', error);
      }
    };

    this.socket.onerror = (error) => {
      this.handleConnectionError(error);
    };

    this.socket.onclose = (event) => {
      this.handleConnectionClose(event);
    };
  }

  private handleConnectionError(error: Event): void {
    this.isConnected = false;
    this.errorHandlers.forEach(handler => handler(error));
    
    // Intentar reconectar
    this.scheduleReconnect();
  }

  private handleConnectionClose(event: CloseEvent): void {
    this.isConnected = false;
    this.closeHandlers.forEach(handler => handler(event));
    
    // Intentar reconectar
    this.scheduleReconnect();
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('❌ Máximo de intentos de reconexión alcanzado');
      return;
    }

    this.reconnectAttempts++;
    console.log(`🔄 Intentando reconectar (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);

    this.reconnectTimeout = setTimeout(() => {
      this.connect();
    }, this.reconnectInterval);
  }

  // ============================================
  // ENVÍO DE MENSAJES
  // ============================================

  /** Envía un mensaje al servidor */
  send(message: any): void {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      console.warn('⚠️ WebSocket no está conectado');
      return;
    }

    try {
      this.socket.send(JSON.stringify(message));
    } catch (error) {
      console.error('❌ Error al enviar mensaje:', error);
    }
  }

  // ============================================
  // REGISTRO DE MANEJADORES
  // ============================================

  /** Registra un manejador de mensajes */
  onMessage(handler: WebSocketMessageHandler): void {
    this.messageHandlers.push(handler);
  }

  /** Elimina un manejador de mensajes */
  offMessage(handler: WebSocketMessageHandler): void {
    this.messageHandlers = this.messageHandlers.filter(h => h !== handler);
  }

  /** Registra un manejador de errores */
  onError(handler: WebSocketErrorHandler): void {
    this.errorHandlers.push(handler);
  }

  /** Elimina un manejador de errores */
  offError(handler: WebSocketErrorHandler): void {
    this.errorHandlers = this.errorHandlers.filter(h => h !== handler);
  }

  /** Registra un manejador de cierre */
  onClose(handler: WebSocketCloseHandler): void {
    this.closeHandlers.push(handler);
  }

  /** Elimina un manejador de cierre */
  offClose(handler: WebSocketCloseHandler): void {
    this.closeHandlers = this.closeHandlers.filter(h => h !== handler);
  }

  // ============================================
  // GETTERS
  // ============================================

  /** Obtiene el estado de conexión */
  getStatus(): { isConnected: boolean; reconnectAttempts: number } {
    return {
      isConnected: this.isConnected,
      reconnectAttempts: this.reconnectAttempts
    };
  }
}

// 🎯 Instancia singular
export const artoWebSocket = new ARTOWebSocketClient();

// 🎯 Factory para crear clientes con configuración personalizada
export function createARTOWebSocketClient(config: WebSocketConfig = {}): ARTOWebSocketClient {
  return new ARTOWebSocketClient(config);
}
