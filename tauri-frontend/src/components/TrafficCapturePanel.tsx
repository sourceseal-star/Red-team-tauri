/**
 * Traffic Capture Panel - Panel de Captura de Tráfico
 * ====================================================
 * Visualiza el tráfico de red capturado por VpnService.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useARTO } from './ARTOProvider';

const styles: Record<string, React.CSSProperties> = {
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
    fontWeight: 600,
    color: '#fff'
  },
  button: {
    padding: '8px 16px',
    border: 'none',
    borderRadius: '6px',
    backgroundColor: '#3b82f6',
    color: '#fff',
    fontSize: '14px',
    fontWeight: 500,
    cursor: 'pointer'
  },
  buttonDanger: {
    padding: '8px 16px',
    border: 'none',
    borderRadius: '6px',
    backgroundColor: '#dc2626',
    color: '#fff',
    fontSize: '14px',
    fontWeight: 500,
    cursor: 'pointer'
  },
  buttonSecondary: {
    padding: '8px 16px',
    border: '1px solid #334155',
    borderRadius: '6px',
    backgroundColor: 'transparent',
    color: '#94a3b8',
    fontSize: '12px',
    cursor: 'pointer'
  },
  statsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
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
    fontSize: '24px',
    fontWeight: 'bold',
    color: '#3b82f6'
  },
  statLabel: {
    fontSize: '12px',
    color: '#94a3b8',
    marginTop: '5px'
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse'
  },
  th: {
    textAlign: 'left',
    padding: '12px 15px',
    backgroundColor: '#0f172a',
    color: '#94a3b8',
    fontSize: '12px',
    textTransform: 'uppercase',
    letterSpacing: '0.5px'
  },
  td: {
    padding: '12px 15px',
    borderTop: '1px solid #334155',
    color: '#e2e8f0',
    fontSize: '14px'
  },
  emptyState: {
    textAlign: 'center',
    padding: '40px 20px',
    color: '#64748b'
  },
  filterBar: {
    display: 'flex',
    gap: '10px',
    marginBottom: '15px',
    flexWrap: 'wrap'
  },
  filterInput: {
    flex: 1,
    minWidth: 150,
    padding: '8px 12px',
    border: '1px solid #334155',
    borderRadius: '6px',
    backgroundColor: '#0f172a',
    color: '#e2e8f0',
    fontSize: '14px'
  }
};

interface TrafficCapturePanelProps {
  onClose?: () => void;
}

const TrafficCapturePanel: React.FC<TrafficCapturePanelProps> = ({ onClose }) => {
  const { isLoading, error } = useARTO();
  const [trafficStats, setTrafficStats] = useState<any>(null);
  const [capturedPackets, setCapturedPackets] = useState<any[]>([]);
  const [isCapturing, setIsCapturing] = useState(false);
  const [analysis, setAnalysis] = useState<any>(null);
  const [filterProtocol, setFilterProtocol] = useState('all');
  const [filterSearch, setFilterSearch] = useState('');

  const loadTrafficData = useCallback(async () => {
    try {
      const response = await fetch('/api/arto/traffic/stats');
      const data = await response.json();
      setTrafficStats(data.stats || data);
      
      const packetsResponse = await fetch('/api/arto/traffic/packets?limit=50');
      const packetsData = await packetsResponse.json();
      setCapturedPackets(packetsData.packets || []);
      
      const analysisResponse = await fetch('/api/arto/traffic/analysis');
      const analysisData = await analysisResponse.json();
      setAnalysis(analysisData.analysis || analysisData);
    } catch (err) {
      console.error('Error loading traffic data:', err);
    }
  }, []);

  const toggleCapture = useCallback(async () => {
    try {
      if (isCapturing) {
        await fetch('/api/arto/traffic/stop', { method: 'POST' });
        setIsCapturing(false);
      } else {
        await fetch('/api/arto/traffic/start', { method: 'POST' });
        setIsCapturing(true);
        loadTrafficData();
      }
    } catch (err) {
      console.error('Error toggling capture:', err);
    }
  }, [isCapturing, loadTrafficData]);

  const clearStats = useCallback(async () => {
    try {
      await fetch('/api/arto/traffic/clear', { method: 'POST' });
      loadTrafficData();
    } catch (err) {
      console.error('Error clearing stats:', err);
    }
  }, [loadTrafficData]);

  const filteredPackets = capturedPackets.filter(packet => {
    if (filterProtocol !== 'all' && packet.protocol !== filterProtocol) return false;
    if (filterSearch && !packet.src_ip?.includes(filterSearch) && !packet.dst_ip?.includes(filterSearch)) return false;
    return true;
  });

  useEffect(() => {
    loadTrafficData();
    const interval = setInterval(loadTrafficData, 5000);
    return () => clearInterval(interval);
  }, [loadTrafficData]);

  const badgeStyle = (severity: string): React.CSSProperties => ({
    padding: '4px 10px',
    borderRadius: '12px',
    fontSize: '11px',
    fontWeight: 600,
    textTransform: 'uppercase',
    backgroundColor: 
      severity === 'critical' ? '#7f1d1d' :
      severity === 'high' ? '#7c2d12' :
      severity === 'medium' ? '#78350f' :
      severity === 'low' ? '#065f46' : '#064e3b',
    color: '#fff'
  });

  return (
    <div style={styles.card}>
      <div style={styles.cardHeader}>
        <h3 style={styles.cardTitle}>🔌 Captura de Tráfico en Tiempo Real</h3>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button style={isCapturing ? styles.buttonDanger : styles.button} onClick={toggleCapture}>
            {isCapturing ? '🛑 Detener' : '▶️ Iniciar Captura'}
          </button>
          {onClose && <button style={styles.buttonSecondary} onClick={onClose}>Cerrar</button>}
        </div>
      </div>

      {error && (
        <div style={{ color: '#ef4444', padding: '10px', backgroundColor: '#7f1d1d', borderRadius: '6px', marginBottom: '15px' }}>
          {error}
        </div>
      )}

      {isLoading ? (
        <div style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>Cargando datos de tráfico...</div>
      ) : (
        <>
          {trafficStats && (
            <div style={styles.statsGrid}>
              <div style={styles.statCard}>
                <div style={styles.statValue}>{trafficStats.total_packets || 0}</div>
                <div style={styles.statLabel}>Paquetes</div>
              </div>
              <div style={styles.statCard}>
                <div style={styles.statValue}>{trafficStats.total_bytes ? (trafficStats.total_bytes / 1024 / 1024).toFixed(2) : '0.00'} MB</div>
                <div style={styles.statLabel}>Datos</div>
              </div>
              <div style={styles.statCard}>
                <div style={styles.statValue}>{Object.keys(trafficStats.connections || {}).length}</div>
                <div style={styles.statLabel}>Conexiones</div>
              </div>
              <div style={styles.statCard}>
                <div style={styles.statValue}>{trafficStats.threats_detected || 0}</div>
                <div style={styles.statLabel}>Amenazas</div>
              </div>
              <div style={styles.statCard}>
                <div style={styles.statValue}>{Math.round(trafficStats.uptime || 0)}s</div>
                <div style={styles.statLabel}>Tiempo Activo</div>
              </div>
            </div>
          )}

          <div style={styles.filterBar}>
            <select style={styles.filterInput} value={filterProtocol} onChange={(e) => setFilterProtocol(e.target.value)}>
              <option value="all">Todos los protocolos</option>
              <option value="tcp">TCP</option>
              <option value="udp">UDP</option>
              <option value="http">HTTP</option>
              <option value="https">HTTPS</option>
              <option value="dns">DNS</option>
            </select>
            <input type="text" placeholder="Filtrar por IP..." style={styles.filterInput} value={filterSearch} onChange={(e) => setFilterSearch(e.target.value)} />
            <button style={styles.buttonSecondary} onClick={clearStats}>🗑️ Limpiar</button>
          </div>

          <div style={{ ...styles.card, marginBottom: 0 }}>
            <h4 style={{ ...styles.cardTitle, fontSize: '14px', marginBottom: '10px' }}>Paquetes Capturados</h4>
            {filteredPackets.length === 0 ? (
              <div style={styles.emptyState}>{isCapturing ? 'Esperando paquetes...' : 'Inicia la captura para ver paquetes'}</div>
            ) : (
              <table style={styles.table}>
                <thead>
                  <tr>
                    <th style={styles.th}>ID</th>
                    <th style={styles.th}>Origen</th>
                    <th style={styles.th}>Destino</th>
                    <th style={styles.th}>Proto</th>
                    <th style={styles.th}>Tamaño</th>
                    <th style={styles.th}>Fecha</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredPackets.slice(0, 50).map((packet, i) => (
                    <tr key={packet.packet_id || i}>
                      <td style={styles.td}>{packet.packet_id?.slice(0, 8)}...</td>
                      <td style={styles.td}>{packet.src_ip}:{packet.src_port}</td>
                      <td style={styles.td}>{packet.dst_ip}:{packet.dst_port}</td>
                      <td style={styles.td}>{packet.protocol}</td>
                      <td style={styles.td}>{packet.length} B</td>
                      <td style={styles.td}>{new Date(packet.timestamp).toLocaleTimeString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {analysis?.threats?.length > 0 && (
            <div style={{ ...styles.card, marginBottom: 0, marginTop: '15px' }}>
              <h4 style={{ ...styles.cardTitle, fontSize: '14px', marginBottom: '10px' }}>🚨 Amenazas Detectadas</h4>
              <table style={styles.table}>
                <thead>
                  <tr><th style={styles.th}>Tipo</th><th style={styles.th}>Severidad</th><th style={styles.th}>Fecha</th></tr>
                </thead>
                <tbody>
                  {analysis.threats.map((threat: any, i: number) => (
                    <tr key={i}>
                      <td style={styles.td}>{threat.name}</td>
                      <td style={styles.td}><span style={badgeStyle(threat.severity)}>{threat.severity}</span></td>
                      <td style={styles.td}>{new Date(threat.timestamp).toLocaleTimeString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {analysis?.top_connections?.length > 0 && (
            <div style={{ ...styles.card, marginBottom: 0, marginTop: '15px' }}>
              <h4 style={{ ...styles.cardTitle, fontSize: '14px', marginBottom: '10px' }}>📊 Conexiones Más Activas</h4>
              <table style={styles.table}>
                <thead>
                  <tr><th style={styles.th}>Conexión</th><th style={styles.th}>Paquetes</th><th style={styles.th}>Datos</th></tr>
                </thead>
                <tbody>
                  {analysis.top_connections.map((conn: any, i: number) => (
                    <tr key={i}>
                      <td style={styles.td}>{conn.connection || 'N/A'}</td>
                      <td style={styles.td}>{conn.count || 0}</td>
                      <td style={styles.td}>{((conn.bytes || 0) / 1024).toFixed(1)} KB</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default TrafficCapturePanel;
