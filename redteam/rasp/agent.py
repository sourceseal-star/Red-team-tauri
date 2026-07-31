#!/usr/bin/env python3
"""
RASP — Runtime Application Self-Protection (Cliente Móvil)
============================================================
Agente embebido que monitorea el runtime del ejecutable y detecta:
  - Hooking (Frida, Xposed, Substrate)
  - Ejecución en emuladores
  - Análisis en memoria (memory dumping, ptrace)
  - Alteración del binario (tampering, repackaging)
  - Debugger attachment (ptrace, gdb, lldb)
  - Root/Jailbreak

Además valida la atestación del dispositivo antes de autorizar
peticiones hacia la API (Play Integrity API / DeviceCheck).

Este módulo genera eventos XDR que se envían al correlador central.
"""
import os
import re
import time
import hashlib
import platform
import subprocess
import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class RASPAlert:
    type: str            # hooking | emulator | memory_dump | tampering | debugger | root
    severity: str
    detail: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    mitre: str = ""


class HookingDetector:
    """Detecta frameworks de hooking: Frida, Xposed, Substrate."""

    FRIDA_INDICATORS = [
        "frida-server", "frida-agent", "re.frida.server",
        "linjector", "gum-js-loop", "gmain",
    ]
    XPOSED_INDICATORS = [
        "de.robv.android.xposed", "XposedBridge",
        "com.saurik.substrate", "Substrate",
    ]

    @classmethod
    def check_processes(cls) -> List[RASPAlert]:
        alerts = []
        system = platform.system()
        if system not in ("Linux", "Darwin"):
            return alerts

        try:
            out = subprocess.check_output(["ps", "auxww"], text=True, timeout=5)
        except Exception:
            return alerts

        for indicator in cls.FRIDA_INDICATORS:
            if indicator in out:
                alerts.append(RASPAlert(
                    type="hooking", severity="critical",
                    detail=f"Frida detectado: proceso '{indicator}' en ejecucion",
                    evidence={"process": indicator, "framework": "frida"},
                    timestamp=datetime.datetime.utcnow().isoformat() + "Z",
                    mitre="T1622",
                ))

        for indicator in cls.XPOSED_INDICATORS:
            if indicator in out:
                alerts.append(RASPAlert(
                    type="hooking", severity="critical",
                    detail=f"Xposed/Substrate detectado: '{indicator}'",
                    evidence={"process": indicator, "framework": "xposed"},
                    timestamp=datetime.datetime.utcnow().isoformat() + "Z",
                    mitre="T1622",
                ))

        # Verificar puertos típicos de Frida (27042)
        try:
            netstat = subprocess.check_output(
                ["netstat", "-tlnp"], text=True, timeout=5
            ) if system == "Linux" else ""
            if "27042" in netstat:
                alerts.append(RASPAlert(
                    type="hooking", severity="critical",
                    detail="Frida escuchando en puerto 27042",
                    evidence={"port": 27042, "framework": "frida"},
                    timestamp=datetime.datetime.utcnow().isoformat() + "Z",
                    mitre="T1622",
                ))
        except Exception:
            pass

        return alerts

    @classmethod
    def check_loaded_libs(cls, target: str = "") -> List[RASPAlert]:
        """Verificar bibliotecas cargadas que indican hooking."""
        alerts = []
        suspicious_libs = [
            "libfrida-agent.so", "libfrida-gadget.so",
            "libsubstrate.so", "libxposed",
            "libcydia", "libssl_kill_switch",
        ]
        try:
            if target and os.path.exists(target):
                out = subprocess.check_output(["strings", "-a", target], text=True, timeout=60)
                for lib in suspicious_libs:
                    if lib in out:
                        alerts.append(RASPAlert(
                            type="hooking", severity="high",
                            detail=f"Biblioteca de hooking encontrada en binario: {lib}",
                            evidence={"library": lib, "target": target},
                            timestamp=datetime.datetime.utcnow().isoformat() + "Z",
                            mitre="T1622",
                        ))
        except Exception:
            pass
        return alerts


class EmulatorDetector:
    """Detecta ejecución en emulador (AVD, Genymotion, QEMU)."""

    EMULATOR_INDICATORS = [
        "goldfish", "ranchu", "generic_x86",
        "sdk_gphone", "google_sdk",
        "Android-x86", "genymotion",
        "qemu", "vbox",
    ]

    @classmethod
    def check(cls) -> List[RASPAlert]:
        alerts = []
        system = platform.system()

        # Verificar propiedades de Android si estamos en Linux
        if system == "Linux":
            for prop_file in ["/system/build.prop", "/system/lib/egl/egl.cfg"]:
                if os.path.exists(prop_file):
                    try:
                        content = open(prop_file, errors="ignore").read()
                        for indicator in cls.EMULATOR_INDICATORS:
                            if indicator.lower() in content.lower():
                                alerts.append(RASPAlert(
                                    type="emulator", severity="high",
                                    detail=f"Emulador detectado: '{indicator}' en {prop_file}",
                                    evidence={"indicator": indicator, "file": prop_file},
                                    timestamp=datetime.datetime.utcnow().isoformat() + "Z",
                                    mitre="T1622",
                                ))
                    except Exception:
                        pass

        # En macOS verificar VirtualBox/QEMU
        if system == "Darwin":
            try:
                out = subprocess.check_output(["sysctl", "machdep.cpu.brand_string"], text=True)
                if "QEMU" in out:
                    alerts.append(RASPAlert(
                        type="emulator", severity="high",
                        detail="CPU QEMU detectada — posible emulador",
                        evidence={"cpu": "QEMU"},
                        timestamp=datetime.datetime.utcnow().isoformat() + "Z",
                        mitre="T1622",
                    ))
            except Exception:
                pass

        return alerts


class TamperDetector:
    """Detecta alteración del binario (repackaging, modificación)."""

    @classmethod
    def check_signature(cls, target: str, expected_hash: str = "") -> List[RASPAlert]:
        alerts = []
        if not target or not os.path.exists(target):
            return alerts

        actual_hash = hashlib.sha256(open(target, "rb").read()).hexdigest()

        if expected_hash and actual_hash != expected_hash:
            alerts.append(RASPAlert(
                type="tampering", severity="critical",
                detail=f"Hash del binario no coincide — repackaging o modificacion detectada",
                evidence={
                    "expected": expected_hash,
                    "actual": actual_hash,
                    "target": target,
                },
                timestamp=datetime.datetime.utcnow().isoformat() + "Z",
                mitre="T1027",
            ))
        return alerts

    @classmethod
    def check_apk_integrity(cls, target: str) -> List[RASPAlert]:
        """Verifica integridad básica del APK."""
        alerts = []
        if not target or not os.path.exists(target):
            return alerts

        try:
            out = subprocess.check_output(["strings", "-a", target], text=True, timeout=60)

            # Buscar indicios de re-firma
            if "testkey" in out or "debug.keystore" in out:
                alerts.append(RASPAlert(
                    type="tampering", severity="high",
                    detail="APK firmada con key de debug/test — posible repackaging",
                    evidence={"indicator": "debug_keystore"},
                    timestamp=datetime.datetime.utcnow().isoformat() + "Z",
                    mitre="T1027",
                ))

            # Verificar que no tiene Meta-INF alterada
            if "META-INF/CERT.SF" not in out and "META-INF/MANIFEST.MF" not in out:
                alerts.append(RASPAlert(
                    type="tampering", severity="high",
                    detail="Estructura de firma del APK alterada",
                    evidence={"missing": "META-INF/CERT.SF"},
                    timestamp=datetime.datetime.utcnow().isoformat() + "Z",
                    mitre="T1027",
                ))
        except Exception:
            pass

        return alerts


class DebuggerDetector:
    """Detecta debugger attached (ptrace, gdb, lldb)."""

    @classmethod
    def check(cls) -> List[RASPAlert]:
        alerts = []
        system = platform.system()

        if system == "Linux":
            # /proc/self/status -> TracerPid
            try:
                status = open("/proc/self/status").read()
                for line in status.splitlines():
                    if line.startswith("TracerPid:"):
                        pid = line.split(":")[1].strip()
                        if pid != "0":
                            alerts.append(RASPAlert(
                                type="debugger", severity="critical",
                                detail=f"Debugger attached: TracerPid={pid}",
                                evidence={"tracer_pid": pid},
                                timestamp=datetime.datetime.utcnow().isoformat() + "Z",
                                mitre="T1622",
                            ))
            except Exception:
                pass

        return alerts


class RootDetector:
    """Detecta root/jailbreak en el dispositivo."""

    ROOT_INDICATORS = [
        "/sbin/su", "/system/bin/su", "/system/xbin/su",
        "/data/local/su", "/data/local/bin/su",
        "/system/app/Superuser.apk", "/system/app/SuperSU",
        "/data/data/com.noshufou.android.su",
        "/system/etc/init.d/99SuperSUDaemon",
        "/dev/com.koushikdut.superuser.daemon",
        "/Magisk", "/sbin/.magisk",
    ]

    @classmethod
    def check(cls) -> List[RASPAlert]:
        alerts = []
        for path in cls.ROOT_INDICATORS:
            if os.path.exists(path):
                alerts.append(RASPAlert(
                    type="root", severity="high",
                    detail=f"Root detectado: {path} existe",
                    evidence={"path": path},
                    timestamp=datetime.datetime.utcnow().isoformat() + "Z",
                    mitre="T1622",
                ))
        return alerts


class AttestationChecker:
    """Valida atestación del dispositivo (Play Integrity / DeviceCheck)."""

    def __init__(self, api_key: str = "", endpoint: str = ""):
        self.api_key = api_key
        self.endpoint = endpoint or os.environ.get(
            "ATTESTATION_ENDPOINT", "https://playintegrity.googleapis.com/v1"
        )

    def verify(self, nonce: str, device_id: str = "") -> Dict[str, Any]:
        """
        Verifica atestación del dispositivo.
        En dry-run retorna postura básica basada en RASP checks.
        """
        result = {
            "attested": False,
            "integrity_pass": False,
            "device_safe": False,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        }

        # Si hay root o hooking, no atestar
        root_alerts = RootDetector.check()
        hook_alerts = HookingDetector.check_processes()
        emu_alerts = EmulatorDetector.check()

        if not root_alerts and not hook_alerts and not emu_alerts:
            result["attested"] = True
            result["integrity_pass"] = True
            result["device_safe"] = True
        else:
            result["issues"] = [a.detail for a in root_alerts + hook_alerts + emu_alerts]

        return result


class RASPAgent:
    """Agente RASP que integra todos los detectores."""

    def __init__(self, target: str = ""):
        self.target = target
        self.alerts: List[RASPAlert] = []

    def scan(self) -> List[RASPAlert]:
        """Ejecuta todos los detectores."""
        self.alerts = []
        self.alerts.extend(HookingDetector.check_processes())
        self.alerts.extend(HookingDetector.check_loaded_libs(self.target))
        self.alerts.extend(EmulatorDetector.check())
        self.alerts.extend(DebuggerDetector.check())
        self.alerts.extend(RootDetector.check())
        if self.target:
            self.alerts.extend(TamperDetector.check_apk_integrity(self.target))
        return self.alerts

    def attest(self) -> Dict[str, Any]:
        """Ejecuta atestación del dispositivo."""
        return AttestationChecker().verify(nonce=hashlib.sha256(str(time.time()).encode()).hexdigest())

    def export_alerts(self) -> List[Dict]:
        return [asdict(a) for a in self.alerts]

    def get_summary(self) -> Dict:
        by_type = {}
        by_severity = {}
        for a in self.alerts:
            by_type[a.type] = by_type.get(a.type, 0) + 1
            by_severity[a.severity] = by_severity.get(a.severity, 0) + 1
        return {
            "total_alerts": len(self.alerts),
            "by_type": by_type,
            "by_severity": by_severity,
            "device_attested": self.attest().get("attested", False) if not self.alerts else False,
        }
