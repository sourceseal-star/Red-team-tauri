"""
defense.ztna — Zero Trust Network Access
=========================================

Implementa el patrón ZTNA: cada request se evalúa contra un ``ZTNAContext``
que contiene identidad, dispositivo, postura y entorno. ``PolicyEngine``
ejecuta ABAC con un DSL simple, ``PostureScorer`` agrega checks de
dispositivo, ``JWTIssuer``/``JWTValidator`` gestionan tokens con
revocación inmediata, y ``BOLAProtector`` valida ownership de recursos.
"""
from __future__ import annotations

import base64
import dataclasses
import hashlib
import hmac
import json
import logging
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ===================== Data types =====================


@dataclasses.dataclass
class ZTNAContext:
    """Contexto de una petición ZTNA (sujeto + entorno + dispositivo)."""
    device_id: str
    user_id: str
    cert_fingerprint: str = ""        # SHA-256 del cert cliente
    posture_score: float = 1.0        # 0.0 (muy malo) .. 1.0 (excelente)
    location_risk: float = 0.0        # 0.0 (oficina) .. 1.0 (TOR/exit node)
    time_of_day: float = 12.0         # hora decimal UTC
    network_trust: float = 0.8        # 0.0 (red desconocida) .. 1.0 (corp)
    extra: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class AccessDecision:
    allow: bool
    reason: str
    matched_rule: Optional[str] = None
    extra: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


# ===================== Posture Scorer =====================


class PostureScorer:
    """Combina checks de postura del dispositivo en un score 0..1.

    Cada check retorna (pass: bool, weight: float). El score final es
    la suma de pesos pasados / suma total de pesos."""

    def __init__(self, *, min_score: float = 0.7):
        self.min_score = min_score
        # Pesos por check (suman 1.0)
        self._weights = {
            "cert_valid": 0.25,
            "os_patch": 0.25,
            "rasp_clean": 0.20,
            "no_jailbreak": 0.15,
            "network_trust": 0.15,
        }

    def evaluate(
        self,
        *,
        cert_valid: bool = True,
        os_patched: bool = True,
        rasp_clean: bool = True,
        jailbroken: bool = False,
        network_trust: float = 0.8,
    ) -> float:
        checks = {
            "cert_valid": (cert_valid, self._weights["cert_valid"]),
            "os_patch": (os_patched, self._weights["os_patch"]),
            "rasp_clean": (rasp_clean, self._weights["rasp_clean"]),
            "no_jailbreak": (not jailbroken, self._weights["no_jailbreak"]),
            "network_trust": (network_trust >= 0.5, self._weights["network_trust"]),
        }
        total = sum(w for _, w in checks.values())
        passed = sum(w for ok, w in checks.values() if ok)
        return round(passed / total, 4) if total else 0.0

    def is_acceptable(self, score: float) -> bool:
        return score >= self.min_score


# ===================== Policy Engine (ABAC) =====================


class PolicyEngine:
    """ABAC minimalista: lista de reglas ``(when, then)`` + default deny.

    El ``when`` es un string con comparaciones sobre campos del
    ZTNAContext. Soporta:

        subject.field op value
        env.field op value
        action == "..."

    Operadores: ``==``, ``!=``, ``<``, ``<=``, ``>``, ``>=``, ``in``.
    """

    OPS = {"==", "!=", "<=", ">=", "<", ">", "in", "not_in"}

    def __init__(self, *, default_deny: bool = True):
        self.default_deny = default_deny
        self._rules: List[Dict[str, Any]] = []
        self._denied_devices: Set[str] = set()

    def add_rule(self, *, when: str, allow: bool, name: str, action: Optional[str] = None) -> None:
        self._rules.append({"when": when, "allow": allow, "name": name, "action": action})

    def add_business_hours_rule(self, start: int = 9, end: int = 18) -> None:
        self.add_rule(
            name="business_hours_only_admin",
            when=f"action == 'admin' AND (env.time_of_day < {start} OR env.time_of_day > {end})",
            allow=False,
            action="admin",
        )

    def deny_device(self, device_id: str) -> None:
        self._denied_devices.add(device_id)

    def is_device_denied(self, device_id: str) -> bool:
        return device_id in self._denied_devices

    def evaluate(self, ctx: ZTNAContext, action: str, resource: str) -> AccessDecision:
        if self.is_device_denied(ctx.device_id):
            return AccessDecision(False, f"device {ctx.device_id} denied perimeter", "device_deny")
        if ctx.posture_score < 0.5:
            return AccessDecision(False, f"posture_score {ctx.posture_score} too low",
                                  "posture_min")
        env = {
            "time_of_day": ctx.time_of_day,
            "location_risk": ctx.location_risk,
            "network_trust": ctx.network_trust,
        }
        subject = {
            "user_id": ctx.user_id,
            "device_id": ctx.device_id,
            "cert_fingerprint": ctx.cert_fingerprint,
            "posture_score": ctx.posture_score,
        }
        scope = {"subject": subject, "env": env,
                 "action": action, "resource": resource}
        for rule in self._rules:
            if rule.get("action") and rule["action"] != action:
                continue
            try:
                ok = self._eval_when(rule["when"], scope)
            except Exception as e:
                logger.warning("regla '%s' falló al evaluar: %s", rule.get("name"), e)
                continue
            if ok:
                if rule["allow"]:
                    return AccessDecision(True, f"matched {rule['name']}", rule["name"])
                return AccessDecision(False, f"denied by {rule['name']}", rule["name"])
        if self.default_deny:
            return AccessDecision(False, "default deny (no allow rule matched)", "default_deny")
        return AccessDecision(True, "default allow", "default_allow")

    # ---------- DSL mini-evaluator ----------

    def _eval_when(self, expr: str, scope: Dict[str, Any]) -> bool:
        # Reemplazos de paths: subject.foo → scope['subject']['foo']
        def resolve(path: str) -> Any:
            path = path.strip()
            if path in scope:
                return scope[path]
            parts = path.split(".")
            node: Any = scope
            for p in parts:
                if isinstance(node, dict):
                    node = node.get(p)
                else:
                    return None
                if node is None:
                    return None
            return node

        # Normalizar operadores: paréntesis simples, AND/OR
        expr = expr.strip()
        # Split top-level por paréntesis equilibrando
        def tokenize(e: str) -> List[str]:
            tokens: List[str] = []
            depth = 0
            cur = ""
            i = 0
            while i < len(e):
                ch = e[i]
                if ch == "(":
                    depth += 1
                    cur += ch
                elif ch == ")":
                    depth -= 1
                    cur += ch
                elif ch == " " and depth == 0:
                    if cur:
                        tokens.append(cur)
                        cur = ""
                else:
                    cur += ch
                i += 1
            if cur:
                tokens.append(cur)
            return tokens

        tokens = tokenize(expr)
        if not tokens:
            return True
        # Resolver OR primero
        def parse_or(toks: List[str]) -> bool:
            left = parse_and(toks)
            i = 1
            while i < len(toks) and toks[i] == "OR":
                right = parse_and(toks[i + 1:])
                left = left or right
                # avanzar saltando right
                # (heurística: parse_and consume un token lógico + subexpr)
                i += 2
            return left

        def parse_and(toks: List[str]) -> bool:
            if not toks:
                return True
            left = parse_atom(toks[0])
            i = 1
            while i < len(toks) and toks[i] == "AND":
                right = parse_atom(toks[i + 1])
                left = left and right
                i += 2
            return left

        def parse_atom(tok: str) -> bool:
            # Quitar paréntesis envolventes
            tok = tok.strip()
            if tok.startswith("(") and tok.endswith(")"):
                return self._eval_when(tok[1:-1], scope)
            # Buscar el operador (los más largos primero para evitar pisar < con <=)
            for op in ["==", "!=", "<=", ">=", "in", "not_in", "<", ">"]:
                idx = tok.find(op)
                if idx > 0:
                    left = resolve(tok[:idx].strip())
                    right_str = tok[idx + len(op):].strip()
                    if op == "in":
                        items = [s.strip().strip("'\"") for s in right_str.split(",") if s.strip()]
                        return str(left) in items
                    if op == "not_in":
                        items = [s.strip().strip("'\"") for s in right_str.split(",") if s.strip()]
                        return str(left) not in items
                    right = resolve(right_str)
                    if right is None:
                        # Intentar literal numérico / string
                        try:
                            right = float(right_str)
                            if right.is_integer():
                                right = int(right)
                        except ValueError:
                            right = right_str.strip("'\"")
                    return self._compare(left, op, right)
            # Si no hay operador, evalúa como truthy sobre scope
            return bool(resolve(tok))

        return parse_or(tokens)

    @staticmethod
    def _compare(left: Any, op: str, right: Any) -> bool:
        if left is None:
            return False
        try:
            if op == "==":
                return left == right
            if op == "!=":
                return left != right
            if op == "<=":
                return left <= right
            if op == ">=":
                return left >= right
            if op == "<":
                return left < right
            if op == ">":
                return left > right
        except TypeError:
            return False
        return False


# ===================== JWT =====================


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + padding)


class JWTIssuer:
    """Emite JWT firmados con HS256. El header.payload va firmado con
    un secret; el ``claims`` dict se inyecta en el payload."""

    def __init__(self, secret: bytes, *, ttl_seconds: int = 900, alg: str = "HS256"):
        self.secret = secret
        self.ttl = ttl_seconds
        self.alg = alg
        self._lock = threading.Lock()
        # jti → exp
        self._issued: Dict[str, float] = {}

    def issue(self, subject: str, claims: Dict[str, Any]) -> str:
        header = {"alg": self.alg, "typ": "JWT"}
        now = int(time.time())
        payload = dict(claims)
        payload.update({"sub": subject, "iat": now,
                        "exp": now + self.ttl, "jti": hashlib.sha256(
                            f"{subject}-{now}-{claims.get('nonce','')}".encode()
                        ).hexdigest()[:16]})
        h = _b64url(json.dumps(header, sort_keys=True).encode())
        p = _b64url(json.dumps(payload, sort_keys=True).encode())
        signing_input = f"{h}.{p}".encode()
        sig = hmac.new(self.secret, signing_input, hashlib.sha256).digest()
        return f"{h}.{p}.{_b64url(sig)}"

    def track(self, jti: str, exp: int) -> None:
        with self._lock:
            self._issued[jti] = exp

    def active(self) -> int:
        now = time.time()
        with self._lock:
            return sum(1 for exp in self._issued.values() if exp > now)


class JWTValidator:
    """Valida y revoca tokens emitidos por ``JWTIssuer``.

    Mantiene un set de revocación inmediata (jti o subject+device)."""

    def __init__(self, secret: bytes, *, check: str = "strict"):
        self.secret = secret
        self.check = check
        self._revoked_jti: Set[str] = set()
        self._revoked_subj_dev: Set[Tuple[str, str]] = set()
        self._lock = threading.Lock()

    def validate(self, token: str) -> Dict[str, Any]:
        try:
            h, p, s = token.split(".")
        except ValueError:
            return {"valid": False, "reason": "malformed"}
        signing_input = f"{h}.{p}".encode()
        expected = hmac.new(self.secret, signing_input, hashlib.sha256).digest()
        try:
            actual = _b64url_decode(s)
        except Exception:
            return {"valid": False, "reason": "bad_signature_encoding"}
        if not hmac.compare_digest(expected, actual):
            return {"valid": False, "reason": "bad_signature"}
        try:
            payload = json.loads(_b64url_decode(p))
        except Exception:
            return {"valid": False, "reason": "bad_payload"}
        now = time.time()
        if payload.get("exp", 0) < now:
            return {"valid": False, "reason": "expired", "payload": payload}
        with self._lock:
            if payload.get("jti") in self._revoked_jti:
                return {"valid": False, "reason": "revoked_jti", "payload": payload}
            key = (payload.get("sub", ""), payload.get("device_id", ""))
            if key in self._revoked_subj_dev:
                return {"valid": False, "reason": "revoked_subj_dev", "payload": payload}
        return {"valid": True, "payload": payload}

    def revoke_jti(self, jti: str) -> None:
        with self._lock:
            self._revoked_jti.add(jti)

    def revoke_subject_device(self, subject: str, device_id: str) -> None:
        with self._lock:
            self._revoked_subj_dev.add((subject, device_id))

    def is_revoked(self, jti: str, subject: str, device_id: str) -> bool:
        with self._lock:
            return (jti in self._revoked_jti
                    or (subject, device_id) in self._revoked_subj_dev)


# ===================== BOLA Protector =====================


class BOLAProtector:
    """Verifica que el ``owner_id`` de un recurso coincida con el
    ``user_id`` del contexto ZTNA. Si no, genera un finding de tipo
    ``bola_attempt``."""

    def __init__(self):
        self._attempts: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def check(self, ctx: ZTNAContext, resource: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]]]:
        owner = resource.get("owner_id")
        if owner is None:
            return True, None  # no hay owner declarado, no se puede juzgar
        if str(owner) == str(ctx.user_id):
            return True, None
        attempt = {
            "user_id": ctx.user_id,
            "device_id": ctx.device_id,
            "resource_id": resource.get("id"),
            "claimed_owner": owner,
            "ts": time.time(),
        }
        with self._lock:
            self._attempts.append(attempt)
        return False, attempt

    def attempts(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._attempts)


# ===================== ZTNA Bundle (para uso externo) =====================


class ZTNAGateway:
    """Fachada que combina PolicyEngine + JWTIssuer + JWTValidator +
    BOLAProtector + PostureScorer. Es el objeto que el ``@protect``
    decorator del ``api_gateway`` consume."""

    def __init__(self, *, secret: bytes = b"change-me-please",
                 default_deny: bool = True,
                 posture_min: float = 0.7,
                 jwt_ttl: int = 900):
        self.posture = PostureScorer(min_score=posture_min)
        self.policy = PolicyEngine(default_deny=default_deny)
        self.issuer = JWTIssuer(secret, ttl_seconds=jwt_ttl)
        self.validator = JWTValidator(secret)
        self.bola = BOLAProtector()
        # Reglas por defecto razonables
        self.policy.add_rule(
            name="allow_high_posture",
            when="subject.posture_score >= 0.7 AND env.network_trust >= 0.5",
            allow=True,
        )
        self.policy.add_rule(
            name="deny_low_posture",
            when="subject.posture_score < 0.5",
            allow=False,
        )
        self.policy.add_rule(
            name="deny_high_location_risk",
            when="env.location_risk >= 0.9",
            allow=False,
        )

    def issue_token(self, ctx: ZTNAContext, claims: Optional[Dict[str, Any]] = None) -> str:
        claims = claims or {}
        claims.update({
            "device_id": ctx.device_id,
            "posture_score": ctx.posture_score,
            "location_risk": ctx.location_risk,
        })
        tok = self.issuer.issue(ctx.user_id, claims)
        # Tracking best-effort
        try:
            _, p, _ = tok.split(".")
            payload = json.loads(_b64url_decode(p))
            self.issuer.track(payload.get("jti", ""), int(payload.get("exp", 0)))
        except Exception:
            pass
        return tok

    def validate_token(self, token: str) -> Dict[str, Any]:
        return self.validator.validate(token)

    def authorize(self, ctx: ZTNAContext, action: str, resource_id: str = "",
                  resource_payload: Optional[Dict[str, Any]] = None) -> AccessDecision:
        decision = self.policy.evaluate(ctx, action, resource_id)
        if not decision.allow:
            return decision
        if resource_payload is not None:
            ok, attempt = self.bola.check(ctx, resource_payload)
            if not ok:
                return AccessDecision(False, f"BOLA: owner_id mismatch ({attempt})", "bola_attempt")
        return decision
