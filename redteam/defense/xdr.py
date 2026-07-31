"""
defense.xdr — Extended Detection and Response
==============================================

Bus de eventos pub/sub con buffer circular, correlator con reglas
multi-componente, mapeo MITRE automático, e IncidentStore con timeline.
"""
from __future__ import annotations

import collections
import dataclasses
import json
import logging
import re
import threading
import time
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ===================== Data types =====================


@dataclasses.dataclass
class XdrEvent:
    """Evento XDR normalizado."""
    source: str        # rasp | ndr | ztna | deception | soar | xdr
    category: str      # frida | beaconing | bola | canary | revoke | ...
    severity: str      # critical | high | medium | low | info
    mitre_id: str = ""
    summary: str = ""
    timestamp: float = dataclasses.field(default_factory=time.time)
    payload: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


# ===================== Event Bus =====================


class EventBus:
    """Bus pub/sub en memoria con buffer circular.

    Suscriptores se registran por topic. ``publish`` agrega el evento al
    buffer y notifica a los suscriptores. Tamaño máximo = 100k por
    defecto."""

    def __init__(self, *, buffer_size: int = 100_000):
        self.buffer_size = buffer_size
        self._buffer: Deque[XdrEvent] = collections.deque(maxlen=buffer_size)
        self._subscribers: Dict[str, List[Callable[[XdrEvent], None]]] = collections.defaultdict(list)
        self._lock = threading.Lock()
        self._all_subscribers: List[Callable[[XdrEvent], None]] = []

    def publish(self, topic: str, payload: Any) -> None:
        """Publica un payload arbitrario. Si es dict con campos
        source/category/severity lo promueve a XdrEvent, sino lo envuelve."""
        if isinstance(payload, XdrEvent):
            event = payload
        elif isinstance(payload, dict):
            event = XdrEvent(
                source=str(payload.get("source", "xdr")),
                category=str(payload.get("category", "generic")),
                severity=str(payload.get("severity", "info")),
                mitre_id=str(payload.get("mitre_id", "")),
                summary=str(payload.get("summary", "")),
                payload=payload,
            )
        else:
            event = XdrEvent(
                source="xdr",
                category="generic",
                severity="info",
                summary=str(payload),
                payload={"raw": payload},
            )
        event.payload["_topic"] = topic
        with self._lock:
            self._buffer.append(event)
            subs = list(self._subscribers.get(topic, [])) + list(self._all_subscribers)
        for sub in subs:
            try:
                sub(event)
            except Exception as e:  # pragma: no cover — defensivo
                logger.warning("subscriber %r falló: %s", sub, e)

    def subscribe(self, topic: str, callback: Callable[[XdrEvent], None]) -> None:
        with self._lock:
            self._subscribers[topic].append(callback)

    def subscribe_all(self, callback: Callable[[XdrEvent], None]) -> None:
        with self._lock:
            self._all_subscribers.append(callback)

    def events(self, n: int = 100) -> List[XdrEvent]:
        with self._lock:
            return list(self._buffer)[-n:]

    def by_source(self, source: str, n: int = 100) -> List[XdrEvent]:
        with self._lock:
            return [e for e in self._buffer if e.source == source][-n:]

    def size(self) -> int:
        with self._lock:
            return len(self._buffer)


# ===================== MITRE Mapper =====================


class MITREMapper:
    """Mapea (source, category) → technique_id y tactic. El catálogo se
    carga desde ``defense/mitre_map.yaml`` o se inicializa con un set
    por defecto."""

    DEFAULT_TACTIC_BY_TECHNIQUE = {
        "T1056.001": "Collection",
        "T1518": "Discovery",
        "T1071.004": "Command and Control",
        "T1071.001": "Command and Control",
        "T1048": "Exfiltration",
        "T1572": "Command and Control",
        "T1095": "Command and Control",
        "T1078": "Defense Evasion",
        "T1078.004": "Defense Evasion",
        "T1611": "Privilege Escalation",
        "T1623": "Persistence",
        "T1190": "Initial Access",
        "T1213": "Collection",
    }

    def __init__(self, technique_map: Optional[Dict[str, Dict[str, Any]]] = None):
        # technique_id → {name, tactic, severity}
        self._map: Dict[str, Dict[str, Any]] = {}
        if technique_map:
            for t in technique_map.get("techniques", []):
                self._map[t["id"]] = t
        # Rellenar con defaults
        for tid, tactic in self.DEFAULT_TACTIC_BY_TECHNIQUE.items():
            if tid not in self._map:
                self._map[tid] = {"id": tid, "name": tid, "tactic": tactic, "severity": "medium"}

    def tactic_for(self, technique_id: str) -> str:
        return self._map.get(technique_id, {}).get("tactic", "unknown")

    def severity_for(self, technique_id: str) -> str:
        return self._map.get(technique_id, {}).get("severity", "medium")

    def annotate(self, event: XdrEvent) -> XdrEvent:
        if event.mitre_id:
            event.payload["tactic"] = self.tactic_for(event.mitre_id)
        return event

    def techniques(self) -> List[Dict[str, Any]]:
        return list(self._map.values())

    def coverage(self) -> Dict[str, int]:
        out: Dict[str, int] = collections.Counter()
        for t in self._map.values():
            out[t.get("tactic", "unknown")] += 1
        return dict(out)


# ===================== Correlator =====================


class Correlator:
    """Reglas de correlación multi-componente. Las reglas tienen la
    forma ``(topic_predicate, …) → mitre_id``. Se evalúan cada vez que
    un evento llega al bus."""

    def __init__(self, bus: EventBus, mapper: MITREMapper,
                 correlation_window_seconds: int = 300):
        self.bus = bus
        self.mapper = mapper
        self.window = correlation_window_seconds
        self._lock = threading.Lock()
        self._recent: Deque[XdrEvent] = collections.deque(maxlen=10000)
        self._incidents: List[Dict[str, Any]] = []
        self._rules: List[Dict[str, Any]] = []
        self._install_default_rules()
        bus.subscribe_all(self._on_event)

    def add_rule(self, *, rule_id: str, name: str, predicates: List[str], mitre: str) -> None:
        self._rules.append({"id": rule_id, "name": name,
                            "predicates": predicates, "mitre": mitre})

    def _install_default_rules(self) -> None:
        self.add_rule(
            rule_id="R-COR-001",
            name="RASP_hooking + outbound_C2",
            predicates=[
                "source:rasp AND category:frida",
                "source:ndr AND category:beaconing",
            ],
            mitre="T1056.001",
        )
        self.add_rule(
            rule_id="R-COR-002",
            name="BOLA + decoy_hit",
            predicates=[
                "source:ztna AND category:bola_attempt",
                "source:deception AND category:hit",
            ],
            mitre="T1078",
        )
        self.add_rule(
            rule_id="R-COR-003",
            name="canary + admin_login",
            predicates=[
                "source:deception AND category:canary_access",
                "source:ztna AND category:admin_login",
            ],
            mitre="T1078.004",
        )

    def _on_event(self, event: XdrEvent) -> None:
        with self._lock:
            self._recent.append(event)
            self._prune()
        # Evaluar reglas
        for rule in self._rules:
            if self._rule_matches(rule):
                self._emit_incident(rule, event)

    def _prune(self) -> None:
        cutoff = time.time() - self.window
        while self._recent and self._recent[0].timestamp < cutoff:
            self._recent.popleft()

    def _rule_matches(self, rule: Dict[str, Any]) -> bool:
        with self._lock:
            recent = list(self._recent)
        for pred in rule["predicates"]:
            if not self._any_match(recent, pred):
                return False
        return True

    @staticmethod
    def _any_match(events: List[XdrEvent], predicate: str) -> bool:
        m = re.match(r"source:(\S+)\s+AND\s+category:(\S+)", predicate.strip())
        if not m:
            return False
        source, category = m.group(1), m.group(2)
        return any(e.source == source and e.category == category for e in events)

    def _emit_incident(self, rule: Dict[str, Any], trigger: XdrEvent) -> None:
        tactic = self.mapper.tactic_for(rule["mitre"])
        with self._lock:
            # Dedupe: si ya hay un incidente abierto con este rule_id en los
            # últimos 60s, no creamos otro.
            cutoff = time.time() - 60
            if any(inc["rule_id"] == rule["id"] and inc["timestamp"] > cutoff
                   for inc in self._incidents):
                return
            timeline = [
                e.to_dict() for e in list(self._recent)[-20:]
            ]
            incident = {
                "id": f"inc-{int(time.time() * 1000)}",
                "rule_id": rule["id"],
                "name": rule["name"],
                "mitre": rule["mitre"],
                "tactic": tactic,
                "severity": self.mapper.severity_for(rule["mitre"]),
                "timestamp": time.time(),
                "trigger": trigger.to_dict(),
                "timeline": timeline,
            }
            self._incidents.append(incident)
        # Re-emit al bus
        self.bus.publish("xdr.incident", {
            "source": "xdr",
            "category": "incident",
            "severity": incident["severity"],
            "mitre_id": rule["mitre"],
            "summary": f"correlated: {rule['name']}",
            "incident_id": incident["id"],
        })

    def incidents(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._incidents)


# ===================== Incident Store =====================


class IncidentStore:
    """Almacén de incidentes con timeline de eventos."""

    def __init__(self):
        self._incidents: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def append(self, *, incident_id: Optional[str] = None,
               event: Optional[XdrEvent] = None,
               severity: str = "info",
               mitre: str = "",
               title: str = "",
               extra: Optional[Dict[str, Any]] = None) -> str:
        with self._lock:
            if incident_id and incident_id in self._incidents:
                inc = self._incidents[incident_id]
            else:
                incident_id = incident_id or f"inc-{int(time.time() * 1000)}"
                inc = {
                    "id": incident_id,
                    "title": title,
                    "severity": severity,
                    "mitre": mitre,
                    "created_at": time.time(),
                    "updated_at": time.time(),
                    "timeline": [],
                    "extra": extra or {},
                }
                self._incidents[incident_id] = inc
            inc["updated_at"] = time.time()
            if event is not None:
                inc["timeline"].append(event.to_dict())
            if not inc.get("title") and title:
                inc["title"] = title
            return incident_id

    def get(self, incident_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return json.loads(json.dumps(self._incidents.get(incident_id)))

    def list(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [json.loads(json.dumps(inc)) for inc in self._incidents.values()]

    def count(self) -> int:
        with self._lock:
            return len(self._incidents)
