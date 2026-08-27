/**
 * ARTO Panel - Panel Principal de ARTO
 * =====================================
 * Componente principal para visualizar y controlar el sistema ARTO.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useARTO } from './ARTOProvider';
import TrafficCapturePanel from './TrafficCapturePanel';
import {
  Operation,
  Prediction,
  Threat,
  Report,
  OperationType,
  RiskLevel,
  ThreatSeverity
} from '../types/arto';

// 🎨 Estilos CSS
const styles = {
  container: {
    fontFamily: 'Segoe UI, Tahoma, Geneva, Verdana, sans-serif',
    maxWidth: '1400px',
    margin: '0 auto',
    padding: '20px',
    backgroundColor: '#0f172a',
    borderRadius: '10px',
    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
    color: '#e2e8f0'
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '20px',
    paddingBottom: '15px',
    borderBottom: '1px solid #334155'
  },
  title: {
    fontSize: '28px',
    fontWeight: 'bold',
    color: '#fff',
    display: 'flex',
    alignItems: 'center',
    gap: '12px'
  },
  subtitle: {
    fontSize: '14px',
    color: '#94a3b8',
    marginTop: '5px'
  },
  statusIndicator: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    padding: '8px 16px',
    borderRadius: '20px',
    backgroundColor: '#1e293b',
    fontSize: '14px'
  },
  statusDot: (color: string) => ({
    width: '10px',
    height: '10px',
    borderRadius: '50%',
    backgroundColor: color
  }),
  tabs: {
    display: 'flex',
    gap: '5px',
    marginBottom: '20px',
    backgroundColor: '#1e293b',
    padding: '5px',
    borderRadius: '8px'
  },
  tab: (isActive: boolean) => ({
    flex: 1,
    padding: '12px 20px',
    border: 'none',
    backgroundColor: isActive ? '#3b82f6' : 'transparent',
    color: isActive ? '#fff' : '#94a3b8',
    borderRadius: '6px',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: '500',
    transition: 'all 0.2s ease'
  }),
  content: {
    padding: '10px'
  },
  card: {
    backgroundColor: '#1e293b',
    borderRadius: '8px',
    padding: '20px',
    marginBottom: '15px',
    border: '1px solid #334155'
  },
  cardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '15px'
  },
  cardTitle: {
    fontSize: '18px',
    fontWeight: '600',
    color: '#fff'
  },
  statsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
    gap: '15px',
    marginBottom: '20px'
  },
  statCard: {
    backgroundColor: '#0f172a',
    borderRadius: '8px',
    padding: '15px',
    border: '1px solid #334155'
  },
  statValue: {
    fontSize: '28px',
    fontWeight: 'bold',
    color: '#3b82f6'
  },
  statLabel: {
    fontSize: '12px',
    color: '#94a3b8',
    marginTop: '5px',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.5px'
  },
  form: {
    display: 'flex',
    gap: '10px',
    marginBottom: '15px'
  },
  input: {
    flex: 1,
    padding: '10px 15px',
    border: '1px solid #334155',
    borderRadius: '6px',
    backgroundColor: '#0f172a',
    color: '#e2e8f0',
    fontSize: '14px'
  },
  select: {
    padding: '10px 15px',
    border: '1px solid #334155',
    borderRadius: '6px',
    backgroundColor: '#0f172a',
    color: '#e2e8f0',
    fontSize: '14px'
  },
  button: {
    padding: '10px 20px',
    border: 'none',
    borderRadius: '6px',
    backgroundColor: '#3b82f6',
    color: '#fff',
    fontSize: '14px',
    fontWeight: '500',
    cursor: 'pointer',
    transition: 'background-color 0.2s ease'
  },
  buttonSecondary: {
    padding: '8px 16px',
    border: '1px solid #334155',
    borderRadius: '6px',
    backgroundColor: 'transparent',
    color: '#94a3b8',
    fontSize: '12px',
    cursor: 'pointer',
    transition: 'all 0.2s ease'
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse' as const
  },
  th: {
    textAlign: 'left' as const,
    padding: '12px 15px',
    backgroundColor: '#0f172a',
    color: '#94a3b8',
    fontSize: '12px',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.5px'
  },
  td: {
    padding: '12px 15px',
    borderTop: '1px solid #334155',
    color: '#e2e8f0',
    fontSize: '14px'
  },
  tr: {
    transition: 'background-color 0.2s ease'
  },
  trHover: {
    backgroundColor: '#334155'
  },
  badge: (severity: RiskLevel | ThreatSeverity) => ({
    padding: '4px 10px',
    borderRadius: '12px',
    fontSize: '11px',
    fontWeight: '600',
    textTransform: 'uppercase' as const,
    backgroundColor: 
      severity === 'critical' ? '#7f1d1d' :
      severity === 'high' ? '#7c2d12' :
      severity === 'medium' ? '#78350f' :
      severity === 'low' ? '#065f46' : '#064e3b',
    color: '#fff'
  }),
  statusBadge: (status: string) => ({
    padding: '4px 10px',
    borderRadius: '12px',
    fontSize: '11px',
    fontWeight: '600',
    backgroundColor: 
      status === 'running' ? '#1d4ed8' :
      status === 'completed' ? '#16a34a' :
      status === 'success' ? '#16a34a' :
      status === 'failed' ? '#dc2626' : '#64748b',
    color: '#fff'
  }),
  emptyState: {
    textAlign: 'center' as const,
    padding: '40px 20px',
    color: '#64748b'
  },
  loading: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    padding: '40px',
    color: '#64748b'
  },
  spinner: {
    width: '40px',
    height: '40px',
    border: '3px solid #334155',
    borderTopColor: '#3b82f6',
    borderRadius: '50%' as const,
    animation: 'spin 1s linear infinite'
  },
  error: {
    color: '#ef4444',
    backgroundColor: '#7f1d1d',
    padding: '12px 16px',
    borderRadius: '6px',
    marginBottom: '15px',
    fontSize: '14px'
  },
  actionButtons: {
    display: 'flex',
    gap: '10px',
    flexWrap: 'wrap' as const
  }
};

// 🎯 Componente de Estadísticas
const StatsOverview: React.FC = () => {
  const { systemStats, operations, predictions, threats } = useARTO();

  return (
    <div style={styles.statsGrid}>
      <div style={styles.statCard}>
        <div style={styles.statValue}>{systemStats?.operations_count || operations.length}</div>
        <div style={styles.statLabel}>Operaciones</div>
      </div>
      <div style={styles.statCard}>
        <div style={styles.statValue}>{systemStats?.predictions_count || predictions.length}</div>
        <div style={styles.statLabel}>Predicciones</div>
      </div>
      <div style={styles.statCard}>
        <div style={styles.statValue}>{systemStats?.threats_count || threats.length}</div>
        <div style={styles.statLabel}>Amenazas</div>
      </div>
      <div style={styles.statCard}>
        <div style={styles.statValue}>
          {systemStats?.running ? <span style={{color: '#16a34a'}}>✅</span> : <span style={{color: '#dc2626'}}>❌</span>}
        </div>
        <div style={styles.statLabel}>Sistema</div>
      </div>
    </div>
  );
};

// 🎯 Componente de Operaciones
const OperationsTab: React.FC = () => {
  const { operations, executeOperation, isLoading, error, refreshData } = useARTO();
  const [target, setTarget] = useState('');
  const [operationType, setOperationType] = useState<OperationType>('scan');

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!target.trim()) return;
    
    await executeOperation(operationType, target);
    setTarget('');
  }, [target, operationType, executeOperation]);

  return (
    <div style={styles.content}>
      {error && <div style={styles.error}>{error}</div>}
      
      <div style={styles.card}>
        <div style={styles.cardHeader}>
          <h3 style={styles.cardTitle}>Nueva Operación</h3>
        </div>
        
        <form onSubmit={handleSubmit} style={styles.form}>
          <input
            type="text"
            placeholder="Objetivo (IP, dominio, URL)"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            style={styles.input}
          />
          <select
            value={operationType}
            onChange={(e) => setOperationType(e.target.value as OperationType)}
            style={styles.select}
          >
            <option value="scan">Escaneo</option>
            <option value="simulate">Simulación</option>
            <option value="monitor">Monitoreo</option>
            <option value="investigate">Investigación</option>
            <option value="defend">Defensa</option>
          </select>
          <button
            type="submit"
            style={styles.button}
            disabled={isLoading || !target.trim()}
          >
            {isLoading ? 'Ejecutando...' : 'Ejecutar'}
          </button>
        </form>
      </div>

      <div style={styles.card}>
        <div style={styles.cardHeader}>
          <h3 style={styles.cardTitle}>Operaciones Recientes</h3>
          <button style={styles.buttonSecondary} onClick={() => refreshData()}>
            🔄 Refrescar
          </button>
        </div>
        
        {operations.length === 0 ? (
          <div style={styles.emptyState}>
            No hay operaciones recientes
          </div>
        ) : (
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>ID</th>
                <th style={styles.th}>Tipo</th>
                <th style={styles.th}>Objetivo</th>
                <th style={styles.th}>Estado</th>
                <th style={styles.th}>Fecha</th>
              </tr>
            </thead>
            <tbody>
              {operations.slice(0, 10).map((op) => (
                <tr key={op.id} style={styles.tr}>
                  <td style={styles.td}>{op.id.slice(0, 8)}...</td>
                  <td style={styles.td}>{op.type}</td>
                  <td style={styles.td}>{op.target}</td>
                  <td style={styles.td}>
                    <span style={styles.statusBadge(op.status)}>{op.status}</span>
                  </td>
                  <td style={styles.td}>{new Date(op.timestamp).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

// 🎯 Componente de Predicciones
const PredictionsTab: React.FC = () => {
  const { predictions, predictAttacks, isLoading, error } = useARTO();
  const [timeHorizon, setTimeHorizon] = useState(24);

  const handlePredict = useCallback(async () => {
    await predictAttacks(timeHorizon);
  }, [timeHorizon, predictAttacks]);

  return (
    <div style={styles.content}>
      {error && <div style={styles.error}>{error}</div>}
      
      <div style={styles.card}>
        <div style={styles.cardHeader}>
          <h3 style={styles.cardTitle}>Predecir Ataques</h3>
        </div>
        
        <div style={styles.form}>
          <select
            value={timeHorizon}
            onChange={(e) => setTimeHorizon(Number(e.target.value))}
            style={styles.select}
          >
            <option value={6}>6 horas</option>
            <option value={12}>12 horas</option>
            <option value={24}>24 horas</option>
            <option value={48}>48 horas</option>
            <option value={72}>72 horas</option>
          </select>
          <button
            onClick={handlePredict}
            style={styles.button}
            disabled={isLoading}
          >
            {isLoading ? 'Prediciendo...' : 'Predecir'}
          </button>
        </div>
      </div>

      <div style={styles.card}>
        <div style={styles.cardHeader}>
          <h3 style={styles.cardTitle}>Predicciones Recientes</h3>
          <button style={styles.buttonSecondary} onClick={handlePredict}>
            🔄 Refrescar
          </button>
        </div>
        
        {predictions.length === 0 ? (
          <div style={styles.emptyState}>
            No hay predicciones recientes
          </div>
        ) : (
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>ID</th>
                <th style={styles.th}>Tipo</th>
                <th style={styles.th}>Objetivo</th>
                <th style={styles.th}>Probabilidad</th>
                <th style={styles.th}>Severidad</th>
              </tr>
            </thead>
            <tbody>
              {predictions.slice(0, 10).map((pred) => (
                <tr key={pred.prediction_id} style={styles.tr}>
                  <td style={styles.td}>{pred.prediction_id.slice(0, 8)}...</td>
                  <td style={styles.td}>{pred.type}</td>
                  <td style={styles.td}>{pred.target}</td>
                  <td style={styles.td}>{(pred.probability * 100).toFixed(1)}%</td>
                  <td style={styles.td}>
                    <span style={styles.badge(pred.severity)}>{pred.severity}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

// 🎯 Componente de Amenazas
const ThreatsTab: React.FC = () => {
  const { threats, respondToThreat, isLoading, error } = useARTO();

  const handleRespond = useCallback(async (threat: Threat) => {
    await respondToThreat(threat);
  }, [respondToThreat]);

  return (
    <div style={styles.content}>
      {error && <div style={styles.error}>{error}</div>}
      
      <div style={styles.card}>
        <div style={styles.cardHeader}>
          <h3 style={styles.cardTitle}>Amenazas Detectadas</h3>
        </div>
        
        {threats.length === 0 ? (
          <div style={styles.emptyState}>
            No hay amenazas detectadas
          </div>
        ) : (
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>ID</th>
                <th style={styles.th}>Tipo</th>
                <th style={styles.th}>Objetivo</th>
                <th style={styles.th}>Severidad</th>
                <th style={styles.th}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {threats.slice(0, 10).map((threat) => (
                <tr key={threat.id} style={styles.tr}>
                  <td style={styles.td}>{threat.id.slice(0, 8)}...</td>
                  <td style={styles.td}>{threat.type}</td>
                  <td style={styles.td}>{threat.target}</td>
                  <td style={styles.td}>
                    <span style={styles.badge(threat.severity)}>{threat.severity}</span>
                  </td>
                  <td style={styles.td}>
                    <button
                      style={styles.buttonSecondary}
                      onClick={() => handleRespond(threat)}
                      disabled={isLoading}
                    >
                      Responder
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

// 🎯 Componente de Simulaciones
const SimulationsTab: React.FC = () => {
  const { simulateAttack, isLoading, error } = useARTO();
  const [target, setTarget] = useState('');
  const [templateName, setTemplateName] = useState('web_attack');

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!target.trim()) return;
    
    await simulateAttack(templateName, target);
    setTarget('');
  }, [target, templateName, simulateAttack]);

  return (
    <div style={styles.content}>
      {error && <div style={styles.error}>{error}</div>}
      
      <div style={styles.card}>
        <div style={styles.cardHeader}>
          <h3 style={styles.cardTitle}>Simular Ataque</h3>
        </div>
        
        <form onSubmit={handleSubmit} style={styles.form}>
          <input
            type="text"
            placeholder="Objetivo"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            style={styles.input}
          />
          <select
            value={templateName}
            onChange={(e) => setTemplateName(e.target.value)}
            style={styles.select}
          >
            <option value="web_attack">Ataque Web</option>
            <option value="domain_attack">Ataque a Dominio</option>
            <option value="ip_attack">Ataque a IP</option>
            <option value="network_attack">Ataque de Red</option>
            <option value="api_attack">Ataque a API</option>
            <option value="auth_attack">Ataque de Autenticación</option>
          </select>
          <button
            type="submit"
            style={styles.button}
            disabled={isLoading || !target.trim()}
          >
            {isLoading ? 'Simulando...' : 'Simular'}
          </button>
        </form>
      </div>

      <div style={styles.card}>
        <div style={styles.cardHeader}>
          <h3 style={styles.cardTitle}>Plantillas de Ataque</h3>
        </div>
        <p style={{ color: '#94a3b8', fontSize: '14px' }}>
          Selecciona una plantilla de ataque para simular diferentes escenarios de seguridad.
        </p>
        <div style={styles.actionButtons}>
          <button style={styles.buttonSecondary}>Ver todas las plantillas</button>
        </div>
      </div>
    </div>
  );
};

// 🎯 Componente Principal
const ARTOPanel: React.FC = () => {
  const { systemStats, isLoading } = useARTO();
  const [activeTab, setActiveTab] = useState('operations');

  // 🎯 Tabs disponibles
  const tabs = [
    { id: 'operations', label: '🎯 Operaciones' },
    { id: 'predictions', label: '🔮 Predicciones' },
    { id: 'threats', label: '🛡️ Amenazas' },
    { id: 'simulations', label: '🎭 Simulaciones' }
  ];

  // 🎯 Renderizar el tab activo
  const renderTab = () => {
    switch (activeTab) {
      case 'operations':
        return <OperationsTab />;
      case 'predictions':
        return <PredictionsTab />;
      case 'threats':
        return <ThreatsTab />;
      case 'simulations':
        return <SimulationsTab />
      case 'traffic':
        return <TrafficCapturePanel />;;
      default:
        return <OperationsTab />;
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>
            <span>🚀 ARTO</span>
            <span style={{ fontSize: '16px', color: '#94a3b8' }}>v1.0.0</span>
          </h1>
          <p style={styles.subtitle}>
            Sistema Autónomo de Operaciones de Red Team
          </p>
        </div>
        <div style={styles.statusIndicator}>
          <div style={styles.statusDot(systemStats?.running ? '#16a34a' : '#dc2626')} />
          {systemStats?.running ? 'Sistema Activo' : 'Sistema Inactivo'}
        </div>
      </div>

      <div style={styles.tabs}>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            style={styles.tab(activeTab === tab.id)}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div style={styles.loading}>
          <div style={styles.spinner} />
          <span style={{ marginLeft: '15px' }}>Cargando...</span>
        </div>
      ) : (
        <>
          <StatsOverview />
          {renderTab()}
        </>
      )}
    </div>
  );
};

export default ARTOPanel;
