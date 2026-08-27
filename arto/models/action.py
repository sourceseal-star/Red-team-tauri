"""
Action Model
============
Modelo de datos para acciones.
"""

from dataclasses import dataclass, field
from typing import Dict, Any
from enum import Enum
import datetime


class ActionType(Enum):
    """Tipos de acciones"""
    SCAN = "scan"
    ATTACK = "attack"
    DEFEND = "defend"
    MONITOR = "monitor"
    INVESTIGATE = "investigate"
    BLOCK = "block"
    ALERT = "alert"
    LOG = "log"
    NOTIFY = "notify"


@dataclass
class Action:
    """Modelo de acción"""
    action_id: str
    action_type: ActionType
    target: str
    status: str
    message: str
    data: Dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "target": self.target,
            "status": self.status,
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Action":
        return cls(
            action_id=data.get("action_id", ""),
            action_type=ActionType(data.get("action_type", "log")),
            target=data.get("target", ""),
            status=data.get("status", "success"),
            message=data.get("message", ""),
            data=data.get("data", {}),
            timestamp=data.get("timestamp", datetime.datetime.now().isoformat())
        )
