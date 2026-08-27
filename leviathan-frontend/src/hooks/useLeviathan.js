import React, { useState, useCallback, createContext, useContext } from 'react';
import axios from 'axios';

/**
 * Cliente API para LEVIATHAN
 */
const leviathanAPI = axios.create({
  baseURL: '/api/leviathan',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
});

// Interceptor para manejar errores
leviathanAPI.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      // El servidor respondió con un error
      return Promise.reject(error.response.data);
    } else if (error.request) {
      // No se recibió respuesta
      return Promise.reject({
        error: 'No se recibió respuesta del servidor',
        status: 503
      });
    } else {
      // Error en la configuración de la petición
      return Promise.reject({
        error: error.message,
        status: 400
      });
    }
  }
);

/**
 * Hook personalizado para interactuar con la API de LEVIATHAN
 * @returns {Object} Objeto con funciones para cada endpoint
 */
export const useLeviathanAPI = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  /**
   * Obtener estado del sistema
   */
  const getStatus = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await leviathanAPI.get('/status');
      return response.data;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Escaneo de red
   * @param {string} network - Red a escanear
   * @param {Object} options - Opciones de escaneo
   */
  const scanNetwork = useCallback(async (network = '192.168.0.0/24', options = {}) => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await leviathanAPI.post('/scan/network', {
        network,
        ...options
      });
      return response.data;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Detección de cámaras
   * @param {string} network - Red a escanear
   */
  const scanCameras = useCallback(async (network = '192.168.0.0/24') => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await leviathanAPI.post('/scan/cameras', { network });
      return response.data;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Escaneo rápido
   * @param {string} target - Objetivo a escanear
   */
  const quickScan = useCallback(async (target) => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await leviathanAPI.post('/scan/quick', { target });
      return response.data;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Explotar cámara
   * @param {string} target - IP de la cámara
   * @param {Object} context - Contexto adicional
   */
  const exploitCamera = useCallback(async (target, context = {}) => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await leviathanAPI.post('/exploit/camera', {
        target,
        context
      });
      return response.data;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Cadena de exploits
   * @param {string} target - Objetivo
   * @param {Array} exploits - Lista de exploits a aplicar
   */
  const exploitChain = useCallback(async (target, exploits = []) => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await leviathanAPI.post('/exploit/chain', {
        target,
        exploits
      });
      return response.data;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Explotación con KRAKEN
   * @param {string} target - Objetivo
   * @param {string} exploitType - Tipo de exploit
   */
  const krakenExploit = useCallback(async (target, exploitType = 'auto') => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await leviathanAPI.post('/exploit/kraken', {
        target,
        exploit_type: exploitType
      });
      return response.data;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Análisis con IA (detección de objetos)
   * @param {string} target - Imagen o stream a analizar
   * @param {Object} context - Contexto adicional
   */
  const analyzeWithAI = useCallback(async (target, context = {}) => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await leviathanAPI.post('/ai/analyze', {
        target,
        context
      });
      return response.data;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Detección de objetos
   * @param {string} target - Imagen o stream
   * @param {Object} options - Opciones
   */
  const detectObjects = useCallback(async (target, options = {}) => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await leviathanAPI.post('/ai/detect', {
        target,
        ...options
      });
      return response.data;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Generar informe
   * @param {string} target - Objetivo del informe
   * @param {Object} data - Datos para el informe
   * @param {string} reportType - Tipo de informe (json, html, pdf)
   */
  const generateReport = useCallback(async (target, data = {}, reportType = 'html') => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await leviathanAPI.post('/report/generate', {
        target,
        data,
        report_type: reportType
      });
      return response.data;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Obtener estadísticas
   */
  const getStats = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await leviathanAPI.get('/stats');
      return response.data;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Obtener alertas
   */
  const getAlerts = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await leviathanAPI.get('/alerts');
      return response.data;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Obtener mapa de amenazas
   */
  const getThreatMap = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await leviathanAPI.get('/threat-map');
      return response.data;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Obtener servicios
   */
  const getServices = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await leviathanAPI.get('/services');
      return response.data;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Obtener historial de operaciones
   */
  const getHistory = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await leviathanAPI.get('/history');
      return response.data;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Limpiar error
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    isLoading,
    error,
    clearError,
    getStatus,
    scanNetwork,
    scanCameras,
    quickScan,
    exploitCamera,
    exploitChain,
    krakenExploit,
    analyzeWithAI,
    detectObjects,
    generateReport,
    getStats,
    getAlerts,
    getThreatMap,
    getServices,
    getHistory
  };
};

/**
 * Proveedor de contexto LEVIATHAN
 */
const LeviathanContext = createContext(null);

export const LeviathanProvider = ({ children }) => {
  const apiState = useLeviathanAPI();
  return React.createElement(LeviathanContext.Provider, { value: apiState }, children);
};

export const useLeviathan = () => {
  const ctx = useContext(LeviathanContext);
  return ctx || useLeviathanAPI();
};

export default useLeviathanAPI;
