#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RTSP SCANNER - Detección de Streams RTSP
========================================
Escanea y detecta streams RTSP en cámaras IP.

Autor: Harold Paredes / SourceSeal Red Team
"""

import asyncio
import re
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field


@dataclass
class RTSPStream:
    """Representa un stream RTSP detectado."""
    ip: str
    port: int
    url: str
    is_authenticated: bool = False
    username: Optional[str] = None
    password: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    resolution: Optional[str] = None
    codec: Optional[str] = None
    is_active: bool = True


class RTSPScanner:
    """Scanner especializado en detección de RTSP."""
    
    def __init__(self):
        self.name = "rtsp_scanner"
        self.category = "scanner"
        self.description = "Detección de streams RTSP en cámaras IP"
        self.author = "Harold Paredes"
        self.version = "3.0.0"
        
    def is_applicable(self, target: str, context: Dict = None) -> bool:
        """Verifica si el scanner es aplicable al objetivo."""
        return True
    
    async def scan(self, target: str, context: Dict = None) -> Dict:
        """
        Escanea un objetivo en busca de streams RTSP.
        
        Args:
            target: IP o hostname a escanear
            context: Contexto adicional
            
        Returns:
            Diccionario con resultados del escaneo
        """
        context = context or {}
        port = context.get("port", 554)
        timeout = context.get("timeout", 2.0)
        
        results = {
            "target": target,
            "port": port,
            "streams": [],
            "success": False,
            "error": None
        }
        
        try:
            # Verificar si el puerto RTSP está abierto
            stream = await self._check_rtsp_port(target, port, timeout)
            if stream:
                results["streams"].append(stream.to_dict())
                results["success"] = True
                
                # Intentar detectar más información
                stream = await self._enrich_stream_info(stream)
                results["streams"][0] = stream.to_dict()
            
            return results
            
        except Exception as e:
            results["error"] = str(e)
            return results
    
    async def _check_rtsp_port(self, ip: str, port: int, timeout: float) -> Optional[RTSPStream]:
        """Verifica si hay un servicio RTSP en el puerto especificado."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=timeout
            )
            
            # Enviar OPTIONS RTSP
            req = f"OPTIONS rtsp://{ip}:{port}/ RTSP/1.0\r\nCSeq: 1\r\n\r\n"
            writer.write(req.encode())
            await writer.drain()
            
            resp = await asyncio.wait_for(
                reader.read(1024),
                timeout=timeout
            )
            writer.close()
            await writer.wait_closed()
            
            response = resp.decode(errors='ignore')
            
            if "RTSP/1.0" in response or "RTSP/1.1" in response:
                return RTSPStream(
                    ip=ip,
                    port=port,
                    url=f"rtsp://{ip}:{port}",
                    is_active=True
                )
            
            return None
            
        except:
            return None
    
    async def _enrich_stream_info(self, stream: RTSPStream) -> RTSPStream:
        """Enriquece la información del stream."""
        try:
            # Intentar detectar vendor y modelo
            vendor, model = await self._detect_vendor_model(stream.ip, stream.port)
            stream.vendor = vendor
            stream.model = model
            
            # Intentar detectar resolución y codec
            resolution, codec = await self._detect_stream_properties(stream.ip, stream.port)
            stream.resolution = resolution
            stream.codec = codec
            
        except:
            pass
        
        return stream
    
    async def _detect_vendor_model(self, ip: str, port: int) -> tuple:
        """Detecta vendor y modelo de la cámara."""
        try:
            import aiohttp
            
            # Intentar con HTTP en el mismo IP
            for http_port in [80, 443, 8000, 8080]:
                try:
                    url = f"http://{ip}:{http_port}"
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, timeout=3.0) as resp:
                            if resp.status == 200:
                                html = await resp.text()
                                
                                # Buscar firmas de cámaras
                                camera_signatures = {
                                    "hikvision": [r"hikvision", r"isapi", r"hik", r"ds-2"],
                                    "dahua": [r"dahua", r"dahuatech", r"DH-", r"IPC"],
                                    "axis": [r"axis", r"AXIS", r"21[0-9]{2}"],
                                    "uniview": [r"uniview", r"UNIVIEW", r"UniView"],
                                }
                                
                                html_lower = html.lower()
                                for vendor, signatures in camera_signatures.items():
                                    for signature in signatures:
                                        if re.search(signature, html_lower, re.I):
                                            model = self._extract_model(html, vendor)
                                            return vendor.capitalize(), model
                                
                                # Verificar headers
                                server = resp.headers.get("Server", "").lower()
                                for vendor, signatures in camera_signatures.items():
                                    for signature in signatures:
                                        if re.search(signature, server, re.I):
                                            return vendor.capitalize(), None
                except:
                    continue
        except:
            pass
        
        return None, None
    
    def _extract_model(self, html: str, vendor: str) -> Optional[str]:
        """Extrae el modelo de la cámara del HTML."""
        vendor_lower = vendor.lower()
        
        if vendor_lower == "hikvision":
            match = re.search(r'DS-2CD[\w-]+|DS-[\d]+[A-Z]?', html, re.I)
            if match:
                return match.group(0)
        elif vendor_lower == "dahua":
            match = re.search(r'DH-IPC-[\w-]+|IPC[\w-]+', html, re.I)
            if match:
                return match.group(0)
        elif vendor_lower == "axis":
            match = re.search(r'AXIS (\w+)|21[0-9]{2}|M[0-9]{3}', html, re.I)
            if match:
                return match.group(0)
        
        return None
    
    async def _detect_stream_properties(self, ip: str, port: int) -> tuple:
        """Detecta propiedades del stream (resolución, codec)."""
        try:
            import aiohttp
            
            # Intentar obtener información del stream
            for http_port in [80, 443, 8000, 8080]:
                try:
                    url = f"http://{ip}:{http_port}/cgi-bin/magicBox.cgi?action=getProductType"
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, timeout=3.0) as resp:
                            if resp.status == 200:
                                text = await resp.text()
                                # Analizar respuesta para obtener propiedades
                                # (Implementación específica por vendor)
                                pass
                except:
                    continue
        except:
            pass
        
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
    return RTSPScanner()
