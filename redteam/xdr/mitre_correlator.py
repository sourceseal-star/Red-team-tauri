#!/usr/bin/env python3
"""
XDR MITRE Correlator — Enriquece eventos con MITRE ATT&CK mapping.
Extiende XDRCorrelator con análisis avanzado de kill chain.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Set, Optional, Tuple
from collections import defaultdict
from xdr.correlator import XDRCorrelator, XDREvent, Incident, MITRE_TECHNIQUES


MITRE_MATRIX = {
    # tactic -> list of (technique_id, name)
    "TA0001-Initial-Access": [("T1190", "Exploit Public-Facing Application"), ("T1078", "Valid Accounts"), ("T1133", "External Remote Services")],
    "TA0002-Execution": [("T1059", "Command and Scripting Interpreter"), ("T1053", "Scheduled Task/Job"), ("T1106", "Native API")],
    "TA0003-Persistence": [("T1098", "Account Manipulation"), ("T1136", "Create Account"), ("T1543", "Create or Modify System Process")],
    "TA0005-Defense-Evasion": [("T1070", "Indicator Removal"), ("T1027", "Obfuscated Files or Information"), ("T1036", "Masquerading")],
    "TA0006-Credential-Access": [("T1110", "Brute Force"), ("T1056", "Input Capture"), ("T1552", "Unsecured Credentials")],
    "TA0007-Discovery": [("T1046", "Network Service Discovery"), ("T1087", "Account Discovery"), ("T1049", "System Network Connections")],
    "TA0008-Lateral-Movement": [("T1021", "Remote Services"), ("T1072", "Software Deployment Tools"), ("T1570", "Lateral Tool Transfer")],
    "TA0009-Collection": [("T1560", "Archive Collected Data"), ("T1005", "Data from Local System"), ("T1113", "Screen Capture")],
    "TA0011-Command-and-Control": [("T1071", "Application Layer Protocol"), ("T1573", "Encrypted Channel"), ("T1090", "Proxy")],
    "TA0010-Exfiltration": [("T1041", "Exfiltration Over C2 Channel"), ("T1048", "Exfiltration Over Alternative Protocol"), ("T1567", "Exfiltration Over Web Service")],
    "TA0040-Impact": [("T1486", "Data Encrypted for Impact"), ("T1499", "Endpoint Denial of Service"), ("T1485", "Data Destruction")],
}

# Reverse map: technique_id -> (tactic, name)
TECHNIQUE_TO_TACTIC: Dict[str, Tuple[str, str]] = {}
for tactic, techs in MITRE_MATRIX.items():
    for tech_id, tech_name in techs:
        TECHNIQUE_TO_TACTIC[tech_id] = (tactic, tech_name)


@dataclass
class AttackPathNode:
    technique: str
    tactic: str
    technique_name: str
    timestamp: str
    source: str
    description: str


class EnhancedMITREMapper:
    """Mapea eventos a MITRE ATT&CK y construye kill chain visualization."""

    KEYWORD_MAP = {
        "frida": "T1059", "inject": "T1055", "hook": "T1055",
        "bypass": "T1070", "root": "T1068", "debug": "T1055",
        "beacon": "T1071", "c2": "T1071", "exfil": "T1041",
        "brute": "T1110", "credential": "T1552", "scan": "T1046",
        "lateral": "T1021", "encrypt": "T1486", "deny": "T1499",
        "bola": "T1190", "access": "T1078", "decoy": "T1057",
        "token": "T1552", "firewall": "T1562", "proxy": "T1090",
    }

    def enrich_event(self, event: Dict) -> Dict:
        """Toma un event dict y agrega mitre_technique, mitre_tactic, mitre_subtechnique."""
        enriched = dict(event)
        text = f"{event.get('title', '')} {event.get('description', '')} {event.get('source', '')}".lower()

        techniques: Set[str] = set()
        for keyword, tech_id in self.KEYWORD_MAP.items():
            if keyword in text:
                techniques.add(tech_id)

        # Preserve existing techniques
        if event.get("mitre_techniques"):
            for t in event["mitre_techniques"]:
                if isinstance(t, str):
                    techniques.add(t)

        enriched["mitre_techniques"] = sorted(techniques)
        tactics = set()
        for t in techniques:
            if t in TECHNIQUE_TO_TACTIC:
                tactics.add(TECHNIQUE_TO_TACTIC[t][0])
        enriched["mitre_tactics"] = sorted(tactics)
        return enriched

    def get_attack_path(self, incidents: List[Incident]) -> List[AttackPathNode]:
        """Construye un timeline (kill chain) desde incidentes."""
        nodes: List[AttackPathNode] = []
        for inc in incidents:
            for event in inc.events:
                for tech in event.get("mitre_techniques", []):
                    if tech in TECHNIQUE_TO_TACTIC:
                        tactic, name = TECHNIQUE_TO_TACTIC[tech]
                        nodes.append(AttackPathNode(
                            technique=tech, tactic=tactic,
                            technique_name=name,
                            timestamp=event.get("timestamp", inc.created_at),
                            source=event.get("source", "unknown"),
                            description=event.get("title", ""),
                        ))
        nodes.sort(key=lambda n: n.timestamp)
        return nodes

    def score_incident(self, incident: Incident) -> float:
        """Score = base severity + mitre_count * weight."""
        base = {"critical": 10, "high": 7, "medium": 5, "low": 2, "info": 0}
        base_score = base.get(incident.severity, 5)
        tech_count = len(set(
            t for e in incident.events for t in e.get("mitre_techniques", [])
        ))
        return base_score + tech_count * 0.5

    def get_mitre_heatmap(self, events: List[XDREvent]) -> Dict:
        """Genera datos para heatmap de ATT&CK matrix."""
        by_tech = defaultdict(int)
        for e in events:
            for t in ([e.mitre_technique] if e.mitre_technique else []):
                by_tech[t] += 1
        heatmap = {}
        for tactic, techs in MITRE_MATRIX.items():
            heatmap[tactic] = [
                {"technique": tid, "name": name, "count": by_tech.get(tid, 0)}
                for tid, name in techs
            ]
        return {
            "matrix": heatmap,
            "total_techniques_detected": len(by_tech),
            "techniques_with_hits": dict(by_tech),
        }


class EnhancedXDRCorrelator(XDRCorrelator):
    """XDRCorrelator con MITRE enrichment automático."""

    def __init__(self):
        super().__init__()
        self.mapper = EnhancedMITREMapper()

    def ingest_raw(self, **kwargs):
        """Override para enriquecer con MITRE antes de ingest."""
        enriched = self.mapper.enrich_event(kwargs)
        if "mitre_techniques" in enriched and enriched["mitre_techniques"]:
            kwargs["mitre_techniques"] = enriched["mitre_techniques"]
        if "mitre_tactics" in enriched and enriched["mitre_tactics"]:
            kwargs["mitre_tactics"] = enriched["mitre_tactics"]
        super().ingest_raw(**kwargs)

    def get_enriched_incidents(self) -> List[Dict]:
        """Retorna incidentes enriquecidos con scores MITRE."""
        incidents = self.correlate()
        result = []
        for inc in incidents:
            result.append({
                "id": inc.id, "title": inc.title,
                "severity": inc.severity,
                "mitre_score": self.mapper.score_incident(inc),
                "mitre_techniques": list(set(
                    t for e in inc.events for t in e.get("mitre_techniques", [])
                )),
                "attack_path": [
                    {"technique": n.technique, "tactic": n.tactic, "name": n.technique_name}
                    for n in self.mapper.get_attack_path([inc])
                ],
            })
        return result
