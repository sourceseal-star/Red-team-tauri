"""
Prediction Engine - Motor de Predicción
======================================
Predice posibles ataques y vulnerabilidades futuras.
"""

import asyncio
import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import hashlib


class PredictionType(Enum):
    """Tipos de predicciones"""
    ATTACK = "attack"
    VULNERABILITY = "vulnerability"
    THREAT = "threat"
    BEHAVIOR = "behavior"


@dataclass
class Prediction:
    """Predicción del motor"""
    prediction_id: str
    type: PredictionType
    target: str
    description: str
    probability: float  # 0.0 - 1.0
    severity: str  # critical, high, medium, low
    timestamp: str
    time_horizon: int  # horas
    confidence: float  # 0.0 - 1.0
    mitigation: Optional[Dict] = None
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "prediction_id": self.prediction_id,
            "type": self.type.value,
            "target": self.target,
            "description": self.description,
            "probability": self.probability,
            "severity": self.severity,
            "timestamp": self.timestamp,
            "time_horizon": self.time_horizon,
            "confidence": self.confidence,
            "mitigation": self.mitigation,
            "metadata": self.metadata
        }


class PredictionEngine:
    """Motor de Predicción Autónomo"""
    
    def __init__(self):
        self.learning_engine = None
        self.memory = None
        self.knowledge_base = None
        self.threat_intel = None
        self.models_loaded = False
        self.prediction_history: List[Prediction] = []
        
    async def load_models(self):
        """Carga los modelos de predicción"""
        print("📊 Cargando modelos de predicción...")
        
        # En implementación completa, esto cargaría modelos de ML
        # Por ahora, simulamos la carga
        await asyncio.sleep(0.5)
        
        self.models_loaded = True
        print("✅ Modelos de predicción cargados")
    
    async def predict_attacks(self, context: Dict, time_horizon: int = 24) -> List[Prediction]:
        """
        Predice posibles ataques.
        
        Args:
            context: Contexto actual (operaciones, predicciones, amenazas)
            time_horizon: Horas hacia adelante para predecir
            
        Returns:
            Lista de predicciones de ataques
        """
        if not self.models_loaded:
            await self.load_models()
        
        predictions = []
        
        # 1. Predicciones basadas en amenazas conocidas
        threat_predictions = await self._predict_from_threats(context, time_horizon)
        predictions.extend(threat_predictions)
        
        # 2. Predicciones basadas en patrones de comportamiento
        behavior_predictions = await self._predict_from_behavior(context, time_horizon)
        predictions.extend(behavior_predictions)
        
        # 3. Predicciones basadas en vulnerabilidades
        vulnerability_predictions = await self._predict_from_vulnerabilities(context, time_horizon)
        predictions.extend(vulnerability_predictions)
        
        # 4. Predicciones basadas en aprendizaje
        if self.learning_engine:
            learning_predictions = await self._predict_from_learning(context, time_horizon)
            predictions.extend(learning_predictions)
        
        # 5. Predicciones basadas en inteligencia de amenazas
        if self.threat_intel:
            intel_predictions = await self._predict_from_intel(context, time_horizon)
            predictions.extend(intel_predictions)
        
        # Ordenar por probabilidad
        predictions.sort(key=lambda p: p.probability, reverse=True)
        
        # Limitar a las mejores predicciones
        predictions = predictions[:10]
        
        # Guardar en historial
        self.prediction_history.extend(predictions)
        if self.memory:
            for pred in predictions:
                await self.memory.store_prediction(pred.to_dict())
        
        return predictions
    
    async def _predict_from_threats(self, context: Dict, time_horizon: int) -> List[Prediction]:
        """Predice ataques basados en amenazas conocidas"""
        predictions = []
        threats = context.get("threats", [])
        operations = context.get("operations", [])
        
        for threat in threats[:5]:  # Limitar a 5 amenazas
            target = threat.get("target", "unknown")
            threat_type = threat.get("type", "unknown")
            severity = threat.get("severity", "medium")
            
            # Generar ID
            pred_id = hashlib.sha256(f"{target}_{threat_type}_{datetime.datetime.now().isoformat()}".encode()).hexdigest()[:16]
            
            predictions.append(Prediction(
                prediction_id=pred_id,
                type=PredictionType.ATTACK,
                target=target,
                description=f"Posible ataque de tipo {threat_type} basado en amenaza detectada",
                probability=self._calculate_threat_probability(threat),
                severity=severity,
                timestamp=datetime.datetime.now().isoformat(),
                time_horizon=time_horizon,
                confidence=0.85,
                mitigation={
                    "action": "block",
                    "priority": "high",
                    "description": f"Bloquear {target} y monitorear actividad"
                },
                metadata={"source": "threat_analysis", "threat_id": threat.get("id")}
            ))
        
        return predictions
    
    async def _predict_from_behavior(self, context: Dict, time_horizon: int) -> List[Prediction]:
        """Predice ataques basados en patrones de comportamiento"""
        predictions = []
        operations = context.get("operations", [])
        
        # Buscar patrones de comportamiento sospechoso
        for op in operations[-10:]:  # Últimas 10 operaciones
            if op.get("type") == "monitoring":
                monitor_result = op.get("result", {}).get("monitor_result", {})
                behavior_data = monitor_result.get("behavior_data", {})
                
                if behavior_data.get("suspicious_count", 0) > 5:
                    target = op.get("target", "unknown")
                    pred_id = hashlib.sha256(f"behavior_{target}_{datetime.datetime.now().isoformat()}".encode()).hexdigest()[:16]
                    
                    predictions.append(Prediction(
                        prediction_id=pred_id,
                        type=PredictionType.BEHAVIOR,
                        target=target,
                        description=f"Comportamiento sospechoso detectado en {target}",
                        probability=0.75,
                        severity="high",
                        timestamp=datetime.datetime.now().isoformat(),
                        time_horizon=time_horizon,
                        confidence=0.80,
                        mitigation={
                            "action": "investigate",
                            "priority": "high",
                            "description": f"Investigar comportamiento en {target}"
                        },
                        metadata={"source": "behavior_analysis", "suspicious_count": behavior_data.get("suspicious_count")}
                    ))
        
        return predictions
    
    async def _predict_from_vulnerabilities(self, context: Dict, time_horizon: int) -> List[Prediction]:
        """Predice ataques basados en vulnerabilidades conocidas"""
        predictions = []
        operations = context.get("operations", [])
        
        for op in operations[-10:]:
            if op.get("type") == "scan":
                scan_result = op.get("result", {}).get("scan_result", {})
                vulnerabilities = scan_result.get("vulnerabilities", [])
                
                for vuln in vulnerabilities[:3]:  # Limitar a 3 vulnerabilidades
                    target = op.get("target", "unknown")
                    vuln_name = vuln.get("name", "unknown")
                    severity = vuln.get("severity", "medium")
                    
                    pred_id = hashlib.sha256(f"vuln_{target}_{vuln_name}_{datetime.datetime.now().isoformat()}".encode()).hexdigest()[:16]
                    
                    predictions.append(Prediction(
                        prediction_id=pred_id,
                        type=PredictionType.VULNERABILITY,
                        target=target,
                        description=f"Explotación potencial de {vuln_name} en {target}",
                        probability=self._calculate_vulnerability_probability(vuln),
                        severity=severity,
                        timestamp=datetime.datetime.now().isoformat(),
                        time_horizon=time_horizon,
                        confidence=0.82,
                        mitigation={
                            "action": "patch",
                            "priority": "critical" if severity == "critical" else "high",
                            "description": f"Aplicar parche para {vuln_name}"
                        },
                        metadata={"source": "vulnerability_scan", "vuln_id": vuln.get("id")}
                    ))
        
        return predictions
    
    async def _predict_from_learning(self, context: Dict, time_horizon: int) -> List[Prediction]:
        """Predice ataques basados en aprendizaje"""
        predictions = []
        
        if self.learning_engine:
            patterns = await self.learning_engine.get_patterns()
            
            for obs_type, pattern_data in patterns.items():
                if pattern_data.get("count", 0) > 5:  # Solo patrones significativos
                    # Predecir basado en patrones históricos
                    pred_id = hashlib.sha256(f"learning_{obs_type}_{datetime.datetime.now().isoformat()}".encode()).hexdigest()[:16]
                    
                    predictions.append(Prediction(
                        prediction_id=pred_id,
                        type=PredictionType.ATTACK,
                        target="multiple",
                        description=f"Ataque potencial basado en patrón de {obs_type}",
                        probability=0.65,
                        severity="medium",
                        timestamp=datetime.datetime.now().isoformat(),
                        time_horizon=time_horizon,
                        confidence=0.75,
                        mitigation={
                            "action": "monitor",
                            "priority": "medium",
                            "description": f"Monitorear patrones de {obs_type}"
                        },
                        metadata={"source": "learning_engine", "pattern_type": obs_type}
                    ))
        
        return predictions
    
    async def _predict_from_intel(self, context: Dict, time_horizon: int) -> List[Prediction]:
        """Predice ataques basados en inteligencia de amenazas"""
        predictions = []
        
        if self.threat_intel:
            intel_data = await self.threat_intel.get_current_threats()
            
            for threat in intel_data[:5]:
                target = threat.get("target", "unknown")
                pred_id = hashlib.sha256(f"intel_{target}_{datetime.datetime.now().isoformat()}".encode()).hexdigest()[:16]
                
                predictions.append(Prediction(
                    prediction_id=pred_id,
                    type=PredictionType.THREAT,
                    target=target,
                    description=f"Amenaza emergente: {threat.get('description', 'Descripción no disponible')}",
                    probability=threat.get("confidence", 0.7),
                    severity=threat.get("severity", "medium"),
                    timestamp=datetime.datetime.now().isoformat(),
                    time_horizon=time_horizon,
                    confidence=0.88,
                    mitigation={
                        "action": "alert",
                        "priority": "high",
                        "description": f"Alertar sobre amenaza en {target}"
                    },
                    metadata={"source": "threat_intelligence", "threat_id": threat.get("id")}
                ))
        
        return predictions
    
    def _calculate_threat_probability(self, threat: Dict) -> float:
        """Calcula la probabilidad de un ataque basado en una amenaza"""
        base_prob = 0.7
        
        severity = threat.get("severity", "medium")
        if severity == "critical":
            base_prob += 0.2
        elif severity == "high":
            base_prob += 0.15
        elif severity == "low":
            base_prob -= 0.1
        
        confidence = threat.get("confidence", 0.5)
        base_prob = base_prob * 0.6 + confidence * 0.4
        
        return max(0.0, min(1.0, base_prob))
    
    def _calculate_vulnerability_probability(self, vulnerability: Dict) -> float:
        """Calcula la probabilidad de explotación de una vulnerabilidad"""
        base_prob = 0.6
        
        severity = vulnerability.get("severity", "medium")
        if severity == "critical":
            base_prob += 0.3
        elif severity == "high":
            base_prob += 0.2
        elif severity == "low":
            base_prob -= 0.2
        
        cvss_score = vulnerability.get("cvss_score", 0)
        base_prob = base_prob * 0.7 + (cvss_score / 10) * 0.3
        
        return max(0.0, min(1.0, base_prob))
    
    async def get_prediction_stats(self) -> Dict:
        """Obtiene estadísticas de predicciones"""
        type_counts = {}
        for pred in self.prediction_history:
            ptype = pred.type.value
            type_counts[ptype] = type_counts.get(ptype, 0) + 1
        
        severity_counts = {}
        for pred in self.prediction_history:
            severity = pred.severity
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        return {
            "total_predictions": len(self.prediction_history),
            "type_counts": type_counts,
            "severity_counts": severity_counts,
            "avg_probability": sum(p.probability for p in self.prediction_history) / len(self.prediction_history) if self.prediction_history else 0
        }
