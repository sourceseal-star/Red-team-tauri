#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ONVIF SCANNER - Detección de Dispositivos ONVIF
===============================================
Escanea y detecta dispositivos compatibles con ONVIF.

Autor: Harold Paredes / SourceSeal Red Team
"""

import asyncio
import re
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field


@dataclass
class ONVIFDevice:
    """Representa un dispositivo ONVIF detectado."""
    ip: str
    port: int
    endpoint: str
    vendor: Optional[str] = None
    model: Optional[str] = None
    firmware_version: Optional[str] = None
    serial_number: Optional[str] = None
    hardware_id: Optional[str] = None
    is_authenticated: bool = False
    username: Optional[str] = None
    password: Optional[str] = None
    profiles: List[Dict] = field(default_factory=list)


class ONVIFScanner:
    """Scanner especializado en detección ONVIF."""
    
    def __init__(self):
        self.name = "onvif_scanner"
        self.category = "scanner"
        self.description = "Detección de dispositivos ONVIF"
        self.author = "Harold Paredes"
        self.version = "3.0.0"
        
    def is_applicable(self, target: str, context: Dict = None) -> bool:
        """Verifica si el scanner es aplicable al objetivo."""
        return True
    
    async def scan(self, target: str, context: Dict = None) -> Dict:
        """
        Escanea un objetivo en busca de dispositivos ONVIF.
        
        Args:
            target: IP o hostname a escanear
            context: Contexto adicional
            
        Returns:
            Diccionario con resultados del escaneo
        """
        context = context or {}
        ports = context.get("ports", [80, 443, 8000, 8080, 8008])
        
        results = {
            "target": target,
            "devices": [],
            "success": False,
            "error": None
        }
        
        try:
            for port in ports:
                device = await self._check_onvif_device(target, port)
                if device:
                    results["devices"].append(device.to_dict())
                    results["success"] = True
            
            return results
            
        except Exception as e:
            results["error"] = str(e)
            return results
    
    async def _check_onvif_device(self, ip: str, port: int) -> Optional[ONVIFDevice]:
        """Verifica si hay un dispositivo ONVIF en el puerto especificado."""
        try:
            import aiohttp
            from onvif_zeep import ONVIFCamera
            
            # Primero verificar si el puerto responde
            url = f"http://{ip}:{port}/onvif/device_service"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=3.0) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        if "ONVIF" in html.upper():
                            # Intentar conectar con ONVIF
                            try:
                                camera = ONVIFCamera(ip, port)
                                
                                # Obtener información del dispositivo
                                device_info = camera.devicemgmt.GetDeviceInformation()
                                
                                device = ONVIFDevice(
                                    ip=ip,
                                    port=port,
                                    endpoint=url,
                                    vendor=getattr(device_info, "Manufacturer", None),
                                    model=getattr(device_info, "Model", None),
                                    firmware_version=getattr(device_info, "FirmwareVersion", None),
                                    serial_number=getattr(device_info, "SerialNumber", None),
                                    hardware_id=getattr(device_info, "HardwareId", None)
                                )
                                
                                # Obtener perfiles
                                profiles = camera.media.GetProfiles()
                                device.profiles = [
                                    {
                                        "name": p.Name,
                                        "token": p.token,
                                        "width": p.VideoEncoderConfiguration.Resolution.Width,
                                        "height": p.VideoEncoderConfiguration.Resolution.Height,
                                        "encoding": p.VideoEncoderConfiguration.Encoding
                                    }
                                    for p in profiles
                                ]
                                
                                return device
                            except:
                                # Si falla ONVIF, devolver dispositivo básico
                                return ONVIFDevice(
                                    ip=ip,
                                    port=port,
                                    endpoint=url,
                                    is_authenticated=False
                                )
            
            return None
            
        except ImportError:
            # Si no está instalado onvif-zeep, hacer detección básica
            return await self._basic_onvif_check(ip, port)
        except:
            return None
    
    async def _basic_onvif_check(self, ip: str, port: int) -> Optional[ONVIFDevice]:
        """Detección básica de ONVIF sin librería."""
        try:
            import aiohttp
            
            url = f"http://{ip}:{port}/onvif/device_service"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=3.0) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        if "ONVIF" in html.upper():
                            return ONVIFDevice(
                                ip=ip,
                                port=port,
                                endpoint=url
                            )
            
            return None
            
        except:
            return None
    
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
    return ONVIFScanner()
