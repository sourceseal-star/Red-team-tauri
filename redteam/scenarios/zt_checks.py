#!/usr/bin/env python3
"""
Zero Trust Checks — Validaciones que se integran con los escenarios existentes.
Cada escenario ofensivo ahora también valida la postura defensiva Zero Trust:

  - ¿El endpoint requiere autenticación?
  - ¿Valida postura del dispositivo (attestation)?
  - ¿Tiene rate limiting?
  - ¿Protege contra BOLA/cross-tenant?
  - ¿Requiere MFA para acciones sensibles?

Estos checks se ejecutan ANTES del ataque ofensivo para mapear la superficie
de defensa, y DESPUÉS para verificar si el ataque fue bloqueado.
"""
import json
import time
import hashlib
import datetime
from typing import List, Dict, Any
from collections import defaultdict


# Mapeo de escenarios a controles Zero Trust que deberían existir
ZT_EXPECTATIONS = {
    "rng": {
        "requires_auth": False,        # verificación pública de entropía
        "requires_attestation": False,
        "rate_limit_per_minute": 60,
        "mfa_required": False,
        "bola_relevant": False,
    },
    "pinning": {
        "requires_auth": False,
        "requires_attestation": True,   # pinning es control del cliente
        "rate_limit_per_minute": 30,
        "mfa_required": False,
        "bola_relevant": False,
    },
    "sidechannel": {
        "requires_auth": False,
        "requires_attestation": True,
        "rate_limit_per_minute": 30,
        "mfa_required": False,
        "bola_relevant": False,
    },
    "keyhandling": {
        "requires_auth": True,
        "requires_attestation": True,  # claves deben estar en HSM
        "rate_limit_per_minute": 10,
        "mfa_required": True,
        "bola_relevant": True,          # no ver claves de otros
    },
    "payments": {
        "requires_auth": True,
        "requires_attestation": True,
        "rate_limit_per_minute": 5,
        "mfa_required": True,
        "bola_relevant": True,          # no pagar con tarjeta de otro
    },
    "biometric": {
        "requires_auth": True,
        "requires_attestation": True,
        "rate_limit_per_minute": 10,
        "mfa_required": True,
        "bola_relevant": True,
    },
    "business_logic": {
        "requires_auth": True,
        "requires_attestation": False,
        "rate_limit_per_minute": 20,
        "mfa_required": False,
        "bola_relevant": True,
    },
    "imei": {
        "requires_auth": True,
        "requires_attestation": True,
        "rate_limit_per_minute": 30,
        "mfa_required": False,
        "bola_relevant": True,
    },
    "multiplatform": {
        "requires_auth": True,
        "requires_attestation": True,
        "rate_limit_per_minute": 30,
        "mfa_required": False,
        "bola_relevant": False,
    },
    "sourcesealcorp": {
        "requires_auth": True,
        "requires_attestation": True,
        "rate_limit_per_minute": 10,
        "mfa_required": True,
        "bola_relevant": True,
    },
    "recovery_page": {
        "requires_auth": False,
        "requires_attestation": False,
        "rate_limit_per_minute": 5,
        "mfa_required": False,
        "bola_relevant": False,
    },
    "pegasus": {
        "requires_auth": False,
        "requires_attestation": True,
        "rate_limit_per_minute": 60,
        "mfa_required": False,
        "bola_relevant": False,
    },
}


def evaluate_zt_posture(scenario_name: str, findings: List[Dict],
                        backend: str = "") -> Dict[str, Any]:
    """
    Evalúa la postura Zero Trust de un escenario basado en sus hallazgos.
    Retorna un score 0-100 y lista de gaps detectados.
    """
    expectations = ZT_EXPECTATIONS.get(scenario_name, {})
    if not expectations:
        return {
            "scenario": scenario_name,
            "zt_score": 0,
            "gaps": ["Sin expectativas ZT definidas para este escenario"],
        }

    gaps = []
    controls_passed = 0
    total_controls = 0

    # 1. ¿El ataque explotó ausencia de auth?
    for f in findings:
        desc = f.get("description", "").lower()
        title = f.get("title", "").lower()

        if expectations.get("requires_auth"):
            total_controls += 1
            if "auth" in desc or "sin autenticacion" in desc or "unauthenticated" in title:
                gaps.append("FAIL: Endpoint accesible sin autenticación")
            else:
                controls_passed += 1

        if expectations.get("requires_attestation"):
            total_controls += 1
            if "attest" in desc or "keystore" in desc or "keychain" in desc:
                # Si el finding es sobre falta de keystore, es un gap
                if "no se encontr" in desc or "sin" in desc or "ausente" in desc:
                    gaps.append("FAIL: Atestación/Keystore no implementado")
                else:
                    controls_passed += 1
            elif f.get("severity") in ("critical", "high"):
                # Finding crítico en escenario que requiere atestación = posible gap
                gaps.append(f"WARN: Finding crítico en escenario que requiere atestación: {f['title']}")
            else:
                controls_passed += 1

        if expectations.get("bola_relevant"):
            total_controls += 1
            if "bola" in desc or "cross-tenant" in desc or "idot" in desc:
                gaps.append("FAIL: BOLA/cross-tenant vulnerability detectada")
            else:
                controls_passed += 1

    # 2. Rate limiting — si el escenario generó muchos findings rápidos, quizá no hay rate limit
    rate_limit = expectations.get("rate_limit_per_minute", 60)
    if findings:
        total_controls += 1
        # Si hay findings de rate limit o race condition, el control falló
        rate_findings = [f for f in findings if "rate" in f.get("title", "").lower()
                       or "race" in f.get("title", "").lower()]
        if rate_findings:
            gaps.append(f"FAIL: Rate limit ({rate_limit}/min) insuficiente o ausente")
        else:
            controls_passed += 1

    # 3. MFA
    if expectations.get("mfa_required"):
        total_controls += 1
        mfa_findings = [f for f in findings if "mfa" in f.get("description", "").lower()
                       or "reauth" in f.get("title", "").lower()]
        if mfa_findings:
            gaps.append("FAIL: MFA no implementado o bypaseable")
        else:
            controls_passed += 1

    # Calcular score
    zt_score = int((controls_passed / max(total_controls, 1)) * 100)

    return {
        "scenario": scenario_name,
        "zt_score": zt_score,
        "zt_expectations": expectations,
        "controls_passed": controls_passed,
        "total_controls": total_controls,
        "gaps": gaps,
    }


def generate_zt_report(all_results: Dict[str, Dict]) -> Dict:
    """Genera un reporte consolidado de postura Zero Trust."""
    scores = []
    all_gaps = []

    for scenario, result in all_results.items():
        scores.append(result["zt_score"])
        all_gaps.extend([{"scenario": scenario, "gap": g} for g in result.get("gaps", [])])

    avg_score = sum(scores) / len(scores) if scores else 0
    failing = [s for s in scores if s < 50]
    passing = [s for s in scores if s >= 80]

    return {
        "overall_zt_score": avg_score,
        "scenarios_evaluated": len(all_results),
        "scenarios_passing_zt": len(passing),
        "scenarios_failing_zt": len(failing),
        "total_gaps": len(all_gaps),
        "gaps": all_gaps,
        "by_scenario": {s: r["zt_score"] for s, r in all_results.items()},
    }
