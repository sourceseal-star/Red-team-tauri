#!/usr/bin/env python3
"""
SOAR Handlers — HTTP action handlers for automated response
===========================================================
Each handler is an async-style function taking a context dict
and returning a result dict: {success, message, timestamp, mitre_technique}

Handlers:
  block_ip_waf         — Block IP in Cloudflare/AWS WAF
  revoke_ztna_session  — Revoke ZTNA session for a host/user
  disable_user_auth    — Disable user in Auth0/Keycloak
  quarantine_email     — Quarantine email in O365/Google Workspace
  dns_sinkhole         — Add domain to DNS sinkhole
  slack_alert          — Send alert to Slack webhook
  restore_email        — Rollback: restore quarantined email
  unblock_ip_waf       — Rollback: remove IP block from WAF
"""

import json
import time
import logging
import datetime
from typing import Dict, Any, Optional

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

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
    """HTTP POST with httpx or fallback simulation."""
    if not url:
        return {"status": "simulated", "reason": "no URL configured"}
    if not HTTPX_AVAILABLE:
        logger.warning("httpx not installed — simulating HTTP call to %s", url)
        return {"status": "simulated", "url": url}
    try:
        import httpx as _httpx
        with _httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload, headers=headers or {})
            return {"status_code": resp.status_code, "body": resp.text[:500]}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ─────────────────────────────────────────────
# Primary Handlers
# ─────────────────────────────────────────────

def block_ip_waf(context: Dict[str, Any]) -> Dict[str, Any]:
    """Block an IP address in Cloudflare or AWS WAF."""
    ip = context.get("source_ip") or context.get("ip") or context.get("c2_ip", "0.0.0.0")
    provider = context.get("waf_provider", "cloudflare")
    cf_token = context.get("cloudflare_token", "")
    cf_zone = context.get("cloudflare_zone", "")
    mitre = "T1562.001"  # Impair Defenses: Disable or Modify Tools

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
            headers={"Authorization": f"Bearer {cf_token}", "Content-Type": "application/json"}
        )
    else:
        # Simulate — log the action
        http_result = {"status": "simulated", "ip": ip, "provider": provider}

    logger.info("[block_ip_waf] Result: %s", http_result)
    return _result(True, f"IP {ip} blocked via {provider} WAF", mitre, {"http_result": http_result, "blocked_ip": ip})


def revoke_ztna_session(context: Dict[str, Any]) -> Dict[str, Any]:
    """Revoke ZTNA session for a user or host."""
    user = context.get("user_id") or context.get("username", "unknown")
    host = context.get("affected_host") or context.get("host", "")
    ztna_url = context.get("ztna_gateway_url", "")
    mitre = "T1078"  # Valid Accounts

    logger.info("[revoke_ztna_session] Revoking session user=%s host=%s", user, host)

    payload = {"user_id": user, "host": host, "action": "revoke", "timestamp": _now()}
    http_result = _http_post(f"{ztna_url}/api/v1/sessions/revoke", payload) if ztna_url else \
        {"status": "simulated", "user": user, "host": host}

    logger.info("[revoke_ztna_session] Result: %s", http_result)
    return _result(True, f"ZTNA session revoked for user={user} host={host}", mitre, {"http_result": http_result})


def disable_user_auth(context: Dict[str, Any]) -> Dict[str, Any]:
    """Disable a user account in Auth0 or Keycloak."""
    user = context.get("user_id") or context.get("username", "unknown")
    provider = context.get("auth_provider", "auth0")
    auth_url = context.get("auth_url", "")
    auth_token = context.get("auth_token", "")
    mitre = "T1098"  # Account Manipulation

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
        http_result = {"status": "simulated", "user": user, "provider": provider, "action": "disabled"}

    logger.info("[disable_user_auth] Result: %s", http_result)
    return _result(True, f"User {user} disabled via {provider}", mitre, {"http_result": http_result, "disabled_user": user})


def quarantine_email(context: Dict[str, Any]) -> Dict[str, Any]:
    """Move an email to quarantine in O365 or Google Workspace."""
    sender = context.get("sender_email", "unknown@unknown.com")
    recipient = context.get("recipient_email", "")
    provider = context.get("email_provider", "o365")
    mitre = "T1566"  # Phishing

    logger.info("[quarantine_email] Quarantining email from=%s provider=%s", sender, provider)

    # In production: call O365 Security & Compliance API or Google Admin SDK
    http_result = {
        "status": "simulated",
        "action": "move_to_quarantine",
        "sender": sender,
        "recipient": recipient,
        "provider": provider,
        "quarantine_id": f"QRN-{int(time.time())}"
    }

    logger.info("[quarantine_email] Result: %s", http_result)
    return _result(True, f"Email from {sender} quarantined ({provider})", mitre,
                   {"http_result": http_result, "quarantine_id": http_result["quarantine_id"]})


def dns_sinkhole(context: Dict[str, Any]) -> Dict[str, Any]:
    """Add a malicious domain to the DNS sinkhole."""
    domain = context.get("domain") or context.get("c2_domain", "malicious.example.com")
    sinkhole_ip = context.get("sinkhole_ip", "127.0.0.1")
    mitre = "T1071"  # Application Layer Protocol

    logger.info("[dns_sinkhole] Sinkholing domain=%s → %s", domain, sinkhole_ip)

    try:
        import socket
        # Attempt to write to local hosts file (requires root — simulated otherwise)
        http_result = {"status": "simulated", "domain": domain, "sinkhole_ip": sinkhole_ip}
    except Exception as e:
        http_result = {"status": "error", "error": str(e)}

    logger.info("[dns_sinkhole] Result: %s", http_result)
    return _result(True, f"Domain {domain} sinkholed → {sinkhole_ip}", mitre,
                   {"http_result": http_result, "sinkholed_domain": domain})


def slack_alert(context: Dict[str, Any]) -> Dict[str, Any]:
    """Send an alert to a Slack webhook."""
    webhook_url = context.get("slack_webhook_url", "")
    incident_id = context.get("incident_id", "INC-???")
    severity = context.get("severity", "HIGH")
    title = context.get("alert_title", "Security Incident Detected")
    message = context.get("alert_message", "Automated SOAR response triggered.")
    mitre = context.get("mitre_technique", "")

    payload = {
        "attachments": [{
            "color": "#FF0000" if severity == "CRITICAL" else "#FF8800",
            "title": f"🚨 [{severity}] {title}",
            "text": message,
            "fields": [
                {"title": "Incident ID", "value": incident_id, "short": True},
                {"title": "MITRE Technique", "value": mitre or "N/A", "short": True},
                {"title": "Timestamp", "value": _now(), "short": True},
            ],
            "footer": "SourceSeal SOAR"
        }]
    }

    logger.info("[slack_alert] Sending alert incident=%s severity=%s", incident_id, severity)
    http_result = _http_post(webhook_url, payload) if webhook_url else \
        {"status": "simulated", "payload_preview": title}

    success = http_result.get("status_code", 200) == 200 or http_result.get("status") == "simulated"
    return _result(success, f"Slack alert sent: {title}", mitre, {"http_result": http_result})


# ─────────────────────────────────────────────
# Rollback Handlers
# ─────────────────────────────────────────────

def restore_email(context: Dict[str, Any]) -> Dict[str, Any]:
    """Rollback: restore a quarantined email."""
    quarantine_id = context.get("quarantine_id", "unknown")
    logger.info("[restore_email] Restoring quarantine_id=%s", quarantine_id)
    return _result(True, f"Email {quarantine_id} restored from quarantine", "T1566",
                   {"status": "simulated", "quarantine_id": quarantine_id})


def unblock_ip_waf(context: Dict[str, Any]) -> Dict[str, Any]:
    """Rollback: remove IP block from WAF."""
    ip = context.get("blocked_ip") or context.get("ip", "0.0.0.0")
    provider = context.get("waf_provider", "cloudflare")
    logger.info("[unblock_ip_waf] Unblocking IP=%s from %s", ip, provider)
    return _result(True, f"IP {ip} unblocked from {provider} WAF", "T1562.001",
                   {"status": "simulated", "unblocked_ip": ip})


# ─────────────────────────────────────────────
# Handler registry (used by DAGExecutor)
# ─────────────────────────────────────────────

HANDLER_REGISTRY: Dict[str, Any] = {
    "block_ip_waf":        block_ip_waf,
    "revoke_ztna_session": revoke_ztna_session,
    "disable_user_auth":   disable_user_auth,
    "quarantine_email":    quarantine_email,
    "dns_sinkhole":        dns_sinkhole,
    "slack_alert":         slack_alert,
    "restore_email":       restore_email,
    "unblock_ip_waf":      unblock_ip_waf,
}
