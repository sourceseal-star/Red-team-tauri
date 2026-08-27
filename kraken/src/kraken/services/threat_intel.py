import requests
from typing import Dict, List, Optional
from datetime import datetime
import ipaddress

from kraken.config.settings import settings
from kraken.core.logger import logger

class ThreatIntelligence:
    """Servicio de inteligencia de amenazas (Shodan, Censys, VirusTotal)."""

    def __init__(self):
        self.shodan_api_key = settings.SHODAN_API_KEY
        self.censys_api_id = settings.CENSYS_API_ID
        self.censys_api_secret = settings.CENSYS_API_SECRET
        self.virustotal_api_key = settings.VIRUSTOTAL_API_KEY

    def get_shodan_info(self, ip: str) -> Optional[Dict]:
        """Obtiene información de Shodan para una IP."""
        if not self.shodan_api_key:
            logger.warning("No se ha configurado SHODAN_API_KEY")
            return None

        url = f"https://api.shodan.io/shodan/host/{ip}"
        params = {"key": self.shodan_api_key}

        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Error consultando Shodan: {e}")
        return None

    def get_censys_info(self, ip: str) -> Optional[Dict]:
        """Obtiene información de Censys para una IP."""
        if not self.censys_api_id or not self.censys_api_secret:
            logger.warning("No se ha configurado CENSYS_API_ID o CENSYS_API_SECRET")
            return None

        url = f"https://api.censys.io/v2/hosts/{ip}"
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json"
        }
        auth = (self.censys_api_id, self.censys_api_secret)

        try:
            response = requests.get(url, headers=headers, auth=auth, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Error consultando Censys: {e}")
        return None

    def get_virustotal_info(self, ip: str) -> Optional[Dict]:
        """Obtiene información de VirusTotal para una IP."""
        if not self.virustotal_api_key:
            logger.warning("No se ha configurado VIRUSTOTAL_API_KEY")
            return None

        url = f"https://www.virustotal.com/api/v3/ip_addresses/{ip}"
        headers = {
            "x-apikey": self.virustotal_api_key,
            "accept": "application/json"
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Error consultando VirusTotal: {e}")
        return None

    def get_threat_info(self, ip: str) -> Dict:
        """Obtiene información de amenazas para una IP desde todas las fuentes."""
        result = {
            "ip": ip,
            "sources": {},
            "threats": [],
            "reputation": "unknown"
        }

        # Validar IP
        try:
            ip_obj = ipaddress.ip_address(ip)
        except:
            return result

        # Shodan
        shodan_data = self.get_shodan_info(ip)
        if shodan_data:
            result["sources"]["shodan"] = {
                "ports": list(shodan_data.get("ports", [])),
                "vulns": list(shodan_data.get("vulns", {}).keys()),
                "os": shodan_data.get("os"),
                "hostnames": shodan_data.get("hostnames", []),
                "asn": shodan_data.get("asn"),
                "isp": shodan_data.get("isp"),
                "org": shodan_data.get("org"),
                "last_update": shodan_data.get("last_update")
            }
            if shodan_data.get("vulns"):
                result["threats"].extend([
                    {"source": "shodan", "type": "vulnerability", "id": cve, "severity": "unknown"}
                    for cve in shodan_data.get("vulns", {}).keys()
                ])

        # Censys
        censys_data = self.get_censys_info(ip)
        if censys_data:
            result["sources"]["censys"] = {
                "services": censys_data.get("result", {}).get("services", []),
                "location": censys_data.get("result", {}).get("location"),
                "autonomous_system": censys_data.get("result", {}).get("autonomous_system"),
                "last_updated": censys_data.get("result", {}).get("last_updated")
            }

        # VirusTotal
        vt_data = self.get_virustotal_info(ip)
        if vt_data:
            attributes = vt_data.get("data", {}).get("attributes", {})
            result["sources"]["virustotal"] = {
                "reputation": attributes.get("reputation"),
                "malicious_votes": attributes.get("malicious_votes"),
                "suspicious_votes": attributes.get("suspicious_votes"),
                "harmless_votes": attributes.get("harmless_votes"),
                "undetected_votes": attributes.get("undetected_votes"),
                "last_analysis_results": attributes.get("last_analysis_results", {}),
                "whois": attributes.get("whois"),
                "asn": attributes.get("asn")
            }
            reputation = attributes.get("reputation", 0)
            if reputation < -50:
                result["reputation"] = "malicious"
            elif reputation < 0:
                result["reputation"] = "suspicious"
            elif reputation > 50:
                result["reputation"] = "trusted"
            else:
                result["reputation"] = "neutral"

            if attributes.get("malicious_votes", 0) > 0:
                result["threats"].append({
                    "source": "virustotal",
                    "type": "malicious",
                    "count": attributes.get("malicious_votes"),
                    "severity": "critical"
                })

        return result

    def enrich_host_data(self, host_data: Dict) -> Dict:
        """Enriquece los datos de un host con información de inteligencia de amenazas."""
        ip = host_data.get("ip")
        if not ip:
            return host_data

        threat_info = self.get_threat_info(ip)
        if threat_info.get("sources"):
            host_data["threat_intel"] = threat_info
            host_data["reputation"] = threat_info.get("reputation", "unknown")

            # Añadir vulnerabilidades de Shodan
            if "shodan" in threat_info["sources"]:
                shodan_vulns = threat_info["sources"]["shodan"].get("vulns", [])
                for vuln in shodan_vulns:
                    if vuln not in [v.get("cve") for v in host_data.get("vulnerabilities", [])]:
                        host_data.setdefault("vulnerabilities", []).append({
                            "cve": vuln,
                            "source": "shodan",
                            "severity": "unknown",
                            "cvss": 0.0
                        })

        return host_data
