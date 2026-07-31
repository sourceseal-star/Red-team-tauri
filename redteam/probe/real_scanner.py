#!/usr/bin/env python3
"""
Real Scanner — Hace requests HTTP reales al backend para detectar vulnerabilidades reales.
No simula nada. Conecta con la API, mide respuestas, y reporta hallazgos reales.
"""
import requests
import json
import time
import hashlib
from datetime import datetime
from urllib.parse import urljoin
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class RealFinding:
    type: str           # bola, auth_bypass, info_disclosure, misconfig, injection
    severity: str       # critical, high, medium, low, info
    endpoint: str
    method: str
    description: str
    evidence: str       # respuesta real del servidor
    status_code: int
    mitre: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class RealScanner:
    def __init__(self, backend_url: str, timeout: int = 10):
        self.backend = backend_url.rstrip("/")
        self.timeout = timeout
        self.findings: List[RealFinding] = []
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "SourceSeal-RedTeam/1.0",
            "Accept": "application/json",
        })
        self.results = {
            "backend": self.backend,
            "scanned_at": datetime.utcnow().isoformat(),
            "endpoints_tested": 0,
            "findings": [],
            "response_times": [],
            "status_codes": {},
            "error": None,
        }

    def _request(self, method: str, path: str, **kwargs) -> Optional[requests.Response]:
        """Hace un request real al backend."""
        url = urljoin(self.backend + "/", path.lstrip("/"))
        try:
            start = time.time()
            resp = self.session.request(
                method, url, timeout=self.timeout,
                verify=kwargs.pop("verify", False),
                **kwargs,
            )
            elapsed = (time.time() - start) * 1000
            self.results["response_times"].append({
                "endpoint": path, "ms": round(elapsed, 0),
                "status": resp.status_code,
            })
            self.results["status_codes"][resp.status_code] = \
                self.results["status_codes"].get(resp.status_code, 0) + 1
            self.results["endpoints_tested"] += 1
            return resp
        except requests.exceptions.ConnectionError:
            return None
        except requests.exceptions.Timeout:
            return None
        except Exception as e:
            return None

    def _add_finding(self, type_, severity, endpoint, method, desc, evidence, code, mitre=""):
        f = RealFinding(
            type=type_, severity=severity, endpoint=endpoint, method=method,
            description=desc, evidence=evidence[:500], status_code=code, mitre=mitre,
        )
        self.findings.append(f)
        self.results["findings"].append({
            "type": f.type, "severity": f.severity,
            "endpoint": f.endpoint, "method": f.method,
            "description": f.description, "evidence": f.evidence,
            "status_code": f.status_code, "mitre": f.mitre,
        })

    def scan_connectivity(self):
        """Test 1: ¿El backend responde?"""
        print("  [probe] Conectando al backend...")
        resp = self._request("GET", "/")
        if resp is None:
            resp = self._request("GET", "/api")
        if resp is None:
            self.results["error"] = "No se pudo conectar al backend"
            print(f"  [probe] ❌ No responde en {self.backend}")
            return False
        
        print(f"  [probe] ✅ Backend responde ({resp.status_code})")
        
        # Headers de seguridad
        sec_headers = [
            "X-Content-Type-Options", "X-Frame-Options", "Strict-Transport-Security",
            "Content-Security-Policy", "X-XSS-Protection",
        ]
        missing = [h for h in sec_headers if h not in resp.headers]
        if missing:
            self._add_finding(
                "misconfig", "medium", "/", "GET",
                f"Headers de seguridad faltantes: {', '.join(missing)}",
                json.dumps(dict(resp.headers)),
                resp.status_code,
            )
        return True

    def scan_api_endpoints(self):
        """Test 2: Descubrir endpoints de API y probar acceso."""
        print("  [probe] Escaneando endpoints API...")
        
        # ─── ENDPOINTS REALES DE SOURCESEAL.CO ────────────────────────────────
        if "sourceseal.co" in self.backend:
            ss_endpoints = [
                "/api/healthz", "/api/seals", "/api/seals/", "/api/seals/1",
                "/api/seals/2", "/api/seals/3", "/api/seals/4", "/api/seals/5",
                "/api/seals/6", "/api/seals/7", "/api/seals/8", "/api/seals/chain",
                "/api/corp/nonce", "/api/corp/seal", "/api/sandbox/nonce",
                "/api/sandbox/seal", "/api/sandbox/verify/",
                "/api/academy/certificate", "/api/admin/threat-intel/events",
                "/api/admin/threat-intel/report", "/api/admin/threat-intel/summary",
                "/api/integrity/status", "/api/legal/frameworks",
                "/api/enforcement/evaluate", "/api/payments/initiate",
                "/api/payments/crypto/address", "/api/payments/crypto/verify",
                "/api/openai/conversations", "/api/openai/proactive-status",
                "/api/social/alerts", "/api/reports", "/api/pitch/access",
                "/api/compliance/data-request", "/api/client/",
                "/api/legal/certificate/",
            ]
            # BOLA: probar IDs secuenciales
            for i in range(1, 20):
                ss_endpoints.append(f"/api/seals/{i}")
            # Param injection
            ss_endpoints.extend([
                "/api/seals?limit=100", "/api/seals?admin=true",
                "/api/openai/conversations?limit=100",
            ])
            for ep in ss_endpoints:
                resp = self._request("GET", ep)
                if resp is None:
                    continue
                # Detectar respuestas sin auth
                if resp.status_code == 200:
                    body = resp.text[:500]
                    if "/admin" in ep:
                        self._add_finding(
                            "auth_bypass", "critical", ep, "GET",
                            f"Endpoint admin accesible SIN auth ({resp.status_code})",
                            body, resp.status_code, "T1190")
                    elif "/api/openai/conversations" in ep:
                        self._add_finding(
                            "info_disclosure", "high", ep, "GET",
                            "Conversaciones de OpenAI accesibles sin auth — expone datos de usuarios",
                            body[:300], resp.status_code, "T1190")
                    elif "/api/integrity/status" in ep:
                        self._add_finding(
                            "info_disclosure", "medium", ep, "GET",
                            "Estado de integridad del sistema expuesto sin auth",
                            body[:300], resp.status_code, "T1046")
                    elif "/api/legal/frameworks" in ep:
                        self._add_finding(
                            "info_disclosure", "low", ep, "GET",
                            "Frameworks legales expuestos sin auth (datos no sensibles)",
                            body[:200], resp.status_code, "T1046")
                    elif "/api/corp/nonce" in ep or "/api/sandbox/nonce" in ep:
                        self._add_finding(
                            "info_disclosure", "medium", ep, "GET",
                            "Nonce criptográfico expuesto sin auth — puede enable replay attacks",
                            body[:300], resp.status_code, "T1552")
                    elif "/api/pitch/access" in ep:
                        self._add_finding(
                            "info_disclosure", "low", ep, "GET",
                            "Info de plan/pitch accesible sin auth",
                            body[:200], resp.status_code, "T1046")
                # Detectar 401 vs 403 — info leak
                if resp.status_code == 401:
                    pass  # Correcto: requiere auth
                elif resp.status_code == 403:
                    self._add_finding(
                        "info_disclosure", "low", ep, "GET",
                        f"403 revela que el endpoint existe (fingerprinting)",
                        resp.text[:200], resp.status_code, "T1046")
                elif resp.status_code == 500:
                    self._add_finding(
                        "info_disclosure", "high", ep, "GET",
                        "Error 500 revela info del servidor",
                        resp.text[:300], resp.status_code, "T1190")
                elif resp.status_code == 503:
                    self._add_finding(
                        "misconfig", "medium", ep, "GET",
                        "Servicio 503 — dependencia caída o mal configurada",
                        resp.text[:200], resp.status_code, "T1499")
            self.results["endpoints_tested"] = len(ss_endpoints)
            return self.results

        endpoints = [
            ("/api/courses", "GET"),
            ("/api/courses/1", "GET"),
            ("/api/admin", "GET"),
            ("/api/admin/seals", "GET"),
            ("/api/admin/users", "GET"),
            ("/api/users", "GET"),
            ("/api/users/me", "GET"),
            ("/api/enrollments", "GET"),
            ("/api/certificates", "GET"),
            ("/api/payments", "GET"),
            ("/api/health", "GET"),
            ("/api/v1", "GET"),
            ("/api/debug", "GET"),
            ("/api/config", "GET"),
            ("/api/auth/me", "GET"),
            ("/api/seals", "GET"),
            ("/api/verify", "GET"),
        ]


        for path, method in endpoints:
            resp = self._request(method, path)
            if resp is None:
                continue
            
            # Detectar respuestas sin auth
            if resp.status_code == 200:
                body = resp.text[:500]
                # ¿Expone datos sin autenticación?
                if any(x in path for x in ["/admin", "/users", "/payments", "/config", "/debug"]):
                    self._add_finding(
                        "auth_bypass", "critical", path, method,
                        f"Endpoint administrativo accesible SIN autenticación ({resp.status_code})",
                        body, resp.status_code, "T1190",
                    )
                elif "/courses" in path:
                    # Cursos publicados deberían ser visibles, pero verificar
                    try:
                        data = resp.json()
                        if isinstance(data, list) and len(data) > 0:
                            # ¿Hay cursos no publicados visibles?
                            for item in data if isinstance(data, list) else [data]:
                                if isinstance(item, dict):
                                    if "isPublished" in item and item.get("isPublished") == False:
                                        self._add_finding(
                                            "info_disclosure", "high", path, method,
                                            "Curso NO publicado visible al público",
                                            json.dumps(item)[:300], resp.status_code, "T1190",
                                        )
                    except:
                        pass
            
            # Detectar errores del servidor que revelan info
            if resp.status_code == 500:
                self._add_finding(
                    "info_disclosure", "medium", path, method,
                    f"Error 500 revela información del servidor",
                    resp.text[:300], resp.status_code,
                )
            
            # Detectar rutas que no deberían existir pero responden
            if resp.status_code == 200 and "/debug" in path:
                self._add_finding(
                    "misconfig", "high", path, method,
                    "Endpoint de debug accesible en producción",
                    resp.text[:300], resp.status_code,
                )

    def scan_bola(self):
        """Test 3: BOLA — acceder a recursos de otros usuarios."""
        print("  [probe] Test BOLA...")
        
        # Intentar acceder a recursos con IDs secuenciales
        for resource_id in [1, 2, 3, 999]:
            for base_path in ["/api/courses", "/api/users", "/api/enrollments"]:
                path = f"{base_path}/{resource_id}"
                resp = self._request("GET", path)
                if resp and resp.status_code == 200:
                    try:
                        data = resp.json()
                        if isinstance(data, dict):
                            # ¿Tiene campo de owner/user?
                            owner_fields = ["userId", "user_id", "ownerId", "created_by", "authorId"]
                            for of in owner_fields:
                                if of in data and data[of] not in [None, "", 0, "0"]:
                                    self._add_finding(
                                        "bola", "high", path, "GET",
                                        f"Posible BOLA: recurso {resource_id} expone campo {of}={data[of]} sin verificar ownership",
                                        json.dumps(data)[:300], resp.status_code, "T1190",
                                    )
                    except:
                        pass

    def scan_injection(self):
        """Test 4: Injection básico en parámetros."""
        print("  [probe] Test injection...")
        
        payloads = [
            ("' OR '1'='1", "SQL"),
            ("${7*7}", "SSTI"),
            ("../../../etc/passwd", "Path Traversal"),
            ("<script>alert(1)</script>", "XSS"),
        ]
        
        for payload, attack_type in payloads:
            # Probar en query params
            resp = self._request("GET", "/api/courses", params={"q": payload})
            if resp and resp.status_code == 200:
                if payload in resp.text or (attack_type == "SSTI" and "49" in resp.text):
                    self._add_finding(
                        "injection", "high", "/api/courses", "GET",
                        f"Posible {attack_type} — payload reflejado en respuesta",
                        f"Payload: {payload}\nRespuesta: {resp.text[:200]}",
                        resp.status_code, "T1059" if "SQL" in attack_type else "T1055",
                    )

    def scan_tls(self):
        """Test 5: Verificar TLS del backend."""
        print("  [probe] Verificando TLS...")
        if not self.backend.startswith("https"):
            self._add_finding(
                "misconfig", "high", "/", "GET",
                "Backend sin HTTPS — tráfico en plano",
                f"URL: {self.backend}", 0,
            )
            return
        
        try:
            resp = self._request("GET", "/")
            if resp:
                hsts = resp.headers.get("Strict-Transport-Security", "")
                if not hsts:
                    self._add_finding(
                        "misconfig", "medium", "/", "GET",
                        "HSTS no configurado",
                        "Sin header Strict-Transport-Security",
                        resp.status_code,
                    )
        except:
            pass

    def scan_rate_limit(self):
        """Test 6: Rate limiting."""
        print("  [probe] Test rate limiting...")
        hit_count = 0
        for i in range(20):
            resp = self._request("GET", "/api/courses")
            if resp and resp.status_code == 429:
                self._add_finding(
                    "info", "info", "/api/courses", "GET",
                    f"Rate limiting activo (429 tras {i+1} requests)",
                    f"Status: 429", 429,
                )
                return
            if resp and resp.status_code == 200:
                hit_count += 1
        
        if hit_count >= 20:
            self._add_finding(
                "misconfig", "medium", "/api/courses", "GET",
                "Sin rate limiting — 20 requests sin bloqueo",
                f"20 requests exitosos consecutivos", 200,
            )

    def scan_all(self):
        """Ejecuta todos los scans reales."""
        print("  [probe] Iniciando scan real contra backend...")
        
        if not self.scan_connectivity():
            return self.results
        
        self.scan_api_endpoints()
        self.scan_bola()
        self.scan_injection()
        self.scan_tls()
        self.scan_rate_limit()
        
        # Resumen
        by_sev = {}
        for f in self.findings:
            by_sev[f.severity] = by_sev.get(f.severity, 0) + 1
        
        self.results["total_findings"] = len(self.findings)
        self.results["by_severity"] = by_sev
        self.results["endpoints_tested"] = self.results["endpoints_tested"]
        
        print(f"  [probe] {len(self.findings)} hallazgos reales | {self.results['endpoints_tested']} endpoints probados")
        
        return self.results
