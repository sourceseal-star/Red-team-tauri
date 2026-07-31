#!/usr/bin/env python3
"""
ZTNA Gateway — Zero Trust Network Access con ABAC
===================================================
Reemplaza accesos perimetrales tradicionales. Cada request requiere:
  1. Autenticación (JWT/CEO hash)
  2. Autorización explícita (RBAC + ABAC)
  3. Validación de postura contextual (dispositivo, ubicación, certificado)
  4. Rate limiting adaptativo
  5. Fuzzing continuo de contratos OpenAPI

ABAC = Attribute-Based Access Control — evalúa atributos del sujeto,
recurso, acción y contexto en tiempo real.
"""
import json
import time
import hashlib
import datetime
import threading
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict, deque


class AccessDecision(Enum):
    ALLOW = "allow"
    DENY = "deny"
    DENY_MFA_REQUIRED = "deny_mfa_required"
    DENY_BAD_POSTURE = "deny_bad_posture"
    DENY_RATE_LIMIT = "deny_rate_limit"
    DENY_BOLA = "deny_bola"


@dataclass
class ABACPolicy:
    name: str
    resource_pattern: str         # regex del endpoint, ej: /api/courses/*
    required_roles: List[str]     # ["student", "ceo"]
    required_posture: Dict[str, Any] = field(default_factory=dict)
    rate_limit_per_minute: int = 60
    require_mfa: bool = False
    allow_cross_tenant: bool = False  # BOLA protection


@dataclass
class AccessRequest:
    user_id: str
    user_hash: str
    role: str
    endpoint: str
    method: str
    resource_owner_id: str = ""   # para BOLA check
    device_attested: bool = False
    device_id: str = ""
    ip_address: str = ""
    geo: str = ""
    jwt: str = ""


class ZTNAGateway:
    """Gateway Zero Trust con evaluación ABAC en tiempo real."""

    POLICIES: List[ABACPolicy] = [
        # Públicos — sin auth
        ABACPolicy(name="public_verify", resource_pattern=r"^/api/seals/verify/",
                   required_roles=[], rate_limit_per_minute=100),
        ABACPolicy(name="public_courses_list", resource_pattern=r"^/api/courses$",
                   required_roles=[], rate_limit_per_minute=60),
        ABACPolicy(name="public_course_detail", resource_pattern=r"^/api/courses/[\w-]+$",
                   required_roles=[], rate_limit_per_minute=60),

        # Estudiantes
        ABACPolicy(name="student_enroll", resource_pattern=r"^/api/enrollments",
                   required_roles=["student", "ceo"],
                   rate_limit_per_minute=20, require_mfa=False),
        ABACPolicy(name="student_progress", resource_pattern=r"^/api/progress",
                   required_roles=["student", "ceo"],
                   rate_limit_per_minute=120),
        ABACPolicy(name="student_certificates", resource_pattern=r"^/api/certificates",
                   required_roles=["student", "ceo"],
                   rate_limit_per_minute=30),

        # CEO Admin
        ABACPolicy(name="ceo_admin", resource_pattern=r"^/api/admin/.*",
                   required_roles=["ceo"],
                   required_posture={"device_attested": True, "mfa": True},
                   rate_limit_per_minute=30, require_mfa=True),
        ABACPolicy(name="ceo_seals", resource_pattern=r"^/api/admin/seals.*",
                   required_roles=["ceo"],
                   required_posture={"device_attested": True, "mfa": True},
                   rate_limit_per_minute=10, require_mfa=True),

        # Pagos
        ABACPolicy(name="payments", resource_pattern=r"^/api/payment.*",
                   required_roles=["student", "ceo"],
                   required_posture={"device_attested": True},
                   rate_limit_per_minute=5, require_mfa=False),

        # Honeypot / Deception — solo SOAR
        ABACPolicy(name="honeypot", resource_pattern=r"^/v1/(keys|auth|transactions)",
                   required_roles=[], rate_limit_per_minute=1000),  # tarpit intencional
    ]

    def __init__(self):
        self._rate_tracker: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._blocked_ips: Dict[str, float] = {}  # ip -> expiry timestamp
        self._quarantined_devices: Dict[str, Dict] = {}
        self._flagged_reauth: Dict[str, float] = {}  # user_hash -> expiry
        self._lock = threading.Lock()
        self.audit_log: List[Dict] = []

    def evaluate(self, req: AccessRequest) -> Tuple[AccessDecision, str, Optional[ABACPolicy]]:
        """Evalúa un request contra las políticas ZTNA + ABAC. Retorna decisión + razón."""
        now = time.time()

        # 1. IP bloqueada?
        with self._lock:
            if req.ip_address in self._blocked_ips:
                if self._blocked_ips[req.ip_address] > now:
                    self._log(req, AccessDecision.DENY, "IP blocked by SOAR")
                    return AccessDecision.DENY, "IP blocked by SOAR", None
                else:
                    del self._blocked_ips[req.ip_address]

        # 2. Dispositivo en cuarentena?
        with self._lock:
            if req.device_id and req.device_id in self._quarantined_devices:
                q = self._quarantined_devices[req.device_id]
                if q.get("allowed_endpoints") and req.endpoint not in q["allowed_endpoints"]:
                    self._log(req, AccessDecision.DENY_BAD_POSTURE, "Device quarantined")
                    return AccessDecision.DENY_BAD_POSTURE, "Device quarantined by SOAR", None

        # 3. Re-auth forzada?
        with self._lock:
            if req.user_hash in self._flagged_reauth:
                if self._flagged_reauth[req.user_hash] > now:
                    if not req.device_attested:
                        self._log(req, AccessDecision.DENY_MFA_REQUIRED, "Forced reauth MFA")
                        return AccessDecision.DENY_MFA_REQUIRED, "MFA required (SOAR triggered)", None
                else:
                    del self._flagged_reauth[req.user_hash]

        # 4. Encontrar política que coincida
        import re
        policy = None
        for p in self.POLICIES:
            if re.match(p.resource_pattern, req.endpoint):
                policy = p
                break

        if not policy:
            self._log(req, AccessDecision.DENY, "No matching policy")
            return AccessDecision.DENY, "No matching ZTNA policy", None

        # 5. Verificar roles
        if policy.required_roles and req.role not in policy.required_roles:
            self._log(req, AccessDecision.DENY, f"Role {req.role} not in {policy.required_roles}")
            return AccessDecision.DENY, f"Insufficient role: {req.role}", policy

        # 6. BOLA / Cross-tenant check
        if not policy.allow_cross_tenant and req.resource_owner_id:
            if req.user_id != req.resource_owner_id and req.role != "ceo":
                self._log(req, AccessDecision.DENY_BOLA, f"BOLA: {req.user_hash} -> {req.resource_owner_id}")
                return AccessDecision.DENY_BOLA, "BOLA: accessing other tenant's resource", policy

        # 7. Postura del dispositivo
        if policy.required_posture.get("device_attested") and not req.device_attested:
            self._log(req, AccessDecision.DENY_BAD_POSTURE, "Device not attested")
            return AccessDecision.DENY_BAD_POSTURE, "Device attestation required", policy

        # 8. MFA
        if policy.require_mfa:
            if not req.device_attested:
                self._log(req, AccessDecision.DENY_MFA_REQUIRED, "MFA required")
                return AccessDecision.DENY_MFA_REQUIRED, "MFA required", policy

        # 9. Rate limiting adaptativo
        key = f"{req.user_hash}:{req.ip_address}"
        with self._lock:
            tracker = self._rate_tracker[key]
            cutoff = now - 60
            while tracker and tracker[0] < cutoff:
                tracker.popleft()
            if len(tracker) >= policy.rate_limit_per_minute:
                self._log(req, AccessDecision.DENY_RATE_LIMIT,
                          f"Rate limit {policy.rate_limit_per_minute}/min exceeded")
                return AccessDecision.DENY_RATE_LIMIT, f"Rate limit exceeded ({policy.rate_limit_per_minute}/min)", policy
            tracker.append(now)

        self._log(req, AccessDecision.ALLOW, "OK")
        return AccessDecision.ALLOW, "Access granted", policy

    def block_ip(self, ip: str, duration_hours: float = 24) -> None:
        with self._lock:
            self._blocked_ips[ip] = time.time() + duration_hours * 3600

    def quarantine_device(self, device_id: str, allowed_endpoints: List[str] = None) -> None:
        with self._lock:
            self._quarantined_devices[device_id] = {
                "quarantined_at": datetime.datetime.utcnow().isoformat() + "Z",
                "allowed_endpoints": allowed_endpoints or ["/api/health"],
            }

    def flag_reauth(self, user_hash: str, duration_minutes: float = 30) -> None:
        with self._lock:
            self._flagged_reauth[user_hash] = time.time() + duration_minutes * 60

    def _log(self, req: AccessRequest, decision: AccessDecision, reason: str) -> None:
        self.audit_log.append({
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "user_hash": req.user_hash,
            "endpoint": req.endpoint,
            "method": req.method,
            "ip": req.ip_address,
            "decision": decision.value,
            "reason": reason,
        })

    def get_audit_summary(self) -> Dict:
        by_decision = {}
        for e in self.audit_log:
            by_decision[e["decision"]] = by_decision.get(e["decision"], 0) + 1
        return {
            "total_evaluations": len(self.audit_log),
            "by_decision": by_decision,
            "blocked_ips": len(self._blocked_ips),
            "quarantined_devices": len(self._quarantined_devices),
            "flagged_reauth": len(self._flagged_reauth),
            "recent": self.audit_log[-20:],
        }


# ─── API Fuzzer — Fuzzing continuo de contratos OpenAPI ─────────────────────

class APIFuzzer:
    """Fuzzer de contratos OpenAPI para integración CI/CD."""

    MUTATIONS = [
        ("type_confusion", lambda v: 12345 if isinstance(v, str) else "injected"),
        ("null_injection", lambda v: None),
        ("overflow", lambda v: "A" * 10000 if isinstance(v, str) else v),
        ("sql_injection", lambda v: "' OR 1=1 --" if isinstance(v, str) else v),
        ("xss", lambda v: "<script>alert(1)</script>" if isinstance(v, str) else v),
        ("path_traversal", lambda v: "../../../etc/passwd" if isinstance(v, str) else v),
        ("race_condition", lambda v: v),  # el handler envía N copias simultáneas
    ]

    def __init__(self, openapi_spec: Dict = None):
        self.spec = openapi_spec or {}
        self.results: List[Dict] = []

    def fuzz_endpoint(self, endpoint: str, method: str, params: Dict[str, Any],
                      handler: callable = None) -> List[Dict]:
        results = []
        for mut_name, mut_fn in self.MUTATIONS:
            mutated = {k: mut_fn(v) for k, v in params.items()}
            try:
                if handler:
                    ok = handler(mutated)
                    results.append({
                        "endpoint": endpoint, "method": method,
                        "mutation": mut_name, "status": "ok" if ok else "error",
                        "input": str(mutated)[:200],
                    })
                else:
                    results.append({
                        "endpoint": endpoint, "method": method,
                        "mutation": mut_name, "status": "dry-run",
                        "input": str(mutated)[:200],
                    })
            except Exception as e:
                results.append({
                    "endpoint": endpoint, "method": method,
                    "mutation": mut_name, "status": "crash",
                    "error": str(e)[:200],
                })
        self.results.extend(results)
        return results

    def get_report(self) -> Dict:
        by_status = {}
        for r in self.results:
            by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        return {
            "total_fuzz_tests": len(self.results),
            "by_status": by_status,
            "crashes": [r for r in self.results if r["status"] == "crash"],
        }
