"""Modelo de Scan para KRAKEN v3.0."""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class Scan:
    id: str
    target: str
    scan_type: str = "network"  # network, service, vulnerability
    status: str = "pending"  # pending, running, completed, failed
    hosts_found: int = 0
    vulns_found: int = 0
    exploits_attempted: int = 0
    exploits_success: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration: Optional[float] = None
    error: Optional[str] = None
    
    def start(self):
        self.status = "running"
        self.started_at = datetime.now().isoformat()
    
    def complete(self):
        self.status = "completed"
        self.completed_at = datetime.now().isoformat()
        if self.started_at:
            start = datetime.fromisoformat(self.started_at)
            self.duration = (datetime.now() - start).total_seconds()
    
    def fail(self, error: str):
        self.status = "failed"
        self.error = error
        self.completed_at = datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "target": self.target,
            "scan_type": self.scan_type,
            "status": self.status,
            "hosts_found": self.hosts_found,
            "vulns_found": self.vulns_found,
            "exploits_attempted": self.exploits_attempted,
            "exploits_success": self.exploits_success,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration": self.duration,
            "error": self.error,
        }
