#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LEVIATHAN INTEGRATION ROUTER — API Unificada v1
=================================================
Monta en dashboard_server.py via include_router.
No crea app propia — usa la que ya existe.

Endpoints en /api/v1/*:
  Scanners:   /scan/network, /scan/cameras, /scan/rtsp, /scan/onvif, /scan/services
  Exploiters: /exploit/camera, /exploit/kraken, /exploit/chain
  AI:         /ai/detect-objects, /ai/detect-anomalies, /ai/threat-scoring
  Reporters:  /report/json, /report/html, /report/pdf
  Commander:  /commander/status
  System:     /status, /health
"""
from __future__ import annotations
import asyncio
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel
from fastapi.responses import FileResponse, JSONResponse

router = APIRouter(prefix="/api/v1", tags=["LEVIATHAN Unified"])

# ── Cargar módulos bajo demanda ──
_scanners = None
_exploiters = None
_analyzers = None
_reporters = None

def _load():
    global _scanners, _exploiters, _analyzers, _reporters
    if _scanners is None:
        try:
            from leviathan_core.modules.scanners import register_all
            _scanners = register_all()
        except Exception:
            _scanners = []
    if _exploiters is None:
        try:
            from leviathan_core.modules.exploiters import register_all
            _exploiters = register_all()
        except Exception:
            _exploiters = []
    if _analyzers is None:
        try:
            from leviathan_core.modules.ai_analyzers import register_all
            _analyzers = register_all()
        except Exception:
            _analyzers = []
    if _reporters is None:
        try:
            from leviathan_core.modules.reporters import register_all
            _reporters = register_all()
        except Exception:
            _reporters = []

# ── Cargar profiles.json ──
_profiles = None
def _load_profiles():
    global _profiles
    if _profiles is None:
        config_path = Path(__file__).resolve().parent.parent / "config" / "profiles.json"
        try:
            with open(config_path) as f:
                _profiles = json.load(f)
        except Exception:
            _profiles = {}
    return _profiles

# ── Modelos ──
class ScanRequest(BaseModel):
    network: str = "192.168.0.0/24"
    profile: str = "camera_detection"
    deep: bool = False
    modules: Optional[List[str]] = None

class ExploitRequest(BaseModel):
    target: str
    vendor: Optional[str] = None
    exploit_type: str = "auto"

class AIRequest(BaseModel):
    target: str
    module: str = "threat_scoring"
    data: Optional[Dict] = None

class ReportRequest(BaseModel):
    target: str
    format: str = "json"
    data: Optional[Dict] = None

# ══════════════════════════════════════════════════════════════
# SCANNERS
# ══════════════════════════════════════════════════════════════

@router.post("/scan/network")
async def scan_network(req: ScanRequest):
    """Escaneo de red completo con detección de cámaras."""
    _load()
    scanner = next((s for s in _scanners if s.name == "network_scanner"), None)
    if not scanner:
        raise HTTPException(500, "network_scanner no disponible")
    try:
        if asyncio.iscoroutinefunction(scanner.scan):
            result = await scanner.scan(req.network, {"deep": req.deep})
        else:
            result = await asyncio.to_thread(scanner.scan, req.network, {"deep": req.deep})
        # Enriquecer con camera_detector
        cam_det = next((s for s in _scanners if s.name == "camera_detector"), None)
        if cam_det and cam_det.is_applicable(req.network):
            if asyncio.iscoroutinefunction(cam_det.scan):
                cam_result = await cam_det.scan(req.network)
            else:
                cam_result = await asyncio.to_thread(cam_det.scan, req.network)
            if isinstance(result, dict):
                result["cameras"] = cam_result.get("cameras", [])
        return {"success": True, "data": result, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(500, str(e)[:300])

@router.post("/scan/cameras")
async def scan_cameras(network: str = "192.168.0.0/24"):
    """Detección especializada de cámaras IP."""
    _load()
    detector = next((s for s in _scanners if s.name == "camera_detector"), None)
    if not detector:
        raise HTTPException(500, "camera_detector no disponible")
    try:
        if asyncio.iscoroutinefunction(detector.scan):
            result = await detector.scan(network)
        else:
            result = await asyncio.to_thread(detector.scan, network)
        return {"success": True, "cameras": result.get("cameras", []) if isinstance(result, dict) else [], "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(500, str(e)[:300])

@router.post("/scan/rtsp")
async def scan_rtsp(target: str, port: int = 554):
    """Detección de streams RTSP."""
    _load()
    scanner = next((s for s in _scanners if s.name == "rtsp_scanner"), None)
    if not scanner:
        raise HTTPException(500, "rtsp_scanner no disponible")
    try:
        if asyncio.iscoroutinefunction(scanner.scan):
            result = await scanner.scan(target, {"port": port})
        else:
            result = await asyncio.to_thread(scanner.scan, target, {"port": port})
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(500, str(e)[:300])

@router.post("/scan/onvif")
async def scan_onvif(target: str):
    """Detección de dispositivos ONVIF."""
    _load()
    scanner = next((s for s in _scanners if s.name == "onvif_scanner"), None)
    if not scanner:
        raise HTTPException(500, "onvif_scanner no disponible")
    try:
        if asyncio.iscoroutinefunction(scanner.scan):
            result = await scanner.scan(target)
        else:
            result = await asyncio.to_thread(scanner.scan, target)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(500, str(e)[:300])

@router.post("/scan/services")
async def scan_services(target: str):
    """Escaneo de puertos y servicios."""
    _load()
    scanner = next((s for s in _scanners if s.name == "service_scanner"), None)
    if not scanner:
        raise HTTPException(500, "service_scanner no disponible")
    try:
        if asyncio.iscoroutinefunction(scanner.scan):
            result = await scanner.scan(target)
        else:
            result = await asyncio.to_thread(scanner.scan, target)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(500, str(e)[:300])

# ══════════════════════════════════════════════════════════════
# EXPLOITERS
# ══════════════════════════════════════════════════════════════

@router.post("/exploit/camera")
async def exploit_camera(req: ExploitRequest):
    """Explotación de cámara por vendor."""
    _load()
    target = req.target
    context = {"vendor": req.vendor}

    if req.exploit_type == "auto" and req.vendor is None:
        # Detectar primero
        detector = next((s for s in _scanners if s.name == "camera_detector"), None)
        if detector:
            if asyncio.iscoroutinefunction(detector.scan):
                cam_result = await detector.scan(target)
            else:
                cam_result = await asyncio.to_thread(detector.scan, target)
            if isinstance(cam_result, dict) and cam_result.get("cameras"):
                cam = cam_result["cameras"][0]
                context.update(cam)
                vendor = cam.get("vendor", "").lower()
            else:
                vendor = "generic"
        else:
            vendor = "generic"
    else:
        vendor = req.exploit_type

    # Seleccionar exploiter
    name_map = {
        "hikvision": "hikvision_rce",
        "hikvision_rce": "hikvision_rce",
        "dahua": "dahua_backdoor",
        "dahua_backdoor": "dahua_backdoor",
        "generic": "generic_brute",
        "generic_brute": "generic_brute",
        "kraken": "kraken_integration",
    }
    exploiter_name = name_map.get(vendor, "generic_brute")
    exploiter = next((e for e in _exploiters if e.name == exploiter_name), None)
    if not exploiter:
        raise HTTPException(404, f"Exploiter '{exploiter_name}' no encontrado")
    try:
        if asyncio.iscoroutinefunction(exploiter.exploit):
            result = await exploiter.exploit(target, context)
        else:
            result = await asyncio.to_thread(exploiter.exploit, target, context)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(500, str(e)[:300])

@router.post("/exploit/chain")
async def exploit_chain(target: str, chain_name: str = "camera_compromise"):
    """Cadena de exploits predefinida."""
    _load()
    exploiter = next((e for e in _exploiters if e.name == "exploit_chain"), None)
    if not exploiter:
        raise HTTPException(404, "exploit_chain no disponible")
    try:
        if asyncio.iscoroutinefunction(exploiter.exploit):
            result = await exploiter.exploit(target, {"chain": chain_name})
        else:
            result = await asyncio.to_thread(exploiter.exploit, target, {"chain": chain_name})
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(500, str(e)[:300])

# ══════════════════════════════════════════════════════════════
# AI ANALYZERS
# ══════════════════════════════════════════════════════════════

@router.post("/ai/threat-scoring")
async def ai_threat_scoring(target: str, data: Dict = None):
    """Puntuación de amenazas."""
    _load()
    analyzer = next((a for a in _analyzers if a.name == "threat_scoring"), None)
    if not analyzer:
        raise HTTPException(404, "threat_scoring no disponible")
    try:
        if asyncio.iscoroutinefunction(analyzer.analyze):
            result = await analyzer.analyze(target, data or {})
        else:
            result = await asyncio.to_thread(analyzer.analyze, target, data or {})
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(500, str(e)[:300])

@router.post("/ai/anomalies")
async def ai_anomalies(target: str, data: Dict = None):
    """Detección de anomalías."""
    _load()
    analyzer = next((a for a in _analyzers if a.name == "anomaly_detector"), None)
    if not analyzer:
        raise HTTPException(404, "anomaly_detector no disponible")
    try:
        if asyncio.iscoroutinefunction(analyzer.analyze):
            result = await analyzer.analyze(target, data or {})
        else:
            result = await asyncio.to_thread(analyzer.analyze, target, data or {})
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(500, str(e)[:300])

@router.post("/ai/behavior")
async def ai_behavior(target: str, data: Dict = None):
    """Análisis de comportamiento."""
    _load()
    analyzer = next((a for a in _analyzers if a.name == "behavior_analyzer"), None)
    if not analyzer:
        raise HTTPException(404, "behavior_analyzer no disponible")
    try:
        if asyncio.iscoroutinefunction(analyzer.analyze):
            result = await analyzer.analyze(target, data or {})
        else:
            result = await asyncio.to_thread(analyzer.analyze, target, data or {})
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(500, str(e)[:300])

# ══════════════════════════════════════════════════════════════
# REPORTERS
# ══════════════════════════════════════════════════════════════

@router.post("/report/json")
async def report_json(target: str, data: Dict = None):
    """Informe JSON."""
    _load()
    reporter = next((r for r in _reporters if r.name == "json_reporter"), None)
    if not reporter:
        raise HTTPException(404, "json_reporter no disponible")
    try:
        if asyncio.iscoroutinefunction(reporter.generate):
            result = await reporter.generate(target, data or {})
        else:
            result = await asyncio.to_thread(reporter.generate, target, data or {})
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(500, str(e)[:300])

@router.post("/report/html")
async def report_html(target: str, data: Dict = None):
    """Informe HTML."""
    _load()
    reporter = next((r for r in _reporters if r.name == "html_reporter"), None)
    if not reporter:
        raise HTTPException(404, "html_reporter no disponible")
    try:
        if asyncio.iscoroutinefunction(reporter.generate):
            result = await reporter.generate(target, data or {})
        else:
            result = await asyncio.to_thread(reporter.generate, target, data or {})
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(500, str(e)[:300])

# ══════════════════════════════════════════════════════════════
# SYSTEM
# ══════════════════════════════════════════════════════════════

@router.get("/status")
async def system_status():
    """Estado completo del sistema LEVIATHAN."""
    _load()
    profiles = _load_profiles()
    return {
        "system": "LEVIATHAN UNIFIED",
        "version": "3.0.0",
        "timestamp": datetime.now().isoformat(),
        "modules": {
            "scanners": [s.to_dict() for s in _scanners],
            "exploiters": [e.to_dict() for e in _exploiters],
            "ai_analyzers": [a.to_dict() for a in _analyzers],
            "reporters": [r.to_dict() for r in _reporters],
        },
        "profiles": list(profiles.get("scan_profiles", {}).keys()) if profiles else [],
        "endpoints": {
            "scanners": ["/api/v1/scan/network", "/api/v1/scan/cameras", "/api/v1/scan/rtsp", "/api/v1/scan/onvif", "/api/v1/scan/services"],
            "exploiters": ["/api/v1/exploit/camera", "/api/v1/exploit/chain"],
            "ai": ["/api/v1/ai/threat-scoring", "/api/v1/ai/anomalies", "/api/v1/ai/behavior"],
            "reporters": ["/api/v1/report/json", "/api/v1/report/html"],
            "system": ["/api/v1/status", "/api/v1/health", "/api/v1/profiles"],
        }
    }

@router.get("/health")
async def health_check():
    """Health check del sistema."""
    _load()
    return {
        "status": "healthy",
        "modules_loaded": len(_scanners) + len(_exploiters) + len(_analyzers) + len(_reporters),
        "timestamp": datetime.now().isoformat(),
    }

@router.get("/profiles")
async def get_profiles():
    """Obtener perfiles de escaneo configurados."""
    profiles = _load_profiles()
    return profiles.get("scan_profiles", {})
