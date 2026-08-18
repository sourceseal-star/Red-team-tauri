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
