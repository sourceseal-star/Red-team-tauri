# -*- coding: utf-8 -*-
"""
NDR Bridge — conecta el módulo NDR (Network Detection & Response) al dashboard
=============================================================================

Módulo que corre: redteam/scripts/dashboard_server.py lo monta en /api/ndr/*
(patrón idéntico al interceptor_bridge v2). El sniffer NDR estaba escrito de
verdad (Scapy + flujos bidireccionales + C2/exfil/tunnel) pero huérfano —
ninguna ruta lo servía. Este puente lo conecta SIN tocar el módulo original.

Endpoints (prefijo /api/ndr):
  POST /control   {action: start|stop|status, interface?}
  GET  /status    — estado de captura + motores + root
  GET  /flows     — flujos reconstruidos (bidireccionales)
  GET  /alerts    — alertas del motor (beaconing C2, exfiltración, túneles)
  GET  /summary   — resumen de alertas por tipo/severidad + MITRE
  POST /pcap      — analiza un archivo .pcap (funciona SIN root)

Realidad de permisos (2026-09-08):
  - Captura EN VIVO: necesita root (raw socket). En Termux con root → wlan0.
  - Análisis de PCAP: sin root, siempre disponible si scapy está instalado.
  El endpoint /status informa todo esto para no dejar a nadie a ciegas.
"""
import os
import threading

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional

from .network_capture import NetworkCapture, load_pcap, SCAPY_AVAILABLE, PYSHARK_AVAILABLE
from .engine import NDREngine, TrafficFlow as EngineTrafficFlow

router = APIRouter(prefix="/api/ndr", tags=["ndr-bridge"])

# Instancias únicas — viven mientras viva el proceso del dashboard
_capture = NetworkCapture(max_flows=10000)
_engine = NDREngine()

# Hilo que alimenta el motor con los flujos capturados (sin duplicados)
_poller_stop = threading.Event()
_poller: Optional[threading.Thread] = None
_last_seen = {}


def _default_iface() -> str:
    """Android/Termux → wlan0; Linux/otros → eth0."""
    return "wlan0" if os.path.exists("/data/data/com.termux") else "eth0"


def _poller_loop():
    """
    Cada 5s ingresa al motor SOLO los flujos con tráfico nuevo.
    Un flujo se re-ingesta solo cuando sus bytes crecieron — evita
    inflar el detector C2 con el mismo flujo duplicado.
    El poller NUNCA tumba el dashboard: todo envuelto en try.
    """
    while not _poller_stop.wait(5.0):
        try:
            for f in _capture.get_flows():
                key = (f.src_ip, f.dst_ip, f.src_port, f.dst_port, f.protocol)
                total = f.bytes_sent + f.bytes_recv
                if _last_seen.get(key) != total:
                    _last_seen[key] = total
                    _ingest(f)
        except Exception:
            pass



def _ts_epoch(t) -> float:
    """datetime → epoch; float → tal cual."""
    if hasattr(t, "timestamp"):
        return t.timestamp()
    return float(t)


def _ingest(f) -> None:
    """
    Ingresa un flujo al motor con el TIMESTAMP REAL del paquete.
    ingest_flow_raw() del motor usa time.time() (útil para captura en vivo,
    destructivo para PCAPs históricos: todos los beacons quedarían 'ahí
    mismo' y el detector C2 no vería intervalos). Por esto el puente
    construye el TrafficFlow del motor directamente.
    """
    try:
        _engine.ingest_flow(EngineTrafficFlow(
            src_ip=f.src_ip, dst_ip=f.dst_ip, dst_port=f.dst_port,
            protocol=f.protocol, bytes_sent=f.bytes_sent,
            bytes_received=f.bytes_recv,
            timestamp=_ts_epoch(f.timestamp),
            duration_ms=int(f.duration_ms),
        ))
    except Exception:
        pass


class NdrControlRequest(BaseModel):
    action: str  # start | stop | status
    interface: Optional[str] = None


@router.post("/control")
async def control(req: NdrControlRequest):
    global _poller
    if req.action == "start":
        iface = (req.interface or _default_iface()).strip()
        if not (SCAPY_AVAILABLE or PYSHARK_AVAILABLE):
            return {
                "ok": False,
                "error": "Sin motores de captura: pip install scapy. "
                         "Mientras tanto /api/ndr/pcap analiza archivos sin root.",
            }
        _capture.start(interface=iface)
        _poller_stop.clear()
        if _poller is None or not _poller.is_alive():
            _poller = threading.Thread(target=_poller_loop, name="NDR-Poller", daemon=True)
            _poller.start()
        return {"ok": True, "running": True, "interface": iface,
                "hint": "Si no ves flujos en unos segundos, revisa /api/ndr/status — root probablemente requerido."}

    if req.action == "stop":
        _capture.stop()
        _poller_stop.set()
        return {"ok": True, "running": False, "interface": _capture.interface}

    # status
    return {"ok": True, "running": _capture.running, "interface": _capture.interface}


@router.get("/status")
async def status():
    return {
        "running": _capture.running,
        "interface": _capture.interface,
        "scapy_available": SCAPY_AVAILABLE,
        "pyshark_available": PYSHARK_AVAILABLE,
        "root": (os.geteuid() == 0) if hasattr(os, "geteuid") else False,
        "flows_in_buffer": len(_capture.circular_buffer),
        "alerts_total": len(_engine.alerts),
        "note": "Captura en vivo = requiere root. /api/ndr/pcap = analiza archivos sin root.",
    }


@router.get("/flows")
async def flows(limit: int = Query(50, ge=1, le=500)):
    items = list(_capture.get_flows())[-limit:]
    return {
        "count": len(items),
        "flows": [
            {
                "src": f.src_ip, "dst": f.dst_ip,
                "src_port": f.src_port, "dst_port": f.dst_port,
                "protocol": f.protocol,
                "bytes_sent": f.bytes_sent, "bytes_recv": f.bytes_recv,
                "duration_ms": f.duration_ms,
                "timestamp": f.timestamp.isoformat() if hasattr(f.timestamp, "isoformat") else f.timestamp,
                "dns_query": f.dns_query,
            }
            for f in items
        ],
    }


@router.get("/alerts")
async def alerts(since: float = 0, limit: int = Query(100, ge=1, le=500)):
    a = _engine.get_alerts(since=since)
    return {"count": len(a), "alerts": a[:limit]}


@router.get("/summary")
async def summary():
    s = _engine.get_summary()
    s["capture_running"] = _capture.running
    s["interface"] = _capture.interface
    return s


class PcapRequest(BaseModel):
    path: str


@router.post("/pcap")
async def pcap(req: PcapRequest):
    """Análisis forense de un PCAP — reconstruye flujos y los pasa por el motor."""
    if not os.path.isfile(req.path):
        return {"ok": False, "error": f"No existe el archivo: {req.path}"}
    if not (SCAPY_AVAILABLE or PYSHARK_AVAILABLE):
        return {"ok": False, "error": "Sin motor de lectura: pip install scapy"}
    try:
        flows = load_pcap(req.path)
    except Exception as e:
        return {"ok": False, "error": f"No se pudo leer el PCAP: {e}"}
    for f in flows:
        _ingest(f)
    return {"ok": True, "file": req.path, "flows_analyzed": len(flows),
            "summary": _engine.get_summary()}
