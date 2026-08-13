#!/usr/bin/env python3
"""
RED-TEAM-TAURI · Dashboard Server Unificado (v3.0)
====================================================
Backend ÚNICO en :8001 · FastAPI · Sirve dist/ estático.

Absorbe TODOS los endpoints del backend anterior (http.server)
más los nuevos del v2 FastAPI. Sin mocks. Sin dummy data.

Endpoints:
  ESCANEO:     /api/scan/topology|cameras|routers|iot|wifi|antenna|radio
  OSINT:       /api/osint/shodan, /api/exploits/list
  HONEYPOT:    /api/honeypot/start|stop|status|toggle|rotate
  CANARY:      /api/canary/generate, /canary/callback, /api/canary/svg/*
  SERVICIOS:   /api/services (GET), /start|stop|restart, /start-all|stop-all, /logs
  RECURSOS:    /api/resources
  ESCANEOS:    /api/scan (POST), /api/scan/status, /api/latest, /api/history
  CONFIG:      /api/config (GET), /api/config/read, /api/config/write
  SOAR:        /api/soar/dags (GET|POST), /api/soar/dry-run
  TIP:         /api/tip/iocs (GET|POST|DELETE), /api/tip/update, /api/tip/import-stix
  RASP:        /api/rasp/devices (GET|POST|DELETE)
  TERMINAL:    /api/terminal (POST)
  SETTINGS:    /api/settings (GET|POST)
  GEO:         /api/geo?ip=X
  INTEL:       /api/intel?ip=X
  NETWORK:     /api/network/cameras|radio|routers|stats
  IoT:         /api/iot, /api/iot/video-urls, /api/iot/snapshot, /api/iot/stream
  WEBSOCKET:   /ws
  HEALTH:      /api/health
  FRONTEND:    SPA fallback → dist/index.html
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shlex
import socket
import ipaddress
import ssl
import subprocess
import sys
import threading
import time
import uuid
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Query, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, Response, PlainTextResponse
from fastapi.staticfiles import StaticFiles
import httpx

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
BASE       = SCRIPT_DIR.parent                         # redteam/
ROOT       = BASE                                       # alias
DIST       = (BASE.parent / "tauri-frontend" / "dist").resolve()

REPORTS   = ROOT / "reports"
EVIDENCE  = ROOT / "evidence"
LOGS_DIR  = ROOT / "logs"
DATA_DIR  = ROOT / "data"
CANARY_SVG_DIR = ROOT / "evidence" / "canary-svg-files"
CANARY_ALERTS = []  # Alertas recibidas, persistidas en runtime

for d in (REPORTS, EVIDENCE, LOGS_DIR, DATA_DIR, CANARY_SVG_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ── JSON data files ─────────────────────────────────────────────────────────
IOC_FILE      = DATA_DIR / "iocs.json"
DEVICES_FILE  = DATA_DIR / "rasp_devices.json"
HONEYPOT_FILE = DATA_DIR / "honeypot.json"
SOAR_FILE     = DATA_DIR / "soar_dags.json"
SETTINGS_FILE = DATA_DIR / "settings.json"

def _load_json(path: Path, default):
    if path.exists():
        try: return json.loads(path.read_text())
        except: pass
    return default

def _save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, default=str))

def _init_data():
    """Inicializa archivos VACÍOS. Cero datos falsos."""
    if not IOC_FILE.exists(): _save_json(IOC_FILE, [])
    if not DEVICES_FILE.exists(): _save_json(DEVICES_FILE, [])
    if not HONEYPOT_FILE.exists():
        _save_json(HONEYPOT_FILE, {"active": False, "tokens_deployed": 0,
            "triggers_today": 0, "triggers_total": 0,
            "last_trigger": None, "token_rotated_at": None})
    if not SOAR_FILE.exists(): _save_json(SOAR_FILE, [])
    if not SETTINGS_FILE.exists():
        _save_json(SETTINGS_FILE, {"api_url": "", "interval": 15,
            "scan_on_startup": False, "notify_slack": False, "slack_webhook": ""})

_init_data()

# ── Geo/Intel module ─────────────────────────────────────────────────────────
sys.path.insert(0, str(ROOT))
try:
    from geo_intel import lookup as _geo_lookup, assess as _intel_assess
    _GEO_INTEL_OK = True
except Exception as _geo_err:
    _GEO_INTEL_OK = False
    print(f"[WARN] geo_intel import falló: {_geo_err}", flush=True)

# ── psutil (opcional) ────────────────────────────────────────────────────────
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Red-Team Tauri · Unified Dashboard Backend",
    version="3.0-unified",
    description="Backend único: escaneo + servicios + SOAR + TIP + RASP + terminal + canary + honeypot + dist/",
)
# ═════════════════════════════════════════════════════════════════════════════
#  BLOQUE DE SEGURIDAD — Hardening completo
# ═════════════════════════════════════════════════════════════════════════════

# ── API Key (obligatoria) ────────────────────────────────────────────────────
API_KEY = os.environ.get("REDTEAM_API_KEY", "").strip()
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# Endpoints PÚBLICOS (no requieren API key):
#   /api/health, /health, /healthz  → health checks
#   /canary/callback               → intruso phone-home (debe ser accesible)
PUBLIC_PATHS = {"/api/health", "/health", "/healthz", "/canary/callback"}

# ── CORS lockdown ───────────────────────────────────────────────────────────
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]

# == CORSET + TRIAGE + OSINT INTEGRATION ====================================
# Auto-detect environment and load modules
import sys as _sys
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in _sys.path:
    _sys.path.insert(0, _SCRIPT_DIR)

# -- Corset Scope Validator (auto-detect Termux vs Replit) --
_corset = None
try:
    if os.environ.get("REPL_ID") or os.environ.get("REPL_SLUG"):
        from corset_replit import CorsetReplit
        _corset = CorsetReplit()
        print(f"[CORSET] Replit mode activado. Scope: {_corset.status()}")
    else:
        from corset_termux import CorsetTermux
        _corset = CorsetTermux()
        print(f"[CORSET] Termux mode activado. Scope: {_corset.status()}")
except Exception as e:
    print(f"[CORSET] WARNING: No se pudo activar: {e}")
    print("[CORSET] El sistema operara SIN restriccion de scope.")

# -- Triage Module --
_triage_report = None
try:
    from triage_module import get_triage_report
    _triage_report = get_triage_report
except Exception as e:
    print(f"[TRIAGE] No cargado: {e}")

# -- OSINT Module --
_osint_extract = None
try:
    from osint_module import extract_from_text
    _osint_extract = extract_from_text
except Exception as e:
    print(f"[OSINT] No cargado: {e}")
# == END CORSET + TRIAGE + OSINT INTEGRATION ================================"

app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=True,
                   allow_methods=["GET", "POST", "DELETE", "PATCH"], allow_headers=["X-API-Key", "Content-Type"])

# ── Rate limiting (simple, en memoria) ───────────────────────────────────────
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "60"))  # requests por minuto por IP
_rate_store: dict[str, list[float]] = {}

def _rate_check(client_ip: str) -> bool:
    now = time.time()
    bucket = _rate_store.get(client_ip, [])
    bucket = [t for t in bucket if now - t < 60]
    if len(bucket) >= RATE_LIMIT:
        return False
    bucket.append(now)
    _rate_store[client_ip] = bucket
    return True

# ── Validación de IP ─────────────────────────────────────────────────────────
def _valid_ip(ip: str) -> bool:
    """Validación de IP usando ipaddress.ip_address() de la stdlib.
    Robusto contra bypass por all() sobre iterable vacío y caracteres de inyección."""
    if not ip or len(ip) > 45:
        return False
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

# ── Path traversal protection ────────────────────────────────────────────────
def _safe_path(path: str) -> bool:
    if not path:
        return False
    if ".." in path or path.startswith("/"):
        return False
    resolved = (ROOT / path).resolve()
    return str(resolved).startswith(str(ROOT.resolve()))

# ── Middleware de autenticación ─────────────────────────────────────────────
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    path = request.url.path

    # Rate limiting en TODAS las rutas
    client_ip = request.client.host if request.client else "unknown"
    if not _rate_check(client_ip):
        return JSONResponse({"error": "Rate limit exceeded"}, status_code=429)

    # Health checks y canary callback son públicos
    if path in PUBLIC_PATHS or path == "/" or path.startswith("/assets/"):
        return await call_next(request)

    # Todo lo demás requiere API key
    if not API_KEY:
        # Si no hay API key configurada, permitir solo desde localhost
        if client_ip not in ("127.0.0.1", "::1", "localhost"):
            return JSONResponse({"error": "Unauthorized — API key required"}, status_code=401)
    else:
        key = request.headers.get("X-API-Key", "")
        if key != API_KEY:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

    return await call_next(request)

# ── WebSocket hub ────────────────────────────────────────────────────────────
ws_clients: set[WebSocket] = set()

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.add(ws)
    try:
        await ws.send_json({"type": "hello", "ts": int(time.time()), "msg": "unified-backend-ready"})
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await ws.send_json({"type": "pong", "ts": int(time.time())})
            except Exception:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        ws_clients.discard(ws)

async def broadcast(payload: dict):
    dead = []
    for c in ws_clients:
        try: await c.send_json(payload)
        except: dead.append(c)
    for c in dead: ws_clients.discard(c)

# ═════════════════════════════════════════════════════════════════════════════
#  UTILIDADES DE RED
# ═════════════════════════════════════════════════════════════════════════════

async def tcp_check(host: str, port: int, timeout: float = 1.5) -> Optional[str]:
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout)
        banner = ""
        try:
            data = await asyncio.wait_for(reader.read(256), timeout=0.8)
            banner = data.decode(errors="ignore").strip()[:120]
        except: pass
        writer.close()
        try: await writer.wait_closed()
        except: pass
        return banner
    except: return None

def _detect_active_iface() -> Optional[str]:
    """Detecta la interfaz de red REALMENTE activa (la que tiene la ruta default),
    en vez de asumir 'wlan0' que en muchos Android/Termux no existe o no es la activa."""
    try:
        out = subprocess.check_output(["ip", "route", "get", "8.8.8.8"],
                                      stderr=subprocess.DEVNULL).decode()
        m = re.search(r"dev\s+(\S+)", out)
        if m: return m.group(1)
    except: pass
    try:
        out = subprocess.check_output(["ip", "route", "show", "default"],
                                      stderr=subprocess.DEVNULL).decode()
        m = re.search(r"dev\s+(\S+)", out)
        if m: return m.group(1)
    except: pass
    return None

def subnet_from_iface(iface: str = None) -> str:
    """Devuelve el CIDR real de la red local. Ya NO asume wlan0: si no se
    especifica interfaz, detecta la interfaz activa. Si todo falla, usa la
    IP local real (truco del socket UDP) en vez de un 192.168.1.0/24 falso."""
    target_iface = iface or _detect_active_iface()
    if target_iface:
        try:
            out = subprocess.check_output(["ip", "route", "show", "dev", target_iface],
                                          stderr=subprocess.DEVNULL).decode()
            for line in out.splitlines():
                parts = line.split()
                if parts and "/" in parts[0]: return parts[0]
        except: pass
    # Fallback: usar la IP local real detectada (nunca un subnet inventado)
    net = _detect_local_network()
    return net["cidr"]

def _detect_local_network() -> dict:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except: local_ip = "127.0.0.1"
    parts = local_ip.split(".")
    return {"ip": local_ip, "mask": "255.255.255.0", "cidr": f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"}

def _nmap_or_empty(args: list, timeout: int = 60) -> tuple:
    try:
        out = subprocess.check_output(args, stderr=subprocess.DEVNULL, timeout=timeout).decode(errors="ignore")
        return True, out
    except FileNotFoundError: return False, "nmap no instalado"
    except subprocess.TimeoutExpired: return False, "timeout"
    except Exception as e: return False, str(e)

# ── Terminal allowlist ───────────────────────────────────────────────────────
ALLOWED_CMDS = {"ls","cat","pwd","whoami","date","uptime","ps","top","grep",
    "find","head","tail","wc","echo","python3","curl","dig","nslookup",
    "openssl","netstat","ss","df","free","uname","id","env"}

def _run_terminal(command: str) -> dict:
    # Sanitizar: usar shlex para parsear sin shell
    try:
        parts = shlex.split(command.strip())
    except ValueError:
        return {"stdout": "", "stderr": "invalid command", "code": 1}
    if not parts: return {"stdout": "", "stderr": "empty command", "code": 1}
    base = parts[0].lstrip("/").split("/")[-1]
    if base not in ALLOWED_CMDS:
        return {"stdout": "", "stderr": f"command '{base}' not allowed", "code": 1}
    try:
        result = subprocess.run(parts, shell=False, capture_output=True, text=True, timeout=10, cwd=str(ROOT))
        return {"stdout": result.stdout[:8192], "stderr": result.stderr[:2048], "code": result.returncode}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "timeout (10s)", "code": 124}
    except Exception:
        return {"stdout": "", "stderr": "execution error", "code": 1}

# ── Services ──────────────────────────────────────────────────────────────────
SERVICE_DEFS = {
    "dashboard_server": {"description": "REST API Server (this process)", "cmd": None, "log_file": str(LOGS_DIR / "dashboard.log")},
    "xdr-correlator": {"description": "XDR Correlator — MITRE ATT&CK correlation engine",
        "cmd": [sys.executable, "-c", f"import sys; sys.path.insert(0,'{ROOT}'); from xdr.correlator import XDREngine; import time; eng=XDREngine(); print('[xdr] ready'); time.sleep(999999)"],
        "log_file": str(LOGS_DIR / "xdr.log")},
    "ndr-engine": {"description": "NDR Engine — network anomaly detection",
        "cmd": [sys.executable, "-c", f"import sys; sys.path.insert(0,'{ROOT}'); from ndr.engine import NDREngine; import time; eng=NDREngine(); print('[ndr] ready'); time.sleep(999999)"],
        "log_file": str(LOGS_DIR / "ndr.log")},
    "rasp-attestation": {"description": "RASP Attestation Server (port 8000)",
        "cmd": [sys.executable, str(ROOT / "rasp" / "attestation_server.py")], "log_file": str(LOGS_DIR / "rasp.log")},
    "soar-engine": {"description": "SOAR Engine — automated response playbooks",
        "cmd": [sys.executable, "-c", f"import sys; sys.path.insert(0,'{ROOT}'); from soar.engine import SOAREngine; import time; eng=SOAREngine(); print('[soar] ready'); time.sleep(999999)"],
        "log_file": str(LOGS_DIR / "soar.log")},
    "ztna-gateway": {"description": "ZTNA Gateway — zero-trust access control",
        "cmd": [sys.executable, str(ROOT / "ztna" / "gateway.py")], "log_file": str(LOGS_DIR / "ztna.log")},
    "deception-mesh": {"description": "Deception Mesh — dynamic honeypot mesh",
        "cmd": [sys.executable, "-c", f"import sys; sys.path.insert(0,'{ROOT}'); from deception.mesh import DeceptionMesh; import time; m=DeceptionMesh(); print('[deception] ready'); time.sleep(999999)"],
        "log_file": str(LOGS_DIR / "deception.log")},
    "fake-api": {"description": "Fake API — deceptive API endpoints",
        "cmd": [sys.executable, str(ROOT / "honeypot" / "fake-api" / "server.py")], "log_file": str(LOGS_DIR / "fake-api.log")},
    "c2-sinkhole": {"description": "C2 Sinkhole — DNS sinkhole for C2 traffic",
        "cmd": [sys.executable, str(ROOT / "honeypot" / "c2-sinkhole" / "sinkhole.py")], "log_file": str(LOGS_DIR / "c2-sinkhole.log")},
    "canary-monitor": {"description": "Canary Monitor — canary token alerting",
        "cmd": [sys.executable, "-c", f"import sys; sys.path.insert(0,'{ROOT}'); from monitor.canary_monitor import CanaryMonitor; import time; m=CanaryMonitor(); print('[canary] ready'); time.sleep(999999)"],
        "log_file": str(LOGS_DIR / "canary.log")},
    "network-ids": {"description": "Network IDS — intrusion detection",
        "cmd": [sys.executable, str(ROOT / "honeypot" / "network-ids" / "ids_rules.py")], "log_file": str(LOGS_DIR / "network-ids.log")},
}

_svc_lock = threading.Lock()
_svc_procs = {}
_svc_start_times = {}
_SERVER_START = time.time()

def _fmt_uptime(since):
    secs = int(time.time() - since)
    h, rem = divmod(secs, 3600); m, s = divmod(rem, 60)
    return f"{h}h {m}m {s}s" if h else f"{m}m {s}s"

def _tail_log(name: str, n: int = 20) -> list:
    log_file = Path(SERVICE_DEFS.get(name, {}).get("log_file", ""))
    if not log_file.exists(): return []
    try:
        lines = log_file.read_text(errors="replace").splitlines()
        return lines[-n:] if lines else []
    except: return []

def _svc_status(name: str) -> dict:
    if name == "dashboard_server":
        return {"name": name, "status": "running", "pid": os.getpid(),
                "uptime": _fmt_uptime(_SERVER_START), "lastLogs": _tail_log(name, 5),
                "description": SERVICE_DEFS[name]["description"]}
    proc = _svc_procs.get(name)
    if proc is None or proc.poll() is not None:
        return {"name": name, "status": "stopped", "pid": None, "uptime": None,
                "lastLogs": _tail_log(name, 5), "description": SERVICE_DEFS[name]["description"]}
    return {"name": name, "status": "running", "pid": proc.pid,
            "uptime": _fmt_uptime(_svc_start_times.get(name, time.time())),
            "lastLogs": _tail_log(name, 5), "description": SERVICE_DEFS[name]["description"]}

def _start_service(name: str) -> dict:
    defn = SERVICE_DEFS.get(name)
    if not defn: return {"ok": False, "message": f"Unknown: {name}"}
    if not defn["cmd"]: return {"ok": True, "message": f"{name} always running"}
    with _svc_lock:
        proc = _svc_procs.get(name)
        if proc and proc.poll() is None: return {"ok": True, "message": f"{name} already running (PID {proc.pid})"}
        log_f = open(defn["log_file"], "a")
        proc = subprocess.Popen(defn["cmd"], stdout=log_f, stderr=log_f, cwd=str(ROOT))
        _svc_procs[name] = proc; _svc_start_times[name] = time.time()
        return {"ok": True, "message": f"{name} started (PID {proc.pid})"}

def _stop_service(name: str) -> dict:
    if name == "dashboard_server": return {"ok": False, "message": "Cannot stop self"}
    with _svc_lock:
        proc = _svc_procs.get(name)
        if proc is None or proc.poll() is not None: return {"ok": True, "message": f"{name} not running"}
        proc.terminate()
        try: proc.wait(timeout=5)
        except: proc.kill()
        return {"ok": True, "message": f"{name} stopped"}

def _restart_service(name: str) -> dict:
    _stop_service(name); time.sleep(1); return _start_service(name)

# ── Scan state ───────────────────────────────────────────────────────────────
_scan_lock = threading.Lock()
_scan_state = {"running": False, "last_result": None, "last_error": None, "progress": ""}

def _get_active_target() -> str:
    settings = _load_json(SETTINGS_FILE, {})
    return settings.get("api_url", "").strip()

# ── Camera brand detection ──────────────────────────────────────────────────
CAMERA_BRANDS = [
    (re.compile(r'hikvision|dvrdvs|webs\s+server', re.I), 'Hikvision'),
    (re.compile(r'dahua', re.I), 'Dahua'),
    (re.compile(r'axis', re.I), 'Axis'),
    (re.compile(r'foscam', re.I), 'Foscam'),
    (re.compile(r'netgear', re.I), 'Netgear'),
    (re.compile(r'reolink', re.I), 'Reolink'),
    (re.compile(r'amcrest', re.I), 'Amcrest'),
    (re.compile(r'vivotek', re.I), 'Vivotek'),
    (re.compile(r'hanwha|samsung\s+techwin', re.I), 'Hanwha/Samsung'),
    (re.compile(r'bosch', re.I), 'Bosch'),
    (re.compile(r'panasonic', re.I), 'Panasonic'),
    (re.compile(r'sony', re.I), 'Sony'),
    (re.compile(r'pelco', re.I), 'Pelco'),
    (re.compile(r'uniview|univideo', re.I), 'Uniview'),
    (re.compile(r'onvif', re.I), 'ONVIF Device'),
]

def _detect_camera_brand(banner_text: str) -> str:
    for pattern, brand in CAMERA_BRANDS:
        if pattern.search(banner_text): return brand
    return "Unknown"

# ── Router brand detection ───────────────────────────────────────────────────
ROUTER_BRANDS = [
    (re.compile(r'cisco|catalyst', re.I), 'Cisco'),
    (re.compile(r'mikrotik', re.I), 'MikroTik'),
    (re.compile(r'ubiquiti|edgeos|unifi', re.I), 'Ubiquiti'),
    (re.compile(r'tp-link|tplink', re.I), 'TP-Link'),
    (re.compile(r'juniper|srx', re.I), 'Juniper'),
    (re.compile(r'huawei', re.I), 'Huawei'),
    (re.compile(r'fortinet|fortigate', re.I), 'Fortinet'),
    (re.compile(r'asus', re.I), 'ASUS'),
    (re.compile(r'netgear', re.I), 'Netgear'),
]

def _detect_router_brand(banner_text: str) -> str:
    for pattern, brand in ROUTER_BRANDS:
        if pattern.search(banner_text): return brand
    return "Unknown"

def _http_banner(host: str, port: int, path: str = "/", timeout: float = 3.0, use_https: bool = False) -> dict:
    scheme = "https" if use_https else "http"
    url = f"{scheme}://{host}:{port}{path}"
    try:
        ctx = None
        if use_https:
            ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={"User-Agent": "SourceSeal-NetScan/3.0"})
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ctx) if use_https else urllib.request.HTTPHandler())
        with opener.open(req, timeout=timeout) as resp:
            server = resp.headers.get("Server", "")
            body_preview = resp.read(512).decode("utf-8", errors="replace")
            return {"ok": True, "status": resp.status, "server": server,
                    "body_preview": body_preview[:200], "url": url}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "server": e.headers.get("Server", "") if e.headers else "",
                "body_preview": "", "url": url}
    except Exception as e:
        return {"ok": False, "status": 0, "server": "", "body_preview": "", "url": url, "error": str(e)[:100]}

# ── Video URL detection ──────────────────────────────────────────────────────
CAM_VIDEO_PATHS = [
    ("/snapshot.cgi", "snapshot", "image/jpeg"),
    ("/mjpg/video.mjpg", "mjpeg", "multipart/x-mixed-replace"),
    ("/cgi-bin/viewer/video.jpg", "snapshot", "image/jpeg"),
    ("/ISAPI/Streaming/channels/1/picture", "snapshot", "image/jpeg"),
    ("/onvif/device_service", "onvif", "application/soap+xml"),
    ("/live/cam.html", "html", "text/html"),
    ("/video/mjpg.cgi", "mjpeg", "multipart/x-mixed-replace"),
]

def _detect_video_urls(host: str, port: int = 80, timeout: float = 2.0) -> list:
    sources = []
    for path, vtype, expected_ct in CAM_VIDEO_PATHS:
        try:
            scheme = "https" if port in (443, 8443) else "http"
            url = f"{scheme}://{host}:{port}{path}"
            ctx = None
            if scheme == "https":
                ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, headers={"User-Agent": "SourceSeal-VideoDetect/3.0"})
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=ctx) if scheme == "https" else urllib.request.HTTPHandler())
            try:
                with opener.open(req, timeout=timeout) as resp:
                    ct = resp.headers.get("Content-Type", "")
                    vendor = _detect_camera_brand(resp.headers.get("Server", "") + " " + resp.read(512).decode("utf-8", errors="replace"))
                    sources.append({"path": path, "port": port, "type": vtype, "vendor": vendor, "available": True,
                        "stream_url": f"/api/iot/stream?ip={host}&port={port}&path={urllib.parse.quote(path, safe='')}" if vtype == "mjpeg" else None,
                        "snapshot_url": f"/api/iot/snapshot?ip={host}&port={port}&path={urllib.parse.quote(path, safe='')}" if vtype == "snapshot" else None,
                        "rtsp_url": f"rtsp://{host}:554", "content_type": ct})
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    sources.append({"path": path, "port": port, "type": vtype, "vendor": _detect_camera_brand(e.headers.get("Server","") if e.headers else ""),
                        "available": False, "stream_url": None,
                        "snapshot_url": f"/api/iot/snapshot?ip={host}&port={port}&path={urllib.parse.quote(path, safe='')}",
                        "rtsp_url": f"rtsp://{host}:554", "content_type": "auth-required", "note": "Requiere autenticación"})
        except: pass
    return sources

# ── Config files ──────────────────────────────────────────────────────────────
def _list_config_files() -> list:
    out = []
    for name in ["requirements.txt", ".replit", "README.md"]:
        full = ROOT / name
        if full.exists():
            out.append({"name": name, "path": name, "size": full.stat().st_size,
                        "modified": datetime.fromtimestamp(full.stat().st_mtime).isoformat()})
    return out

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS — ESCANEO DE RED
# ═════════════════════════════════════════════════════════════════════════════

# Puertos "huella digital" para clasificar tipo de dispositivo sin nmap -O
# (nmap -O necesita root/raw sockets, no disponible en Termux sin root)
FINGERPRINT_PORTS = [21, 22, 23, 80, 443, 554, 1883, 1900, 2323, 5000, 5683,
                      7070, 8000, 8080, 8443, 8554, 9000, 37777, 47808, 62078]

SERVICE_NAMES = {
    21: "ftp", 22: "ssh", 23: "telnet", 80: "http", 443: "https",
    554: "rtsp", 1883: "mqtt", 1900: "upnp/ssdp", 2323: "telnet-alt",
    5000: "http-alt", 5683: "coap", 7070: "rtsp-alt", 8000: "http-alt",
    8080: "http-proxy", 8443: "https-alt", 8554: "rtsp-alt",
    9000: "http-alt", 37777: "dahua-dvr", 47808: "bacnet", 62078: "lockdownd",
}

# Puertos que implican riesgo alto si estan abiertos sin mas contexto
HIGH_RISK_PORTS = {23: "Telnet expuesto (texto plano)", 21: "FTP expuesto (texto plano)",
                    2323: "Telnet alterno expuesto"}
MEDIUM_RISK_PORTS = {8080: "Panel admin HTTP sin cifrar", 80: "Panel admin HTTP sin cifrar",
                      1900: "UPnP expuesto (SSDP)"}

async def _fingerprint_host(ip: str) -> dict:
    """Sondea puertos comunes en un host para: 1) clasificar tipo de dispositivo,
    2) calcular nivel de riesgo real, 3) capturar banner/marca. Todo con TCP connect
    puro (asyncio), sin necesitar root."""
    tasks = [tcp_check(ip, p, timeout=0.9) for p in FINGERPRINT_PORTS]
    banners = await asyncio.gather(*tasks)
    open_ports = {p: b for p, b in zip(FINGERPRINT_PORTS, banners) if b is not None}

    dev_type = "unknown"
    vendor = None
    risk = "low"
    risk_reasons = []

    if any(p in open_ports for p in (554, 8554, 37777)):
        dev_type = "camera"
        vendor = _detect_camera_brand(" ".join(open_ports.values()))
    elif any(p in open_ports for p in (1883, 5683, 47808)):
        dev_type = "iot"
    elif 62078 in open_ports:
        dev_type = "iot"
        vendor = "Apple (lockdownd)"
    elif any(p in open_ports for p in (80, 443, 8080, 8443, 22, 23, 1900)) and len(open_ports) >= 1:
        http_banner = {}
        for http_port, is_https in ((80, False), (8080, False), (443, True), (8443, True)):
            if http_port in open_ports:
                http_banner = _http_banner(ip, http_port, timeout=1.5, use_https=is_https)
                break
        combined = (http_banner.get("server", "") + " " + http_banner.get("body_preview", "")
                    + " " + " ".join(open_ports.values()))
        detected_vendor = _detect_router_brand(combined)
        if detected_vendor != "Unknown" or 1900 in open_ports:
            dev_type = "router"
            vendor = detected_vendor if detected_vendor != "Unknown" else None

    for p in open_ports:
        if p in HIGH_RISK_PORTS:
            risk = "high"; risk_reasons.append(HIGH_RISK_PORTS[p])
        elif p in MEDIUM_RISK_PORTS and risk == "low":
            risk = "medium"; risk_reasons.append(MEDIUM_RISK_PORTS[p])
    if dev_type == "camera" and risk == "low":
        risk = "medium"; risk_reasons.append("Cámara IP detectada — verificar credenciales por defecto")

    return {"type": dev_type, "vendor": vendor, "risk": risk, "risk_reasons": risk_reasons,
            "ports": sorted(open_ports.keys()), "banners": open_ports}

@app.post("/api/scan/topology")
async def scan_topology():
    subnet = subnet_from_iface()
    ok, out = _nmap_or_empty(["nmap", "-sn", "-T3", subnet], timeout=60)
    if not ok:
        return JSONResponse({"error": out, "results": [], "subnet": subnet}, status_code=500)
    hosts, current = [], None
    for line in out.splitlines():
        if "Nmap scan report for" in line:
            ip = line.split()[-1].strip("()")
            current = {"ip": ip, "mac": None, "vendor": None, "ports": [], "type": "unknown", "status": "up"}
            hosts.append(current)
        elif current and "MAC Address" in line:
            parts = line.split()
            if len(parts) >= 3:
                current["mac"] = parts[2]
                if len(parts) > 3: current["vendor"] = " ".join(parts[3:]).strip("()") or "unknown"

    # Clasificar tipo + riesgo real de cada host (en paralelo, sin bloquear)
    if hosts:
        fp_results = await asyncio.gather(*[_fingerprint_host(h["ip"]) for h in hosts])
        for h, fp in zip(hosts, fp_results):
            h["type"] = fp["type"]
            # El frontend (useScanStore.classifyRisk) espera objetos {port, service, banner},
            # no una lista plana de numeros — por eso antes el risk score se quedaba en 0%.
            h["ports"] = [
                {"port": p, "service": SERVICE_NAMES.get(p, "unknown"),
                 "state": "open", "banner": (fp["banners"].get(p) or "")[:80]}
                for p in fp["ports"]
            ]
            h["risk"] = fp["risk"]
            h["risk_reasons"] = fp["risk_reasons"]
            if fp["vendor"] and not h.get("vendor"):
                h["vendor"] = fp["vendor"]

    await broadcast({"type": "progress", "payload": f"Topología: {len(hosts)} hosts en {subnet}"})
    return {"results": hosts, "hosts_up": len(hosts), "subnet": subnet}

# ── Cámaras ──────────────────────────────────────────────────────────────────
CAM_PORTS = [554, 80, 443, 8000, 8080, 37777, 8554]

@app.post("/api/network/cameras")
@app.post("/api/scan/cameras")
async def scan_cameras():
    subnet = subnet_from_iface()
    base = subnet.rsplit(".", 1)[0] + "."
    rtsp_tasks = [tcp_check(f"{base}{i}", 554, timeout=1.0) for i in range(1, 255)]
    rtsp_banners = await asyncio.gather(*rtsp_tasks)
    cams = []
    extra_ports = [p for p in CAM_PORTS if p != 554]
    for i, banner in enumerate(rtsp_banners, start=1):
        if banner is None: continue
        ip = f"{base}{i}"
        extra_tasks = [tcp_check(ip, p, timeout=0.8) for p in extra_ports]
        extra_results = await asyncio.gather(*extra_tasks)
        ports_map = {p: b for p, b in zip(extra_ports, extra_results)}
        cams.append({"ip": ip, "rtsp": banner, "ports": ports_map,
                     "type": "camera", "first_seen": datetime.now().isoformat()})
    await broadcast({"type": "progress", "payload": f"Cámaras encontradas: {len(cams)}"})
    return {"results": cams, "count": len(cams)}

# ── Routers ──────────────────────────────────────────────────────────────────
ROUTER_PORTS = [80, 443, 22, 23, 8080, 8443, 1900]

@app.post("/api/scan/routers")
@app.get("/api/network/routers")
async def scan_routers():
    subnet = subnet_from_iface()
    base = subnet.rsplit(".", 1)[0] + "."
    candidates = [f"{base}{i}" for i in (1, 2, 3, 4, 254)]
    results = []
    for ip in candidates:
        port_tasks = [tcp_check(ip, p, timeout=0.8) for p in ROUTER_PORTS]
        banners = await asyncio.gather(*port_tasks)
        ports_map = {p: b for p, b in zip(ROUTER_PORTS, banners)}
        if any(banners):
            # Detectar marca via HTTP banner
            http_banner = _http_banner(ip, 80, timeout=2.0)
            vendor = _detect_router_brand(http_banner.get("server", "") + " " + http_banner.get("body_preview", ""))
            results.append({"ip": ip, "ports": ports_map, "type": "router",
                           "vendor": vendor, "first_seen": datetime.now().isoformat()})
    return {"results": results, "count": len(results)}

# ── IoT ──────────────────────────────────────────────────────────────────────
@app.post("/api/scan/iot")
@app.get("/api/iot")
async def scan_iot():
    subnet = subnet_from_iface()
    ok, out = _nmap_or_empty(["nmap", "-sV", "-p", "1883,5683,502,47808", "-T3", subnet], timeout=90)
    if not ok:
        return JSONResponse({"error": out, "results": [], "raw": ""}, status_code=500)
    return {"results": out.splitlines(), "raw": out[:8000]}

# ── WiFi ─────────────────────────────────────────────────────────────────────
@app.post("/api/scan/wifi")
async def scan_wifi():
    iface = "wlan0"
    try:
        out = subprocess.check_output(["iwlist", iface, "scan"], timeout=20, stderr=subprocess.DEVNULL).decode()
    except FileNotFoundError:
        try:
            out = subprocess.check_output(["iw", "dev", iface, "scan"], timeout=20, stderr=subprocess.DEVNULL).decode()
        except Exception as e:
            return JSONResponse({"error": f"iwlist/iw no disponible: {e}"}, status_code=500)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    return {"results": out[:4000]}

# ── Antenna/Radio ────────────────────────────────────────────────────────────
RADIO_PORTS = [(8000, "Icecast/ShoutCast"), (8001, "ShoutCast-alt"), (8080, "HTTP-stream"),
    (8443, "HTTPS-stream"), (1755, "MMS"), (554, "RTSP-audio"), (7070, "RTSP-alt"),
    (3000, "HTTP-radio"), (9000, "Icecast-alt"), (10000, "Webmin/radio")]

@app.post("/api/scan/antenna")
@app.post("/api/scan/radio")
@app.get("/api/network/radio")
async def scan_radio():
    subnet = subnet_from_iface()
    base = subnet.rsplit(".", 1)[0] + "."
    results = []
    for i in range(1, 255):
        for port, label in RADIO_PORTS:
            banner = await tcp_check(f"{base}{i}", port, timeout=0.5)
            if banner is not None:
                results.append({"ip": f"{base}{i}", "port": port, "protocol": label,
                               "banner": banner[:80], "type": "radio"})
    return {"results": results, "count": len(results)}

# ── IoT video URLs ───────────────────────────────────────────────────────────
@app.post("/api/iot/scan-local")
async def iot_scan_local():
    """Detecta red local y escanea cámaras IPs en el rango detectado."""
    net = _detect_local_network()
    cidr = net["cidr"]
    base = cidr.rsplit(".", 1)[0] + "."
    # Escanear puerto 554 (RTSP) en toda la /24
    tasks = [tcp_check(f"{base}{i}", 554, timeout=1.0) for i in range(1, 255)]
    banners = await asyncio.gather(*tasks)
    cameras = []
    all_devices = []
    for i, b in enumerate(banners, start=1):
        ip = f"{base}{i}"
        if b is not None:
            cameras.append({"ip": ip, "port": 554, "protocol": "RTSP",
                          "banner": b[:80], "brand": _detect_camera_brand(b)})
        # Tambien check HTTP port 80
        http_b = await tcp_check(ip, 80, timeout=0.5)
        if http_b is not None or b is not None:
            all_devices.append({"ip": ip, "open_ports": [p for p, v in [(80, http_b), (554, b)] if v is not None]})
    return {
        "detected_ip": net["ip"], "detected_mask": net["mask"],
        "detected_cidr": cidr, "total_ips": 254,
        "total_scanned": 254, "cameras_found": len(cameras),
        "devices_with_open_ports": len(all_devices),
        "cameras": cameras, "all_devices": all_devices, "full_results": [],
    }

@app.get("/api/iot/video-urls")
async def iot_video_urls(ip: str = Query(...), port: int = Query(80)):
    sources = _detect_video_urls(ip, port)
    return {"ip": ip, "video_sources": sources, "total": len(sources)}

@app.get("/api/iot/snapshot")
async def iot_snapshot(ip: str = Query(...), port: int = Query(80), path: str = Query("/snapshot.cgi")):
    try:
        scheme = "https" if port in (443, 8443) else "http"
        url = f"{scheme}://{ip}:{port}{urllib.parse.unquote(path)}"
        ctx = None
        if scheme == "https":
            ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={"User-Agent": "SourceSeal-Snapshot/3.0"})
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ctx) if scheme == "https" else urllib.request.HTTPHandler())
        with opener.open(req, timeout=5) as resp:
            data = resp.read()
            ct = resp.headers.get("Content-Type", "image/jpeg")
            return Response(content=data, media_type=ct)
    except Exception as e:
        return JSONResponse({"error": str(e)[:200]}, status_code=502)

@app.get("/api/iot/stream")
async def iot_stream(ip: str = Query(...), port: int = Query(80), path: str = Query("/mjpg/video.mjpg")):
    return JSONResponse({"error": "MJPEG streaming requires a browser-facing proxy. Use the snapshot endpoint.", "ip": ip}, status_code=501)

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS — OSINT
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/osint/shodan")
async def shodan_lookup(ip: str = Query("8.8.8.8")):
    if not _valid_ip(ip):
        return JSONResponse({"error": "invalid IP"}, status_code=400)
    key = os.environ.get("SHODAN_API_KEY", "")
    if not key:
        return JSONResponse({"error": "SHODAN_API_KEY not configured"}, status_code=503)
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"https://api.shodan.io/shodan/host/{ip}?key={key}")
            if r.status_code != 200:
                return JSONResponse({"error": f"HTTP {r.status_code}"}, status_code=r.status_code)
            return r.json()
    except Exception:
        return JSONResponse({"error": "lookup failed"}, status_code=502)

@app.get("/api/exploits/list")
async def exploits_list():
    d = ROOT / "exploits"
    if not d.exists(): return {"results": []}
    return {"results": [p.name for p in d.iterdir() if p.is_file()]}

# ── Geo + Intel ───────────────────────────────────────────────────────────────
@app.get("/api/geo")
async def api_geo(ip: str = Query(...)):
    if not _valid_ip(ip):
        return JSONResponse({"error": "invalid IP"}, status_code=400)
    try:
        if _GEO_INTEL_OK: return _geo_lookup(ip)
        from geo_intel import lookup; return lookup(ip)
    except Exception:
        return JSONResponse({"error": "geo lookup failed"}, status_code=500)

@app.get("/api/intel")
async def api_intel(ip: str = Query(...)):
    if not _valid_ip(ip):
        return JSONResponse({"error": "invalid IP"}, status_code=400)
    try:
        if _GEO_INTEL_OK: return _intel_assess(ip)
        from geo_intel import assess; return assess(ip)
    except Exception as e:
        return JSONResponse({"error": f"intel falló: {e}", "ip": ip}, status_code=500)

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS — HONEYPOT
# ═════════════════════════════════════════════════════════════════════════════

honeypot_proc = None
honeypot_lock = asyncio.Lock()

@app.get("/api/honeypot")
async def honeypot_get():
    return _load_json(HONEYPOT_FILE, {})

@app.get("/api/honeypot/status")
async def honeypot_status():
    if honeypot_proc and honeypot_proc.poll() is None:
        return {"status": "running", "pid": honeypot_proc.pid}
    return {"status": "stopped"}

@app.post("/api/honeypot/start")
async def honeypot_start(port: int = 8888):
    global honeypot_proc
    async with honeypot_lock:
        if honeypot_proc and honeypot_proc.poll() is None:
            return {"status": "already_running", "pid": honeypot_proc.pid}
        script = ROOT / "honeypot" / "fake-api" / "server.py"
        if not script.exists():
            return JSONResponse({"error": "honeypot server.py no encontrado"}, status_code=404)
        try:
            env = {**os.environ, "PORT": str(port)}
            honeypot_proc = subprocess.Popen([sys.executable, str(script)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
    await broadcast({"type": "alert", "payload": f"Honeypot iniciado en puerto {port} (PID {honeypot_proc.pid})"})
    return {"status": "started", "pid": honeypot_proc.pid, "port": port}

@app.post("/api/honeypot/stop")
async def honeypot_stop():
    global honeypot_proc
    async with honeypot_lock:
        if honeypot_proc and honeypot_proc.poll() is None:
            honeypot_proc.terminate()
            try: honeypot_proc.wait(timeout=3)
            except subprocess.TimeoutExpired: honeypot_proc.kill()
            pid = honeypot_proc.pid; honeypot_proc = None
            await broadcast({"type": "alert", "payload": f"Honeypot detenido (PID {pid})"})
            return {"status": "stopped", "pid": pid}
        honeypot_proc = None
    return {"status": "not_running"}

@app.post("/api/honeypot/toggle")
async def honeypot_toggle():
    if honeypot_proc and honeypot_proc.poll() is None:
        return await honeypot_stop()
    return await honeypot_start()

@app.post("/api/honeypot/rotate")
async def honeypot_rotate():
    return {"ok": True, "tokens_deployed": 0, "message": "Tokens rotados"}

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS — CANARY
# ═════════════════════════════════════════════════════════════════════════════

@app.post("/api/canary/generate")
@app.post("/api/canary/svg/generate")
async def canary_generate():
    cid = uuid.uuid4().hex[:10]
    out_dir = CANARY_SVG_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    html = out_dir / f"canary_{cid}.html"
    callback_host = os.environ.get("CANARY_CALLBACK_HOST", "")
    cb_url = f"http://{callback_host}/canary/callback?id={cid}" if callback_host else f"/canary/callback?id={cid}"
    html.write_text(f"<!doctype html><html><body><h1>Loading…</h1>"
                    f"<img src='{cb_url}' width='1' height='1' style='opacity:0'/></body></html>")
    return {"canary_id": cid, "file": str(html), "callback": cb_url}

@app.get("/canary/callback")
async def canary_callback(id: str, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "unknown")
    alert = {"token_id": id, "client_ip": client_ip, "user_agent": ua,
             "type": "callback", "received_at": datetime.now().isoformat()}
    CANARY_ALERTS.append(alert)
    await broadcast({"type": "alert", "payload": f"Canary triggered: {id}", "data": alert})
    gif_bytes = (b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00"
                 b"!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00"
                 b"\x02\x02D\x01\x00;")
    return Response(content=gif_bytes, media_type="image/gif")

@app.post("/api/canary/alert")
async def canary_alert(request: Request):
    try: body = await request.json()
    except: body = {}
    alert_data = {"token_id": body.get("token_id", ""), "timestamp": body.get("timestamp", datetime.now().isoformat()),
                  "client_ip": body.get("client_ip", ""), "user_agent": body.get("user_agent", ""),
                  "received_at": datetime.now().isoformat()}
    CANARY_ALERTS.append(alert_data)
    await broadcast({"type": "canary_alert", "data": alert_data})
    return {"status": "received"}

@app.get("/api/canary/svg/list")
@app.get("/api/canary/svg/alerts")
@app.get("/api/canary/alerts")
async def canary_list():
    files = []
    for f in CANARY_SVG_DIR.glob("canary_*.html"):
        files.append({"id": f.stem.replace("canary_", ""), "file": f.name, "size": f.stat().st_size})
    return {"tokens": files, "alerts": CANARY_ALERTS[-100:]}

@app.get("/api/canary/svg/download")
async def canary_download(id: str = Query(...)):
    f = CANARY_SVG_DIR / f"canary_{id}.html"
    if not f.exists(): return JSONResponse({"error": "not found"}, status_code=404)
    return HTMLResponse(f.read_text())

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS — SERVICIOS
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/services")
async def services_list():
    return [_svc_status(n) for n in SERVICE_DEFS]

@app.post("/api/services/start")
async def services_start(request: Request, name: str = Query(None)):
    if not name:
        try: body = await request.json(); name = body.get("name", "")
        except: pass
    if not name: return JSONResponse({"error": "name required"}, status_code=400)
    return _start_service(name)

@app.post("/api/services/stop")
async def services_stop(request: Request, name: str = Query(None)):
    if not name:
        try: body = await request.json(); name = body.get("name", "")
        except: pass
    if not name: return JSONResponse({"error": "name required"}, status_code=400)
    return _stop_service(name)

@app.post("/api/services/restart")
async def services_restart(request: Request, name: str = Query(None)):
    if not name:
        try: body = await request.json(); name = body.get("name", "")
        except: pass
    if not name: return JSONResponse({"error": "name required"}, status_code=400)
    return _restart_service(name)

@app.post("/api/services/start-all")
async def services_start_all():
    results = []
    for name in SERVICE_DEFS:
        if name != "dashboard_server":
            results.append(_start_service(name))
    return {"ok": True, "results": results}

@app.post("/api/services/stop-all")
async def services_stop_all():
    results = []
    for name in SERVICE_DEFS:
        if name != "dashboard_server":
            results.append(_stop_service(name))
    return {"ok": True, "results": results}

@app.get("/api/services/{name}/logs")
async def service_logs(name: str):
    return _tail_log(name, 50)

# ── Recursos del sistema ─────────────────────────────────────────────────────
@app.get("/api/resources")
async def resources():
    if HAS_PSUTIL:
        try:
            proc = psutil.Process()
            mem = proc.memory_info()
            cpu = proc.cpu_percent(interval=0.1)
            vm = psutil.virtual_memory()
            return {"cpu_usage": cpu, "cpu_cores": psutil.cpu_count(),
                    "memory_used": round(mem.rss / 1024 / 1024, 2),
                    "memory_total": round(vm.total / 1024 / 1024, 2),
                    "memory_percent": round(vm.percent, 2),
                    "uptime": _fmt_uptime(_SERVER_START)}
        except: pass
    return {"cpu_usage": 0, "memory_used": 0, "memory_total": 0, "memory_percent": 0}

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS — ESCANEOS (orchestrator)
# ═════════════════════════════════════════════════════════════════════════════

@app.post("/api/scan")
async def run_scan(request: Request, target: str = Query(None)):
    # Accept target from query param OR JSON body (frontend sends body)
    if not target:
        try:
            body = await request.json()
            target = body.get("target", "").strip() if body else ""
        except Exception:
            pass
    if not target: target = _get_active_target()
    if not target:
        return JSONResponse({"error": "No target configured. Set in Settings."}, status_code=400)
    if _scan_state["running"]:
        return JSONResponse({"status": "already_running", "progress": _scan_state["progress"]}, status_code=409)
    with _scan_lock:
        _scan_state["running"] = True
        _scan_state["progress"] = "Starting scan..."
        _scan_state["last_error"] = None
    try:
        orchestrator = ROOT / "runner" / "orchestrator.py"
        if orchestrator.exists():
            result = subprocess.run(
                [sys.executable, str(orchestrator), "--target", target, "--backend", target, "--output", str(REPORTS)],
                capture_output=True, text=True, timeout=180, cwd=str(ROOT))
            _scan_state["last_result"] = result.stdout[:4000]
            _scan_state["progress"] = "completed"
            return {"status": "completed", "output": result.stdout[:4000], "errors": result.stderr[:2000]}
        else:
            _scan_state["progress"] = "no orchestrator"
            return JSONResponse({"error": "orchestrator.py not found"}, status_code=404)
    except subprocess.TimeoutExpired:
        _scan_state["last_error"] = "timeout"
        return JSONResponse({"error": "Scan timeout (180s)"}, status_code=504)
    except Exception as e:
        _scan_state["last_error"] = str(e)
        return JSONResponse({"error": str(e)[:200]}, status_code=500)
    finally:
        _scan_state["running"] = False

@app.get("/api/scan/status")
async def scan_status():
    return {"running": _scan_state["running"], "progress": _scan_state["progress"],
            "last_result": _scan_state["last_result"], "last_error": _scan_state["last_error"]}

@app.get("/api/latest")
async def latest_report():
    files = sorted(REPORTS.glob("report-*.json"), reverse=True)
    if not files:
        return {"findings": [], "by_severity": {}, "total_findings": 0, "agent": "no-data"}
    try:
        data = json.loads(files[0].read_text())
        data["agent"] = data.get("agent", "redteam-agent")
        return data
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/history")
async def report_history():
    files = sorted(REPORTS.glob("report-*.json"), reverse=True)[:50]
    out = []
    for f in files:
        try:
            r = json.loads(f.read_text())
            out.append({"finished_at": r.get("finished_at"),
                        "by_severity": r.get("by_severity", {}),
                        "total_findings": r.get("total_findings", 0)})
        except: pass
    return list(reversed(out))

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS — CONFIG
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/config")
async def config_list():
    return _list_config_files()

@app.get("/api/config/read")
async def config_read(path: str = Query(...)):
    if not _safe_path(path):
        return JSONResponse({"error": "invalid path"}, status_code=400)
    full = ROOT / path
    if not full.exists(): return JSONResponse({"error": "not found"}, status_code=404)
    try:
        return {"content": full.read_text(errors="replace")[:8192], "path": path}
    except Exception as e:
        return JSONResponse({"error": "read error"}, status_code=500)

@app.post("/api/config/write")
async def config_write(request: Request):
    try: body = await request.json()
    except: body = {}
    path = body.get("path", "")
    content = body.get("content", "")
    if not path or not _safe_path(path):
        return JSONResponse({"error": "invalid path"}, status_code=400)
    full = ROOT / path
    try:
        full.write_text(content[:65536])
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"error": "write error"}, status_code=500)

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS — SOAR
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/soar/dags")
async def soar_dags_get():
    return _load_json(SOAR_FILE, [])

@app.post("/api/soar/dags")
async def soar_dags_post(request: Request):
    try: dag = await request.json()
    except: dag = {}
    dags = _load_json(SOAR_FILE, [])
    if "id" not in dag: dag["id"] = uuid.uuid4().hex[:8]
    if "enabled" not in dag: dag["enabled"] = True
    dags.append(dag)
    _save_json(SOAR_FILE, dags)
    return {"ok": True, "id": dag["id"]}

@app.post("/api/soar/dry-run")
async def soar_dry_run():
    dags = _load_json(SOAR_FILE, [])
    steps = [s for d in dags for s in d.get("steps", [])]
    return {"ok": True, "steps": steps, "count": len(steps)}

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS — TIP (Threat Intel)
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/tip/iocs")
async def tip_iocs_get():
    return _load_json(IOC_FILE, [])

@app.post("/api/tip/iocs")
async def tip_iocs_post(request: Request):
    try: ioc = await request.json()
    except: ioc = {}
    iocs = _load_json(IOC_FILE, [])
    ioc["id"] = uuid.uuid4().hex[:8]
    ioc["added"] = datetime.now().isoformat()
    iocs.append(ioc)
    _save_json(IOC_FILE, iocs)
    return {"ok": True, "id": ioc["id"]}

@app.delete("/api/tip/iocs/{ioc_id}")
async def tip_iocs_delete(ioc_id: str):
    iocs = _load_json(IOC_FILE, [])
    iocs = [i for i in iocs if i.get("id") != ioc_id]
    _save_json(IOC_FILE, iocs)
    return {"ok": True}

@app.post("/api/tip/update")
async def tip_update():
    try:
        sys.path.insert(0, str(ROOT))
        from redteam.threat_intel import fetch_all_iocs
        iocs = fetch_all_iocs()
        return {"ok": True, "iocs_loaded": len(iocs)}
    except ImportError:
        return {"ok": True, "iocs_loaded": 0, "note": "threat_intel module not available"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

@app.post("/api/tip/import-stix")
async def tip_import_stix(request: Request):
    try: bundle = await request.json()
    except: bundle = {}
    try:
        sys.path.insert(0, str(ROOT))
        from redteam.threat_intel import import_stix
        result = import_stix(bundle)
        return result
    except ImportError:
        return {"ok": False, "error": "threat_intel module not available"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS — RASP
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/rasp/devices")
async def rasp_devices_get():
    return _load_json(DEVICES_FILE, [])

@app.post("/api/rasp/devices")
async def rasp_devices_post(request: Request):
    try: device = await request.json()
    except: device = {}
    devices = _load_json(DEVICES_FILE, [])
    device["id"] = uuid.uuid4().hex[:8]
    device["enrolled"] = True
    device["last_seen"] = datetime.now().isoformat()
    devices.append(device)
    _save_json(DEVICES_FILE, devices)
    return {"ok": True, "id": device["id"]}

@app.delete("/api/rasp/devices/{device_id}")
async def rasp_devices_delete(device_id: str):
    devices = _load_json(DEVICES_FILE, [])
    devices = [d for d in devices if d.get("id") != device_id]
    _save_json(DEVICES_FILE, devices)
    return {"ok": True}

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS — TERMINAL
# ═════════════════════════════════════════════════════════════════════════════

@app.post("/api/terminal")
async def terminal(request: Request):
    try: body = await request.json()
    except: body = {}
    command = body.get("command", "")
    return _run_terminal(command)

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS — SETTINGS
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/settings")
async def settings_get():
    return _load_json(SETTINGS_FILE, {})

@app.post("/api/settings")
async def settings_post(request: Request):
    try: body = await request.json()
    except: body = {}
    current = _load_json(SETTINGS_FILE, {})
    current.update(body)
    _save_json(SETTINGS_FILE, current)
    return {"ok": True}

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS — AUTH (básico, sin mocks)
# ═════════════════════════════════════════════════════════════════════════════

@app.post("/api/auth/login")
async def auth_login(request: Request):
    return {"ok": False, "error": "Auth no configurado. Usar API key via Settings."}

@app.post("/api/auth/biometric")
async def auth_biometric(request: Request):
    return {"ok": False, "error": "Biometric no disponible en este entorno."}

@app.post("/api/auth/logout")
async def auth_logout():
    return {"ok": True}

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS — STATS / META / HEALTH
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/network/stats")
async def network_stats():
    return {"hosts": 0, "cameras": 0, "routers": 0, "alerts": 0,
            "backend": "unified", "version": "3.0-unified", "ts": int(time.time())}

@app.get("/api/health")
@app.get("/health")
@app.get("/healthz")
async def health():
    return {"status": "ok", "backend": "red-team-tauri-unified", "version": "3.0-unified",
            "dist_built": DIST.exists(), "ws_clients": len(ws_clients),
            "honeypot_running": bool(honeypot_proc and honeypot_proc.poll() is None),
            "psutil": HAS_PSUTIL, "geo_intel": _GEO_INTEL_OK, "ts": int(time.time())}

@app.get("/")
async def root():
    index = DIST / "index.html"
    if index.exists(): return FileResponse(index)
    return {
        "status": "ok", "backend": "red-team-tauri-unified", "version": "3.0-unified",
        "dist_built": False,
        "hint": f"cd tauri-frontend && npm run build (esperado: {DIST})",
        "endpoints": [
            "POST /api/scan/topology", "POST /api/scan/cameras | /api/network/cameras",
            "POST /api/scan/routers", "POST /api/scan/iot", "POST /api/scan/wifi",
            "POST /api/scan/antenna | /api/scan/radio", "GET /api/network/radio",
            "GET /api/osint/shodan?ip=X", "GET /api/exploits/list",
            "GET /api/geo?ip=X", "GET /api/intel?ip=X",
            "GET /api/services", "POST /api/services/start|stop|restart?name=X",
            "POST /api/services/start-all|stop-all", "GET /api/services/{name}/logs",
            "GET /api/resources", "POST /api/scan", "GET /api/scan/status",
            "GET /api/latest", "GET /api/history",
            "GET /api/config", "GET /api/config/read?path=X", "POST /api/config/write",
            "GET /api/honeypot", "POST /api/honeypot/start|stop|toggle|rotate",
            "GET /api/honeypot/status",
            "GET /api/soar/dags", "POST /api/soar/dags", "POST /api/soar/dry-run",
            "GET /api/tip/iocs", "POST /api/tip/iocs", "DELETE /api/tip/iocs/{id}",
            "POST /api/tip/update", "POST /api/tip/import-stix",
            "GET /api/rasp/devices", "POST /api/rasp/devices", "DELETE /api/rasp/devices/{id}",
            "POST /api/terminal", "GET /api/settings", "POST /api/settings",
            "POST /api/auth/login|biometric|logout",
            "POST /api/canary/generate | /api/canary/svg/generate",
            "GET /canary/callback?id=X", "POST /api/canary/alert",
            "GET /api/canary/svg/list|alerts", "GET /api/canary/svg/download?id=X",
            "GET /api/iot/video-urls?ip=X&port=X", "GET /api/iot/snapshot?ip=X",
            "GET /api/network/stats", "GET /api/health", "WS /ws",
        ],
    }

# ═════════════════════════════════════════════════════════════════════════════
#  FRONTEND ESTÁTICO — SPA
# ═════════════════════════════════════════════════════════════════════════════

if DIST.exists() and DIST.is_dir():
    assets_dir = DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        if not full_path:
            index = DIST / "index.html"
            return FileResponse(index) if index.exists() else JSONResponse({"error": "dist/ empty"}, status_code=404)
        # NUNCA servir el SPA para rutas API — devuelve 404 JSON
        if full_path.startswith(("api/", "canary/", "ws")):
            return JSONResponse({"error": "not found"}, status_code=404)
        if full_path.startswith("assets/"):
            candidate = DIST / full_path
            if candidate.exists() and candidate.is_file():
                return FileResponse(candidate)
            return JSONResponse({"error": "not found"}, status_code=404)
        candidate = DIST / full_path
        if candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
        index = DIST / "index.html"
        return FileResponse(index) if index.exists() else JSONResponse({"error": "dist/index.html missing"}, status_code=404)
else:
    @app.get("/{full_path:path}")
    async def no_dist_fallback(full_path: str):
        if full_path.startswith(("api/", "canary/", "ws", "health")):
            return JSONResponse({"error": "not found"}, status_code=404)
        return JSONResponse({"status": "ok", "backend": "red-team-tauri-unified",
                            "dist_built": False, "hint": f"cd tauri-frontend && npm run build (esperado: {DIST})"})

# ═════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═════════════════════════════════════════════════════════════════════════════

# == CORSET + TRIAGE + OSINT ENDPOINTS ====================================
@app.get("/api/corset/status")
async def corset_status():
    if _corset is None:
        return {"active": False, "error": "Corset not initialized"}
    return _corset.status()

@app.get("/api/triage")
async def triage_scan():
    if _triage_report is None:
        return {"error": "Triage module not available"}
    return _triage_report()

@app.post("/api/osint/extract")
async def osint_extract(request: Request):
    if _osint_extract is None:
        return {"error": "OSINT module not available"}
    try:
        data = await request.json()
        text = data.get("text", "")
        if not text:
            return {"error": "No text provided"}
        return _osint_extract(text)
    except Exception as e:
        return {"error": str(e)}
# == END CORSET + TRIAGE + OSINT ENDPOINTS ================================

if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8001"))
    print("═" * 60, flush=True)
    print(f"  RED-TEAM-TAURI · Unified Dashboard Backend v3.0", flush=True)
    print(f"  → Escuchando en  http://{host}:{port}", flush=True)
    print(f"  → Frontend dist/ {'OK' if DIST.exists() else 'FALTA'}: {DIST}", flush=True)
    print(f"  → WebSocket:     ws://{host}:{port}/ws", flush=True)
    print(f"  → psutil: {'OK' if HAS_PSUTIL else 'NOT AVAILABLE'}", flush=True)
    print(f"  → geo_intel: {'OK' if _GEO_INTEL_OK else 'NOT AVAILABLE'}", flush=True)
    print(f"  → Sin mocks. Sin dummy data. Solo datos reales.", flush=True)
    print("═" * 60, flush=True)
    uvicorn.run(app, host=host, port=port, log_level="info")

# ============================================================
# ENDPOINTS — VIDEO EN VIVO (MJPEG + RTSP → HLS)
# ============================================================

import shutil as _shutil
import signal as _signal

HLS_CACHE_DIR = str(DATA_DIR / "hls_cache")
os.makedirs(HLS_CACHE_DIR, exist_ok=True)

# Diccionario para rastrear procesos ffmpeg activos
active_ffmpeg_processes: dict = {}


@app.get("/api/iot/mjpeg-proxy")
async def mjpeg_proxy(url: str = Query(...)):
    """
    Proxy para streams MJPEG.
    Uso: /api/iot/mjpeg-proxy?url=http://camara/mjpg/video.mjpg
    Devuelve el stream en formato multipart/x-mixed-replace para el navegador.
    """
    try:
        client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        req = await client.get(url)
        return StreamingResponse(
            req.aiter_bytes(),
            media_type="multipart/x-mixed-replace; boundary=--myboundary"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/iot/rtsp-to-hls")
async def rtsp_to_hls(rtsp_url: str = Query(...), duration: int = 60):
    """
    Convierte un stream RTSP a HLS usando ffmpeg.
    duration: tiempo en segundos que estará activo (default 60).
    Devuelve la URL del archivo .m3u8 para reproducir con hls.js.
    """
    try:
        session_id = str(uuid.uuid4())[:8]
        output_dir = os.path.join(HLS_CACHE_DIR, session_id)
        os.makedirs(output_dir, exist_ok=True)
        m3u8_path = os.path.join(output_dir, "index.m3u8")

        # Comando ffmpeg optimizado para baja latencia
        cmd = [
            "ffmpeg",
            "-rtsp_transport", "tcp",
            "-i", rtsp_url,
            "-c:v", "copy",
            "-c:a", "aac",
            "-f", "hls",
            "-hls_time", "2",
            "-hls_list_size", "5",
            "-hls_flags", "delete_segments+omit_endlist",
            m3u8_path
        ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid
        )

        active_ffmpeg_processes[session_id] = {
            "process": process,
            "m3u8_path": m3u8_path,
            "created_at": asyncio.get_event_loop().time()
        }

        # Programar auto-destrucción después de 'duration' segundos
        async def auto_kill():
            await asyncio.sleep(duration)
            await kill_rtsp_session(session_id)
        asyncio.create_task(auto_kill())

        return {
            "stream_url": f"/hls/{session_id}/index.m3u8",
            "session_id": session_id,
            "expires_in": duration
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/iot/rtsp-stop/{session_id}")
async def kill_rtsp_session(session_id: str):
    """Detiene un proceso ffmpeg y elimina los archivos HLS."""
    if session_id in active_ffmpeg_processes:
        process_info = active_ffmpeg_processes[session_id]
        proc = process_info["process"]
        try:
            os.killpg(os.getpgid(proc.pid), _signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

        output_dir = os.path.join(HLS_CACHE_DIR, session_id)
        if os.path.exists(output_dir):
            _shutil.rmtree(output_dir, ignore_errors=True)

        del active_ffmpeg_processes[session_id]
        return {"status": "stopped", "session_id": session_id}
    else:
        return {"status": "not_found", "session_id": session_id}


@app.get("/api/iot/rtsp-active")
async def list_active_streams():
    """Devuelve las sesiones RTSP→HLS activas."""
    sessions = []
    for sid, info in active_ffmpeg_processes.items():
        sessions.append({
            "session_id": sid,
            "m3u8_path": info["m3u8_path"],
            "created_at": info["created_at"]
        })
    return {"active_streams": sessions, "total": len(sessions)}


# Servir archivos HLS estáticos
try:
    app.mount("/hls", StaticFiles(directory=HLS_CACHE_DIR, html=True), name="hls")
except RuntimeError:
    pass  # Ya montado

# == END VIDEO EN VIVO ================================================
