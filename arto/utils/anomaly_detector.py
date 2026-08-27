"""
Anomaly Detector - Detector de Anomalías
========================================
Detecta comportamientos anómalos en datos de seguridad.
"""

import asyncio
import datetime
import statistics
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class AnomalyType(Enum):
    """Tipos de anomalías"""
    STATISTICAL = "statistical"
    BEHAVIORAL = "behavioral"
    TEMPORAL = "temporal"
    PATTERN = "pattern"


@dataclass
class Anomaly:
    """Anomalía detectada"""
    anomaly_id: str
    type: AnomalyType
    name: str
    description: str
    severity: str
    confidence: float
    value: Any
    expected: Any
    deviation: float
    timestamp: str
    
    def to_dict(self) -> Dict:
        return {
            "anomaly_id": self.anomaly_id,
            "type": self.type.value,
            "name": self.name,
            "description": self.description,
            "severity": self.severity,
            "confidence": self.confidence,
            "value": str(self.value),
            "expected": str(self.expected),
            "deviation": self.deviation,
            "timestamp": self.timestamp
        }


class AnomalyDetector:
    """Detector de Anomalías Autónomo"""
    
    def __init__(self):
        self.baseline: Dict[str, Dict] = {}
        self.history: Dict[str, List[Any]] = {}
        self.thresholds: Dict[str, float] = {
            "request_rate": 3.0,  # Desviación estándar
            "error_rate": 2.0,
            "unique_ips": 2.5,
            "failed_logins": 2.0,
            "data_transfer": 3.0
        }
    
    async def detect_anomalies(self, data: Dict) -> List[Dict]:
        """
        Detecta anomalías en los datos proporcionados.
        
        Args:
            data: Datos a analizar
            
        Returns:
            Lista de anomalías detectadas
        """
        anomalies = []
        
        # Detectar anomalías estadísticas
        anomalies.extend(await self._detect_statistical_anomalies(data))
        
        # Detectar anomalías de comportamiento
        anomalies.extend(await self._detect_behavioral_anomalies(data))
        
        # Detectar anomalías temporales
        anomalies.extend(await self._detect_temporal_anomalies(data))
        
        return [a.to_dict() for a in anomalies]
    
    async def _detect_statistical_anomalies(self, data: Dict) -> List[Anomaly]:
        """Detecta anomalías estadísticas"""
        anomalies = []
        
        # Métricas comunes
        metrics = {
            "request_rate": data.get("request_rate", 0),
            "error_rate": data.get("error_rate", 0),
            "unique_ips": data.get("unique_ips", 0),
            "failed_logins": data.get("failed_logins", 0),
            "data_transfer": data.get("data_transfer", 0)
        }
        
        for metric, value in metrics.items():
            if value == 0:
                continue
            
            # Obtener baseline
            baseline = self.baseline.get(metric, {"mean": 0, "std": 1})
            mean = baseline.get("mean", 0)
            std = baseline.get("std", 1)
            
            # Calcular desviación
            if std > 0:
                deviation = abs(value - mean) / std
            else:
                deviation = 0
            
            # Detectar anomalía
            threshold = self.thresholds.get(metric, 2.0)
            if deviation > threshold:
                severity = "critical" if deviation > threshold * 2 else "high" if deviation > threshold * 1.5 else "medium"
                confidence = min(1.0, deviation / (threshold * 2))
                
                anomaly = Anomaly(
                    anomaly_id=f"stat_{metric}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                    type=AnomalyType.STATISTICAL,
                    name=f"Anomalía en {metric}",
                    description=f"Valor {value} desvía {deviation:.2f} desviaciones estándar del baseline",
                    severity=severity,
                    confidence=confidence,
                    value=value,
                    expected=mean,
                    deviation=deviation,
                    timestamp=datetime.datetime.now().isoformat()
                )
                anomalies.append(anomaly)
        
        return anomalies
    
    async def _detect_behavioral_anomalies(self, data: Dict) -> List[Anomaly]:
        """Detecta anomalías de comportamiento"""
        anomalies = []
        
        # Comportamientos sospechosos
        suspicious_behaviors = {
            "high_request_rate": {
                "condition": lambda d: d.get("request_rate", 0) > 100,
                "description": "Tasa de solicitudes extremadamente alta",
                "severity": "high"
            },
            "high_error_rate": {
                "condition": lambda d: d.get("error_rate", 0) > 0.5,
                "description": "Tasa de errores muy alta",
                "severity": "high"
            },
            "many_unique_ips": {
                "condition": lambda d: d.get("unique_ips", 0) > 50,
                "description": "Número de IPs únicas sospechoso",
                "severity": "medium"
            },
            "many_failed_logins": {
                "condition": lambda d: d.get("failed_logins", 0) > 10,
                "description": "Múltiples intentos de login fallidos",
                "severity": "high"
            },
            "high_data_transfer": {
                "condition": lambda d: d.get("data_transfer", 0) > 10000000,  # 10MB
                "description": "Transferencia de datos sospechosamente alta",
                "severity": "medium"
            }
        }
        
        for behavior_name, behavior_data in suspicious_behaviors.items():
            if behavior_data["condition"](data):
                anomaly = Anomaly(
                    anomaly_id=f"beh_{behavior_name}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                    type=AnomalyType.BEHAVIORAL,
                    name=behavior_data["description"],
                    description=behavior_data["description"],
                    severity=behavior_data["severity"],
                    confidence=0.85,
                    value=data.get(list(behavior_data["condition"].__code__.co_varnames)[0], 0),
                    expected="Normal",
                    deviation=1.0,
                    timestamp=datetime.datetime.now().isoformat()
                )
                anomalies.append(anomaly)
        
        return anomalies
    
    async def _detect_temporal_anomalies(self, data: Dict) -> List[Anomaly]:
        """Detecta anomalías temporales"""
        anomalies = []
        
        # Verificar si hay datos históricos
        for metric, value in data.items():
            if metric not in self.history:
                continue
            
            history = self.history[metric]
            if len(history) < 5:
                continue
            
            # Calcular tendencias
            recent = history[-5:]
            mean = statistics.mean(recent)
            std = statistics.stdev(recent) if len(recent) > 1 else 1
            
            if std > 0:
                deviation = abs(value - mean) / std
            else:
                deviation = 0
            
            # Detectar anomalía
            if deviation > 2.5:
                severity = "high" if deviation > 3.0 else "medium"
                confidence = min(1.0, deviation / 3.0)
                
                anomaly = Anomaly(
                    anomaly_id=f"temp_{metric}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                    type=AnomalyType.TEMPORAL,
                    name=f"Anomalía temporal en {metric}",
                    description=f"Valor {value} desvía significativamente de la tendencia reciente",
                    severity=severity,
                    confidence=confidence,
                    value=value,
                    expected=mean,
                    deviation=deviation,
                    timestamp=datetime.datetime.now().isoformat()
                )
                anomalies.append(anomaly)
        
        return anomalies
    
    async def update_baseline(self, data: Dict):
        """Actualiza el baseline con nuevos datos"""
        for metric, value in data.items():
            if metric not in self.baseline:
                self.baseline[metric] = {"values": [], "mean": 0, "std": 1}
            
            # Agregar valor al historial
            self.baseline[metric]["values"].append(value)
            
            # Limitar historial
            if len(self.baseline[metric]["values"]) > 100:
                self.baseline[metric]["values"] = self.baseline[metric]["values"][-100:]
            
            # Recalcular estadísticas
            values = self.baseline[metric]["values"]
            if len(values) > 1:
                self.baseline[metric]["mean"] = statistics.mean(values)
                self.baseline[metric]["std"] = statistics.stdev(values)
            elif len(values) == 1:
                self.baseline[metric]["mean"] = values[0]
                self.baseline[metric]["std"] = 1
    
    async def update_history(self, metric: str, value: Any):
        """Actualiza el historial de una métrica"""
        if metric not in self.history:
            self.history[metric] = []
        
        self.history[metric].append(value)
        
        # Limitar historial
        if len(self.history[metric]) > 100:
            self.history[metric] = self.history[metric][-100:]
    
    async def get_anomaly_stats(self) -> Dict:
        """Obtiene estadísticas de detección de anomalías"""
        # Esto sería más preciso con datos reales de detección
        return {
            "total_anomalies": 0,
            "by_type": {
                "statistical": 0,
                "behavioral": 0,
                "temporal": 0,
                "pattern": 0
            },
            "by_severity": {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0
            }
        }
