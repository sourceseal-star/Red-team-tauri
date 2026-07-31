#!/usr/bin/env python3
"""
SOAR Engine — Security Orchestration, Automation, and Response
================================================================
Ejecuta playbooks de respuesta automática cuando el XDR genera incidentes.
Cada playbook define una secuencia de acciones con condiciones de ejecución.

Playbooks implementados:
  1. block_ip          — Bloquear IP en WAF/Firewall perimetral
  2. rate_limit        — Activar rate-limiting agresivo en API Gateway
  3. revoke_tokens     — Revocar sesiones JWT del usuario afectado
  4. isolate_endpoint  — Aislar dispositivo a nivel de ZTNA
  5. quarantine_device — Cuarentena de dispositivo (revocar + bloquear)
  6. kill_app_session  — Terminar sesión de app móvil
  7. force_reauth      — Forzar re-autenticación con MFA
  8. alert_soc         — Enviar alerta al equipo SOC (TheHive/Slack/Email)
"""
import json
import time
import hashlib
import datetime
import threading
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum


class ActionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlaybookAction:
    name: str
    handler: str          # nombre del handler registrado
    params: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 30
    continue_on_failure: bool = False


@dataclass
class Playbook:
    name: str
    trigger_severity: List[str]          # ["critical", "high"]
    trigger_actions: List[str]          # ["block_ip", "revoke_tokens"]
    steps: List[PlaybookAction]
    description: str = ""


@dataclass
class ExecutionResult:
    playbook: str
    action: str
    status: str
    timestamp: str
    detail: str = ""
    duration_ms: int = 0


class SOAREngine:
    """Motor de ejecución de playbooks de respuesta automática."""

    # Playbooks predefinidos
    BUILTIN_PLAYBOOKS = {
        "block_ip": Playbook(
            name="block_ip",
            trigger_severity=["critical", "high"],
            trigger_actions=["block_ip"],
            description="Bloquea IP en WAF/Firewall perimetral",
            steps=[
                PlaybookAction(name="lookup_ip_reputation", handler="check_ip_reputation"),
                PlaybookAction(name="add_to_blocklist", handler="waf_block_ip",
                               params={"duration": "24h"}, timeout_seconds=10),
                PlaybookAction(name="log_action", handler="audit_log"),
            ],
        ),
        "rate_limit": Playbook(
            name="rate_limit",
            trigger_severity=["high", "medium"],
            trigger_actions=["rate_limit"],
            description="Activa rate-limiting agresivo en API Gateway",
            steps=[
                PlaybookAction(name="set_rate_limit", handler="ztna_rate_limit",
                               params={"requests_per_minute": 10, "duration": "1h"}),
                PlaybookAction(name="log_action", handler="audit_log"),
            ],
        ),
        "revoke_tokens": Playbook(
            name="revoke_tokens",
            trigger_severity=["critical", "high"],
            trigger_actions=["revoke_tokens"],
            description="Revoca sesiones JWT activas del usuario afectado",
            steps=[
                PlaybookAction(name="find_active_tokens", handler="find_tokens"),
                PlaybookAction(name="revoke_all", handler="revoke_jwt",
                               continue_on_failure=True),
                PlaybookAction(name="log_action", handler="audit_log"),
            ],
        ),
        "isolate_endpoint": Playbook(
            name="isolate_endpoint",
            trigger_severity=["critical"],
            trigger_actions=["isolate_endpoint"],
            description="Aisla dispositivo a nivel de ZTNA — solo acceso a endpoints de cuarentena",
            steps=[
                PlaybookAction(name="quarantine_policy", handler="ztna_quarantine",
                               params={"allowed_endpoints": ["/api/health"]}),
                PlaybookAction(name="notify_user", handler="send_notification"),
                PlaybookAction(name="alert_soc", handler="soc_alert"),
                PlaybookAction(name="log_action", handler="audit_log"),
            ],
        ),
        "quarantine_device": Playbook(
            name="quarantine_device",
            trigger_severity=["critical"],
            trigger_actions=["quarantine_device"],
            description="Cuarentena completa: revocar tokens + bloquear IP + aislar",
            steps=[
                PlaybookAction(name="revoke_tokens", handler="revoke_jwt"),
                PlaybookAction(name="block_ip", handler="waf_block_ip",
                               params={"duration": "72h"}, continue_on_failure=True),
                PlaybookAction(name="isolate", handler="ztna_quarantine",
                               continue_on_failure=True),
                PlaybookAction(name="alert_soc", handler="soc_alert"),
                PlaybookAction(name="log_action", handler="audit_log"),
            ],
        ),
        "kill_app_session": Playbook(
            name="kill_app_session",
            trigger_severity=["critical", "high"],
            trigger_actions=["kill_app_session"],
            description="Termina sesión de app móvil vía push notification de revocación",
            steps=[
                PlaybookAction(name="send_kill_push", handler="push_kill_session"),
                PlaybookAction(name="revoke_jwt", handler="revoke_jwt",
                               continue_on_failure=True),
                PlaybookAction(name="log_action", handler="audit_log"),
            ],
        ),
        "force_reauth": Playbook(
            name="force_reauth",
            trigger_severity=["high", "medium"],
            trigger_actions=["force_reauth"],
            description="Fuerza re-autenticación con MFA en próximo request",
            steps=[
                PlaybookAction(name="flag_reauth", handler="ztna_flag_reauth",
                               params={"require_mfa": True}),
                PlaybookAction(name="log_action", handler="audit_log"),
            ],
        ),
        "alert_soc": Playbook(
            name="alert_soc",
            trigger_severity=["critical", "high", "medium"],
            trigger_actions=["alert_soc"],
            description="Envía alerta al equipo SOC",
            steps=[
                PlaybookAction(name="create_thehive_case", handler="thehive_create_case",
                               continue_on_failure=True),
                PlaybookAction(name="send_slack", handler="slack_notify",
                               continue_on_failure=True),
                PlaybookAction(name="log_action", handler="audit_log"),
            ],
        ),
    }

    def __init__(self):
        self.playbooks: Dict[str, Playbook] = dict(self.BUILTIN_PLAYBOOKS)
        self.handlers: Dict[str, Callable] = {}
        self.execution_log: List[ExecutionResult] = []
        self._lock = threading.Lock()
        self._register_default_handlers()

    def register_handler(self, name: str, fn: Callable) -> None:
        self.handlers[name] = fn

    def execute_incident(self, incident: Dict[str, Any]) -> List[ExecutionResult]:
        """Ejecuta playbooks basados en las acciones recomendadas de un incidente."""
        results: List[ExecutionResult] = []
        severity = incident.get("severity", "info")
        actions = incident.get("recommended_actions", [])

        for action in actions:
            if action in self.playbooks:
                pb = self.playbooks[action]
                if severity in pb.trigger_severity:
                    for step in pb.steps:
                        result = self._execute_step(pb.name, step, incident)
                        results.append(result)
                        if result.status == "failed" and not step.continue_on_failure:
                            break
        return results

    def _execute_step(self, playbook_name: str, step: PlaybookAction,
                      incident: Dict) -> ExecutionResult:
        handler = self.handlers.get(step.handler)
        if not handler:
            return ExecutionResult(
                playbook=playbook_name, action=step.name,
                status="skipped", timestamp=datetime.datetime.utcnow().isoformat() + "Z",
                detail=f"Handler '{step.handler}' no registrado — dry-run",
            )

        start = time.time()
        try:
            ctx = {**step.params, "incident": incident}
            detail = handler(ctx)
            elapsed = int((time.time() - start) * 1000)
            result = ExecutionResult(
                playbook=playbook_name, action=step.name,
                status="success", timestamp=datetime.datetime.utcnow().isoformat() + "Z",
                detail=str(detail or "OK"), duration_ms=elapsed,
            )
        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            result = ExecutionResult(
                playbook=playbook_name, action=step.name,
                status="failed", timestamp=datetime.datetime.utcnow().isoformat() + "Z",
                detail=str(e), duration_ms=elapsed,
            )

        with self._lock:
            self.execution_log.append(result)
        return result

    def _register_default_handlers(self):
        """Handlers por defecto — todos en dry-run (registran la acción)."""

        def _dry(ctx, msg="dry-run"):
            incident = ctx.get("incident", {})
            return f"{msg} | incident={incident.get('id','?')} src_ips={incident.get('src_ips',[])}"

        self.register_handler("check_ip_reputation", lambda ctx: _dry(ctx, "ip_reputation_check"))
        self.register_handler("waf_block_ip", lambda ctx: _dry(ctx, f"waf_block {ctx.get('duration','24h')}"))
        self.register_handler("ztna_rate_limit", lambda ctx: _dry(ctx, f"rate_limit {ctx.get('requests_per_minute',10)}/min"))
        self.register_handler("find_tokens", lambda ctx: _dry(ctx, "token_lookup"))
        self.register_handler("revoke_jwt", lambda ctx: _dry(ctx, "jwt_revoked"))
        self.register_handler("ztna_quarantine", lambda ctx: _dry(ctx, f"quarantine allowed={ctx.get('allowed_endpoints',[])}"))
        self.register_handler("send_notification", lambda ctx: _dry(ctx, "user_notified"))
        self.register_handler("soc_alert", lambda ctx: _dry(ctx, "soc_alerted"))
        self.register_handler("push_kill_session", lambda ctx: _dry(ctx, "kill_push_sent"))
        self.register_handler("ztna_flag_reauth", lambda ctx: _dry(ctx, f"reauth_flag mfa={ctx.get('require_mfa',True)}"))
        self.register_handler("thehive_create_case", lambda ctx: _dry(ctx, "thehive_case"))
        self.register_handler("slack_notify", lambda ctx: _dry(ctx, "slack_sent"))
        self.register_handler("audit_log", lambda ctx: _dry(ctx, "audit_logged"))

    def get_execution_summary(self) -> Dict:
        by_status = {}
        for r in self.execution_log:
            by_status[r.status] = by_status.get(r.status, 0) + 1
        return {
            "total_executions": len(self.execution_log),
            "by_status": by_status,
            "recent": [asdict(r) for r in self.execution_log[-20:]],
        }
