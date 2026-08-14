"""
defense.soar — Security Orchestration, Automation, Response
============================================================

Carga playbooks YAML y los ejecuta como una secuencia de acciones. Cada
acción retorna ``ActionResult(success, latency_ms, side_effects)``. La
latencia total del playbook se compara contra el SLA configurado
(default 500ms).

Los playbooks pueden llamar a callables registrados en el ``ActionRegistry``
(acciones internas) o a sistemas externos vía HTTP (mock).
"""
from __future__ import annotations

import dataclasses
import json
import logging
import os
import pathlib
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from defense._yaml import load as _yaml_load

logger = logging.getLogger(__name__)


# ===================== Data types =====================


@dataclasses.dataclass
class ActionResult:
    action_id: str
    success: bool
    latency_ms: float
    side_effects: List[str] = dataclasses.field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class PlaybookRun:
    run_id: str
    playbook_id: str
    started_at: float
    finished_at: float
    total_latency_ms: float
    actions: List[ActionResult]
    sla_breach: bool
    inputs: Dict[str, Any]
    extra: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


# ===================== Action Registry =====================


class ActionRegistry:
    """Registro de acciones invocables. Las acciones reciben
    ``(params: dict, context: dict)`` y retornan un dict con
    ``{'side_effects': [...]}``."""

    def __init__(self):
        self._actions: Dict[str, Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]] = {}
        self._lock = threading.Lock()

    def register(self, name: str,
                 fn: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]) -> None:
        with self._lock:
            self._actions[name] = fn

    def has(self, name: str) -> bool:
        with self._lock:
            return name in self._actions

    def call(self, name: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            fn = self._actions.get(name)
        if fn is None:
            return {"side_effects": [], "error": f"action {name} not registered"}
        return fn(params, context)

    def names(self) -> List[str]:
        with self._lock:
            return list(self._actions.keys())


# ===================== Playbook Engine =====================


class PlaybookEngine:
    """Ejecuta playbooks YAML con un registry de acciones."""

    def __init__(self, registry: ActionRegistry, *, max_latency_ms: int = 500,
                 playbooks_dir: Optional[pathlib.Path] = None,
                 default_actions: Optional[Dict[str, Any]] = None):
        self.registry = registry
        self.max_latency_ms = max_latency_ms
        self.playbooks_dir = pathlib.Path(playbooks_dir) if playbooks_dir else None
        self._playbooks: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._runs: List[PlaybookRun] = []
        self._default_actions = default_actions or {}
        # Instalar playbooks embebidos por defecto (no dependemos de
        # playbooks_dir si está vacío).
        self._install_embedded()

    # ---------- Playbook loading ----------

    def _install_embedded(self) -> None:
        embedded = self._default_actions or {}
        for pb_id, pb in embedded.items():
            self._playbooks[pb_id] = pb

    def load_directory(self, directory: pathlib.Path) -> int:
        """Carga todos los ``*.yaml`` de un directorio. Retorna cuántos
        playbooks se cargaron."""
        if not directory.exists():
            return 0
        loaded = 0
        for path in directory.glob("*.yaml"):
            try:
                pb = _yaml_load(open(path))
                self._playbooks[pb["id"]] = pb
                loaded += 1
            except Exception as e:
                logger.warning("no se pudo cargar playbook %s: %s", path, e)
        return loaded

    def register(self, playbook: Dict[str, Any]) -> None:
        self._playbooks[playbook["id"]] = playbook

    def get(self, playbook_id: str) -> Optional[Dict[str, Any]]:
        return self._playbooks.get(playbook_id)

    def list(self) -> List[str]:
        return list(self._playbooks.keys())

    # ---------- Execution ----------

    def run(self, playbook_id: str, inputs: Optional[Dict[str, Any]] = None) -> PlaybookRun:
        inputs = inputs or {}
        pb = self.get(playbook_id)
        run_id = f"run-{uuid.uuid4()}"
        if pb is None:
            run = PlaybookRun(
                run_id=run_id,
                playbook_id=playbook_id,
                started_at=time.time(),
                finished_at=time.time(),
                total_latency_ms=0.0,
                actions=[ActionResult(
                    action_id="__load__", success=False, latency_ms=0.0,
                    error=f"playbook {playbook_id} not found")],
                sla_breach=True,
                inputs=inputs,
            )
            with self._lock:
                self._runs.append(run)
            return run
        start = time.time()
        results: List[ActionResult] = []
        for action in pb.get("actions", []):
            t0 = time.time()
            params = {"inputs": inputs, "target": action.get("target"),
                      "id": action.get("id"), "type": action.get("type")}
            context = {"playbook_id": playbook_id, "run_id": run_id,
                       "registry": self.registry}
            outcome = self.registry.call(action.get("target", ""), params, context)
            t1 = time.time()
            err = outcome.get("error")
            results.append(ActionResult(
                action_id=action.get("id", action.get("target", "?")),
                success=err is None,
                latency_ms=round((t1 - t0) * 1000, 3),
                side_effects=list(outcome.get("side_effects", [])),
                error=err,
            ))
            # Si timeout_ms definido y excedido, abortamos
            tmo = action.get("timeout_ms", 0)
            if tmo and (t1 - t0) * 1000 > tmo:
                results.append(ActionResult(
                    action_id=action.get("id", action.get("target", "?")),
                    success=False,
                    latency_ms=round((t1 - t0) * 1000, 3),
                    error=f"timeout exceeded ({tmo}ms)",
                ))
                break
        end = time.time()
        total = round((end - start) * 1000, 3)
        run = PlaybookRun(
            run_id=run_id,
            playbook_id=playbook_id,
            started_at=start,
            finished_at=end,
            total_latency_ms=total,
            actions=results,
            sla_breach=total > self.max_latency_ms,
            inputs=inputs,
        )
        with self._lock:
            self._runs.append(run)
        return run

    def runs(self) -> List[PlaybookRun]:
        with self._lock:
            return list(self._runs)

    def last_run(self, playbook_id: str) -> Optional[PlaybookRun]:
        with self._lock:
            for r in reversed(self._runs):
                if r.playbook_id == playbook_id:
                    return r
        return None


# ===================== Embedded playbooks (defaults) =====================


def default_playbooks() -> Dict[str, Dict[str, Any]]:
    """Cuatro playbooks requeridos. Cargados si no se encuentran en disco."""
    return {
        "pb_revoke_jwt": {
            "id": "pb_revoke_jwt",
            "name": "Revoke compromised JWTs",
            "description": "Revoca todos los tokens emitidos para un user_id o subject fingerprint.",
            "trigger_category": "credential_compromise",
            "severity_min": "high",
            "sources": ["deception.canary", "ztna.bola_attempt", "xdr.correlation"],
            "inputs": [
                {"name": "user_id", "type": "string", "required": True},
                {"name": "cert_fingerprint", "type": "string", "required": False},
                {"name": "reason", "type": "string", "required": True},
            ],
            "actions": [
                {"id": "add_to_jwt_revoke_list", "type": "internal",
                 "target": "ZTNA.JWTValidator.revocation_set", "timeout_ms": 50},
                {"id": "force_session_termination", "type": "internal",
                 "target": "RASPEnforcer.revoke_session", "timeout_ms": 100},
                {"id": "create_thehive_case", "type": "external",
                 "target": "thehive.case_creator", "timeout_ms": 200},
                {"id": "emit_incident", "type": "internal",
                 "target": "XDR.IncidentStore.append", "timeout_ms": 50},
            ],
            "sla_ms": 500,
            "mitre": ["T1078", "T1078.004", "T1190"],
        },
        "pb_isolate_device": {
            "id": "pb_isolate_device",
            "name": "Isolate compromised device",
            "description": "Aísla un device_id del API Gateway.",
            "trigger_category": "device_compromise",
            "severity_min": "high",
            "sources": ["rasp.hooking", "ndr.beaconing", "xdr.correlation"],
            "inputs": [
                {"name": "device_id", "type": "string", "required": True},
                {"name": "user_id", "type": "string", "required": False},
                {"name": "reason", "type": "string", "required": True},
            ],
            "actions": [
                {"id": "quarantine_device", "type": "internal",
                 "target": "RASPEnforcer.quarantine", "timeout_ms": 100},
                {"id": "block_in_api_gateway", "type": "internal",
                 "target": "ZTNA.PolicyEngine.deny_device", "timeout_ms": 50},
                {"id": "revoke_user_sessions", "type": "internal",
                 "target": "RASPEnforcer.revoke_session", "timeout_ms": 100},
                {"id": "emit_ioc", "type": "internal",
                 "target": "Deception.STIXExporter.export", "timeout_ms": 100},
                {"id": "notify_thehive", "type": "external",
                 "target": "thehive.case_creator", "timeout_ms": 200},
            ],
            "sla_ms": 500,
            "mitre": ["T1056.001", "T1071.001", "T1611"],
        },
        "pb_block_ioc": {
            "id": "pb_block_ioc",
            "name": "Block IoC perimeter-wide",
            "description": "Inserta IoC en lista de bloqueo perimetral.",
            "trigger_category": "ioc_discovered",
            "severity_min": "medium",
            "sources": ["ndr.beaconing", "ndr.dns_tunneling", "ndr.icmp_tunnel"],
            "inputs": [
                {"name": "ioc_type", "type": "enum", "required": True},
                {"name": "ioc_value", "type": "string", "required": True},
                {"name": "source", "type": "string", "required": True},
            ],
            "actions": [
                {"id": "push_to_blocklist", "type": "internal",
                 "target": "NDR.blocklist_add", "timeout_ms": 50},
                {"id": "export_stix", "type": "internal",
                 "target": "Deception.STIXExporter.export", "timeout_ms": 100},
                {"id": "notify_thehive", "type": "external",
                 "target": "thehive.case_creator", "timeout_ms": 200},
                {"id": "emit_incident", "type": "internal",
                 "target": "XDR.IncidentStore.append", "timeout_ms": 50},
            ],
            "sla_ms": 500,
            "mitre": ["T1071.004", "T1048", "T1572", "T1095"],
        },
        "pb_quarantine_apk": {
            "id": "pb_quarantine_apk",
            "name": "Quarantine suspicious binary",
            "description": "Marca un binario como malicioso y bloquea device_id.",
            "trigger_category": "binary_malicious",
            "severity_min": "high",
            "sources": ["rasp.memory_tamper", "attestation.integrity_failure"],
            "inputs": [
                {"name": "sha256", "type": "string", "required": True},
                {"name": "device_id", "type": "string", "required": True},
                {"name": "reason", "type": "string", "required": True},
            ],
            "actions": [
                {"id": "flag_binary", "type": "internal",
                 "target": "RASPProbe.hash_allowlist_remove", "timeout_ms": 50},
                {"id": "quarantine_device", "type": "internal",
                 "target": "RASPEnforcer.quarantine", "timeout_ms": 100},
                {"id": "export_stix", "type": "internal",
                 "target": "Deception.STIXExporter.export", "timeout_ms": 100},
                {"id": "notify_thehive", "type": "external",
                 "target": "thehive.case_creator", "timeout_ms": 200},
            ],
            "sla_ms": 500,
            "mitre": ["T1518", "T1611", "T1623"],
        },
    }
