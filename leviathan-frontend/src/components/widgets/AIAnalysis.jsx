import React, { useState, useCallback, useRef } from 'react';
import { useLeviathanAPI } from '../../hooks/useLeviathan';
import '../../styles/widgets.css';

const AIAnalysis = ({ onAnalysisComplete }) => {
  const { analyzeWithAI, detectObjects, isLoading, error, clearError } = useLeviathanAPI();
  const [source, setSource] = useState(null);
  const [sourceType, setSourceType] = useState('image'); // image, stream, file
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResults, setAnalysisResults] = useState(null);
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [previewUrl, setPreviewUrl] = useState(null);
  const fileInputRef = useRef(null);

  // Tipos de fuente
  const sourceTypes = [
    { value: 'image', label: 'Imagen', icon: '📷' },
    { value: 'stream', label: 'Stream', icon: '🎥' },
    { value: 'file', label: 'Archivo', icon: '📁' }
  ];

  // Manejar cambio de archivo
  const handleFileChange = useCallback((e) => {
    const file = e.target.files[0];
    if (!file) return;

    setSource(file);
    setSourceType('file');
    
    // Crear preview
    const reader = new FileReader();
    reader.onload = (event) => {
      setPreviewUrl(event.target.result);
    };
    reader.readAsDataURL(file);
  }, []);

  // Analizar con IA
  const handleAnalyze = useCallback(async () => {
    if (!source) return;
    
    clearError();
    setIsAnalyzing(true);
    setAnalysisResults(null);
    setAnalysisProgress(0);

    try {
      // Simular progreso
      const progressInterval = setInterval(() => {
        setAnalysisProgress(prev => Math.min(prev + 12, 88));
      }, 350);

      let result;
      
      if (sourceType === 'file' && source instanceof File) {
        // Subir archivo (simulado - en producción usar FormData)
        result = await detectObjects(URL.createObjectURL(source), {
          analyze_objects: true,
          analyze_anomalies: true,
          analyze_threats: true
        });
      } else {
        result = await analyzeWithAI(source, {
          analyze_objects: true,
          analyze_anomalies: true,
          analyze_threats: true
        });
      }

      setAnalysisResults(result);
      setAnalysisProgress(100);
      clearInterval(progressInterval);

      // Llamar callback
      if (onAnalysisComplete) {
        onAnalysisComplete(result);
      }
    } catch (err) {
      console.error('Error during AI analysis:', err);
    } finally {
      setIsAnalyzing(false);
    }
  }, [source, sourceType, analyzeWithAI, detectObjects, onAnalysisComplete, clearError]);

  // Obtener icono de objeto
  const getObjectIcon = (object) => {
    const icons = {
      person: '👤',
      car: '🚗',
      phone: '📱',
      face: '😊',
      animal: '🐕',
      bag: '🛍️',
      weapon: '⚔️',
      unknown: '❓'
    };
    const lowerObject = object?.toLowerCase();
    for (const [key, icon] of Object.entries(icons)) {
      if (lowerObject?.includes(key)) return icon;
    }
    return icons.unknown;
  };

  // Calcular nivel de riesgo
  const getRiskLevel = (score) => {
    if (score >= 80) return 'critical';
    if (score >= 60) return 'high';
    if (score >= 40) return 'medium';
    if (score >= 20) return 'low';
    return 'none';
  };

  // Formatear porcentaje
  const formatPercentage = (value) => {
    return value ? `${Math.round(value * 100)}%` : '0%';
  };

  return (
    <div className="widget ai-analysis-widget">
      <div className="widget-header">
        <div className="widget-title">
          <span className="widget-icon">🤖</span>
          <span>Análisis con IA</span>
        </div>
        <div className="widget-actions">
          <button 
            className="widget-action-btn"
            onClick={() => fileInputRef.current?.click()}
            disabled={isAnalyzing || isLoading}
            title="Seleccionar archivo"
          >
            📁
          </button>
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept="image/*,video/*"
            style={{ display: 'none' }}
          />
        </div>
      </div>

      {/* Controles */}
      <div className="ai-analysis-controls">
        <select
          className="form-control"
          value={sourceType}
          onChange={(e) => setSourceType(e.target.value)}
          disabled={isAnalyzing || isLoading}
        >
          {sourceTypes.map(type => (
            <option key={type.value} value={type.value}>
              {type.icon} {type.label}
            </option>
          ))}
        </select>
        
        {sourceType === 'image' || sourceType === 'stream' ? (
          <input
            type="text"
            className="form-control"
            value={source || ''}
            onChange={(e) => {
              setSource(e.target.value);
              setPreviewUrl(e.target.value);
            }}
            placeholder={sourceType === 'image' ? 'URL de la imagen' : 'URL del stream'}
            disabled={isAnalyzing || isLoading}
          />
        ) : null}
        
        <button
          className="btn-primary btn-sm"
          onClick={handleAnalyze}
          disabled={!source || isAnalyzing || isLoading}
        >
          {isAnalyzing ? 'Analizando...' : 'Analizar'}
        </button>
      </div>

      {/* Preview */}
      {previewUrl && (
        <div className="ai-analysis-preview">
          {sourceType === 'file' || sourceType === 'image' ? (
            <img 
              src={previewUrl} 
              alt="Preview"
              onError={(e) => {
                e.target.style.display = 'none';
              }}
            />
          ) : (
            <video 
              src={previewUrl} 
              controls 
              style={{ width: '100%', height: '100%' }}
              onError={(e) => {
                e.target.style.display = 'none';
              }}
            />
          )}
          
          {isAnalyzing && (
            <div className="ai-analysis-overlay">
              <div className="animate-pulse">Analizando...</div>
              <div className="quick-scan-progress" style={{ width: '80%', background: 'rgba(255,255,255,0.3)' }}>
                <div 
                  className="quick-scan-progress-bar" 
                  style={{ width: `${analysisProgress}%`, background: 'linear-gradient(135deg, #667eea, #764ba2)' }}
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="alert alert-danger mt-2">
          <span>❌ {error.error || 'Error en el análisis con IA'}</span>
        </div>
      )}

      {/* Resultados */}
      {analysisResults && (
        <div className="ai-analysis-results-section">
          {/* Objetos detectados */}
          {analysisResults.objects && analysisResults.objects.length > 0 && (
            <div className="mt-2">
              <h4 className="text-sm font-semibold mb-1">Objetos Detectados</h4>
              <div className="ai-analysis-results">
                {analysisResults.objects.map((obj, index) => (
                  <div key={index} className="ai-analysis-result-card">
                    <div className="ai-analysis-result-icon">{getObjectIcon(obj.class)}</div>
                    <div className="ai-analysis-result-label">{obj.class}</div>
                    <div className="ai-analysis-result-value">{formatPercentage(obj.confidence)}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Anomalías */}
          {analysisResults.anomalies && analysisResults.anomalies.length > 0 && (
            <div className="mt-2">
              <h4 className="text-sm font-semibold mb-1">Anomalías</h4>
              <div className="ai-analysis-results">
                {analysisResults.anomalies.map((anomaly, index) => (
                  <div key={index} className="ai-analysis-result-card">
                    <div className="ai-analysis-result-icon">⚠️</div>
                    <div className="ai-analysis-result-label">{anomaly.type}</div>
                    <div className="ai-analysis-result-value">{formatPercentage(anomaly.score)}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Puntuación de amenaza */}
          {analysisResults.threat_score !== undefined && (
            <div className="ai-analysis-score mt-2">
              <div className="ai-analysis-score-value">
                {Math.round(analysisResults.threat_score * 100) / 100}
              </div>
              <div className="ai-analysis-score-label">
                Puntuación de Amenaza / 100
              </div>
              <div className={`ai-analysis-score-level ${getRiskLevel(analysisResults.threat_score * 100)}`}>
                {getRiskLevel(analysisResults.threat_score * 100).toUpperCase()}
              </div>
            </div>
          )}

          {/* Mensaje de análisis */}
          {analysisResults.summary && (
            <div className="mt-2 p-2" style={{ 
              background: 'var(--bg-secondary)', 
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border)'
            }}>
              <p className="text-sm text-secondary">{analysisResults.summary}</p>
            </div>
          )}
        </div>
      )}

      {/* Mensaje vacío */}
      {!analysisResults && !isAnalyzing && !previewUrl && (
        <div className="ai-analysis-upload" onClick={() => fileInputRef.current?.click()}>
          <div className="ai-analysis-upload-icon">📷</div>
          <div className="ai-analysis-upload-text">
            Haz clic para seleccionar una imagen o ingresa una URL
          </div>
        </div>
      )}
    </div>
  );
};

export default AIAnalysis;
