#!/usr/bin/env python3
"""
Attestation API Server — Recibe y valida reportes RASP de dispositivos móviles.
Standalone: no requiere FastAPI. Usa http.server nativo de Python.
"""
import json
import time
import hashlib
import hmac
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse


@dataclass
class Finding:
    severity: str  # "critical", "high", "medium"
    type: str
    detail: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class AttestationReport:
    device_id: str
    platform: str  # "android" or "ios"
    integrity_token: str  # Play Integrity JWT or DeviceCheck token
    findings: List[Finding] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    status: str = "pending"  # pending, safe, suspicious, compromised


class AttestationServer:
    """Servidor de atestación de dispositivos móviles."""

    def __init__(self, hmac_secret: str = "sourceseal-attestation-key"):
        self.hmac_secret = hmac_secret
        self.reports: List[AttestationReport] = []
        self.device_status: Dict[str, str] = {}
        self.rate_limit: Dict[str, float] = {}  # device_id -> last_report_time

    def receive_report(self, report_data: Dict) -> Dict:
        """Recibe y procesa un reporte RASP de un dispositivo."""
        device_id = report_data.get("device_id", "unknown")

        # Rate limit: 1 report per device per 30s
        now = time.time()
        if device_id in self.rate_limit:
            elapsed = now - self.rate_limit[device_id]
            if elapsed < 30:
                return {"status": "rate_limited", "message": f"Wait {int(30 - elapsed)}s"}

        self.rate_limit[device_id] = now

        # Validar integrity token (simulado — en producción validar con Google/Apple)
        token = report_data.get("integrity_token", "")
        token_valid = self._validate_token(token, device_id)

        # Procesar findings
        findings = [
            Finding(severity=f.get("severity", "medium"),
                    type=f.get("type", "unknown"),
                    detail=f.get("detail", ""),
                    timestamp=f.get("timestamp", datetime.utcnow().isoformat()))
            for f in report_data.get("findings", [])
        ]

        # Determinar status
        has_critical = any(f.severity == "critical" for f in findings)
        has_high = any(f.severity == "high" for f in findings)

        if has_critical or not token_valid:
            status = "compromised"
        elif has_high:
            status = "suspicious"
        else:
            status = "safe"

        report = AttestationReport(
            device_id=device_id,
            platform=report_data.get("platform", "unknown"),
            integrity_token=token,
            findings=findings,
            status=status,
        )
        self.reports.append(report)
        self.device_status[device_id] = status

        return {
            "status": status,
            "device_id": device_id,
            "findings_count": len(findings),
            "token_valid": token_valid,
            "timestamp": report.timestamp,
        }

    def get_device_status(self, device_id: str) -> Dict:
        """Retorna el último estado de atestación de un dispositivo."""
        status = self.device_status.get(device_id, "unknown")
        latest = None
        for r in reversed(self.reports):
            if r.device_id == device_id:
                latest = r
                break
        return {
            "device_id": device_id,
            "status": status,
            "last_report": latest.timestamp if latest else None,
            "findings": [
                {"severity": f.severity, "type": f.type, "detail": f.detail}
                for f in (latest.findings if latest else [])
            ],
        }

    def _validate_token(self, token: str, device_id: str) -> bool:
        """Valida un Play Integrity / DeviceCheck token (simulado)."""
        if not token:
            return False
        # En producción: validar JWT con Google Play Integrity API o Apple DeviceCheck
        # Aquí: verificar que el token tenga formato válido
        return len(token) > 10

    def get_all_devices(self) -> List[Dict]:
        """Retorna estado de todos los dispositivos."""
        return [
            {"device_id": did, "status": status}
            for did, status in self.device_status.items()
        ]


class AttestationHandler(BaseHTTPRequestHandler):
    """HTTP handler para la API de atestación."""

    server_instance: AttestationServer = None

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/attestation/report":
            content_length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_length))
            result = self.server_instance.receive_report(body)
            self._send_json(200, result)
        else:
            self._send_json(404, {"error": "Not found"})

    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith("/api/attestation/status/"):
            device_id = path.split("/")[-1]
            result = self.server_instance.get_device_status(device_id)
            self._send_json(200, result)
        elif path == "/api/attestation/devices":
            self._send_json(200, self.server_instance.get_all_devices())
        else:
            self._send_json(404, {"error": "Not found"})

    def _send_json(self, code: int, data: dict):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def log_message(self, format, *args):
        pass  # Suppress logs


def run_server(port: int = 9090, secret: str = "sourceseal-attestation-key"):
    """Inicia el servidor de atestación."""
    server = AttestationServer(hmac_secret=secret)
    AttestationHandler.server_instance = server
    httpd = HTTPServer(("0.0.0.0", port), AttestationHandler)
    print(f"[attestation] Server running on port {port}")
    httpd.serve_forever()
