"""
Threat Model
============
Modelo de datos para amenazas.
"""

from dataclasses import dataclass, field
from typing import Dict
from enum import Enum
import datetime


class ThreatSeverity(Enum):
    """Severidad de amenazas"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class Threat:
    """Modelo de amenaza"""
    id: str
    type: str
    target: str
    description: str
    severity: ThreatSeverity
    confidence: float
    source: str
    timestamp: str
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type,
            "target": self.target,
            "description": self.description,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "source": self.source,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Threat":
        return cls(
            id=data.get("id", ""),
            type=data.get("type", ""),
            target=data.get("target", ""),
            description=data.get("description", ""),
            severity=ThreatSeverity(data.get("severity", "medium")),
            confidence=data.get("confidence", 0.0),
            source=data.get("source", "unknown"),
            timestamp=data.get("timestamp", datetime.datetime.now().isoformat()),
            metadata=data.get("metadata", {})
        )
