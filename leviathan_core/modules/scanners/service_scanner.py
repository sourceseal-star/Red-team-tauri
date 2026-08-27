#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SERVICE SCANNER - Escaneo de Servicios
======================================
Escaneo de puertos y servicios en un objetivo.

Autor: Harold Paredes / SourceSeal Red Team
"""

import asyncio
import socket
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field


@dataclass
class ServiceInfo:
    """Información de un servicio."""
    port: int
    protocol: str = "tcp"
    service_name: Optional[str] = None
    banner: Optional[str] = None
    is_open: bool = False
    version: Optional[str] = None
    product: Optional[str] = None


class ServiceScanner:
    """Scanner de servicios."""
    
    def __init__(self):
        self.name = "service_scanner"
        self.category = "scanner"
        self.description = "Escaneo de puertos y servicios"
        self.author = "Harold Paredes"
        self.version = "3.0.0"
        
        # Puertos comunes
        self.common_ports = [
            21, 22, 23, 25, 53, 80, 110, 139, 143, 443, 445, 465, 587,
            993, 995, 1433, 1521, 1723, 3306, 3389, 5432, 5900, 6379,
            8000, 8008, 8080, 8081, 8443, 8554, 8888, 9000, 9200, 9300,
            37777, 3702
        ]
        
        # Mapeo de puertos a servicios
        self.port_to_service = {
            21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP",
            53: "DNS", 80: "HTTP", 110: "POP3", 139: "NetBIOS",
            143: "IMAP", 443: "HTTPS", 445: "SMB", 465: "SMTPS",
            587: "SMTP-Submission", 993: "IMAPS", 995: "POP3S",
            1433: "MSSQL", 1521: "Oracle", 1723: "PPTP",
            3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL",
            5900: "VNC", 6379: "Redis", 8000: "HTTP-Alt",
            8080: "HTTP-Proxy", 8443: "HTTPS-Alt", 8554: "RTSP-Alt",
            8888: "HTTP-Alt", 9000: "Portainer", 9200: "Elasticsearch",
            9300: "Elasticsearch-Transport", 37777: "Camera", 3702: "WS-Discovery"
        }
        
    def is_applicable(self, target: str, context: Dict = None) -> bool:
        """Verifica si el scanner es aplicable al objetivo."""
        return True
    
    async def scan(self, target: str, context: Dict = None) -> Dict:
        """
        Escanea un objetivo en busca de servicios abiertos.
        
        Args:
            target: IP o hostname a escanear
            context: Contexto adicional
            
        Returns:
            Diccionario con resultados del escaneo
        """
        context = context or {}
        ports = context.get("ports", self.common_ports)
        
        results = {
            "target": target,
            "services": [],
            "statistics": {
                "total_ports": len(ports),
                "open_ports": 0,
                "scan_duration": 0.0
            },
            "success": False,
            "error": None
        }
        
        try:
            import time
            start_time = time.time()
            
            # Escanear puertos
            open_services = await self._scan_ports(target, ports, context)
            
            results["services"] = [s.to_dict() for s in open_services]
            results["statistics"]["open_ports"] = len(open_services)
            results["statistics"]["scan_duration"] = time.time() - start_time
            results["success"] = True
            
            return results
            
        except Exception as e:
            results["error"] = str(e)
            return results
    
    async def _scan_ports(self, ip: str, ports: List[int], context: Dict) -> List[ServiceInfo]:
        """Escanea una lista de puertos."""
        open_services = []
        timeout = context.get("timeout", 0.5)
        max_concurrency = context.get("max_concurrency", 50)
        
        semaphore = asyncio.Semaphore(max_concurrency)
        
        async def check_port(port):
            async with semaphore:
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(ip, port),
                        timeout=timeout
                    )
                    
                    # Intentar obtener banner
                    try:
                        writer.write(b'\r\n')
                        await writer.drain()
                        banner = await asyncio.wait_for(
                            reader.read(1024),
                            timeout=0.5
                        )
                        banner_str = banner.decode(errors='ignore')
                    except:
                        banner_str = ""
                    
                    writer.close()
                    await writer.wait_closed()
                    
                    # Identificar servicio
                    service_name = self._identify_service(port, banner_str)
                    version, product = self._extract_version_product(banner_str)
                    
                    return ServiceInfo(
                        port=port,
                        is_open=True,
                        service_name=service_name,
                        banner=banner_str[:200] if banner_str else None,
                        version=version,
                        product=product
                    )
                except:
                    return None
        
        tasks = [check_port(port) for port in ports]
        results = await asyncio.gather(*tasks)
        
        return [s for s in results if s is not None]
    
    def _identify_service(self, port: int, banner: str) -> str:
        """Identifica el servicio por puerto y banner."""
        # Primero por puerto conocido
        if port in self.port_to_service:
            return self.port_to_service[port]
        
        # Luego por banner
        banner_lower = banner.lower()
        
        if "ssh" in banner_lower:
            return "SSH"
        elif "ftp" in banner_lower:
            return "FTP"
        elif "http" in banner_lower or "server" in banner_lower:
            return "HTTP"
        elif "rtsp" in banner_lower:
            return "RTSP"
        elif "smtp" in banner_lower:
            return "SMTP"
        elif "mysql" in banner_lower:
            return "MySQL"
        elif "postgresql" in banner_lower or "postgres" in banner_lower:
            return "PostgreSQL"
        elif "redis" in banner_lower:
            return "Redis"
        elif "mongodb" in banner_lower:
            return "MongoDB"
        
        return "Unknown"
    
    def _extract_version_product(self, banner: str) -> tuple:
        """Extrae versión y producto del banner."""
        if not banner:
            return None, None
        
        # Buscar patrones de versión
        version_patterns = [
            r'([\d]+\.[\d]+\.[\d]+)',
            r'([\d]+\.[\d]+)',
            r'v([\d.]+)',
            r'version[\s:]+([\d.]+)',
        ]
        
        for pattern in version_patterns:
            match = re.search(pattern, banner, re.I)
            if match:
                return match.group(1), None
        
        # Buscar productos conocidos
        product_patterns = {
            "Apache": r"Apache[/\s]?([\d.]+)?",
            "Nginx": r"nginx[/\s]?([\d.]+)?",
            "IIS": r"Microsoft-IIS[/\s]?([\d.]+)?",
            "Tomcat": r"Apache Tomcat[/\s]?([\d.]+)?",
            "Node.js": r"Node\.js",
            "PHP": r"PHP[/\s]?([\d.]+)?",
            "Python": r"Python[/\s]?([\d.]+)?",
        }
        
        for product, pattern in product_patterns.items():
            if re.search(pattern, banner, re.I):
                return None, product
        
        return None, None
    
    def to_dict(self) -> Dict:
        """Convierte a diccionario."""
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "author": self.author,
            "version": self.version
        }


def register():
    """Función de registro para el sistema de plugins."""
    return ServiceScanner()
