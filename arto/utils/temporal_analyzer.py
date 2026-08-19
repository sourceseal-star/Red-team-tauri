"""
Temporal Analyzer - Analizador Temporal
=======================================
Analiza patrones y tendencias a lo largo del tiempo.
"""

import asyncio
import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import statistics


@dataclass
class TemporalAnalysis:
    """Análisis temporal"""
    target: str
    time_range: str
    trends: Dict[str, Dict]
    anomalies: List[Dict]
    patterns: List[Dict]
    predictions: List[Dict]
    timestamp: str
    
    def to_dict(self) -> Dict:
        return {
            "target": self.target,
            "time_range": self.time_range,
            "trends": self.trends,
            "anomalies": self.anomalies,
            "patterns": self.patterns,
            "predictions": self.predictions,
            "timestamp": self.timestamp
        }


class TemporalAnalyzer:
    """Analizador Temporal Autónomo"""
    
    def __init__(self):
        self.time_series: Dict[str, Dict[str, List[Any]]] = {}
        self.trend_data: Dict[str, Dict] = {}
    
    async def analyze_temporal(self, target: str, *data_sources: Dict) -> TemporalAnalysis:
        """
        Analiza datos temporales de múltiples fuentes.
        
        Args:
            target: Objetivo del análisis
            data_sources: Fuentes de datos a analizar
            
        Returns:
            TemporalAnalysis: Análisis temporal completo
        """
        trends = {}
        anomalies = []
        patterns = []
        predictions = []
        
        # Procesar cada fuente de datos
        for data in data_sources:
            if "timestamp" in data:
                # Almacenar en series de tiempo
                await self._store_time_series(target, data)
            
            # Analizar tendencias
            if "behavior_data" in data:
                trends.update(await self._analyze_behavior_trends(target, data["behavior_data"]))
            
            if "requests" in data:
                trends.update(await self._analyze_request_trends(target, data["requests"]))
        
        # Detectar anomalías temporales
        anomalies = await self._detect_temporal_anomalies(target)
        
        # Identificar patrones temporales
        patterns = await self._identify_temporal_patterns(target)
        
        # Generar predicciones
        predictions = await self._generate_temporal_predictions(target)
        
        return TemporalAnalysis(
            target=target,
            time_range="Últimas 24 horas",
            trends=trends,
            anomalies=anomalies,
            patterns=patterns,
            predictions=predictions,
            timestamp=datetime.datetime.now().isoformat()
        )
    
    async def _store_time_series(self, target: str, data: Dict):
        """Almacena datos en series de tiempo"""
        timestamp = data.get("timestamp", datetime.datetime.now().isoformat())
        
        if target not in self.time_series:
            self.time_series[target] = {}
        
        # Almacenar cada métrica
        for key, value in data.items():
            if key == "timestamp":
                continue
            
            if key not in self.time_series[target]:
                self.time_series[target][key] = []
            
            self.time_series[target][key].append({
                "timestamp": timestamp,
                "value": value
            })
            
            # Limitar tamaño
            if len(self.time_series[target][key]) > 1000:
                self.time_series[target][key] = self.time_series[target][key][-1000:]
    
    async def _analyze_behavior_trends(self, target: str, behavior_data: Dict) -> Dict:
        """Analiza tendencias de comportamiento"""
        trends = {}
        
        # Tendencias de tasa de solicitudes
        if "request_rate" in behavior_data:
            trends["request_rate"] = await self._calculate_trend(
                target, "request_rate", behavior_data["request_rate"]
            )
        
        # Tendencias de tasa de errores
        if "error_rate" in behavior_data:
            trends["error_rate"] = await self._calculate_trend(
                target, "error_rate", behavior_data["error_rate"]
            )
        
        # Tendencias de IPs únicas
        if "unique_ips" in behavior_data:
            trends["unique_ips"] = await self._calculate_trend(
                target, "unique_ips", behavior_data["unique_ips"]
            )
        
        # Tendencias de intentos de login fallidos
        if "failed_logins" in behavior_data:
            trends["failed_logins"] = await self._calculate_trend(
                target, "failed_logins", behavior_data["failed_logins"]
            )
        
        return trends
    
    async def _analyze_request_trends(self, target: str, requests: List[Dict]) -> Dict:
        """Analiza tendencias en solicitudes"""
        trends = {}
        
        # Agrupar por hora
        hourly_counts = {}
        for req in requests:
            timestamp = req.get("timestamp", "")
            try:
                dt = datetime.datetime.fromisoformat(timestamp)
                hour = dt.strftime("%Y-%m-%d %H:00")
                hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
            except:
                pass
        
        # Calcular tendencia
        if hourly_counts:
            hours = sorted(hourly_counts.keys())
            values = [hourly_counts[h] for h in hours]
            
            if len(values) > 1:
                slope = self._calculate_slope(values)
                trends["request_trend"] = {
                    "direction": "increasing" if slope > 0 else "decreasing" if slope < 0 else "stable",
                    "slope": slope,
                    "values": values,
                    "hours": hours
                }
        
        return trends
    
    async def _calculate_trend(self, target: str, metric: str, current_value: Any) -> Dict:
        """Calcula la tendencia de una métrica"""
        if target not in self.time_series or metric not in self.time_series[target]:
            return {
                "metric": metric,
                "direction": "stable",
                "slope": 0,
                "current": current_value
            }
        
        values = [v["value"] for v in self.time_series[target][metric] if isinstance(v["value"], (int, float))]
        
        if len(values) < 2:
            return {
                "metric": metric,
                "direction": "stable",
                "slope": 0,
                "current": current_value
            }
        
        slope = self._calculate_slope(values)
        direction = "increasing" if slope > 0.1 else "decreasing" if slope < -0.1 else "stable"
        
        return {
            "metric": metric,
            "direction": direction,
            "slope": slope,
            "current": current_value,
            "history": values[-10:]  # Últimos 10 valores
        }
    
    def _calculate_slope(self, values: List[float]) -> float:
        """Calcula la pendiente de una serie de valores"""
        if len(values) < 2:
            return 0.0
        
        n = len(values)
        x = list(range(n))
        y = values
        
        # Calcular pendiente usando mínimos cuadrados
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi ** 2 for xi in x)
        
        numerator = n * sum_xy - sum_x * sum_y
        denominator = n * sum_x2 - sum_x ** 2
        
        if denominator == 0:
            return 0.0
        
        return numerator / denominator
    
    async def _detect_temporal_anomalies(self, target: str) -> List[Dict]:
        """Detecta anomalías temporales"""
        anomalies = []
        
        if target not in self.time_series:
            return anomalies
        
        for metric, values in self.time_series[target].items():
            if len(values) < 5:
                continue
            
            # Calcular media y desviación estándar
            numeric_values = [v["value"] for v in values if isinstance(v["value"], (int, float))]
            
            if len(numeric_values) < 5:
                continue
            
            mean = statistics.mean(numeric_values)
            std = statistics.stdev(numeric_values)
            
            # Verificar el último valor
            last_value = numeric_values[-1]
            deviation = abs(last_value - mean) / std if std > 0 else 0
            
            if deviation > 2.5:
                anomalies.append({
                    "metric": metric,
                    "value": last_value,
                    "expected": mean,
                    "deviation": deviation,
                    "severity": "high" if deviation > 3.0 else "medium",
                    "timestamp": values[-1].get("timestamp", "")
                })
        
        return anomalies
    
    async def _identify_temporal_patterns(self, target: str) -> List[Dict]:
        """Identifica patrones temporales"""
        patterns = []
        
        if target not in self.time_series:
            return patterns
        
        # Patrones de periodicidad
        for metric, values in self.time_series[target].items():
            if len(values) < 10:
                continue
            
            # Verificar periodicidad diaria
            hourly_values = {}
            for v in values:
                try:
                    dt = datetime.datetime.fromisoformat(v["timestamp"])
                    hour = dt.hour
                    hourly_values[hour] = hourly_values.get(hour, 0) + (v["value"] if isinstance(v["value"], (int, float)) else 0)
                except:
                    pass
            
            if hourly_values:
                # Verificar si hay picos en horas específicas
                max_hour = max(hourly_values.items(), key=lambda x: x[1])
                min_hour = min(hourly_values.items(), key=lambda x: x[1])
                
                if max_hour[1] > 2 * min_hour[1] and min_hour[1] > 0:
                    patterns.append({
                        "type": "periodic",
                        "metric": metric,
                        "description": f"Patrón periódico en {metric} con pico a las {max_hour[0]}:00",
                        "severity": "low",
                        "confidence": 0.7
                    })
        
        return patterns
    
    async def _generate_temporal_predictions(self, target: str) -> List[Dict]:
        """Genera predicciones temporales"""
        predictions = []
        
        if target not in self.time_series:
            return predictions
        
        for metric, values in self.time_series[target].items():
            if len(values) < 5:
                continue
            
            numeric_values = [v["value"] for v in values if isinstance(v["value"], (int, float))]
            
            if len(numeric_values) < 5:
                continue
            
            # Calcular tendencia
            slope = self._calculate_slope(numeric_values)
            last_value = numeric_values[-1]
            
            # Predecir siguiente valor
            predicted = last_value + slope
            
            # Determinar severidad
            if slope > 0.5:
                severity = "high"
            elif slope > 0.1:
                severity = "medium"
            elif slope < -0.5:
                severity = "high"
            elif slope < -0.1:
                severity = "medium"
            else:
                severity = "low"
            
            predictions.append({
                "metric": metric,
                "current": last_value,
                "predicted": predicted,
                "trend": "increasing" if slope > 0 else "decreasing" if slope < 0 else "stable",
                "severity": severity,
                "confidence": min(1.0, abs(slope) / 1.0)
            })
        
        return predictions
    
    async def get_temporal_stats(self, target: str) -> Dict:
        """Obtiene estadísticas temporales"""
        if target not in self.time_series:
            return {"target": target, "metrics": {}}
        
        stats = {}
        for metric, values in self.time_series[target].items():
            numeric_values = [v["value"] for v in values if isinstance(v["value"], (int, float))]
            
            if numeric_values:
                stats[metric] = {
                    "count": len(numeric_values),
                    "mean": statistics.mean(numeric_values),
                    "min": min(numeric_values),
                    "max": max(numeric_values),
                    "std": statistics.stdev(numeric_values) if len(numeric_values) > 1 else 0
                }
        
        return {"target": target, "metrics": stats}
