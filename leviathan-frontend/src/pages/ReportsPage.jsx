import React, { useState, useEffect } from 'react';
import { useLeviathanAPI } from '../hooks/useLeviathan';
import StatsWidget from '../components/widgets/StatsWidget';
import AlertCenter from '../components/widgets/AlertCenter';
import '../styles/widgets.css';

const ReportsPage = () => {
  const { getHistory, generateReport, isLoading, error } = useLeviathanAPI();
  const [history, setHistory] = useState([]);
  const [selectedOperation, setSelectedOperation] = useState(null);
  const [reportType, setReportType] = useState('html');
  const [isGenerating, setIsGenerating] = useState(false);

  // Obtener historial
  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const data = await getHistory();
        setHistory(data.operations || []);
      } catch (err) {
        console.error('Error fetching history:', err);
      }
    };
    
    fetchHistory();
  }, [getHistory]);

  // Generar informe
  const handleGenerateReport = async () => {
    if (!selectedOperation) return;
    
    setIsGenerating(true);
    
    try {
      const result = await generateReport(
        selectedOperation.target,
        selectedOperation,
        reportType
      );
      
      // Descargar informe (simulado)
      console.log('Report generated:', result);
      alert(`Informe ${reportType} generado con éxito!`);
    } catch (err) {
      console.error('Error generating report:', err);
    } finally {
      setIsGenerating(false);
    }
  };

  // Tipos de informe
  const reportTypes = [
    { value: 'html', label: 'HTML' },
    { value: 'json', label: 'JSON' },
    { value: 'pdf', label: 'PDF' }
  ];

  return (
    <div className="page reports-page">
      <h1 className="text-2xl font-bold mb-4">📋 Reportes</h1>
      
      <div className="page-grid">
        <div className="page-section">
          <StatsWidget />
        </div>
        
        <div className="page-section">
          <AlertCenter onAlertSelect={(alert) => console.log('Alert selected:', alert)} />
        </div>
        
        <div className="page-section full-width">
          <div className="card">
            <div className="card-header">
              <h2 className="text-lg font-semibold">Historial de Operaciones</h2>
            </div>
            <div className="card-body">
              <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Fecha</th>
                      <th>Tipo</th>
                      <th>Objetivo</th>
                      <th>Estado</th>
                      <th>Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((op, index) => (
                      <tr 
                        key={op.id || index}
                        onClick={() => setSelectedOperation(op)}
                        style={{
                          cursor: 'pointer',
                          background: selectedOperation?.id === op.id ? 'var(--bg-hover)' : 'transparent'
                        }}
                      >
                        <td>{new Date(op.timestamp).toLocaleString()}</td>
                        <td>{op.type}</td>
                        <td>{op.target}</td>
                        <td>
                          <span className={`badge ${op.status === 'success' ? 'badge-success' : 'badge-danger'}`}>
                            {op.status}
                          </span>
                        </td>
                        <td>
                          <button 
                            className="btn btn-sm btn-info"
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedOperation(op);
                            }}
                          >
                            Ver
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {selectedOperation && (
                <div className="mt-3 p-3" style={{ 
                  background: 'var(--bg-secondary)', 
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border)'
                }}>
                  <h3 className="text-md font-semibold mb-2">Detalles de la Operación</h3>
                  <pre className="text-sm" style={{ 
                    background: 'var(--bg-primary)', 
                    padding: 'var(--spacing-sm)', 
                    borderRadius: 'var(--radius-sm)',
                    overflow: 'auto'
                  }}>
                    {JSON.stringify(selectedOperation, null, 2)}
                  </pre>
                  
                  <div className="mt-2 flex gap-2">
                    <select
                      className="form-control form-control-sm"
                      value={reportType}
                      onChange={(e) => setReportType(e.target.value)}
                    >
                      {reportTypes.map(type => (
                        <option key={type.value} value={type.value}>
                          {type.label}
                        </option>
                      ))}
                    </select>
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={handleGenerateReport}
                      disabled={isGenerating || isLoading}
                    >
                      {isGenerating ? 'Generando...' : 'Generar Informe'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <style jsx>{`
        .page {
          padding: var(--spacing-lg);
          animation: fadeIn 0.5s ease-out;
        }

        .page-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
          gap: var(--spacing-lg);
        }

        .page-section {
          min-height: 300px;
        }

        .page-section.full-width {
          grid-column: 1 / -1;
        }

        .table {
          width: 100%;
          border-collapse: collapse;
        }

        .table th,
        .table td {
          padding: var(--spacing-sm);
          text-align: left;
          border-bottom: 1px solid var(--border-light);
        }

        .table th {
          background: var(--bg-secondary);
          font-weight: 600;
          color: var(--text-secondary);
          font-size: 0.8rem;
          text-transform: uppercase;
        }

        .table tr:hover {
          background: var(--bg-hover);
        }

        @media (max-width: 768px) {
          .page {
            padding: var(--spacing-sm);
          }
          
          .page-grid {
            grid-template-columns: 1fr;
          }
          
          .table {
            font-size: 0.8rem;
          }
        }
      `}</style>
    </div>
  );
};

export default ReportsPage;
