"""
defense.rasp — Runtime Application Self-Protection
==================================================

Probes que detectan intentos de hooking/instrumentación sobre la app móvil
(Frida, Xposed, emulador, debugger, memory tampering) y un enforcer que
publica acciones al bus interno del DefenseMesh.

Modelo de detección:
    * Hooks sobre datos observables en el dispositivo (puertos, /proc,
      strings en memoria, system properties).
    * Cada detector retorna un ``ThreatSignal`` con severidad, categoría,
      evidencia y mapeo MITRE ATT&CK.
    * El enforcer NO contacta APIs externas: publica a un callable de bus
      que el ``DefenseMesh`` conecta en ``__init__``.
"""
from __future__ import annotations

import dataclasses
import hashlib
import logging
import os
import pathlib
import platform
import re
import socket
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ===================== Data types =====================


@dataclasses.dataclass
class ThreatSignal:
    """Señal de amenaza detectada por RASP o cualquier otro componente."""
    severity: str          # critical | high | medium | low | info
    category: str          # frida | xposed | emulator | debugger | memory_tamper | binary
    evidence: str          # descripción humana + datos
    mitre_id: str          # técnica MITRE
    source: str = "rasp"   # origen de la señal
    timestamp: float = dataclasses.field(default_factory=time.time)
    extra: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


# ===================== Probe =====================


class RASPProbe:
    """Probes de Runtime Application Self-Protection.

    Todos los métodos son idempotentes y thread-safe. Las detecciones son
    *best-effort*: en un dispositivo real, Frida/Xposed evolucionan; en este
    entorno de tests se inyectan indicadores via setters para poder
    ejercitar todas las rutas.
    """

    DEFAULT_FRIDA_PORTS = (27042, 27043)
    DEFAULT_FRIDA_LIBS = ("frida-agent", "frida-gadget", "libfrida")
    DEFAULT_XPOSED_INDICATORS = (
        "de.robv.android.xposed",
        "XposedBridge",
        "LSPosed",
    )
    DEFAULT_EMULATOR_INDICATORS = (
        "ro.product.model=sdk",
        "ro.product.model=Emulator",
        "ro.product.model=google_sdk",
        "ro.hardware=goldfish",
        "ro.hardware=qemu",
        "ro.boot.qemu=1",
    )

    def __init__(
        self,
        *,
        frida_ports: Tuple[int, ...] = DEFAULT_FRIDA_PORTS,
        frida_libs: Tuple[str, ...] = DEFAULT_FRIDA_LIBS,
        xposed_indicators: Tuple[str, ...] = DEFAULT_XPOSED_INDICATORS,
        emulator_indicators: Tuple[str, ...] = DEFAULT_EMULATOR_INDICATORS,
        binary_allowlist: Optional[List[str]] = None,
        system_properties: Optional[Dict[str, str]] = None,
        loaded_libs: Optional[List[str]] = None,
        proc_status: Optional[Dict[str, str]] = None,
        binary_path: Optional[pathlib.Path] = None,
    ):
        self.frida_ports = tuple(frida_ports)
        self.frida_libs = tuple(frida_libs)
        self.xposed_indicators = tuple(xposed_indicators)
        self.emulator_indicators = tuple(emulator_indicators)
        self.binary_allowlist = set(binary_allowlist or [])
        self._system_properties = dict(system_properties or {})
        self._loaded_libs = list(loaded_libs or [])
        self._proc_status = dict(proc_status or {})
        self.binary_path = pathlib.Path(binary_path) if binary_path else None
        self._lock = threading.Lock()
        # Cache de puertos frida ya probados (negativo en este proceso)
        self._port_open_cache: Dict[int, bool] = {}

    # ---------- Setters (para tests) ----------

    def inject_system_property(self, key: str, value: str) -> None:
        with self._lock:
            self._system_properties[key] = value

    def inject_loaded_lib(self, lib: str) -> None:
        with self._lock:
            if lib not in self._loaded_libs:
                self._loaded_libs.append(lib)

    def inject_proc_status(self, tracer_pid: str) -> None:
        with self._lock:
            self._proc_status["TracerPid"] = tracer_pid

    def set_binary_path(self, path: pathlib.Path) -> None:
        self.binary_path = pathlib.Path(path)

    # ---------- Detectors ----------

    def detect_frida(self) -> Optional[ThreatSignal]:
        """Detecta el daemon de Frida (puertos 27042/27043 + libs cargadas)."""
        evidence_parts: List[str] = []

        # 1) Puertos abiertos
        for port in self.frida_ports:
            if self._is_port_open(port):
                evidence_parts.append(f"frida port {port} reachable")
        # 2) Librerías en memoria
        for lib in self._loaded_libs:
            for indicator in self.frida_libs:
                if indicator in lib:
                    evidence_parts.append(f"loaded lib: {lib}")
        # 3) Mapeos /proc/maps con frida
        if self._proc_status.get("frida_in_maps"):
            evidence_parts.append("frida strings in /proc/self/maps")

        if not evidence_parts:
            return None
        return ThreatSignal(
            severity="critical",
            category="frida",
            evidence="; ".join(evidence_parts),
            mitre_id="T1056.001",
            extra={"ports": list(self.frida_ports)},
        )

    def detect_xposed(self) -> Optional[ThreatSignal]:
        """Detecta el framework Xposed / LSPosed."""
        evidence_parts: List[str] = []
        # 1) Clases cargadas
        for indicator in self.xposed_indicators:
            for lib in self._loaded_libs:
                if indicator in lib:
                    evidence_parts.append(f"class indicator {indicator} in {lib}")
        # 2) Xposed en system properties
        for k, v in self._system_properties.items():
            if "xposed" in str(v).lower():
                evidence_parts.append(f"prop {k}={v}")
        if not evidence_parts:
            return None
        return ThreatSignal(
            severity="high",
            category="xposed",
            evidence="; ".join(evidence_parts),
            mitre_id="T1056.001",
        )

    def detect_emulator(self) -> Optional[ThreatSignal]:
        """Detecta entorno emulado (qemu, goldfish, sdk)."""
        evidence_parts: List[str] = []
        for prop_string in self.emulator_indicators:
            if "=" in prop_string:
                k, _, expected = prop_string.partition("=")
                actual = self._system_properties.get(k)
                if actual and expected and expected.lower() in actual.lower():
                    evidence_parts.append(f"{k}={actual}")
        if not evidence_parts:
            return None
        return ThreatSignal(
            severity="medium",
            category="emulator",
            evidence="; ".join(evidence_parts),
            mitre_id="T1518",
        )

    def detect_memory_tamper(self) -> Optional[ThreatSignal]:
        """Heurística de tampering en memoria: librerías escritas fuera de
        /system o /data, o mprotect con RWX tras cargar."""
        evidence_parts: List[str] = []
        for lib in self._loaded_libs:
            # Cualquier lib en /tmp o con permisos no estándar
            if lib.startswith("/tmp/") or "/rwx_" in lib or "tampered" in lib:
                evidence_parts.append(f"suspicious mapping: {lib}")
        if not evidence_parts:
            return None
        return ThreatSignal(
            severity="critical",
            category="memory_tamper",
            evidence="; ".join(evidence_parts),
            mitre_id="T1611",
        )

    def detect_debugger(self) -> Optional[ThreatSignal]:
        """Detecta debugger activo via ``TracerPid`` en /proc/self/status.
        En Android se aplica al PID del zygote / app process."""
        tracer = self._proc_status.get("TracerPid", "0")
        try:
            tracer_int = int(tracer)
        except (TypeError, ValueError):
            tracer_int = -1
        if tracer_int <= 0:
            return None
        return ThreatSignal(
            severity="high",
            category="debugger",
            evidence=f"TracerPid={tracer_int}",
            mitre_id="T1611",
        )

    # ---------- Binary integrity ----------

    def compute_binary_hash(self, path: Optional[pathlib.Path] = None) -> str:
        """SHA-256 del binario asociado. Si el path no existe, devuelve
        el hash de un payload vacío (tests deterministas)."""
        target = pathlib.Path(path) if path else self.binary_path
        if target is None or not target.exists():
            return hashlib.sha256(b"").hexdigest()
        h = hashlib.sha256()
        with open(target, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def is_binary_allowed(self, sha256: str) -> bool:
        """True si el hash está en el allowlist o el allowlist está vacío
        (modo permisivo; útil durante el primer despliegue)."""
        if not self.binary_allowlist:
            return True
        return sha256 in self.binary_allowlist

    def verify_binary(self) -> Optional[ThreatSignal]:
        """Compara hash actual contra el allowlist; retorna señal si
        el binario NO está permitido."""
        sha = self.compute_binary_hash()
        if self.is_binary_allowed(sha):
            return None
        return ThreatSignal(
            severity="high",
            category="binary",
            evidence=f"sha256={sha} not in allowlist",
            mitre_id="T1623",
            extra={"sha256": sha},
        )

    # ---------- Aggregate ----------

    def scan(self) -> List[ThreatSignal]:
        """Corre todos los detectores y devuelve la lista agregada."""
        detectors = [
            self.detect_frida,
            self.detect_xposed,
            self.detect_emulator,
            self.detect_memory_tamper,
            self.detect_debugger,
            self.verify_binary,
        ]
        results: List[ThreatSignal] = []
        for det in detectors:
            try:
                r = det()
            except Exception as e:  # pragma: no cover — defensivo
                logger.warning("detector %s falló: %s", det.__name__, e)
                continue
            if r is not None:
                results.append(r)
        return results

    # ---------- Helpers ----------

    def _is_port_open(self, port: int, host: str = "127.0.0.1", timeout: float = 0.1) -> bool:
        if port in self._port_open_cache:
            return self._port_open_cache[port]
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                s.connect((host, port))
                self._port_open_cache[port] = True
                return True
        except OSError:
            self._port_open_cache[port] = False
            return False


# ===================== Enforcer =====================


class RASPEnforcer:
    """Aplica acciones reactivas a señales de RASP. Las acciones se
    publican a un callable (``bus.publish``) que el DefenseMesh conecta.
    En modo test se puede pasar un ``MockBus``."""

    def __init__(self, bus: Optional[Any] = None, *, device_id: str = "device-unknown"):
        self.bus = bus
        self.device_id = device_id
        self._actions: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def _publish(self, topic: str, payload: Dict[str, Any]) -> None:
        record = {"topic": topic, "payload": payload, "ts": time.time()}
        with self._lock:
            self._actions.append(record)
        if self.bus is not None:
            try:
                self.bus.publish(topic, payload)
            except Exception as e:  # pragma: no cover — defensivo
                logger.warning("bus.publish falló: %s", e)

    def quarantine(self, reason: str, signal: Optional[ThreatSignal] = None) -> Dict[str, Any]:
        """Aísla al dispositivo (push notification + revoke tokens)."""
        payload = {
            "device_id": self.device_id,
            "action": "quarantine",
            "reason": reason,
            "signal": signal.to_dict() if signal else None,
        }
        self._publish("rasp.quarantine", payload)
        return payload

    def revoke_session(self, reason: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Revoca la sesión del usuario en el device."""
        payload = {
            "device_id": self.device_id,
            "user_id": user_id,
            "action": "revoke_session",
            "reason": reason,
        }
        self._publish("rasp.revoke_session", payload)
        return payload

    def notify_soar(self, playbook_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Emite un evento al SOAR para disparar un playbook."""
        payload = {
            "device_id": self.device_id,
            "playbook_id": playbook_id,
            "inputs": inputs,
        }
        self._publish("soar.run_playbook", payload)
        return payload

    # ---------- Inspection (tests/dashboard) ----------

    def actions(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._actions)


# ===================== Mock bus para tests =====================


class MockBus:
    """Bus en memoria minimal. Captura todos los ``publish(topic, payload)``."""

    def __init__(self):
        self.events: List[Tuple[str, Dict[str, Any]]] = []
        self._lock = threading.Lock()

    def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            self.events.append((topic, payload))

    def by_topic(self, topic: str) -> List[Dict[str, Any]]:
        return [p for t, p in self.events if t == topic]
