#!/usr/bin/env python3
"""
SOAR Incident Manager — Lifecycle management for security incidents
===================================================================
States: OPEN → INVESTIGATING → CONTAINED → ERADICATED → RECOVERED → CLOSED
Tracks MTTR, MTTD, auto-assigns playbooks based on MITRE technique.
"""

import json
import uuid
import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum


class IncidentState(Enum):
    OPEN          = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    CONTAINED     = "CONTAINED"
    ERADICATED    = "ERADICATED"
    RECOVERED     = "RECOVERED"
    CLOSED        = "CLOSED"


class Severity(Enum):
    LOW      = 1
    MEDIUM   = 2
    HIGH     = 3
    CRITICAL = 4


# MITRE → Playbook mapping
MITRE_PLAYBOOK_MAP = {
    "T1566": "playbook_phishing",
    "T1486": "playbook_ransomware",
    "T1071": "playbook_c2_beaconing",
    "T1110": "playbook_credential_stuffing",
    "T1021": "playbook_lateral_movement",
    "T1041": "playbook_data_exfiltration",
}

# MITRE → auto-escalate severity
MITRE_SEVERITY_MAP = {
    "T1486": "CRITICAL",  # Ransomware
    "T1041": "CRITICAL",  # Data exfiltration
    "T1566": "HIGH",
    "T1071": "HIGH",
    "T1021": "HIGH",
    "T1110": "MEDIUM",
}


@dataclass
class StateTransition:
    from_state: str
    to_state: str
    timestamp: str
    note: str = ""


@dataclass
class Incident:
    id: str
    title: str
    severity: str
    mitre_techniques: List[str]
    source_ip: str
    affected_hosts: List[str]
    state: str
    created_at: str
    assigned_playbook: Optional[str]
    state_history: List[Dict] = field(default_factory=list)
    detected_at: Optional[str] = None
    respond_at: Optional[str] = None
    recover_at: Optional[str] = None
    closed_at: Optional[str] = None
    mttr_seconds: Optional[float] = None
    mttd_seconds: Optional[float] = None
    notes: List[str] = field(default_factory=list)
    raw_alert: Dict = field(default_factory=dict)


class IncidentManager:
    """
    Manages the full lifecycle of security incidents.

    Usage:
        mgr = IncidentManager()
        inc = mgr.create_incident(alert)
        mgr.update_state(inc.id, "INVESTIGATING")
        report = mgr.export_report(inc.id)
        metrics = mgr.get_metrics()
    """

    def __init__(self):
        self.incidents: Dict[str, Incident] = {}

    def _now(self) -> str:
        return datetime.datetime.utcnow().isoformat() + "Z"

    def _escalate_severity(self, severity: str, mitre_techniques: List[str]) -> str:
        """Auto-escalate severity based on MITRE technique criticality."""
        current_level = Severity[severity].value if severity in Severity.__members__ else 2
        for technique in mitre_techniques:
            mapped = MITRE_SEVERITY_MAP.get(technique)
            if mapped and Severity[mapped].value > current_level:
                current_level = Severity[mapped].value
        return Severity(current_level).name

    def _assign_playbook(self, mitre_techniques: List[str]) -> Optional[str]:
        """Auto-assign playbook based on first matching MITRE technique."""
        for technique in mitre_techniques:
            if technique in MITRE_PLAYBOOK_MAP:
                return MITRE_PLAYBOOK_MAP[technique]
        return None

    def create_incident(self, alert: Dict[str, Any]) -> Incident:
        """Create a new incident from an XDR-like alert."""
        now = self._now()
        raw_severity = alert.get("severity", "MEDIUM").upper()
        mitre_techniques = alert.get("mitre_techniques", [])

        # Normalize severity
        if raw_severity not in Severity.__members__:
            raw_severity = "MEDIUM"

        # Auto-escalate based on MITRE
        final_severity = self._escalate_severity(raw_severity, mitre_techniques)
        assigned_playbook = self._assign_playbook(mitre_techniques)

        incident = Incident(
            id=alert.get("id") or f"INC-{uuid.uuid4().hex[:8].upper()}",
            title=alert.get("title", "Security Incident"),
            severity=final_severity,
            mitre_techniques=mitre_techniques,
            source_ip=alert.get("source_ip", ""),
            affected_hosts=alert.get("affected_hosts", []),
            state=IncidentState.OPEN.value,
            created_at=now,
            detected_at=alert.get("timestamp") or now,
            assigned_playbook=assigned_playbook,
            raw_alert=alert,
            state_history=[{
                "from_state": None,
                "to_state": IncidentState.OPEN.value,
                "timestamp": now,
                "note": "Incident created from XDR alert"
            }]
        )

        self.incidents[incident.id] = incident
        return incident

    def update_state(self, incident_id: str, new_state: str, note: str = "") -> Incident:
        """Transition incident to a new state with timestamp tracking."""
        incident = self.incidents.get(incident_id)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")

        if new_state not in IncidentState.__members__:
            raise ValueError(f"Invalid state: {new_state}. Valid: {[s.value for s in IncidentState]}")

        now = self._now()
        transition = {
            "from_state": incident.state,
            "to_state": new_state,
            "timestamp": now,
            "note": note
        }
        incident.state_history.append(transition)
        incident.state = new_state

        # Track timing milestones
        if new_state == IncidentState.INVESTIGATING.value and not incident.respond_at:
            incident.respond_at = now
            if incident.detected_at:
                t1 = datetime.datetime.fromisoformat(incident.detected_at.rstrip("Z"))
                t2 = datetime.datetime.fromisoformat(now.rstrip("Z"))
                incident.mttd_seconds = (t2 - t1).total_seconds()

        elif new_state == IncidentState.RECOVERED.value and not incident.recover_at:
            incident.recover_at = now
            if incident.detected_at:
                t1 = datetime.datetime.fromisoformat(incident.detected_at.rstrip("Z"))
                t2 = datetime.datetime.fromisoformat(now.rstrip("Z"))
                incident.mttr_seconds = (t2 - t1).total_seconds()

        elif new_state == IncidentState.CLOSED.value:
            incident.closed_at = now

        return incident

    def assign_playbook(self, incident_id: str) -> Optional[str]:
        """Return the auto-assigned playbook name for the incident."""
        incident = self.incidents.get(incident_id)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")
        return incident.assigned_playbook

    def add_note(self, incident_id: str, note: str) -> None:
        """Add an analyst note to the incident."""
        incident = self.incidents.get(incident_id)
        if incident:
            incident.notes.append(f"[{self._now()}] {note}")

    def get_metrics(self) -> Dict[str, Any]:
        """Return aggregate metrics: MTTR, MTTD, count by severity."""
        mttr_list = [i.mttr_seconds for i in self.incidents.values() if i.mttr_seconds]
        mttd_list = [i.mttd_seconds for i in self.incidents.values() if i.mttd_seconds]

        by_severity = {}
        by_state = {}
        for inc in self.incidents.values():
            by_severity[inc.severity] = by_severity.get(inc.severity, 0) + 1
            by_state[inc.state] = by_state.get(inc.state, 0) + 1

        return {
            "total_incidents": len(self.incidents),
            "avg_mttr_seconds": round(sum(mttr_list) / len(mttr_list), 2) if mttr_list else None,
            "avg_mttd_seconds": round(sum(mttd_list) / len(mttd_list), 2) if mttd_list else None,
            "min_mttr_seconds": round(min(mttr_list), 2) if mttr_list else None,
            "max_mttr_seconds": round(max(mttr_list), 2) if mttr_list else None,
            "incidents_by_severity": by_severity,
            "incidents_by_state": by_state,
        }

    def export_report(self, incident_id: str) -> Dict[str, Any]:
        """Export a full JSON report for an incident."""
        incident = self.incidents.get(incident_id)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")
        return asdict(incident)

    def list_incidents(self, state: Optional[str] = None, severity: Optional[str] = None) -> List[Dict]:
        """List incidents, optionally filtered by state or severity."""
        result = []
        for inc in self.incidents.values():
            if state and inc.state != state:
                continue
            if severity and inc.severity != severity:
                continue
            result.append({
                "id": inc.id,
                "title": inc.title,
                "severity": inc.severity,
                "state": inc.state,
                "created_at": inc.created_at,
                "assigned_playbook": inc.assigned_playbook,
                "mitre_techniques": inc.mitre_techniques,
            })
        return sorted(result, key=lambda x: x["created_at"], reverse=True)
