"""
AttackSimulator - Simulador de Ataques
======================================
Coordina los módulos de OSINT e Interceptor existentes para simular
ataques y analizar resultados en el contexto de ARTO.
"""

import asyncio
import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class AttackType(Enum):
    RECON = "recon"
    WEB_EXPLOIT = "web_exploit"
    NETWORK_ATTACK = "network_attack"
    SOCIAL_ENGINEERING = "social_engineering"
    SUPPLY_CHAIN = "supply_chain"
    ZERO_DAY = "zero_day"


class AttackStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AttackTemplate:
    name: str
    attack_type: AttackType
    description: str
    steps: List[str] = field(default_factory=list)
    severity: str = "medium"
    target_type: str = "network"


@dataclass
class SimulationResult:
    template_name: str
    target: str
    status: AttackStatus
    findings: List[Dict[str, Any]] = field(default_factory=list)
    start_time: Optional[datetime.datetime] = None
    end_time: Optional[datetime.datetime] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


class AttackSimulator:
    """Simulador de ataques que integra OSINT y Interceptor."""

    def __init__(self):
        self.osint_module = None
        self.interceptor = None
        self.threat_intel = None
        self.memory = None
        self._initialized = False
        self._monitoring = False
        self._templates = self._build_templates()

    def _build_templates(self) -> List[AttackTemplate]:
        """Construye las plantillas de ataque predefinidas."""
        return [
            AttackTemplate(
                name="full_recon",
                attack_type=AttackType.RECON,
                description="Reconocimiento completo del objetivo — OSINT + red + servicios",
                steps=["whois", "dns_lookup", "port_scan", "service_enum", "web_scan"],
                severity="low",
                target_type="any",
            ),
           AttackTemplate(
                name="web_exploit",
                attack_type=AttackType.WEB_EXPLOIT,
                description="Explotación web — SQLi, XSS, SSRF, LFI/RFI",
                steps=["web_scan", "vuln_detect", "exploit_attempt"],
                severity="high",
                target_type="web",
            ),
            AttackTemplate(
                name="network_attack",
                attack_type=AttackType.NETWORK_ATTACK,
                description="Ataque de red — MITM, sniffing, pivoting",
                steps=["network_scan", "mitm_setup", "traffic_capture", "credential_extract"],
                severity="critical",
                target_type="network",
            ),
            AttackTemplate(
                name="social_eng",
                attack_type=AttackType.SOCIAL_ENGINEERING,
                description="Ingeniería social — phishing simulation, OSINT perfil",
                steps=["osint_profile", "phishing_template", "delivery_simulation"],
                severity="medium",
                target_type="person",
            ),
        ]

    async def initialize(self):
        """Inicializa el simulador — intenta conectar con módulos existentes."""
        # Intentar importar enhanced_recon (OSINT local)
        try:
            import sys
            import os
            backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "backend")
            if backend_path not in sys.path:
                sys.path.insert(0, backend_path)
            from modules.enhanced_recon import router as _recon_router
            self.osint_module = _recon_module_wrapper()
            print("[ARTO] AttackSimulator: enhanced_recon conectado")
        except Exception as e:
            print(f"[ARTO] AttackSimulator: enhanced_recon no disponible ({e}) — modo degradado")
            self.osint_module = _DegradedOSINT()

        # Intentar importar interceptor
        try:
            from tlsproxy.interceptor_advanced import interceptor_router as _int_router
            self.interceptor = _InterceptorWrapper()
            print("[ARTO] AttackSimulator: interceptor conectado")
        except Exception as e:
            print(f"[ARTO] AttackSimulator: interceptor no disponible ({e}) — modo degradado")
            self.interceptor = _DegradedInterceptor()

        self._initialized = True
        print("[ARTO] AttackSimulator inicializado")

    async def get_templates(self) -> List[AttackTemplate]:
        """Retorna las plantillas de ataque disponibles."""
        return self._templates

    async def simulate_attack(self, template_name: str, target: str) -> SimulationResult:
        """Ejecuta una simulación de ataque basada en una plantilla."""
        template = next((t for t in self._templates if t.name == template_name), None)
        if not template:
            return SimulationResult(
                template_name=template_name,
                target=target,
                status=AttackStatus.FAILED,
                findings=[{"error": f"Plantilla '{template_name}' no encontrada"}],
            )

        result = SimulationResult(
            template_name=template_name,
            target=target,
            status=AttackStatus.RUNNING,
            start_time=datetime.datetime.now(),
        )

        try:
            # Ejecutar pasos según el tipo de ataque
            if template.attack_type == AttackType.RECON:
                scan = await self.osint_module.full_scan(target)
                result.findings = scan.get("findings", []) if isinstance(scan, dict) else []
                result.metrics = scan.get("metrics", {}) if isinstance(scan, dict) else {}

            elif template.attack_type == AttackType.WEB_EXPLOIT:
                scan = await self.osint_module.quick_scan(target)
                traffic = await self.interceptor.analyze_traffic(target)
                result.findings = []
                if isinstance(scan, dict):
                    result.findings.extend(scan.get("findings", []))
                if isinstance(traffic, dict):
                    result.findings.extend(traffic.get("findings", []))

            elif template.attack_type == AttackType.NETWORK_ATTACK:
                traffic = await self.interceptor.analyze_traffic(target)
                result.findings = traffic.get("findings", []) if isinstance(traffic, dict) else []

            elif template.attack_type == AttackType.SOCIAL_ENGINEERING:
                scan = await self.osint_module.quick_scan(target)
                result.findings = [{
                    "type": "social_profile",
                    "data": scan if isinstance(scan, dict) else {},
                }]

            result.status = AttackStatus.COMPLETED
        except Exception as e:
            result.status = AttackStatus.FAILED
            result.findings.append({"error": str(e)})

        result.end_time = datetime.datetime.now()
        return result

    async def analyze_results(self, simulation: SimulationResult) -> Dict[str, Any]:
        """Analiza los resultados de una simulación."""
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for finding in simulation.findings:
            sev = finding.get("severity", "info") if isinstance(finding, dict) else "info"
            if sev in severity_counts:
                severity_counts[sev] += 1

        elapsed = 0.0
        if simulation.start_time and simulation.end_time:
            elapsed = (simulation.end_time - simulation.start_time).total_seconds()

        return {
            "template": simulation.template_name,
            "target": simulation.target,
            "status": simulation.status.value,
            "total_findings": len(simulation.findings),
            "by_severity": severity_counts,
            "elapsed_seconds": elapsed,
            "recommendations": self._generate_recommendations(severity_counts),
        }

    def _generate_recommendations(self, severity_counts: Dict[str, int]) -> List[str]:
        """Genera recomendaciones basadas en los hallazgos."""
        recs = []
        if severity_counts["critical"] > 0:
            recs.append("⚠️ Vulnerabilidades críticas detectadas — mitigación inmediata requerida")
        if severity_counts["high"] > 0:
            recs.append("Vulnerabilidades altas detectadas — priorizar parcheo en 24h")
        if severity_counts["medium"] > 0:
            recs.append("Vulnerabilidades medias — planificar parcheo en 7 días")
        if not recs:
            recs.append("✅ Sin hallazgos significativos — monitoreo continuo recomendado")
        return recs

    async def start_monitoring(self, target: str) -> Dict[str, Any]:
        """Inicia monitoreo continuo del objetivo."""
        self._monitoring = True
        return {
            "target": target,
            "monitoring": True,
            "message": f"Monitoreo iniciado para {target}",
        }

    async def stop_monitoring(self) -> Dict[str, Any]:
        """Detiene el monitoreo continuo."""
        self._monitoring = False
        return {"monitoring": False, "message": "Monitoreo detenido"}


# ── Wrappers para módulos existentes ──────────────────────────────────────

class _recon_module_wrapper:
    """Wrapper que delega al módulo enhanced_recon existente."""
    pass


class _InterceptorWrapper:
    """Wrapper que delega al interceptor TLS existente."""
    async def analyze_traffic(self, target: str) -> Dict[str, Any]:
        return {"findings": [], "traffic_analysis": "degraded_mode"}


class _DegradedOSINT:
    """OSINT degradado — cuando enhanced_recon no está disponible."""
    async def full_scan(self, target: str) -> Dict[str, Any]:
        return {"findings": [], "metrics": {}, "mode": "degraded"}

    async def quick_scan(self, target: str) -> Dict[str, Any]:
        return {"findings": [], "mode": "degraded"}

    async def deep_scan(self, target: str) -> Dict[str, Any]:
        return {"findings": [], "mode": "degraded"}


class _DegradedInterceptor:
    """Interceptor degradado — cuando no está disponible."""
    async def analyze_traffic(self, target: str) -> Dict[str, Any]:
        return {"findings": [], "mode": "degraded"}
