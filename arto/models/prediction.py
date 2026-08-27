"""
Prediction Model
================
Modelo de datos para predicciones.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
import datetime


class PredictionType(Enum):
    """Tipos de predicciones"""
    ATTACK = "attack"
    VULNERABILITY = "vulnerability"
    THREAT = "threat"
    BEHAVIOR = "behavior"


@dataclass
class Prediction:
    """Modelo de predicción"""
    prediction_id: str
    type: PredictionType
    target: str
    description: str
    probability: float
    severity: str
    timestamp: str
    time_horizon: int
    confidence: float
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
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Prediction":
        return cls(
            prediction_id=data.get("prediction_id", ""),
            type=PredictionType(data.get("type", "attack")),
            target=data.get("target", ""),
            description=data.get("description", ""),
            probability=data.get("probability", 0.0),
            severity=data.get("severity", "medium"),
            timestamp=data.get("timestamp", datetime.datetime.now().isoformat()),
            time_horizon=data.get("time_horizon", 24),
            confidence=data.get("confidence", 0.0),
            mitigation=data.get("mitigation"),
            metadata=data.get("metadata", {})
        )
