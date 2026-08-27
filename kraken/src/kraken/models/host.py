"""Modelo de Host para KRAKEN v3.0."""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class Host:
    ip: str
    hostname: Optional[str] = None
    status: str = "unknown"  # up, down, unknown
    os: Optional[str] = None
    ports: List[dict] = field(default_factory=list)
    services: dict = field(default_factory=dict)
    vulnerabilities: List[dict] = field(default_factory=list)
    mac: Optional[str] = None
    vendor: Optional[str] = None
    first_seen: str = field(default_factory=lambda: datetime.now().isoformat())
    last_seen: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        return {
            "ip": self.ip,
            "hostname": self.hostname,
            "status": self.status,
            "os": self.os,
            "ports": self.ports,
            "services": self.services,
            "vulnerabilities": self.vulnerabilities,
            "mac": self.mac,
            "vendor": self.vendor,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
        }
