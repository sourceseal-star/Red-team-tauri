"""
Knowledge Model
==============
Modelo de datos para la base de conocimiento.
"""

from dataclasses import dataclass, field
from typing import Dict, List
import datetime


@dataclass
class KnowledgeEntry:
    """Entrada de conocimiento"""
    id: str
    type: str  # observation, pattern, threat, vulnerability, recommendation
    data: Dict
    timestamp: str
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type,
            "data": self.data,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "KnowledgeEntry":
        return cls(
            id=data.get("id", ""),
            type=data.get("type", "observation"),
            data=data.get("data", {}),
            timestamp=data.get("timestamp", datetime.datetime.now().isoformat()),
            metadata=data.get("metadata", {})
        )
