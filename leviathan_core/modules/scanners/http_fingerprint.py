#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTTP FINGERPRINT - Identificación por Banners HTTP
==================================================
Identifica servicios HTTP por sus banners y headers.

Autor: Harold Paredes / SourceSeal Red Team
"""

import asyncio
import re
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field


@dataclass
class HTTPFingerprint:
    """Representa un fingerprint HTTP."""
    ip: str
    port: int
    url: str
    status_code: int
    server: Optional[str] = None
    x_powered_by: Optional[str] = None
    via: Optional[str] = None
    www_authenticate: Optional[str] = None
    title: Optional[str] = None
    body_hash: Optional[str] = None
    technology: Optional[str] = None
    version: Optional[str] = None
    is_camera: bool = False
    camera_vendor: Optional[str] = None
    camera_model: Optional[str] = None
    vulnerabilities: List[str] = field(default_factory=list)


class HTTPFingerprintScanner:
    """Scanner de fingerprinting HTTP."""
    
    def __init__(self):
        self.name = "http_fingerprint"
        self.category = "scanner"
        self.description = "Identificación de servicios HTTP por banners"
        self.author = "Harold Paredes"
        self.version = "3.0.0"
        
        # Base de datos de firmas
        self.fingerprints_db = self._load_fingerprints_db()
        self.camera_signatures = self._load_camera_signatures()
        self.vulnerability_signatures = self._load_vulnerability_signatures()
        
    def is_applicable(self, target: str, context: Dict = None) -> bool:
        """Verifica si el scanner es aplicable al objetivo."""
        return True
    
    async def scan(self, target: str, context: Dict = None) -> Dict:
        """
        Escanea un objetivo y obtiene su fingerprint HTTP.
        
        Args:
            target: IP o hostname a escanear
            context: Contexto adicional
            
        Returns:
            Diccionario con resultados del escaneo
        """
        context = context or {}
        ports = context.get("ports", [80, 443, 8000, 8080, 8008, 8081])
        
        results = {
            "target": target,
            "fingerprints": [],
            "success": False,
            "error": None
        }
        
        try:
            for port in ports:
                fingerprint = await self._get_fingerprint(target, port)
                if fingerprint:
                    # Enriquecer con detección de cámaras y vulnerabilidades
                    fingerprint = self._enrich_fingerprint(fingerprint)
                    results["fingerprints"].append(fingerprint.to_dict())
                    results["success"] = True
            
            return results
            
        except Exception as e:
            results["error"] = str(e)
            return results
    
    async def _get_fingerprint(self, ip: str, port: int) -> Optional[HTTPFingerprint]:
        """Obtiene el fingerprint HTTP de un objetivo."""
        try:
            import aiohttp
            from hashlib import sha256
            
            url = f"http://{ip}:{port}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5.0) as resp:
                    status_code = resp.status
                    
                    # Obtener headers
                    server = resp.headers.get("Server")
                    x_powered_by = resp.headers.get("X-Powered-By")
                    via = resp.headers.get("Via")
                    www_authenticate = resp.headers.get("WWW-Authenticate")
                    
                    # Obtener cuerpo (solo los primeros 10KB para eficiencia)
                    body = await resp.read()
                    body_text = body.decode(errors='ignore')[:10000]
                    body_hash = sha256(body).hexdigest()[:16]
                    
                    # Extraer título
                    title = self._extract_title(body_text)
                    
                    fingerprint = HTTPFingerprint(
                        ip=ip,
                        port=port,
                        url=url,
                        status_code=status_code,
                        server=server,
                        x_powered_by=x_powered_by,
                        via=via,
                        www_authenticate=www_authenticate,
                        title=title,
                        body_hash=body_hash
                    )
                    
                    # Identificar tecnología
                    fingerprint.technology, fingerprint.version = self._identify_technology(
                        server, x_powered_by, body_text
                    )
                    
                    return fingerprint
            
            return None
            
        except:
            return None
    
    def _enrich_fingerprint(self, fingerprint: HTTPFingerprint) -> HTTPFingerprint:
        """Enriquece el fingerprint con información adicional."""
        # Detectar si es cámara
        fingerprint.is_camera, fingerprint.camera_vendor, fingerprint.camera_model = \
            self._detect_camera(fingerprint)
        
        # Detectar vulnerabilidades
        fingerprint.vulnerabilities = self._detect_vulnerabilities(fingerprint)
        
        return fingerprint
    
    def _extract_title(self, html: str) -> Optional[str]:
        """Extrae el título de una página HTML."""
        match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.I)
        if match:
            return match.group(1).strip()
        return None
    
    def _identify_technology(self, server: str, x_powered_by: str, body: str) -> tuple:
        """Identifica la tecnología y versión."""
        if not server and not x_powered_by:
            return None, None
        
        headers = f"{server} {x_powered_by}".lower()
        
        # Buscar en base de datos de firmas
        for tech, signatures in self.fingerprints_db.items():
            for signature in signatures:
                if re.search(signature, headers, re.I):
                    # Extraer versión
                    version_match = re.search(signature, headers, re.I)
                    if version_match:
                        version = version_match.group(0)
                        # Limpiar versión
                        version = re.sub(r'[^\d.]', '', version)
                        return tech, version if version else None
                    return tech, None
        
        return None, None
    
    def _detect_camera(self, fingerprint: HTTPFingerprint) -> tuple:
        """Detecta si el dispositivo es una cámara."""
        if not fingerprint.server and not fingerprint.title and not fingerprint.body_hash:
            return False, None, None
        
        # Buscar en firmas de cámaras
        search_text = f"{fingerprint.server} {fingerprint.title}".lower()
        
        for vendor, signatures in self.camera_signatures.items():
            for signature in signatures:
                if re.search(signature, search_text, re.I):
                    # Extraer modelo
                    model = self._extract_camera_model(search_text, vendor)
                    return True, vendor.capitalize(), model
        
        return False, None, None
    
    def _extract_camera_model(self, text: str, vendor: str) -> Optional[str]:
        """Extrae el modelo de la cámara."""
        vendor_lower = vendor.lower()
        
        if vendor_lower == "hikvision":
            match = re.search(r'DS-2CD[\w-]+|DS-[\d]+[A-Z]?', text, re.I)
            if match:
                return match.group(0)
        elif vendor_lower == "dahua":
            match = re.search(r'DH-IPC-[\w-]+|IPC[\w-]+', text, re.I)
            if match:
                return match.group(0)
        
        return None
    
    def _detect_vulnerabilities(self, fingerprint: HTTPFingerprint) -> List[str]:
        """Detecta vulnerabilidades conocidas."""
        vulnerabilities = []
        
        if not fingerprint.server and not fingerprint.technology:
            return vulnerabilities
        
        search_text = f"{fingerprint.server} {fingerprint.technology} {fingerprint.version}".lower()
        
        for vuln_name, signatures in self.vulnerability_signatures.items():
            for signature in signatures:
                if re.search(signature, search_text, re.I):
                    if vuln_name not in vulnerabilities:
                        vulnerabilities.append(vuln_name)
        
        return vulnerabilities
    
    def _load_fingerprints_db(self) -> Dict:
        """Carga la base de datos de firmas."""
        return {
            "Apache": [r"Apache[/\s]?([\d.]+)?", r"Apache-Coyote"],
            "Nginx": [r"nginx[/\s]?([\d.]+)?"],
            "IIS": [r"Microsoft-IIS[/\s]?([\d.]+)?", r"IIS"],
            "Tomcat": [r"Apache Tomcat[/\s]?([\d.]+)?", r"Tomcat"],
            "Node.js": [r"Node\.js", r"Express"],
            "PHP": [r"PHP[/\s]?([\d.]+)?"],
            "Python": [r"Python[/\s]?([\d.]+)?", r"Werkzeug"],
            "Java": [r"Java[/\s]?([\d.]+)?", r"Jetty"],
            "Go": [r"Go[/\s]?([\d.]+)?", r"Golang"],
            "Ruby": [r"Ruby[/\s]?([\d.]+)?"],
        }
    
    def _load_camera_signatures(self) -> Dict:
        """Carga las firmas de cámaras."""
        return {
            "hikvision": [r"hikvision", r"isapi", r"hik", r"ds-2", r"iVMS"],
            "dahua": [r"dahua", r"dahuatech", r"Dahua", r"DH-", r"IPC"],
            "axis": [r"axis", r"AXIS", r"21[0-9]{2}", r"AXIS Camera"],
            "uniview": [r"uniview", r"UNIVIEW", r"UniView", r"NVR"],
            "honeywell": [r"honeywell", r"Honeywell", r"Performance"],
            "bosch": [r"bosch", r"BOSCH", r"Bosch Security"],
            "ezviz": [r"ezviz", r"EZVIZ", r"CS-"],
            "xiaomi": [r"xiaomi", r"mi", r"Mi Camera"],
        }
    
    def _load_vulnerability_signatures(self) -> Dict:
        """Carga las firmas de vulnerabilidades."""
        return {
            "CVE-2021-36260": [r"Hikvision.*V5\.5\.[0-7]", r"Hikvision.*< V5\.5\.80"],
            "CVE-2021-31956": [r"Dahua.*< V2\.800", r"Dahua.*2\.600"],
            "CVE-2017-17215": [r"Hikvision.*V5\.2\.[0-9]", r"Hikvision.*5\.2\.x"],
            "CVE-2018-10660": [r"Dahua.*V2\.400", r"Dahua.*2\.400"],
            "CVE-2020-12066": [r"Apache.*2\.4\.[0-4][0-9]"],
            "CVE-2021-41773": [r"Apache.*2\.4\.49", r"Apache.*2\.4\.50"],
            "CVE-2014-6271": [r"ShellShock", r"CGI.*bash"],
            "CVE-2017-5638": [r"Struts2", r"Apache Struts"],
        }
    
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
    return HTTPFingerprintScanner()
