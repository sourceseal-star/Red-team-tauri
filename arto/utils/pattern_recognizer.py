"""
Pattern Recognizer - Reconocedor de Patrones
===========================================
Identifica patrones en datos de seguridad.
"""

import asyncio
import datetime
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class PatternType(Enum):
    """Tipos de patrones"""
    MALICIOUS = "malicious"
    SUSPICIOUS = "suspicious"
    NORMAL = "normal"
    UNKNOWN = "unknown"


@dataclass
class Pattern:
    """Patrón identificado"""
    pattern_id: str
    type: PatternType
    name: str
    description: str
    severity: str
    confidence: float
    evidence: List[str]
    timestamp: str
    
    def to_dict(self) -> Dict:
        return {
            "pattern_id": self.pattern_id,
            "type": self.type.value,
            "name": self.name,
            "description": self.description,
            "severity": self.severity,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "timestamp": self.timestamp
        }


class PatternRecognizer:
    """Reconocedor de Patrones Autónomo"""
    
    def __init__(self):
        self.patterns: Dict[str, Dict] = {
            "sqli": {
                "name": "SQL Injection",
                "type": PatternType.MALICIOUS,
                "severity": "critical",
                "regex": [r"SELECT.*FROM", r"UNION.*SELECT", r"OR 1=1", r"';", r"--", r"#"],
                "description": "Patrón de inyección SQL detectado"
            },
            "xss": {
                "name": "Cross-Site Scripting",
                "type": PatternType.MALICIOUS,
                "severity": "high",
                "regex": [r"<script>.*</script>", r"javascript:", r"onerror=", r"onload=", r"alert\('"],
                "description": "Patrón de XSS detectado"
            },
            "command_injection": {
                "name": "Command Injection",
                "type": PatternType.MALICIOUS,
                "severity": "critical",
                "regex": [r";\s*", r"\|\s*", r"&&\s*", r"`.*`", r"\$\(", r"\$\{"],
                "description": "Patrón de inyección de comandos detectado"
            },
            "path_traversal": {
                "name": "Path Traversal",
                "type": PatternType.MALICIOUS,
                "severity": "high",
                "regex": [r"\.\./\.\.", r"\.\./etc/passwd", r"\.\./etc/shadow"],
                "description": "Patrón de traversal de directorios detectado"
            },
            "lfi": {
                "name": "Local File Inclusion",
                "type": PatternType.MALICIOUS,
                "severity": "high",
                "regex": [r"file://", r"php://filter/read", r"include.*\."],
                "description": "Patrón de inclusión de archivos local detectado"
            },
            "rfi": {
                "name": "Remote File Inclusion",
                "type": PatternType.MALICIOUS,
                "severity": "critical",
                "regex": [r"http://", r"https://", r"ftp://"],
                "description": "Patrón de inclusión de archivos remotos detectado"
            },
            "brute_force": {
                "name": "Brute Force Attack",
                "type": PatternType.MALICIOUS,
                "severity": "high",
                "regex": [],
                "description": "Patrón de fuerza bruta detectado",
                "behavioral": True
            },
            "port_scan": {
                "name": "Port Scanning",
                "type": PatternType.SUSPICIOUS,
                "severity": "medium",
                "regex": [],
                "description": "Patrón de escaneo de puertos detectado",
                "behavioral": True
            },
            "dns_tunneling": {
                "name": "DNS Tunneling",
                "type": PatternType.SUSPICIOUS,
                "severity": "medium",
                "regex": [r"[a-zA-Z0-9]{50,}\.", r"base64"],
                "description": "Patrón de tunneling DNS detectado"
            }
        }
    
    async def recognize_patterns(self, data: Dict) -> List[Dict]:
        """
        Reconoce patrones en los datos proporcionados.
        
        Args:
            data: Datos a analizar (puede ser tráfico, logs, etc.)
            
        Returns:
            Lista de patrones reconocidos
        """
        patterns_found = []
        
        # Analizar según el tipo de datos
        if "requests" in data:
            patterns_found.extend(await self._analyze_requests(data["requests"]))
        
        if "responses" in data:
            patterns_found.extend(await self._analyze_responses(data["responses"]))
        
        if "logs" in data:
            patterns_found.extend(await self._analyze_logs(data["logs"]))
        
        if "behavior_data" in data:
            patterns_found.extend(await self._analyze_behavior(data["behavior_data"]))
        
        return [p.to_dict() for p in patterns_found]
    
    async def _analyze_requests(self, requests: List[Dict]) -> List[Pattern]:
        """Analiza patrones en solicitudes"""
        patterns_found = []
        
        for req in requests:
            body = req.get("body", "")
            path = req.get("path", "")
            method = req.get("method", "")
            headers = req.get("headers", {})
            
            # Convertir body a string si es dict
            if isinstance(body, dict):
                body_str = str(body)
            else:
                body_str = str(body)
            
            # Combinar todos los textos
            text = f"{method} {path} {body_str} {' '.join(f'{k}:{v}' for k, v in headers.items())}"
            
            # Buscar patrones
            for pattern_name, pattern_data in self.patterns.items():
                if pattern_data.get("behavioral"):
                    continue
                
                for regex in pattern_data.get("regex", []):
                    if re.search(regex, text, re.IGNORECASE):
                        pattern = Pattern(
                            pattern_id=f"{pattern_name}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                            type=pattern_data["type"],
                            name=pattern_data["name"],
                            description=pattern_data["description"],
                            severity=pattern_data["severity"],
                            confidence=0.9,
                            evidence=[text[:100]],
                            timestamp=datetime.datetime.now().isoformat()
                        )
                        patterns_found.append(pattern)
                        break
        
        return patterns_found
    
    async def _analyze_responses(self, responses: List[Dict]) -> List[Pattern]:
        """Analiza patrones en respuestas"""
        patterns_found = []
        
        for resp in responses:
            body = resp.get("body", "")
            headers = resp.get("headers", {})
            status = resp.get("status_code", 200)
            
            # Convertir body a string si no lo es
            if not isinstance(body, str):
                body = str(body)
            
            # Buscar patrones en el cuerpo
            for pattern_name, pattern_data in self.patterns.items():
                if pattern_data.get("behavioral"):
                    continue
                
                for regex in pattern_data.get("regex", []):
                    if re.search(regex, body, re.IGNORECASE):
                        pattern = Pattern(
                            pattern_id=f"{pattern_name}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                            type=pattern_data["type"],
                            name=pattern_data["name"],
                            description=pattern_data["description"],
                            severity=pattern_data["severity"],
                            confidence=0.85,
                            evidence=[body[:100]],
                            timestamp=datetime.datetime.now().isoformat()
                        )
                        patterns_found.append(pattern)
                        break
        
        return patterns_found
    
    async def _analyze_logs(self, logs: List[Dict]) -> List[Pattern]:
        """Analiza patrones en logs"""
        patterns_found = []
        
        for log in logs:
            message = log.get("message", "")
            
            # Buscar patrones en el mensaje
            for pattern_name, pattern_data in self.patterns.items():
                if pattern_data.get("behavioral"):
                    continue
                
                for regex in pattern_data.get("regex", []):
                    if re.search(regex, message, re.IGNORECASE):
                        pattern = Pattern(
                            pattern_id=f"{pattern_name}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                            type=pattern_data["type"],
                            name=pattern_data["name"],
                            description=pattern_data["description"],
                            severity=pattern_data["severity"],
                            confidence=0.8,
                            evidence=[message[:100]],
                            timestamp=datetime.datetime.now().isoformat()
                        )
                        patterns_found.append(pattern)
                        break
        
        return patterns_found
    
    async def _analyze_behavior(self, behavior_data: Dict) -> List[Pattern]:
        """Analiza patrones de comportamiento"""
        patterns_found = []
        
        # Patrones de fuerza bruta
        if behavior_data.get("failed_logins", 0) > 10:
            pattern = Pattern(
                pattern_id=f"brute_force_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                type=PatternType.MALICIOUS,
                name="Brute Force Attack",
                description="Múltiples intentos de login fallidos detectados",
                severity="high",
                confidence=0.9,
                evidence=[f"Failed logins: {behavior_data.get('failed_logins', 0)}"],
                timestamp=datetime.datetime.now().isoformat()
            )
            patterns_found.append(pattern)
        
        # Patrones de escaneo de puertos
        if behavior_data.get("unique_ips", 0) > 50:
            pattern = Pattern(
                pattern_id=f"port_scan_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                type=PatternType.SUSPICIOUS,
                name="Port Scanning",
                description="Múltiples IPs únicas detectadas",
                severity="medium",
                confidence=0.8,
                evidence=[f"Unique IPs: {behavior_data.get('unique_ips', 0)}"],
                timestamp=datetime.datetime.now().isoformat()
            )
            patterns_found.append(pattern)
        
        # Patrones de alta tasa de solicitudes
        if behavior_data.get("request_rate", 0) > 100:
            pattern = Pattern(
                pattern_id=f"high_rate_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                type=PatternType.SUSPICIOUS,
                name="High Request Rate",
                description="Alta tasa de solicitudes detectada",
                severity="medium",
                confidence=0.75,
                evidence=[f"Request rate: {behavior_data.get('request_rate', 0)}"],
                timestamp=datetime.datetime.now().isoformat()
            )
            patterns_found.append(pattern)
        
        return patterns_found
    
    async def get_pattern_stats(self) -> Dict:
        """Obtiene estadísticas de patrones"""
        type_counts = {}
        severity_counts = {}
        
        for pattern_name, pattern_data in self.patterns.items():
            ptype = pattern_data["type"].value
            type_counts[ptype] = type_counts.get(ptype, 0) + 1
            
            severity = pattern_data["severity"]
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        return {
            "total_patterns": len(self.patterns),
            "type_counts": type_counts,
            "severity_counts": severity_counts
        }
    
    async def add_custom_pattern(self, name: str, pattern_type: PatternType,
                                severity: str, regex: List[str],
                                description: str) -> bool:
        """Agrega un patrón personalizado"""
        if name in self.patterns:
            return False
        
        self.patterns[name] = {
            "name": name,
            "type": pattern_type,
            "severity": severity,
            "regex": regex,
            "description": description
        }
        
        return True
    
    async def remove_pattern(self, name: str) -> bool:
        """Elimina un patrón"""
        if name in self.patterns:
            del self.patterns[name]
            return True
        return False
