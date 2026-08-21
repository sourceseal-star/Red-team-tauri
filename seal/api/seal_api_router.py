#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SEAL API ROUTER - Endpoints FastAPI para SEAL SUPER PACK
========================================================
Proporciona una API REST para interactuar con el SEAL SUPER PACK.

Endpoints disponibles:
- GET /api/devices - Lista todos los dispositivos
- GET /api/devices/{ip} - Obtiene un dispositivo específico
- GET /api/scan - Ejecuta un escaneo de red
- GET /api/scan/{ip} - Escanea una IP específica
- GET /api/alerts - Lista todas las alertas
- GET /api/alerts/unresolved - Lista alertas no resueltas
- POST /api/alerts/{id}/resolve - Resuelve una alerta
- GET /api/status - Obtiene el estado del orquestador
- GET /api/arto/analyze - Analiza con ARTO
- GET /api/arto/predictions - Obtiene predicciones de ARTO
- POST /api/arto/operation - Ejecuta una operación autónoma

Autor: Harold Paredes / SourceSeal Red Team
Uso: Incluir en tu aplicación FastAPI: from seal.api.seal_api_router import router
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Dict, Optional
import asyncio
import json
from datetime import datetime

# Importar módulos
from seal.scanners.network_sweep_ultimate import (
    discover_active_ips, scan_target, get_my_network
)
from seal.attackers.hikvision_killer import scan_and_attack
from seal.scanners.onvif_scanner import check_onvif_ports, scan_network
from seal.scanners.fingerprint_engine import FingerprintEngine, VulnerabilityAnalyzer
from seal.orchestrator.seal_orchestrator import get_orchestrator
from seal.ai.arto_integration import get_arto_integration
from seal.utils.vendor_dicts import VENDOR_CREDS, get_vendor_creds


# ============================================================
# CONFIGURACIÓN
# ============================================================

router = APIRouter(prefix="/api", tags=["seal"])

# Instancias globales
fingerprint_engine = FingerprintEngine()
vuln_analyzer = VulnerabilityAnalyzer()


# ============================================================
# ENDPOINTS DE DISPOSITIVOS
# ============================================================

@router.get("/devices", summary="Lista todos los dispositivos")
async def get_devices(status: Optional[str] = None, risk: Optional[str] = None):
    """
    Obtiene la lista de todos los dispositivos detectados.
    
    Parámetros:
    - status: Filtrar por estado (active, inactive)
    - risk: Filtrar por nivel de riesgo (low, medium, high, critical)
    """
    orchestrator = get_orchestrator()
    devices = orchestrator.device_manager.get_all_devices()
    
    # Filtrar
    if status:
        devices = [d for d in devices if d.get("status") == status]
    if risk:
        devices = [d for d in devices if d.get("risk") == risk]
    
    return JSONResponse(content={
        "success": True,
        "count": len(devices),
        "devices": devices
    })


@router.get("/devices/{ip}", summary="Obtiene un dispositivo específico")
async def get_device(ip: str):
    """
    Obtiene información de un dispositivo específico.
    
    Parámetros:
    - ip: IP del dispositivo
    """
    orchestrator = get_orchestrator()
    device = orchestrator.device_manager.get_device(ip)
    
    if not device:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    
    return JSONResponse(content={
        "success": True,
        "device": device
    })


@router.get("/devices/{ip}/scan", summary="Escanea un dispositivo")
async def scan_device(ip: str, deep: bool = False):
    """
    Escanea un dispositivo específico.
    
    Parámetros:
    - ip: IP del dispositivo
    - deep: Escaneo profundo (opcional)
    """
    try:
        result = await scan_target(ip, deep)
        
        # Analizar con fingerprint
        fingerprint_result = fingerprint_engine.identify(
            banner=result.get("services", [{}])[0].get("banner"),
            port=result.get("services", [{}])[0].get("port"),
            ip=ip
        )
        
        # Verificar vulnerabilidades
        if fingerprint_result.get("vendor") != "Unknown":
            fingerprint_result["vulnerabilities"] = vuln_analyzer.check_vulnerabilities(
                fingerprint_result["vendor"],
                fingerprint_result.get("model", "")
            )
        
        result["fingerprint"] = fingerprint_result
        
        return JSONResponse(content={
            "success": True,
            "result": result
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# ENDPOINTS DE ESCANEO
# ============================================================

@router.get("/scan", summary="Ejecuta escaneo de red")
async def start_scan(network: Optional[str] = None, deep: bool = False, 
                     background_tasks: BackgroundTasks = None):
    """
    Ejecuta un escaneo completo de la red.
    
    Parámetros:
    - network: Red a escanear (ej: 192.168.1.0/24)
    - deep: Escaneo profundo
    """
    try:
        net = network or get_my_network()
        
        # Escanear IPs activas
        active_ips = await discover_active_ips(net)
        
        # Escanear cada IP
        results = []
        for ip in active_ips:
            target_data = await scan_target(ip, deep)
            
            # Analizar con fingerprint
            fingerprint_result = fingerprint_engine.identify(
                banner=target_data.get("services", [{}])[0].get("banner"),
                port=target_data.get("services", [{}])[0].get("port"),
                ip=ip
            )
            
            # Verificar vulnerabilidades
            if fingerprint_result.get("vendor") != "Unknown":
                fingerprint_result["vulnerabilities"] = vuln_analyzer.check_vulnerabilities(
                    fingerprint_result["vendor"],
                    fingerprint_result.get("model", "")
                )
            
            target_data["fingerprint"] = fingerprint_result
            results.append(target_data)
        
        # Filtrar solo resultados con servicios
        targets = [r for r in results if r['services']]
        
        return JSONResponse(content={
            "success": True,
            "network": net,
            "scanned_ips": len(active_ips),
            "targets": targets
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scan/quick", summary="Escaneo rápido")
async def quick_scan(network: Optional[str] = None):
    """
    Ejecuta un escaneo rápido (solo detección de IPs activas).
    
    Parámetros:
    - network: Red a escanear
    """
    try:
        net = network or get_my_network()
        active_ips = await discover_active_ips(net)
        
        return JSONResponse(content={
            "success": True,
            "network": net,
            "active_ips": active_ips
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# ENDPOINTS DE ALERTAS
# ============================================================

@router.get("/alerts", summary="Lista todas las alertas")
async def get_alerts(resolved: Optional[bool] = None, severity: Optional[str] = None,
                     limit: int = 100):
    """
    Obtiene la lista de alertas.
    
    Parámetros:
    - resolved: Filtrar por estado (True/False)
    - severity: Filtrar por gravedad (info, warning, high, critical)
    - limit: Límites de resultados
    """
    orchestrator = get_orchestrator()
    alerts = orchestrator.alert_manager.get_alerts(
        resolved=resolved, severity=severity, limit=limit
    )
    
    return JSONResponse(content={
        "success": True,
        "count": len(alerts),
        "alerts": alerts
    })


@router.post("/alerts/{alert_id}/resolve", summary="Resuelve una alerta")
async def resolve_alert(alert_id: int):
    """
    Marca una alerta como resuelta.
    
    Parámetros:
    - alert_id: ID de la alerta
    """
    orchestrator = get_orchestrator()
    success = orchestrator.alert_manager.resolve_alert(alert_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    
    return JSONResponse(content={
        "success": True,
        "message": f"Alerta {alert_id} resuelta"
    })


# ============================================================
# ENDPOINTS DE ESTADO
# ============================================================

@router.get("/status", summary="Estado del orquestador")
async def get_status():
    """Obtiene el estado del orquestador."""
    orchestrator = get_orchestrator()
    status = orchestrator.get_status()
    
    return JSONResponse(content={
        "success": True,
        "status": status
    })


@router.get("/stats", summary="Estadísticas")
async def get_stats():
    """Obtiene estadísticas del sistema."""
    orchestrator = get_orchestrator()
    status = orchestrator.get_status()
    
    # Estadísticas adicionales
    devices = orchestrator.device_manager.get_all_devices()
    
    vendor_stats = {}
    type_stats = {}
    risk_stats = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    
    for device in devices:
        vendor = device.get("vendor", "Unknown")
        device_type = device.get("type", "Unknown")
        risk = device.get("risk", "low")
        
        vendor_stats[vendor] = vendor_stats.get(vendor, 0) + 1
        type_stats[device_type] = type_stats.get(device_type, 0) + 1
        risk_stats[risk] = risk_stats.get(risk, 0) + 1
    
    return JSONResponse(content={
        "success": True,
        "orchestrator": status,
        "stats": {
            "vendors": vendor_stats,
            "types": type_stats,
            "risks": risk_stats
        }
    })


# ============================================================
# ENDPOINTS DE ARTO
# ============================================================

@router.get("/arto/analyze", summary="Analiza con ARTO")
async def arto_analyze(target: Optional[str] = None):
    """
    Analiza un objetivo con ARTO.
    
    Parámetros:
    - target: IP o dominio a analizar
    """
    try:
        integration = get_arto_integration()
        
        if target:
            # Analizar objetivo específico
            result = await integration.process_single_target(target)
        else:
            # Analizar todos los dispositivos
            orchestrator = get_orchestrator()
            devices = orchestrator.device_manager.get_all_devices()
            
            results = []
            for device in devices:
                result = await integration.process_single_target(device.get("ip"), device)
                results.append(result)
            
            return JSONResponse(content={
                "success": True,
                "count": len(results),
                "results": results
            })
        
        return JSONResponse(content={
            "success": True,
            "result": result
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/arto/predictions", summary="Obtiene predicciones de ARTO")
async def arto_predictions(timeframe: int = 24):
    """
    Obtiene predicciones de ARTO.
    
    Parámetros:
    - timeframe: Horizonte de predicción en horas
    """
    try:
        integration = get_arto_integration()
        result = await integration.get_autonomous_recommendations()
        
        return JSONResponse(content={
            "success": True,
            "predictions": result
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/arto/operation", summary="Ejecuta operación autónoma")
async def arto_operation(target: str, operation_type: str, data: Dict = {}):
    """
    Ejecuta una operación autónoma en un objetivo.
    
    Parámetros:
    - target: IP o dominio del objetivo
    - operation_type: Tipo de operación (scan, simulate, monitor, investigate, defend)
    - data: Datos adicionales
    """
    try:
        integration = get_arto_integration()
        
        # Para operaciones de escaneo, usar el escáner directamente
        if operation_type == "scan":
            scan_result = await scan_target(target)
            arto_result = await integration.process_scan_results({
                "scan": {
                    "timestamp": datetime.now().isoformat(),
                    "network": "single_target",
                    "total_devices": 1
                },
                "targets": [scan_result]
            })
            return JSONResponse(content={
                "success": True,
                "scan_result": scan_result,
                "arto_analysis": arto_result
            })
        
        # Para otras operaciones, usar ARTO
        result = await integration.process_single_target(target, data)
        
        return JSONResponse(content={
            "success": True,
            "result": result
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# ENDPOINTS DE HIKVISION
# ============================================================

@router.get("/hikvision/scan", summary="Escanea cámaras Hikvision")
async def hikvision_scan(network: Optional[str] = None):
    """
    Escanea la red en busca de cámaras Hikvision.
    
    Parámetros:
    - network: Red a escanear
    """
    try:
        from seal.attackers.hikvision_killer import is_hikvision_device, get_hikvision_model
        import ipaddress
        
        net = network or get_my_network()
        ip_network = ipaddress.ip_network(net, strict=False)
        all_ips = [str(ip) for ip in ip_network.hosts()]
        
        hikvision_cameras = []
        for ip in all_ips:
            is_hik, banner = await is_hikvision_device(ip)
            if is_hik:
                model = await get_hikvision_model(ip)
                hikvision_cameras.append({
                    "ip": ip,
                    "model": model,
                    "banner": banner
                })
        
        return JSONResponse(content={
            "success": True,
            "network": net,
            "scanned_ips": len(all_ips),
            "hikvision_cameras": hikvision_cameras
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hikvision/attack/{ip}", summary="Ataque a cámara Hikvision")
async def hikvision_attack(ip: str):
    """
    Ejecuta ataque completo a una cámara Hikvision.
    
    Parámetros:
    - ip: IP de la cámara
    """
    try:
        result = await scan_and_attack(ip)
        
        return JSONResponse(content={
            "success": True,
            "result": result
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# ENDPOINTS DE ONVIF
# ============================================================

@router.get("/onvif/scan", summary="Escanea dispositivos ONVIF")
async def onvif_scan(network: Optional[str] = None):
    """
    Escanea la red en busca de dispositivos ONVIF.
    
    Parámetros:
    - network: Red a escanear
    """
    try:
        devices = await scan_network(network or get_my_network())
        
        return JSONResponse(content={
            "success": True,
            "network": network or get_my_network(),
            "onvif_devices": devices
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/onvif/check/{ip}", summary="Verifica dispositivo ONVIF")
async def onvif_check(ip: str):
    """
    Verifica si un dispositivo es ONVIF.
    
    Parámetros:
    - ip: IP del dispositivo
    """
    try:
        devices = await check_onvif_ports(ip)
        
        return JSONResponse(content={
            "success": True,
            "ip": ip,
            "onvif_devices": devices
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# ENDPOINTS DE DICCIONARIOS
# ============================================================

@router.get("/dicts/vendors", summary="Lista todos los vendors")
async def get_vendors():
    """Obtiene la lista de todos los vendors con diccionarios."""
    return JSONResponse(content={
        "success": True,
        "vendors": list(VENDOR_CREDS.keys())
    })


@router.get("/dicts/{vendor}", summary="Obtiene diccionario de un vendor")
async def get_vendor_dict(vendor: str):
    """
    Obtiene el diccionario de credenciales de un vendor.
    
    Parámetros:
    - vendor: Nombre del vendor
    """
    creds = get_vendor_creds(vendor)
    
    if not creds:
        raise HTTPException(status_code=404, detail="Vendor no encontrado")
    
    return JSONResponse(content={
        "success": True,
        "vendor": vendor,
        "credentials_count": len(creds),
        "credentials": creds
    })


@router.get("/dicts/all", summary="Obtiene todas las credenciales")
async def get_all_dicts():
    """Obtiene todas las credenciales de todos los vendors."""
    all_creds = {}
    for vendor, creds in VENDOR_CREDS.items():
        all_creds[vendor] = creds
    
    return JSONResponse(content={
        "success": True,
        "total_vendors": len(all_creds),
        "total_credentials": sum(len(c) for c in all_creds.values()),
        "credentials": all_creds
    })


# ============================================================
# ENDPOINT DE SALUD
# ============================================================

@router.get("/health", summary="Verifica estado del servicio")
async def health_check():
    """Verifica que el servicio esté funcionando."""
    return JSONResponse(content={
        "success": True,
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0"
    })


# ============================================================
# INTEGRACIÓN CON APP PRINCIPAL
# ============================================================

def get_seal_router() -> APIRouter:
    """Obtiene el router de SEAL."""
    return router


def include_seal_routes(app):
    """Incluye las rutas de SEAL en la aplicación FastAPI."""
    app.include_router(router)