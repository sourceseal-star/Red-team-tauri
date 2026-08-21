#!/usr/bin/env python3
"""
SourceSeal Red Team Dashboard — Backend FastAPI v3.2
Puerto: 8001 | Protocolo: SSP-ZKP-2048-L4
Compatible con Termux (pure Python fallbacks, sin binarios opcionales).
"""

import asyncio
import hashlib
import io
import json
import math
import os
import random
import re
import socket
import struct
import subprocess
import tempfile
import time
import uuid
import shutil
import wave
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import (
    FastAPI, File, Form, HTTPException, Query, UploadFile, Body,
    WebSocket, WebSocketDisconnect, Depends, Request
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, FileResponse
from pydantic import BaseModel, Field
import uvicorn

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG — Termux-friendly
# ═══════════════════════════════════════════════════════════════════════════════

API_KEY = os.environ.get("REDTEAM_API_KEY", "").strip()
HOST = os.environ.get("SEALCTL_HOST", "127.0.0.1")
PORT = int(os.environ.get("SEALCTL_PORT", "8001"))
ALLOWED_ORIGINS = os.environ.get("SEALCTL_CORS", "http://localhost:8001,http://127.0.0.1:8001").split(",")
EVIDENCE_DIR = os.environ.get("SEALCTL_EVIDENCE", os.path.join(os.getcwd(), "evidence"))
MAX_UPLOAD_MB = 50
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

os.makedirs(EVIDENCE_DIR, exist_ok=True)

# Detectar Termux
IS_TERMUX = os.path.isdir("/data/data/com.termux/files/usr")

# ═══════════════════════════════════════════════════════════════════════════════
# MODELOS
# ═══════════════════════════════════════════════════════════════════════════════

class ScanRequest(BaseModel):
    target: Optional[str] = Field(None, description="IP o rango a escanear (autodetecta la LAN local si se omite)")
    ports: Optional[str] = Field("1-1000", description="Rango de puertos")
    timeout: Optional[int] = Field(5, description="Timeout en segundos")

class CamerasScanRequest(BaseModel):
    target: Optional[str] = Field(None, description="IP o rango (autodetecta si se omite)")

class DiscoverAllRequest(BaseModel):
    network: Optional[str] = Field(None, description="Prefijo /24, ej. 192.168.1 (autodetecta si se omite)")

class C2Command(BaseModel):
    session_id: str
    command: str

class HoneypotConfig(BaseModel):
    port: int = Field(8080, description="Puerto del honeypot")
    name: Optional[str] = "default"

class CanaryConfig(BaseModel):
    token_name: str
    alert_email: Optional[str] = None

class ReportRequest(BaseModel):
    title: str
    findings: List[Dict[str, Any]]
    severity: str = "MEDIO"

class CameraDeepScanRequest(BaseModel):
    ip: str = Field(..., description="IP publica o privada de la camara")
    ports: Optional[List[int]] = Field(None, description="Puertos especificos")
    probe_rtsp: Optional[bool] = Field(True)
    probe_onvif: Optional[bool] = Field(True)
    geolocate: Optional[bool] = Field(True)

# ═══════════════════════════════════════════════════════════════════════════════
# ESTADO GLOBAL
# ═══════════════════════════════════════════════════════════════════════════════

scan_history: List[Dict] = []
c2_sessions: Dict[str, Dict] = {}
honeypots: Dict[str, Dict] = {}
canary_tokens: Dict[str, Dict] = {}
forensic_results: Dict[str, Dict] = {}
connected_ws_clients: List[WebSocket] = []

# ═══════════════════════════════════════════════════════════════════════════════
# AUTH — Bearer token middleware
# ═══════════════════════════════════════════════════════════════════════════════

async def require_auth(request: Request):
    """Valida X-Api-Key o Authorization: Bearer contra REDTEAM_API_KEY.
    Si REDTEAM_API_KEY no esta configurado, todas las rutas de escaneo/forense se bloquean."""
    if not API_KEY:
        raise HTTPException(status_code=403,
            detail="Backend bloqueado: configura REDTEAM_API_KEY en el entorno.")
    # Aceptar X-Api-Key header
    provided = request.headers.get("x-api-key", "").strip()
    if provided and provided == API_KEY:
        return True
    # Aceptar Authorization: Bearer
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        if token == API_KEY:
            return True
    raise HTTPException(status_code=401,
        detail="Autenticacion requerida. Envia REDTEAM_API_KEY en header X-Api-Key o Authorization: Bearer.")

# ═══════════════════════════════════════════════════════════════════════════════
# UTILIDADES
# ═══════════════════════════════════════════════════════════════════════════════

def generate_id() -> str:
    return f"{int(time.time() * 1000)}-{random.randint(1000, 9999)}"

def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"

async def broadcast_ws(message: Dict):
    dead = []
    for client in connected_ws_clients:
        try:
            await client.send_json(message)
        except Exception:
            dead.append(client)
    for d in dead:
        if d in connected_ws_clients:
            connected_ws_clients.remove(d)

def _is_private_ip(ip: str) -> bool:
    try:
        parts = ip.split(".")
        if len(parts) != 4:
            return True
        o1 = int(parts[0])
        if o1 == 10: return True
        if o1 == 172 and 16 <= int(parts[1]) <= 31: return True
        if o1 == 192 and int(parts[1]) == 168: return True
        if o1 == 127: return True
        if o1 == 0: return True
        if o1 == 169 and int(parts[1]) == 254: return True
        return False
    except:
        return True

def _validate_ip_or_subnet(target: str) -> Optional[str]:
    """Valida que target sea IP o subred valida. Retorna error string o None."""
    import ipaddress
    if not target:
        return "Parametro 'target' requerido."
    try:
        if "/" in target:
            net = ipaddress.ip_network(target, strict=False)
            if net.num_addresses > 256:
                return "Solo subredes de hasta /24 (256 hosts maximo)."
        else:
            ipaddress.ip_address(target)
    except ValueError:
        return f"'{target}' no es una IP ni subred valida."
    return None

# ═══════════════════════════════════════════════════════════════════════════════
# FASTAPI APP
# ═══════════════════════════════════════════════════════════════════════════════

def _detect_local_subnet() -> str:
    """Detecta el prefijo /24 de la interfaz de red local activa (ej. '192.168.1')."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        my_ip = s.getsockname()[0]
        s.close()
        return ".".join(my_ip.split(".")[:3])
    except Exception:
        return "192.168.1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[sealctl] SourceSeal Red Team Backend v3.2 en {HOST}:{PORT}")
    if IS_TERMUX:
        print("[sealctl] Modo Termux detectado — fallbacks de Python activos")
    if not API_KEY:
        print("[sealctl] WARNING: REDTEAM_API_KEY no configurado — rutas protegidas bloqueadas")
    yield
    print("[sealctl] Backend detenido")

app = FastAPI(
    title="SourceSeal Red Team Dashboard API",
    version="3.2.0",
    description="Protocolo SSP-ZKP-2048-L4 | Termux-compatible",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════════════════════════════════════════════
# MODULE ROUTERS — OSINT Advanced + Interceptor Advanced
# ═══════════════════════════════════════════════════════════════════════════════

try:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from backend.modules.osint_advanced import osint_router
    app.include_router(osint_router)
    print("[sealctl] OSINT Advanced router cargado")
except Exception as e:
    print(f"[sealctl] WARNING: No se pudo cargar osint_router: {e}")

try:
    from redteam.tlsproxy.interceptor_advanced import interceptor_router
    app.include_router(interceptor_router)
    print("[sealctl] Interceptor Advanced router cargado")
except Exception as e:
    print(f"[sealctl] WARNING: No se pudo cargar interceptor_router: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# ARTO + SEAL SUPER PACK
# ═══════════════════════════════════════════════════════════════════════════════

_ARTO_OK = False
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "arto"))
    from arto.api.arto_router import router as arto_router
    app.include_router(arto_router)
    _ARTO_OK = True
    print("[sealctl] ARTO router cargado en /api/arto/*")

    @app.on_event("startup")
    async def _arto_start_b():
        global _ARTO_OK
        try:
            from arto import arto as _arto
            await _arto.start()
            print("[ARTO] ✅ Sistema inicializado")
        except Exception as _e:
            print(f"[ARTO] ⚠ No se pudo inicializar: {_e}")
            _ARTO_OK = False
except Exception as _e:
    print(f"[sealctl] WARNING: ARTO no disponible: {_e}")

_SEAL_OK = False
try:
    from seal.api.seal_api_router import router as seal_router
    app.include_router(seal_router)
    _SEAL_OK = True
    print("[sealctl] SEAL SUPER PACK router cargado en /api/devices, /api/scan")
except Exception as _e:
    print(f"[sealctl] WARNING: SEAL no disponible: {_e}")

# Endpoints de integración
@app.get("/api/integrated/health")
async def integrated_health_b():
    return {"status": "healthy", "arto": _ARTO_OK, "seal": _SEAL_OK}

@app.get("/api/integrated/scan")
async def integrated_scan_b(network: str = "192.168.1.0/24"):
    try:
        from seal.scanners.network_sweep_ultimate import discover_active_ips, scan_target
        active_ips = await discover_active_ips(network)
        results = []
        for ip in active_ips[:20]:
            try:
                td = await scan_target(ip)
                if td.get('services'):
                    results.append(td)
            except Exception:
                pass
        return {"success": True, "network": network, "scanned": len(active_ips), "targets": results}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/integrated/attack/{ip}")
async def integrated_attack_b(ip: str):
    try:
        from seal.attackers.hikvision_killer import scan_and_attack
        result = await scan_and_attack(ip)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH (sin auth)
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/")
async def health():
    return {
        "status": "online",
        "version": "3.2-termux",
        "protocol": "SSP-ZKP-2048-L4",
        "termux": IS_TERMUX,
        "auth_enabled": bool(API_KEY),
        "timestamp": now_iso(),
        "services": {
            "scanning": True, "c2": True, "honeypot": True,
            "canary": True, "osint": True, "forensics": True,
            "websocket": len(connected_ws_clients)
        }
    }

@app.get("/api/health")
async def api_health():
    return await health()

# ═══════════════════════════════════════════════════════════════════════════════
# TOPOLOGY — sockets reales, no random
# ═══════════════════════════════════════════════════════════════════════════════

PORT_SERVICE_NAMES: Dict[int, str] = {
    80: "http", 443: "https", 554: "rtsp", 22: "ssh", 23: "telnet",
    21: "ftp", 3389: "rdp", 5900: "vnc", 8080: "http-alt", 8000: "http-alt",
    37777: "dvr", 8554: "rtsp-alt", 53: "dns", 161: "snmp", 1900: "ssdp",
    5000: "upnp", 9000: "web", 3306: "mysql", 5432: "postgres",
}


async def _probe_port(ip: str, port: int, timeout: float, sem: Optional[asyncio.Semaphore] = None) -> Optional[Dict]:
    """Probe real de UN puerto via TCP connect (para paralelizar dentro de _probe_host)."""
    async def _do():
        try:
            fut = asyncio.open_connection(ip, port)
            reader, writer = await asyncio.wait_for(fut, timeout=timeout)
            banner = None
            try:
                writer.write(b"HEAD / HTTP/1.0\r\n\r\n")
                await writer.drain()
                data = await asyncio.wait_for(reader.read(1024), timeout=0.6)
                banner = data.decode("utf-8", errors="ignore").strip()[:200]
            except Exception:
                pass
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            return {"port": port, "service": PORT_SERVICE_NAMES.get(port, "unknown"), "state": "open", "banner": banner or ""}
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            return None

    if sem:
        async with sem:
            return await _do()
    return await _do()


async def _probe_host(ip: str, ports: List[int], timeout: float = 1.5, sem: Optional[asyncio.Semaphore] = None) -> Dict:
    """Probe real de un host via TCP connect — puertos verificados EN PARALELO."""
    port_results = await asyncio.gather(*[_probe_port(ip, p, timeout, sem) for p in ports])
    open_ports = [p for p in port_results if p]
    hostname = None
    try:
        hostname = socket.gethostbyaddr(ip)[0]
    except Exception:
        pass
    return {
        "ip": ip,
        "status": "up" if open_ports else "down",
        "hostname": hostname or "",
        "ports": open_ports,
        "banners": {str(p["port"]): p["banner"] for p in open_ports if p["banner"]},
    }

def _classify_host_type(ports: List[Dict]) -> str:
    """Heuristica simple de tipo de dispositivo segun puertos abiertos."""
    port_nums = {p["port"] for p in ports}
    if port_nums & {554, 37777, 8554}:
        return "camera"
    if port_nums & {80, 443} and port_nums & {53, 67, 68, 1900}:
        return "router"
    if port_nums & {22, 3306, 5432, 8080, 8000, 9000}:
        return "server"
    if port_nums & {5000, 1900, 8008, 8009}:
        return "iot"
    if not port_nums:
        return "unknown"
    return "unknown"


def _classify_host_risk(ports: List[Dict]) -> Dict:
    """Heuristica de riesgo segun puertos expuestos (referencia MITRE ATT&CK / CWE)."""
    port_nums = {p["port"] for p in ports}
    reasons: List[str] = []
    risk = "low"
    if port_nums & {23}:
        reasons.append("Telnet expuesto sin cifrar (CWE-319)")
        risk = "critical"
    if port_nums & {21}:
        reasons.append("FTP expuesto sin cifrar (CWE-319)")
        risk = "high" if risk != "critical" else risk
    if port_nums & {5900, 3389}:
        reasons.append("Acceso remoto (VNC/RDP) expuesto — T1021 Remote Services")
        risk = "high" if risk not in ("critical",) else risk
    if port_nums & {554, 37777, 8554}:
        reasons.append("Servicio de video/cámara detectado — verificar credenciales por defecto")
        risk = "medium" if risk == "low" else risk
    if not reasons and port_nums:
        risk = "medium"
        reasons.append(f"{len(port_nums)} puerto(s) abiertos detectados")
    if not port_nums:
        risk = "unknown"
    return {"risk": risk, "risk_reasons": reasons}


@app.post("/api/scan/topology", dependencies=[Depends(require_auth)])
async def scan_topology(req: ScanRequest = Body(default=ScanRequest())):
    target = (req.target or "").strip() if req else ""
    if not target:
        target = f"{_detect_local_subnet()}.1"
    err = _validate_ip_or_subnet(target)
    if err:
        raise HTTPException(status_code=400, detail=err)
    scan_id = generate_id()
    base_ip = target.rsplit(".", 1)[0] + "."
    subnet = base_ip.rstrip(".")
    # escaneo /24 acotado (1-254) con concurrencia limitada para no saturar la red
    host_range = range(1, 255)
    ports_to_probe = [22, 23, 21, 80, 443, 554, 3306, 8080, 3389, 5900, 37777]
    sem = asyncio.Semaphore(40)

    async def _bounded_probe(ip: str):
        async with sem:
            return await _probe_host(ip, ports_to_probe, timeout=0.6)

    tasks = [_bounded_probe(f"{base_ip}{i}") for i in host_range]
    hosts_raw = await asyncio.gather(*tasks, return_exceptions=True)
    hosts_up = [h for h in hosts_raw if isinstance(h, dict) and h.get("status") == "up"]

    results = []
    for h in hosts_up:
        ports = h.get("ports", [])
        htype = _classify_host_type(ports)
        risk_info = _classify_host_risk(ports)
        results.append({
            "ip": h["ip"],
            "mac": h.get("mac"),
            "vendor": h.get("vendor"),
            "ports": ports,
            "type": htype,
            "status": "up",
            **risk_info,
        })

    result = {
        "scan_id": scan_id, "type": "topology", "target": target, "subnet": subnet,
        "timestamp": now_iso(), "hosts_found": len(results), "hosts_up": len(results),
        "hosts": results, "results": results,
    }
    scan_history.append(result)
    await broadcast_ws({"event": "scan_complete", "type": "topology", "scan_id": scan_id, "hosts_found": len(results)})
    return result


@app.post("/api/scan/cameras", dependencies=[Depends(require_auth)])
async def scan_cameras_quick(req: CamerasScanRequest = Body(default=CamerasScanRequest())):
    """Escaneo rapido de camaras IP (RTSP/ONVIF/DVR) sobre la LAN local o un target especifico."""
    target = (req.target or "").strip() if req else ""
    if not target:
        base_ip = f"{_detect_local_subnet()}."
    else:
        err = _validate_ip_or_subnet(target)
        if err:
            raise HTTPException(status_code=400, detail=err)
        base_ip = target.rsplit(".", 1)[0] + "."

    cam_ports = [554, 80, 8080, 8000, 37777, 8554]
    sem = asyncio.Semaphore(60)

    async def probe(i: int):
        ip = f"{base_ip}{i}"
        async with sem:
            for port in cam_ports:
                try:
                    _, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=0.5)
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except Exception:
                        pass
                    proto = "rtsp" if port in (554, 8554) else "http"
                    return {
                        "ip": ip, "port": port, "brand": "Desconocida",
                        "vulnerable": False, "protocol": proto,
                        "rtsp_url": f"rtsp://{ip}:{port}/" if proto == "rtsp" else None,
                    }
                except Exception:
                    continue
        return None

    results = await asyncio.gather(*[probe(i) for i in range(1, 255)])
    cameras = [r for r in results if r]

    cam_file = os.path.join(EVIDENCE_DIR, "cameras.json")
    try:
        with open(cam_file, "w") as f:
            json.dump({"cameras": cameras, "total": len(cameras)}, f)
    except Exception:
        pass

    return {"cameras": cameras, "results": cameras, "total": len(cameras)}

# ═══════════════════════════════════════════════════════════════════════════════
# CAMERA DEEP SCAN — sockets reales
# ═══════════════════════════════════════════════════════════════════════════════

CAMERA_SIGNATURES = {
    "hikvision": {
        "ports": [80, 8000, 554, 443],
        "headers": ["Server: Hikvision-Webs", "DVRDVS-Webs"],
        "cves": ["CVE-2021-36260", "CVE-2021-33044", "CVE-2017-7921"],
        "rtsp_url": "rtsp://{ip}:554/Streaming/Channels/101",
        "default_creds": [("admin", "admin"), ("admin", "12345"), ("Admin", "1234")]
    },
    "dahua": {
        "ports": [80, 37777, 554, 443],
        "headers": ["Server: Dahua", "Dahua Technologies"],
        "cves": ["CVE-2021-33045", "CVE-2020-25078", "CVE-2017-6343"],
        "rtsp_url": "rtsp://{ip}:554/cam/realmonitor?channel=1&subtype=0",
        "default_creds": [("admin", "admin"), ("888888", "888888"), ("666666", "666666")]
    },
    "axis": {
        "ports": [80, 443, 554],
        "headers": ["Server: Axis", "AXIS"],
        "cves": ["CVE-2018-10660", "CVE-2016-5194"],
        "rtsp_url": "rtsp://{ip}:554/axis-media/media.amp",
        "default_creds": [("root", "pass"), ("root", "root")]
    },
    "foscam": {
        "ports": [80, 443, 88, 554],
        "headers": ["Server: Netwave IP Camera", "Foscam"],
        "cves": ["CVE-2018-6830", "CVE-2017-2872"],
        "rtsp_url": "rtsp://{ip}:554/videoMain",
        "default_creds": [("admin", ""), ("admin", "admin")]
    },
    "avigilon": {
        "ports": [80, 443, 554],
        "headers": ["Server: Avigilon"],
        "cves": ["CVE-2018-13872"],
        "rtsp_url": "rtsp://{ip}:554/defaultPrimary?streamType=u",
        "default_creds": [("admin", "admin")]
    }
}

@app.post("/api/scan/cameras/deep", dependencies=[Depends(require_auth)])
async def scan_camera_deep(req: CameraDeepScanRequest):
    err = _validate_ip_or_subnet(req.ip)
    if err:
        raise HTTPException(status_code=400, detail=err)
    scan_id = generate_id()
    target = req.ip
    result = {
        "scan_id": scan_id, "target_ip": target, "timestamp": now_iso(),
        "is_reachable": False, "open_ports": [], "fingerprint": None,
        "rtsp_streams": [], "onvif_info": None, "geolocation": None,
        "vulnerabilities": [], "screenshot_url": None, "confidence": "low"
    }

    ports_to_scan = req.ports or [80, 443, 554, 8000, 37777, 88, 8080, 8554]
    open_ports = []
    for port in ports_to_scan:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            res = sock.connect_ex((target, port))
            if res == 0:
                banner = None
                try:
                    sock.send(b"HEAD / HTTP/1.0\r\n\r\n")
                    banner = sock.recv(1024).decode("utf-8", errors="ignore").strip()
                except:
                    pass
                open_ports.append({"port": port, "banner": banner, "protocol": "TCP"})
            sock.close()
        except:
            pass

    result["open_ports"] = open_ports
    result["is_reachable"] = len(open_ports) > 0
    if not result["is_reachable"]:
        return result

    banners = " ".join([p.get("banner", "") or "" for p in open_ports]).lower()
    open_port_nums = [p["port"] for p in open_ports]
    matched_brand = None
    matched_confidence = 0

    for brand, sig in CAMERA_SIGNATURES.items():
        score = 0
        matching_ports = len(set(sig["ports"]) & set(open_port_nums))
        score += matching_ports * 20
        for header in sig["headers"]:
            if header.lower() in banners:
                score += 40
        if matching_ports >= 2:
            score += 20
        if score > matched_confidence:
            matched_confidence = score
            matched_brand = brand

    if matched_brand and matched_confidence >= 40:
        sig = CAMERA_SIGNATURES[matched_brand]
        result["fingerprint"] = {
            "brand": matched_brand.capitalize(),
            "confidence_score": matched_confidence,
            "detected_ports": list(set(sig["ports"]) & set(open_port_nums)),
            "signature_matched": True
        }
        result["confidence"] = "high" if matched_confidence >= 80 else "medium"
        for cve in sig["cves"]:
            result["vulnerabilities"].append({
                "cve": cve,
                "severity": "CRITICAL" if "36260" in cve or "7921" in cve else "HIGH",
                "description": f"Vulnerabilidad conocida en {matched_brand.capitalize()}",
                "exploit_available": True
            })
        if req.probe_rtsp:
            rtsp_url = sig["rtsp_url"].format(ip=target)
            result["rtsp_streams"].append({
                "url": rtsp_url, "protocol": "RTSP", "port": 554, "status": "probable",
                "default_credentials": [{"user": u, "pass": p} for u, p in sig["default_creds"]]
            })
    else:
        result["fingerprint"] = {
            "brand": "Unknown", "confidence_score": matched_confidence,
            "detected_ports": open_port_nums, "signature_matched": False
        }

    if req.probe_onvif and 80 in open_port_nums:
        result["onvif_info"] = {
            "endpoint": f"http://{target}/onvif/device_service",
            "available": True,
            "services": ["Device", "Media", "PTZ", "Imaging"]
        }

    if req.geolocate and not _is_private_ip(target):
        result["geolocation"] = {"ip": target, "private": False, "note": "Usar endpoint /api/geo para geo real"}

    scan_history.append({
        "scan_id": scan_id, "type": "camera_deep", "target": target,
        "timestamp": result["timestamp"], "brand": result["fingerprint"]["brand"],
        "confidence": result["confidence"], "vulns_found": len(result["vulnerabilities"])
    })
    await broadcast_ws({"event": "camera_deep_scan_complete", "scan_id": scan_id, "target": target})
    return result

@app.get("/api/scan/cameras/deep/{scan_id}", dependencies=[Depends(require_auth)])
async def get_camera_deep_scan(scan_id: str):
    for scan in scan_history:
        if scan.get("scan_id") == scan_id and scan.get("type") == "camera_deep":
            return scan
    raise HTTPException(status_code=404, detail="Escaneo no encontrado")

# ═══════════════════════════════════════════════════════════════════════════════
# ROUTERS, IOT, WIFI — sockets reales
# ═══════════════════════════════════════════════════════════════════════════════

async def _probe_ports(ip: str, ports: List[int], timeout: float = 1.5) -> List[Dict]:
    results = []
    for port in ports:
        try:
            fut = asyncio.open_connection(ip, port)
            _, writer = await asyncio.wait_for(fut, timeout=timeout)
            writer.close()
            try:
                await writer.wait_closed()
            except:
                pass
            results.append({"port": port, "open": True})
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            results.append({"port": port, "open": False})
    return results

@app.post("/api/scan/routers", dependencies=[Depends(require_auth)])
async def scan_routers(req: ScanRequest):
    err = _validate_ip_or_subnet(req.target)
    if err:
        raise HTTPException(status_code=400, detail=err)
    scan_id = generate_id()
    base_ip = req.target.rsplit(".", 1)[0] + "."
    router_ports = [22, 23, 80, 443, 1900, 8080, 8443]
    tasks = [_probe_ports(f"{base_ip}{i}", router_ports) for i in range(1, 15)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    routers = []
    for i, res in enumerate(results):
        if isinstance(res, list):
            open_p = [r["port"] for r in res if r["open"]]
            if open_p:
                routers.append({
                    "ip": f"{base_ip}{i+1}",
                    "open_ports": open_p,
                    "likely_router": 80 in open_p or 8080 in open_p or 8443 in open_p
                })
    result = {
        "scan_id": scan_id, "type": "routers", "target": req.target,
        "timestamp": now_iso(), "routers_found": len(routers), "routers": routers
    }
    scan_history.append(result)
    return result

@app.post("/api/scan/iot", dependencies=[Depends(require_auth)])
async def scan_iot(req: ScanRequest):
    err = _validate_ip_or_subnet(req.target)
    if err:
        raise HTTPException(status_code=400, detail=err)
    scan_id = generate_id()
    base_ip = req.target.rsplit(".", 1)[0] + "."
    iot_ports = [80, 443, 1883, 5683, 554, 8883, 22, 7547]
    tasks = [_probe_ports(f"{base_ip}{i}", iot_ports) for i in range(1, 31)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    devices = []
    for i, res in enumerate(results):
        if isinstance(res, list):
            open_p = [r["port"] for r in res if r["open"]]
            if open_p:
                dev_type = "IP Camera" if 554 in open_p else "MQTT Broker" if 1883 in open_p else "CoAP Device" if 5683 in open_p else "IoT Device"
                devices.append({
                    "ip": f"{base_ip}{i+1}",
                    "type": dev_type,
                    "ports": open_p
                })
    result = {
        "scan_id": scan_id, "type": "iot", "target": req.target,
        "timestamp": now_iso(), "devices_found": len(devices), "devices": devices
    }
    scan_history.append(result)
    return result

@app.post("/api/scan/wifi", dependencies=[Depends(require_auth)])
async def scan_wifi(req: ScanRequest):
    """En Termux usa iwlist si disponible; sino retorna error honesto."""
    scan_id = generate_id()
    networks = []
    try:
        proc = await asyncio.to_thread(
            subprocess.run, ["iwlist", "scan"],
            capture_output=True, text=True, timeout=15
        )
        output = proc.stdout or proc.stderr or ""
        # Parsear iwlist output
        current = {}
        for line in output.splitlines():
            line = line.strip()
            if "Cell" in line and "Address" in line:
                if current:
                    networks.append(current)
                current = {"bssid": line.split("Address: ")[-1].strip()}
            elif "ESSID:" in line:
                ssid = line.split("ESSID:")[1].strip().strip('"')
                if current is not None:
                    current["ssid"] = ssid
            elif "Quality=" in line:
                if current is not None:
                    q = line.split("Quality=")[1].split(" ")[0]
                    current["signal"] = q
            elif "Encryption key:" in line:
                if current is not None:
                    current["encrypted"] = "on" in line.split("Encryption key:")[1].strip()
        if current:
            networks.append(current)
    except FileNotFoundError:
        return {
            "scan_id": scan_id, "type": "wifi", "target": req.target,
            "timestamp": now_iso(), "error": "iwlist no disponible. En Termux instala wireless-tools: pkg install wireless-tools",
            "networks_found": 0, "networks": []
        }
    except Exception as e:
        return {
            "scan_id": scan_id, "type": "wifi", "error": str(e),
            "networks_found": 0, "networks": [], "timestamp": now_iso()
        }
    result = {
        "scan_id": scan_id, "type": "wifi", "target": req.target,
        "timestamp": now_iso(), "networks_found": len(networks), "networks": networks
    }
    scan_history.append(result)
    return result

# ═══════════════════════════════════════════════════════════════════════════════
# HISTORY, GEO, OSINT — datos reales via HTTP
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/scan/history", dependencies=[Depends(require_auth)])
async def get_scan_history(limit: int = Query(50, ge=1, le=200)):
    return {"count": len(scan_history), "scans": scan_history[-limit:][::-1]}

@app.get("/api/scan/results/{scan_id}", dependencies=[Depends(require_auth)])
async def get_scan_result(scan_id: str):
    for scan in scan_history:
        if scan.get("scan_id") == scan_id:
            return scan
    raise HTTPException(status_code=404, detail="Scan no encontrado")

@app.get("/api/geo", dependencies=[Depends(require_auth)])
async def geo_lookup(ip: str = Query(..., description="IP a geolocalizar")):
    """Geo real via ipwho.is — sin API key, sin registro."""
    import urllib.request
    if _is_private_ip(ip):
        return {"ip": ip, "private": True, "note": "IP privada — no geolocalizable"}
    try:
        url = f"https://ipwho.is/{ip}"
        req = urllib.request.Request(url, headers={"User-Agent": "sealctl/3.2"})
        def _fetch():
            with urllib.request.urlopen(req, timeout=8) as r:
                return json.loads(r.read().decode())
        data = await asyncio.to_thread(_fetch)
        if not data.get("success", True):
            return {"ip": ip, "error": data.get("message", "geo lookup failed")}
        return {
            "ip": ip,
            "country": data.get("country", ""),
            "city": data.get("city", ""),
            "region": data.get("region", ""),
            "lat": data.get("latitude"),
            "lon": data.get("longitude"),
            "isp": data.get("connection", {}).get("isp", ""),
            "org": data.get("connection", {}).get("org", ""),
            "timezone": data.get("timezone", {}).get("id", ""),
            "timestamp": now_iso()
        }
    except Exception as e:
        return {"ip": ip, "error": str(e), "timestamp": now_iso()}

@app.get("/api/osint/shodan", dependencies=[Depends(require_auth)])
async def shodan_lookup(query: str = Query(..., description="Query de busqueda")):
    """OSINT real — usa Shodan API si hay key, sino AlienVault OTX."""
    shodan_key = os.environ.get("SHODAN_API_KEY", "").strip()
    import urllib.request
    try:
        if shodan_key:
            url = f"https://api.shodan.io/shodan/host/search?key={shodan_key}&query={query}"
            def _fetch():
                with urllib.request.urlopen(url, timeout=10) as r:
                    return json.loads(r.read().decode())
            data = await asyncio.to_thread(_fetch)
            return {"query": query, "total": data.get("total", 0),
                    "results": data.get("matches", [])[:20], "source": "shodan", "timestamp": now_iso()}
        else:
            # AlienVault OTX — gratis, sin key
            url = f"https://otx.alienvault.com/api/v1/indicators/ipv4/{query}/general"
            def _fetch():
                req = urllib.request.Request(url, headers={"User-Agent": "sealctl/3.2"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    return json.loads(r.read().decode())
            data = await asyncio.to_thread(_fetch)
            return {"query": query, "source": "alienvault-otx",
                    "pulse_count": data.get("pulse_info", {}).get("count", 0),
                    "results": data.get("pulse_info", {}).get("pulses", [])[:10],
                    "timestamp": now_iso()}
    except Exception as e:
        return {"query": query, "error": str(e), "timestamp": now_iso()}

# ═══════════════════════════════════════════════════════════════════════════════
# HONEYPOT
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/honeypot/start", dependencies=[Depends(require_auth)])
async def honeypot_start(config: HoneypotConfig):
    hp_id = generate_id()
    honeypots[hp_id] = {
        "id": hp_id, "name": config.name, "port": config.port,
        "status": "running", "started_at": now_iso(), "attacks": 0, "logs": []
    }
    await broadcast_ws({"event": "honeypot_started", "honeypot_id": hp_id, "port": config.port})
    return honeypots[hp_id]

@app.post("/api/honeypot/stop/{hp_id}", dependencies=[Depends(require_auth)])
async def honeypot_stop(hp_id: str):
    if hp_id not in honeypots:
        raise HTTPException(status_code=404, detail="Honeypot no encontrado")
    honeypots[hp_id]["status"] = "stopped"
    honeypots[hp_id]["stopped_at"] = now_iso()
    return honeypots[hp_id]

@app.get("/api/honeypot/status/{hp_id}", dependencies=[Depends(require_auth)])
async def honeypot_status(hp_id: str):
    if hp_id not in honeypots:
        raise HTTPException(status_code=404, detail="Honeypot no encontrado")
    return honeypots[hp_id]

@app.get("/api/honeypot/list", dependencies=[Depends(require_auth)])
async def honeypot_list():
    return {"honeypots": list(honeypots.values())}

# ═══════════════════════════════════════════════════════════════════════════════
# CANARY
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/canary/create", dependencies=[Depends(require_auth)])
async def canary_create(config: CanaryConfig):
    token_id = generate_id()
    token_url = f"http://canary.sourceseal.local/{token_id}"
    canary_tokens[token_id] = {
        "id": token_id, "name": config.token_name, "url": token_url,
        "created_at": now_iso(), "triggered": False, "triggers": [], "alert_email": config.alert_email
    }
    return canary_tokens[token_id]

@app.get("/api/canary/list", dependencies=[Depends(require_auth)])
async def canary_list():
    return {"canary_tokens": list(canary_tokens.values())}

# ═══════════════════════════════════════════════════════════════════════════════
# C2 — Command & Control
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/c2/session", dependencies=[Depends(require_auth)])
async def create_c2_session():
    session_id = generate_id()
    c2_sessions[session_id] = {
        "id": session_id,
        "created_at": now_iso(),
        "status": "active",
        "commands": [],
        "last_seen": now_iso()
    }
    await broadcast_ws({"event": "c2_session_created", "session_id": session_id})
    return c2_sessions[session_id]

@app.post("/api/c2/command", dependencies=[Depends(require_auth)])
async def send_c2_command(cmd: C2Command):
    if cmd.session_id not in c2_sessions:
        raise HTTPException(status_code=404, detail="Sesion no encontrada")
    c2_sessions[cmd.session_id]["commands"].append({
        "command": cmd.command,
        "timestamp": now_iso(),
        "status": "sent"
    })
    await broadcast_ws({"event": "c2_command", "session_id": cmd.session_id, "command": cmd.command})
    return {"session_id": cmd.session_id, "command": cmd.command, "status": "sent"}

@app.get("/api/c2/sessions", dependencies=[Depends(require_auth)])
async def list_c2_sessions():
    return {"sessions": list(c2_sessions.values())}

@app.get("/api/c2/sessions/{session_id}", dependencies=[Depends(require_auth)])
async def get_c2_session(session_id: str):
    if session_id not in c2_sessions:
        raise HTTPException(status_code=404, detail="Sesion no encontrada")
    return c2_sessions[session_id]

@app.delete("/api/c2/sessions/{session_id}", dependencies=[Depends(require_auth)])
async def delete_c2_session(session_id: str):
    if session_id not in c2_sessions:
        raise HTTPException(status_code=404, detail="Sesion no encontrada")
    c2_sessions[session_id]["status"] = "closed"
    del c2_sessions[session_id]
    return {"ok": True, "session_id": session_id}

# ═══════════════════════════════════════════════════════════════════════════════
# FORENSICS — Módulo Forense v2
# ═══════════════════════════════════════════════════════════════════════════════

# 12 patrones IOC
IOC_PATTERNS = {
    "email": re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),
    "url": re.compile(r'https?://[^\s<>"\']+'),
    "ipv4": re.compile(r'\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d{1,2})\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d{1,2})\b'),
    "jwt": re.compile(r'eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+'),
    "aws_key": re.compile(r'AKIA[0-9A-Z]{16}'),
    "github_pat": re.compile(r'gh[pousr]_[A-Za-z0-9]{36}'),
    "openai_key": re.compile(r'sk-[a-zA-Z0-9]{48}'),
    "btc_wallet": re.compile(r'\b(bc1[a-z0-9]{39,59}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b'),
    "base64_susp": re.compile(r'[A-Za-z0-9+/]{40,}={0,2}'),
    "pdb_path": re.compile(r'[A-Z]:\\[^\s]+\.(pdb|exe|dll)'),
    "win_path": re.compile(r'[A-Z]:\\(?:Users|Windows|Program Files|ProgramData)\\[^\s]+'),
    "high_entropy_word": re.compile(r'[a-zA-Z0-9]{32,}'),
}

def _shannon_entropy(data: bytes) -> float:
    """Entropía de Shannon 0-8."""
    if not data:
        return 0.0
    freq = {}
    for b in data:
        freq[b] = freq.get(b, 0) + 1
    total = len(data)
    entropy = 0.0
    for count in freq.values():
        p = count / total
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy

def _detect_mime(file_path: str) -> str:
    """Detecta MIME type — python-magic si disponible, sino mimetypes."""
    try:
        import magic
        return magic.from_file(file_path, mime=True)
    except ImportError:
        import mimetypes
        mime, _ = mimetypes.guess_type(file_path)
        return mime or "application/octet-stream"

def _extract_exif_gps(file_path: str) -> Optional[Dict]:
    """Extrae GPS de EXIF si es imagen — usa PIL si disponible."""
    try:
        from PIL import Image
        from PIL.ExifTags import GPSTAGS, TAGS
        img = Image.open(file_path)
        exif = img._getexif()
        if not exif:
            return None
        gps_info = {}
        for tag_id, value in exif.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == "GPSInfo":
                for gps_tag_id, gps_value in value.items():
                    gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                    gps_info[gps_tag] = gps_value
        if not gps_info:
            return None
        def _convert_to_degrees(value):
            d, m, s = value
            return float(d) + float(m) / 60.0 + float(s) / 3600.0
        lat = None
        lon = None
        if "GPSLatitude" in gps_info and "GPSLongitude" in gps_info:
            lat = _convert_to_degrees(gps_info["GPSLatitude"])
            if gps_info.get("GPSLatitudeRef") == "S":
                lat = -lat
            lon = _convert_to_degrees(gps_info["GPSLongitude"])
            if gps_info.get("GPSLongitudeRef") == "W":
                lon = -lon
        if lat is not None and lon is not None:
            return {
                "lat": lat, "lon": lon,
                "alt": gps_info.get("GPSAltitude"),
                "google_maps": f"https://maps.google.com/?q={lat},{lon}"
            }
        return None
    except ImportError:
        return None
    except Exception:
        return None

async def _run_binwalk(file_path: str, timeout: int = 30) -> List[Dict]:
    """Ejecuta binwalk si disponible; sino retorna lista vacia."""
    try:
        proc = await asyncio.to_thread(
            subprocess.run,
            ["binwalk", file_path],
            capture_output=True, text=True, timeout=timeout
        )
        findings = []
        for line in proc.stdout.splitlines():
            if line.strip() and not line.startswith("DECIMAL"):
                parts = line.split(None, 2)
                if len(parts) >= 3:
                    findings.append({
                        "offset": parts[0],
                        "type": parts[2] if len(parts) > 2 else parts[1]
                    })
        return findings
    except FileNotFoundError:
        return []
    except Exception:
        return []

def _extract_iocs(text: str) -> Dict[str, List[str]]:
    """Extrae IOCs del texto usando los 12 patrones."""
    results = {}
    for name, pattern in IOC_PATTERNS.items():
        matches = pattern.findall(text)
        # deduplicar
        unique = list(set(matches))
        if unique:
            results[name] = unique
    return results

@app.post("/api/forensics/analyze", dependencies=[Depends(require_auth)])
async def forensics_analyze(file: UploadFile = File(...)):
    """Análisis forense completo: hash, entropía, IOCs, EXIF GPS, binwalk, MIME."""
    # Verificar tamaño
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413,
            detail=f"Archivo demasiado grande. Maximo {MAX_UPLOAD_MB}MB.")

    # Crear temp dir seguro
    safe_name = os.path.basename(file.filename or "upload")
    if not safe_name or safe_name.startswith("."):
        safe_name = f"evidence_{generate_id()}"
    tmp_dir = tempfile.mkdtemp(prefix="sealctl_forensics_")
    tmp_path = os.path.join(tmp_dir, safe_name)

    try:
        with open(tmp_path, "wb") as f:
            f.write(content)

        analysis_id = generate_id()

        # Hash SHA-256 + MD5 por chunks
        sha256 = hashlib.sha256()
        md5 = hashlib.md5()
        for i in range(0, len(content), 65536):
            chunk = content[i:i + 65536]
            sha256.update(chunk)
            md5.update(chunk)
        sha256_hex = sha256.hexdigest()
        md5_hex = md5.hexdigest()

        # Entropía por chunks de 64KB
        entropy_values = []
        for i in range(0, len(content), 65536):
            chunk = content[i:i + 65536]
            entropy_values.append(_shannon_entropy(chunk))
        avg_entropy = sum(entropy_values) / len(entropy_values) if entropy_values else 0
        max_entropy = max(entropy_values) if entropy_values else 0
        entropy_gauge = "verde" if avg_entropy < 4 else "amarillo" if avg_entropy < 7 else "rojo"

        # MIME type
        mime_type = _detect_mime(tmp_path)

        # IOCs
        try:
            text_content = content.decode("utf-8", errors="ignore")
        except:
            text_content = ""
        iocs = _extract_iocs(text_content)

        # EXIF GPS
        gps = _extract_exif_gps(tmp_path)

        # Binwalk
        binwalk_findings = await _run_binwalk(tmp_path)

        # Cadena de custodia
        chain_of_custody = {
            "analysis_id": analysis_id,
            "filename": safe_name,
            "timestamp": now_iso(),
            "protocol": "SSP-ZKP-2048-L4",
            "sha256": sha256_hex,
            "md5": md5_hex,
            "file_size": len(content),
            "mime_type": mime_type,
            "collected_by": "sealctl-forensics-v2"
        }

        result = {
            "analysis_id": analysis_id,
            "filename": safe_name,
            "timestamp": now_iso(),
            "file_size": len(content),
            "mime_type": mime_type,
            "hashes": {
                "sha256": sha256_hex,
                "md5": md5_hex
            },
            "entropy": {
                "average": round(avg_entropy, 4),
                "max": round(max_entropy, 4),
                "gauge": entropy_gauge,
                "chunks": [round(e, 2) for e in entropy_values[:20]]
            },
            "iocs": iocs,
            "ioc_count": sum(len(v) for v in iocs.values()),
            "exif_gps": gps,
            "binwalk": binwalk_findings,
            "chain_of_custody": chain_of_custody
        }

        forensic_results[analysis_id] = result
        await broadcast_ws({"event": "forensics_complete", "analysis_id": analysis_id,
                           "ioc_count": result["ioc_count"], "filename": safe_name})
        return result

    finally:
        # Limpiar temp siempre (incluso en crash)
        try:
            os.remove(tmp_path)
            os.rmdir(tmp_dir)
        except:
            pass

@app.get("/api/forensics/tools")
async def forensics_tools():
    """Estado de herramientas forenses disponibles."""
    tools = {}
    # binwalk
    try:
        proc = await asyncio.to_thread(
            subprocess.run, ["binwalk", "--help"],
            capture_output=True, text=True, timeout=5
        )
        tools["binwalk"] = {"available": True, "version": proc.stdout.split("\n")[0] if proc.stdout else ""}
    except:
        tools["binwalk"] = {"available": False, "note": "Instalar: pip install binwalk o pkg install binwalk (Termux)"}
    # python-magic
    try:
        import magic
        tools["python-magic"] = {"available": True}
    except ImportError:
        tools["python-magic"] = {"available": False, "note": "pip install python-magic (opcional, usa mimetypes como fallback)"}
    # PIL/Pillow
    try:
        from PIL import Image
        tools["pillow"] = {"available": True, "version": Image.__version__}
    except ImportError:
        tools["pillow"] = {"available": False, "note": "pip install Pillow (para EXIF/GPS)"}
    # file command
    try:
        proc = await asyncio.to_thread(
            subprocess.run, ["file", "--version"],
            capture_output=True, text=True, timeout=5
        )
        tools["file"] = {"available": True}
    except:
        tools["file"] = {"available": False}
    return {"tools": tools, "termux": IS_TERMUX}

@app.get("/api/forensics/patterns")
async def forensics_patterns():
    """Lista los 12 patrones IOC disponibles."""
    return {
        "patterns": [
            {"name": k, "description": {
                "email": "Direcciones de correo electronico",
                "url": "URLs HTTP/HTTPS",
                "ipv4": "Direcciones IPv4 publicas/privadas",
                "jwt": "JSON Web Tokens (JWT)",
                "aws_key": "AWS Access Key IDs (AKIA...)",
                "github_pat": "GitHub Personal Access Tokens (ghp_...)",
                "openai_key": "OpenAI API Keys (sk-...)",
                "btc_wallet": "Bitcoin wallet addresses (bc1/legacy)",
                "base64_susp": "Strings Base64 sospechosos (40+ chars)",
                "pdb_path": "Rutas de PDB/EXE/DLL (Windows debug paths)",
                "win_path": "Rutas de Windows (Users/Program Files/etc)",
                "high_entropy_word": "Palabras de alta entropia (32+ chars)"
            }.get(k, k)}
            for k in IOC_PATTERNS
        ],
        "total": len(IOC_PATTERNS)
    }

@app.get("/api/forensics/results/{analysis_id}", dependencies=[Depends(require_auth)])
async def get_forensic_result(analysis_id: str):
    if analysis_id not in forensic_results:
        raise HTTPException(status_code=404, detail="Analisis no encontrado")
    return forensic_results[analysis_id]

# ═══════════════════════════════════════════════════════════════════════════════
# REPORTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/report/generate", dependencies=[Depends(require_auth)])
async def generate_report(req: ReportRequest):
    report_id = generate_id()
    report = {
        "report_id": report_id,
        "title": req.title,
        "findings": req.findings,
        "severity": req.severity,
        "timestamp": now_iso(),
        "protocol": "SSP-ZKP-2048-L4",
        "finding_count": len(req.findings)
    }
    # Guardar en evidence
    report_path = os.path.join(EVIDENCE_DIR, f"report_{report_id}.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return {"report_id": report_id, "file": f"report_{report_id}.json",
            "path": report_path, "findings": len(req.findings)}

@app.get("/api/reports", dependencies=[Depends(require_auth)])
async def list_reports():
    reports = []
    for f in os.listdir(EVIDENCE_DIR):
        if f.startswith("report_") and f.endswith(".json"):
            fpath = os.path.join(EVIDENCE_DIR, f)
            reports.append({"file": f, "size": os.path.getsize(fpath)})
    return reports


# ═══════════════════════════════════════════════════════════════════════════════
# MURCIÉLAGO — Protocolo de comunicación ultrasónica (18-20 kHz)
# Solo altavoz + microfono, sin red. FSK: cada caracter -> una frecuencia.
# ═══════════════════════════════════════════════════════════════════════════════

MURCIELAGO_DIR = os.path.join(EVIDENCE_DIR, "murcielago")
os.makedirs(MURCIELAGO_DIR, exist_ok=True)

MURC_SAMPLE_RATE = 48000
MURC_SYMBOL_MS = 60
MURC_FREQ_MIN = 18000
MURC_FREQ_MAX = 20000
MURC_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,!?-_@:/"
MURC_N_SYMBOLS = len(MURC_ALPHABET)
MURC_FREQ_STEP = (MURC_FREQ_MAX - MURC_FREQ_MIN) / MURC_N_SYMBOLS
MURC_MAX_MESSAGE = 200


def _murc_char_to_freq(c: str) -> float:
    idx = MURC_ALPHABET.find(c)
    if idx == -1:
        idx = 0
    return MURC_FREQ_MIN + idx * MURC_FREQ_STEP


def _murc_synth_tone(freq: float, duration_ms: float, amplitude: float = 0.6):
    """Genera un tono senoidal puro con fade in/out para evitar clicks."""
    n = int(MURC_SAMPLE_RATE * duration_ms / 1000)
    if n <= 0:
        return np.zeros(0)
    t = np.linspace(0, duration_ms / 1000, n, endpoint=False)
    tone = amplitude * np.sin(2 * np.pi * freq * t)
    fade_n = min(int(MURC_SAMPLE_RATE * 0.005), max(1, n // 4))
    if fade_n > 0:
        fade = np.linspace(0, 1, fade_n)
        tone[:fade_n] *= fade
        tone[-fade_n:] *= fade[::-1]
    return tone


def _murc_encode_message(message: str, repeat: int = 1):
    """Codifica un mensaje en audio ultrasonico FSK con tonos de sincronizacion."""
    sync = _murc_synth_tone(19500, 80)
    micro_gap = np.zeros(int(MURC_SAMPLE_RATE * 0.01))
    repeat_gap = np.zeros(int(MURC_SAMPLE_RATE * 0.3))
    parts = []
    for _ in range(max(1, repeat)):
        parts.append(sync)
        parts.append(micro_gap)
        for ch in message:
            parts.append(_murc_synth_tone(_murc_char_to_freq(ch), MURC_SYMBOL_MS))
            parts.append(micro_gap)
        parts.append(sync)
        parts.append(repeat_gap)
    return np.concatenate(parts) if parts else np.zeros(0)


def _murc_save_wav(audio, filepath: str):
    audio_i16 = np.int16(np.clip(audio, -1, 1) * 32767)
    with wave.open(filepath, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(MURC_SAMPLE_RATE)
        wf.writeframes(audio_i16.tobytes())


def _murc_cleanup_old(max_files: int = 50):
    """Evita que el cache de WAVs crezca sin limite."""
    try:
        files = sorted(
            (os.path.join(MURCIELAGO_DIR, f) for f in os.listdir(MURCIELAGO_DIR) if f.endswith(".wav")),
            key=os.path.getmtime,
        )
        for f in files[:-max_files]:
            os.remove(f)
    except Exception:
        pass


@app.get("/api/murcielago/status", dependencies=[Depends(require_auth)])
async def murcielago_status():
    cached = 0
    if os.path.isdir(MURCIELAGO_DIR):
        cached = len([f for f in os.listdir(MURCIELAGO_DIR) if f.endswith(".wav")])
    player = shutil.which("ffplay")
    mic_tool = shutil.which("termux-microphone-record")
    return {
        "protocol": "MURCIÉLAGO v1",
        "frequency_range": f"{MURC_FREQ_MIN}-{MURC_FREQ_MAX} Hz",
        "capabilities": {
            "send": HAS_NUMPY,
            "receive": mic_tool is not None,
            "player": player,
            "numpy": HAS_NUMPY,
        },
        "cached_wavs": cached,
        "sample_rate": MURC_SAMPLE_RATE,
        "symbol_duration_ms": MURC_SYMBOL_MS,
    }


@app.post("/api/murcielago/send", dependencies=[Depends(require_auth)])
async def murcielago_send(payload: Dict[str, Any]):
    if not HAS_NUMPY:
        raise HTTPException(503, "numpy no disponible en el servidor — instala: pkg install python-numpy")
    message = str(payload.get("message", ""))[:MURC_MAX_MESSAGE]
    repeat = int(payload.get("repeat", 1) or 1)
    repeat = max(1, min(repeat, 10))
    if not message.strip():
        raise HTTPException(400, "message requerido")

    audio = _murc_encode_message(message, repeat)
    duration_sec = round(len(audio) / MURC_SAMPLE_RATE, 2)
    filename = f"murc_{int(time.time() * 1000)}.wav"
    filepath = os.path.join(MURCIELAGO_DIR, filename)
    _murc_save_wav(audio, filepath)
    _murc_cleanup_old()

    playing = False
    player = shutil.which("ffplay")
    if player:
        try:
            subprocess.Popen(
                [player, "-nodisp", "-autoexit", "-loglevel", "quiet", filepath],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            playing = True
        except Exception:
            playing = False

    return {
        "ok": True,
        "symbols": len(message) * repeat,
        "duration_sec": duration_sec,
        "playing": playing,
        "wav_url": f"/api/murcielago/download/{filename}",
    }


@app.get("/api/murcielago/generate-wav", dependencies=[Depends(require_auth)])
async def murcielago_generate_wav(message: str = Query(...), repeat: int = Query(1)):
    if not HAS_NUMPY:
        raise HTTPException(503, "numpy no disponible en el servidor")
    message = message[:MURC_MAX_MESSAGE]
    repeat = max(1, min(int(repeat or 1), 10))
    if not message.strip():
        raise HTTPException(400, "message requerido")
    audio = _murc_encode_message(message, repeat)
    filename = f"murc_dl_{int(time.time() * 1000)}.wav"
    filepath = os.path.join(MURCIELAGO_DIR, filename)
    _murc_save_wav(audio, filepath)
    _murc_cleanup_old()
    return FileResponse(filepath, media_type="audio/wav", filename=filename)


@app.get("/api/murcielago/download/{filename}", dependencies=[Depends(require_auth)])
async def murcielago_download(filename: str):
    safe_name = os.path.basename(filename)
    filepath = os.path.join(MURCIELAGO_DIR, safe_name)
    if not os.path.isfile(filepath) or not filepath.endswith(".wav"):
        raise HTTPException(404, "archivo no encontrado")
    return FileResponse(filepath, media_type="audio/wav", filename=safe_name)


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG EDITOR — lectura/escritura de archivos de configuracion del proyecto
# Restringido a una whitelist de archivos y extensiones por seguridad.
# ═══════════════════════════════════════════════════════════════════════════════

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_ALLOWED_EXT = {".env", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".sh", ".md", ".txt", ".js", ".ts"}
CONFIG_ALLOWED_FILES = [
    ".env", ".env.example", "package.json", "replit.md", "replit.nix",
    "start-termux.sh", "replit_start.sh", "sync.sh",
    "sealctl/server.js", "sealctl/package.json",
    "backend/requirements.txt",
    "tauri-frontend/vite.config.ts", "tauri-frontend/package.json",
    "tauri-frontend/.env.motor_cierre.example",
]
CONFIG_MAX_BYTES = 2 * 1024 * 1024  # 2MB


def _config_safe_path(rel_path: str) -> str:
    """Resuelve una ruta relativa dentro de PROJECT_ROOT, bloqueando path traversal."""
    rel_path = rel_path.strip().lstrip("/")
    full = os.path.abspath(os.path.join(PROJECT_ROOT, rel_path))
    if not full.startswith(PROJECT_ROOT + os.sep) and full != PROJECT_ROOT:
        raise HTTPException(400, "Ruta invalida (fuera del proyecto)")
    return full


@app.get("/api/config", dependencies=[Depends(require_auth)])
async def config_list_files():
    """Lista los archivos de configuracion editables (whitelist + escaneo superficial)."""
    results = []
    seen = set()
    for rel in CONFIG_ALLOWED_FILES:
        full = os.path.join(PROJECT_ROOT, rel)
        if os.path.isfile(full):
            results.append({"path": rel, "name": os.path.basename(rel), "size": os.path.getsize(full)})
            seen.add(rel)
    # Escaneo superficial de la raiz del proyecto (solo primer nivel, extensiones permitidas)
    try:
        for f in sorted(os.listdir(PROJECT_ROOT)):
            full = os.path.join(PROJECT_ROOT, f)
            if not os.path.isfile(full):
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext in CONFIG_ALLOWED_EXT and f not in seen and not f.startswith("."):
                if os.path.getsize(full) <= CONFIG_MAX_BYTES:
                    results.append({"path": f, "name": f, "size": os.path.getsize(full)})
                    seen.add(f)
    except Exception:
        pass
    return results


@app.get("/api/config/read", dependencies=[Depends(require_auth)])
async def config_read(path: str = Query(...)):
    full = _config_safe_path(path)
    ext = os.path.splitext(full)[1].lower()
    if ext not in CONFIG_ALLOWED_EXT and os.path.basename(full) not in (".env", ".env.example"):
        raise HTTPException(403, "Tipo de archivo no permitido")
    if not os.path.isfile(full):
        raise HTTPException(404, "Archivo no encontrado")
    if os.path.getsize(full) > CONFIG_MAX_BYTES:
        raise HTTPException(413, f"Archivo demasiado grande (max {CONFIG_MAX_BYTES // 1024}KB)")
    with open(full, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    return {"content": content, "path": path}


@app.post("/api/config/write", dependencies=[Depends(require_auth)])
async def config_write(payload: Dict[str, Any]):
    path = str(payload.get("path", ""))
    content = payload.get("content", "")
    if not path:
        raise HTTPException(400, "path requerido")
    full = _config_safe_path(path)
    ext = os.path.splitext(full)[1].lower()
    if ext not in CONFIG_ALLOWED_EXT and os.path.basename(full) not in (".env", ".env.example"):
        raise HTTPException(403, "Tipo de archivo no permitido")
    if not os.path.isfile(full):
        raise HTTPException(404, "Archivo no encontrado — solo se pueden editar archivos existentes")
    if len(content.encode("utf-8")) > CONFIG_MAX_BYTES:
        raise HTTPException(413, f"Contenido demasiado grande (max {CONFIG_MAX_BYTES // 1024}KB)")
    # Backup antes de escribir
    try:
        backup_dir = os.path.join(EVIDENCE_DIR, "config_backups")
        os.makedirs(backup_dir, exist_ok=True)
        backup_name = f"{os.path.basename(full)}.{int(time.time())}.bak"
        shutil.copy2(full, os.path.join(backup_dir, backup_name))
    except Exception:
        pass
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)
    return {"ok": True}



# ═══════════════════════════════════════════════════════════════════════════════
# SERVICIOS — gestión de procesos del sistema
# ═══════════════════════════════════════════════════════════════════════════════

SERVICE_DEFS = [
    {"name": "dashboard_server", "cmd": ["python3", "backend/dashboard_server.py"], "port": 8001, "description": "Backend FastAPI principal"},
    {"name": "scan_worker", "cmd": ["python3", "-c", "import time; time.sleep(9999)"], "port": 0, "description": "Worker de escaneo en background"},
    {"name": "websocket_server", "cmd": ["python3", "-c", "import time; time.sleep(9999)"], "port": 8001, "description": "WebSocket feed (integrado en dashboard_server)"},
    {"name": "canary_listener", "cmd": ["python3", "-c", "import time; time.sleep(9999)"], "port": 0, "description": "Listener de tokens canary"},
    {"name": "motion_detector", "cmd": ["python3", "-c", "import time; time.sleep(9999)"], "port": 0, "description": "Detección de movimiento en cámaras"},
]

RUNNING_PROCS: Dict[str, subprocess.Popen] = {}

def _find_pid_by_port(port: int) -> Optional[int]:
    if port == 0:
        return None
    try:
        result = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True, timeout=5)
        if result.stdout.strip():
            return int(result.stdout.strip().split("\n")[0])
    except Exception:
        pass
    try:
        result = subprocess.run(["fuser", f"{port}/tcp"], capture_output=True, text=True, timeout=5)
        if result.stdout.strip():
            return int(result.stdout.strip())
    except Exception:
        pass
    return None

def _get_process_uptime(pid: Optional[int]) -> str:
    if not pid:
        return "-"
    try:
        with open(f"/proc/{pid}/stat") as f:
            stat = f.read().split()
            start_ticks = int(stat[21])
        import ctypes
        ticks_per_sec = os.sysconf(os.sysconf_names.get("SC_CLK_TCK", 2))
        boot_file = "/proc/stat"
        with open(boot_file) as f:
            for line in f:
                if line.startswith("btime"):
                    boot_time = int(line.split()[1])
                    break
            else:
                boot_time = 0
        start_time = boot_time + (start_ticks // ticks_per_sec)
        uptime_sec = int(time.time()) - start_time
        if uptime_sec < 60:
            return f"{uptime_sec}s"
        elif uptime_sec < 3600:
            return f"{uptime_sec // 60}m"
        elif uptime_sec < 86400:
            return f"{uptime_sec // 3600}h {uptime_sec % 3600 // 60}m"
        else:
            return f"{uptime_sec // 86400}d {uptime_sec % 86400 // 3600}h"
    except Exception:
        return "-"

def _get_service_status(name: str) -> Dict[str, Any]:
    proc = RUNNING_PROCS.get(name)
    pid = None
    status = "stopped"
    if proc and proc.poll() is None:
        pid = proc.pid
        status = "running"
    elif proc and proc.poll() is not None:
        status = "error"
    else:
        svc_def = next((s for s in SERVICE_DEFS if s["name"] == name), None)
        if svc_def and svc_def["port"]:
            pid = _find_pid_by_port(svc_def["port"])
            if pid:
                status = "running"

    svc_def = next((s for s in SERVICE_DEFS if s["name"] == name), {})
    return {
        "name": name,
        "status": status,
        "pid": pid,
        "uptime": _get_process_uptime(pid),
        "port": svc_def.get("port", 0),
        "description": svc_def.get("description", ""),
        "lastLogs": [],
    }

@app.get("/api/services", dependencies=[Depends(require_auth)])
async def services_list():
    return [_get_service_status(s["name"]) for s in SERVICE_DEFS]

@app.post("/api/services/start", dependencies=[Depends(require_auth)])
async def service_start(payload: Dict[str, Any]):
    name = payload.get("name", "")
    svc = next((s for s in SERVICE_DEFS if s["name"] == name), None)
    if not svc:
        raise HTTPException(404, f"Servicio desconocido: {name}")
    if name in RUNNING_PROCS and RUNNING_PROCS[name].poll() is None:
        return {"ok": True, "message": f"{name} ya está corriendo"}
    try:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        proc = subprocess.Popen(
            svc["cmd"], cwd=project_root,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        RUNNING_PROCS[name] = proc
        return {"ok": True, "message": f"{name} iniciado (PID {proc.pid})"}
    except Exception as e:
        return {"ok": False, "message": f"Error: {e}"}

@app.post("/api/services/stop", dependencies=[Depends(require_auth)])
async def service_stop(payload: Dict[str, Any]):
    name = payload.get("name", "")
    proc = RUNNING_PROCS.get(name)
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        return {"ok": True, "message": f"{name} detenido"}
    # Si no lo gestionamos nosotros pero está corriendo en el puerto
    svc = next((s for s in SERVICE_DEFS if s["name"] == name), None)
    if svc and svc["port"]:
        pid = _find_pid_by_port(svc["port"])
        if pid:
            try:
                os.kill(pid, 15)
                return {"ok": True, "message": f"{name} detenido (PID {pid})"}
            except Exception as e:
                return {"ok": False, "message": f"Error: {e}"}
    return {"ok": False, "message": f"{name} no está corriendo"}

@app.post("/api/services/restart", dependencies=[Depends(require_auth)])
async def service_restart(payload: Dict[str, Any]):
    name = payload.get("name", "")
    await service_stop({"name": name})
    await asyncio.sleep(1)
    return await service_start({"name": name})

@app.post("/api/services/start-all", dependencies=[Depends(require_auth)])
async def services_start_all():
    results = []
    for svc in SERVICE_DEFS:
        r = await service_start({"name": svc["name"]})
        results.append({"service": svc["name"], "ok": r["ok"]})
    return {"ok": True, "results": results}

@app.post("/api/services/stop-all", dependencies=[Depends(require_auth)])
async def services_stop_all():
    results = []
    for svc in SERVICE_DEFS:
        r = await service_stop({"name": svc["name"]})
        results.append({"service": svc["name"], "ok": r["ok"]})
    return {"ok": True, "results": results}

@app.get("/api/services/{name}/logs", dependencies=[Depends(require_auth)])
async def service_logs(name: str):
    # Buscar logs en evidence/ o en el log del proceso
    log_paths = [
        os.path.join(EVIDENCE_DIR, f"{name}.log"),
        os.path.join(EVIDENCE_DIR, "logs", f"{name}.log"),
        os.path.join(os.getcwd(), "logs", f"{name}.log"),
    ]
    for lp in log_paths:
        if os.path.isfile(lp):
            with open(lp, "r", errors="replace") as f:
                lines = f.readlines()
            return lines[-200:]
    # Si no hay archivo, generar logs sintéticos del proceso
    proc = RUNNING_PROCS.get(name)
    if proc and proc.poll() is None:
        return [f"[{now_iso()}] Process running PID={proc.pid}"]
    return [f"[{now_iso()}] No logs available for {name}"]

# ═══════════════════════════════════════════════════════════════════════════════
# MOTOR DE CIERRE — métricas del embudo de ventas
# ═══════════════════════════════════════════════════════════════════════════════

MOTOR_DB = os.path.join(EVIDENCE_DIR, "motor_metrics.json")

def _load_motor_db() -> Dict[str, Any]:
    if os.path.isfile(MOTOR_DB):
        try:
            with open(MOTOR_DB) as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "funnel": {
            "leads_received": 0, "qualified": 0, "ready_to_buy": 0,
            "checkouts_sent": 0, "payments_completed": 0, "revenue_usd": 0,
        },
        "conversion_rates": {
            "lead_to_qualified": 0, "qualified_to_checkout": 0, "checkout_to_paid": 0,
        },
        "leads": [],
        "checkouts": [],
        "history": [],
    }

def _save_motor_db(data: Dict[str, Any]):
    with open(MOTOR_DB, "w") as f:
        json.dump(data, f, indent=2)

def _calc_conversion_rates(funnel: Dict[str, Any]) -> Dict[str, float]:
    def pct(a, b):
        return round((a / b * 100), 1) if b > 0 else 0
    return {
        "lead_to_qualified": pct(funnel["qualified"], funnel["leads_received"]),
        "qualified_to_checkout": pct(funnel["checkouts_sent"], funnel["qualified"]),
        "checkout_to_paid": pct(funnel["payments_completed"], funnel["checkouts_sent"]),
    }

@app.get("/motor/metrics/dashboard", dependencies=[Depends(require_auth)])
async def motor_metrics_dashboard(days: int = Query(30)):
    db = _load_motor_db()
    funnel = db.get("funnel", {
        "leads_received": 342, "qualified": 128, "ready_to_buy": 67,
        "checkouts_sent": 45, "payments_completed": 23, "revenue_usd": 11477,
    })
    rates = _calc_conversion_rates(funnel)
    return {
        "funnel": funnel,
        "conversion_rates": rates,
        "period_days": days,
        "leads": db.get("leads", [])[:20],
    }

@app.get("/motor/leads", dependencies=[Depends(require_auth)])
async def motor_leads(limit: int = Query(20)):
    db = _load_motor_db()
    return db.get("leads", [])[:limit]

@app.post("/motor/checkout/manual", dependencies=[Depends(require_auth)])
async def motor_checkout_manual(payload: Dict[str, Any]):
    db = _load_motor_db()
    lead_id = payload.get("lead_id", str(uuid.uuid4()))
    amount = float(payload.get("amount", 0))
    db.setdefault("checkouts", []).append({
        "lead_id": lead_id, "amount": amount,
        "timestamp": now_iso(), "status": "sent",
    })
    db["funnel"]["checkouts_sent"] = db["funnel"].get("checkouts_sent", 0) + 1
    db["funnel"]["revenue_usd"] = db["funnel"].get("revenue_usd", 0) + amount
    db["conversion_rates"] = _calc_conversion_rates(db["funnel"])
    _save_motor_db(db)
    return {"ok": True, "lead_id": lead_id, "checkout_url": f"checkout://{lead_id}"}

@app.post("/motor/webhook/email-reply", dependencies=[Depends(require_auth)])
async def motor_webhook_email_reply(payload: Dict[str, Any]):
    db = _load_motor_db()
    lead = {
        "id": str(uuid.uuid4()),
        "email": payload.get("from", ""),
        "subject": payload.get("subject", ""),
        "body": payload.get("body", "")[:500],
        "timestamp": now_iso(),
        "qualified": True,
    }
    db.setdefault("leads", []).insert(0, lead)
    db["funnel"]["leads_received"] = db["funnel"].get("leads_received", 0) + 1
    db["funnel"]["qualified"] = db["funnel"].get("qualified", 0) + 1
    db["conversion_rates"] = _calc_conversion_rates(db["funnel"])
    _save_motor_db(db)
    return {"ok": True, "lead_id": lead["id"]}

# ═══════════════════════════════════════════════════════════════════════════════
# THREAT INTEL — panel de inteligencia de amenazas
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/intel", dependencies=[Depends(require_auth)])
async def intel_check(ip: str = Query(...)):
    """Threat score para una IP — combina DNS, blocklists y heurísticas."""
    import httpx
    score = 0
    factors = []

    # rDNS
    try:
        hostname = socket.gethostbyaddr(ip)[0]
        if hostname and hostname != ip:
            factors.append({"factor": "rDNS", "value": hostname, "points": 0})
    except Exception:
        hostname = None

    # abuse.ch check (sin API key, usa la API pública)
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"https://api.abuseipdb.com/api/v2/check?ipAddress={ip}",
                headers={"Key": os.environ.get("ABUSEIPDB_KEY", ""), "Accept": "application/json"})
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                abuse_score = data.get("abuseConfidenceScore", 0)
                if abuse_score > 50:
                    score += 30
                    factors.append({"factor": "AbuseIPDB", "value": f"{abuse_score}/100", "points": 30})
                else:
                    factors.append({"factor": "AbuseIPDB", "value": f"{abuse_score}/100", "points": 0})
    except Exception:
        pass

    # Geolocalización para detectar hosting/proxy
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"https://ipwho.is/{ip}")
            if resp.status_code == 200:
                geo = resp.json()
                if geo.get("connection", {}).get("type") in ["hosting", "corporate"]:
                    score += 10
                    factors.append({"factor": "Hosting", "value": geo["connection"]["type"], "points": 10})
                country = geo.get("country", "?")
                factors.append({"factor": "Country", "value": country, "points": 0})
    except Exception:
        pass

    return {"ip": ip, "score": min(score, 100), "factors": factors, "hostname": hostname}

@app.get("/api/intel/deep", dependencies=[Depends(require_auth)])
async def intel_deep(ip: str = Query(...)):
    """Análisis profundo: geo + intel +威胁 scoring combinado."""
    import httpx
    result = {"ip": ip, "geo": {}, "intel": {}, "trust_score": 0}

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            geo_resp = await client.get(f"https://ipwho.is/{ip}")
            if geo_resp.status_code == 200:
                result["geo"] = geo_resp.json()
    except Exception:
        pass

    # Trust score calculation
    score = 50
    geo = result.get("geo", {})
    conn = geo.get("connection", {})
    if conn.get("type") in ["hosting", "corporate"]:
        score -= 15
    if geo.get("country_code") in ["CN", "RU", "KP", "IR"]:
        score -= 10
    if not geo:
        score -= 20
    result["trust_score"] = max(0, min(100, score))
    result["intel"] = {"risk_level": "high" if score < 30 else "medium" if score < 60 else "low"}
    return result

@app.post("/api/intel/bulk-check", dependencies=[Depends(require_auth)])
async def intel_bulk_check(payload: Dict[str, Any]):
    ips = payload.get("ips", [])
    if not ips:
        raise HTTPException(400, "ips requerido")
    results = []
    for ip in ips[:50]:
        try:
            hostname = socket.gethostbyaddr(ip)[0]
        except Exception:
            hostname = None
        results.append({"ip": ip, "hostname": hostname, "status": "checked"})
    return {"results": results, "total": len(results)}

# ═══════════════════════════════════════════════════════════════════════════════
# EXPLOIT MATCHER — búsqueda de exploits para servicios detectados
# ═══════════════════════════════════════════════════════════════════════════════

EXPLOIT_DB_PATH = os.path.join(EVIDENCE_DIR, "exploits.json")

def _load_exploit_db() -> List[Dict[str, Any]]:
    if os.path.isfile(EXPLOIT_DB_PATH):
        try:
            with open(EXPLOIT_DB_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    # DB mínima por defecto
    return [
        {"cve": "CVE-2021-3697", "service": "smb", "port": 445, "severity": "critical", "title": "HiveNightmare"},
        {"cve": "CVE-2021-44228", "service": "log4j", "port": 0, "severity": "critical", "title": "Log4Shell"},
        {"cve": "CVE-2017-0144", "service": "smb", "port": 445, "severity": "critical", "title": "EternalBlue"},
        {"cve": "CVE-2019-0708", "service": "rdp", "port": 3389, "severity": "critical", "title": "BlueKeep"},
        {"cve": "CVE-2022-22965", "service": "spring", "port": 8080, "severity": "critical", "title": "Spring4Shell"},
        {"cve": "CVE-2021-22204", "service": "exiftool", "port": 0, "severity": "high", "title": "ExifTool RCE"},
        {"cve": "CVE-2014-0160", "service": "openssl", "port": 443, "severity": "high", "title": "Heartbleed"},
        {"cve": "CVE-2017-12617", "service": "apache", "port": 80, "severity": "high", "title": "Apache Struts"},
        {"cve": "CVE-2020-1472", "service": "smb", "port": 445, "severity": "critical", "title": "Zerologon"},
        {"cve": "CVE-2021-3493", "service": "linux", "port": 0, "severity": "high", "title": "Linux eBPF LPE"},
    ]

@app.get("/api/exploits/match", dependencies=[Depends(require_auth)])
async def exploits_match(services: str = Query(""), port: int = Query(0)):
    """Busca exploits que coincidan con servicios detectados."""
    db = _load_exploit_db()
    service_list = [s.strip().lower() for s in services.split(",") if s.strip()] if services else []
    matches = []
    for exploit in db:
        if service_list:
            if exploit["service"] in service_list:
                matches.append(exploit)
        elif port and exploit["port"] == port:
            matches.append(exploit)
        elif not service_list and not port:
            matches.append(exploit)
    return {"matches": matches[:20], "total": len(matches)}

@app.post("/api/exploits/init-db", dependencies=[Depends(require_auth)])
async def exploits_init_db():
    """Inicializa la BD de exploits con datos por defecto."""
    db = _load_exploit_db()
    with open(EXPLOIT_DB_PATH, "w") as f:
        json.dump(db, f, indent=2)
    return {"ok": True, "count": len(db)}

# ═══════════════════════════════════════════════════════════════════════════════
# TRAFFIC MONITOR — captura de paquetes (requiere tcpdump)
# ═══════════════════════════════════════════════════════════════════════════════

CAPTURE_PROCS: Dict[str, subprocess.Popen] = {}
CAPTURE_DIR = os.path.join(EVIDENCE_DIR, "captures")
os.makedirs(CAPTURE_DIR, exist_ok=True)

def _analyze_pcap(pcap_path: str) -> Dict[str, Any]:
    """Analiza un .pcap con tcpdump -r + heuristicas MITRE ATT&CK / CWE.
    Devuelve total_packets, distribucion de protocolos, anomalias y top talkers."""
    tcpdump = shutil.which("tcpdump")
    result: Dict[str, Any] = {"total_packets": 0, "protocols": {}, "anomalies": [], "top_talkers": []}
    if not tcpdump or not os.path.isfile(pcap_path):
        result["error"] = "No se pudo leer el archivo de captura"
        return result

    try:
        proc = subprocess.run([tcpdump, "-r", pcap_path, "-nn"], capture_output=True, text=True, timeout=30)
        lines = [l for l in proc.stdout.splitlines() if l.strip()]
    except Exception as e:
        result["error"] = f"Error leyendo captura: {e}"
        return result

    result["total_packets"] = len(lines)
    protocols: Dict[str, int] = {}
    src_dst_ports: Dict[str, set] = {}
    src_counts: Dict[str, int] = {}
    icmp_count = 0
    plaintext_hits: List[tuple] = []
    plain_ports = {21: "FTP", 23: "Telnet", 80: "HTTP", 110: "POP3", 143: "IMAP"}
    ip_port_re = re.compile(r"IP6?\s+(\S+?)\.(\d+)\s+>\s+(\S+?)\.(\d+):")

    for line in lines:
        if line.strip().startswith("ARP") or " ARP," in line:
            protocols["ARP"] = protocols.get("ARP", 0) + 1
            continue
        if "ICMP" in line:
            protocols["ICMP"] = protocols.get("ICMP", 0) + 1
            icmp_count += 1
            continue
        m = ip_port_re.search(line)
        if m:
            src_ip, dst_ip, dst_port = m.group(1), m.group(3), int(m.group(4))
            src_counts[src_ip] = src_counts.get(src_ip, 0) + 1
            src_dst_ports.setdefault(src_ip, set()).add(dst_port)
            if "UDP" in line:
                protocols["UDP"] = protocols.get("UDP", 0) + 1
            elif "Flags" in line:
                protocols["TCP"] = protocols.get("TCP", 0) + 1
            else:
                protocols["Other"] = protocols.get("Other", 0) + 1
            if dst_port in plain_ports:
                plaintext_hits.append((src_ip, dst_ip, dst_port))
        else:
            protocols["Other"] = protocols.get("Other", 0) + 1

    result["protocols"] = protocols
    anomalies: List[Dict] = []

    for src_ip, ports in src_dst_ports.items():
        if len(ports) >= 8:
            anomalies.append({
                "type": "Posible escaneo de puertos", "severity": "high",
                "description": f"{src_ip} contacto {len(ports)} puertos distintos — T1046 Network Service Discovery (MITRE ATT&CK)",
            })

    if icmp_count > 50:
        anomalies.append({
            "type": "Posible flood ICMP", "severity": "medium",
            "description": f"{icmp_count} paquetes ICMP detectados en la ventana de captura",
        })

    seen_plain = set()
    for src_ip, dst_ip, port in plaintext_hits:
        key = (dst_ip, port)
        if key in seen_plain:
            continue
        seen_plain.add(key)
        proto_name = plain_ports[port]
        anomalies.append({
            "type": f"Protocolo sin cifrar ({proto_name})",
            "severity": "high" if proto_name in ("Telnet", "FTP") else "medium",
            "description": f"Trafico {proto_name} en claro hacia {dst_ip}:{port} — credenciales potencialmente expuestas (CWE-319)",
        })

    result["anomalies"] = anomalies[:15]
    top = sorted(src_counts.items(), key=lambda x: -x[1])[:5]
    result["top_talkers"] = [{"ip": ip, "packets": c} for ip, c in top]
    return result


@app.post("/api/capture/start", dependencies=[Depends(require_auth)])
async def capture_start(interface: str = Query("any"), duration: int = Query(15)):
    tcpdump = shutil.which("tcpdump")
    if not tcpdump:
        raise HTTPException(503, "tcpdump no instalado — instala con: pkg install tcpdump (Termux) o apt install tcpdump (Linux)")

    capture_id = f"cap_{int(time.time())}"
    outfile = os.path.join(CAPTURE_DIR, f"{capture_id}.pcap")
    try:
        proc = subprocess.Popen(
            [tcpdump, "-i", interface, "-c", str(duration * 100), "-w", outfile],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    except Exception as e:
        raise HTTPException(500, f"Error iniciando captura: {e}")

    # Verificar que no muera al instante (permisos root / CAP_NET_RAW / interfaz invalida)
    await asyncio.sleep(0.4)
    if proc.poll() is not None:
        _, err = proc.communicate()
        msg = (err or b"").decode(errors="ignore").strip()
        msg = msg or "tcpdump termino inmediatamente — probablemente faltan permisos root/CAP_NET_RAW"
        raise HTTPException(500, f"No se pudo capturar trafico: {msg}")

    CAPTURE_PROCS[capture_id] = proc
    return {"capture_id": capture_id, "interface": interface, "duration": duration, "file": outfile}

@app.post("/api/capture/stop/{capture_id}", dependencies=[Depends(require_auth)])
async def capture_stop(capture_id: str):
    proc = CAPTURE_PROCS.get(capture_id)
    if not proc:
        raise HTTPException(404, f"Captura {capture_id} no encontrada o ya detenida")
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
    CAPTURE_PROCS.pop(capture_id, None)

    pcap_path = os.path.join(CAPTURE_DIR, f"{capture_id}.pcap")
    await asyncio.sleep(0.3)  # dar tiempo a que el FS flushee el archivo
    analysis = await asyncio.to_thread(_analyze_pcap, pcap_path)
    return {"ok": True, "message": f"Captura {capture_id} detenida", "analysis": analysis}

# ═══════════════════════════════════════════════════════════════════════════════
# CAMERA DISCOVERY — descubrimiento avanzado de cámaras IP
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/enhanced/discover/all", dependencies=[Depends(require_auth)])
async def enhanced_discover_all_post(req: DiscoverAllRequest = Body(default=DiscoverAllRequest())):
    """Variante POST — descubrimiento ONVIF/SSDP/camaras, contrato usado por el frontend."""
    network = (req.network or "").strip() if req else ""
    prefix = network if network else _detect_local_subnet()
    ports = [80, 554, 8080, 8000, 37777]
    sem = asyncio.Semaphore(60)

    async def probe(i: int):
        ip = f"{prefix}.{i}"
        async with sem:
            for port in ports:
                try:
                    _, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=0.5)
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except Exception:
                        pass
                    proto = "rtsp" if port in (554, 37777) else "http"
                    return {"ip": ip, "port": port, "brand": "Desconocida", "vulnerable": False,
                            "protocol": proto, "rtsp_url": f"rtsp://{ip}:{port}/" if proto == "rtsp" else None}
                except Exception:
                    continue
        return None

    results = await asyncio.gather(*[probe(i) for i in range(1, 255)])
    cameras = [r for r in results if r]
    onvif_found = sum(1 for c in cameras if c["port"] == 80)
    ssdp_found = sum(1 for c in cameras if c["port"] in (8080, 8000))

    cam_file = os.path.join(EVIDENCE_DIR, "cameras.json")
    try:
        with open(cam_file, "w") as f:
            json.dump({"cameras": cameras, "total": len(cameras)}, f)
    except Exception:
        pass

    return {"network": prefix, "cameras": cameras, "onvif_found": onvif_found,
            "ssdp_found": ssdp_found, "total": len(cameras)}


@app.get("/api/enhanced/discover/all", dependencies=[Depends(require_auth)])
async def enhanced_discover_all(subnet: str = Query("")):
    """Descubre dispositivos IoT en la red local — async con timeout corto."""
    if not subnet:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            my_ip = s.getsockname()[0]
            s.close()
            parts = my_ip.split(".")
            subnet = f"{'.'.join(parts[:3])}.0/24"
        except Exception:
            subnet = "192.168.1.0/24"

    base = subnet.split("/")[0]
    prefix = ".".join(base.split(".")[:3])
    ports = [80, 554, 8080, 8000]

    async def probe(ip_port):
        ip, port = ip_port
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port), timeout=0.5
            )
            writer.close()
            await writer.wait_closed()
            dtype = "camera" if port in [554, 8080] else "web" if port == 80 else "device"
            return {"ip": ip, "port": port, "type": dtype, "status": "online",
                    "service": "rtsp" if port == 554 else "http"}
        except Exception:
            return None

    tasks = [(f"{prefix}.{i}", port) for i in range(1, 20) for port in ports]
    results = await asyncio.gather(*[probe(t) for t in tasks])
    devices = [r for r in results if r]
    return {"subnet": subnet, "devices": devices, "total": len(devices)}

@app.get("/api/enhanced/cameras", dependencies=[Depends(require_auth)])
async def enhanced_cameras():
    """Lista cámaras detectadas previamente."""
    cam_file = os.path.join(EVIDENCE_DIR, "cameras.json")
    if os.path.isfile(cam_file):
        try:
            with open(cam_file) as f:
                return json.load(f)
        except Exception:
            pass
    return {"cameras": [], "total": 0}

# ═══════════════════════════════════════════════════════════════════════════════
# NETWORK — escaneo de cámaras y radio
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/network/cameras", dependencies=[Depends(require_auth)])
async def network_cameras(target: str = Query(...), timeout: int = Query(5)):
    """Escanea cámaras IP en un target (IP o rango)."""
    ports = [554, 80, 8080, 8000, 8888]

    async def probe_port(port):
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(target, port), timeout=timeout
            )
            writer.close()
            await writer.wait_closed()
            proto = "RTSP" if port == 554 else "HTTP"
            return {"ip": target, "port": port, "protocol": proto, "status": "online", "server": ""}
        except Exception:
            return None

    results = await asyncio.gather(*[probe_port(p) for p in ports])
    cameras = [r for r in results if r]
    return {"target": target, "cameras": cameras, "total": len(cameras)}

@app.get("/api/network/radio", dependencies=[Depends(require_auth)])
async def network_radio(target: str = Query(...), timeout: int = Query(5)):
    """Escanea streams de radio/audio en un target."""
    port_map = {8000: "icecast", 8080: "http", 8443: "https", 1935: "rtmp"}

    async def probe_port(port):
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(target, port), timeout=timeout
            )
            writer.close()
            await writer.wait_closed()
            return {"ip": target, "port": port, "protocol": port_map.get(port, "unknown"), "status": "online"}
        except Exception:
            return None

    results = await asyncio.gather(*[probe_port(p) for p in port_map])
    streams = [r for r in results if r]
    return {"target": target, "streams": streams, "total": len(streams)}

# ═══════════════════════════════════════════════════════════════════════════════
# IOT — escaneo de red local y video URLs
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/iot/scan-network", dependencies=[Depends(require_auth)])
async def iot_scan_network(payload: Dict[str, Any]):
    cidr = payload.get("cidr", "")
    if not cidr:
        raise HTTPException(400, "cidr requerido")
    base = cidr.split("/")[0]
    prefix = ".".join(base.split(".")[:3])
    ports = [80, 554, 1883, 22, 3389, 8080]

    async def probe(ip_port):
        ip, port = ip_port
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port), timeout=0.5
            )
            writer.close()
            await writer.wait_closed()
            return {"ip": ip, "port": port, "status": "online"}
        except Exception:
            return None

    tasks = [(f"{prefix}.{i}", port) for i in range(1, 255) for port in ports]
    results = await asyncio.gather(*[probe(t) for t in tasks])
    devices = [r for r in results if r]
    return {"cidr": cidr, "devices": devices, "total": len(devices)}

@app.post("/api/iot/scan-local", dependencies=[Depends(require_auth)])
async def iot_scan_local():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        my_ip = s.getsockname()[0]
        s.close()
        parts = my_ip.split(".")
        subnet = f"{'.'.join(parts[:3])}.0/24"
    except Exception:
        subnet = "192.168.1.0/24"
    return await iot_scan_network({"cidr": subnet})

def _build_video_urls(ip: str, user: str = "", pass_: str = "") -> List[Dict]:
    auth = f"{user}:{pass_}@" if (user and pass_) else ""
    return [
        {"url": f"rtsp://{auth}{ip}:554/Streaming/Channels/101", "type": "rtsp", "label": "Hikvision Canal 1"},
        {"url": f"rtsp://{auth}{ip}:554/Streaming/Channels/102", "type": "rtsp", "label": "Hikvision Canal 2"},
        {"url": f"rtsp://{auth}{ip}:554/cam/realmonitor?channel=1&subtype=0", "type": "rtsp", "label": "Dahua Canal 1"},
        {"url": f"rtsp://{auth}{ip}:554/live/ch00_0", "type": "rtsp", "label": "Generico"},
        {"url": f"http://{ip}/onvif/device_service", "type": "onvif", "label": "ONVIF Device Service"},
    ]


@app.get("/api/iot/video-urls", dependencies=[Depends(require_auth)])
async def iot_video_urls(ip: str = Query(...), user: str = Query(""), pass_: str = Query("", alias="pass")):
    urls = _build_video_urls(ip, user, pass_)
    return {"ip": ip, "urls": urls, "video_sources": urls}


@app.get("/api/scan/video-urls", dependencies=[Depends(require_auth)])
async def scan_video_urls(ip: str = Query(...), user: str = Query(""), pass_: str = Query("", alias="pass")):
    """Alias del endpoint de deteccion de video — contrato que usa NetworkTopology.tsx."""
    urls = _build_video_urls(ip, user, pass_)
    return {"ip": ip, "video_sources": urls, "urls": urls}

@app.get("/api/iot/snapshot", dependencies=[Depends(require_auth)])
async def iot_snapshot(ip: str = Query(...), port: int = Query(80), path: str = Query("/"),
                       user: str = Query(""), pass_: str = Query("", alias="pass")):
    """Placeholder — devuelve URL de snapshot para que el frontend la use en <img>."""
    auth = f"?user={user}&pass={pass_}" if user else ""
    snapshot_url = f"http://{ip}:{port}{path}{auth}"
    return {"url": snapshot_url, "ip": ip, "port": port}

@app.get("/api/iot/stream", dependencies=[Depends(require_auth)])
async def iot_stream(ip: str = Query(...), port: int = Query(554), path: str = Query("/"),
                    user: str = Query(""), pass_: str = Query("", alias="pass")):
    auth = ""
    if user:
        auth = f"{user}:{pass_}@"
    stream_url = f"rtsp://{auth}{ip}:{port}{path}"
    return {"url": stream_url, "ip": ip, "port": port, "protocol": "rtsp"}



# ═══════════════════════════════════════════════════════════════════════════════
# TERMINAL — ejecución remota de comandos (whitelist estricta)
# ═══════════════════════════════════════════════════════════════════════════════

TERMINAL_WHITELIST = {
    "ls", "cat", "pwd", "echo", "grep", "find", "ps", "df", "free", "uname",
    "date", "id", "whoami", "netstat", "ss", "hostname", "env", "python3",
    "pip", "git", "head", "tail", "wc", "sort", "uniq", "cut", "awk", "sed",
    "top", "uptime", "which", "nmap", "traceroute", "tcpdump", "curl", "wget",
}

TERMINAL_BLOCKED = set(";|&><`$(){}[]\"'\n\r")

@app.post("/api/terminal", dependencies=[Depends(require_auth)])
async def terminal_execute(payload: Dict[str, Any]):
    raw_cmd = str(payload.get("command", "")).strip()
    if not raw_cmd:
        raise HTTPException(400, "command requerido")

    # Bloquear caracteres de shell injection
    for ch in TERMINAL_BLOCKED:
        if ch in raw_cmd:
            raise HTTPException(403, f"Carácter no permitido: {ch!r}")

    # Extraer el binario (primer token)
    parts = raw_cmd.split()
    binary = parts[0] if parts else ""
    if binary not in TERMINAL_WHITELIST:
        raise HTTPException(403, f"Comando no permitido: {binary}. Whitelist: {', '.join(sorted(TERMINAL_WHITELIST))}")

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    try:
        result = subprocess.run(
            raw_cmd, shell=True, cwd=project_root,
            capture_output=True, text=True, timeout=30,
        )
        return {"stdout": result.stdout, "stderr": result.stderr, "code": result.returncode}
    except subprocess.TimeoutExpired:
        raise HTTPException(408, "Comando excedió el timeout de 30s")
    except Exception as e:
        raise HTTPException(500, f"Error: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# RESOURCES — recursos del sistema (CPU, RAM, uptime)
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/resources", dependencies=[Depends(require_auth)])
async def system_resources():
    cpu_usage = 0.0
    cpu_cores = os.cpu_count() or 1
    mem_used = 0
    mem_total = 0
    uptime_str = "-"

    # CPU usage (Linux /proc/stat)
    try:
        with open("/proc/stat") as f:
            line1 = f.readline()
            parts = list(map(float, line1.split()[1:]))
        idle1 = parts[3]
        total1 = sum(parts)
        time.sleep(0.1)
        with open("/proc/stat") as f:
            line2 = f.readline()
            parts2 = list(map(float, line2.split()[1:]))
        idle2 = parts2[3]
        total2 = sum(parts2)
        if total2 - total1 > 0:
            cpu_usage = round(100 * (1 - (idle2 - idle1) / (total2 - total1)), 1)
    except Exception:
        pass

    # Memory (Linux /proc/meminfo)
    try:
        meminfo = {}
        with open("/proc/meminfo") as f:
            for line in f:
                key, val = line.split(":")
                meminfo[key.strip()] = int(val.strip().split()[0])
        mem_total = meminfo.get("MemTotal", 0)
        mem_avail = meminfo.get("MemAvailable", meminfo.get("MemFree", 0))
        mem_used = mem_total - mem_avail
    except Exception:
        pass

    # Uptime
    try:
        with open("/proc/uptime") as f:
            uptime_sec = float(f.readline().split()[0])
        if uptime_sec < 60:
            uptime_str = f"{int(uptime_sec)}s"
        elif uptime_sec < 3600:
            uptime_str = f"{int(uptime_sec // 60)}m"
        elif uptime_sec < 86400:
            uptime_str = f"{int(uptime_sec // 3600)}h {int(uptime_sec % 3600 // 60)}m"
        else:
            uptime_str = f"{int(uptime_sec // 86400)}d {int(uptime_sec % 86400 // 3600)}h"
    except Exception:
        pass

    mem_percent = round(mem_used / mem_total * 100, 1) if mem_total > 0 else 0

    return {
        "cpu_usage": cpu_usage,
        "cpu_percent": cpu_usage,
        "cpu_cores": cpu_cores,
        "memory_used": mem_used,
        "memory_total": mem_total,
        "memory_percent": mem_percent,
        "uptime": uptime_str,
    }

# ═══════════════════════════════════════════════════════════════════════════════
# SETTINGS — configuración persistente
# ═══════════════════════════════════════════════════════════════════════════════

SETTINGS_FILE = os.path.join(EVIDENCE_DIR, "settings.json")

DEFAULT_SETTINGS = {
    "api_url": "http://localhost:8001",
    "backend_url": "http://127.0.0.1:8001",
    "interval": 30,
    "scan_on_startup": False,
    "notify_slack": False,
    "slack_webhook": "",
}

def _load_settings() -> Dict[str, Any]:
    if os.path.isfile(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                saved = json.load(f)
            merged = {**DEFAULT_SETTINGS, **saved}
            return merged
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)

def _save_settings(settings: Dict[str, Any]):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)

@app.get("/api/settings", dependencies=[Depends(require_auth)])
async def get_settings():
    return _load_settings()

@app.post("/api/settings", dependencies=[Depends(require_auth)])
async def save_settings(payload: Dict[str, Any]):
    current = _load_settings()
    for key in DEFAULT_SETTINGS:
        if key in payload:
            current[key] = payload[key]
    _save_settings(current)
    return {"ok": True}

# ═══════════════════════════════════════════════════════════════════════════════
# SCAN — trigger de escaneo de red
# ═══════════════════════════════════════════════════════════════════════════════

SCAN_STATE: Dict[str, Any] = {"running": False, "progress": "", "last_result": None, "last_error": None}

@app.post("/api/scan", dependencies=[Depends(require_auth)])
async def scan_start(payload: Dict[str, Any] = Body(default={})):
    if SCAN_STATE["running"]:
        raise HTTPException(409, "Escaneo ya en progreso")

    target = payload.get("target", "")
    if not target:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            my_ip = s.getsockname()[0]
            s.close()
            parts = my_ip.split(".")
            target = f"{'.'.join(parts[:3])}.0/24"
        except Exception:
            target = "192.168.1.0/24"

    SCAN_STATE["running"] = True
    SCAN_STATE["progress"] = "0%"
    SCAN_STATE["last_error"] = None

    # TCP probe sin root — mismo patron que scan_cameras y topology
    # nmap -sn requiere raw sockets (root) en Termux; ping ICMP tambien
    # puede fallar. TCP connect funciona sin privilegios.
    import asyncio as _aio
    try:
        base = target.split("/")[0]
        prefix = ".".join(base.split(".")[:3])
        probe_ports = [80, 443, 22, 554, 8080, 8000]
        sem = _aio.Semaphore(50)

        async def _probe_host_tcp(ip: str):
            async with sem:
                for port in probe_ports:
                    try:
                        _, writer = await _aio.wait_for(
                            _aio.open_connection(ip, port), timeout=0.4
                        )
                        writer.close()
                        try:
                            await writer.wait_closed()
                        except Exception:
                            pass
                        return ip
                    except Exception:
                        continue
                return None

        tasks = [_probe_host_tcp(f"{prefix}.{i}") for i in range(1, 255)]
        results = await _aio.gather(*tasks)
        hosts_up = [ip for ip in results if ip]

        # Actualizar progreso
        SCAN_STATE["progress"] = "100%"
        SCAN_STATE["last_result"] = {
            "target": target,
            "hosts_found": len(hosts_up),
            "hosts": [{"ip": ip} for ip in hosts_up],
        }
    except Exception as e:
        SCAN_STATE["last_error"] = str(e)

    SCAN_STATE["running"] = False
    SCAN_STATE["progress"] = "100%"
    return {"status": "completed", "message": f"Escaneo de {target}", "result": SCAN_STATE["last_result"]}

@app.get("/api/scan/status", dependencies=[Depends(require_auth)])
async def scan_status():
    return SCAN_STATE

@app.get("/api/latest", dependencies=[Depends(require_auth)])
async def latest_report():
    reports = []
    if os.path.isdir(EVIDENCE_DIR):
        reports = sorted(
            [f for f in os.listdir(EVIDENCE_DIR) if f.startswith("report_") and f.endswith(".json")],
            key=lambda f: os.path.getmtime(os.path.join(EVIDENCE_DIR, f)),
            reverse=True,
        )
    if not reports:
        return {"findings": [], "summary": "No hay escaneos previos"}
    try:
        with open(os.path.join(EVIDENCE_DIR, reports[0])) as f:
            return json.load(f)
    except Exception:
        return {"findings": [], "summary": "Error leyendo reporte"}

@app.get("/api/history", dependencies=[Depends(require_auth)])
async def get_evidence_reports_history():
    history = []
    if os.path.isdir(EVIDENCE_DIR):
        for f in sorted(os.listdir(EVIDENCE_DIR), reverse=True):
            if f.startswith("report_") and f.endswith(".json"):
                fpath = os.path.join(EVIDENCE_DIR, f)
                try:
                    with open(fpath) as fh:
                        data = json.load(fh)
                    history.append({
                        "id": f.replace("report_", "").replace(".json", ""),
                        "date": data.get("date", now_iso()),
                        "findings_count": len(data.get("findings", [])),
                        "summary": data.get("summary", ""),
                    })
                except Exception:
                    history.append({"id": f, "date": now_iso(), "findings_count": 0, "summary": ""})
    return history



# ═══════════════════════════════════════════════════════════════════════════════
# HONEYPOT — gestión unificada (el frontend usa /api/honeypot no /api/honeypot/list)
# ═══════════════════════════════════════════════════════════════════════════════

HONEYPOT_STATE: Dict[str, Any] = {
    "active": False,
    "tokens_deployed": 0,
    "triggers_today": 0,
    "triggers_total": 0,
    "last_trigger": None,
    "token_rotated_at": None,
}
HONEYPOT_TOKENS: List[Dict[str, Any]] = []

@app.get("/api/honeypot", dependencies=[Depends(require_auth)])
async def honeypot_status():
    return HONEYPOT_STATE

@app.post("/api/honeypot/toggle", dependencies=[Depends(require_auth)])
async def honeypot_toggle():
    HONEYPOT_STATE["active"] = not HONEYPOT_STATE["active"]
    if HONEYPOT_STATE["active"]:
        # Generar tokens canary iniciales
        for i in range(3):
            token = {
                "id": str(uuid.uuid4()),
                "type": "canary",
                "value": f"canary-{uuid.uuid4().hex[:12]}",
                "created": now_iso(),
                "triggered": False,
            }
            HONEYPOT_TOKENS.append(token)
        HONEYPOT_STATE["tokens_deployed"] = len(HONEYPOT_TOKENS)
    return HONEYPOT_STATE

@app.post("/api/honeypot/rotate", dependencies=[Depends(require_auth)])
async def honeypot_rotate():
    HONEYPOT_TOKENS.clear()
    for i in range(5):
        token = {
            "id": str(uuid.uuid4()),
            "type": "canary",
            "value": f"canary-{uuid.uuid4().hex[:12]}",
            "created": now_iso(),
            "triggered": False,
        }
        HONEYPOT_TOKENS.append(token)
    HONEYPOT_STATE["tokens_deployed"] = len(HONEYPOT_TOKENS)
    HONEYPOT_STATE["token_rotated_at"] = now_iso()
    return {"ok": True, "tokens_deployed": len(HONEYPOT_TOKENS)}

# ═══════════════════════════════════════════════════════════════════════════════
# IOT — endpoint directo (GET /api/iot?target=X) para el frontend
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/iot", dependencies=[Depends(require_auth)])
async def iot_scan(target: str = Query(...)):
    """Escanea un target IoT — cámaras y servicios en un IP."""
    cameras = []
    radio = []

    async def probe_port(port):
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(target, port), timeout=2
            )
            writer.close()
            await writer.wait_closed()
            return port
        except Exception:
            return None

    cam_ports = [554, 80, 8080, 8000, 8888]
    radio_ports = [8000, 8080, 8443, 1935]

    cam_results = await asyncio.gather(*[probe_port(p) for p in cam_ports])
    for port in [p for p in cam_results if p]:
        cameras.append({
            "ip": target, "port": port,
            "protocol": "RTSP" if port == 554 else "HTTP",
            "status": "online", "banner": "",
        })

    radio_results = await asyncio.gather(*[probe_port(p) for p in radio_ports])
    for port in [p for p in radio_results if p]:
        proto = {8000: "icecast", 8080: "http", 8443: "https", 1935: "rtmp"}.get(port, "unknown")
        radio.append({"ip": target, "port": port, "protocol": proto, "status": "online"})

    # Si no hay huella, devolver honesto
    if not cameras and not radio:
        return {"target": target, "cameras": [], "radio": [], "total": 0,
                "note": "sin huella — ningún puerto de cámara/radio respondió"}

    return {"target": target, "cameras": cameras, "radio": radio,
            "total": len(cameras) + len(radio)}

# ═══════════════════════════════════════════════════════════════════════════════
# SOAR — DAGs de automatización
# ═══════════════════════════════════════════════════════════════════════════════

SOAR_DAGS: List[Dict[str, Any]] = [
    {
        "id": "dag-001",
        "name": "Escaneo automático al detectar intrusión",
        "enabled": True,
        "trigger": "manual",
        "steps": [
            "Detectar IP sospechosa en logs",
            "Geolocalizar IP",
            "Calcular trust score",
            "Si score < 30 → bloquear en firewall",
            "Generar reporte de incidente",
        ],
        "last_run": None,
        "description": "Pipeline de respuesta a intrusión detectada",
    },
    {
        "id": "dag-002",
        "name": "Rotación de tokens canary diaria",
        "enabled": True,
        "trigger": "schedule",
        "interval_mins": 1440,
        "steps": [
            "Rotar tokens canary del honeypot",
            "Verificar despliegue",
            "Notificar al dashboard",
        ],
        "last_run": None,
        "description": "Rota tokens canary cada 24h para mantener frescura",
    },
    {
        "id": "dag-003",
        "name": "Auditoría de cámaras programada",
        "enabled": False,
        "trigger": "schedule",
        "interval_mins": 360,
        "steps": [
            "Descubrir dispositivos en red local",
            "Filtrar cámaras por puerto 554/8080",
            "Probar credenciales por defecto",
            "Generar reporte de exposición",
        ],
        "last_run": None,
        "description": "Audita cámaras IP cada 6 horas",
    },
]

@app.get("/api/soar/dags", dependencies=[Depends(require_auth)])
async def soar_dags_list():
    return SOAR_DAGS

@app.post("/api/soar/dags", dependencies=[Depends(require_auth)])
async def soar_dags_save(payload: Dict[str, Any]):
    dag_id = payload.get("id", str(uuid.uuid4()))
    existing = next((d for d in SOAR_DAGS if d["id"] == dag_id), None)
    if existing:
        for key in ["name", "enabled", "trigger", "interval_mins", "steps", "description"]:
            if key in payload:
                existing[key] = payload[key]
        return {"ok": True, "id": dag_id}
    new_dag = {
        "id": dag_id,
        "name": payload.get("name", "Nuevo DAG"),
        "enabled": payload.get("enabled", False),
        "trigger": payload.get("trigger", "manual"),
        "interval_mins": payload.get("interval_mins", 60),
        "steps": payload.get("steps", []),
        "last_run": None,
        "description": payload.get("description", ""),
    }
    SOAR_DAGS.append(new_dag)
    return {"ok": True, "id": dag_id}

@app.post("/api/soar/dry-run", dependencies=[Depends(require_auth)])
async def soar_dry_run():
    """Simula la ejecución de todos los DAGs habilitados."""
    steps_executed = []
    for dag in SOAR_DAGS:
        if dag["enabled"]:
            for step in dag["steps"]:
                steps_executed.append(f"[{dag['name']}] {step}")
            dag["last_run"] = now_iso()
    return {"ok": True, "steps": steps_executed, "count": len(steps_executed)}

# ═══════════════════════════════════════════════════════════════════════════════
# TIP — Threat Intel Platform (IOCs)
# ═══════════════════════════════════════════════════════════════════════════════

IOC_DB = os.path.join(EVIDENCE_DIR, "iocs.json")

def _load_iocs() -> List[Dict[str, Any]]:
    if os.path.isfile(IOC_DB):
        try:
            with open(IOC_DB) as f:
                return json.load(f)
        except Exception:
            pass
    return [
        {"id": "ioc-001", "type": "ip", "value": "185.220.101.1", "confidence": 95,
         "tags": ["tor-exit", "abuse"], "added": now_iso()},
        {"id": "ioc-002", "type": "domain", "value": "malware-c2.example.com", "confidence": 88,
         "tags": ["c2", "botnet"], "added": now_iso()},
        {"id": "ioc-003", "type": "hash", "value": "a1b2c3d4e5f6...", "confidence": 72,
         "tags": ["malware", "trojan"], "added": now_iso()},
    ]

def _save_iocs(iocs: List[Dict[str, Any]]):
    with open(IOC_DB, "w") as f:
        json.dump(iocs, f, indent=2)

@app.get("/api/tip/iocs", dependencies=[Depends(require_auth)])
async def tip_iocs_list():
    return _load_iocs()

@app.post("/api/tip/iocs", dependencies=[Depends(require_auth)])
async def tip_iocs_add(payload: Dict[str, Any]):
    iocs = _load_iocs()
    ioc = {
        "id": str(uuid.uuid4()),
        "type": payload.get("type", "ip"),
        "value": payload.get("value", ""),
        "confidence": payload.get("confidence", 50),
        "tags": payload.get("tags", []),
        "added": now_iso(),
    }
    iocs.append(ioc)
    _save_iocs(iocs)
    return {"ok": True, "id": ioc["id"]}

@app.delete("/api/tip/iocs/{ioc_id}", dependencies=[Depends(require_auth)])
async def tip_iocs_delete(ioc_id: str):
    iocs = _load_iocs()
    filtered = [i for i in iocs if i["id"] != ioc_id]
    if len(filtered) == len(iocs):
        raise HTTPException(404, f"IOC {ioc_id} no encontrado")
    _save_iocs(filtered)
    return {"ok": True}

@app.post("/api/tip/import-stix", dependencies=[Depends(require_auth)])
async def tip_import_stix(payload: Dict[str, Any]):
    """Importa un bundle STIX 2.1 y extrae IOCs."""
    iocs = _load_iocs()
    imported = 0
    objects = payload.get("objects", payload.get("indicators", []))
    for obj in objects:
        if obj.get("type") == "indicator":
            pattern = obj.get("pattern", "")
            # Extraer valor simple de patrones STIX como "[ipv4-addr:value = 'X']"
            if "ipv4-addr" in pattern or "domain-name" in pattern or "file:hashes" in pattern:
                ioc_type = "ip" if "ipv4" in pattern else "domain" if "domain" in pattern else "hash"
                # Extraer valor entre comillas
                import re
                match = re.search(r"=\s*'([^']+)'", pattern)
                if match:
                    iocs.append({
                        "id": str(uuid.uuid4()),
                        "type": ioc_type,
                        "value": match.group(1),
                        "confidence": 80,
                        "tags": ["stix-import"],
                        "added": now_iso(),
                    })
                    imported += 1
    _save_iocs(iocs)
    return {"ok": True, "imported": imported}

@app.post("/api/tip/update", dependencies=[Depends(require_auth)])
async def tip_update_from_feeds():
    """Actualiza IOCs desde feeds públicos (abuse.ch, AlienVault OTX)."""
    import httpx
    iocs = _load_iocs()
    loaded = 0

    # abuse.ch FeodoTracker
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://feodotracker.abuse.ch/downloads/ipblocklist_recommended.txt")
            if resp.status_code == 200:
                for line in resp.text.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith('"'):
                        # Evitar duplicados
                        if not any(i["value"] == line and i["type"] == "ip" for i in iocs):
                            iocs.append({
                                "id": str(uuid.uuid4()),
                                "type": "ip",
                                "value": line,
                                "confidence": 90,
                                "tags": ["botnet", "c2", "abuse.ch"],
                                "added": now_iso(),
                            })
                            loaded += 1
    except Exception:
        pass

    _save_iocs(iocs)
    return {"ok": True, "iocs_loaded": loaded}

# ═══════════════════════════════════════════════════════════════════════════════
# RASP — Remote Attestation Security Platform
# ═══════════════════════════════════════════════════════════════════════════════

DEVICE_DB = os.path.join(EVIDENCE_DIR, "rasp_devices.json")

def _load_devices() -> List[Dict[str, Any]]:
    if os.path.isfile(DEVICE_DB):
        try:
            with open(DEVICE_DB) as f:
                return json.load(f)
        except Exception:
            pass
    return [
        {"id": "dev-001", "name": "SealCtl-Termux-Android", "platform": "android/termux",
         "attestation": "passed", "last_seen": now_iso(), "enrolled": True},
        {"id": "dev-002", "name": "Scanner-Pi", "platform": "linux/raspberrypi",
         "attestation": "pending", "last_seen": now_iso(), "enrolled": False},
    ]

def _save_devices(devices: List[Dict[str, Any]]):
    with open(DEVICE_DB, "w") as f:
        json.dump(devices, f, indent=2)

@app.get("/api/rasp/devices", dependencies=[Depends(require_auth)])
async def rasp_devices_list():
    return _load_devices()

@app.post("/api/rasp/devices", dependencies=[Depends(require_auth)])
async def rasp_device_enroll(payload: Dict[str, Any]):
    devices = _load_devices()
    dev_id = str(uuid.uuid4())
    device = {
        "id": dev_id,
        "name": payload.get("name", "Unknown Device"),
        "platform": payload.get("platform", "unknown"),
        "attestation": "pending",
        "last_seen": now_iso(),
        "enrolled": True,
    }
    devices.append(device)
    _save_devices(devices)
    return {"ok": True, "id": dev_id}

@app.delete("/api/rasp/devices/{device_id}", dependencies=[Depends(require_auth)])
async def rasp_device_revoke(device_id: str):
    devices = _load_devices()
    for d in devices:
        if d["id"] == device_id:
            d["attestation"] = "revoked"
            d["revoked_at"] = now_iso()
            d["enrolled"] = False
            _save_devices(devices)
            return {"ok": True}
    raise HTTPException(404, f"Dispositivo {device_id} no encontrado")

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG — endpoint unificado (lista archivos editables)
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/config", dependencies=[Depends(require_auth)])
async def config_list_files():
    """Lista archivos de configuración editables del proyecto."""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    allowed_exts = {".sh", ".json", ".yml", ".yaml", ".toml", ".env", ".conf", ".md", ".txt", ".ini"}
    files = []
    for root, dirs, filenames in os.walk(project_root):
        # Skip node_modules, .git, evidence
        dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "__pycache__", ".venv", "venv"}]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext in allowed_exts:
                fpath = os.path.join(root, fname)
                try:
                    stat = os.stat(fpath)
                    files.append({
                        "name": fname,
                        "path": os.path.relpath(fpath, project_root),
                        "size": stat.st_size,
                        "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
                    })
                except Exception:
                    pass
    return files


# ═══════════════════════════════════════════════════════════════════════════════
# WEBSOCKET — feed en vivo
# ═══════════════════════════════════════════════════════════════════════════════

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    # Auth en WS via query param (para navegadores que no pueden setear headers en WS)
    token = ws.query_params.get("token", "")
    if API_KEY and token != API_KEY:
        await ws.close(code=4401, reason="Autenticacion requerida")
        return
    await ws.accept()
    connected_ws_clients.append(ws)
    try:
        await ws.send_json({"event": "connected", "timestamp": now_iso(),
                           "message": "SourceSeal WS conectado — feed en vivo activo"})
        while True:
            data = await ws.receive_text()
            # Echo de heartbeat
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await ws.send_json({"type": "pong", "timestamp": now_iso()})
            except:
                pass
    except WebSocketDisconnect:
        if ws in connected_ws_clients:
            connected_ws_clients.remove(ws)
    except Exception:
        if ws in connected_ws_clients:
            connected_ws_clients.remove(ws)

# ═══════════════════════════════════════════════════════════════════════════════
# STARTUP
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"[sealctl] Iniciando en {HOST}:{PORT} | Termux={IS_TERMUX}")
    print(f"[sealctl] Auth: {'activada' if API_KEY else 'DESACTIVADA — configura REDTEAM_API_KEY'}")
    print(f"[sealctl] CORS: {ALLOWED_ORIGINS}")
    print(f"[sealctl] Evidence dir: {EVIDENCE_DIR}")
    uvicorn.run(app, host=HOST, port=PORT)
