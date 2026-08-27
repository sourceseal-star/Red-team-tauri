"""
Behavior Analyzer - Analizador de Comportamiento
=================================================
Analiza patrones de comportamiento para detectar anomalías.
"""

import asyncio
import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import statistics


class BehaviorType(Enum):
    """Tipos de comportamiento"""
    NORMAL = "normal"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"
    UNUSUAL = "unusual"


@dataclass
class BehaviorAnalysis:
    """Análisis de comportamiento"""
    analysis_id: str
    entity: str
    behavior_type: BehaviorType
    score: float  # 0.0 - 1.0 (0 = normal, 1 = malicioso)
    anomalies: List[Dict]
    patterns: List[Dict]
    recommendations: List[str]
    timestamp: str
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "analysis_id": self.analysis_id,
            "entity": self.entity,
            "behavior_type": self.behavior_type.value,
            "score": self.score,
            "anomalies": self.anomalies,
            "patterns": self.patterns,
            "recommendations": self.recommendations,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }


class BehaviorAnalyzer:
    """Analizador de Comportamiento Autónomo"""
    
    def __init__(self):
        self.pattern_recognizer = None
        self.anomaly_detector = None
        self.temporal_analyzer = None
        self.behavior_history: Dict[str, List[Dict]] = {}
        self.analysis_history: List[BehaviorAnalysis] = []
    
    async def analyze_behavior(self, entity: str, behavior_data: Dict) -> BehaviorAnalysis:
        """
        Analiza el comportamiento de una entidad.
        
        Args:
            entity: Entidad a analizar (IP, usuario, dominio, etc.)
            behavior_data: Datos de comportamiento
            
        Returns:
            BehaviorAnalysis: Análisis completo
        """
        analysis_id = f"ba_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        
        # Almacenar datos de comportamiento
        if entity not in self.behavior_history:
            self.behavior_history[entity] = []
        self.behavior_history[entity].append(behavior_data)
        
        # Limitar historial
        if len(self.behavior_history[entity]) > 100:
            self.behavior_history[entity] = self.behavior_history[entity][-100:]
        
        # Analizar con diferentes métodos
        anomalies = []
        patterns = []
        
        if self.anomaly_detector:
            anomalies = await self.anomaly_detector.detect_anomalies(behavior_data)
        
        if self.pattern_recognizer:
            patterns = await self.pattern_recognizer.recognize_patterns(behavior_data)
        
        # Calcular score de comportamiento
        score = await self._calculate_behavior_score(behavior_data, anomalies, patterns)
        
        # Determinar tipo de comportamiento
        behavior_type = self._determine_behavior_type(score, anomalies)
        
        # Generar recomendaciones
        recommendations = await self._generate_recommendations(
            entity, behavior_data, anomalies, patterns, behavior_type
        )
        
        # Crear análisis
        analysis = BehaviorAnalysis(
            analysis_id=analysis_id,
            entity=entity,
            behavior_type=behavior_type,
            score=score,
            anomalies=anomalies,
            patterns=patterns,
            recommendations=recommendations,
            timestamp=datetime.datetime.now().isoformat(),
            metadata={
                "behavior_data_size": len(behavior_data),
                "anomaly_count": len(anomalies),
                "pattern_count": len(patterns)
            }
        )
        
        # Guardar en historial
        self.analysis_history.append(analysis)
        
        return analysis
    
    async def _calculate_behavior_score(self, behavior_data: Dict, 
                                       anomalies: List[Dict], 
                                       patterns: List[Dict]) -> float:
        """Calcula el score de comportamiento (0.0 - 1.0)"""
        score = 0.0
        weights = {
            "anomalies": 0.5,
            "patterns": 0.3,
            "behavior_metrics": 0.2
        }
        
        # Score basado en anomalías
        anomaly_score = 0.0
        if anomalies:
            anomaly_score = sum(a.get("severity_score", 0.5) for a in anomalies) / len(anomalies)
            anomaly_score = min(1.0, anomaly_score * len(anomalies) * 0.2)
        
        # Score basado en patrones
        pattern_score = 0.0
        if patterns:
            malicious_patterns = sum(1 for p in patterns if p.get("type") == "malicious")
            suspicious_patterns = sum(1 for p in patterns if p.get("type") == "suspicious")
            pattern_score = (malicious_patterns * 0.8 + suspicious_patterns * 0.5) / len(patterns) if patterns else 0.0
        
        # Score basado en métricas de comportamiento
        behavior_metrics_score = await self._calculate_behavior_metrics_score(behavior_data)
        
        # Combinar scores
        score = (anomaly_score * weights["anomalies"] + 
                 pattern_score * weights["patterns"] + 
                 behavior_metrics_score * weights["behavior_metrics"])
        
        return max(0.0, min(1.0, score))
    
    async def _calculate_behavior_metrics_score(self, behavior_data: Dict) -> float:
        """Calcula score basado en métricas de comportamiento"""
        score = 0.0
        
        # Métricas comunes
        request_rate = behavior_data.get("request_rate", 0)
        error_rate = behavior_data.get("error_rate", 0)
        unique_ips = behavior_data.get("unique_ips", 0)
        failed_logins = behavior_data.get("failed_logins", 0)
        data_transfer = behavior_data.get("data_transfer", 0)
        
        # Calcular score basado en métricas
        if request_rate > 100:
            score += 0.3
        if error_rate > 0.5:
            score += 0.25
        if unique_ips > 50:
            score += 0.2
        if failed_logins > 5:
            score += 0.25
        if data_transfer > 1000000:  # 1MB
            score += 0.2
        
        return min(1.0, score)
    
    def _determine_behavior_type(self, score: float, anomalies: List[Dict]) -> BehaviorType:
        """Determina el tipo de comportamiento"""
        if score >= 0.9:
            return BehaviorType.MALICIOUS
        elif score >= 0.7:
            return BehaviorType.SUSPICIOUS
        elif score >= 0.4:
            return BehaviorType.UNUSUAL
        else:
            return BehaviorType.NORMAL
    
    async def _generate_recommendations(self, entity: str, behavior_data: Dict,
                                        anomalies: List[Dict], patterns: List[Dict],
                                        behavior_type: BehaviorType) -> List[str]:
        """Genera recomendaciones basadas en el análisis"""
        recommendations = []
        
        # Recomendaciones por tipo de comportamiento
        if behavior_type == BehaviorType.MALICIOUS:
            recommendations.append(f"🚨 BLOQUEAR INMEDIATAMENTE: {entity} - Comportamiento malicioso detectado")
            recommendations.append(f"🔍 Investigar origen de {entity}")
            recommendations.append(f"📊 Analizar tráfico asociado a {entity}")
        elif behavior_type == BehaviorType.SUSPICIOUS:
            recommendations.append(f"⚠️ MONITOREAR: {entity} - Comportamiento sospechoso")
            recommendations.append(f"🔍 Realizar escaneo profundo de {entity}")
            recommendations.append(f"📈 Aumentar nivel de logging para {entity}")
        elif behavior_type == BehaviorType.UNUSUAL:
            recommendations.append(f"👁️ OBSERVAR: {entity} - Comportamiento inusual")
            recommendations.append(f"📊 Revisar patrones de {entity}")
        
        # Recomendaciones por anomalías
        for anomaly in anomalies:
            severity = anomaly.get("severity", "medium")
            description = anomaly.get("description", "Anomalía")
            
            if severity == "critical":
                recommendations.append(f"🚨 ACCIÓN INMEDIATA: {description}")
            elif severity == "high":
                recommendations.append(f"⚠️ INVESTIGAR: {description}")
        
        # Recomendaciones por patrones
        for pattern in patterns:
            ptype = pattern.get("type", "unknown")
            if ptype == "malicious":
                recommendations.append(f"🚨 PATRÓN MALICIOSO: {pattern.get('description', 'Descripción no disponible')}")
            elif ptype == "suspicious":
                recommendations.append(f"⚠️ PATRÓN SOSPECHOSO: {pattern.get('description', 'Descripción no disponible')}")
        
        # Recomendaciones específicas por métricas
        if behavior_data.get("failed_logins", 0) > 10:
            recommendations.append(f"🔒 BLOQUEAR INTENTOS DE LOGIN FALLIDOS: {entity}")
        if behavior_data.get("request_rate", 0) > 1000:
            recommendations.append(f"🚦 LIMITAR TASA DE SOLICITUDES: {entity}")
        if behavior_data.get("error_rate", 0) > 0.8:
            recommendations.append(f"🔍 INVESTIGAR ERRORES: {entity}")
        
        # Eliminar duplicados
        recommendations = list(set(recommendations))
        
        return recommendations
    
    async def get_behavior_stats(self, entity: Optional[str] = None) -> Dict:
        """Obtiene estadísticas de comportamiento"""
        if entity:
            if entity in self.behavior_history:
                return {
                    "entity": entity,
                    "data_points": len(self.behavior_history[entity]),
                    "latest": self.behavior_history[entity][-1] if self.behavior_history[entity] else None
                }
            return {"entity": entity, "data_points": 0}
        
        stats = {}
        for entity, data in self.behavior_history.items():
            stats[entity] = len(data)
        
        return {
            "total_entities": len(self.behavior_history),
            "entity_stats": stats,
            "total_analyses": len(self.analysis_history)
        }
    
    async def get_anomaly_trends(self, entity: str, hours: int = 24) -> Dict:
        """Obtiene tendencias de anomalías para una entidad"""
        if entity not in self.behavior_history:
            return {"entity": entity, "trends": []}
        
        # Filtrar datos por tiempo
        cutoff = datetime.datetime.now() - datetime.timedelta(hours=hours)
        recent_data = [
            d for d in self.behavior_history[entity] 
            if datetime.datetime.fromisoformat(d.get("timestamp", "1970-01-01")) >= cutoff
        ]
        
        # Contar anomalías por hora
        hourly_anomalies = {}
        for data in recent_data:
            hour = datetime.datetime.fromisoformat(data.get("timestamp", "1970-01-01")).hour
            anomaly_count = data.get("anomaly_count", 0)
            hourly_anomalies[hour] = hourly_anomalies.get(hour, 0) + anomaly_count
        
        return {
            "entity": entity,
            "time_range": f"Últimas {hours} horas",
            "trends": hourly_anomalies
        }
