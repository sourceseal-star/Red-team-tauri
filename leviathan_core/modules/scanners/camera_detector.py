#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CAMERA DETECTOR - Detección Especializada de Cámaras IP
======================================================
Detección avanzada de cámaras IP por vendor y modelo.

Autor: Harold Paredes / SourceSeal Red Team
"""

import asyncio
import re
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field


@dataclass
class DetectedCamera:
    """Representa una cámara IP detectada."""
    ip: str
    port: int
    vendor: Optional[str] = None
    model: Optional[str] = None
    firmware_version: Optional[str] = None
    serial_number: Optional[str] = None
    hardware_version: Optional[str] = None
    services: List[Dict] = field(default_factory=list)
    is_accessible: bool = False
    access_url: Optional[str] = None
    credentials: Optional[str] = None
    rtsp_url: Optional[str] = None
    http_url: Optional[str] = None
    onvif_endpoint: Optional[str] = None
    is_vulnerable: bool = False
    vulnerabilities: List[str] = field(default_factory=list)


class CameraDetector:
    """Detector especializado de cámaras IP."""
    
    def __init__(self):
        self.name = "camera_detector"
        self.category = "scanner"
        self.description = "Detección especializada de cámaras IP"
        self.author = "Harold Paredes"
        self.version = "3.0.0"
        
        # Credenciales por defecto por vendor
        self.default_credentials = {
            "hikvision": [
                ("admin", "12345"), ("admin", "admin"), ("admin", "123456"),
                ("admin", "password"), ("admin", ""), ("12345", "12345"),
                ("admin", "abc123"), ("admin", "1234"), ("admin", "111111"),
                ("admin", "666666"), ("admin", "888888"), ("admin", "000000"),
            ],
            "dahua": [
                ("admin", "admin"), ("admin", "dahua123"), ("admin", "Dahua123"),
                ("admin", "12345"), ("admin", "123456"),
            ],
            "axis": [
                ("root", "pass"), ("admin", "admin"), ("root", "root"),
            ],
            "uniview": [
                ("admin", "admin"), ("admin", "12345"), ("admin", "123456"),
            ],
            "generic": [
                ("admin", "admin"), ("admin", "password"), ("admin", "12345"),
                ("admin", "123456"), ("root", "root"), ("root", "toor"),
                ("user", "user"), ("administrator", "administrator"),
                ("guest", "guest"), ("ubnt", "ubnt"), ("admin", "admin123"),
            ]
        }
        
        # Vulnerabilidades conocidas por vendor
        self.known_vulnerabilities = {
            "hikvision": [
                "CVE-2021-36260", "CVE-2017-17215", "CVE-2021-31956",
                "CVE-2020-9048", "CVE-2020-9050", "CVE-2020-24217"
            ],
            "dahua": [
                "CVE-2021-31956", "CVE-2018-10660", "CVE-2018-10661",
                "CVE-2018-10662", "CVE-2017-16740", "CVE-2017-16741"
            ],
            "axis": [
                "CVE-2018-10660", "CVE-2017-8227", "CVE-2017-8228"
            ],
            "generic": [
                "CVE-2014-6271", "CVE-2017-5638", "CVE-2021-44228"
            ]
        }
        
    def is_applicable(self, target: str, context: Dict = None) -> bool:
        """Verifica si el scanner es aplicable al objetivo."""
        return True
    
    async def scan(self, target: str, context: Dict = None) -> Dict:
        """
        Escanea un objetivo en busca de cámaras IP.
        
        Args:
            target: IP, red o hostname a escanear
            context: Contexto adicional
            
        Returns:
            Diccionario con resultados del escaneo
        """
        context = context or {}
        
        results = {
            "target": target,
            "cameras": [],
            "statistics": {
                "total_detected": 0,
                "accessible": 0,
                "vulnerable": 0
            },
            "success": False,
            "error": None
        }
        
        try:
            # Verificar si es una red o una IP individual
            try:
                network = ipaddress.ip_network(target, strict=False)
                is_network = True
            except:
                is_network = False
            
            if is_network:
                # Escanear red completa
                cameras = await self._scan_network(target, context)
            else:
                # Escanear IP individual
                camera = await self._scan_single_target(target, context)
                cameras = [camera] if camera else []
            
            results["cameras"] = [c.to_dict() for c in cameras if c]
            results["statistics"]["total_detected"] = len(results["cameras"])
            results["statistics"]["accessible"] = sum(1 for c in results["cameras"] if c.get("is_accessible"))
            results["statistics"]["vulnerable"] = sum(1 for c in results["cameras"] if c.get("is_vulnerable"))
            results["success"] = True
            
            return results
            
        except Exception as e:
            results["error"] = str(e)
            return results
    
    async def _scan_network(self, network: str, context: Dict) -> List[DetectedCamera]:
        """Escanea una red completa en busca de cámaras."""
        from .network_scanner import NetworkScanner
        
        network_scanner = NetworkScanner()
        scan_result = await network_scanner.scan(network, context)
        
        cameras = []
        for device in scan_result.get("devices", []):
            if device.get("is_camera"):
                camera = await self._create_camera_from_device(device, context)
                if camera:
                    cameras.append(camera)
        
        return cameras
    
    async def _scan_single_target(self, target: str, context: Dict) -> Optional[DetectedCamera]:
        """Escanea un objetivo individual."""
        # Probar diferentes métodos de detección
        camera = await self._try_detect_camera(target, context)
        return camera
    
    async def _try_detect_camera(self, ip: str, context: Dict) -> Optional[DetectedCamera]:
        """Intenta detectar una cámara usando múltiples métodos."""
        from .http_fingerprint import HTTPFingerprintScanner
        from .rtsp_scanner import RTSPScanner
        from .onvif_scanner import ONVIFScanner
        
        fingerprint_scanner = HTTPFingerprintScanner()
        rtsp_scanner = RTSPScanner()
        onvif_scanner = ONVIFScanner()
        
        ports = context.get("ports", [80, 443, 554, 8000, 8080, 37777])
        
        camera = DetectedCamera(ip=ip)
        
        # Probar detección HTTP
        for port in ports:
            if port in [80, 443, 8000, 8080, 8008, 8081]:
                fp_result = await fingerprint_scanner.scan(f"{ip}:{port}")
                if fp_result.get("fingerprints"):
                    for fp in fp_result["fingerprints"]:
                        if fp.get("is_camera"):
                            camera.port = port
                            camera.vendor = fp.get("camera_vendor")
                            camera.model = fp.get("camera_model")
                            camera.http_url = f"http://{ip}:{port}"
                            camera.services.append({"port": port, "service": "http"})
                            
                            # Verificar si es accesible
                            if await self._test_http_access(ip, port, camera):
                                camera.is_accessible = True
                            
                            break
        
        # Probar detección RTSP
        for port in ports:
            if port == 554:
                rtsp_result = await rtsp_scanner.scan(ip, {"port": port})
                if rtsp_result.get("streams"):
                    stream = rtsp_result["streams"][0]
                    camera.port = port
                    if not camera.vendor:
                        camera.vendor = stream.get("vendor")
                    if not camera.model:
                        camera.model = stream.get("model")
                    camera.rtsp_url = stream.get("url")
                    camera.services.append({"port": port, "service": "rtsp"})
                    
                    if stream.get("is_authenticated"):
                        camera.is_accessible = True
                        camera.credentials = f"{stream.get('username')}:{stream.get('password')}"
        
        # Probar detección ONVIF
        for port in ports:
            onvif_result = await onvif_scanner.scan(ip, {"ports": [port]})
            if onvif_result.get("devices"):
                device = onvif_result["devices"][0]
                camera.port = port
                if not camera.vendor:
                    camera.vendor = device.get("vendor")
                if not camera.model:
                    camera.model = device.get("model")
                if not camera.firmware_version:
                    camera.firmware_version = device.get("firmware_version")
                if not camera.serial_number:
                    camera.serial_number = device.get("serial_number")
                camera.onvif_endpoint = device.get("endpoint")
                camera.services.append({"port": port, "service": "onvif"})
                
                if device.get("is_authenticated"):
                    camera.is_accessible = True
                    camera.credentials = f"{device.get('username')}:{device.get('password')}"
        
        # Verificar vulnerabilidades
        if camera.vendor:
            camera.vulnerabilities = self.known_vulnerabilities.get(
                camera.vendor.lower(), []
            )
            camera.is_vulnerable = len(camera.vulnerabilities) > 0
        
        # Si no se detectó nada, no es una cámara
        if not camera.vendor and not camera.model and not camera.services:
            return None
        
        return camera
    
    async def _test_http_access(self, ip: str, port: int, camera: DetectedCamera) -> bool:
        """Prueba acceso HTTP con credenciales por defecto."""
        try:
            import aiohttp
            from aiohttp import BasicAuth
            
            vendor = camera.vendor.lower() if camera.vendor else "generic"
            credentials = self.default_credentials.get(vendor, [])
            
            for user, password in credentials:
                try:
                    url = f"http://{ip}:{port}"
                    auth = BasicAuth(user, password)
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, auth=auth, timeout=3.0) as resp:
                            if resp.status == 200:
                                camera.credentials = f"{user}:{password}"
                                camera.access_url = url
                                return True
                except:
                    continue
            
            return False
            
        except:
            return False
    
    async def _create_camera_from_device(self, device: Dict, context: Dict) -> Optional[DetectedCamera]:
        """Crea una cámara a partir de un dispositivo detectado."""
        camera_info = device.get("camera_info", {})
        
        camera = DetectedCamera(
            ip=device.get("ip"),
            vendor=camera_info.get("vendor"),
            model=camera_info.get("model"),
            is_accessible=camera_info.get("is_accessible", False),
            access_url=camera_info.get("access_url")
        )
        
        # Agregar servicios
        for service in device.get("services", []):
            camera.services.append(service)
        
        # Verificar vulnerabilidades
        if camera.vendor:
            camera.vulnerabilities = self.known_vulnerabilities.get(
                camera.vendor.lower(), []
            )
            camera.is_vulnerable = len(camera.vulnerabilities) > 0
        
        return camera
    
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
    return CameraDetector()
