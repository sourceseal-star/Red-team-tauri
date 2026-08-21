#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LEVIATHAN SCANNERS - Módulos de Escaneo
=========================================
Paquete de scanners especializados.
"""

from .rtsp_scanner import RTSPScanner
from .onvif_scanner import ONVIFScanner
from .http_fingerprint import HTTPFingerprintScanner
from .network_scanner import NetworkScanner
from .camera_detector import CameraDetector
from .service_scanner import ServiceScanner

__all__ = [
    "RTSPScanner",
    "ONVIFScanner", 
    "HTTPFingerprintScanner",
    "NetworkScanner",
    "CameraDetector",
    "ServiceScanner"
]


def register_all():
    """Registra todos los scanners."""
    return [
        RTSPScanner(),
        ONVIFScanner(),
        HTTPFingerprintScanner(),
        NetworkScanner(),
        CameraDetector(),
        ServiceScanner()
    ]
