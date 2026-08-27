"""
Report Model
===========
Modelo de datos para informes.
"""

from dataclasses import dataclass, field
from typing import Dict, List
from enum import Enum
import datetime


class ReportType(Enum):
    """Tipos de informes"""
    SCAN = "scan"
    SIMULATION = "simulation"
    MONITORING = "monitoring"
    INVESTIGATION = "investigation"
    DEFENSE = "defense"
    THREAT = "threat"
    DAILY = "daily"
    WEEKLY = "weekly"


@dataclass
class Report:
    """Modelo de informe"""
    report_id: str
    type: ReportType
    title: str
    target: str
    summary: str
    findings: List[Dict]
    recommendations: List[str]
    risk_score: float
    severity: str
    timestamp: str
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "report_id": self.report_id,
            "type": self.type.value,
            "title": self.title,
            "target": self.target,
            "summary": self.summary,
            "findings": self.findings,
            "recommendations": self.recommendations,
            "risk_score": self.risk_score,
            "severity": self.severity,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Report":
        return cls(
            report_id=data.get("report_id", ""),
            type=ReportType(data.get("type", "scan")),
            title=data.get("title", ""),
            target=data.get("target", ""),
            summary=data.get("summary", ""),
            findings=data.get("findings", []),
            recommendations=data.get("recommendations", []),
            risk_score=data.get("risk_score", 0.0),
            severity=data.get("severity", "medium"),
            timestamp=data.get("timestamp", datetime.datetime.now().isoformat()),
            metadata=data.get("metadata", {})
        )
