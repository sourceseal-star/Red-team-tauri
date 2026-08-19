/**
 * ARTO Provider - Proveedor de Contexto ARTO
 * =========================================
 * Proporciona el contexto ARTO a toda la aplicación.
 */

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { artoApi, artoWebSocket } from '../api';
import {
  ARTOContext,
  Operation,
  Prediction,
  Threat,
  Report,
  SystemStats
} from '../types/arto';

// 🎯 Contexto ARTO
const ARTOContext = createContext<ARTOContext | undefined>(undefined);

// 🎯 Proveedor ARTO
interface ARTOProviderProps {
  children: ReactNode;
  autoConnect?: boolean;
  autoStart?: boolean;
}

export function ARTOProvider({
  children,
  autoConnect = true,
  autoStart = true
}: ARTOProviderProps) {
  const [operations, setOperations] = useState<Operation[]>([]);
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [threats, setThreats] = useState<Threat[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [systemStats, setSystemStats] = useState<SystemStats | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // 🔄 Cargar datos iniciales
  const loadInitialData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      // Obtener estado del sistema
      const statusResponse = await artoApi.getStatus();
      if (statusResponse.status === 'success') {
        setSystemStats(statusResponse.data || null);
      }

      // Obtener operaciones
      const operationsResponse = await artoApi.getOperations();
      if (operationsResponse.status === 'success') {
        setOperations(operationsResponse.data?.operations || []);
      }

      // Obtener predicciones
      const predictionsResponse = await artoApi.getPredictions();
      if (predictionsResponse.status === 'success') {
        setPredictions(predictionsResponse.data?.predictions || []);
      }

      // Obtener amenazas
      const threatsResponse = await artoApi.getThreats();
      if (threatsResponse.status === 'success') {
        setThreats(threatsResponse.data?.threats || []);
      }

      // Iniciar el sistema si autoStart está activado (una sola vez)
      if (autoStart && statusResponse.data?.running === false && statusResponse.status === 'success') {
        try {
          await artoApi.start();
          // Recargar estado después de iniciar
          const newStatusResponse = await artoApi.getStatus();
          if (newStatusResponse.status === 'success') {
            setSystemStats(newStatusResponse.data || null);
          }
        } catch (e) {
          // ARTO no pudo iniciar — no reintentar en cada polling
          console.warn('[ARTO] Auto-start falló:', e);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar datos iniciales');
    } finally {
      setIsLoading(false);
    }
  }, [autoStart]);

  // 🎯 Configurar WebSocket
  useEffect(() => {
    if (!autoConnect) return;

    // Conectar WebSocket
    artoWebSocket.connect();

    // Manejar mensajes WebSocket
    const messageHandler = (event: any) => {
      switch (event.type) {
        case 'operation':
          setOperations(prev => [event.data, ...prev].slice(0, 100));
          break;
        case 'prediction':
          setPredictions(prev => [event.data, ...prev].slice(0, 50));
          break;
        case 'threat':
          setThreats(prev => [event.data, ...prev].slice(0, 50));
          break;
        case 'status':
          setSystemStats(prev => ({ ...prev, ...event.data }));
          break;
      }
    };

    artoWebSocket.onMessage(messageHandler);

    // Limpiar al desmontar
    return () => {
      artoWebSocket.offMessage(messageHandler);
      artoWebSocket.disconnect();
    };
  }, [autoConnect]);

  // 🔄 Cargar datos iniciales al montar
  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  // 🔄 Actualizar datos periódicamente
  useEffect(() => {
    const interval = setInterval(() => {
      // Solo polling si ARTO está activo — evita rate limit cuando está inactivo
      if (systemStats?.running) {
        loadInitialData();
      }
    }, 60000); // Cada 60 segundos — reduce rate limit pressure

    return () => clearInterval(interval);
  }, [loadInitialData]);

  // 🎯 Funciones de acción
  const executeOperation = useCallback(async (operationType: string, target: string) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await artoApi.autonomousOperation(operationType, target);
      if (response.status === 'success') {
        // Recargar operaciones
        const operationsResponse = await artoApi.getOperations();
        if (operationsResponse.status === 'success') {
          setOperations(operationsResponse.data?.operations || []);
        }
        return response;
      } else {
        setError(response.error || 'Error al ejecutar operación');
        return response;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al ejecutar operación');
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const predictAttacks = useCallback(async (timeHorizon: number = 24) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await artoApi.predictAttacks(timeHorizon);
      if (response.status === 'success') {
        setPredictions(response.data?.predictions || []);
        return response;
      } else {
        setError(response.error || 'Error al predecir ataques');
        return response;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al predecir ataques');
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const respondToThreat = useCallback(async (threat: Threat) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await artoApi.respondToThreat(threat);
      if (response.status === 'success') {
        // Recargar amenazas
        const threatsResponse = await artoApi.getThreats();
        if (threatsResponse.status === 'success') {
          setThreats(threatsResponse.data?.threats || []);
        }
        return response;
      } else {
        setError(response.error || 'Error al responder a amenaza');
        return response;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al responder a amenaza');
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const scanTarget = useCallback(async (target: string, scanType: 'full' | 'quick' | 'deep' = 'full') => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await artoApi.scanTarget(target, scanType);
      if (response.status === 'success') {
        // La operación de escaneo se añadirá automáticamente a través de WebSocket
        return response;
      } else {
        setError(response.error || 'Error al escanear objetivo');
        return response;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al escanear objetivo');
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const simulateAttack = useCallback(async (templateName: string, target: string) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await artoApi.simulateAttack(templateName, target);
      if (response.status === 'success') {
        return response;
      } else {
        setError(response.error || 'Error al simular ataque');
        return response;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al simular ataque');
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const refreshData = useCallback(async () => {
    await loadInitialData();
  }, [loadInitialData]);

  // 🎯 Contexto a proveer
  const contextValue: ARTOContext = {
    arto: null, // Se puede usar artoApi directamente
    operations,
    predictions,
    threats,
    reports,
    isLoading,
    error,
    // Funciones
    executeOperation,
    predictAttacks,
    respondToThreat,
    scanTarget,
    simulateAttack,
    refreshData
  };

  return (
    <ARTOContext.Provider value={contextValue}>
      {children}
    </ARTOContext.Provider>
  );
}

// 🎯 Hook personalizado para usar el contexto ARTO
export function useARTO() {
  const context = useContext(ARTOContext);
  
  if (context === undefined) {
    throw new Error('useARTO debe ser usado dentro de un ARTOProvider');
  }

  return context;
}

// 🎯 Exportar el contexto para uso directo (si es necesario)
export { ARTOContext };
