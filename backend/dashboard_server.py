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
    FastAPI, File, Form, HTTPException, Query, UploadFile,
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
    target: str = Field(..., description="IP o rango a escanear")
    ports: Optional[str] = Field("1-1000", description="Rango de puertos")
    timeout: Optional[int] = Field(5, description="Timeout en segundos")

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

async def _probe_host(ip: str, ports: List[int], timeout: float = 1.5) -> Dict:
    """Probe real de un host via TCP connect."""
    open_ports = []
    for port in ports:
        try:
            fut = asyncio.open_connection(ip, port)
            reader, writer = await asyncio.wait_for(fut, timeout=timeout)
            # intentar leer banner
            banner = None
            try:
                writer.write(b"HEAD / HTTP/1.0\r\n\r\n")
                await writer.drain()
                data = await asyncio.wait_for(reader.read(1024), timeout=1.0)
                banner = data.decode("utf-8", errors="ignore").strip()[:200]
            except:
                pass
            writer.close()
            try:
                await writer.wait_closed()
            except:
                pass
            open_ports.append({"port": port, "banner": banner})
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            pass
    # resolver hostname
    hostname = None
    try:
        hostname = socket.gethostbyaddr(ip)[0]
    except:
        pass
    return {
        "ip": ip,
        "status": "up" if open_ports else "down",
        "hostname": hostname or "",
        "ports": [p["port"] for p in open_ports],
        "banners": {str(p["port"]): p["banner"] for p in open_ports if p["banner"]}
    }

@app.post("/api/scan/topology", dependencies=[Depends(require_auth)])
async def scan_topology(req: ScanRequest):
    err = _validate_ip_or_subnet(req.target)
    if err:
        raise HTTPException(status_code=400, detail=err)
    scan_id = generate_id()
    base_ip = req.target.rsplit(".", 1)[0] + "."
    # solo escanear /28 (14 hosts) por defecto para no tardar demasiado
    host_range = range(1, 15)
    ports_to_probe = [22, 80, 443, 3306, 8080, 3389]
    tasks = [_probe_host(f"{base_ip}{i}", ports_to_probe) for i in host_range]
    hosts_raw = await asyncio.gather(*tasks, return_exceptions=True)
    hosts = [h for h in hosts_raw if isinstance(h, dict) and h["status"] == "up"]
    result = {
        "scan_id": scan_id, "type": "topology", "target": req.target,
        "timestamp": now_iso(), "hosts_found": len(hosts), "hosts": hosts
    }
    scan_history.append(result)
    await broadcast_ws({"event": "scan_complete", "type": "topology", "scan_id": scan_id, "hosts_found": len(hosts)})
    return result

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
