"""
Decision Model
=============
Modelo de datos para decisiones.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
from enum import Enum
import datetime


class DecisionAction(Enum):
    """Acciones de decisión"""
    SCAN = "scan"
    ATTACK = "attack"
    DEFEND = "defend"
    MONITOR = "monitor"
    INVESTIGATE = "investigate"
    BLOCK = "block"
    ALERT = "alert"
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
    """Modelo de decisión"""
    decision_id: str
    action: str
    confidence: float
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
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Decision":
        return cls(
            decision_id=data.get("decision_id", ""),
            action=data.get("action", ""),
            confidence=data.get("confidence", 0.0),
            reason=data.get("reason", ""),
            risk_level=RiskLevel(data.get("risk_level", "info")),
            context=data.get("context", {}),
            timestamp=data.get("timestamp", datetime.datetime.now().isoformat()),
            metadata=data.get("metadata", {})
        )
