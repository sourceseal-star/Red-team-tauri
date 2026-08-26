/**
 * ARTO API Client - Cliente API para ARTO
 * ======================================
 * Provee metodos para interactuar con la API de ARTO.
 * FIX v4.1: Ahora envia Authorization Bearer + usa getBaseUrl() dinámico.
 */

import { APIResponse, Operation, Prediction, Threat, SimulationResult, SystemStats, OSINTScanResult } from '../types/arto';
import { getApiKey, getBaseUrl } from '../lib/api';

const API_BASE_URL = '/api/arto';

// 🔧 Configuración de la API
export interface APIConfig {
  baseUrl?: string;
  timeout?: number;
  headers?: Record<string, string>;
}

function _authHeaders(extra?: Record<string, string>): Record<string, string> {
  const h: Record<string, string> = { 'Content-Type': 'application/json' };
  const key = getApiKey();
  if (key) h['Authorization'] = `Bearer ${key}`;
  return { ...h, ...extra };
}

class ARTOApiClient {
  private baseUrl: string;
  private timeout: number;

  constructor(config: APIConfig = {}) {
    // FIX: Usar getBaseUrl() para resolver la URL del backend dinámicamente
    this.baseUrl = config.baseUrl || `${getBaseUrl()}${API_BASE_URL}`;
    this.timeout = config.timeout || 45000; // FIX: 15s era muy poco para Termux/movil -- causaba 'signal is aborted without reason'
  }

  // 🔧 Metodo generico para solicitudes
  private async request<T>(
    method: 'GET' | 'POST' | 'PUT' | 'DELETE',
    endpoint: string,
    data?: any
  ): Promise<APIResponse<T>> {
    const url = `${this.baseUrl}${endpoint}`;
    const options: RequestInit = {
      method,
      headers: _authHeaders(),
      body: data ? JSON.stringify(data) : undefined
    };

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(new DOMException(`Timeout tras ${this.timeout}ms`, 'TimeoutError')), this.timeout);

      const response = await fetch(url, {
        ...options,
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || errorData.detail || `HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      return {
        status: 'error',
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      };
    }
  }

  // ============================================
  // METODOS DE SISTEMA
  // ============================================

  async getStatus(): Promise<APIResponse<SystemStats>> {
    return this.request<SystemStats>('GET', '/status');
  }

  async start(): Promise<APIResponse<{ message: string }>> {
    return this.request('POST', '/start');
  }

  async stop(): Promise<APIResponse<{ message: string }>> {
    return this.request('POST', '/stop');
  }

  // ============================================
  // METODOS DE OPERACIONES
  // ============================================

  async autonomousOperation(
    operationType: string,
    target: string
  ): Promise<APIResponse<any>> {
    return this.request('POST', `/operation/${operationType}`, { target });
  }

  async getOperations(): Promise<APIResponse<{ count: number; operations: Operation[] }>> {
    return this.request('GET', '/operations');
  }

  async getOperation(operationId: string): Promise<APIResponse<{ operation: Operation }>> {
    return this.request('GET', `/operations/${operationId}`);
  }

  // ============================================
  // METODOS DE PREDICCION
  // ============================================

  async getPredictions(): Promise<APIResponse<{ count: number; predictions: Prediction[] }>> {
    return this.request('GET', '/predictions');
  }

  async predictAttacks(timeHorizon: number = 24): Promise<APIResponse<{ predictions: Prediction[] }>> {
    return this.request('POST', '/predict', { time_horizon: timeHorizon });
  }

  // ============================================
  // METODOS DE DEFENSA
  // ============================================

  async respondToThreat(threat: Threat): Promise<APIResponse<any>> {
    return this.request('POST', '/defend', { threat });
  }

  async getThreats(): Promise<APIResponse<{ count: number; threats: Threat[] }>> {
    return this.request('GET', '/threats');
  }

  // ============================================
  // METODOS DE SIMULACION
  // ============================================

  async simulateAttack(templateName: string, target: string): Promise<APIResponse<SimulationResult>> {
    return this.request('POST', '/simulate', { template_name: templateName, target });
  }

  async getTemplates(): Promise<APIResponse<{ count: number; templates: Record<string, any> }>> {
    return this.request('GET', '/templates');
  }

  // ============================================
  // METODOS DE ANALISIS
  // ============================================

  async analyzeBehavior(entity: string, behaviorData: any = {}): Promise<APIResponse<any>> {
    return this.request('POST', '/analyze/behavior', { entity, behavior_data: behaviorData });
  }

  // ============================================
  // METODOS DE ESCANEO
  // ============================================

  async scanTarget(target: string, scanType: 'full' | 'quick' | 'deep' = 'full'): Promise<APIResponse<OSINTScanResult>> {
    return this.autonomousOperation('scan', target);
  }

  // ============================================
  // METODOS DE ESTADISTICAS
  // ============================================

  async getAllStats(): Promise<APIResponse<any>> {
    return this.request('GET', '/stats');
  }

  async getMemoryStats(): Promise<APIResponse<any>> {
    return this.request('GET', '/memory/stats');
  }

  async getKnowledgeStats(): Promise<APIResponse<any>> {
    return this.request('GET', '/knowledge/stats');
  }

  // ============================================
  // METODOS DE TRAFICO
  // ============================================

  async startTrafficCapture(): Promise<APIResponse<any>> {
    return this.request('POST', '/traffic/start');
  }

  async stopTrafficCapture(): Promise<APIResponse<any>> {
    return this.request('POST', '/traffic/stop');
  }

  async getTrafficPackets(): Promise<APIResponse<any>> {
    return this.request('GET', '/traffic/packets');
  }

  async getTrafficStats(): Promise<APIResponse<any>> {
    return this.request('GET', '/traffic/stats');
  }
}

// Instancia singular
export const artoApi = new ARTOApiClient();

// Factory para crear clientes con config personalizada
export function createARTOApiClient(config: APIConfig = {}): ARTOApiClient {
  return new ARTOApiClient(config);
}
