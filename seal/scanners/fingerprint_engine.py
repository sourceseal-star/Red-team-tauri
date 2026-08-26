#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FINGERPRINT ENGINE - Motor de Identificación de Dispositivos
========================================================
Analiza banners y respuestas para identificar fabricantes, modelos y vulnerabilidades.

Capacidades:
- Identificación de vendor por firmas en banners
- Detección de modelos específicos
- Evaluación de riesgo por puerto
- Detección de vulnerabilidades conocidas
- Análisis de headers HTTP

Autor: Harold Paredes / SourceSeal Red Team
Uso: python3 fingerprint_engine.py [JSON_FILE]
"""

import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import argparse
import sys


# ============================================================
# BASE DE DATOS DE FINGERPRINTING
# ============================================================

# Firmas de vendors (expandido)
VENDOR_SIGNATURES = {
    # Cámaras de seguridad
    "hikvision": {
        "signatures": [
            r"hikvision", r"isapi", r"hik", r"ds-2", r"iVMS",
            r"Server: Hikvision", r"Hikvision Web Server", r"DS-2CD",
            r"Hikvision Digital", r"Hikvision Network"
        ],
        "models": {
            r"DS-2CD(\d+[A-Z]*)": "Hikvision DS-2CD Series",
            r"DS-2DE(\d+[A-Z]*)": "Hikvision DS-2DE Series",
            r"DS-2DF(\d+[A-Z]*)": "Hikvision DS-2DF Series",
        },
        "cves": ["CVE-2021-36260", "CVE-2017-17215", "CVE-2017-7945"]
    },
    "dahua": {
        "signatures": [
            r"dahua", r"dahuatech", r"Dahua", r"DH-", r"IPC",
            r"Server: Dahua", r"Dahua Web Server", r"Dahua Technology",
            r"Dahua IPC", r"Dahua NVR"
        ],
        "models": {
            r"DH-IPC-[A-Z0-9]+": "Dahua IPC Camera",
            r"DH-NVR[\d]+": "Dahua NVR",
        },
        "cves": ["CVE-2021-33044", "CVE-2021-33045", "CVE-2018-17881"]
    },
    "axis": {
        "signatures": [
            r"axis", r"AXIS", r"2100", r"2120", r"2130", r"2140",
            r"Server: AXIS", r"AXIS Communications", r"AXIS Camera",
            r"AXIS OS"
        ],
        "models": {
            r"AXIS (\w+)": "AXIS \1",
            r"21[0-9]{2}": "AXIS 21xx Series",
        },
        "cves": ["CVE-2018-10660", "CVE-2018-10661"]
    },
    "uniview": {
        "signatures": [
            r"uniview", r"UNIVIEW", r"UniView", r"NVR", r"IPC",
            r"Server: UniView", r"UniView Technologies", r"UNV"
        ],
        "models": {},
        "cves": []
    },
    "honeywell": {
        "signatures": [
            r"honeywell", r"Honeywell", r"Performance Series",
            r"Pro-Watch", r"Honeywell Security"
        ],
        "models": {},
        "cves": []
    },
    "bosch": {
        "signatures": [
            r"bosch", r"BOSCH", r"Bosch Security", r"VIP",
            r"Bosch Video", r"BIS"
        ],
        "models": {},
        "cves": []
    },
    
    # Routers
    "tenda": {
        "signatures": [
            r"tenda", r"Tenda", r"AC5", r"AC6", r"AC10", r"AC15",
            r"Server: Tenda", r"Tenda Technology", r"Tenda Wireless",
            r"Tenda Nova", r"Tenda UH"
        ],
        "models": {
            r"AC(\d+)": "Tenda AC\1",
            r"A(\d+)": "Tenda A\1",
            r"F(\d+)": "Tenda F\1",
        },
        "cves": ["CVE-2020-10987", "CVE-2018-14558"]
    },
    "tp-link": {
        "signatures": [
            r"tp-link", r"TP-Link", r"Archer", r"TL-WR", r"TL-MR",
            r"Server: TP-LINK", r"TP-LINK Technologies", r"TP-Link Wireless",
            r"TL-WDR", r"TL-WA", r"Archer C", r"Archer A"
        ],
        "models": {
            r"Archer C(\d+)": "TP-Link Archer C\1",
            r"Archer A(\d+)": "TP-Link Archer A\1",
            r"TL-WR(\d+)": "TP-Link TL-WR\1",
        },
        "cves": ["CVE-2021-41653", "CVE-2020-10879"]
    },
    "asus": {
        "signatures": [
            r"asus", r"ASUS", r"RT-AC", r"RT-AX", r"RT-N",
            r"Server: ASUS", r"ASUSTek", r"ASUS Wireless",
            r"ASUS Router", r"RT-AC5", r"RT-AC6", r"RT-AX8"
        ],
        "models": {
            r"RT-AC(\d+)": "ASUS RT-AC\1",
            r"RT-AX(\d+)": "ASUS RT-AX\1",
            r"RT-N(\d+)": "ASUS RT-N\1",
        },
        "cves": ["CVE-2018-5999", "CVE-2017-17215"]
    },
    "netgear": {
        "signatures": [
            r"netgear", r"NETGEAR", r"R6", r"R7", r"R8",
            r"Server: NETGEAR", r"NETGEAR Router"
        ],
        "models": {
            r"R(\d+)": "NETGEAR R\1",
        },
        "cves": ["CVE-2017-17215", "CVE-2016-6277"]
    },
    "linksys": {
        "signatures": [
            r"linksys", r"Linksys", r"EA", r"WRT",
            r"Server: Linksys", r"Linksys Router"
        ],
        "models": {
            r"WRT(\d+)": "Linksys WRT\1",
            r"EA(\d+)": "Linksys EA\1",
        },
        "cves": []
    },
    "mercury": {
        "signatures": [
            r"mercury", r"Mercury", r"DW", r"Mercusys",
            r"Server: Mercury", r"Mercury Router"
        ],
        "models": {},
        "cves": []
    },
    
    # DVRs/NVRs
    "xiongmai": {
        "signatures": [
            r"xm", r"Xiongmai", r"XM", r"Goolink", r"Goke",
            r"XMeye", r"Xiongmai"
        ],
        "models": {},
        "cves": ["CVE-2016-6277", "CVE-2017-17215"]
    },
    "lorex": {
        "signatures": [
            r"lorex", r"Lorex", r"LH", r"LNR",
            r"Lorex Technology", r"Lorex Security"
        ],
        "models": {},
        "cves": []
    },
    "swann": {
        "signatures": [
            r"swann", r"Swann", r"SWV",
            r"Swann Security"
        ],
        "models": {},
        "cves": []
    },
    "annke": {
        "signatures": [
            r"annke", r"Annke", r"I61",
            r"Annke Security"
        ],
        "models": {},
        "cves": []
    },
    
    # IoT
    "xiaomi": {
        "signatures": [
            r"xiaomi", r"mi", r"Mi Camera", r"Mi Home", r"Mi WiFi",
            r"Server: nginx/1.8.0", r"Xiaomi", r"MiJia",
            r"Xiaomi Router"
        ],
        "models": {
            r"Mi (\w+)": "Xiaomi Mi \1",
        },
        "cves": []
    },
    "ezviz": {
        "signatures": [
            r"ezviz", r"EZVIZ", r"CS-",
            r"EZVIZ Security", r"EZVIZ Camera"
        ],
        "models": {},
        "cves": []
    },
    
    # Servidores
    "nginx": {
        "signatures": [r"nginx", r"nginx/", r"Server: nginx"],
        "models": {},
        "cves": []
    },
    "apache": {
        "signatures": [r"apache", r"Apache", r"Server: Apache"],
        "models": {},
        "cves": []
    },
    "iis": {
        "signatures": [r"IIS", r"Microsoft-IIS", r"Server: Microsoft-IIS"],
        "models": {},
        "cves": []
    },
    "tomcat": {
        "signatures": [r"tomcat", r"Apache-Coyote", r"Server: Apache-Coyote"],
        "models": {},
        "cves": []
    },
}

# Información de puertos
PORT_INFO = {
    21: {"service": "FTP", "risk": "medium", "category": "file_transfer"},
    22: {"service": "SSH", "risk": "low", "category": "remote_access"},
    23: {"service": "Telnet", "risk": "critical", "category": "remote_access"},
    25: {"service": "SMTP", "risk": "medium", "category": "email"},
    53: {"service": "DNS", "risk": "medium", "category": "network"},
    80: {"service": "HTTP", "risk": "low", "category": "web"},
    443: {"service": "HTTPS", "risk": "low", "category": "web"},
    554: {"service": "RTSP", "risk": "medium", "category": "streaming"},
    1935: {"service": "RTMP", "risk": "medium", "category": "streaming"},
    8000: {"service": "HTTP-Alt", "risk": "low", "category": "web"},
    8080: {"service": "HTTP-Proxy", "risk": "low", "category": "web"},
    8081: {"service": "HTTP-Alt", "risk": "low", "category": "web"},
    8082: {"service": "HTTP-Alt", "risk": "low", "category": "web"},
    8443: {"service": "HTTPS-Alt", "risk": "low", "category": "web"},
    7547: {"service": "TR-069", "risk": "high", "category": "management"},
    3389: {"service": "RDP", "risk": "critical", "category": "remote_access"},
    3702: {"service": "ONVIF-WS", "risk": "low", "category": "camera"},
    8008: {"service": "HTTP-Alt", "risk": "low", "category": "web"},
    8088: {"service": "HTTP-Alt", "risk": "low", "category": "web"},
    8888: {"service": "HTTP-Alt", "risk": "low", "category": "web"},
}


# ============================================================
# MOTOR DE FINGERPRINTING
# ============================================================

class FingerprintEngine:
    """Motor de identificación de dispositivos."""
    
    def __init__(self):
        self.vendor_signatures = VENDOR_SIGNATURES
        self.port_info = PORT_INFO
    
    def identify(self, banner: Optional[str] = None, port: Optional[int] = None, 
                headers: Optional[Dict] = None, ip: str = "unknown") -> Dict:
        """
        Identifica un dispositivo basado en banner, puerto y headers.
        
        Args:
            banner: Banner HTTP o del servicio
            port: Puerto del servicio
            headers: Headers HTTP
            ip: IP del dispositivo
            
        Returns:
            Diccionario con información del dispositivo
        """
        result = {
            "ip": ip,
            "port": port,
            "vendor": "Unknown",
            "type": "Unknown",
            "model": "Unknown",
            "os": "Unknown",
            "risk": "low",
            "category": "unknown",
            "cves": [],
            "confidence": 0,
            "evidence": []
        }
        
        # 1. Identificar por banner
        if banner:
            vendor_info = self._identify_by_banner(banner)
            result.update(vendor_info)
        
        # 2. Identificar por puerto
        if port:
            port_info = self._identify_by_port(port)
            if port_info.get("vendor") != "Unknown":
                result.update(port_info)
        
        # 3. Identificar por headers
        if headers:
            header_info = self._identify_by_headers(headers)
            if header_info.get("vendor") != "Unknown":
                result.update(header_info)
        
        # 4. Determinar tipo si no se ha identificado
        if result["type"] == "Unknown":
            result["type"] = self._determine_type(banner, port, headers)
        
        # 5. Determinar OS si no se ha identificado
        if result["os"] == "Unknown":
            result["os"] = self._determine_os(banner, headers)
        
        # 6. Determinar riesgo
        result["risk"] = self._determine_risk(result)
        
        return result
    
    def _identify_by_banner(self, banner: str) -> Dict:
        """Identifica por banner."""
        result = {
            "vendor": "Unknown",
            "model": "Unknown",
            "cves": [],
            "evidence": []
        }
        
        banner_lower = banner.lower()
        
        # Buscar por vendor
        for vendor, info in self.vendor_signatures.items():
            for signature in info["signatures"]:
                if re.search(signature, banner_lower, re.I):
                    result["vendor"] = vendor.capitalize()
                    result["cves"] = info.get("cves", [])
                    result["evidence"].append(f"Banner match: {signature}")
                    
                    # Buscar modelo
                    for model_pattern, model_name in info.get("models", {}).items():
                        model_match = re.search(model_pattern, banner, re.I)
                        if model_match:
                            result["model"] = model_name
                            if model_match.groups():
                                result["model"] = model_name.replace("\1", model_match.group(1))
                            result["evidence"].append(f"Model match: {model_pattern}")
                            break
                    
                    return result
        
        return result
    
    def _identify_by_port(self, port: int) -> Dict:
        """Identifica por puerto."""
        result = {
            "service": "Unknown",
            "category": "unknown",
            "risk": "low"
        }
        
        if port in self.port_info:
            result.update(self.port_info[port])
        
        return result
    
    def _identify_by_headers(self, headers: Dict) -> Dict:
        """Identifica por headers HTTP."""
        result = {
            "vendor": "Unknown",
            "os": "Unknown",
            "evidence": []
        }
        
        # Verificar Server header
        server = headers.get("Server", "").lower()
        if server:
            for vendor, info in self.vendor_signatures.items():
                for signature in info["signatures"]:
                    if re.search(signature, server, re.I):
                        result["vendor"] = vendor.capitalize()
                        result["evidence"].append(f"Server header match: {signature}")
                        return result
        
        # Verificar X-Powered-By
        powered_by = headers.get("X-Powered-By", "").lower()
        if powered_by:
            for vendor, info in self.vendor_signatures.items():
                for signature in info["signatures"]:
                    if re.search(signature, powered_by, re.I):
                        result["vendor"] = vendor.capitalize()
                        result["evidence"].append(f"X-Powered-By match: {signature}")
                        return result
        
        return result
    
    def _determine_type(self, banner: Optional[str], port: Optional[int], 
                       headers: Optional[Dict]) -> str:
        """Determina el tipo de dispositivo."""
        if not banner and not port and not headers:
            return "Unknown"
        
        banner_lower = (banner or "").lower()
        
        # Por banner
        if "camera" in banner_lower or "ip camera" in banner_lower:
            return "Camera"
        if "nvr" in banner_lower or "dvr" in banner_lower:
            return "DVR/NVR"
        if "router" in banner_lower or "gateway" in banner_lower or "wireless" in banner_lower:
            return "Router"
        if "switch" in banner_lower:
            return "Switch"
        if "printer" in banner_lower:
            return "Printer"
        if "nas" in banner_lower or "storage" in banner_lower:
            return "NAS/Storage"
        if "iot" in banner_lower or "smart" in banner_lower:
            return "IoT Device"
        if "server" in banner_lower or "web server" in banner_lower:
            return "Server"
        
        # Por puerto
        if port:
            if port == 554:
                return "Camera"
            if port == 3702:
                return "Camera"
            if port == 7547:
                return "Router"
            if port == 3389:
                return "Remote Access"
        
        return "Unknown"
    
    def _determine_os(self, banner: Optional[str], headers: Optional[Dict]) -> str:
        """Determina el sistema operativo."""
        if not banner and not headers:
            return "Unknown"
        
        banner_lower = (banner or "").lower()
        
        # Por banner
        if "linux" in banner_lower:
            return "Linux"
        if "busybox" in banner_lower:
            return "BusyBox (Embedded Linux)"
        if "windows" in banner_lower:
            return "Windows"
        if "mikrotik" in banner_lower or "routeros" in banner_lower:
            return "MikroTik RouterOS"
        if "embedded" in banner_lower:
            return "Embedded OS"
        if "unix" in banner_lower:
            return "Unix"
        
        # Por headers
        if headers:
            server = headers.get("Server", "").lower()
            if "linux" in server:
                return "Linux"
            if "windows" in server:
                return "Windows"
        
        return "Unknown"
    
    def _determine_risk(self, result: Dict) -> str:
        """Determina el nivel de riesgo."""
        # Riesgo por puerto
        if result.get("port") in self.port_info:
            port_risk = self.port_info[result["port"]].get("risk", "low")
            if port_risk in ["critical", "high"]:
                return port_risk
        
        # Riesgo por CVE
        if result.get("cves"):
            return "high"
        
        # Riesgo por vendor
        if result.get("vendor") != "Unknown":
            vendor_lower = result["vendor"].lower()
            if vendor_lower in ["hikvision", "dahua", "xiongmai", "tenda"]:
                return "high"
        
        return "low"
    
    def analyze_bulk(self, targets: List[Dict]) -> List[Dict]:
        """Analiza múltiples objetivos."""
        results = []
        for target in targets:
            result = self.identify(
                banner=target.get("banner"),
                port=target.get("port"),
                headers=target.get("headers"),
                ip=target.get("ip", "unknown")
            )
            results.append(result)
        return results


# ============================================================
# ANÁLISIS DE VULNERABILIDADES
# ============================================================

class VulnerabilityAnalyzer:
    """Analiza vulnerabilidades conocidas."""
    
    def __init__(self):
        self.vulnerability_db = self._load_vulnerability_db()
    
    def _load_vulnerability_db(self) -> Dict:
        """Carga la base de datos de vulnerabilidades."""
        return {
            "CVE-2021-36260": {
                "name": "Hikvision Authentication Bypass",
                "vendor": "hikvision",
                "severity": "critical",
                "description": "Authentication bypass vulnerability in Hikvision firmware <V5.5.80",
                "affected_versions": ["<V5.5.80"],
                "solution": "Update firmware to V5.5.80 or later"
            },
            "CVE-2021-33044": {
                "name": "Dahua Remote Code Execution",
                "vendor": "dahua",
                "severity": "critical",
                "description": "Remote code execution vulnerability in Dahua devices",
                "affected_versions": ["Multiple"],
                "solution": "Update to latest firmware"
            },
            "CVE-2017-17215": {
                "name": " Mirai Botnet Vulnerability",
                "vendor": ["xiongmai", "dahua", "hikvision"],
                "severity": "critical",
                "description": "Vulnerability exploited by Mirai botnet",
                "affected_versions": ["Multiple"],
                "solution": "Update firmware and change default credentials"
            },
            "CVE-2018-17881": {
                "name": "Dahua Backdoor",
                "vendor": "dahua",
                "severity": "critical",
                "description": "Backdoor account in Dahua devices",
                "affected_versions": ["Multiple"],
                "solution": "Update firmware"
            },
            "CVE-2020-10987": {
                "name": "Tenda Router RCE",
                "vendor": "tenda",
                "severity": "critical",
                "description": "Remote code execution in Tenda routers",
                "affected_versions": ["AC15", "AC18"],
                "solution": "Update firmware"
            },
            "CVE-2018-14558": {
                "name": "Tenda Authentication Bypass",
                "vendor": "tenda",
                "severity": "high",
                "description": "Authentication bypass in Tenda routers",
                "affected_versions": ["AC15", "AC18"],
                "solution": "Update firmware"
            },
        }
    
    def check_vulnerabilities(self, vendor: str, model: str = "", 
                              firmware: str = "") -> List[Dict]:
        """Verifica vulnerabilidades conocidas para un dispositivo."""
        vulnerabilities = []
        
        vendor_lower = vendor.lower()
        
        for cve, info in self.vulnerability_db.items():
            # Verificar por vendor
            if isinstance(info.get("vendor"), list):
                if vendor_lower in [v.lower() for v in info["vendor"]]:
                    vulnerabilities.append({"cve": cve, **info})
            elif info.get("vendor", "").lower() == vendor_lower:
                vulnerabilities.append({"cve": cve, **info})
            
            # Verificar por modelo (si está disponible)
            if model:
                model_lower = model.lower()
                if "affected_models" in info:
                    if model_lower in [m.lower() for m in info["affected_models"]]:
                        vulnerabilities.append({"cve": cve, **info})
        
        return vulnerabilities


# ============================================================
# PRINCIPAL
# ============================================================

def main():
    """Función principal."""
    parser = argparse.ArgumentParser(
        description="Fingerprint Engine - Identificación de dispositivos"
    )
    parser.add_argument("file", nargs="?", help="Archivo JSON con resultados de escaneo")
    
    args = parser.parse_args()
    
    engine = FingerprintEngine()
    vuln_analyzer = VulnerabilityAnalyzer()
    
    if args.file:
        # Cargar archivo JSON
        with open(args.file, 'r') as f:
            data = json.load(f)
        
        # Analizar targets
        if "targets" in data:
            print(f"Analizando {len(data['targets'])} objetivos...")
            
            results = []
            for target in data["targets"]:
                # Analizar cada servicio
                for service in target.get("services", []):
                    fp_result = engine.identify(
                        banner=service.get("banner"),
                        port=service.get("port"),
                        ip=target.get("ip")
                    )
                    
                    # Verificar vulnerabilidades
                    if fp_result.get("vendor") != "Unknown":
                        fp_result["vulnerabilities"] = vuln_analyzer.check_vulnerabilities(
                            fp_result["vendor"],
                            fp_result.get("model", "")
                        )
                    
                    results.append({
                        "ip": target.get("ip"),
                        "port": service.get("port"),
                        "service": service.get("service"),
                        "fingerprint": fp_result
                    })
            
            # Guardar resultados
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"fingerprint_results_{timestamp}.json"
            
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Resultados guardados en: {output_file}")
            
            # Mostrar resumen
            print("\n" + "="*70)
            print("  📊 RESUMEN DE IDENTIFICACIÓN")
            print("="*70)
            
            vendors = {}
            types = {}
            risks = {"low": 0, "medium": 0, "high": 0, "critical": 0}
            
            for r in results:
                fp = r["fingerprint"]
                vendor = fp.get("vendor", "Unknown")
                device_type = fp.get("type", "Unknown")
                risk = fp.get("risk", "low")
                
                vendors[vendor] = vendors.get(vendor, 0) + 1
                types[device_type] = types.get(device_type, 0) + 1
                risks[risk] = risks.get(risk, 0) + 1
            
            print(f"\n🏭 Por fabricante:")
            for vendor, count in sorted(vendors.items(), key=lambda x: x[1], reverse=True):
                print(f"  {vendor:15} : {count}")
            
            print(f"\n🏷️  Por tipo:")
            for device_type, count in sorted(types.items(), key=lambda x: x[1], reverse=True):
                print(f"  {device_type:15} : {count}")
            
            print(f"\n⚠️  Por riesgo:")
            for risk, count in sorted(risks.items(), key=lambda x: x[0]):
                print(f"  {risk.upper():10} : {count}")
        else:
            print("❌ Formato de archivo no válido")
    else:
        # Modo interactivo
        print("Fingerprint Engine - Modo interactivo")
        print("Ingresa el banner o presiona Enter para salir:")
        
        while True:
            banner = input("\nBanner: ").strip()
            if not banner:
                break
            
            port_input = input("Puerto (opcional): ").strip()
            port = int(port_input) if port_input else None
            
            result = engine.identify(banner=banner, port=port)
            
            print("\nResultado:")
            for key, value in result.items():
                print(f"  {key}: {value}")
            
            # Verificar vulnerabilidades
            if result.get("vendor") != "Unknown":
                vulns = vuln_analyzer.check_vulnerabilities(result["vendor"])
                if vulns:
                    print(f"\n  ⚠️  Vulnerabilidades: {len(vulns)}")
                    for vuln in vulns:
                        print(f"    - {vuln['cve']}: {vuln['name']} ({vuln['severity'].upper()})")


if __name__ == "__main__":
    main()
