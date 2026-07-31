"""
Escenario: Página de Recuperación de Hash (Recovery Page)
----------------------------------------------------------
La página que listaste es el TARGET MÁS CRÍTICO del sistema.
Si se compromete, todas las biometrías son recuperables.

Vectoriza:
- Sin auth: ¿se puede listar hashes sin login?
- IDOR: cambiar un parámetro y ver hash de otro vendedor/cliente
- Fuerza bruta sobre códigos de recuperación
- CSRF: acciones que mutan estado sin token
- XSS en campos de búsqueda (si la página es web)
- Clickjacking: ¿X-Frame-Options / CSP frame-ancestors?
- Information disclosure: mensajes de error verbosos
- Backup: ¿se puede descargar masivamente?
- 2FA: acciones críticas sin segundo factor
- Audit log: ¿queda registro de quién recuperó qué?
"""
import os
import re
import time
import json
import pathlib
import hashlib
import secrets
import urllib.request
import urllib.error
from typing import List, Dict

DEFAULT_RECOVERY_URL = os.environ.get("RECOVERY_PAGE", "")


def _request(method, url, body=None, cookies=None, timeout=3):
    headers = {"User-Agent": "RedTeam-Agent/1.0"}
    if cookies: headers["Cookie"] = cookies
    data = json.dumps(body).encode() if body else None
    if data: headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"status": r.status, "headers": dict(r.headers),
                    "body": r.read().decode()[:3000]}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "headers": dict(e.headers or {}),
                "body": e.read().decode()[:1000]}
    except Exception as e:
        return {"status": 0, "error": str(e), "dry_run": True}


def run(target: str, backend: str, output_dir: str) -> List[Dict]:
    findings = []
    evidence = pathlib.Path(output_dir)
    evidence.mkdir(parents=True, exist_ok=True)

    if not DEFAULT_RECOVERY_URL:
        return [{
            "scenario": "recovery_page",
            "severity": "info",
            "title": "RECOVERY_PAGE no configurada",
            "description": "Configurar la variable de entorno RECOVERY_PAGE para auditar la página de recuperación.",
            "evidence_path": "",
            "remediation": "Set RECOVERY_PAGE=https://recuperacion.tu-dominio.com",
        }]

    log = {}

    # 1. Health check + headers de seguridad
    r = _request("GET", DEFAULT_RECOVERY_URL)
    log["health"] = r
    h = {k.lower(): v for k, v in (r.get("headers") or {}).items()}

    missing_headers = []
    for hdr in ["x-frame-options", "content-security-policy",
                "x-content-type-options", "strict-transport-security",
                "referrer-policy"]:
        if hdr not in h:
            missing_headers.append(hdr)
    if missing_headers:
        findings.append({
            "scenario": "recovery_page",
            "severity": "high",
            "title": f"Headers de seguridad ausentes en página de recuperación",
            "description": "Faltan: " + ", ".join(missing_headers),
            "evidence_path": str(evidence / "recovery-health.json"),
            "remediation": "Añadir headers: X-Frame-Options DENY, CSP frame-ancestors 'none', "
                           "HSTS 1 año, X-Content-Type-Options nosniff.",
        })

    # 2. Listar sin autenticación
    r = _request("GET", f"{DEFAULT_RECOVERY_URL.rstrip('/')}/api/hashes")
    log["no_auth_list"] = r
    if r.get("status") == 200:
        findings.append({
            "scenario": "recovery_page",
            "severity": "critical",
            "title": "Página de recuperación lista hashes SIN autenticación",
            "description": f"GET /api/hashes devolvió 200 con {len(r.get('body', ''))} bytes. "
                           "Cualquiera con la URL puede listar biometrías.",
            "evidence_path": str(evidence / "recovery-noauth.json"),
            "remediation": "AÑADIR AUTH inmediatamente. Requerir login + 2FA + audit log por acceso.",
        })

    # 3. IDOR en endpoint de hash individual
    test_id = "test-" + secrets.token_hex(4)
    r = _request("GET", f"{DEFAULT_RECOVERY_URL.rstrip('/')}/api/hashes/{test_id}")
    log["idor_test"] = r
    if r.get("status") not in (401, 403, 404):
        findings.append({
            "scenario": "recovery_page",
            "severity": "high",
            "title": "Endpoint de hash responde sin auth",
            "description": f"GET /api/hashes/{{id}} devolvió {r.get('status')}. "
                           "Si devuelve datos sin token válido, hay IDOR.",
            "evidence_path": str(evidence / "recovery-idor.json"),
            "remediation": "Validar sesión + ownership antes de servir datos de hash.",
        })

    # 4. CSRF: ¿se puede mutar sin token?
    r = _request("POST", f"{DEFAULT_RECOVERY_URL.rstrip('/')}/api/regenerate",
                 body={"hash_id": test_id, "action": "rotate"})
    log["csrf_test"] = r
    if r.get("status") in (200, 201, 202):
        findings.append({
            "scenario": "recovery_page",
            "severity": "critical",
            "title": "Mutación sin token CSRF / auth",
            "description": f"POST /api/regenerate devolvió {r.get('status')}. "
                           "Acciones de regeneración sin token = disaster.",
            "evidence_path": str(evidence / "recovery-csrf.json"),
            "remediation": "CSRF token + SameSite=Strict cookies + Origin check.",
        })

    # 5. Clickjacking
    if "x-frame-options" not in h and "frame-ancestors" not in h.get("content-security-policy", ""):
        findings.append({
            "scenario": "recovery_page",
            "severity": "medium",
            "title": "Vulnerable a clickjacking",
            "description": "Sin X-Frame-Options ni CSP frame-ancestors, la página puede ser embebida en iframes maliciosos.",
            "evidence_path": str(evidence / "recovery-clickjack.json"),
            "remediation": "X-Frame-Options: DENY o CSP: frame-ancestors 'none'.",
        })

    # 6. 2FA en acciones críticas
    r = _request("GET", f"{DEFAULT_RECOVERY_URL.rstrip('/')}/api/regenerate")
    log["2fa_check"] = {"status": r.get("status"), "body_excerpt": (r.get("body") or "")[:200]}
    body_lower = (r.get("body") or "").lower()
    has_2fa = any(s in body_lower for s in ["2fa", "totp", "mfa", "authenticator"])
    if not has_2fa and r.get("status") == 200:
        findings.append({
            "scenario": "recovery_page",
            "severity": "high",
            "title": "Sin evidencia de 2FA en la página de recuperación",
            "description": "Acciones críticas de rotación de hash sin segundo factor detectable.",
            "evidence_path": str(evidence / "recovery-2fa.json"),
            "remediation": "Implementar TOTP/WebAuthn obligatorio para cualquier acción de recuperación.",
        })

    (evidence / "recovery-all.json").write_text(json.dumps(log, indent=2, ensure_ascii=False))

    if not findings:
        findings.append({
            "scenario": "recovery_page",
            "severity": "info",
            "title": "Página de recuperación: checks básicos OK",
            "description": f"URL auditada: {DEFAULT_RECOVERY_URL}",
            "evidence_path": str(evidence / "recovery-all.json"),
            "remediation": "Mantener audit log, monitorear accesos anómalos, rotar sesiones.",
        })

    return findings
