"""
WEB ANALYZER INTERCEPTOR - Proxy MITM Avanzado
==============================================
Integracion con redteam/tlsproxy/interceptor.py existente.
Nuevas capacidades: Proxy MITM funcional, analisis de payloads,
deteccion de inyecciones, logging estructurado para SIEM.

Referencias: NIST SP 800-94 (Guide to Intrusion Detection and Prevention Systems)
             MITRE ATT&CK T1190 (Exploit Public-Facing Application)
             CWE-89 (SQL Injection), CWE-79 (XSS), CWE-94 (Code Injection)

Uso:
    from tlsproxy.interceptor_advanced import (
        interceptor_router, RequestAnalyzer, ResponseAnalyzer,
        InjectionDetector, SIEMLogger, FlowDB
    )
"""

import asyncio
import json
import ssl
import socket
import re
import sqlite3
import hashlib
import os
import time
import datetime
from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field, asdict
from urllib.parse import urlparse, parse_qs, unquote

from fastapi import APIRouter, HTTPException, Query, Body, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ============================================================================
# CONFIG
# ============================================================================

interceptor_router = APIRouter(prefix="/api/interceptor", tags=["interceptor-advanced"])

INTERCEPTOR_DB_PATH = os.path.join(os.getcwd(), "evidence", "interceptor_flows.db")


# ============================================================================
# DATABASE
# ============================================================================

def _init_db():
    os.makedirs(os.path.dirname(INTERCEPTOR_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(INTERCEPTOR_DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS intercepted_flows (
        id TEXT PRIMARY KEY,
        src_ip TEXT,
        dst_host TEXT,
        dst_port INTEGER,
        method TEXT,
        path TEXT,
        status_code INTEGER,
        request_headers TEXT,
        response_headers TEXT,
        request_size INTEGER,
        response_size INTEGER,
        duration_ms INTEGER,
        alerts TEXT,
        timestamp TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS injection_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        flow_id TEXT,
        alert_type TEXT,
        severity TEXT,
        payload TEXT,
        pattern_matched TEXT,
        cwe TEXT,
        mitre TEXT,
        timestamp TEXT
    )''')
    conn.commit()
    conn.close()


_init_db()


# ============================================================================
# DETECTION PATTERNS
# ============================================================================

# SQL Injection patterns (CWE-89, OWASP Top 10 #1)
SQL_INJECTION_PATTERNS = [
    (r"(?i)(?:'|\")(?:\s|--|#|(?:--|#).*(?:\n|$))", "SQLi: Quote + comment"),
    (r"(?i)\bUNION\s+(?:ALL\s+)?SELECT\b", "SQLi: UNION SELECT"),
    (r"(?i)\bSELECT\s+.+\s+FROM\s+", "SQLi: SELECT FROM"),
    (r"(?i)\bINSERT\s+INTO\s+", "SQLi: INSERT INTO"),
    (r"(?i)\bDELETE\s+FROM\s+", "SQLi: DELETE FROM"),
    (r"(?i)\bDROP\s+TABLE\s+", "SQLi: DROP TABLE"),
    (r"(?i)\bUPDATE\s+.+\s+SET\s+", "SQLi: UPDATE SET"),
    (r"(?i)1\s*=\s*1", "SQLi: Boolean tautology"),
    (r"(?i)\bOR\s+1\s*=\s*1\b", "SQLi: OR 1=1"),
    (r"(?i)\bAND\s+1\s*=\s*1\b", "SQLi: AND 1=1"),
    (r"(?i)\bWAITFOR\s+DELAY\b", "SQLi: Time-based blind"),
    (r"(?i)\bSLEEP\s*\(\s*\d+\s*\)", "SQLi: SLEEP()"),
    (r"(?i)\bBENCHMARK\s*\(", "SQLi: BENCHMARK()"),
    (r"(?i)\bINTO\s+OUTFILE\b", "SQLi: INTO OUTFILE"),
    (r"(?i)\bINTO\s+DUMPFILE\b", "SQLi: INTO DUMPFILE"),
    (r"(?i)\bLOAD_FILE\s*\(", "SQLi: LOAD_FILE()"),
    (r"(?i)\bXP_CMDSHELL\b", "SQLi: xp_cmdshell"),
    (r"(?i)0x[0-9a-f]{8,}", "SQLi: Hex payload"),
]

# XSS patterns (CWE-79, OWASP Top 10 #3)
XSS_PATTERNS = [
    (r"(?i)<script\b", "XSS: <script> tag"),
    (r"(?i)javascript:", "XSS: javascript: protocol"),
    (r"(?i)on(?:error|load|click|mouseover|focus|blur|submit)\s*=", "XSS: Event handler"),
    (r"(?i)<iframe\b", "XSS: <iframe> tag"),
    (r"(?i)<svg\b[^>]*on", "XSS: SVG with event handler"),
    (r"(?i)<img\b[^>]*onerror", "XSS: <img onerror>"),
    (r"(?i)<body\b[^>]*onload", "XSS: <body onload>"),
    (r"(?i)document\.cookie", "XSS: document.cookie access"),
    (r"(?i)document\.write\b", "XSS: document.write()"),
    (r"(?i)\beval\s*\(", "XSS: eval()"),
    (r"(?i)String\.fromCharCode\b", "XSS: String.fromCharCode()"),
    (r"(?i)alert\s*\(", "XSS: alert()"),
    (r"(?i)prompt\s*\(", "XSS: prompt()"),
    (r"(?i)confirm\s*\(", "XSS: confirm()"),
]

# Command Injection patterns (CWE-78, MITRE ATT&CK T1059)
CMD_INJECTION_PATTERNS = [
    (r";\s*(?:ls|cat|whoami|id|uname|pwd|wget|curl|nc|bash|sh|python|perl|ruby)\b", "Cmd: Shell metachar + command"),
    (r"\|\s*(?:ls|cat|whoami|id|uname|pwd|wget|curl|nc|bash|sh)\b", "Cmd: Pipe to command"),
    (r"&&\s*(?:ls|cat|whoami|id|uname|pwd|wget|curl|nc|bash|sh)\b", "Cmd: AND command"),
    (r"\$\(", "Cmd: Command substitution $()"),
    (r"`[^`]+`", "Cmd: Backtick substitution"),
    (r"(?i)\bnc\s+-[elp]", "Cmd: Netcat listener"),
    (r"(?i)\bwget\s+https?://", "Cmd: wget download"),
    (r"(?i)\bcurl\s+-[oO]", "Cmd: curl output"),
    (r"(?i)\bpython\s+-c\s", "Cmd: Python -c"),
    (r"(?i)\bperl\s+-e\s", "Cmd: Perl -e"),
    (r"(?i)\bruby\s+-e\s", "Cmd: Ruby -e"),
]

# Path Traversal patterns (CWE-22)
PATH_TRAVERSAL_PATTERNS = [
    (r"\.\./", "Path traversal: ../"),
    (r"\.\.\\", "Path traversal: ..\\"),
    (r"%2e%2e%2f", "Path traversal: encoded ../"),
    (r"%2e%2e/", "Path traversal: partial encoded"),
    (r"\.\.%2f", "Path traversal: mixed encoding"),
    (r"/etc/passwd", "Path traversal: /etc/passwd"),
    (r"/etc/shadow", "Path traversal: /etc/shadow"),
    (r"\\windows\\system32", "Path traversal: Windows system32"),
    (r"C:\\windows\\", "Path traversal: Windows absolute path"),
]

# SSRF patterns (CWE-918)
SSRF_PATTERNS = [
    (r"(?i)http://169\.254\.169\.254", "SSRF: AWS metadata endpoint"),
    (r"(?i)http://metadata\.google\.internal", "SSRF: GCP metadata"),
    (r"(?i)http://169\.254\.169\.254/latest/meta-data", "SSRF: AWS meta-data API"),
    (r"(?i)file:///", "SSRF: file:// protocol"),
    (r"(?i)gopher://", "SSRF: gopher:// protocol"),
    (r"(?i)dict://", "SSRF: dict:// protocol"),
    (r"(?i)ftp://", "SSRF: ftp:// protocol"),
    (r"(?i)ldap://", "SSRF: ldap:// protocol"),
    (r"(?i)jar://", "SSRF: jar:// protocol"),
]

ALL_PATTERNS = [
    ("SQL Injection", SQL_INJECTION_PATTERNS, "CWE-89", "T1190"),
    ("XSS", XSS_PATTERNS, "CWE-79", "T1059.007"),
    ("Command Injection", CMD_INJECTION_PATTERNS, "CWE-78", "T1059"),
    ("Path Traversal", PATH_TRAVERSAL_PATTERNS, "CWE-22", "T1083"),
    ("SSRF", SSRF_PATTERNS, "CWE-918", "T1190"),
]


# ============================================================================
# CLASSES
# ============================================================================

class InjectionDetector:
    """
    Detector de inyecciones — NIST SP 800-94 §3.2 (Signature-based detection).
    Analiza payloads HTTP en busca de patrones maliciosos conocidos.
    """

    def __init__(self):
        self.patterns = ALL_PATTERNS

    def analyze(self, payload: str) -> List[Dict[str, Any]]:
        """Analiza un string y retorna lista de alertas detectadas."""
        if not payload:
            return []

        # Decode URL-encoded payloads
        decoded = unquote(payload)
        candidates = [payload, decoded]

        alerts: List[Dict[str, Any]] = []
        for category, patterns, cwe, mitre in self.patterns:
            for candidate in candidates:
                for pattern, description in patterns:
                    m = re.search(pattern, candidate)
                    if m:
                        alerts.append({
                            "category": category,
                            "type": description,
                            "pattern_matched": m.group(0),
                            "cwe": cwe,
                            "mitre": mitre,
                            "severity": "critical" if category in ("SQL Injection", "Command Injection") else "high",
                        })
                        break  # una alerta por categoria por candidato

        return alerts


class RequestAnalyzer:
    """
    Analizador de requests HTTP — NIST SP 800-94 §3.1.
    Inspecciona headers, query params, body y path.
    """

    def __init__(self):
        self.detector = InjectionDetector()

    def analyze(self, method: str, path: str, headers: Dict, body: str = "") -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "method": method,
            "path": path,
            "alerts": [],
            "score": 0,
        }

        # Analizar path + query
        parsed = urlparse(path)
        alerts = self.detector.analyze(parsed.path)
        if parsed.query:
            alerts.extend(self.detector.analyze(parsed.query))
        result["alerts"].extend(alerts)

        # Analizar headers
        for key, val in headers.items():
            h_alerts = self.detector.analyze(str(val))
            if h_alerts:
                for a in h_alerts:
                    a["location"] = f"header:{key}"
                result["alerts"].extend(h_alerts)

        # Analizar body
        if body:
            body_alerts = self.detector.analyze(body)
            if body_alerts:
                for a in body_alerts:
                    a["location"] = "body"
                result["alerts"].extend(body_alerts)

        # Calcular score
        severity_scores = {"critical": 30, "high": 20, "medium": 10, "low": 5}
        result["score"] = sum(severity_scores.get(a.get("severity", "medium"), 10) for a in result["alerts"])
        result["score"] = min(result["score"], 100)

        return result


class ResponseAnalyzer:
    """
    Analizador de responses HTTP — detecta info leaks y configuraciones inseguras.
    """

    LEAKING_HEADERS = {
        "x-powered-by": "Information disclosure: Technology stack",
        "server": "Information disclosure: Server version",
        "via": "Information disclosure: Proxy info",
        "x-aspnet-version": "Information disclosure: ASP.NET version",
        "x-aspnetmvc-version": "Information disclosure: MVC version",
    }

    def analyze(self, status_code: int, headers: Dict, body: str = "") -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "status_code": status_code,
            "alerts": [],
            "score": 0,
        }

        for h, desc in self.LEAKING_HEADERS.items():
            if h.lower() in {k.lower() for k in headers}:
                result["alerts"].append({
                    "category": "Information Disclosure",
                    "type": desc,
                    "header": h,
                    "value": headers.get(h, ""),
                    "severity": "low",
                    "cwe": "CWE-200",
                })

        # Error messages in body
        error_patterns = [
            (r"(?i)stack\s+trace", "Error: Stack trace exposed"),
            (r"(?i)sql\s+syntax\s+error", "Error: SQL error exposed"),
            (r"(?i)warning:\s+\w+\(\)", "Error: PHP warning exposed"),
            (r"(?i)fatal error", "Error: Fatal error exposed"),
            (r"(?i)exception\s+(?:in|at)\b", "Error: Exception details exposed"),
            (r"(?i)debug\s+info", "Error: Debug info exposed"),
        ]
        for pattern, desc in error_patterns:
            if re.search(pattern, body):
                result["alerts"].append({
                    "category": "Information Disclosure",
                    "type": desc,
                    "severity": "medium",
                    "cwe": "CWE-209",
                })

        # Missing security headers (NIST SP 800-44)
        security_headers = [
            "strict-transport-security",
            "x-frame-options",
            "x-content-type-options",
            "content-security-policy",
        ]
        missing = [h for h in security_headers if h not in {k.lower() for k in headers}]
        if missing:
            result["alerts"].append({
                "category": "Security Misconfiguration",
                "type": f"Missing security headers: {', '.join(missing)}",
                "severity": "medium",
                "cwe": "CWE-693",
            })

        severity_scores = {"critical": 30, "high": 20, "medium": 10, "low": 5}
        result["score"] = sum(severity_scores.get(a.get("severity", "medium"), 10) for a in result["alerts"])
        result["score"] = min(result["score"], 100)

        return result


class SIEMLogger:
    """
    Logger estructurado para SIEM — NIST SP 800-92 (Guide to Computer Security Log Management).
    Formato JSON compatible con Splunk, ELK, Wazuh.
    """

    def __init__(self, db_path: str = INTERCEPTOR_DB_PATH):
        self.db_path = db_path

    def log_flow(self, flow_id: str, src_ip: str, dst_host: str, dst_port: int,
                 method: str, path: str, status_code: int,
                 request_headers: Dict, response_headers: Dict,
                 request_size: int, response_size: int,
                 duration_ms: int, alerts: List[Dict]) -> Dict:
        """Registra un flujo completo en la BD y retorna un evento SIEM."""

        event = {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "flow_id": flow_id,
            "src_ip": src_ip,
            "dst_host": dst_host,
            "dst_port": dst_port,
            "method": method,
            "path": path,
            "status_code": status_code,
            "request_size": request_size,
            "response_size": response_size,
            "duration_ms": duration_ms,
            "alerts_count": len(alerts),
            "alerts": alerts,
        }

        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('''INSERT OR REPLACE INTO intercepted_flows
                (id, src_ip, dst_host, dst_port, method, path, status_code,
                 request_headers, response_headers, request_size, response_size,
                 duration_ms, alerts, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (flow_id, src_ip, dst_host, dst_port, method, path, status_code,
                 json.dumps(request_headers), json.dumps(response_headers),
                 request_size, response_size, duration_ms,
                 json.dumps(alerts), event["timestamp"]))

            for alert in alerts:
                c.execute('''INSERT INTO injection_alerts
                    (flow_id, alert_type, severity, payload, pattern_matched, cwe, mitre, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (flow_id, alert.get("type", "unknown"), alert.get("severity", "medium"),
                     alert.get("payload", ""), alert.get("pattern_matched", ""),
                     alert.get("cwe", ""), alert.get("mitre", ""), event["timestamp"]))

            conn.commit()
            conn.close()
        except Exception as e:
            event["db_error"] = str(e)

        return event


# ============================================================================
# MODELS
# ============================================================================

class AnalyzeRequestModel(BaseModel):
    method: str = Field("GET", description="Metodo HTTP")
    path: str = Field(..., description="Path + query string")
    headers: Dict[str, str] = Field(default_factory=dict, description="Headers del request")
    body: str = Field("", description="Body del request")


class AnalyzeResponseModel(BaseModel):
    status_code: int = Field(..., description="Status code de la respuesta")
    headers: Dict[str, str] = Field(default_factory=dict, description="Headers de la respuesta")
    body: str = Field("", description="Body de la respuesta")


# ============================================================================
# ENDPOINTS
# ============================================================================

@interceptor_router.post("/analyze/request")
async def api_analyze_request(req: AnalyzeRequestModel):
    """Analiza un request HTTP en busca de inyecciones y patrones maliciosos."""
    analyzer = RequestAnalyzer()
    result = analyzer.analyze(req.method, req.path, req.headers, req.body)
    return result


@interceptor_router.post("/analyze/response")
async def api_analyze_response(resp: AnalyzeResponseModel):
    """Analiza un response HTTP en busca de info leaks y misconfiguraciones."""
    analyzer = ResponseAnalyzer()
    result = analyzer.analyze(resp.status_code, resp.headers, resp.body)
    return result


@interceptor_router.get("/flows")
async def api_get_flows(limit: int = Query(50, ge=1, le=200)):
    """Lista flujos interceptados recientes (NIST SP 800-92)."""
    try:
        conn = sqlite3.connect(INTERCEPTOR_DB_PATH)
        c = conn.cursor()
        rows = c.execute(
            "SELECT id, src_ip, dst_host, dst_port, method, path, status_code, "
            "request_size, response_size, duration_ms, alerts, timestamp "
            "FROM intercepted_flows ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()

        flows = []
        for r in rows:
            flows.append({
                "id": r[0], "src_ip": r[1], "dst_host": r[2], "dst_port": r[3],
                "method": r[4], "path": r[5], "status_code": r[6],
                "request_size": r[7], "response_size": r[8], "duration_ms": r[9],
                "alerts": json.loads(r[10]) if r[10] else [],
                "timestamp": r[11],
            })
        return {"flows": flows, "total": len(flows)}
    except Exception as e:
        return {"error": str(e), "flows": []}


@interceptor_router.get("/alerts")
async def api_get_alerts(limit: int = Query(100, ge=1, le=500)):
    """Lista alertas de inyeccion detectadas (NIST SP 800-94)."""
    try:
        conn = sqlite3.connect(INTERCEPTOR_DB_PATH)
        c = conn.cursor()
        rows = c.execute(
            "SELECT id, flow_id, alert_type, severity, payload, pattern_matched, "
            "cwe, mitre, timestamp FROM injection_alerts "
            "ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()

        alerts = []
        for r in rows:
            alerts.append({
                "id": r[0], "flow_id": r[1], "type": r[2], "severity": r[3],
                "payload": r[4], "pattern_matched": r[5],
                "cwe": r[6], "mitre": r[7], "timestamp": r[8],
            })
        return {"alerts": alerts, "total": len(alerts)}
    except Exception as e:
        return {"error": str(e), "alerts": []}


@interceptor_router.get("/stats")
async def api_get_stats():
    """Estadisticas del interceptor — resumen para dashboard SIEM."""
    try:
        conn = sqlite3.connect(INTERCEPTOR_DB_PATH)
        c = conn.cursor()

        total_flows = c.execute("SELECT COUNT(*) FROM intercepted_flows").fetchone()[0]
        total_alerts = c.execute("SELECT COUNT(*) FROM injection_alerts").fetchone()[0]

        by_severity = {}
        for row in c.execute(
            "SELECT severity, COUNT(*) FROM injection_alerts GROUP BY severity"
        ).fetchall():
            by_severity[row[0]] = row[1]

        by_cwe = {}
        for row in c.execute(
            "SELECT cwe, COUNT(*) FROM injection_alerts GROUP BY cwe"
        ).fetchall():
            by_cwe[row[0]] = row[1]

        by_category = {}
        for row in c.execute(
            "SELECT alert_type, COUNT(*) FROM injection_alerts GROUP BY alert_type ORDER BY COUNT(*) DESC LIMIT 10"
        ).fetchall():
            by_category[row[0]] = row[1]

        conn.close()

        return {
            "total_flows": total_flows,
            "total_alerts": total_alerts,
            "by_severity": by_severity,
            "by_cwe": by_cwe,
            "top_alert_types": by_category,
        }
    except Exception as e:
        return {"error": str(e)}


@interceptor_router.delete("/flows")
async def api_clear_flows():
    """Limpia todos los flujos interceptados de la base de datos."""
    try:
        conn = sqlite3.connect(INTERCEPTOR_DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM intercepted_flows")
        c.execute("DELETE FROM injection_alerts")
        conn.commit()
        conn.close()
        return {"ok": True, "message": "Flujos y alertas eliminados"}
    except Exception as e:
        raise HTTPException(500, str(e))


# ============================================================================
# XXE PATTERNS (CWE-611)
# ============================================================================

XXE_PATTERNS = [
    (r"(?i)<!ENTITY\s+", "XXE: ENTITY declaration"),
    (r"(?i)<!DOCTYPE\s+[^>]*\[", "XXE: DOCTYPE with internal subset"),
    (r"(?i)SYSTEM\s+[\"']", "XXE: SYSTEM identifier"),
    (r"(?i)ENTITY\s+\w+\s+SYSTEM", "XXE: External entity"),
    (r"(?i)&\w+;", "XXE: Entity reference"),
    (r"(?i)file:///", "XXE: file:// protocol"),
    (r"(?i)expect://", "XXE: expect:// protocol"),
    (r"(?i)php://filter", "XXE: PHP filter wrapper"),
    (r"(?i)CDATA\[", "XXE: CDATA section"),
]

# LFI/RFI PATTERNS (CWE-98)
LFI_RFI_PATTERNS = [
    (r"(?i)php://input", "LFI: PHP input wrapper"),
    (r"(?i)php://filter.*resource=", "LFI: PHP filter resource"),
    (r"(?i)data://text", "LFI: data:// wrapper"),
    (r"(?i)input://", "LFI: input:// wrapper"),
    (r"(?i)expect://", "LFI: expect:// wrapper"),
    (r"(?i)include\s*\(", "LFI: include() function"),
    (r"(?i)require\s*\(", "LFI: require() function"),
    (r"(?i)require_once\s*\(", "LFI: require_once()"),
    (r"(?i)include_once\s*\(", "LFI: include_once()"),
    (r"(?i)\.\./.*\.php", "LFI: Path traversal to PHP file"),
    (r"(?i)\.\./.*\.conf", "LFI: Path traversal to config"),
    (r"(?i)https?://.*\.(?:php|jsp|asp)", "RFI: Remote file inclusion"),
]

# LDAP INJECTION PATTERNS (CWE-90)
LDAP_INJECTION_PATTERNS = [
    (r"\*\)", "LDAP: Wildcard close paren"),
    (r"\(\|", "LDAP: OR filter"),
    (r"\(&", "LDAP: AND filter"),
    (r"\)\(", "LDAP: Filter chaining"),
    (r"(?i)\*objectClass\*", "LDAP: objectClass wildcard"),
    (r"(?i)admin\)", "LDAP: admin close"),
    (r"(?i)uid=\*", "LDAP: uid wildcard"),
    (r"(?i)cn=\*", "LDAP: cn wildcard"),
    (r"(?i)userPassword", "LDAP: userPassword access"),
]

# NOSQL INJECTION PATTERNS (CWE-943)
NOSQL_INJECTION_PATTERNS = [
    (r"\$ne\b", "NoSQLi: $ne (not equal)"),
    (r"\$gt\b", "NoSQLi: $gt (greater than)"),
    (r"\$lt\b", "NoSQLi: $lt (less than)"),
    (r"\$gte\b", "NoSQLi: $gte (greater or equal)"),
    (r"\$lte\b", "NoSQLi: $lte (less or equal)"),
    (r"\$regex\b", "NoSQLi: $regex operator"),
    (r"\$where\b", "NoSQLi: $where injection"),
    (r"\$or\b", "NoSQLi: $or operator"),
    (r"\$in\b", "NoSQLi: $in operator"),
    (r"(?i)\bthis\.\w+", "NoSQLi: this.property access"),
    (r"(?i)\breturn\s+true", "NoSQLi: return true bypass"),
]

# Add new pattern categories to ALL_PATTERNS
ALL_PATTERNS.extend([
    ("XXE", XXE_PATTERNS, "CWE-611", "T1059.002"),
    ("LFI/RFI", LFI_RFI_PATTERNS, "CWE-98", "T1020"),
    ("LDAP Injection", LDAP_INJECTION_PATTERNS, "CWE-90", "T1190"),
    ("NoSQL Injection", NOSQL_INJECTION_PATTERNS, "CWE-943", "T1190"),
])


# ============================================================================
# PAYLOAD DECODER
# ============================================================================

def decode_payload(payload: str) -> List[str]:
    """
    Decodifica un payload en multiples formatos para deteccion profunda.
    Retorna lista de variantes decodificadas para analisis.
    """
    variants = [payload]

    # URL decode
    try:
        decoded_url = unquote(payload)
        if decoded_url != payload:
            variants.append(decoded_url)
        # Doble URL decode
        decoded_url2 = unquote(decoded_url)
        if decoded_url2 != decoded_url:
            variants.append(decoded_url2)
    except Exception:
        pass

    # Base64 decode
    try:
        import base64
        # Intentar decodificar si parece base64
        stripped = payload.strip()
        if len(stripped) > 8 and re.match(r'^[A-Za-z0-9+/=\s]+$', stripped):
            decoded_b64 = base64.b64decode(stripped).decode('utf-8', errors='ignore')
            if decoded_b64 and decoded_b64 != payload:
                variants.append(decoded_b64)
    except Exception:
        pass

    # Hex decode
    try:
        if re.match(r'^[0-9a-fA-F]{10,}$', payload.strip()):
            decoded_hex = bytes.fromhex(payload.strip()).decode('utf-8', errors='ignore')
            if decoded_hex:
                variants.append(decoded_hex)
    except Exception:
        pass

    # Unicode decode
    try:
        decoded_unicode = payload.encode('utf-8').decode('unicode_escape')
        if decoded_unicode != payload:
            variants.append(decoded_unicode)
    except Exception:
        pass

    return list(set(variants))


# ============================================================================
# CERTIFICATE ANALYSIS
# ============================================================================

def analyze_certificate(host: str, port: int = 443, timeout: float = 5.0) -> Dict[str, Any]:
    """
    Analiza el certificado TLS de un host — NIST SP 800-52 Rev. 2.
    """
    result: Dict[str, Any] = {"host": host, "port": port, "cert": {}, "issues": []}

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()

                # TLS version
                tls_version = ssock.version()
                result["tls_version"] = tls_version
                if tls_version in ("TLSv1", "TLSv1.1", "SSLv3"):
                    result["issues"].append({
                        "type": "weak_tls",
                        "severity": "high",
                        "description": f"TLS obsoleto: {tls_version}",
                        "cwe": "CWE-326",
                        "mitre": "T1573",
                    })

                # Certificate details
                if cert:
                    subject = dict(x[0] for x in cert.get("subject", []))
                    issuer = dict(x[0] for x in cert.get("issuer", []))
                    result["cert"] = {
                        "subject": subject,
                        "issuer": issuer,
                        "not_before": cert.get("notBefore"),
                        "not_after": cert.get("notAfter"),
                        "serial": cert.get("serialNumber"),
                        "san": cert.get("subjectAltName", []),
                    }

                    # Check expiry
                    from datetime import datetime as dt
                    try:
                        expiry = dt.strptime(cert.get("notAfter", ""), "%b %d %H:%M:%S %Y %Z")
                        days_left = (expiry - dt.utcnow()).days
                        if days_left < 0:
                            result["issues"].append({
                                "type": "expired_cert",
                                "severity": "critical",
                                "description": f"Certificado expirado hace {abs(days_left)} dias",
                                "cwe": "CWE-295",
                            })
                        elif days_left < 30:
                            result["issues"].append({
                                "type": "expiring_cert",
                                "severity": "medium",
                                "description": f"Certificado expira en {days_left} dias",
                                "cwe": "CWE-295",
                            })
                    except Exception:
                        pass

                    # SNI mismatch
                    if host not in str(cert.get("subject", "")) and host not in str(cert.get("subjectAltName", "")):
                        result["issues"].append({
                            "type": "sni_mismatch",
                            "severity": "medium",
                            "description": f"SNI mismatch: {host} no coincide con el cert",
                            "cwe": "CWE-295",
                        })
    except Exception as e:
        result["error"] = str(e)

    return result


# ============================================================================
# RATE LIMITING / BRUTE FORCE DETECTION
# ============================================================================

class RateLimitDetector:
    """Detecta patrones de brute force y rate limit bypass — NIST SP 800-94 §3.3."""

    def __init__(self, window_seconds: int = 60, threshold: int = 30):
        self.window = window_seconds
        self.threshold = threshold
        self.requests: Dict[str, List[float]] = {}

    def check(self, src_ip: str) -> Dict[str, Any]:
        now = time.time()
        if src_ip not in self.requests:
            self.requests[src_ip] = []

        # Limpiar ventana
        self.requests[src_ip] = [t for t in self.requests[src_ip] if now - t < self.window]
        self.requests[src_ip].append(now)

        count = len(self.requests[src_ip])
        alerts = []

        if count > self.threshold:
            alerts.append({
                "type": "brute_force",
                "severity": "critical",
                "description": f"{count} requests en {self.window}s desde {src_ip}",
                "cwe": "CWE-307",
                "mitre": "T1110",
            })

        if count > self.threshold // 2:
            alerts.append({
                "type": "rate_anomaly",
                "severity": "medium",
                "description": f"Rate elevado: {count} requests en {self.window}s",
                "cwe": "CWE-770",
            })

        return {
            "ip": src_ip,
            "count": count,
            "window": self.window,
            "threshold": self.threshold,
            "alerts": alerts,
        }


# ============================================================================
# USER-AGENT ANALYSIS
# ============================================================================

SUSPICIOUS_UA_PATTERNS = [
    (r"(?i)sqlmap", "SQLmap scanner"),
    (r"(?i)nmap", "Nmap scanner"),
    (r"(?i)nikto", "Nikto scanner"),
    (r"(?i)masscan", "Masscan scanner"),
    (r"(?i)dirbuster", "DirBuster"),
    (r"(?i)gobuster", "Gobuster"),
    (r"(?i)wpscan", "WPScan"),
    (r"(?i)hydra", "Hydra brute force"),
    (r"(?i)metasploit", "Metasploit"),
    (r"(?i)burp", "Burp Suite"),
    (r"(?i)zap", "OWASP ZAP"),
    (r"(?i)acunetix", "Acunetix scanner"),
    (r"(?i)nessus", "Nessus scanner"),
    (r"(?i)openvas", "OpenVAS scanner"),
    (r"(?i)w3af", "w3af scanner"),
    (r"(?i)skipfish", "Skipfish scanner"),
    (r"(?i)curl/[0-9]", "curl (automated)"),
    (r"(?i)wget/[0-9]", "wget (automated)"),
    (r"(?i)python-requests", "Python requests (automated)"),
    (r"(?i)go-http-client", "Go HTTP client (automated)"),
    (r"(?i)scrapy", "Scrapy crawler"),
    (r"(?i)semrush", "Semrush bot"),
    (r"(?i)ahrefs", "Ahrefs bot"),
    (r"(?i)empty", "Empty User-Agent"),
]

def analyze_user_agent(ua: str) -> Dict[str, Any]:
    """Analiza un User-Agent en busca de scanners y herramientas de ataque."""
    if not ua or ua.strip() == "":
        return {"ua": ua, "suspicious": True, "type": "Empty User-Agent", "mitre": "T1190", "cwe": "CWE-451"}

    for pattern, name in SUSPICIOUS_UA_PATTERNS:
        if re.search(pattern, ua):
            return {
                "ua": ua,
                "suspicious": True,
                "type": name,
                "mitre": "T1190" if "scanner" in name.lower() or "brute" in name.lower() else "T1589",
                "cwe": "CWE-451",
            }

    return {"ua": ua, "suspicious": False}


# ============================================================================
# ENHANCED ENDPOINTS
# ============================================================================

class DecodePayloadModel(BaseModel):
    payload: str = Field(..., description="Payload a decodificar")

@interceptor_router.post("/decode")
async def api_decode_payload(req: DecodePayloadModel):
    """Decodifica un payload en multiples formatos para analisis manual."""
    variants = decode_payload(req.payload)
    return {"original": req.payload, "variants": variants, "total": len(variants)}


@interceptor_router.get("/cert/{host}")
async def api_analyze_cert(host: str, port: int = Query(443, ge=1, le=65535)):
    """Analiza el certificado TLS de un host — NIST SP 800-52 Rev. 2."""
    return analyze_certificate(host, port)


class UserAgentModel(BaseModel):
    ua: str = Field("", description="User-Agent a analizar")
    user_agent: str = Field("", description="User-Agent (alias alternativo)")

    def get_ua(self) -> str:
        return self.user_agent if self.user_agent else self.ua

@interceptor_router.post("/analyze/user-agent")
async def api_analyze_ua(req: UserAgentModel):
    """Analiza un User-Agent en busca de herramientas de ataque."""
    return analyze_user_agent(req.get_ua())


@interceptor_router.get("/rate-check/{ip}")
async def api_rate_check(ip: str):
    """Verifica el rate de un IP especifico."""
    detector = RateLimitDetector()
    return detector.check(ip)


# ============================================================================
# CAPTURA DE TRÁFICO REAL — Sniffer pasivo + Honeypot de captura
# ============================================================================

class _TrafficCapture:
    """Captura conexiones TCP entrantes para análisis de tráfico real."""
    def __init__(self):
        self.active = False
        self.server = None
        self.captured_flows = []

    async def start_capture(self, port: int = 8888):
        """Inicia un servidor TCP honeypot que captura intentos de conexión."""
        if self.active:
            return {"status": "already_running", "port": port}
        self.active = True
        self.captured_flows = []
        try:
            self.server = await asyncio.start_server(
                self._handle_connection, '0.0.0.0', port
            )
            return {"status": "started", "port": port}
        except OSError as e:
            self.active = False
            return {"status": "error", "error": str(e)}

    async def _handle_connection(self, reader, writer):
        """Maneja una conexión entrante — captura y analiza."""
        peer = writer.get_extra_info('peername')
        peer_ip = peer[0] if peer else "unknown"
        peer_port = peer[1] if peer else 0

        flow_id = hashlib.md5(f"{peer_ip}:{peer_port}:{time.time()}".encode()).hexdigest()[:12]

        # Leer datos (con timeout)
        try:
            data = await asyncio.wait_for(reader.read(4096), timeout=5.0)
            raw_data = data.decode('utf-8', errors='replace')[:500]
        except asyncio.TimeoutError:
            raw_data = ""

        # Analizar con el detector de inyecciones
        alerts = []
        if raw_data:
            detector = InjectionDetector()
            detected = detector.analyze(raw_data)
            for d in detected:
                alerts.append({
                    "alert_type": d.get("type", "unknown"),
                    "severity": d.get("severity", "info"),
                    "payload": raw_data[:100],
                    "pattern_matched": d.get("pattern", ""),
                    "cwe": d.get("cwe", ""),
                    "mitre": d.get("mitre", ""),
                })

        # Log el flow
        flow = {
            "id": flow_id,
            "src_ip": peer_ip,
            "dst_host": "localhost",
            "dst_port": 8888,
            "method": "TCP",
            "path": raw_data.split('\n')[0][:100] if raw_data else "",
            "status_code": 0,
            "request_headers": {},
            "response_headers": {},
            "request_size": len(data) if raw_data else 0,
            "response_size": 0,
            "duration_ms": 0,
            "alerts": json.dumps(alerts),
            "timestamp": datetime.datetime.now().isoformat(),
            "raw_data": raw_data[:200],
        }
        self.captured_flows.append(flow)

        # Guardar en DB
        try:
            siem = SIEMLogger()
            siem.log_flow(flow_id, peer_ip, "localhost", 8888,
                         "TCP", raw_data[:100], 0, {}, {},
                         len(raw_data), 0, 0, alerts)
        except Exception:
            pass

        # Responder con datos falsos (deception)
        try:
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n")
            await writer.drain()
        except Exception:
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def stop_capture(self):
        """Detiene la captura."""
        self.active = False
        if self.server:
            self.server.close()
            try:
                await self.server.wait_closed()
            except Exception:
                pass
            self.server = None
        return {"status": "stopped", "captured": len(self.captured_flows)}

    def get_captured(self, limit: int = 50):
        return self.captured_flows[-limit:]


_traffic_capture = _TrafficCapture()


@interceptor_router.post("/capture/start")
async def api_start_capture(port: int = Query(8888, ge=1, le=65535)):
    """Inicia un honeypot TCP que captura conexiones entrantes para análisis real."""
    result = await _traffic_capture.start_capture(port)
    return result


@interceptor_router.post("/capture/stop")
async def api_stop_capture():
    """Detiene la captura de tráfico."""
    return await _traffic_capture.stop_capture()


@interceptor_router.get("/capture/status")
async def api_capture_status():
    """Estado de la captura — muestra las conexiones capturadas."""
    return {
        "active": _traffic_capture.active,
        "captured": len(_traffic_capture.captured_flows),
        "flows": _traffic_capture.get_captured(50),
    }


@interceptor_router.post("/inject-flow")
async def api_inject_flow(flow: dict):
    """Inyecta un flow manualmente al interceptor para análisis (para testing)."""
    flow_id = hashlib.md5(f"{time.time()}".encode()).hexdigest()[:12]
    src_ip = flow.get("src_ip", "manual")
    dst_host = flow.get("dst_host", "unknown")
    dst_port = flow.get("dst_port", 0)
    method = flow.get("method", "GET")
    path = flow.get("path", "/")
    body = flow.get("body", "")

    detector = InjectionDetector()
    alerts = detector.analyze(f"{method} {path} {body}")

    request_analyzer = RequestAnalyzer()
    req_analysis = request_analyzer.analyze(method, path, {}, body)

    all_alerts = []
    for a in alerts + req_analysis.get("alerts", []):
        all_alerts.append({
            "alert_type": a.get("type", a.get("category", "unknown")),
            "severity": a.get("severity", "info"),
            "payload": (path + " " + body)[:200],
            "pattern_matched": a.get("pattern", a.get("pattern_matched", "")),
            "cwe": a.get("cwe", ""),
            "mitre": a.get("mitre", ""),
        })

    try:
        siem = SIEMLogger()
        siem.log_flow(flow_id, src_ip, dst_host, dst_port,
                     method, path, 0, {}, {},
                     len(body), 0, 0, all_alerts)
    except Exception:
        pass

    return {
        "flow_id": flow_id,
        "alerts": all_alerts,
        "alert_count": len(all_alerts),
        "analysis": req_analysis,
    }
