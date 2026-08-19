"""
Threat Intelligence - Inteligencia de Amenazas
==============================================
Recopila y analiza información de amenazas de múltiples fuentes.
"""

import asyncio
import datetime
import aiohttp
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class Threat:
    """Amenaza detectada"""
    id: str
    type: str
    target: str
    description: str
    severity: str
    confidence: float
    source: str
    timestamp: str
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type,
            "target": self.target,
            "description": self.description,
            "severity": self.severity,
            "confidence": self.confidence,
            "source": self.source,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }


class ThreatIntelligence:
    """Inteligencia de Amenazas"""
    
    def __init__(self):
        self.sources: Dict[str, Dict] = {
            "local": {"enabled": True, "priority": 10},
            "virus_total": {"enabled": True, "priority": 9, "api_key": None},
            "shodan": {"enabled": True, "priority": 8, "api_key": None},
            "censys": {"enabled": True, "priority": 7, "api_key": None},
            "abuse_ipdb": {"enabled": True, "priority": 6, "api_key": None},
            "threat_fox": {"enabled": True, "priority": 5, "api_key": None}
        }
        self.threat_cache: Dict[str, Threat] = {}
        self.cache_expiry = datetime.timedelta(hours=1)
        self.initialized = False
        
    async def initialize(self):
        """Inicializa el módulo de inteligencia de amenazas"""
        print("🎯 Inicializando Threat Intelligence...")
        
        # Cargar configuración
        await self._load_configuration()
        
        self.initialized = True
        print("✅ Threat Intelligence listo")
    
    async def _load_configuration(self):
        """Carga la configuración de fuentes"""
        # En implementación completa, esto cargaría de un archivo de configuración
        pass
    
    async def analyze_target(self, target: str, scan_result: Optional[Dict] = None) -> Dict:
        """
        Analiza un objetivo en busca de amenazas.
        
        Args:
            target: Objetivo a analizar (IP, dominio, URL)
            scan_result: Resultados de escaneo (opcional)
            
        Returns:
            Análisis de amenazas
        """
        analysis = {
            "target": target,
            "timestamp": datetime.datetime.now().isoformat(),
            "threats": [],
            "threat_score": 0.0,
            "severity": "info",
            "sources_checked": []
        }
        
        # Analizar con cada fuente
        for source_name, source_config in self.sources.items():
            if not source_config.get("enabled", False):
                continue
            
            try:
                result = await self._analyze_with_source(source_name, target, scan_result)
                if result:
                    analysis["sources_checked"].append(source_name)
                    analysis["threats"].extend(result.get("threats", []))
            except Exception as e:
                print(f"⚠️ Error con fuente {source_name}: {e}")
        
        # Calcular score de amenaza
        analysis["threat_score"] = self._calculate_threat_score(analysis["threats"])
        analysis["severity"] = self._determine_severity(analysis["threat_score"])
        
        # Almacenar en caché
        for threat in analysis["threats"]:
            self.threat_cache[threat.get("id")] = Threat(**threat)
        
        return analysis
    
    async def _analyze_with_source(self, source: str, target: str, 
                                   scan_result: Optional[Dict]) -> Optional[Dict]:
        """Analiza con una fuente específica"""
        if source == "local":
            return await self._analyze_local(target, scan_result)
        elif source == "virus_total":
            return await self._analyze_virustotal(target)
        elif source == "shodan":
            return await self._analyze_shodan(target)
        elif source == "censys":
            return await self._analyze_censys(target)
        elif source == "abuse_ipdb":
            return await self._analyze_abuseipdb(target)
        elif source == "threat_fox":
            return await self._analyze_threatfox(target)
        return None
    
    async def _analyze_local(self, target: str, scan_result: Optional[Dict]) -> Dict:
        """Analiza usando datos locales"""
        threats = []
        
        # Analizar basado en escaneo
        if scan_result:
            # Buscar puertos peligrosos
            port_scan = scan_result.get("sources", {}).get("port_scan", {})
            for port in port_scan.get("open_ports", []):
                if port.get("risk") == "high":
                    threats.append({
                        "id": f"local_port_{target}_{port['port']}",
                        "type": "open_port",
                        "target": target,
                        "description": f"Puerto {port['port']} ({port['service']}) abierto",
                        "severity": "high",
                        "confidence": 0.9,
                        "source": "local",
                        "timestamp": datetime.datetime.now().isoformat(),
                        "metadata": {"port": port["port"], "service": port["service"]}
                    })
            
            # Analizar VirusTotal local
            vt_data = scan_result.get("sources", {}).get("virustotal", {})
            if vt_data.get("malicious", False):
                threats.append({
                    "id": f"local_vt_{target}",
                    "type": "malicious_domain",
                    "target": target,
                    "description": f"Dominio {target} marcado como malicioso",
                    "severity": "critical",
                    "confidence": 0.95,
                    "source": "local",
                    "timestamp": datetime.datetime.now().isoformat(),
                    "metadata": {"detection_ratio": vt_data.get("detection_ratio", 0)}
                })
            
            # Analizar Shodan local
            shodan_data = scan_result.get("sources", {}).get("shodan", {})
            for vuln in shodan_data.get("vulnerabilities", []):
                threats.append({
                    "id": f"local_shodan_{target}_{vuln['name']}",
                    "type": "vulnerability",
                    "target": target,
                    "description": f"Vulnerabilidad {vuln['name']} detectada",
                    "severity": vuln.get("severity", "medium"),
                    "confidence": 0.85,
                    "source": "local",
                    "timestamp": datetime.datetime.now().isoformat(),
                    "metadata": {"vulnerability": vuln}
                })
        
        return {"threats": threats, "source": "local"}
    
    async def _analyze_virustotal(self, target: str) -> Dict:
        """Analiza usando VirusTotal API"""
        # Simulación - en implementación real usar la API
        threats = []
        
        # Simular resultado
        if target in ["malicious.com", "evil.com", "bad-actor.net"]:
            threats.append({
                "id": f"vt_{target}",
                "type": "malicious_domain",
                "target": target,
                "description": f"Dominio {target} marcado como malicioso en VirusTotal",
                "severity": "critical",
                "confidence": 0.95,
                "source": "virus_total",
                "timestamp": datetime.datetime.now().isoformat(),
                "metadata": {"detected_by": ["Kaspersky", "Norton", "McAfee"]}
            })
        
        return {"threats": threats, "source": "virus_total"}
    
    async def _analyze_shodan(self, target: str) -> Dict:
        """Analiza usando Shodan API"""
        # Simulación
        threats = []
        
        # Simular resultado
        if target in ["192.168.1.1", "10.0.0.1"]:
            threats.append({
                "id": f"shodan_{target}",
                "type": "exposed_service",
                "target": target,
                "description": f"Servicios expuestos en {target}",
                "severity": "high",
                "confidence": 0.9,
                "source": "shodan",
                "timestamp": datetime.datetime.now().isoformat(),
                "metadata": {"ports": [80, 443, 22, 3389]}
            })
        
        return {"threats": threats, "source": "shodan"}
    
    async def _analyze_censys(self, target: str) -> Dict:
        """Analiza usando Censys API"""
        # Simulación
        threats = []
        
        # Simular resultado
        if target in ["192.168.1.1", "10.0.0.1"]:
            threats.append({
                "id": f"censys_{target}",
                "type": "misconfiguration",
                "target": target,
                "description": f"Configuración incorrecta en {target}",
                "severity": "medium",
                "confidence": 0.8,
                "source": "censys",
                "timestamp": datetime.datetime.now().isoformat(),
                "metadata": {"issue": "TLS outdated"}
            })
        
        return {"threats": threats, "source": "censys"}
    
    async def _analyze_abuseipdb(self, target: str) -> Dict:
        """Analiza usando AbuseIPDB API"""
        # Simulación
        threats = []
        
        # Simular resultado
        if target in ["192.168.1.100", "10.0.0.100"]:
            threats.append({
                "id": f"abuseipdb_{target}",
                "type": "abusive_ip",
                "target": target,
                "description": f"IP {target} reportada por actividad abusiva",
                "severity": "high",
                "confidence": 0.85,
                "source": "abuse_ipdb",
                "timestamp": datetime.datetime.now().isoformat(),
                "metadata": {"abuse_score": 95}
            })
        
        return {"threats": threats, "source": "abuse_ipdb"}
    
    async def _analyze_threatfox(self, target: str) -> Dict:
        """Analiza usando ThreatFox API"""
        # Simulación
        threats = []
        
        # Simular resultado
        if target in ["malware-domain.com", "c2-server.net"]:
            threats.append({
                "id": f"threatfox_{target}",
                "type": "malware_domain",
                "target": target,
                "description": f"Dominio {target} asociado a malware",
                "severity": "critical",
                "confidence": 0.98,
                "source": "threat_fox",
                "timestamp": datetime.datetime.now().isoformat(),
                "metadata": {"malware_family": "Emotet"}
            })
        
        return {"threats": threats, "source": "threat_fox"}
    
    def _calculate_threat_score(self, threats: List[Dict]) -> float:
        """Calcula el score de amenaza"""
        if not threats:
            return 0.0
        
        score = 0.0
        weights = {"critical": 1.0, "high": 0.8, "medium": 0.5, "low": 0.2, "info": 0.0}
        
        for threat in threats:
            severity = threat.get("severity", "info")
            confidence = threat.get("confidence", 0.5)
            score += weights.get(severity, 0.0) * confidence
        
        # Normalizar
        score = score / len(threats)
        
        return max(0.0, min(1.0, score))
    
    def _determine_severity(self, score: float) -> str:
        """Determina la severidad basada en el score"""
        if score >= 0.9:
            return "critical"
        elif score >= 0.7:
            return "high"
        elif score >= 0.4:
            return "medium"
        elif score >= 0.1:
            return "low"
        else:
            return "info"
    
    async def scan_target(self, target: str) -> Dict:
        """Escanea un objetivo usando todas las fuentes"""
        return await self.analyze_target(target)
    
    async def get_current_threats(self) -> List[Dict]:
        """Obtiene las amenazas actuales de la caché"""
        return [t.to_dict() for t in self.threat_cache.values()]
    
    async def get_threat_by_id(self, threat_id: str) -> Optional[Threat]:
        """Obtiene una amenaza por ID"""
        return self.threat_cache.get(threat_id)
    
    async def get_threats_by_target(self, target: str) -> List[Threat]:
        """Obtiene amenazas por objetivo"""
        return [t for t in self.threat_cache.values() if t.target == target]
    
    async def get_threat_stats(self) -> Dict:
        """Obtiene estadísticas de amenazas"""
        severity_counts = {}
        source_counts = {}
        
        for threat in self.threat_cache.values():
            severity = threat.severity
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            source = threat.source
            source_counts[source] = source_counts.get(source, 0) + 1
        
        return {
            "total_threats": len(self.threat_cache),
            "severity_counts": severity_counts,
            "source_counts": source_counts
        }
