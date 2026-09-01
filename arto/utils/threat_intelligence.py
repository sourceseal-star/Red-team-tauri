"""
Threat Intelligence - Inteligencia de Amenazas
==============================================
Recopila y analiza información de amenazas de múltiples fuentes reales.
Carga API keys desde variables de entorno (.env).
"""

import asyncio
import datetime
import json
import os
import ipaddress
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

try:
    import aiohttp
except ImportError:
    aiohttp = None


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
    """Inteligencia de Amenazas con APIs reales"""
    
    def __init__(self):
        self.sources: Dict[str, Dict] = {
            "local": {"enabled": True, "priority": 10},
            "virus_total": {"enabled": True, "priority": 9, "api_key": None},
            "shodan": {"enabled": True, "priority": 8, "api_key": None},
            "censys": {"enabled": True, "priority": 7, "api_id": None, "api_secret": None},
            "abuse_ipdb": {"enabled": True, "priority": 6, "api_key": None},
            "threat_fox": {"enabled": True, "priority": 5, "api_key": None}
        }
        self.threat_cache: Dict[str, Threat] = {}
        self.cache_expiry = datetime.timedelta(hours=1)
        self.initialized = False
        
    async def initialize(self):
        """Inicializa el módulo de inteligencia de amenazas"""
        print("🎯 Inicializando Threat Intelligence...")
        await self._load_configuration()
        self.initialized = True
        
        # Reportar qué fuentes tienen API keys
        configured = [s for s, c in self.sources.items() if s == "local" or c.get("api_key") or c.get("api_id")]
        unconfigured = [s for s, c in self.sources.items() if s != "local" and not (c.get("api_key") or c.get("api_id"))]
        if configured:
            print(f"  ✅ Fuentes con API key: {', '.join(configured)}")
        if unconfigured:
            print(f"  ⚠️  Fuentes sin API key (simulación): {', '.join(unconfigured)}")
        print("✅ Threat Intelligence listo")
    
    async def _load_configuration(self):
        """Carga las API keys desde las variables de entorno (.env)"""
        # VirusTotal
        vt_key = os.environ.get("VIRUSTOTAL_API_KEY", "").strip()
        self.sources["virus_total"]["api_key"] = vt_key or None
        if not vt_key:
            self.sources["virus_total"]["enabled"] = False
        
        # Shodan
        shodan_key = os.environ.get("SHODAN_API_KEY", "").strip()
        self.sources["shodan"]["api_key"] = shodan_key or None
        if not shodan_key:
            self.sources["shodan"]["enabled"] = False
        
        # Censys (usa ID + Secret)
        censys_id = os.environ.get("CENSYS_API_ID", "").strip()
        censys_secret = os.environ.get("CENSYS_API_SECRET", "").strip()
        self.sources["censys"]["api_id"] = censys_id or None
        self.sources["censys"]["api_secret"] = censys_secret or None
        if not censys_id or not censys_secret:
            self.sources["censys"]["enabled"] = False
        
        # AbuseIPDB
        abuse_key = os.environ.get("ABUSEIPDB_KEY", "").strip()
        self.sources["abuse_ipdb"]["api_key"] = abuse_key or None
        if not abuse_key:
            self.sources["abuse_ipdb"]["enabled"] = False
        
        # ThreatFox (no requiere API key — API pública gratuita)
        # https://threatfox.abuse.ch/api/ — pública, sin autenticación
    
    def _is_ip(self, target: str) -> bool:
        """Determina si el target es una IP o un dominio"""
        try:
            ipaddress.ip_address(target)
            return True
        except ValueError:
            return False
    
    async def analyze_target(self, target: str, scan_result: Optional[Dict] = None) -> Dict:
        """Analiza un objetivo en busca de amenazas usando todas las fuentes activas."""
        analysis = {
            "target": target,
            "timestamp": datetime.datetime.now().isoformat(),
            "threats": [],
            "threat_score": 0.0,
            "severity": "info",
            "sources_checked": []
        }
        
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
        
        analysis["threat_score"] = self._calculate_threat_score(analysis["threats"])
        analysis["severity"] = self._determine_severity(analysis["threat_score"])
        
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
        """Analiza usando datos locales del escaneo previo"""
        threats = []
        if scan_result:
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
        """Analiza usando VirusTotal API v3 (real)"""
        api_key = self.sources["virus_total"].get("api_key")
        if not api_key:
            return {"threats": [], "source": "virus_total"}
        
        is_ip = self._is_ip(target)
        if aiohttp is None:
            return {"threats": [], "source": "virus_total"}
        
        url = f"https://www.virustotal.com/api/v3/{'ip_addresses' if is_ip else 'domains'}/{target}"
        headers = {"x-apikey": api_key, "accept": "application/json"}
        threats = []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        return {"threats": [], "source": "virus_total"}
                    data = await resp.json()
                    attrs = data.get("data", {}).get("attributes", {})
                    last_analysis = attrs.get("last_analysis_stats", {})
                    malicious = last_analysis.get("malicious", 0)
                    suspicious = last_analysis.get("suspicious", 0)
                    total = sum(last_analysis.values())
                    
                    if malicious > 0:
                        severity = "critical" if malicious >= 5 else "high"
                        threats.append({
                            "id": f"vt_{target}",
                            "type": "malicious_indicator" if is_ip else "malicious_domain",
                            "target": target,
                            "description": f"{target} detectado por {malicious}/{total} engines en VirusTotal",
                            "severity": severity,
                            "confidence": min(0.95, 0.5 + malicious / max(total, 1) * 0.5),
                            "source": "virus_total",
                            "timestamp": datetime.datetime.now().isoformat(),
                            "metadata": {"malicious": malicious, "suspicious": suspicious, "total": total}
                        })
                    elif suspicious > 0:
                        threats.append({
                            "id": f"vt_{target}",
                            "type": "suspicious_indicator",
                            "target": target,
                            "description": f"{target} marcado como sospechoso por {suspicious} engines",
                            "severity": "medium",
                            "confidence": 0.6,
                            "source": "virus_total",
                            "timestamp": datetime.datetime.now().isoformat(),
                            "metadata": {"suspicious": suspicious, "total": total}
                        })
        except asyncio.TimeoutError:
            print("  ⚠️ VirusTotal: timeout")
        except Exception as e:
            print(f"  ⚠️ VirusTotal: {e}")
        
        return {"threats": threats, "source": "virus_total"}
    
    async def _analyze_shodan(self, target: str) -> Dict:
        """Analiza usando Shodan API (real)"""
        api_key = self.sources["shodan"].get("api_key")
        if not api_key or aiohttp is None:
            return {"threats": [], "source": "shodan"}
        
        is_ip = self._is_ip(target)
        threats = []
        
        try:
            if is_ip:
                # Shodan host lookup para IPs
                url = f"https://api.shodan.io/shodan/host/{target}?key={api_key}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        if resp.status == 404:
                            return {"threats": [], "source": "shodan"}
                        if resp.status != 200:
                            return {"threats": [], "source": "shodan"}
                        data = await resp.json()
                        
                        # Puertos expuestos
                        ports = data.get("ports", [])
                        if len(ports) > 5:
                            threats.append({
                                "id": f"shodan_{target}_exposed",
                                "type": "exposed_services",
                                "target": target,
                                "description": f"{len(ports)} puertos expuestos en {target}: {', '.join(map(str, ports[:10]))}",
                                "severity": "high" if len(ports) > 10 else "medium",
                                "confidence": 0.9,
                                "source": "shodan",
                                "timestamp": datetime.datetime.now().isoformat(),
                                "metadata": {"ports": ports, "country": data.get("country_name"), "org": data.get("org")}
                            })
                        
                        # Vulnerabilidades conocidas
                        vulns = data.get("vulns", [])
                        for v in vulns[:10]:
                            threats.append({
                                "id": f"shodan_{target}_vuln_{v}",
                                "type": "vulnerability",
                                "target": target,
                                "description": f"Vulnerabilidad {v} detectada en {target}",
                                "severity": "high",
                                "confidence": 0.85,
                                "source": "shodan",
                                "timestamp": datetime.datetime.now().isoformat(),
                                "metadata": {"cve": v}
                            })
            else:
                # Shodan dns-domain lookup para dominios
                url = f"https://api.shodan.io/dns/domain/{target}?key={api_key}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        if resp.status != 200:
                            return {"threats": [], "source": "shodan"}
                        data = await resp.json()
                        subdomains = data.get("subdomains", [])
                        if len(subdomains) > 0:
                            threats.append({
                                "id": f"shodan_dns_{target}",
                                "type": "dns_exposure",
                                "target": target,
                                "description": f"{len(subdomains)} subdominios encontrados en Shodan para {target}",
                                "severity": "info",
                                "confidence": 0.7,
                                "source": "shodan",
                                "timestamp": datetime.datetime.now().isoformat(),
                                "metadata": {"subdomain_count": len(subdomains)}
                            })
        except asyncio.TimeoutError:
            print("  ⚠️ Shodan: timeout")
        except Exception as e:
            print(f"  ⚠️ Shodan: {e}")
        
        return {"threats": threats, "source": "shodan"}
    
    async def _analyze_censys(self, target: str) -> Dict:
        """Analiza usando Censys API v2 (real)"""
        api_id = self.sources["censys"].get("api_id")
        api_secret = self.sources["censys"].get("api_secret")
        if not api_id or not api_secret or aiohttp is None:
            return {"threats": [], "source": "censys"}
        
        is_ip = self._is_ip(target)
        threats = []
        
        try:
            # Censys Search API v2
            auth = (api_id, api_secret)
            if is_ip:
                url = "https://search.censys.io/api/v2/hosts/search"
                query = f"ip: {target}"
            else:
                url = "https://search.censys.io/api/v2/hosts/search"
                query = f"services.tls.certificates.leaf_data.subject.common_name: {target}"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={"q": query, "per_page": 25}, 
                                        auth=aiohttp.BasicAuth(api_id, api_secret),
                                        timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        return {"threats": [], "source": "censys"}
                    data = await resp.json()
                    hits = data.get("result", {}).get("hits", [])
                    if hits:
                        services_count = sum(len(h.get("services", [])) for h in hits)
                        if services_count > 5:
                            threats.append({
                                "id": f"censys_{target}",
                                "type": "exposed_services",
                                "target": target,
                                "description": f"Censys detectó {services_count} servicios expuestos en {target}",
                                "severity": "medium",
                                "confidence": 0.8,
                                "source": "censys",
                                "timestamp": datetime.datetime.now().isoformat(),
                                "metadata": {"hosts_count": len(hits), "services_count": services_count}
                            })
        except asyncio.TimeoutError:
            print("  ⚠️ Censys: timeout")
        except Exception as e:
            print(f"  ⚠️ Censys: {e}")
        
        return {"threats": threats, "source": "censys"}
    
    async def _analyze_abuseipdb(self, target: str) -> Dict:
        """Analiza usando AbuseIPDB API v2 (real)"""
        api_key = self.sources["abuse_ipdb"].get("api_key")
        if not api_key or aiohttp is None:
            return {"threats": [], "source": "abuse_ipdb"}
        
        if not self._is_ip(target):
            return {"threats": [], "source": "abuse_ipdb"}  # AbuseIPDB solo funciona con IPs
        
        url = "https://api.abuseipdb.com/api/v2/check"
        headers = {"Key": api_key, "Accept": "application/json"}
        params = {"ipAddress": target, "maxAgeInDays": 90}
        threats = []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params,
                                      timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        return {"threats": [], "source": "abuse_ipdb"}
                    data = await resp.json()
                    abuse_score = data.get("data", {}).get("abuseConfidenceScore", 0)
                    
                    if abuse_score >= 50:
                        threats.append({
                            "id": f"abuseipdb_{target}",
                            "type": "abusive_ip",
                            "target": target,
                            "description": f"IP {target} tiene score de abuso {abuse_score}% en AbuseIPDB",
                            "severity": "critical" if abuse_score >= 75 else "high",
                            "confidence": abuse_score / 100,
                            "source": "abuse_ipdb",
                            "timestamp": datetime.datetime.now().isoformat(),
                            "metadata": {"abuse_score": abuse_score, "country": data.get("data", {}).get("countryCode")}
                        })
                    elif abuse_score > 0:
                        threats.append({
                            "id": f"abuseipdb_{target}",
                            "type": "abusive_ip",
                            "target": target,
                            "description": f"IP {target} reportada con score {abuse_score}% en AbuseIPDB",
                            "severity": "low",
                            "confidence": abuse_score / 100,
                            "source": "abuse_ipdb",
                            "timestamp": datetime.datetime.now().isoformat(),
                            "metadata": {"abuse_score": abuse_score}
                        })
        except asyncio.TimeoutError:
            print("  ⚠️ AbuseIPDB: timeout")
        except Exception as e:
            print(f"  ⚠️ AbuseIPDB: {e}")
        
        return {"threats": threats, "source": "abuse_ipdb"}
    
    async def _analyze_threatfox(self, target: str) -> Dict:
        """Analiza usando ThreatFox API (pública, sin API key)"""
        if aiohttp is None:
            return {"threats": [], "source": "threat_fox"}
        
        threats = []
        try:
            url = "https://threatfox-api.abuse.ch/api/v1/"
            payload = {"query": "search_ioc", "search_term": target}
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload,
                                       timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        return {"threats": [], "source": "threat_fox"}
                    data = await resp.json()
                    iocs = data.get("data", [])
                    for ioc in iocs[:5]:
                        threats.append({
                            "id": f"threatfox_{target}_{ioc.get('id', '')}",
                            "type": "malware_indicator",
                            "target": target,
                            "description": f"IOC en ThreatFox: {ioc.get('ioc_type', 'unknown')} — {ioc.get('malware', 'unknown')}",
                            "severity": "critical" if ioc.get("confidence_level") == "100" else "high",
                            "confidence": int(ioc.get("confidence_level", 50)) / 100,
                            "source": "threat_fox",
                            "timestamp": datetime.datetime.now().isoformat(),
                            "metadata": {"malware": ioc.get("malware"), "threat_type": ioc.get("threat_type")}
                        })
        except asyncio.TimeoutError:
            print("  ⚠️ ThreatFox: timeout")
        except Exception as e:
            print(f"  ⚠️ ThreatFox: {e}")
        
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
