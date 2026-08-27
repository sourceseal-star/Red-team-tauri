#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NETWORK SCANNER - Escaneo de Red Avanzado
==========================================
Escanea redes completas en busca de dispositivos activos.

Autor: Harold Paredes / SourceSeal Red Team
"""

import asyncio
import ipaddress
import socket
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field


@dataclass
class NetworkDevice:
    """Representa un dispositivo en la red."""
    ip: str
    hostname: Optional[str] = None
    is_active: bool = False
    mac_address: Optional[str] = None
    vendor: Optional[str] = None
    open_ports: List[int] = field(default_factory=list)
    services: List[Dict] = field(default_factory=list)
    response_time: Optional[float] = None
    is_camera: bool = False
    camera_info: Optional[Dict] = None


class NetworkScanner:
    """Scanner de red avanzado."""
    
    def __init__(self):
        self.name = "network_scanner"
        self.category = "scanner"
        self.description = "Escaneo de red con detección de dispositivos"
        self.author = "Harold Paredes"
        self.version = "3.0.0"
        
        # Puertos comunes
        self.common_ports = [21, 22, 23, 25, 53, 80, 110, 139, 443, 445, 554, 1935, 
                           3306, 3389, 5432, 6379, 8000, 8080, 8443, 8554, 8888, 37777, 3702]
        self.camera_ports = [80, 443, 554, 8000, 8080, 37777]
        
    def is_applicable(self, target: str, context: Dict = None) -> bool:
        """Verifica si el scanner es aplicable al objetivo."""
        # Este scanner siempre es aplicable a redes
        try:
            ipaddress.ip_network(target)
            return True
        except:
            return False
    
    async def scan(self, target: str, context: Dict = None) -> Dict:
        """
        Escanea una red completa.
        
        Args:
            target: Red a escanear (ej: 192.168.0.0/24)
            context: Contexto adicional
            
        Returns:
            Diccionario con resultados del escaneo
        """
        context = context or {}
        
        results = {
            "target": target,
            "devices": [],
            "statistics": {
                "total_ips": 0,
                "active_ips": 0,
                "cameras_found": 0,
                "scan_duration": 0.0
            },
            "success": False,
            "error": None
        }
        
        try:
            import time
            start_time = time.time()
            
            # Validar red
            network = ipaddress.ip_network(target, strict=False)
            all_ips = [str(ip) for ip in network.hosts()]
            
            results["statistics"]["total_ips"] = len(all_ips)
            
            # Escanear IPs activas
            active_ips = await self._scan_active_ips(all_ips, context)
            results["statistics"]["active_ips"] = len(active_ips)
            
            # Escanear dispositivos en IPs activas
            devices = []
            for ip in active_ips:
                device = await self._scan_device(ip, context)
                if device.is_active:
                    devices.append(device)
                    
                    # Verificar si es cámara
                    if device.is_camera:
                        results["statistics"]["cameras_found"] += 1
            
            results["devices"] = [d.to_dict() for d in devices]
            results["success"] = True
            
            # Calcular duración
            results["statistics"]["scan_duration"] = time.time() - start_time
            
            return results
            
        except Exception as e:
            results["error"] = str(e)
            return results
    
    async def _scan_active_ips(self, ips: List[str], context: Dict) -> List[str]:
        """Escanea IPs activas usando ping."""
        active_ips = []
        max_concurrency = context.get("max_concurrency", 100)
        timeout = context.get("timeout", 0.5)
        
        semaphore = asyncio.Semaphore(max_concurrency)
        
        async def ping_ip(ip):
            async with semaphore:
                try:
                    # Usar comando ping
                    proc = await asyncio.create_subprocess_exec(
                        'ping', '-c', '1', '-W', str(int(timeout)), ip,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(),
                        timeout=timeout + 1
                    )
                    
                    if proc.returncode == 0:
                        return ip
                    return None
                except:
                    return None
        
        tasks = [ping_ip(ip) for ip in ips]
        results = await asyncio.gather(*tasks)
        
        return [ip for ip in results if ip is not None]
    
    async def _scan_device(self, ip: str, context: Dict) -> NetworkDevice:
        """Escanea un dispositivo individual."""
        device = NetworkDevice(ip=ip, is_active=True)
        
        try:
            # Obtener hostname
            try:
                device.hostname = socket.gethostbyaddr(ip)[0]
            except:
                pass
            
            # Obtener MAC address (requiere permisos)
            device.mac_address = await self._get_mac_address(ip)
            
            # Escanear puertos
            device.open_ports = await self._scan_ports(ip, context)
            
            # Detectar servicios
            device.services = await self._detect_services(ip, device.open_ports)
            
            # Verificar si es cámara
            device.is_camera, device.camera_info = await self._detect_camera(ip, device.open_ports)
            
            # Detectar vendor por MAC
            if device.mac_address:
                device.vendor = self._get_vendor_by_mac(device.mac_address)
            
        except:
            pass
        
        return device
    
    async def _get_mac_address(self, ip: str) -> Optional[str]:
        """Obtiene la dirección MAC de una IP."""
        try:
            # Usar arp (Linux)
            proc = await asyncio.create_subprocess_exec(
                'arp', '-n', ip,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await proc.communicate()
            
            for line in stdout.decode().split('\n'):
                if ip in line and 'ether' in line:
                    parts = line.split()
                    for part in parts:
                        if ':' in part and len(part) == 17:
                            return part
            
            return None
        except:
            return None
    
    async def _scan_ports(self, ip: str, context: Dict) -> List[int]:
        """Escanea puertos abiertos."""
        open_ports = []
        ports = context.get("ports", self.common_ports)
        timeout = context.get("port_timeout", 0.3)
        max_concurrency = context.get("port_concurrency", 20)
        
        semaphore = asyncio.Semaphore(max_concurrency)
        
        async def check_port(port):
            async with semaphore:
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(ip, port),
                        timeout=timeout
                    )
                    writer.close()
                    await writer.wait_closed()
                    return port
                except:
                    return None
        
        tasks = [check_port(port) for port in ports]
        results = await asyncio.gather(*tasks)
        
        return [port for port in results if port is not None]
    
    async def _detect_services(self, ip: str, ports: List[int]) -> List[Dict]:
        """Detecta servicios en puertos abiertos."""
        services = []
        
        for port in ports:
            service = await self._identify_service(ip, port)
            if service:
                services.append(service)
        
        return services
    
    async def _identify_service(self, ip: str, port: int) -> Optional[Dict]:
        """Identifica el servicio en un puerto."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=1.0
            )
            
            # Enviar un byte y recibir respuesta
            writer.write(b'\r\n')
            await writer.drain()
            
            try:
                resp = await asyncio.wait_for(
                    reader.read(1024),
                    timeout=1.0
                )
                banner = resp.decode(errors='ignore')
                
                # Identificar servicio por banner
                service_type = self._identify_by_banner(banner, port)
                
                writer.close()
                await writer.wait_closed()
                
                return {
                    "port": port,
                    "service": service_type,
                    "banner": banner[:200]
                }
            except:
                writer.close()
                await writer.wait_closed()
                return {
                    "port": port,
                    "service": "unknown",
                    "banner": ""
                }
        except:
            return None
    
    def _identify_by_banner(self, banner: str, port: int) -> str:
        """Identifica el servicio por su banner."""
        banner_lower = banner.lower()
        
        # Puertos conocidos
        port_services = {
            21: "FTP",
            22: "SSH",
            23: "Telnet",
            25: "SMTP",
            53: "DNS",
            80: "HTTP",
            443: "HTTPS",
            554: "RTSP",
            1935: "RTMP",
            3306: "MySQL",
            3389: "RDP",
            5432: "PostgreSQL",
            6379: "Redis",
            8000: "HTTP-Alt",
            8080: "HTTP-Proxy",
            8443: "HTTPS-Alt",
            8554: "RTSP-Alt",
            8888: "HTTP-Alt",
            37777: "Camera",
            3702: "WS-Discovery"
        }
        
        if port in port_services:
            return port_services[port]
        
        # Identificar por banner
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
        elif "postgresql" in banner_lower:
            return "PostgreSQL"
        elif "redis" in banner_lower:
            return "Redis"
        
        return "Unknown"
    
    async def _detect_camera(self, ip: str, ports: List[int]) -> tuple:
        """Detecta si un dispositivo es una cámara."""
        from .http_fingerprint import HTTPFingerprintScanner
        from .rtsp_scanner import RTSPScanner
        from .onvif_scanner import ONVIFScanner
        
        fingerprint_scanner = HTTPFingerprintScanner()
        rtsp_scanner = RTSPScanner()
        onvif_scanner = ONVIFScanner()
        
        # Verificar puertos de cámara
        camera_ports_to_check = [p for p in ports if p in self.camera_ports]
        
        if not camera_ports_to_check:
            return False, None
        
        # Probar detección HTTP
        for port in camera_ports_to_check:
            if port in [80, 443, 8000, 8080, 8008, 8081]:
                fp_result = await fingerprint_scanner.scan(f"{ip}:{port}")
                if fp_result.get("fingerprints"):
                    for fp in fp_result["fingerprints"]:
                        if fp.get("is_camera"):
                            return True, {
                                "type": "http",
                                "port": port,
                                "vendor": fp.get("camera_vendor"),
                                "model": fp.get("camera_model")
                            }
        
        # Probar detección RTSP
        for port in camera_ports_to_check:
            if port == 554:
                rtsp_result = await rtsp_scanner.scan(ip, {"port": port})
                if rtsp_result.get("streams"):
                    return True, {
                        "type": "rtsp",
                        "port": port,
                        "vendor": rtsp_result["streams"][0].get("vendor"),
                        "model": rtsp_result["streams"][0].get("model")
                    }
        
        # Probar detección ONVIF
        for port in camera_ports_to_check:
            onvif_result = await onvif_scanner.scan(ip, {"ports": [port]})
            if onvif_result.get("devices"):
                return True, {
                    "type": "onvif",
                    "port": port,
                    "vendor": onvif_result["devices"][0].get("vendor"),
                    "model": onvif_result["devices"][0].get("model")
                }
        
        return False, None
    
    def _get_vendor_by_mac(self, mac: str) -> Optional[str]:
        """Obtiene el vendor por dirección MAC."""
        # Base de datos de OUIs
        oui_db = {
            "00:1E:58": "Google",
            "00:1F:16": "Sony",
            "00:21:5A": "Hikvision",
            "00:23:CD": "Dahua",
            "00:40:8C": "Axis",
            "00:15:6D": "Bosch",
            "00:1D:0F": "Samsung",
            "00:25:4B": "Apple",
            "00:50:C2": "3Com",
            "00:0C:29": "VMware",
        }
        
        # Extraer OUI (primeros 3 bytes)
        mac_upper = mac.upper().replace(':', '-')
        oui = mac_upper[:8]
        
        return oui_db.get(oui, None)
    
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
    return NetworkScanner()
