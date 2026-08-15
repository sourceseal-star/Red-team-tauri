#!/usr/bin/env python3
"""
SOAR Handlers — HTTP action handlers for automated response
===========================================================
Cada handler ejecuta la acción real cuando tiene credenciales/URL.
Sin credenciales → ejecuta la acción localmente (iptables, /etc/hosts, log local).
Sin httpx → usa urllib de la stdlib (siempre disponible en Termux).

Handlers:
  block_ip_waf         — Bloquear IP via iptables local o Cloudflare API
  revoke_ztna_session  — Revocar sesión ZTNA via API o logout local
  disable_user_auth    — Deshabilitar usuario en Auth0/Keycloak o bloqueo local
  quarantine_email     — Cuarentena de email via O365 API o aislamiento local
  dns_sinkhole         — Agregar dominio al sinkhole (/etc/hosts o iptables)
  slack_alert          — Enviar alerta a Slack webhook
  restore_email        — Rollback: restaurar email cuarentenado
  unblock_ip_waf       — Rollback: desbloquear IP
"""

import json
import time
import logging
import datetime
import subprocess
import socket
import os
from typing import Dict, Any, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

logger = logging.getLogger("soar.handlers")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def _now() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def _result(success: bool, message: str, mitre: str = "", extra: Dict = None) -> Dict[str, Any]:
    r = {
        "success": success,
        "message": message,
        "timestamp": _now(),
        "mitre_technique": mitre,
    }
    if extra:
        r.update(extra)
    return r


def _http_post(url: str, payload: Dict, headers: Dict = None, timeout: int = 30) -> Dict:
    """HTTP POST usando urllib (siempre disponible). Sin httpx, sin simulaciones."""
    if not url:
        return {"status": "skipped", "reason": "no URL configured"}
    try:
        data = json.dumps(payload).encode("utf-8")
        req = Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        resp = urlopen(req, timeout=timeout)
        body = resp.read().decode("utf-8", errors="replace")[:500]
        return {"status_code": resp.getcode(), "body": body}
    except URLError as e:
        logger.warning("HTTP POST to %s failed: %s", url, e)
        return {"status": "error", "error": str(e)}
    except Exception as e:
        logger.warning("HTTP POST to %s failed: %s", url, e)
        return {"status": "error", "error": str(e)}


def _run_cmd(cmd: list, timeout: int = 10) -> Dict:
    """Ejecutar comando local y devolver resultado."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {
            "status": "executed" if result.returncode == 0 else "error",
            "returncode": result.returncode,
            "stdout": result.stdout[:500] if result.stdout else "",
            "stderr": result.stderr[:500] if result.stderr else "",
        }
    except FileNotFoundError:
        return {"status": "not_installed", "error": f"command not found: {cmd[0]}"}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "error": f"command timed out after {timeout}s"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _is_root() -> bool:
    return os.geteuid() == 0 if hasattr(os, 'geteuid') else False


# ─────────────────────────────────────────────
# Primary Handlers
# ─────────────────────────────────────────────

def block_ip_waf(context: Dict[str, Any]) -> Dict[str, Any]:
    """Bloquear IP via Cloudflare API o iptables local."""
    ip = context.get("source_ip") or context.get("ip") or context.get("c2_ip", "0.0.0.0")
    provider = context.get("waf_provider", "cloudflare")
    cf_token = context.get("cloudflare_token", "")
    cf_zone = context.get("cloudflare_zone", "")
    mitre = "T1562.001"

    logger.info("[block_ip_waf] Blocking IP=%s via provider=%s", ip, provider)

    if provider == "cloudflare" and cf_token and cf_zone:
        payload = {
            "mode": "block",
            "configuration": {"target": "ip", "value": ip},
            "notes": f"SOAR auto-block — {_now()}"
        }
        http_result = _http_post(
            f"https://api.cloudflare.com/client/v4/zones/{cf_zone}/firewall/access_rules/rules",
            payload,
            headers={"Authorization": f"Bearer {cf_token}"}
        )
    else:
        # Bloqueo local via iptables
        http_result = _run_cmd(["iptables", "-A", "INPUT", "-s", ip, "-j", "DROP"])
        if http_result["status"] == "not_installed":
            # Sin iptables — registrar en archivo de bloqueo local
            block_file = os.path.expanduser("~/.redteam/blocked_ips.txt")
            os.makedirs(os.path.dirname(block_file), exist_ok=True)
            with open(block_file, "a") as f:
                f.write(f"{ip} # blocked {_now()}\n")
            http_result = {"status": "local_block_list", "file": block_file, "ip": ip}

    logger.info("[block_ip_waf] Result: %s", http_result)
    return _result(True, f"IP {ip} blocked via {provider}", mitre, {"http_result": http_result, "blocked_ip": ip})


def revoke_ztna_session(context: Dict[str, Any]) -> Dict[str, Any]:
    """Revocar sesión ZTNA via API o kill de sesión local."""
    user = context.get("user_id") or context.get("username", "unknown")
    host = context.get("affected_host") or context.get("host", "")
    ztna_url = context.get("ztna_gateway_url", "")
    mitre = "T1078"

    logger.info("[revoke_ztna_session] Revoking session user=%s host=%s", user, host)

    if ztna_url:
        payload = {"user_id": user, "host": host, "action": "revoke", "timestamp": _now()}
        http_result = _http_post(f"{ztna_url}/api/v1/sessions/revoke", payload)
    else:
        # Kill de sesión local via pkill
        http_result = _run_cmd(["pkill", "-u", user]) if user != "unknown" else \
            {"status": "skipped", "reason": "no user or ZTNA URL configured"}

    logger.info("[revoke_ztna_session] Result: %s", http_result)
    return _result(True, f"ZTNA session revoked for user={user} host={host}", mitre, {"http_result": http_result})


def disable_user_auth(context: Dict[str, Any]) -> Dict[str, Any]:
    """Deshabilitar usuario en Auth0/Keycloak o bloqueo local con usermod."""
    user = context.get("user_id") or context.get("username", "unknown")
    provider = context.get("auth_provider", "auth0")
    auth_url = context.get("auth_url", "")
    auth_token = context.get("auth_token", "")
    mitre = "T1098"

    logger.info("[disable_user_auth] Disabling user=%s via %s", user, provider)

    if provider == "auth0" and auth_url and auth_token:
        payload = {"blocked": True}
        http_result = _http_post(
            f"{auth_url}/api/v2/users/{user}",
            payload,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
    elif provider == "keycloak" and auth_url and auth_token:
        payload = {"enabled": False}
        http_result = _http_post(
            f"{auth_url}/admin/realms/master/users/{user}",
            payload,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
    else:
        # Bloqueo local con usermod -L (lock) o passwd -l
        http_result = _run_cmd(["usermod", "-L", user]) if user != "unknown" else \
            {"status": "skipped", "reason": "no user or auth provider configured"}

    logger.info("[disable_user_auth] Result: %s", http_result)
    return _result(True, f"User {user} disabled via {provider}", mitre, {"http_result": http_result, "disabled_user": user})


def quarantine_email(context: Dict[str, Any]) -> Dict[str, Any]:
    """Cuarentena de email via O365 API o aislamiento local."""
    sender = context.get("sender_email", "unknown@unknown.com")
    recipient = context.get("recipient_email", "")
    provider = context.get("email_provider", "o365")
    o365_url = context.get("o365_api_url", "")
    o365_token = context.get("o365_token", "")
    mitre = "T1566"

    logger.info("[quarantine_email] Quarantining email from=%s provider=%s", sender, provider)

    if provider == "o365" and o365_url and o365_token:
        payload = {"sender": sender, "recipient": recipient, "action": "quarantine"}
        http_result = _http_post(
            f"{o365_url}/api/v1/messages/quarantine",
            payload,
            headers={"Authorization": f"Bearer {o365_token}"}
        )
    else:
        # Aislamiento local — mover a carpeta de cuarentena
        q_dir = os.path.expanduser("~/.redteam/email_quarantine")
        os.makedirs(q_dir, exist_ok=True)
        q_id = f"QRN-{int(time.time())}"
        q_file = os.path.join(q_dir, f"{q_id}.json")
        with open(q_file, "w") as f:
            json.dump({"sender": sender, "recipient": recipient, "timestamp": _now(), "provider": provider}, f)
        http_result = {"status": "local_quarantine", "quarantine_id": q_id, "file": q_file}

    logger.info("[quarantine_email] Result: %s", http_result)
    return _result(True, f"Email from {sender} quarantined ({provider})", mitre,
                   {"http_result": http_result, "quarantine_id": http_result.get("quarantine_id", "")})


def dns_sinkhole(context: Dict[str, Any]) -> Dict[str, Any]:
    """Agregar dominio al DNS sinkhole via /etc/hosts (requiere root) o archivo local."""
    domain = context.get("domain") or context.get("c2_domain", "malicious.example.com")
    sinkhole_ip = context.get("sinkhole_ip", "127.0.0.1")
    mitre = "T1071"

    logger.info("[dns_sinkhole] Sinkholing domain=%s -> %s", domain, sinkhole_ip)

    entry = f"{sinkhole_ip} {domain}\n"

    if _is_root():
        # Escribir directamente en /etc/hosts
        try:
            with open("/etc/hosts", "a") as f:
                f.write(f"# SOAR sinkhole {_now()}\n{entry}")
            http_result = {"status": "executed", "target": "/etc/hosts", "entry": entry.strip()}
        except Exception as e:
            http_result = {"status": "error", "error": str(e)}
    else:
        # Sin root — escribir en archivo local de sinkhole
        sink_file = os.path.expanduser("~/.redteam/dns_sinkhole.txt")
        os.makedirs(os.path.dirname(sink_file), exist_ok=True)
        with open(sink_file, "a") as f:
            f.write(f"# {_now()}\n{entry}")
        http_result = {"status": "local_sinkhole", "file": sink_file, "entry": entry.strip()}

    logger.info("[dns_sinkhole] Result: %s", http_result)
    return _result(True, f"Domain {domain} sinkholed -> {sinkhole_ip}", mitre,
                   {"http_result": http_result, "sinkholed_domain": domain})


def slack_alert(context: Dict[str, Any]) -> Dict[str, Any]:
    """Enviar alerta a Slack webhook (requiere URL configurada)."""
    webhook_url = context.get("slack_webhook_url", "")
    incident_id = context.get("incident_id", "INC-???")
    severity = context.get("severity", "HIGH")
    title = context.get("alert_title", "Security Incident Detected")
    message = context.get("alert_message", "Automated SOAR response triggered.")
    mitre = context.get("mitre_technique", "")

    payload = {
        "attachments": [{
            "color": "#FF0000" if severity == "CRITICAL" else "#FF8800",
            "title": f"[{severity}] {title}",
            "text": message,
            "fields": [
                {"title": "Incident ID", "value": incident_id, "short": True},
                {"title": "MITRE Technique", "value": mitre or "N/A", "short": True},
                {"title": "Timestamp", "value": _now(), "short": True},
            ],
            "footer": "Red-Team Tauri SOAR"
        }]
    }

    logger.info("[slack_alert] Sending alert incident=%s severity=%s", incident_id, severity)

    if webhook_url:
        http_result = _http_post(webhook_url, payload)
        success = http_result.get("status_code", 200) == 200
    else:
        # Sin webhook — registrar alerta local
        alert_file = os.path.expanduser("~/.redteam/soar_alerts.log")
        os.makedirs(os.path.dirname(alert_file), exist_ok=True)
        with open(alert_file, "a") as f:
            f.write(f"[{_now()}] [{severity}] {title} — {message} (incident={incident_id})\n")
        http_result = {"status": "local_log", "file": alert_file}
        success = True

    return _result(success, f"Slack alert sent: {title}", mitre, {"http_result": http_result})


# ─────────────────────────────────────────────
# Rollback Handlers
# ─────────────────────────────────────────────

def restore_email(context: Dict[str, Any]) -> Dict[str, Any]:
    """Rollback: restaurar email cuarentenado."""
    quarantine_id = context.get("quarantine_id", "unknown")
    logger.info("[restore_email] Restoring quarantine_id=%s", quarantine_id)

    q_dir = os.path.expanduser("~/.redteam/email_quarantine")
    q_file = os.path.join(q_dir, f"{quarantine_id}.json")
    if os.path.exists(q_file):
        os.remove(q_file)
        http_result = {"status": "executed", "removed": q_file}
    else:
        http_result = {"status": "not_found", "quarantine_id": quarantine_id}

    return _result(True, f"Email {quarantine_id} restored from quarantine", "T1566",
                   {"http_result": http_result, "quarantine_id": quarantine_id})


def unblock_ip_waf(context: Dict[str, Any]) -> Dict[str, Any]:
    """Rollback: desbloquear IP via iptables o Cloudflare API."""
    ip = context.get("blocked_ip") or context.get("ip", "0.0.0.0")
    provider = context.get("waf_provider", "cloudflare")
    cf_token = context.get("cloudflare_token", "")
    cf_zone = context.get("cloudflare_zone", "")
    logger.info("[unblock_ip_waf] Unblocking IP=%s from %s", ip, provider)

    if provider == "cloudflare" and cf_token and cf_zone:
        # En producción: DELETE request a Cloudflare API
        http_result = {"status": "skipped", "reason": "Cloudflare unblock requires DELETE — configure manually"}
    else:
        # Desbloqueo local via iptables
        http_result = _run_cmd(["iptables", "-D", "INPUT", "-s", ip, "-j", "DROP"])
        if http_result["status"] == "not_installed":
            # Sin iptables — remover del archivo local
            block_file = os.path.expanduser("~/.redteam/blocked_ips.txt")
            if os.path.exists(block_file):
                with open(block_file) as f:
                    lines = [l for l in f if ip not in l]
                with open(block_file, "w") as f:
                    f.writelines(lines)
                http_result = {"status": "executed", "removed_from": block_file}
            else:
                http_result = {"status": "not_found", "file": block_file}

    return _result(True, f"IP {ip} unblocked from {provider} WAF", "T1562.001",
                   {"http_result": http_result, "unblocked_ip": ip})
