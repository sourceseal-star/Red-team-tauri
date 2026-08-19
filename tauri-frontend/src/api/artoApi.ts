/**
 * ARTO API Client - Cliente API para ARTO
 * ======================================
 * Proporciona métodos para interactuar con la API de ARTO.
 */

import { APIResponse, Operation, Prediction, Threat, Report, SimulationResult, SystemStats, OSINTScanResult } from '../types/arto';

const API_BASE_URL = '/api/arto';

// 🎯 Configuración de la API
export interface APIConfig {
  baseUrl?: string;
  timeout?: number;
  headers?: Record<string, string>;
}

class ARTOApiClient {
  private baseUrl: string;
  private timeout: number;
  private headers: Record<string, string>;

  constructor(config: APIConfig = {}) {
    this.baseUrl = config.baseUrl || API_BASE_URL;
    this.timeout = config.timeout || 10000;
    this.headers = {
      'Content-Type': 'application/json',
      ...config.headers
    };
  }

  // 🔧 Método genérico para solicitudes
  private async request<T>(
    method: 'GET' | 'POST' | 'PUT' | 'DELETE',
    endpoint: string,
    data?: any
  ): Promise<APIResponse<T>> {
    const url = `${this.baseUrl}${endpoint}`;
    const options: RequestInit = {
      method,
      headers: this.headers,
      body: data ? JSON.stringify(data) : undefined
    };

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), this.timeout);
      
      const response = await fetch(url, {
        ...options,
        signal: controller.signal
      });
      
      clearTimeout(timeoutId);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
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
  // MÉTODOS DE SISTEMA
  // ============================================

  /** Obtiene el estado del sistema ARTO */
  async getStatus(): Promise<APIResponse<SystemStats>> {
    return this.request<SystemStats>('GET', '/status');
  }

  /** Inicia el sistema ARTO */
  async start(): Promise<APIResponse<{ message: string }>> {
    return this.request('POST', '/start');
  }

  /** Detiene el sistema ARTO */
  async stop(): Promise<APIResponse<{ message: string }>> {
    return this.request('POST', '/stop');
  }

  // ============================================
  // MÉTODOS DE OPERACIONES
  // ============================================

  /** Ejecuta una operación autónoma */
  async autonomousOperation(
    operationType: string,
    target: string
  ): Promise<APIResponse<any>> {
    return this.request('POST', `/operation/${operationType}`, { target });
  }

  /** Obtiene todas las operaciones */
  async getOperations(): Promise<APIResponse<{ count: number; operations: Operation[] }>> {
    return this.request('GET', '/operations');
  }

  /** Obtiene una operación específica */
  async getOperation(operationId: string): Promise<APIResponse<{ operation: Operation }>> {
    return this.request('GET', `/operations/${operationId}`);
  }

  // ============================================
  // MÉTODOS DE PREDICCIÓN
  // ============================================

  /** Obtiene todas las predicciones */
  async getPredictions(): Promise<APIResponse<{ count: number; predictions: Prediction[] }>> {
    return this.request('GET', '/predictions');
  }

  /** Predice posibles ataques */
  async predictAttacks(timeHorizon: number = 24): Promise<APIResponse<{ predictions: Prediction[] }>> {
    return this.request('POST', '/predict', { time_horizon: timeHorizon });
  }

  // ============================================
  // MÉTODOS DE DEFENSA
  // ============================================

  /** Responde a una amenaza */
  async respondToThreat(threat: Threat): Promise<APIResponse<any>> {
    return this.request('POST', '/defend', { threat });
  }

  /** Obtiene todas las amenazas */
  async getThreats(): Promise<APIResponse<{ count: number; threats: Threat[] }>> {
    return this.request('GET', '/threats');
  }

  // ============================================
  // MÉTODOS DE SIMULACIÓN
  // ============================================

  /** Simula un ataque */
  async simulateAttack(templateName: string, target: string): Promise<APIResponse<SimulationResult>> {
    return this.request('POST', '/simulate', { template_name: templateName, target });
  }

  /** Obtiene todas las plantillas de ataque */
  async getTemplates(): Promise<APIResponse<{ count: number; templates: Record<string, any> }>> {
    return this.request('GET', '/templates');
  }

  // ============================================
  // MÉTODOS DE ANÁLISIS
  // ============================================

  /** Analiza comportamiento */
  async analyzeBehavior(entity: string, behaviorData: any = {}): Promise<APIResponse<any>> {
    return this.request('POST', '/analyze/behavior', { entity, behavior_data: behaviorData });
  }

  // ============================================
  // MÉTODOS DE ESCANEO
  // ============================================

  /** Ejecuta un escaneo OSINT */
  async scanTarget(target: string, scanType: 'full' | 'quick' | 'deep' = 'full'): Promise<APIResponse<OSINTScanResult>> {
    return this.autonomousOperation('scan', target);
  }

  // ============================================
  // MÉTODOS DE ESTADÍSTICAS
  // ============================================

  /** Obtiene todas las estadísticas */
  async getAllStats(): Promise<APIResponse<any>> {
    return this.request('GET', '/stats');
  }

  /** Obtiene estadísticas de memoria */
  async getMemoryStats(): Promise<APIResponse<any>> {
    return this.request('GET', '/memory/stats');
  }

  /** Obtiene estadísticas de conocimiento */
  async getKnowledgeStats(): Promise<APIResponse<any>> {
    return this.request('GET', '/knowledge/stats');
  }
}

// 🎯 Instancia singular
export const artoApi = new ARTOApiClient();

// 🎯 Factory para crear clientes con configuración personalizada
export function createARTOApiClient(config: APIConfig = {}): ARTOApiClient {
  return new ARTOApiClient(config);
}
