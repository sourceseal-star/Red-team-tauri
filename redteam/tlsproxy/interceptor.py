#!/usr/bin/env python3
"""
TLS Proxy — Proxy de Desencapsulado TLS/SSL
============================================
Intercepta e inspecciona tráfico cifrado en capas 3-7 mediante
terminación TLS segura. Permite análisis de payloads en tiempo real
sin vulnerar la confidencialidad interna.

Diseñado para integrarse con el NDR — los flujos interceptados
se envían al motor comportamental para análisis.

Modo de operación:
  1. MITM con CA interna (auto-generada si no se provee)
  2. Inspección de headers, payload y timing
  3. Detección de anomalias en capa de aplicación
  4. Logging de metadatos (NO contenido) para privacidad

Nota: En producción, usar mitmproxy o un WAF con TLS termination.
Este módulo provee la interfaz de integración con el NDR.
"""
import ssl
import time
import json
import hashlib
import datetime
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field, asdict


@dataclass
class InterceptedFlow:
    id: str
    src_ip: str
    dst_host: str
    dst_port: int
    method: str
    path: str
    status_code: int = 0
    request_headers: Dict[str, str] = field(default_factory=dict)
    response_headers: Dict[str, str] = field(default_factory=dict)
    request_size: int = 0
    response_size: int = 0
    duration_ms: int = 0
    tls_version: str = ""
    sni: str = ""
    cert_valid: bool = True
    cert_issuer: str = ""
    timestamp: str = ""

    # Metadatos para NDR (sin contenido del payload)
    content_type: str = ""         # application/json, text/html, etc.
    has_binary: bool = False
    suspicious_headers: List[str] = field(default_factory=list)


class TLSProxy:
    """
    Proxy de desencapsulado TLS.
    En producción se integra con mitmproxy o nginx stream proxy.
    Aquí provee la interfaz para que el NDR consuma los flujos.
    """

    SUSPICIOUS_HEADERS = [
        "x-forwarded-for",          # IP spoofing attempt
        "x-real-ip",                # IP override
        "x-original-url",           # URL rewrite attack
        "x-rewrite-url",            # URL rewrite attack
        "x-custom-ip-authorization",# auth bypass
    ]

    SUSPICIOUS_PATHS = [
        "/.env", "/.git", "/wp-admin", "/admin/secret",
        "/api/internal", "/actuator", "/health",
        "/.aws/credentials", "/id_rsa",
    ]

    def __init__(self, ca_cert: str = "", ca_key: str = ""):
        self.ca_cert = ca_cert
        self.ca_key = ca_key
        self.flows: List[InterceptedFlow] = []
        self.alerts: List[Dict] = []
        self.on_flow: Optional[Callable] = None  # callback para NDR

    def process_flow(self, flow: InterceptedFlow) -> List[Dict]:
        """Procesa un flujo interceptado y genera alertas si detecta anomalias."""
        self.flows.append(flow)
        alerts = []

        # 1. Headers sospechosos
        for h in self.SUSPICIOUS_HEADERS:
            if h.lower() in {k.lower() for k in flow.request_headers}:
                alerts.append({
                    "type": "suspicious_header",
                    "severity": "high",
                    "title": f"Header sospechoso: {h}",
                    "description": f"Request a {flow.dst_host}{flow.path} contiene header {h}",
                    "evidence": {"header": h, "host": flow.dst_host, "path": flow.path},
                    "timestamp": flow.timestamp,
                    "mitre": "T1190",
                    "src_ip": flow.src_ip,
                })

        # 2. Paths sospechosos
        for p in self.SUSPICIOUS_PATHS:
            if p in flow.path:
                alerts.append({
                    "type": "suspicious_path",
                    "severity": "critical" if p.startswith("/.env") or p.startswith("/.git") else "high",
                    "title": f"Path sospechoso accedido: {flow.path}",
                    "description": f"Acceso a {p} desde {flow.src_ip}",
                    "evidence": {"path": flow.path, "pattern": p, "host": flow.dst_host},
                    "timestamp": flow.timestamp,
                    "mitre": "T1046",
                    "src_ip": flow.src_ip,
                })

        # 3. Certificado invalido
        if not flow.cert_valid:
            alerts.append({
                "type": "invalid_cert",
                "severity": "medium",
                "title": f"Certificado TLS invalido: {flow.dst_host}",
                "description": f"SNI={flow.sni}, issuer={flow.cert_issuer}",
                "evidence": {"host": flow.dst_host, "sni": flow.sni, "issuer": flow.cert_issuer},
                "timestamp": flow.timestamp,
                "mitre": "T1556",
                "src_ip": flow.src_ip,
            })

        # 4. TLS version obsoleta
        if flow.tls_version and flow.tls_version in ("TLSv1", "TLSv1.1", "SSLv3"):
            alerts.append({
                "type": "weak_tls",
                "severity": "high",
                "title": f"TLS obsoleto: {flow.tls_version}",
                "description": f"Conexion a {flow.dst_host} usa {flow.tls_version}",
                "evidence": {"host": flow.dst_host, "tls_version": flow.tls_version},
                "timestamp": flow.timestamp,
                "mitre": "T1573",
                "src_ip": flow.src_ip,
            })

        # 5. Response con binario donde no debería
        if flow.has_binary and flow.content_type.startswith("text/"):
            alerts.append({
                "type": "content_mismatch",
                "severity": "medium",
                "title": "Content-Type no coincide con contenido",
                "description": f"Response declara {flow.content_type} pero contiene binario",
                "evidence": {"content_type": flow.content_type, "response_size": flow.response_size},
                "timestamp": flow.timestamp,
                "src_ip": flow.src_ip,
            })

        self.alerts.extend(alerts)

        # Notificar al NDR si hay callback
        if self.on_flow:
            self.on_flow(flow)

        return alerts

    def get_flows_summary(self) -> Dict:
        by_status = {}
        by_host = {}
        for f in self.flows:
            status_bucket = f"{f.status_code // 100}xx"
            by_status[status_bucket] = by_status.get(status_bucket, 0) + 1
            by_host[f.dst_host] = by_host.get(f.dst_host, 0) + 1

        return {
            "total_flows": len(self.flows),
            "by_status": by_status,
            "top_hosts": dict(sorted(by_host.items(), key=lambda x: -x[1])[:10]),
            "total_alerts": len(self.alerts),
            "alert_types": list(set(a["type"] for a in self.alerts)),
        }
