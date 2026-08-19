/**
 * ARTO Types - Tipos TypeScript para el sistema ARTO
 * ==================================================
 */

// 🎯 Tipos de Operaciones
export type OperationType = 
  | 'scan'
  | 'simulate'
  | 'monitor'
  | 'investigate'
  | 'defend';

// 📊 Tipos de Decisiones
export type DecisionAction = 
  | 'scan'
  | 'attack'
  | 'defend'
  | 'monitor'
  | 'investigate'
  | 'block'
  | 'alert'
  | 'log_and_continue'
  | 'ignore';

export type RiskLevel = 'critical' | 'high' | 'medium' | 'low' | 'info';

// 🎭 Tipos de Plantillas de Ataque
export type AttackTemplateType = 
  | 'web'
  | 'network'
  | 'social'
  | 'physical'
  | 'wireless'
  | 'database'
  | 'api';

// 🛡️ Tipos de Acciones de Defensa
export type DefenseAction = 
  | 'block'
  | 'isolate'
  | 'monitor'
  | 'alert'
  | 'patch'
  | 'investigate'
  | 'quarantine'
  | 'shutdown';

export type ThreatSeverity = 'critical' | 'high' | 'medium' | 'low' | 'info';

// 📈 Tipos de Predicciones
export type PredictionType = 
  | 'attack'
  | 'vulnerability'
  | 'threat'
  | 'behavior';

// 📄 Tipos de Informes
export type ReportType = 
  | 'scan'
  | 'simulation'
  | 'monitoring'
  | 'investigation'
  | 'defense'
  | 'threat'
  | 'daily'
  | 'weekly';

// 🔍 Tipos de Anomalías
export type AnomalyType = 
  | 'statistical'
  | 'behavioral'
  | 'temporal'
  | 'pattern';

// 🎯 Tipos de Patrones
export type PatternType = 
  | 'malicious'
  | 'suspicious'
  | 'normal'
  | 'unknown';

// ⚡ Tipos de Eventos WebSocket
export type WebSocketEventType = 
  | 'operation'
  | 'prediction'
  | 'threat'
  | 'alert'
  | 'status';

// ============================================
// INTERFACES
// ============================================

// 🎯 Interfaz de Operación
export interface Operation {
  id: string;
  type: OperationType;
  target: string;
  timestamp: string;
  status: 'running' | 'completed' | 'failed';
  result?: any;
  error?: string;
  traceback?: string;
}

// 📊 Interfaz de Decisión
export interface Decision {
  decision_id: string;
  action: DecisionAction;
  confidence: number; // 0.0 - 1.0
  reason: string;
  risk_level: RiskLevel;
  context: Record<string, any>;
  timestamp: string;
  metadata: Record<string, any>;
}

// 🎭 Interfaz de Plantilla de Ataque
export interface AttackTemplate {
  name: string;
  type: AttackTemplateType;
  description: string;
  phases: AttackPhase[];
  parameters: Record<string, any>;
  severity: ThreatSeverity;
  difficulty: 'easy' | 'medium' | 'hard' | 'expert';
  tags: string[];
}

// 🏆 Fases de Ataque
export type AttackPhase = 
  | 'reconnaissance'
  | 'scanning'
  | 'gaining_access'
  | 'maintaining_access'
  | 'exfiltration'
  | 'covering_tracks';

// 🎯 Interfaz de Simulación
export interface SimulationResult {
  simulation_id: string;
  template_name: string;
  target: string;
  execution: Record<string, any>;
  results: Record<string, any>;
  findings: Finding[];
  recommendations: string[];
  timestamp: string;
  duration: number; // segundos
  success: boolean;
}

// 📋 Interfaz de Hallazgo
export interface Finding {
  type: string;
  category?: string;
  title?: string;
  description?: string;
  severity?: ThreatSeverity;
  count?: number;
  details?: any;
}

// 🛡️ Interfaz de Respuesta de Defensa
export interface DefenseResponse {
  response_id: string;
  threat_id: string;
  action: DefenseAction;
  target: string;
  status: 'success' | 'failed' | 'partial';
  message: string;
  severity: ThreatSeverity;
  timestamp: string;
  details: Record<string, any>;
}

// 🚨 Interfaz de Amenaza
export interface Threat {
  id: string;
  type: string;
  target: string;
  description: string;
  severity: ThreatSeverity;
  confidence: number; // 0.0 - 1.0
  source: string;
  timestamp: string;
  metadata: Record<string, any>;
}

// 📈 Interfaz de Predicción
export interface Prediction {
  prediction_id: string;
  type: PredictionType;
  target: string;
  description: string;
  probability: number; // 0.0 - 1.0
  severity: ThreatSeverity;
  timestamp: string;
  time_horizon: number; // horas
  confidence: number; // 0.0 - 1.0
  mitigation?: {
    action: string;
    priority: 'high' | 'medium' | 'low';
    description: string;
  };
  metadata: Record<string, any>;
}

// 📊 Interfaz de Evaluación de Riesgo
export interface RiskAssessment {
  score: number; // 0.0 - 1.0
  severity: RiskLevel;
  factors: Record<string, number>;
  recommendations: string[];
  timestamp: string;
}

// 📋 Interfaz de Análisis de Comportamiento
export interface BehaviorAnalysis {
  analysis_id: string;
  entity: string;
  behavior_type: PatternType;
  score: number; // 0.0 - 1.0
  anomalies: Anomaly[];
  patterns: Pattern[];
  recommendations: string[];
  timestamp: string;
  metadata: Record<string, any>;
}

// 🎯 Interfaz de Anomalía
export interface Anomaly {
  anomaly_id: string;
  type: AnomalyType;
  name: string;
  description: string;
  severity: ThreatSeverity;
  confidence: number; // 0.0 - 1.0
  value: any;
  expected: any;
  deviation: number;
  timestamp: string;
}

// 🔍 Interfaz de Patrón
export interface Pattern {
  pattern_id: string;
  type: PatternType;
  name: string;
  description: string;
  severity: ThreatSeverity;
  confidence: number; // 0.0 - 1.0
  evidence: string[];
  timestamp: string;
}

// 📄 Interfaz de Informe
export interface Report {
  report_id: string;
  type: ReportType;
  title: string;
  target: string;
  summary: string;
  findings: Finding[];
  recommendations: string[];
  risk_score: number; // 0.0 - 1.0
  severity: ThreatSeverity;
  timestamp: string;
  metadata: Record<string, any>;
}

// 📊 Interfaz de Estadísticas del Sistema
export interface SystemStats {
  running: boolean;
  operations_count: number;
  predictions_count: number;
  threats_count: number;
  memory_stats: Record<string, any>;
  knowledge_stats: Record<string, any>;
}

// 🎯 Interfaz de Escaneo OSINT
export interface OSINTScanResult {
  target: string;
  timestamp: string;
  type?: 'full' | 'quick' | 'deep';
  sources: Record<string, any>;
  vulnerabilities?: Finding[];
  threats?: Threat[];
  findings?: Finding[];
  recommendations?: string[];
  duration?: number;
}

// 🔌 Interfaz de Análisis de Tráfico
export interface TrafficAnalysis {
  timestamp: string;
  requests: Request[];
  responses: Response[];
  injections: Injection[];
  behavior_data: BehaviorData;
}

// 📥 Interfaz de Solicitud
export interface Request {
  id: number;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  path: string;
  headers: Record<string, string>;
  body?: any;
  timestamp: string;
  ip: string;
}

// 📤 Interfaz de Respuesta
export interface Response {
  id: number;
  status_code: number;
  headers: Record<string, string>;
  body?: any;
  timestamp: string;
}

// 💉 Interfaz de Inyección
export interface Injection {
  id: string;
  request_id: number;
  type: string; // 'sqli', 'xss', 'rce', etc.
  severity: ThreatSeverity;
  description: string;
  evidence: string;
  timestamp: string;
}

// 📊 Interfaz de Datos de Comportamiento
export interface BehaviorData {
  request_rate: number;
  error_rate: number;
  suspicious_count: number;
  unique_ips: number;
  failed_logins?: number;
  data_transfer?: number;
}

// 🎯 Interfaz de Análisis Temporal
export interface TemporalAnalysis {
  target: string;
  time_range: string;
  trends: Record<string, Trend>;
  anomalies: Anomaly[];
  patterns: Pattern[];
  predictions: Prediction[];
  timestamp: string;
}

// 📈 Interfaz de Tendencia
export interface Trend {
  direction: 'increasing' | 'decreasing' | 'stable';
  slope: number;
  current: any;
  history?: any[];
}

// 📡 Interfaz de Evento WebSocket
export interface WebSocketEvent {
  type: WebSocketEventType;
  data: any;
}

// 🎯 Interfaz de Estado de ARTO
export interface ARTOStatus {
  running: boolean;
  operations_count: number;
  predictions_count: number;
  threats_count: number;
  memory_stats: Record<string, any>;
  knowledge_stats: Record<string, any>;
}

// 📦 Interfaz de Resultado de API
export interface APIResponse<T> {
  status: 'success' | 'error' | 'partial';
  data?: T;
  message?: string;
  error?: string;
  timestamp: string;
}

// 🎯 Interfaz de Contexto ARTO
export interface ARTOContext {
  arto: any;
  operations: Operation[];
  predictions: Prediction[];
  threats: Threat[];
  reports: Report[];
  isLoading: boolean;
  error: string | null;
}

// 🎨 Tipos de Panel
export type PanelType = 
  | 'osint'
  | 'interceptor'
  | 'threat-intel'
  | 'topology'
  | 'arto';

// 📊 Tipos de Vista
export type ViewType = 
  | 'dashboard'
  | 'operations'
  | 'predictions'
  | 'threats'
  | 'reports'
  | 'simulations';
