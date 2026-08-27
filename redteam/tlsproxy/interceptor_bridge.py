"""
Interceptor Bridge v2 - Integracion profunda con frontend
========================================================
Envuelve las funciones reales de interceptor_advanced.py en un formato
estructurado para el panel Interceptor Advanced del frontend.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
import json

from .interceptor_advanced import (
    InjectionDetector, RequestAnalyzer, ResponseAnalyzer,
    SIEMLogger, _traffic_capture,
    interceptor_router,
)

router = APIRouter(prefix="/api/interceptor/v2", tags=["interceptor-bridge-v2"])


class ProxyControlRequest(BaseModel):
    action: str  # start, stop, status
    port: int = 8888


class FlowAnalysisRequest(BaseModel):
    analyze_injections: bool = True
    analyze_payloads: bool = True


@router.post("/control")
async def control_proxy(request: ProxyControlRequest):
    """Control del capturador de trafico (honeypot TCP)."""
    if request.action == "start":
        result = await _traffic_capture.start_capture(request.port)
        return result
    elif request.action == "stop":
        result = await _traffic_capture.stop_capture()
        return result
    elif request.action == "status":
        return {
            "running": _traffic_capture.active,
            "port": request.port if _traffic_capture.active else None,
            "total_flows": len(_traffic_capture.captured_flows),
            "total_alerts": sum(
                len(json.loads(f.get("alerts", "[]")) if isinstance(f.get("alerts"), str) else f.get("alerts", []))
                for f in _traffic_capture.captured_flows
            ),
        }
    else:
        raise HTTPException(status_code=400, detail="Accion no valida: use start, stop o status")


@router.get("/flows")
async def get_flows(limit: int = 50, filter_malicious: bool = False):
    """Obtener flujos capturados."""
    if not _traffic_capture.active and not _traffic_capture.captured_flows:
        return {"total": 0, "flows": []}

    flows = _traffic_capture.get_captured(limit)

    if filter_malicious:
        flows = [f for f in flows if f.get("alerts") and f["alerts"] != "[]"]

    # Normalizar formato para el frontend
    formatted = []
    for f in flows:
        alerts = json.loads(f.get("alerts", "[]")) if isinstance(f.get("alerts"), str) else f.get("alerts", [])
        formatted.append({
            "flow_id": f.get("id", ""),
            "src_ip": f.get("src_ip", ""),
            "dst_host": f.get("dst_host", "localhost"),
            "dst_port": f.get("dst_port", 0),
            "method": f.get("method", "TCP"),
            "path": f.get("path", ""),
            "status_code": f.get("status_code", 0),
            "request_size": f.get("request_size", 0),
            "is_suspicious": len(alerts) > 0,
            "is_malicious": any(a.get("severity") in ("critical", "high") for a in alerts),
            "severity": alerts[0]["severity"] if alerts and isinstance(alerts, list) and isinstance(alerts[0], dict) else "info",
            "alerts_count": len(alerts),
            "timestamp": f.get("timestamp", ""),
            "raw_data": f.get("raw_data", "")[:200],
        })

    return {"total": len(formatted), "flows": formatted}


@router.get("/alerts")
async def get_alerts(limit: int = 50, severity: Optional[str] = None):
    """Obtener alertas de los flujos capturados."""
    all_alerts = []
    for f in _traffic_capture.captured_flows:
        alerts = json.loads(f.get("alerts", "[]")) if isinstance(f.get("alerts"), str) else f.get("alerts", [])
        for a in alerts:
            alert = {
                "flow_id": f.get("id", ""),
                "src_ip": f.get("src_ip", ""),
                "alert_type": a.get("alert_type", a.get("type", "unknown")),
                "severity": a.get("severity", "info"),
                "payload": a.get("payload", "")[:100],
                "pattern_matched": a.get("pattern_matched", a.get("pattern", "")),
                "cwe": a.get("cwe", ""),
                "mitre": a.get("mitre", ""),
                "timestamp": f.get("timestamp", ""),
            }
            if severity is None or alert["severity"] == severity:
                all_alerts.append(alert)

    return {"total": len(all_alerts), "alerts": all_alerts[-limit:]}


@router.get("/stats")
async def get_stats():
    """Estadisticas del interceptor."""
    flows = _traffic_capture.captured_flows
    total_alerts = 0
    by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}

    for f in flows:
        alerts = json.loads(f.get("alerts", "[]")) if isinstance(f.get("alerts"), str) else f.get("alerts", [])
        total_alerts += len(alerts)
        for a in alerts:
            sev = a.get("severity", "info")
            if sev in by_severity:
                by_severity[sev] += 1

    # Tipos de ataque detectados
    attack_types = {}
    for f in flows:
        alerts = json.loads(f.get("alerts", "[]")) if isinstance(f.get("alerts"), str) else f.get("alerts", [])
        for a in alerts:
            atype = a.get("alert_type", a.get("type", "unknown"))
            attack_types[atype] = attack_types.get(atype, 0) + 1

    return {
        "active": _traffic_capture.active,
        "total_flows": len(flows),
        "total_alerts": total_alerts,
        "by_severity": by_severity,
        "attack_types": attack_types,
        "unique_src_ips": len(set(f.get("src_ip", "") for f in flows)),
    }


@router.post("/analyze-flow/{flow_id}")
async def analyze_flow(flow_id: str, request: FlowAnalysisRequest):
    """Analizar un flujo especifico en profundidad."""
    flow = None
    for f in _traffic_capture.captured_flows:
        if f.get("id") == flow_id:
            flow = f
            break

    if not flow:
        raise HTTPException(status_code=404, detail="Flujo no encontrado")

    raw_data = flow.get("raw_data", "")

    # Deteccion de inyecciones
    injection_results = {}
    if request.analyze_injections and raw_data:
        detector = InjectionDetector()
        detected = detector.analyze(raw_data)
        for d in detected:
            itype = d.get("type", "unknown")
            injection_results[itype] = {
                "is_vulnerable": True,
                "pattern": d.get("pattern", ""),
                "cwe": d.get("cwe", ""),
                "mitre": d.get("mitre", ""),
                "payload": d.get("payload", raw_data[:100]),
            }

    # Generar recomendaciones
    recommendations = []
    alerts = json.loads(flow.get("alerts", "[]")) if isinstance(flow.get("alerts"), str) else flow.get("alerts", [])
    for a in alerts:
        atype = a.get("alert_type", a.get("type", ""))
        if "sqli" in atype.lower() or "sql" in atype.lower():
            recommendations.append("Usar consultas parametrizadas y sanitizar inputs")
        elif "xss" in atype.lower():
            recommendations.append("Escapar outputs HTML y usar CSP headers")
        elif "rce" in atype.lower() or "command" in atype.lower():
            recommendations.append("Restringir ejecucion de comandos del sistema")
        elif "path" in atype.lower() or "traversal" in atype.lower():
            recommendations.append("Validar rutas de archivo y restringir directorios base")

    for itype, data in injection_results.items():
        if data.get("is_vulnerable"):
            if "sqli" in itype.lower():
                recommendations.append("Vulnerabilidad SQLi: Usar ORM o consultas preparadas")
            elif "xss" in itype.lower():
                recommendations.append("Vulnerabilidad XSS: Implementar sanitizacion HTML")
            elif "rce" in itype.lower():
                recommendations.append("Vulnerabilidad RCE: Restringir ejecucion de comandos")

    if not recommendations:
        recommendations.append("No se detectaron vulnerabilidades criticas")

    return {
        "flow_id": flow_id,
        "src_ip": flow.get("src_ip", ""),
        "raw_data": raw_data[:500],
        "alerts": alerts,
        "injection_detection": injection_results,
        "recommendations": recommendations,
    }
