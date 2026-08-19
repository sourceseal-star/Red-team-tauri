"""
Decision Engine - Motor de Decisiones
====================================
Toma decisiones autónomas basadas en el contexto actual.
"""

import asyncio
import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import hashlib


class DecisionType(Enum):
    """Tipos de decisiones"""
    SCAN = "scan"
    ATTACK = "attack"
    DEFEND = "defend"
    MONITOR = "monitor"
    INVESTIGATE = "investigate"
    LOG_AND_CONTINUE = "log_and_continue"
    IGNORE = "ignore"


class RiskLevel(Enum):
    """Niveles de riesgo"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class Decision:
    """Decisión del motor"""
    decision_id: str
    action: str
    confidence: float  # 0.0 - 1.0
    reason: str
    risk_level: RiskLevel
    context: Dict
    timestamp: str
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "decision_id": self.decision_id,
            "action": self.action,
            "confidence": self.confidence,
            "reason": self.reason,
            "risk_level": self.risk_level.value,
            "context": self.context,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }


class DecisionEngine:
    """Motor de Decisiones Autónomas"""
    
    def __init__(self):
        self.learning_engine = None
        self.threat_intel = None
        self.memory = None
        self.decision_history: List[Decision] = []
        self.rules = self._load_default_rules()
        
    def _load_default_rules(self) -> Dict:
        """Carga las reglas por defecto"""
        return {
            "high_risk": {
                "condition": lambda ctx: ctx.get("risk_level") == RiskLevel.CRITICAL.value or \
                                        (ctx.get("threat_score", 0) > 0.9 and ctx.get("vulnerability_score", 0) > 0.7),
                "action": DecisionType.DEFEND.value,
                "confidence": 0.95,
                "reason": "Alto riesgo detectado - acción de defensa requerida"
            },
            "medium_risk": {
                "condition": lambda ctx: ctx.get("risk_level") == RiskLevel.HIGH.value or \
                                        (ctx.get("threat_score", 0) > 0.7 and ctx.get("vulnerability_score", 0) > 0.5),
                "action": DecisionType.INVESTIGATE.value,
                "confidence": 0.85,
                "reason": "Riesgo medio - investigación requerida"
            },
            "scan_result_with_vulnerabilities": {
                "condition": lambda ctx: ctx.get("type") == "scan_result" and \
                                        ctx.get("scan_result", {}).get("vulnerabilities", []),
                "action": DecisionType.INVESTIGATE.value,
                "confidence": 0.90,
                "reason": "Vulnerabilidades encontradas en escaneo"
            },
            "scan_result_clean": {
                "condition": lambda ctx: ctx.get("type") == "scan_result" and \
                                        not ctx.get("scan_result", {}).get("vulnerabilities", []) and \
                                        not ctx.get("scan_result", {}).get("threats", []),
                "action": DecisionType.MONITOR.value,
                "confidence": 0.70,
                "reason": "Escaneo limpio - continuar monitoreando"
            },
            "threat_detected": {
                "condition": lambda ctx: ctx.get("threat_detected", False) or \
                                        ctx.get("threat_score", 0) > 0.8,
                "action": DecisionType.DEFEND.value,
                "confidence": 0.98,
                "reason": "Amenaza detectada - acción de defensa inmediata"
            },
            "anomaly_detected": {
                "condition": lambda ctx: ctx.get("anomalies", []) and len(ctx.get("anomalies", [])) > 0,
                "action": DecisionType.INVESTIGATE.value,
                "confidence": 0.88,
                "reason": "Anomalías detectadas - investigación requerida"
            },
            "pattern_recognized": {
                "condition": lambda ctx: ctx.get("patterns", []) and len(ctx.get("patterns", [])) > 0,
                "action": DecisionType.ANALYZE.value,
                "confidence": 0.82,
                "reason": "Patrones reconocidos - análisis adicional"
            },
            "default": {
                "condition": lambda ctx: True,
                "action": DecisionType.LOG_AND_CONTINUE.value,
                "confidence": 0.50,
                "reason": "Sin acción específica requerida"
            }
        }
    
    async def decide_action(self, context: Dict) -> Decision:
        """
        Decide la mejor acción basada en el contexto.
        
        Args:
            context: Contexto de la decisión (escaneo, monitoreo, etc.)
            
        Returns:
            Decision: Decisión tomada
        """
        # Generar ID único
        context_str = json.dumps(context, sort_keys=True)
        decision_id = hashlib.sha256(context_str.encode()).hexdigest()[:16]
        
        # Evaluar reglas
        best_decision = None
        best_confidence = -1
        
        for rule_name, rule in self.rules.items():
            try:
                if rule["condition"](context):
                    confidence = rule["confidence"]
                    
                    # Ajustar confianza basado en aprendizaje
                    if self.learning_engine:
                        learned_confidence = await self.learning_engine.get_decision_confidence(
                            rule_name, context
                        )
                        confidence = (confidence + learned_confidence) / 2
                    
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_decision = Decision(
                            decision_id=decision_id,
                            action=rule["action"],
                            confidence=confidence,
                            reason=rule["reason"],
                            risk_level=self._determine_risk_level(context),
                            context=context,
                            timestamp=datetime.datetime.now().isoformat(),
                            metadata={"rule": rule_name}
                        )
            except Exception as e:
                # Log error but continue
                continue
        
        # Si no se encontró ninguna regla, usar default
        if best_decision is None:
            best_decision = Decision(
                decision_id=decision_id,
                action=DecisionType.LOG_AND_CONTINUE.value,
                confidence=0.5,
                reason="No se aplicó ninguna regla",
                risk_level=RiskLevel.INFO,
                context=context,
                timestamp=datetime.datetime.now().isoformat(),
                metadata={"rule": "default"}
            )
        
        # Guardar en historial
        self.decision_history.append(best_decision)
        if self.memory:
            await self.memory.store_decision(best_decision.to_dict())
        
        return best_decision
    
    def _determine_risk_level(self, context: Dict) -> RiskLevel:
        """Determina el nivel de riesgo del contexto"""
        risk_score = 0.0
        
        # Calcular score de riesgo
        if context.get("threat_score"):
            risk_score += context["threat_score"] * 0.4
        if context.get("vulnerability_score"):
            risk_score += context["vulnerability_score"] * 0.3
        if context.get("anomaly_score"):
            risk_score += context["anomaly_score"] * 0.2
        if context.get("impact_score"):
            risk_score += context["impact_score"] * 0.1
        
        # Determinar nivel
        if risk_score >= 0.9:
            return RiskLevel.CRITICAL
        elif risk_score >= 0.7:
            return RiskLevel.HIGH
        elif risk_score >= 0.4:
            return RiskLevel.MEDIUM
        elif risk_score >= 0.1:
            return RiskLevel.LOW
        else:
            return RiskLevel.INFO
    
    async def get_decision_history(self, limit: int = 100) -> List[Dict]:
        """Obtiene el historial de decisiones"""
        return [d.to_dict() for d in self.decision_history[-limit:]]
    
    async def get_decision_stats(self) -> Dict:
        """Obtiene estadísticas de decisiones"""
        action_counts = {}
        for decision in self.decision_history:
            action = decision.action
            action_counts[action] = action_counts.get(action, 0) + 1
        
        return {
            "total_decisions": len(self.decision_history),
            "action_counts": action_counts,
            "avg_confidence": sum(d.confidence for d in self.decision_history) / len(self.decision_history) if self.decision_history else 0
        }
    
    def add_rule(self, name: str, condition, action: str, confidence: float, reason: str):
        """Agrega una regla personalizada"""
        self.rules[name] = {
            "condition": condition,
            "action": action,
            "confidence": confidence,
            "reason": reason
        }
    
    def remove_rule(self, name: str):
        """Elimina una regla"""
        if name in self.rules:
            del self.rules[name]
