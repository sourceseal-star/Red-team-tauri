#!/usr/bin/env python3
"""
XDR Correlator — Extended Detection and Response
=================================================
Ingesta y correlación de eventos de todos los sensores:
  - RASP (cliente)
  - NDR (red)
  - Deception Mesh (engaño)
  - ZTNA Gateway (API)
  - Honeypot / C2 Sinkhole

Mapea incidentes contra la matriz MITRE ATT&CK v15.
Genera eventos correlacionados que el SOAR consume para ejecutar playbooks.
"""
import json
import time
import hashlib
import datetime
import threading
from collections import defaultdict, deque
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict


# ─── Matriz MITRE ATT&CK v15 (subset relevante) ─────────────────────────────
MITRE_TECHNIQUES = {
    "T1046": {"name": "Network Service Discovery",         "tactic": "Reconnaissance"},
    "T1595": {"name": "Active Scanning",                    "tactic": "Reconnaissance"},
    "T1071": {"name": "Application Layer Protocol",         "tactic": "Command and Control"},
    "T1573": {"name": "Encrypted Channel",                  "tactic": "Command and Control"},
    "T1041": {"name": "Exfiltration Over C2 Channel",       "tactic": "Exfiltration"},
    "T1567": {"name": "Exfiltration Over Web Service",      "tactic": "Exfiltration"},
    "T1059": {"name": "Command and Scripting Interpreter",  "tactic": "Execution"},
    "T1622": {"name": "Debugger Evasion",                   "tactic": "Defense Evasion"},
    "T1027": {"name": "Obfuscated Files or Information",    "tactic": "Defense Evasion"},
    "T1556": {"name": "Modify Authentication Process",      "tactic": "Credential Access"},
    "T1110": {"name": "Brute Force",                        "tactic": "Credential Access"},
    "T1550": {"name": "Use Alternate Auth Material",        "tactic": "Lateral Movement"},
    "T1486": {"name": "Data Encrypted for Impact",          "tactic": "Impact"},
    "T1499": {"name": "Endpoint Denial of Service",         "tactic": "Impact"},
    "T1053": {"name": "Scheduled Task/Job",                 "tactic": "Persistence"},
    "T1547": {"name": "Boot or Logon Autostart Execution",  "tactic": "Persistence"},
    "T1055": {"name": "Process Injection",                  "tactic": "Defense Evasion"},
    "T1005": {"name": "Data from Local System",             "tactic": "Collection"},
    "T1074": {"name": "Data Staged",                        "tactic": "Collection"},
    "T1190": {"name": "Exploit Public-Facing Application",  "tactic": "Initial Access"},
    "T1133": {"name": "External Remote Services",           "tactic": "Initial Access"},
    "T1566": {"name": "Phishing",                             "tactic": "Initial Access"},
    "T1204": {"name": "User Execution",                       "tactic": "Execution"},
    "T1049": {"name": "System Information Discovery",          "tactic": "Discovery"},
    "T1087": {"name": "Account Discovery",                     "tactic": "Discovery"},
}


@dataclass
class XDREvent:
    id: str
    source: str
    severity: str
    title: str
    description: str
    timestamp: str
    mitre_technique: str = ""
    src_ip: str = ""
    dst_ip: str = ""
    user_hash: str = ""
    endpoint: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Incident:
    id: str
    title: str
    severity: str
    status: str
    events: List[Dict] = field(default_factory=list)
    mitre_techniques: List[str] = field(default_factory=list)
    mitre_tactics: List[str] = field(default_factory=list)
    src_ips: List[str] = field(default_factory=list)
    affected_assets: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    confidence: float = 0.0


class XDRCorrelator:
    """Motor de correlación de eventos XDR con mapeo MITRE ATT&CK."""

    CORRELATION_RULES = [
        {
            "name": "C2 Beaconing + Exfiltracion",
            "description": "Beaconing detectado por NDR seguido de exfiltracion",
            "sources": {"ndr", "deception"},
            "techniques": {"T1071", "T1573", "T1041"},
            "min_events": 2,
            "severity": "critical",
            "window_seconds": 300,
            "actions": ["block_ip", "isolate_endpoint", "revoke_tokens"],
        },
        {
            "name": "Reconocimiento + Explotacion API",
            "description": "Escaneo seguido de exploit en API publica",
            "sources": {"ztna", "ndr", "honeypot"},
            "techniques": {"T1046", "T1595", "T1190"},
            "min_events": 2,
            "severity": "high",
            "window_seconds": 180,
            "actions": ["block_ip", "rate_limit", "alert_soc"],
        },
        {
            "name": "Evasion de Debugger + Inyeccion",
            "description": "RASP detecta Frida/hooking seguido de inyeccion",
            "sources": {"rasp"},
            "techniques": {"T1622", "T1055", "T1027"},
            "min_events": 2,
            "severity": "critical",
            "window_seconds": 60,
            "actions": ["kill_app_session", "revoke_tokens", "quarantine_device"],
        },
        {
            "name": "Credenciales Comprometidas",
            "description": "Brute force seguido de acceso exitoso",
            "sources": {"ztna", "rasp", "deception"},
            "techniques": {"T1110", "T1556", "T1550"},
            "min_events": 2,
            "severity": "high",
            "window_seconds": 600,
            "actions": ["revoke_tokens", "force_reauth", "block_ip"],
        },
        {
            "name": "Movimiento Lateral via Deception",
            "description": "Canary token consumido indica movimiento lateral",
            "sources": {"deception", "honeypot"},
            "techniques": {"T1550", "T1074", "T1005"},
            "min_events": 1,
            "severity": "critical",
            "window_seconds": 30,
            "actions": ["isolate_endpoint", "block_ip", "alert_soc", "revoke_tokens"],
        },
        {
            "name": "DoS / Rate Limit Saturado",
            "description": "Multiples requests excediendo limites ZTNA",
            "sources": {"ztna"},
            "techniques": {"T1499"},
            "min_events": 5,
            "severity": "high",
            "window_seconds": 30,
            "actions": ["rate_limit", "block_ip", "alert_soc"],
        },
    ]

    def __init__(self, max_events: int = 10000):
        self.events: deque = deque(maxlen=max_events)
        self.incidents: List[Incident] = []
        self._lock = threading.Lock()
        self._by_ip: Dict[str, List[XDREvent]] = defaultdict(list)

    def ingest(self, event: XDREvent) -> None:
        with self._lock:
            self.events.append(event)
            if event.src_ip:
                self._by_ip[event.src_ip].append(event)

    def ingest_raw(self, source: str, severity: str, title: str,
                   description: str, **kwargs) -> str:
        eid = hashlib.sha256(f"{title}{time.time()}{source}".encode()).hexdigest()[:16]
        ev = XDREvent(
            id=eid, source=source, severity=severity, title=title,
            description=description,
            timestamp=datetime.datetime.utcnow().isoformat() + "Z",
            mitre_technique=kwargs.get("mitre", ""),
            src_ip=kwargs.get("src_ip", ""),
            dst_ip=kwargs.get("dst_ip", ""),
            user_hash=kwargs.get("user_hash", ""),
            endpoint=kwargs.get("endpoint", ""),
            raw=kwargs.get("raw", {}),
        )
        self.ingest(ev)
        return eid

    def correlate(self) -> List[Incident]:
        now = time.time()
        new_incidents = []

        for rule in self.CORRELATION_RULES:
            window = rule["window_seconds"]
            cutoff = now - window
            recent = [
                e for e in self.events
                if self._ts(e.timestamp) >= cutoff
                and e.source in rule["sources"]
            ]

            if rule.get("techniques"):
                tech_events = [
                    e for e in recent
                    if e.mitre_technique and e.mitre_technique in rule["techniques"]
                ]
                if len(tech_events) >= rule["min_events"]:
                    new_incidents.append(self._make_incident(rule, tech_events))
                    continue

            if len(recent) >= rule["min_events"]:
                new_incidents.append(self._make_incident(rule, recent))

        for inc in new_incidents:
            dup = any(
                i.title == inc.title and
                set(i.src_ips) & set(inc.src_ips) and
                self._ts(i.updated_at) > now - 3600
                for i in self.incidents
            )
            if not dup:
                self.incidents.append(inc)

        return [i for i in self.incidents if i.status == "open"]

    def _make_incident(self, rule, events):
        techs = sorted(set(e.mitre_technique for e in events if e.mitre_technique))
        tactics = sorted(set(MITRE_TECHNIQUES.get(t, {}).get("tactic", "") for t in techs))
        ips = sorted(set(e.src_ip for e in events if e.src_ip))
        assets = sorted(set(e.endpoint for e in events if e.endpoint))
        iid = hashlib.sha256(f"{rule['name']}{''.join(ips)}{time.time()}".encode()).hexdigest()[:16]
        return Incident(
            id=iid, title=rule["name"], severity=rule["severity"], status="open",
            events=[asdict(e) for e in events], mitre_techniques=techs,
            mitre_tactics=tactics, src_ips=ips, affected_assets=assets,
            recommended_actions=rule["actions"],
            created_at=datetime.datetime.utcnow().isoformat() + "Z",
            updated_at=datetime.datetime.utcnow().isoformat() + "Z",
            confidence=min(1.0, len(events) / max(rule["min_events"] * 2, 1)),
        )

    @staticmethod
    def _ts(ts: str) -> float:
        try:
            return datetime.datetime.fromisoformat(ts.replace("Z", "")).timestamp()
        except Exception:
            return 0.0

    def export_incidents(self) -> List[Dict]:
        return [asdict(i) for i in self.incidents]

    def get_attack_surface_map(self) -> Dict:
        by_tech = defaultdict(lambda: {"count": 0, "tactic": "", "name": ""})
        for e in self.events:
            if e.mitre_technique:
                t = e.mitre_technique
                by_tech[t]["count"] += 1
                by_tech[t]["tactic"] = MITRE_TECHNIQUES.get(t, {}).get("tactic", "Unknown")
                by_tech[t]["name"] = MITRE_TECHNIQUES.get(t, {}).get("name", "Unknown")
        by_src = defaultdict(int)
        for e in self.events:
            by_src[e.source] += 1
        by_sev = defaultdict(int)
        for e in self.events:
            by_sev[e.severity] += 1
        return {
            "total_events": len(self.events),
            "by_technique": dict(by_tech),
            "by_source": dict(by_src),
            "by_severity": dict(by_sev),
            "open_incidents": sum(1 for i in self.incidents if i.status == "open"),
            "mitre_tactics_covered": sorted(set(v["tactic"] for v in by_tech.values() if v["tactic"])),
        }


# ─── XDR __init__ ────────────────────────────────────────────────────────────
