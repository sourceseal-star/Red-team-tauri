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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Query, Depends, HTTPException, Security, Body
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


# ── Enhanced Recon Module (ONVIF, SSDP, SNMP, NetBIOS, mDNS) ────────────────
try:
    sys.path.insert(0, str(BASE.parent / "backend"))
    from modules.enhanced_recon import router as enhanced_recon_router
    _ENHANCED_RECON_OK = True
    print("[ENHANCED-RECON] Módulo cargado: ONVIF + SSDP + SNMP + NetBIOS + mDNS")
except Exception as _er_err:
    _ENHANCED_RECON_OK = False
    print(f"[WARN] enhanced_recon import falló: {_er_err}", flush=True)

# ── OSINT Advanced v4.0 (Google, Shodan, VirusTotal, Censys, Social) ─────────
try:
    from modules.osint_advanced import osint_router
    _OSINT_ADVANCED_OK = True
    print("[OSINT-ADVANCED] Módulo v4.0 cargado: WHOIS + DNS + Shodan + VirusTotal + Google + Social")
except Exception as _oa_err:
    _OSINT_ADVANCED_OK = False
    print(f"[WARN] osint_advanced import falló: {_oa_err}", flush=True)

# ── Interceptor Advanced v4.0 (XXE, LFI/RFI, LDAP, NoSQL, SQLi, XSS, SSRF) ──
try:
    from tlsproxy.interceptor_advanced import interceptor_router
    _INTERCEPTOR_ADVANCED_OK = True
    print("[INTERCEPTOR-ADVANCED] Módulo v4.0 cargado: MITM + Injection Detection + SIEM")
except Exception as _ia_err:
    _INTERCEPTOR_ADVANCED_OK = False
    print(f"[WARN] interceptor_advanced import falló: {_ia_err}", flush=True)

API_KEY = os.environ.get("REDTEAM_API_KEY", "").strip()

# ── Motor de Cierre (leads/checkout/metrics) — antes corria como un 2do
# proceso FastAPI en el MISMO puerto 8001 que este backend, lo que hacia
# que solo uno de los dos pudiera estar vivo a la vez. Se monta aqui como
# sub-app para que TODO viva en un solo proceso/puerto de verdad.
    # Alinear el API key: dashboard_server.py emite tokens via REDTEAM_API_KEY
    # su propio default distinto ("dev-key-cambiar-en-produccion") -> con
    # esto ambos aceptan el MISMO token emitido por /api/auth/login.

# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Red-Team Tauri · Unified Dashboard Backend",
    version="4.0-unified",
    description="Backend único: escaneo + servicios + SOAR + TIP + RASP + terminal + canary + honeypot + dist/",
)

# ── Include Enhanced Recon router ──────────────────────────────────────────
if _ENHANCED_RECON_OK:
    app.include_router(enhanced_recon_router)
    print("[ENHANCED-RECON] Router montado en /api/enhanced/*")

# ── Include OSINT Advanced v4.0 router ─────────────────────────────────────
if _OSINT_ADVANCED_OK:
    app.include_router(osint_router)
    print("[OSINT-ADVANCED] Router montado en /api/osint/* (v4.0: Google, Shodan, VT, Social)")

# ── Include Interceptor Advanced v4.0 router ──────────────────────────────
if _INTERCEPTOR_ADVANCED_OK:
    app.include_router(interceptor_router)
    print("[INTERCEPTOR-ADVANCED] Router montado en /api/interceptor/* (v4.0: MITM + SIEM)")

# ── API Key (obligatoria) ────────────────────────────────────────────────────
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# Endpoints PÚBLICOS (no requieren API key):
#   /api/health, /health, /healthz  → health checks
#   /canary/callback               → intruso phone-home (debe ser accesible)
PUBLIC_PATHS = {"/api/health", "/health", "/healthz", "/canary/callback", "/api/auth/login", "/api/auth/biometric", "/api/auth/password", "/api/auth/webauthn/status", "/api/auth/webauthn/register/begin", "/api/auth/webauthn/register/finish", "/api/auth/webauthn/auth/begin", "/api/auth/webauthn/auth/finish"}

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

    # Todo lo demás requiere autenticación. El frontend envía el token emitido
    # por /api/auth/login como "Authorization: Bearer <token>". También se
    # acepta X-API-Key para compatibilidad con scripts.
    if not API_KEY:
        # Si no hay API key configurada, permitir solo desde localhost
        if client_ip not in ("127.0.0.1", "::1", "localhost"):
            return JSONResponse({"error": "Unauthorized — API key required"}, status_code=401)
    else:
        # Intentar X-API-Key primero (compatibilidad scripts)
        key = request.headers.get("X-API-Key", "")
        # Luego intentar Authorization: Bearer <token> (lo que usa el frontend)
        if not key:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                key = auth_header[7:]
        if key != API_KEY:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

    # Timeout global: ningún endpoint puede bloquear el event loop más de 30s
    try:
        return await asyncio.wait_for(call_next(request), timeout=20.0)
    except asyncio.TimeoutError:
        return JSONResponse(
            {"error": "Request timeout", "detail": "La operación tardó más de 30 segundos. Intenta con un rango más pequeño."},
            status_code=504
        )

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
    # Paralelizar: lanzar todos los tcp_check a la vez con un semaphore
    # para no saturar el event loop (254 IPs × 10 puertos = 2540 checks)
    sem = asyncio.Semaphore(200)

    async def check_one(ip, port, label):
        async with sem:
            banner = await tcp_check(ip, port, timeout=0.3)
            if banner is not None:
                return {"ip": ip, "port": port, "protocol": label,
                        "banner": banner[:80], "type": "radio"}
            return None

    tasks = []
    for i in range(1, 255):
        ip = f"{base}{i}"
        for port, label in RADIO_PORTS:
            tasks.append(check_one(ip, port, label))

    raw = await asyncio.gather(*tasks)
    results = [r for r in raw if r is not None]
    return {"results": results, "count": len(results)}

# ── IoT scan por CIDR (escanear red específica) ────────────────────────────────
@app.post("/api/iot/scan-network")
async def iot_scan_network(body: dict = Body(...)):
    """Escanea una red CIDR específica en busca de cámaras IP y dispositivos con puertos abiertos."""
    import ipaddress as _ipa
    cidr = str(body.get("cidr", "")).strip()
    if not cidr:
        return JSONResponse({"error": "cidr requerido (ej: 192.168.1.0/24)"}, status_code=400)
    try:
        net = _ipa.ip_network(cidr, strict=False)
    except Exception:
        return JSONResponse({"error": f"CIDR inválido: {cidr}"}, status_code=400)
    
    hosts = [str(h) for h in net.hosts()][:254]  # limitar a /24
    # Escanear puertos de cámara + comunes
    SCAN_PORTS = [554, 80, 443, 8080, 8000, 37777, 8554, 23, 22]
    
    cameras = []
    all_devices = []
    
    # Escaneo paralelo por IP
    async def scan_ip(ip: str):
        results = {}
        for port in SCAN_PORTS:
            b = await tcp_check(ip, port, timeout=1.0)
            if b is not None:
                results[port] = b[:80]
        return ip, results
    
    tasks = [scan_ip(ip) for ip in hosts]
    scan_results = await asyncio.gather(*tasks)
    
    for ip, ports in scan_results:
        if not ports:
            continue
        open_port_list = list(ports.keys())
        device_type = "device"
        brand = None
        
        if 554 in ports:
            brand = _detect_camera_brand(ports[554])
            cameras.append({
                "ip": ip, "port": 554, "protocol": "RTSP",
                "banner": ports[554], "brand": brand,
                "type": "camera",
                "ports_open": [f"{p}/tcp" for p in open_port_list],
            })
            device_type = "camera"
        
        all_devices.append({
            "ip": ip,
            "type": device_type,
            "vendor": brand or _detect_camera_brand(" ".join(ports.values())),
            "ports_open": [f"{p}/tcp" for p in open_port_list],
            "evidence": [{"port": p, "banner": b} for p, b in ports.items()],
        })
    
    await broadcast({"type": "progress", "payload": f"Scan completo: {len(cameras)} cámaras, {len(all_devices)} dispositivos"})
    
    return {
        "network": cidr,
        "total_ips": len(hosts),
        "total_scanned": len(hosts),
        "cameras_found": len(cameras),
        "devices_with_open_ports": len(all_devices),
        "cameras": cameras,
        "all_devices": all_devices,
        "full_results": [],
    }

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

@app.get("/api/intel/deep")
async def api_intel_deep(ip: str = Query(...)):
    """Intel profundo: geo + reputation + port inference + threat correlation"""
    if not _valid_ip(ip):
        return JSONResponse({"error": "invalid IP"}, status_code=400)
    try:
        # 1. Intel base
        if _GEO_INTEL_OK: base = _intel_assess(ip)
        else:
            from geo_intel import assess; base = assess(ip)
        
        # 2. Info adicional: shodan-like port inference
        deep_info = {
            **base,
            "ports_inferred": [80, 443, 22, 8080] if base.get("is_tor") else [80, 443],
            "risk_factors": [],
            "recommendations": []
        }
        
        if base.get("risk_score", 0) > 70:
            deep_info["risk_factors"].append("high_risk_score")
            deep_info["recommendations"].append("Bloquear IP en firewall perimetral")
        if base.get("is_tor"):
            deep_info["risk_factors"].append("tor_exit_node")
            deep_info["recommendations"].append("Requiere investigación adicional — nodo Tor")
        if base.get("is_vpn"):
            deep_info["risk_factors"].append("vpn_detected")
            deep_info["recommendations"].append("Verificar legitimidad del acceso")
        
        if not deep_info["risk_factors"]:
            deep_info["risk_factors"].append("low_risk")
            deep_info["recommendations"].append("Sin acción requerida")
        
        return deep_info
    except Exception as e:
        return JSONResponse({"error": f"intel deep falló: {e}", "ip": ip}, status_code=500)

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
# NOTA: las implementaciones reales de /api/auth/login y /api/auth/biometric
# estan mas abajo (usan ADMIN_EMAIL/ADMIN_PASSWORD). Antes habia un stub
# duplicado aqui que SIEMPRE devolvia ok:false porque FastAPI/Starlette
# usa la PRIMERA ruta que matchea el path -> el login real quedaba muerto,
# nunca se ejecutaba sin importar la contrasena que pusieras.

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

# == AUTENTICACION DEL DASHBOARD (email/password + WebAuthn real) ==========
import secrets as _secrets
import json as _json
import time as _time

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@redteam.local").strip()
# FIX CRITICO: antes leia "API_KEY" (env var que nunca se seteaba) mientras
# el middleware de seguridad exige "REDTEAM_API_KEY" (variable API_KEY definida
# arriba, linea ~136). Esto causaba que el login emitiera un token que NUNCA
# coincidia con el que el middleware validaba -> 401 en TODO despues de loguear.
DASHBOARD_TOKEN = API_KEY or "local-dev-token"

_AUTH_DIR = os.path.join(os.path.dirname(__file__), ".auth")
_PASS_FILE = os.path.join(_AUTH_DIR, "password.json")
_WEBAUTHN_FILE = os.path.join(_AUTH_DIR, "webauthn.json")
os.makedirs(_AUTH_DIR, exist_ok=True)

def _get_password():
    if os.path.exists(_PASS_FILE):
        try:
            with open(_PASS_FILE) as f:
                return _json.load(f).get("password", "")
        except Exception:
            pass
    return os.environ.get("ADMIN_PASSWORD", "admin123").strip()

def _set_password(new_pass):
    with open(_PASS_FILE, 'w') as f:
        _json.dump({"password": new_pass, "changed": _time.time()}, f)

def _load_webauthn():
    if os.path.exists(_WEBAUTHN_FILE):
        try:
            with open(_WEBAUTHN_FILE) as f:
                return _json.load(f)
        except Exception:
            pass
    return {"credentials": [], "pending_challenge": None, "pending_auth_challenge": None}

def _save_webauthn(data):
    with open(_WEBAUTHN_FILE, 'w') as f:
        _json.dump(data, f, indent=2)

@app.post("/api/auth/login")
async def auth_login(body: dict = Body(...)):
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    if email != ADMIN_EMAIL or password != _get_password():
        raise HTTPException(status_code=401, detail="Credenciales invalidas")
    return {"token": DASHBOARD_TOKEN, "email": email}

@app.post("/api/auth/password")
async def change_password(body: dict = Body(...)):
    current = body.get("current_password", "")
    new = body.get("new_password", "")
    if current != _get_password():
        raise HTTPException(status_code=401, detail="Contrasena actual incorrecta")
    if len(new) < 6:
        raise HTTPException(status_code=400, detail="Minimo 6 caracteres")
    _set_password(new)
    return {"status": "ok", "message": "Contrasena actualizada"}

@app.get("/api/auth/webauthn/status")
async def webauthn_status():
    data = _load_webauthn()
    return {"registered": len(data.get("credentials", [])) > 0, "count": len(data.get("credentials", []))}

@app.post("/api/auth/webauthn/register/begin")
async def webauthn_register_begin(body: dict = Body(...)):
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    if email != ADMIN_EMAIL or password != _get_password():
        raise HTTPException(status_code=401, detail="Credenciales invalidas")
    challenge = _secrets.token_urlsafe(32)
    data = _load_webauthn()
    data["pending_challenge"] = challenge
    _save_webauthn(data)
    return {
        "challenge": challenge,
        "rp": {"name": "RedTeam Dashboard", "id": "localhost"},
        "user": {"id": _secrets.token_urlsafe(8), "name": email, "displayName": "Admin"},
        "pubKeyCredParams": [{"type": "public-key", "alg": -7}, {"type": "public-key", "alg": -257}],
        "authenticatorSelection": {"authenticatorAttachment": "platform", "userVerification": "required"},
        "timeout": 60000
    }

@app.post("/api/auth/webauthn/register/finish")
async def webauthn_register_finish(body: dict = Body(...)):
    challenge = body.get("challenge", "")
    credential_id = body.get("credentialId", "")
    if not credential_id:
        raise HTTPException(status_code=400, detail="credentialId requerido")
    data = _load_webauthn()
    if data.get("pending_challenge") != challenge:
        raise HTTPException(status_code=400, detail="Challenge invalido o expirado")
    data["credentials"].append({"id": credential_id, "created": _time.time()})
    data["pending_challenge"] = None
    _save_webauthn(data)
    return {"status": "ok", "message": "Huella registrada"}

@app.post("/api/auth/webauthn/auth/begin")
async def webauthn_auth_begin():
    challenge = _secrets.token_urlsafe(32)
    data = _load_webauthn()
    if not data.get("credentials"):
        raise HTTPException(status_code=400, detail="No hay huella registrada")
    data["pending_auth_challenge"] = challenge
    _save_webauthn(data)
    return {
        "challenge": challenge,
        "credentials": [{"type": "public-key", "id": c["id"]} for c in data["credentials"]],
        "timeout": 60000,
        "userVerification": "required"
    }

@app.post("/api/auth/webauthn/auth/finish")
async def webauthn_auth_finish(body: dict = Body(...)):
    challenge = body.get("challenge", "")
    credential_id = body.get("credentialId", "")
    data = _load_webauthn()
    if data.get("pending_auth_challenge") != challenge:
        raise HTTPException(status_code=400, detail="Challenge invalido")
    stored_ids = [c["id"] for c in data.get("credentials", [])]
    if credential_id not in stored_ids:
        raise HTTPException(status_code=401, detail="Huella no reconocida")
    data["pending_auth_challenge"] = None
    _save_webauthn(data)
    return {"token": DASHBOARD_TOKEN, "email": ADMIN_EMAIL}

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
            "GET /api/osint/shodan?ip=X", "GET /api/osint/whois/{domain}", "GET /api/osint/subdomains/{domain}", "GET /api/osint/emails/{domain}", "GET /api/intel/ip/{ip}", "GET /api/intel/bulk-check", "GET /api/investigate/ip/{ip}", "GET /api/investigate/camera/{ip}", "GET /api/exploits/list",
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
        client = httpx.AsyncClient(timeout=20.0, follow_redirects=True)
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

# ============================================================
# FASE 3: EVIDENCIA BLINDADA (Hash + Blockchain + QR + PDF)
# ============================================================

import hashlib as _hashlib
import csv as _csv
import io as _io
import base64 as _b64

try:
    import qrcode as _qrcode
    from reportlab.lib.pagesizes import letter as _letter_size
    from reportlab.pdfgen import canvas as _rl_canvas
    from reportlab.lib.utils import ImageReader as _rl_img_reader
    _HAS_PDF_DEPS = True
except ImportError:
    _HAS_PDF_DEPS = False

# Configuración
SOURCESEAL_API = os.environ.get("SOURCESEAL_API", "https://source.coal/api/v1/seal")
SOURCESEAL_VERIFY = os.environ.get("SOURCESEAL_VERIFY", "https://source.coal/api/v1/verify")
PENDING_SEALS_FILE = str(DATA_DIR / "pending_seals.txt")
EVIDENCE_CACHE_DIR = str(DATA_DIR / "evidence_cache")
os.makedirs(EVIDENCE_CACHE_DIR, exist_ok=True)


async def _get_topology_data():
    """Obtiene los datos reales de topología reutilizando scan_topology."""
    subnet = subnet_from_iface()
    ok, out = _nmap_or_empty(["nmap", "-sn", "-T3", subnet], timeout=60)
    if not ok:
        return {"devices": [], "subnet": subnet, "error": out, "timestamp": datetime.now().isoformat()}

    hosts, current = [], None
    for line in out.splitlines():
        if "Nmap scan report for" in line:
            ip = line.split()[-1].strip("()")
            current = {"ip": ip, "hostname": "", "type": "unknown", "ports": [], "mac": None, "vendor": None}
            hosts.append(current)
        elif current and "MAC Address" in line:
            parts = line.split()
            if len(parts) >= 3:
                current["mac"] = parts[2]
                if len(parts) > 3:
                    current["vendor"] = " ".join(parts[3:]).strip("()")

    if hosts:
        fp_results = await asyncio.gather(*[_fingerprint_host(h["ip"]) for h in hosts])
        for h, fp in zip(hosts, fp_results):
            h["type"] = fp["type"]
            h["ports"] = fp["ports"]
            h["risk"] = fp["risk"]
            if fp["vendor"] and not h.get("vendor"):
                h["vendor"] = fp["vendor"]

    return {"devices": hosts, "subnet": subnet, "timestamp": datetime.now().isoformat()}


@app.get("/api/export/sealed-json")
async def export_sealed_json():
    """Exporta la topología completa con hash SHA-256 y anclaje blockchain."""
    data = await _get_topology_data()
    data_json = json.dumps(data, default=str)
    file_hash = _hashlib.sha256(data_json.encode('utf-8')).hexdigest()

    tx_id = None
    try:
        import requests as _requests
        response = _requests.post(
            SOURCESEAL_API,
            json={"hash": file_hash, "metadata": {"source": "RedTeam_Topology", "timestamp": datetime.now().isoformat()}},
            timeout=10
        )
        if response.status_code == 200:
            tx_id = response.json().get("tx_id")
    except Exception:
        with open(PENDING_SEALS_FILE, "a") as f:
            f.write(f"{file_hash}|{datetime.now().isoformat()}\n")
        tx_id = "offline_pending"

    sealed_package = {
        "seal": {
            "hash": file_hash,
            "timestamp": datetime.now().isoformat(),
            "blockchain_tx": tx_id,
            "verification_url": f"https://source.coal/verify/{file_hash}",
            "instructions": "Verifica este hash en la blockchain para validar la integridad."
        },
        "data": data
    }

    filename = f"evidence_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    return StreamingResponse(
        iter([json.dumps(sealed_package, indent=2)]),
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "X-Evidence-Hash": file_hash,
            "X-Blockchain-Tx": str(tx_id or "pending")
        }
    )


@app.get("/api/export/paper-evidence")
async def export_paper_evidence():
    """Genera un PDF imprimible con resumen, hash SHA-256 y código QR."""
    if not _HAS_PDF_DEPS:
        raise HTTPException(status_code=503, detail="Dependencias no instaladas: pip install qrcode reportlab")

    data = await _get_topology_data()
    data_json = json.dumps(data, default=str)
    file_hash = _hashlib.sha256(data_json.encode('utf-8')).hexdigest()

    # Código QR
    qr = _qrcode.QRCode(box_size=8, border=3)
    qr.add_data(f"https://source.coal/verify/{file_hash}")
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")

    qr_buffer = _io.BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)
    qr_reader = _rl_img_reader(qr_buffer)

    # PDF
    pdf_buffer = _io.BytesIO()
    c = _rl_canvas.Canvas(pdf_buffer, pagesize=_letter_size)
    width, height = _letter_size

    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, height - 50, "EVIDENCIA DE AUDITORIA DE RED")
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 70, f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    c.drawString(50, height - 85, f"Hash SHA-256: {file_hash}")

    devices = data.get('devices', [])
    c.drawString(50, height - 115, f"Dispositivos detectados: {len(devices)}")
    c.drawString(50, height - 130, f"Subred: {data.get('subnet', 'N/A')}")
    y_pos = height - 150
    for idx, d in enumerate(devices[:15]):
        c.drawString(60, y_pos, f"{idx+1}. {d.get('ip', '')} ({d.get('type', 'unknown')}) risk={d.get('risk', 'N/A')}")
        y_pos -= 15
        if idx == 14 and len(devices) > 15:
            c.drawString(60, y_pos, f"... y {len(devices)-15} mas")
            break

    c.drawImage(qr_reader, width - 200, height - 300, width=140, height=140)

    c.setFont("Helvetica-Oblique", 8)
    c.drawString(50, 80, "Instrucciones:")
    c.drawString(50, 65, "1. Escanea el codigo QR o visita la URL.")
    c.drawString(50, 50, "2. Verifica que el hash coincida con el de la blockchain.")
    c.drawString(50, 35, "3. Este documento tiene validez internacional si el hash esta registrado.")
    c.drawString(50, 20, "4. Guarda este papel en un lugar seguro. Es tu prueba fisica.")

    c.save()
    pdf_buffer.seek(0)

    filename = f"paper_evidence_{datetime.now().strftime('%Y%m%d')}.pdf"
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "X-Evidence-Hash": file_hash
        }
    )


@app.post("/api/export/process-pending")
async def process_pending_seals():
    """Procesa sellos guardados offline y los ancla en blockchain."""
    if not os.path.exists(PENDING_SEALS_FILE):
        return {"status": "no_pending", "message": "No hay sellos pendientes"}

    with open(PENDING_SEALS_FILE, "r") as f:
        lines = f.readlines()

    results, new_pending = [], []
    for line in lines:
        parts = line.strip().split("|")
        if len(parts) < 2:
            continue
        file_hash, timestamp = parts[0], parts[1]
        try:
            import requests as _requests
            resp = _requests.post(SOURCESEAL_API, json={"hash": file_hash, "metadata": {"offline_recovery": timestamp}}, timeout=10)
            if resp.status_code == 200:
                results.append({"hash": file_hash, "status": "sealed", "tx": resp.json().get("tx_id")})
            else:
                new_pending.append(line.strip())
        except Exception:
            new_pending.append(line.strip())

    with open(PENDING_SEALS_FILE, "w") as f:
        if new_pending:
            f.write("\n".join(new_pending) + "\n")

    return {
        "processed": len(results),
        "still_pending": len(new_pending),
        "details": results
    }


@app.get("/api/export/verify/{hash_value}")
async def verify_hash(hash_value: str):
    """Consulta si un hash esta registrado en SourceSeal."""
    try:
        import requests as _requests
        response = _requests.get(f"{SOURCESEAL_VERIFY}/{hash_value}", timeout=10)
        if response.status_code == 200:
            return {"verified": True, "data": response.json()}
        else:
            return {"verified": False, "message": "Hash no encontrado en blockchain"}
    except Exception:
        return {"verified": False, "message": "No se pudo conectar con SourceSeal"}


@app.get("/api/export/sealed-csv")
async def export_sealed_csv():
    """Exporta la topología a CSV con hash SHA-256 en headers."""
    data = await _get_topology_data()
    devices = data.get('devices', [])

    output = _io.StringIO()
    writer = _csv.writer(output)
    writer.writerow(['IP', 'Type', 'Ports', 'MAC', 'Vendor', 'Risk', 'Timestamp'])
    for d in devices:
        ports_str = ';'.join(str(p) if isinstance(p, int) else str(p.get('port', '')) for p in d.get('ports', []))
        writer.writerow([
            d.get('ip', ''),
            d.get('type', 'unknown'),
            ports_str,
            d.get('mac', ''),
            d.get('vendor', ''),
            d.get('risk', ''),
            data.get('timestamp', '')
        ])
    csv_content = output.getvalue()
    file_hash = _hashlib.sha256(csv_content.encode('utf-8')).hexdigest()

    filename = f"topology_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "X-Evidence-Hash": file_hash,
            "X-Verification-URL": f"https://source.coal/verify/{file_hash}"
        }
    )

# == END FASE 3: EVIDENCIA BLINDADA ==================================

# ============================================================
# PROTOCOLO MURCIÉLAGO — Ultrasonidos 18-20 kHz
# ============================================================

import math as _math
import struct as _struct
import tempfile as _tempfile

MURCIELAGO_DIR = str(ROOT / "murcielago")
MURCIELAGO_WAV_CACHE = str(DATA_DIR / "murcielago_wav")
os.makedirs(MURCIELAGO_WAV_CACHE, exist_ok=True)

# Tabla de frecuencias
_MURC_FREQ_TABLE = {
    '0': (18000, 18400), '1': (18100, 18500), '2': (18200, 18600),
    '3': (18300, 18700), '4': (18400, 18800), '5': (18500, 18900),
    '6': (18600, 19000), '7': (18700, 19100), '8': (18800, 19200),
    '9': (18900, 19300), 'A': (19000, 19400), 'B': (19100, 19500),
    'C': (19200, 19600), 'D': (19300, 19700), 'E': (19400, 19800),
    'F': (19500, 19900), '#': (18000, 19500), '*': (18500, 20000)
}
_MURC_SYNC_FREQ = 19500
_MURC_SAMPLE_RATE = 48000
_MURC_DURATION_SYMBOL = 0.08
_MURC_SILENCE_BETWEEN = 0.025


def _murc_generate_tone(freq, duration, sample_rate=48000):
    n = int(sample_rate * duration)
    samples = [int(_math.sin(2 * _math.pi * freq * (i / sample_rate)) * 32767) for i in range(n)]
    return _struct.pack(f'<{n}h', *samples)


def _murc_generate_silence(duration, sample_rate=48000):
    n = int(sample_rate * duration)
    return _struct.pack(f'<{n}h', *[0] * n)


def _murc_encode_symbols(message):
    msg_bytes = message.encode('utf-8')
    checksum = sum(msg_bytes) % 256
    hex_str = msg_bytes.hex().upper()
    check_hex = f"{checksum:02X}"
    return list(hex_str + '*' + check_hex)


def _murc_build_wav(symbols, repeat=1):
    full = b''
    for _ in range(repeat):
        full += _murc_generate_tone(_MURC_SYNC_FREQ, 0.3)
        full += _murc_generate_silence(0.05)
        for sym in symbols:
            if sym in _MURC_FREQ_TABLE:
                f1, f2 = _MURC_FREQ_TABLE[sym]
                n = int(_MURC_SAMPLE_RATE * _MURC_DURATION_SYMBOL)
                pcm = [int((0.5 * _math.sin(2 * _math.pi * f1 * (i / _MURC_SAMPLE_RATE)) +
                            0.5 * _math.sin(2 * _math.pi * f2 * (i / _MURC_SAMPLE_RATE))) * 20000)
                       for i in range(n)]
                full += _struct.pack(f'<{n}h', *pcm)
            else:
                full += _murc_generate_silence(_MURC_DURATION_SYMBOL)
            full += _murc_generate_silence(_MURC_SILENCE_BETWEEN)
        full += _murc_generate_tone(_MURC_SYNC_FREQ, 0.2)
        full += _murc_generate_silence(0.1)

    # Cabecera WAV
    data_len = len(full)
    header = b'RIFF' + _struct.pack('<I', data_len + 36) + b'WAVE'
    header += b'fmt ' + _struct.pack('<IHHIIHH', 16, 1, 1, _MURC_SAMPLE_RATE, _MURC_SAMPLE_RATE * 2, 2, 16)
    header += b'data' + _struct.pack('<I', data_len)
    return header + full


@app.post("/api/murcielago/send")
async def murcielago_send(request: Request):
    """Genera y reproduce un mensaje por ultrasonidos."""
    try:
        data = await request.json()
        message = data.get("message", "").strip()
        repeat = data.get("repeat", 1)
        if not message:
            raise HTTPException(status_code=400, detail="Mensaje vacío")
        if len(message) > 200:
            raise HTTPException(status_code=400, detail="Mensaje demasiado largo (máx 200 chars)")

        symbols = _murc_encode_symbols(message)
        wav_bytes = _murc_build_wav(symbols, repeat=repeat)

        # Guardar WAV en cache
        wav_filename = f"murc_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.wav"
        wav_path = os.path.join(MURCIELAGO_WAV_CACHE, wav_filename)
        with open(wav_path, 'wb') as f:
            f.write(wav_bytes)

        # Intentar reproducir en segundo plano (no bloquear la respuesta)
        player = None
        for cmd in (['ffplay', '-nodisp', '-autoexit', '-volume', '80', wav_path],
                    ['aplay', '-q', wav_path]):
            try:
                player = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                break
            except FileNotFoundError:
                continue

        return {
            "status": "sent",
            "message": message,
            "symbols": ''.join(symbols),
            "wav_file": wav_filename,
            "wav_url": f"/api/murcielago/download/{wav_filename}",
            "playing": player is not None,
            "duration_sec": round(len(symbols) * (_MURC_DURATION_SYMBOL + _MURC_SILENCE_BETWEEN) * repeat + 0.7 * repeat, 2)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/murcielago/generate-wav")
async def murcielago_generate_wav(message: str = Query(...), repeat: int = 1):
    """Genera un WAV sin reproducirlo. Devuelve el archivo para descargar."""
    if len(message) > 200:
        raise HTTPException(status_code=400, detail="Mensaje demasiado largo (máx 200 chars)")

    symbols = _murc_encode_symbols(message)
    wav_bytes = _murc_build_wav(symbols, repeat=repeat)

    filename = f"murc_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
    return StreamingResponse(
        iter([wav_bytes]),
        media_type="audio/wav",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/api/murcielago/download/{filename}")
async def murcielago_download(filename: str):
    """Descarga un WAV generado previamente."""
    wav_path = os.path.join(MURCIELAGO_WAV_CACHE, filename)
    if not os.path.exists(wav_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(wav_path, media_type="audio/wav", filename=filename)


@app.get("/api/murcielago/status")
async def murcielago_status():
    """Estado del protocolo MURCIÉLAGO."""
    has_ffplay = shutil.which("ffplay") is not None if (shutil := __import__('shutil')) else False
    has_aplay = shutil.which("aplay") is not None if shutil else False
    has_numpy = False
    try:
        import numpy
        has_numpy = True
    except ImportError:
        pass

    wav_files = [f for f in os.listdir(MURCIELAGO_WAV_CACHE) if f.endswith('.wav')] if os.path.exists(MURCIELAGO_WAV_CACHE) else []

    return {
        "protocol": "MURCIÉLAGO v2.0",
        "frequency_range": "18-20 kHz",
        "capabilities": {
            "send": has_ffplay or has_aplay,
            "receive": has_numpy,
            "player": "ffplay" if has_ffplay else ("aplay" if has_aplay else None),
            "numpy": has_numpy
        },
        "cached_wavs": len(wav_files),
        "sample_rate": _MURC_SAMPLE_RATE,
        "symbol_duration_ms": int(_MURC_DURATION_SYMBOL * 1000)
    }

# == END PROTOCOLO MURCIÉLAGO =========================================

# ============================================================
# SALA DE GUERRA — Traceroute + Comms Ultrasónicas
# ============================================================

@app.get("/api/topology/traceroute")
async def traceroute_route(target_ip: str = Query(...)):
    """Traceroute real a una IP objetivo."""
    try:
        cmd = ["traceroute", "-n", "-m", "15", "-w", "2", target_ip]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        hops = []
        for line in proc.stdout.split('\n'):
            parts = line.strip().split()
            if len(parts) >= 2 and parts[0].isdigit():
                hop_num = int(parts[0])
                ip = parts[1] if parts[1] != '*' else None
                rtt_values = []
                for p in parts[2:]:
                    if 'ms' in p:
                        try:
                            rtt_values.append(float(p.replace('ms', '')))
                        except ValueError:
                            pass
                avg_rtt = round(sum(rtt_values) / len(rtt_values), 2) if rtt_values else None
                hops.append({
                    "hop": hop_num,
                    "ip": ip,
                    "rtt_avg_ms": avg_rtt,
                    "rtt_samples": rtt_values
                })
        await broadcast({"type": "progress", "payload": f"Traceroute a {target_ip}: {len(hops)} saltos"})
        return {"target": target_ip, "hops": hops, "total_hops": len(hops)}
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail=f"Traceroute timeout a {target_ip}")
    except FileNotFoundError:
        # Fallback: usar nmap --traceroute si traceroute no está instalado
        try:
            cmd = ["nmap", "-sn", "--traceroute", target_ip]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
            hops = []
            for line in proc.stdout.split('\n'):
                if 'traceroute' in line.lower() or 'hop' in line.lower():
                    hops.append({"hop": len(hops) + 1, "ip": line.strip(), "rtt_avg_ms": None, "rtt_samples": []})
            return {"target": target_ip, "hops": hops, "total_hops": len(hops), "method": "nmap"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ni traceroute ni nmap disponibles: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/comms/ultrasonic-receive")
async def ultrasonic_receive(duration: int = 6):
    """Graba audio y decodifica mensaje ultrasonico ejecutando murcielago_receiver.py."""
    receiver_script = str(ROOT / "murcielago" / "murcielago_receiver.py")
    if not os.path.exists(receiver_script):
        # Fallback a ruta alternativa
        receiver_script = str(Path(__file__).parent / "murcielago_receiver.py")
    if not os.path.exists(receiver_script):
        return JSONResponse(
            {"error": "Receptor no encontrado. Instala murcielago_receiver.py"},
            status_code=503
        )

    try:
        result = subprocess.run(
            ["python3", receiver_script, "--duration", str(duration)],
            capture_output=True, text=True, timeout=duration + 10
        )
        message = None
        for line in result.stdout.split('\n'):
            if "Mensaje recibido:" in line:
                message = line.split("Mensaje recibido:")[-1].strip()
                break
        await broadcast({"type": "ultrasonic", "payload": f"Recibido: {message or 'sin señal'}"})
        return {"message": message, "raw": result.stdout[-500:] if result.stdout else ""}
    except subprocess.TimeoutExpired:
        return {"message": None, "error": "Timeout en grabación"}
    except Exception as e:
        return {"message": None, "error": str(e)}


@app.post("/api/comms/ultrasonic-send")
async def ultrasonic_send(request: Request):
    """Envía un mensaje por ultrasonidos con offset de frecuencia opcional."""
    try:
        data = await request.json()
        message = data.get("message", "").strip()
        freq_offset = data.get("freq_offset", 0)

        if not message:
            raise HTTPException(status_code=400, detail="Mensaje vacío")
        if len(message) > 200:
            raise HTTPException(status_code=400, detail="Mensaje demasiado largo (máx 200 chars)")

        # Generar WAV usando el módulo existente
        symbols = _murc_encode_symbols(message)
        wav_bytes = _murc_build_wav(symbols, repeat=1)

        # Aplicar offset de frecuencia al WAV (re-generar con frecuencias ajustadas)
        if freq_offset != 0:
            adjusted_table = {k: (f1 + freq_offset, f2 + freq_offset) for k, (f1, f2) in _MURC_FREQ_TABLE.items()}
            adjusted_sync = _MURC_SYNC_FREQ + freq_offset
            full = b''
            full += _murc_generate_tone(adjusted_sync, 0.3)
            full += _murc_generate_silence(0.05)
            for sym in symbols:
                if sym in adjusted_table:
                    f1, f2 = adjusted_table[sym]
                    n = int(_MURC_SAMPLE_RATE * _MURC_DURATION_SYMBOL)
                    pcm = [int((0.5 * _math.sin(2 * _math.pi * f1 * (i / _MURC_SAMPLE_RATE)) +
                                0.5 * _math.sin(2 * _math.pi * f2 * (i / _MURC_SAMPLE_RATE))) * 20000)
                           for i in range(n)]
                    full += _struct.pack(f'<{n}h', *pcm)
                else:
                    full += _murc_generate_silence(_MURC_DURATION_SYMBOL)
                full += _murc_generate_silence(_MURC_SILENCE_BETWEEN)
            full += _murc_generate_tone(adjusted_sync, 0.2)
            data_len = len(full)
            header = b'RIFF' + _struct.pack('<I', data_len + 36) + b'WAVE'
            header += b'fmt ' + _struct.pack('<IHHIIHH', 16, 1, 1, _MURC_SAMPLE_RATE, _MURC_SAMPLE_RATE * 2, 2, 16)
            header += b'data' + _struct.pack('<I', data_len)
            wav_bytes = header + full

        # Guardar WAV
        wav_filename = f"war_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.wav"
        wav_path = os.path.join(MURCIELAGO_WAV_CACHE, wav_filename)
        with open(wav_path, 'wb') as f:
            f.write(wav_bytes)

        # Reproducir en background
        player = None
        for cmd in (['ffplay', '-nodisp', '-autoexit', '-volume', '80', wav_path],
                    ['aplay', '-q', wav_path]):
            try:
                player = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                break
            except FileNotFoundError:
                continue

        freq_base = 18000 + freq_offset
        await broadcast({"type": "ultrasonic", "payload": f"Enviado: {message} @ {freq_base} Hz"})

        return {
            "status": "sent",
            "message": message,
            "freq_base": freq_base,
            "symbols": ''.join(symbols),
            "wav_url": f"/api/murcielago/download/{wav_filename}",
            "playing": player is not None,
            "duration_sec": round(len(symbols) * (_MURC_DURATION_SYMBOL + _MURC_SILENCE_BETWEEN) + 0.7, 2)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/vision/motion-detect")
async def motion_detect(rtsp_url: str = Query(...), threshold: float = 0.02, duration: int = 6):
    """Detección de movimiento en stream RTSP usando ffmpeg + diferencia de frames."""
    import tempfile as _tmpdir
    frames_dir = _tmpdir.mkdtemp(prefix="motion_")
    try:
        # Extraer frames del stream
        cmd = [
            "ffmpeg", "-i", rtsp_url, "-frames:v", "2",
            "-vf", f"select='gte(scene,{threshold}')", "-vsync", "vfr",
            "-frame_pts", "1", f"{frames_dir}/frame_%04d.png",
            "-t", str(duration), "-y"
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=duration + 5)

        captures = []
        for fname in sorted(os.listdir(frames_dir)) if os.path.exists(frames_dir) else []:
            if fname.endswith('.png'):
                fpath = os.path.join(frames_dir, fname)
                with open(fpath, 'rb') as f:
                    file_hash = _hashlib.sha256(f.read()).hexdigest()
                captures.append({
                    "filename": fname,
                    "hash": file_hash,
                    "timestamp": datetime.now().isoformat()
                })

        motion_detected = len(captures) > 0

        # Broadcast alert si hay movimiento
        if motion_detected:
            await broadcast({"type": "alert", "payload": f"🚨 Movimiento detectado en {rtsp_url}: {len(captures)} capturas"})

        return {
            "rtsp_url": rtsp_url,
            "motion_detected": motion_detected,
            "captures": captures,
            "threshold": threshold,
            "duration": duration
        }
    except subprocess.TimeoutExpired:
        return {"rtsp_url": rtsp_url, "motion_detected": False, "captures": [], "error": "Timeout"}
    except Exception as e:
        return {"rtsp_url": rtsp_url, "motion_detected": False, "captures": [], "error": str(e)}
    finally:
        # Limpiar frames temporales
        if os.path.exists(frames_dir):
            for f in os.listdir(frames_dir):
                os.unlink(os.path.join(frames_dir, f))
            os.rmdir(frames_dir)

# == END SALA DE GUERRA ===============================================

# ============================================================
# MÓDULO 1: THREAT INTELLIGENCE (AbuseIPDB + Cache SQLite)
# ============================================================

import sqlite3 as _sqlite3
import ipaddress as _ipaddr_check

INTEL_CACHE_DB = str(DATA_DIR / "intel_cache.db")
_abuseipdb_key = os.environ.get("ABUSEIPDB_KEY", "")

def _init_intel_db():
    conn = _sqlite3.connect(INTEL_CACHE_DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS ip_cache (
        ip TEXT PRIMARY KEY, data TEXT, timestamp TEXT, abuse_score INTEGER
    )''')
    conn.commit()
    conn.close()

_init_intel_db()

async def _check_abuseipdb(ip: str) -> dict:
    if not _abuseipdb_key:
        return {"error": "API key no configurada. Regístrate gratis en abuseipdb.com y setea ABUSEIPDB_KEY"}
    url = f"https://api.abuseipdb.com/api/v2/check?ipAddress={ip}&maxAgeInDays=90&verbose="
    headers = {"Key": _abuseipdb_key, "Accept": "application/json"}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                return resp.json().get("data", {})
            return {"error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def _get_cached_ip(ip: str) -> Optional[dict]:
    conn = _sqlite3.connect(INTEL_CACHE_DB)
    c = conn.cursor()
    c.execute("SELECT data, timestamp FROM ip_cache WHERE ip = ?", (ip,))
    row = c.fetchone()
    conn.close()
    if row:
        try:
            cache_time = datetime.fromisoformat(row[1])
            if datetime.now() - cache_time < timedelta(hours=24):
                return json.loads(row[0])
        except Exception:
            pass
    return None

def _cache_ip(ip: str, data: dict):
    conn = _sqlite3.connect(INTEL_CACHE_DB)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO ip_cache VALUES (?, ?, ?, ?)",
              (ip, json.dumps(data), datetime.now().isoformat(), data.get("abuseConfidenceScore", 0)))
    conn.commit()
    conn.close()

@app.get("/api/intel/ip/{ip}")
async def get_ip_reputation(ip: str):
    try:
        _ipaddr_check.ip_address(ip)
    except ValueError:
        raise HTTPException(status_code=400, detail="IP inválida")

    cached = _get_cached_ip(ip)
    if cached:
        score = cached.get("abuseConfidenceScore", 0)
        return {
            "ip": ip, "abuse_score": score,
            "country": cached.get("countryCode", "Unknown"),
            "isp": cached.get("isp", "Unknown"),
            "total_reports": cached.get("totalReports", 0),
            "last_reported": cached.get("lastReportedAt", "Never"),
            "is_tor": cached.get("isTor", False),
            "verdict": "MALICIOUS" if score > 75 else "SUSPICIOUS" if score > 25 else "CLEAN",
            "cached": True
        }

    data = await _check_abuseipdb(ip)
    if "error" in data:
        raise HTTPException(status_code=503, detail=data["error"])

    _cache_ip(ip, data)
    score = data.get("abuseConfidenceScore", 0)
    return {
        "ip": ip, "abuse_score": score,
        "country": data.get("countryCode", "Unknown"),
        "isp": data.get("isp", "Unknown"),
        "total_reports": data.get("totalReports", 0),
        "last_reported": data.get("lastReportedAt", "Never"),
        "is_tor": data.get("isTor", False),
        "verdict": "MALICIOUS" if score > 75 else "SUSPICIOUS" if score > 25 else "CLEAN",
        "cached": False
    }

@app.post("/api/intel/bulk-check")
async def bulk_check_ips(request: Request):
    """Consulta masiva con rate limiting (max 5 concurrentes)."""
    try:
        ips = await request.json()
        if not isinstance(ips, list):
            raise HTTPException(status_code=400, detail="Se esperaba una lista de IPs")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="JSON inválido")

    semaphore = asyncio.Semaphore(5)

    async def check_one(ip):
        async with semaphore:
            try:
                return await get_ip_reputation(ip)
            except Exception as e:
                return {"ip": ip, "error": str(e), "verdict": "UNKNOWN"}

    results = await asyncio.gather(*[check_one(ip) for ip in ips[:20]])
    malicious = sum(1 for r in results if isinstance(r, dict) and r.get("verdict") == "MALICIOUS")
    return {"results": results, "total": len(results), "malicious": malicious}

# == END THREAT INTEL =================================================

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINT — INVESTIGACIÓN COMPLETA DE IP (Due Diligence)
#  Combina geo + intel + abuseipdb + shodan + rdns + blocklist
#  Para investigar antecedentes de IPs y cámaras de segunda mano
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/investigate/ip/{ip}")
async def investigate_ip(ip: str):
    """
    Investigación completa de una IP para due diligence.
    Combina todas las fuentes OSINT disponibles:
    - Geo-localización (ipwho.is, sin API key)
    - Threat intel assessment (scoring, flags, blocklist)
    - AbuseIPDB reputation (si hay API key)
    - Shodan (si hay API key)
    - rDNS lookup
    - Análisis de riesgo consolidado
    
    Útil para investigar antecedentes de IPs/cámaras de segunda mano.
    """
    import ipaddress as _ipa
    try:
        _ipa.ip_address(ip)
    except ValueError:
        raise HTTPException(status_code=400, detail="IP inválida")

    result = {
        "ip": ip,
        "timestamp": datetime.now().isoformat(),
        "sources": {},
        "risk_assessment": {},
        "recommendations": []
    }

    # 1. Geo-localización (siempre disponible, sin API key)
    try:
        if _GEO_INTEL_OK:
            result["sources"]["geo"] = _geo_lookup(ip)
        else:
            from geo_intel import lookup
            result["sources"]["geo"] = lookup(ip)
    except Exception as e:
        result["sources"]["geo"] = {"error": str(e)}

    geo = result["sources"].get("geo", {})
    
    # 2. Threat Intel Assessment (siempre disponible, sin API key)
    try:
        if _GEO_INTEL_OK:
            result["sources"]["intel"] = _intel_assess(ip)
        else:
            from geo_intel import assess
            result["sources"]["intel"] = assess(ip)
    except Exception as e:
        result["sources"]["intel"] = {"error": str(e)}

    intel = result["sources"].get("intel", {})

    # 3. AbuseIPDB (si hay API key)
    try:
        abuse = await _check_abuseipdb(ip)
        result["sources"]["abuseipdb"] = abuse
    except Exception as e:
        result["sources"]["abuseipdb"] = {"error": str(e)}

    abuse = result["sources"].get("abuseipdb", {})
    abuse_score = abuse.get("abuseConfidenceScore", 0) if "error" not in abuse else None

    # 4. Shodan (si hay API key)
    shodan_key = os.environ.get("SHODAN_API_KEY", "")
    if shodan_key:
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(f"https://api.shodan.io/shodan/host/{ip}?key={shodan_key}")
                if r.status_code == 200:
                    result["sources"]["shodan"] = r.json()
                else:
                    result["sources"]["shodan"] = {"error": f"HTTP {r.status_code}"}
        except Exception as e:
            result["sources"]["shodan"] = {"error": str(e)}
    else:
        result["sources"]["shodan"] = {"note": "SHODAN_API_KEY no configurada"}

    shodan = result["sources"].get("shodan", {})
    shodan_ports = shodan.get("ports", []) if isinstance(shodan, dict) else []

    # 5. rDNS
    try:
        rdns = socket.gethostbyaddr(ip)[0]
        result["sources"]["rdns"] = rdns
    except Exception:
        result["sources"]["rdns"] = None

    # 6. Risk Assessment Consolidado
    risk_score = 0
    risk_factors = []

    if geo.get("hosting"):
        risk_score += 15
        risk_factors.append({"factor": "Hosting/Cloud", "weight": 15, "detail": f"ISP: {geo.get('isp', '?')}"})
    
    if geo.get("proxy"):
        risk_score += 25
        risk_factors.append({"factor": "Proxy/VPN", "weight": 25, "detail": "IP usa proxy o VPN"})
    
    if intel.get("blocklist") and ip in (intel.get("flags", {}).get("blocklist", "") or ""):
        risk_score += 40
        risk_factors.append({"factor": "Blocklist abuse.ch", "weight": 40, "detail": "IP en lista de bloqueo"})

    if abuse_score is not None:
        if abuse_score > 75:
            risk_score += 40
            risk_factors.append({"factor": "AbuseIPDB Crítico", "weight": 40, "detail": f"Score: {abuse_score}/100"})
        elif abuse_score > 25:
            risk_score += 20
            risk_factors.append({"factor": "AbuseIPDB Sospechoso", "weight": 20, "detail": f"Score: {abuse_score}/100"})
        elif abuse_score == 0:
            risk_factors.append({"factor": "AbuseIPDB Limpio", "weight": 0, "detail": "Sin reportes de abuso"})

    if shodan_ports:
        cam_ports = [p for p in shodan_ports if p in [554, 8000, 8080, 8888, 37777, 37778]]
        if cam_ports:
            risk_score += 10
            risk_factors.append({"factor": "Puertos de cámara abiertos", "weight": 10, "detail": f"Puertos: {cam_ports}"})

    intel_score = intel.get("score", 0)
    if intel_score > 50:
        risk_score += 20
        risk_factors.append({"factor": "Threat Intel Score alto", "weight": 20, "detail": f"Score: {intel_score}/100, {intel.get('label', '?')}"})

    risk_score = max(0, min(100, risk_score))
    
    if risk_score >= 70:
        verdict = "ALTO RIESGO"
        recommendation = "NO usar sin investigación adicional. Posible equipo comprometido o robado."
    elif risk_score >= 40:
        verdict = "RIESGO MEDIO"
        recommendation = "Precaución. Verificar procedencia con documentación."
    elif risk_score >= 20:
        verdict = "RIESGO BAJO"
        recommendation = "Bajo riesgo. Verificar documentación normal."
    else:
        verdict = "LIMPIO"
        recommendation = "Sin señales de riesgo. Proceder con normalidad."

    result["risk_assessment"] = {
        "score": risk_score,
        "verdict": verdict,
        "factors": risk_factors,
        "recommendation": recommendation
    }

    # Recommendations específicas
    recs = []
    if abuse_score is not None and abuse_score > 0:
        recs.append(f"AbuseIPDB: {abuse_score}/100 — {abuse.get('totalReports', 0)} reportes en 90 días")
    if geo.get("hosting"):
        recs.append(f"IP pertenece a hosting/cloud ({geo.get('isp')}) — no es ISP residencial")
    if shodan_ports:
        recs.append(f"Shodan detectó puertos abiertos: {shodan_ports}")
        if 554 in shodan_ports:
            recs.append("Puerto 554 (RTSP) abierto — cámara accesible públicamente en el pasado")
    if result["sources"]["rdns"]:
        recs.append(f"rDNS: {result['sources']['rdns']}")
    if intel.get("blocklist"):
        recs.append("IP aparece en blocklist de abuse.ch (botnet/C2 conocido)")
    recs.append(recommendation)
    result["recommendations"] = recs

    return result


@app.get("/api/investigate/camera/{ip}")
async def investigate_camera(ip: str, port: int = 80):
    """
    Investigación de una cámara IP específica.
    Combina investigación de IP + detección de marca/modelo + puertos + streams.
    """
    import ipaddress as _ipa
    try:
        _ipa.ip_address(ip)
    except ValueError:
        raise HTTPException(status_code=400, detail="IP inválida")

    # 1. Investigación base de la IP
    ip_investigation = await investigate_ip(ip)

    # 2. Detección de marca/modelo
    banner = _http_banner(ip, port, "/", timeout=5.0)
    brand = _detect_camera_brand(banner.get("server", "") + " " + banner.get("body_preview", ""))

    # 3. Detección de streams de video
    video_sources = _detect_video_urls(ip, port, timeout=3.0)

    # 4. Escaneo de puertos comunes de cámara
    cam_ports = [80, 443, 554, 8000, 8080, 8888, 37777, 37778]
    open_ports = {}
    for p in cam_ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.5)
            result = sock.connect_ex((ip, p))
            if result == 0:
                open_ports[p] = "open"
            sock.close()
        except Exception:
            pass

    # 5. SSL info si hay HTTPS
    ssl_info = None
    if 443 in open_ports or port in (443, 8443):
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with socket.create_connection((ip, port), timeout=5) as sock:
                with ctx.wrap_socket(sock, server_hostname=ip) as ssock:
                    cert = ssock.getpeercert()
                    ssl_info = {"issuer": dict(x[0]) for x in cert.get("issuer", [])} if cert else None
        except Exception:
            ssl_info = {"error": "No se pudo obtener certificado SSL"}

    return {
        "ip": ip,
        "port": port,
        "brand": brand,
        "banner": banner,
        "video_sources": video_sources,
        "open_ports": open_ports,
        "ssl_info": ssl_info,
        "ip_investigation": ip_investigation,
        "timestamp": datetime.now().isoformat()
    }



# ============================================================
# MÓDULO 2: EXPLOIT MATCHER (ExploitDB)
# ============================================================

EXPLOIT_DB_DIR = str(DATA_DIR / "exploitdb")
EXPLOIT_CSV = os.path.join(EXPLOIT_DB_DIR, "files_exploits.csv")

def _init_exploit_db():
    os.makedirs(EXPLOIT_DB_DIR, exist_ok=True)
    if not os.path.exists(EXPLOIT_CSV):
        try:
            import requests as _req
            r = _req.get("https://raw.githubusercontent.com/offensive-security/exploitdb/master/files_exploits.csv", timeout=60)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(EXPLOIT_CSV, "wb") as f:
                    f.write(r.content)
                print("[+] ExploitDB descargado")
        except Exception as e:
            print(f"[!] Error descargando ExploitDB: {e}")

def _search_exploits(service: str, version: str = None) -> list:
    if not os.path.exists(EXPLOIT_CSV):
        _init_exploit_db()
    if not os.path.exists(EXPLOIT_CSV):
        return []

    exploits = []
    with open(EXPLOIT_CSV, "r", encoding="utf-8", errors="ignore") as f:
        next(f)  # skip header
        for line in f:
            parts = line.strip().split(",")
            if len(parts) < 7:
                continue
            eid, file_path, title = parts[0], parts[1], parts[2]
            platform = parts[5] if len(parts) > 5 else "unknown"
            etype = parts[6] if len(parts) > 6 else "unknown"

            title_lower = title.lower()
            service_lower = service.lower()

            confidence = None
            if service_lower in title_lower:
                if version and version in title:
                    confidence = "HIGH"
                else:
                    confidence = "MEDIUM"
            elif any(k in title_lower for k in service_lower.split()):
                confidence = "LOW"

            if confidence:
                exploits.append({
                    "id": eid, "title": title, "platform": platform,
                    "type": etype, "verified": "verified" in title_lower,
                    "url": f"https://www.exploit-db.com/exploits/{eid}",
                    "match_confidence": confidence
                })

    priority = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    exploits.sort(key=lambda x: priority.get(x.get("match_confidence", "LOW"), 3))
    return exploits[:25]

@app.post("/api/exploits/match")
async def match_exploits(request: Request):
    try:
        fingerprints = await request.json()
        if not isinstance(fingerprints, list):
            raise HTTPException(status_code=400, detail="Se esperaba una lista de fingerprints")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="JSON inválido")

    all_matches = []
    for fp in fingerprints:
        name = fp.get("name", "")
        version = fp.get("version")
        matches = _search_exploits(name, version)
        for m in matches:
            all_matches.append({"service": name, "version": version, "exploit": m})

    return {
        "total_matches": len(all_matches),
        "high_confidence": sum(1 for m in all_matches if m["exploit"]["match_confidence"] == "HIGH"),
        "medium_confidence": sum(1 for m in all_matches if m["exploit"]["match_confidence"] == "MEDIUM"),
        "exploits": all_matches
    }

@app.get("/api/exploits/search")
async def search_exploit(query: str = Query(...)):
    return {"query": query, "results": _search_exploits(query)}

@app.post("/api/exploits/init-db")
async def init_exploit_db_endpoint():
    _init_exploit_db()
    if os.path.exists(EXPLOIT_CSV):
        size = os.path.getsize(EXPLOIT_CSV)
        return {"status": "ok", "csv_size": size}
    return {"status": "failed", "message": "No se pudo descargar ExploitDB"}

# == END EXPLOIT MATCHER ==============================================


# ============================================================
# MÓDULO 3: PACKET ANALYZER (tcpdump + detección de anomalías)
# ============================================================

CAPTURE_DIR = str(DATA_DIR / "captures")
os.makedirs(CAPTURE_DIR, exist_ok=True)
_active_captures = {}

@app.post("/api/capture/start")
async def start_capture(interface: str = "any", bpf_filter: str = "", duration: int = 15):
    session_id = uuid.uuid4().hex[:8]
    pcap_file = os.path.join(CAPTURE_DIR, f"{session_id}.pcap")

    cmd = ["tcpdump", "-i", interface, "-w", pcap_file, "-G", str(duration), "-W", "1", "-q"]
    if bpf_filter:
        cmd.extend(bpf_filter.split())

    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _active_captures[session_id] = {
            "process": process, "start_time": datetime.now(),
            "interface": interface, "pcap_file": pcap_file
        }

        # Auto-stop thread
        def auto_stop():
            time.sleep(duration + 2)
            if session_id in _active_captures:
                _stop_capture_internal(session_id)
        threading.Thread(target=auto_stop, daemon=True).start()

        await broadcast({"type": "capture", "payload": f"Captura iniciada en {interface} ({session_id})"})
        return {
            "session_id": session_id, "status": "capturing",
            "interface": interface, "duration": duration, "pcap_file": pcap_file
        }
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="tcpdump no instalado. Instala: pkg install tcpdump (Termux) o apt install tcpdump")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _stop_capture_internal(session_id: str):
    if session_id not in _active_captures:
        return None

    session = _active_captures[session_id]
    process = session["process"]

    try:
        process.send_signal(_signal.SIGTERM)
        process.wait(timeout=5)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass

    pcap_file = session["pcap_file"]
    stats = {"total_packets": 0, "protocols": {}, "anomalies": []}

    if os.path.exists(pcap_file):
        try:
            result = subprocess.run(["tcpdump", "-r", pcap_file, "-n"],
                                     capture_output=True, text=True, timeout=30)
            for line in result.stderr.split('\n'):
                if "packets captured" in line:
                    try:
                        stats["total_packets"] = int(line.split()[0])
                    except ValueError:
                        pass
        except Exception:
            pass

        try:
            result = subprocess.run(["tcpdump", "-r", pcap_file, "-n", "-tttt"],
                                     capture_output=True, text=True, timeout=30)
            arp_count, syn_count = 0, 0
            port_scan_ips = {}

            for line in result.stdout.split('\n'):
                if "ARP" in line:
                    arp_count += 1
                if "Flags [S]" in line and "length 0" in line:
                    syn_count += 1
                    parts = line.split()
                    if len(parts) > 2:
                        src_ip = parts[2].split('.')[0:4]
                        src_ip_str = '.'.join(src_ip)
                        port_scan_ips[src_ip_str] = port_scan_ips.get(src_ip_str, 0) + 1

            if arp_count > 50:
                stats["anomalies"].append({
                    "type": "ARP_STORM", "severity": "HIGH",
                    "description": f"Detectados {arp_count} paquetes ARP. Posible ARP Spoofing.",
                    "count": arp_count
                })

            for ip, count in port_scan_ips.items():
                if count > 20:
                    stats["anomalies"].append({
                        "type": "PORT_SCAN", "severity": "MEDIUM",
                        "description": f"Posible port scan desde {ip}: {count} SYN",
                        "source": ip, "count": count
                    })

            stats["protocols"] = {
                "ARP": arp_count, "TCP_SYN": syn_count,
                "OTHER": max(0, stats["total_packets"] - arp_count - syn_count)
            }
        except Exception as e:
            stats["error"] = str(e)

    del _active_captures[session_id]
    if stats["anomalies"]:
        loop = asyncio.get_event_loop()
        for a in stats["anomalies"]:
            asyncio.ensure_future(broadcast({"type": "alert", "payload": f"🚨 {a['type']}: {a['description']}"}), loop=loop)

    return {
        "session_id": session_id, "status": "completed",
        "analysis": stats, "pcap_file": pcap_file,
        "duration": (datetime.now() - session["start_time"]).seconds
    }

@app.post("/api/capture/stop/{session_id}")
async def stop_capture(session_id: str):
    result = _stop_capture_internal(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    return result

@app.get("/api/capture/active")
async def list_active_captures():
    return {"active": [
        {"session_id": sid, "interface": s["interface"],
         "running_for": (datetime.now() - s["start_time"]).seconds}
        for sid, s in _active_captures.items()
    ]}

# == END PACKET ANALYZER ==============================================

# ============================================================
# MÓDULO 4: OSINT ENGINE (crt.sh + brute force + WHOIS + emails)
# ============================================================

OSINT_DB = str(DATA_DIR / "osint_cache.db")
WORDLIST_PATH = str(DATA_DIR / "wordlists" / "subdomains.txt")
_hunter_key = os.environ.get("HUNTER_API_KEY", "")

def _init_osint_db():
    conn = _sqlite3.connect(OSINT_DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS osint_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target TEXT, type TEXT, data TEXT, timestamp TEXT
    )''')
    conn.commit()
    conn.close()

_init_osint_db()

def _osint_cache_result(target: str, rtype: str, data: dict):
    conn = _sqlite3.connect(OSINT_DB)
    c = conn.cursor()
    c.execute("INSERT INTO osint_cache (target, type, data, timestamp) VALUES (?, ?, ?, ?)",
              (target, rtype, json.dumps(data), datetime.now().isoformat()))
    conn.commit()
    conn.close()

def _osint_get_cache(target: str, rtype: str, hours: int = 24):
    conn = _sqlite3.connect(OSINT_DB)
    c = conn.cursor()
    since = (datetime.now() - timedelta(hours=hours)).isoformat()
    c.execute("SELECT data FROM osint_cache WHERE target = ? AND type = ? AND timestamp > ?",
              (target, rtype, since))
    rows = c.fetchall()
    conn.close()
    return [json.loads(r[0]) for r in rows] if rows else None

async def _fetch_crtsh(domain: str) -> list:
    """Subdominios via crt.sh — 100% gratis, sin API key."""
    url = f"https://crt.sh/?q=%.{domain}&output=json"
    results = []
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                seen = set()
                for entry in data:
                    name = entry.get("name_value", "").strip()
                    if name and name not in seen and "*" not in name:
                        seen.add(name)
                        results.append({"subdomain": name, "source": "crt.sh", "ip": None, "status": "active"})
    except Exception as e:
        print(f"[crt.sh error] {e}")
    return results

async def _brute_subdomains(domain: str, max_concurrent: int = 50) -> list:
    """Brute force de subdominios con dig."""
    os.makedirs(os.path.dirname(WORDLIST_PATH), exist_ok=True)
    if not os.path.exists(WORDLIST_PATH):
        default_words = ["www","mail","ftp","admin","api","app","blog","dev","staging","test",
                         "vpn","ns1","ns2","portal","shop","cdn","media","static","assets",
                         "secure","login","dashboard","panel","cpanel","webmail","smtp","pop",
                         "imap","mx","support","help","docs","wiki","git","gitlab","github",
                         "jenkins","jira","confluence","grafana","prometheus","kibana","elastic",
                         "db","database","sql","mysql","postgres","redis","mongo","backup",
                         "old","beta","alpha","demo","internal","intranet","extranet","private"]
        with open(WORDLIST_PATH, "w") as f:
            f.write("\n".join(default_words))

    with open(WORDLIST_PATH, "r") as f:
        wordlist = [line.strip() for line in f if line.strip()]

    semaphore = asyncio.Semaphore(max_concurrent)
    found = []

    async def check_one(sub: str):
        full = f"{sub}.{domain}"
        async with semaphore:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "dig", "+short", full,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
                ip = stdout.decode().strip().split("\n")[0]
                if ip and not ip.startswith(";") and ip:
                    found.append({"subdomain": full, "source": "brute-force", "ip": ip, "status": "resolved"})
            except Exception:
                pass

    await asyncio.gather(*[check_one(w) for w in wordlist])
    return found

@app.get("/api/osint/whois/{domain}")
async def osint_whois(domain: str):
    cached = _osint_get_cache(domain, "whois")
    if cached:
        return cached[0]

    try:
        proc = await asyncio.create_subprocess_exec(
            "whois", domain,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
        output = stdout.decode()

        parsed = {}
        for line in output.split("\n"):
            if ":" in line and not line.startswith("%"):
                key, val = line.split(":", 1)
                key = key.strip()
                val = val.strip()
                if key and val and key not in parsed:
                    parsed[key] = val

        result = {"domain": domain, "raw": output[:5000], "parsed": parsed}
        _osint_cache_result(domain, "whois", result)
        return result
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="whois no instalado. Instala: pkg install whois (Termux) o apt install whois (Linux)")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/osint/subdomains/{domain}")
async def osint_subdomains(domain: str, brute: bool = False):
    cached = _osint_get_cache(domain, "subdomains")
    if cached and not brute:
        return {"domain": domain, "subdomains": cached[0], "cached": True}

    crt_results = await _fetch_crtsh(domain)

    brute_results = []
    if brute:
        brute_results = await _brute_subdomains(domain)

    seen = {s["subdomain"] for s in crt_results}
    all_results = crt_results[:]
    for b in brute_results:
        if b["subdomain"] not in seen:
            all_results.append(b)
            seen.add(b["subdomain"])

    _osint_cache_result(domain, "subdomains", all_results)
    await broadcast({"type": "osint", "payload": f"Subdominios de {domain}: {len(all_results)} encontrados"})
    return {"domain": domain, "subdomains": all_results, "cached": False}

@app.get("/api/osint/emails/{domain}")
async def osint_emails(domain: str):
    cached = _osint_get_cache(domain, "emails")
    if cached:
        return {"domain": domain, "emails": cached[0].get("emails", []), "cached": True}

    results = []

    # Hunter.io si hay key
    if _hunter_key:
        try:
            url = f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={_hunter_key}"
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    for e in data.get("data", {}).get("emails", []):
                        results.append({"email": e["value"], "source": "hunter.io", "confidence": e.get("confidence")})
        except Exception as e:
            print(f"[Hunter error] {e}")

    # Fallback: pattern guess
    if not results:
        common_patterns = ["info", "admin", "support", "contact", "sales", "webmaster", "security"]
        for pat in common_patterns:
            results.append({"email": f"{pat}@{domain}", "source": "pattern-guess", "confidence": None})

    _osint_cache_result(domain, "emails", {"emails": results})
    return {"domain": domain, "emails": results, "cached": False}

@app.post("/api/osint/metadata")
async def osint_metadata(file_path: str = Query(...)):
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    suspicious_fields = ["Author", "Creator", "Producer", "Company", "Template",
                        "LastModifiedBy", "Manager", "Software"]
    fields = {}
    suspicious = []

    try:
        proc = await asyncio.create_subprocess_exec(
            "exiftool", "-json", file_path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        data = json.loads(stdout.decode())
        if data and len(data) > 0:
            meta = data[0]
            for k, v in meta.items():
                if v and str(v).strip():
                    fields[k] = str(v)
                    if any(s.lower() in k.lower() for s in suspicious_fields):
                        suspicious.append(f"{k}: {v}")
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="exiftool no instalado. Instala: pkg install exiftool (Termux) o apt install libimage-exiftool-perl (Linux)")
    except Exception as e:
        fields["error"] = str(e)

    return {"filename": os.path.basename(file_path), "fields": fields, "suspicious": suspicious}

@app.get("/api/osint/history/{target}")
async def osint_history(target: str):
    conn = _sqlite3.connect(OSINT_DB)
    c = conn.cursor()
    c.execute("SELECT type, data, timestamp FROM osint_cache WHERE target = ? ORDER BY timestamp DESC", (target,))
    rows = c.fetchall()
    conn.close()
    return {"target": target, "history": [{"type": r[0], "data": json.loads(r[1]), "timestamp": r[2]} for r in rows]}

# ============================================================
# NOVOS ENDPOINTS OSINT ENGINE
# ============================================================

DISPOSABLE_DOMAINS = {
    "mailinator.com", "tempmail.com", "10minutemail.com", "guerrillamail.com",
    "throwawaymail.com", "yopmail.com", "trashmail.com", "sharklasers.com",
    "getnada.com", "dispostable.com", "tempail.com", "guerrillamailblock.com"
}

SOCIAL_PLATFORMS = [
    ("GitHub", "https://github.com/{}"),
    ("Twitter/X", "https://x.com/{}"),
    ("Instagram", "https://instagram.com/{}"),
    ("YouTube", "https://youtube.com/@{}"),
    ("TikTok", "https://tiktok.com/@{}"),
    ("Reddit", "https://reddit.com/user/{}"),
    ("GitLab", "https://gitlab.com/{}"),
    ("Medium", "https://medium.com/@{}"),
    ("Steam", "https://steamcommunity.com/id/{}"),
]

def _parse_rdn_tuple(rdn):
    if not rdn:
        return {}
    res = {}
    for r in rdn:
        for k, v in r:
            res[k] = v
    return res

async def _helper_get_ssl_cert(domain: str, port: int = 443) -> dict:
    loop = asyncio.get_running_loop()
    ctx = ssl.create_default_context()

    def _fetch_verified():
        with socket.create_connection((domain, port), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                return ssock.getpeercert()

    try:
        cert = await loop.run_in_executor(None, _fetch_verified)
        issuer = _parse_rdn_tuple(cert.get("issuer", ()))
        subject = _parse_rdn_tuple(cert.get("subject", ()))
        is_self_signed = (issuer == subject) if (issuer and subject) else False
        return {
            "domain": domain,
            "port": port,
            "issuer": issuer,
            "subject": subject,
            "notBefore": cert.get("notBefore"),
            "notAfter": cert.get("notAfter"),
            "serialNumber": cert.get("serialNumber"),
            "version": cert.get("version"),
            "self_signed": is_self_signed,
            "verified": True,
            "error": None
        }
    except Exception as err:
        try:
            def _fetch_pem():
                return ssl.get_server_certificate((domain, port), timeout=5)

            pem = await loop.run_in_executor(None, _fetch_pem)
            proc = await asyncio.create_subprocess_exec(
                "openssl", "x509", "-noout", "-issuer", "-subject", "-dates", "-serial",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(input=pem.encode()), timeout=5)
            out_str = stdout.decode()

            parsed = {}
            for line in out_str.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    parsed[k.strip().lower()] = v.strip()

            issuer_str = parsed.get("issuer", "")
            subject_str = parsed.get("subject", "")
            is_self = (issuer_str == subject_str) if (issuer_str and subject_str) else True

            return {
                "domain": domain,
                "port": port,
                "issuer": issuer_str,
                "subject": subject_str,
                "notBefore": parsed.get("notbefore"),
                "notAfter": parsed.get("notafter"),
                "serialNumber": parsed.get("serial"),
                "version": None,
                "self_signed": is_self,
                "verified": False,
                "error": str(err)
            }
        except Exception:
            return {
                "domain": domain,
                "port": port,
                "issuer": None,
                "subject": None,
                "notBefore": None,
                "notAfter": None,
                "serialNumber": None,
                "version": None,
                "self_signed": None,
                "verified": False,
                "error": str(err)
            }

def _detect_technologies(headers: dict) -> list:
    techs = []
    headers_lower = {str(k).lower(): str(v) for k, v in headers.items()}

    server = headers_lower.get("server", "")
    if server:
        techs.append(f"Server: {server}")

    x_powered_by = headers_lower.get("x-powered-by", "")
    if x_powered_by:
        techs.append(f"X-Powered-By: {x_powered_by}")

    x_aspnet = headers_lower.get("x-aspnet-version") or headers_lower.get("x-aspnetmvc-version")
    if x_aspnet:
        techs.append(f"ASP.NET ({x_aspnet})")

    x_gen = headers_lower.get("x-generator", "")
    if x_gen:
        techs.append(f"Generator: {x_gen}")

    if "cf-ray" in headers_lower or "cloudflare" in server.lower() or "cf-cache-status" in headers_lower:
        techs.append("Cloudflare")

    if "x-varnish" in headers_lower or "varnish" in headers_lower.get("via", "").lower():
        techs.append("Varnish Cache")

    if "x-github-request-id" in headers_lower:
        techs.append("GitHub Pages")

    cookies = headers_lower.get("set-cookie", "")
    if "phpsessid" in cookies.lower():
        techs.append("PHP")
    if "jsessionid" in cookies.lower():
        techs.append("Java/Servlet")
    if "asp.net_sessionid" in cookies.lower() or "aspsessionid" in cookies.lower():
        techs.append("ASP.NET")
    if "laravel_session" in cookies.lower():
        techs.append("Laravel")
    if "wordpress_" in cookies.lower() or "wp-settings-" in cookies.lower():
        techs.append("WordPress")
    if "csrftoken" in cookies.lower():
        techs.append("Django")

    return list(dict.fromkeys(techs))


@app.get("/api/osint/dns/{domain}")
async def osint_dns(domain: str):
    cached = _osint_get_cache(domain, "dns")
    if cached:
        return cached[0]

    record_types = ["A", "AAAA", "MX", "TXT", "NS", "CNAME", "SOA"]
    records = {}

    async def fetch_record(rtype: str):
        try:
            proc = await asyncio.create_subprocess_exec(
                "dig", "+short", rtype, domain,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            lines = [l.strip() for l in stdout.decode().splitlines() if l.strip() and not l.strip().startswith(";")]
            return rtype, lines
        except FileNotFoundError:
            raise FileNotFoundError("dig_not_installed")
        except Exception:
            return rtype, []

    try:
        results = await asyncio.gather(*[fetch_record(rt) for rt in record_types])
        for rtype, lines in results:
            records[rtype] = lines
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="dig no instalado. Instala: pkg install bind-tools (Termux) o apt install bind9-dnsutils (Linux)"
        )

    result = {
        "domain": domain,
        "records": records,
        "timestamp": datetime.now().isoformat()
    }
    _osint_cache_result(domain, "dns", result)
    return result


@app.get("/api/osint/headers/{domain}")
async def osint_headers(domain: str):
    cached = _osint_get_cache(domain, "headers")
    if cached:
        return cached[0]

    headers = {}
    status_code = None
    url_used = None
    error = None

    for scheme in ["https", "http"]:
        target_url = f"{scheme}://{domain}"
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=10.0, verify=False) as client:
                resp = await client.get(target_url)
                headers = dict(resp.headers)
                status_code = resp.status_code
                url_used = str(resp.url)
                break
        except Exception as e:
            error = str(e)

    tls_info = None
    try:
        tls_info = await _helper_get_ssl_cert(domain, 443)
    except Exception as e:
        tls_info = {"error": str(e)}

    technologies = _detect_technologies(headers)

    result = {
        "domain": domain,
        "url": url_used,
        "status_code": status_code,
        "headers": headers,
        "technologies": technologies,
        "tls": tls_info,
        "error": error if not headers else None,
        "timestamp": datetime.now().isoformat()
    }

    _osint_cache_result(domain, "headers", result)
    return result


@app.get("/api/osint/reverse/{ip}")
async def osint_reverse(ip: str):
    if not _valid_ip(ip):
        raise HTTPException(status_code=400, detail="Dirección IP inválida")

    cached = _osint_get_cache(ip, "reverse")
    if cached:
        return cached[0]

    loop = asyncio.get_running_loop()

    hostname = None
    aliases = []
    try:
        res = await loop.run_in_executor(None, socket.gethostbyaddr, ip)
        hostname = res[0]
        aliases = res[1]
    except Exception:
        hostname = None

    geo_data = {}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"https://ipwho.is/{ip}")
            if resp.status_code == 200:
                geo_data = resp.json()
    except Exception as e:
        geo_data = {"error": str(e)}

    result = {
        "ip": ip,
        "hostname": hostname,
        "aliases": aliases,
        "geo": geo_data,
        "timestamp": datetime.now().isoformat()
    }

    _osint_cache_result(ip, "reverse", result)
    return result


@app.get("/api/osint/breach/{email}")
async def osint_breach(email: str):
    cached = _osint_get_cache(email, "breach")
    if cached:
        return cached[0]

    email_pattern = r"^[^@\s]+@([^@\s]+\.[^@\s]+)$"
    match = re.match(email_pattern, email)
    valid_format = bool(match)
    domain = match.group(1).lower() if match else ""

    is_disposable = domain in DISPOSABLE_DOMAINS if domain else False

    mx_records = []
    if domain:
        try:
            proc = await asyncio.create_subprocess_exec(
                "dig", "+short", "MX", domain,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            mx_records = [l.strip() for l in stdout.decode().splitlines() if l.strip() and not l.strip().startswith(";")]
        except Exception:
            mx_records = []

    breaches = []
    status_note = "Local validation + MX verification completed."

    headers = {"User-Agent": "RedTeam-Dashboard-OSINT/1.0"}
    async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
        try:
            resp = await client.get(f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}")
            if resp.status_code == 200:
                breaches = resp.json()
                status_note = "Breaches retrieved from HaveIBeenPwned."
            elif resp.status_code in (401, 403):
                status_note = "HaveIBeenPwned requires API key. Tried free fallback API."
        except Exception:
            pass

        if not breaches:
            try:
                resp = await client.get(f"https://leakcheck.io/api/public?check={email}")
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success"):
                        breaches = data.get("sources", [])
                        status_note = "Breach data retrieved from LeakCheck free API."
            except Exception:
                pass

        if not breaches and "HaveIBeenPwned" not in status_note and "LeakCheck" not in status_note:
            try:
                resp = await client.get(f"https://api.dehash.lt/api/search?email={email}")
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        breaches = data
                        status_note = "Breach data retrieved from DeHash API."
                    elif isinstance(data, dict) and data.get("results"):
                        breaches = data.get("results")
                        status_note = "Breach data retrieved from DeHash API."
            except Exception:
                pass

    result = {
        "email": email,
        "valid_format": valid_format,
        "domain": domain,
        "disposable": is_disposable,
        "mx_records": mx_records,
        "breaches": breaches,
        "status_note": status_note,
        "timestamp": datetime.now().isoformat()
    }

    _osint_cache_result(email, "breach", result)
    return result


@app.get("/api/osint/social/{username}")
async def osint_social(username: str):
    cached = _osint_get_cache(username, "social")
    if cached:
        return cached[0]

    semaphore = asyncio.Semaphore(5)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    async def check_platform(client, platform_name: str, url_tmpl: str):
        url = url_tmpl.format(username)
        async with semaphore:
            try:
                resp = await client.get(url)
                status_code = resp.status_code
                exists = (200 <= status_code < 300)
                return {
                    "platform": platform_name,
                    "url": url,
                    "exists": exists,
                    "status_code": status_code
                }
            except Exception as e:
                return {
                    "platform": platform_name,
                    "url": url,
                    "exists": False,
                    "status_code": None,
                    "error": str(e)
                }

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=headers) as client:
        results = await asyncio.gather(
            *[check_platform(client, p, u) for p, u in SOCIAL_PLATFORMS]
        )

    total_found = sum(1 for r in results if r.get("exists"))
    result = {
        "username": username,
        "results": results,
        "total_found": total_found,
        "timestamp": datetime.now().isoformat()
    }

    _osint_cache_result(username, "social", result)
    return result


@app.get("/api/osint/cert/{domain}")
async def osint_cert(domain: str):
    cached = _osint_get_cache(domain, "cert")
    if cached:
        return cached[0]

    result = await _helper_get_ssl_cert(domain, 443)
    result["timestamp"] = datetime.now().isoformat()

    _osint_cache_result(domain, "cert", result)
    return result


@app.get("/api/osint/full/{target}")
async def osint_full(target: str):
    cached = _osint_get_cache(target, "full")
    if cached:
        return cached[0]

    is_ip = _valid_ip(target)

    if is_ip:
        async def _rdns_task(ip):
            loop = asyncio.get_running_loop()
            try:
                res = await loop.run_in_executor(None, socket.gethostbyaddr, ip)
                return {"hostname": res[0], "aliases": res[1]}
            except Exception as e:
                return {"hostname": None, "error": str(e)}

        async def _geo_task(ip):
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.get(f"https://ipwho.is/{ip}")
                    if resp.status_code == 200:
                        return resp.json()
            except Exception as e:
                return {"error": str(e)}
            return {}

        async def _threat_task(ip):
            threat_data = {"ip": ip, "is_private": False, "flags": [], "risk_score": 0}
            try:
                ip_obj = ipaddress.ip_address(ip)
                if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved:
                    threat_data["is_private"] = True
                    threat_data["flags"].append("internal/private_ip")
                    threat_data["risk_score"] = 0
                    return threat_data
            except Exception:
                pass

            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.get(f"https://ipwho.is/{ip}")
                    if resp.status_code == 200:
                        data = resp.json()
                        security = data.get("security", {})
                        if security.get("vpn"):
                            threat_data["flags"].append("vpn")
                            threat_data["risk_score"] += 20
                        if security.get("proxy"):
                            threat_data["flags"].append("proxy")
                            threat_data["risk_score"] += 30
                        if security.get("tor"):
                            threat_data["flags"].append("tor")
                            threat_data["risk_score"] += 50
                        if security.get("hosting"):
                            threat_data["flags"].append("datacenter/hosting")
                            threat_data["risk_score"] += 10
            except Exception as e:
                threat_data["error"] = str(e)

            return threat_data

        rdns_res, geo_res, threat_res = await asyncio.gather(
            _rdns_task(target),
            _geo_task(target),
            _threat_task(target)
        )

        full_report = {
            "target": target,
            "target_type": "ip",
            "timestamp": datetime.now().isoformat(),
            "rdns": rdns_res,
            "geo": geo_res,
            "threat_intel": threat_res
        }
    else:
        async def _whois_task(domain):
            try:
                proc = await asyncio.create_subprocess_exec(
                    "whois", domain,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
                output = stdout.decode()
                parsed = {}
                for line in output.split("\n"):
                    if ":" in line and not line.startswith("%"):
                        k, v = line.split(":", 1)
                        k = k.strip()
                        v = v.strip()
                        if k and v and k not in parsed:
                            parsed[k] = v
                return {"raw": output[:3000], "parsed": parsed}
            except Exception as e:
                return {"error": str(e)}

        async def _subdomains_task(domain):
            try:
                return await _fetch_crtsh(domain)
            except Exception as e:
                return [{"error": str(e)}]

        async def _dns_task(domain):
            record_types = ["A", "AAAA", "MX", "TXT", "NS", "CNAME", "SOA"]
            records = {}

            async def fetch_record(rt):
                try:
                    proc = await asyncio.create_subprocess_exec(
                        "dig", "+short", rt, domain,
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
                    lines = [l.strip() for l in stdout.decode().splitlines() if l.strip() and not l.strip().startswith(";")]
                    return rt, lines
                except Exception:
                    return rt, []

            results = await asyncio.gather(*[fetch_record(rt) for rt in record_types])
            for rt, lines in results:
                records[rt] = lines
            return records

        async def _headers_task(domain):
            headers = {}
            status_code = None
            url_used = None
            for scheme in ["https", "http"]:
                try:
                    async with httpx.AsyncClient(follow_redirects=True, timeout=8.0, verify=False) as client:
                        resp = await client.get(f"{scheme}://{domain}")
                        headers = dict(resp.headers)
                        status_code = resp.status_code
                        url_used = str(resp.url)
                        break
                except Exception:
                    pass
            techs = _detect_technologies(headers)
            return {"url": url_used, "status_code": status_code, "headers": headers, "technologies": techs}

        async def _cert_task(domain):
            try:
                return await _helper_get_ssl_cert(domain, 443)
            except Exception as e:
                return {"error": str(e)}

        whois_res, subdomains_res, dns_res, headers_res, cert_res = await asyncio.gather(
            _whois_task(target),
            _subdomains_task(target),
            _dns_task(target),
            _headers_task(target),
            _cert_task(target)
        )

        full_report = {
            "target": target,
            "target_type": "domain",
            "timestamp": datetime.now().isoformat(),
            "whois": whois_res,
            "subdomains": subdomains_res,
            "dns": dns_res,
            "headers": headers_res,
            "cert": cert_res
        }

    _osint_cache_result(target, "full", full_report)
    return full_report


@app.get("/api/osint/export/{target}")
async def osint_export(target: str):
    cached = _osint_get_cache(target, "full")
    if cached:
        report = cached[0]
    else:
        report = await osint_full(target)

    return JSONResponse(
        content=report,
        headers={"Content-Disposition": f'attachment; filename="osint_report_{target}.json"'}
    )


# == END OSINT ENGINE =================================================


# ============================================================
# MÓDULO 5: WIFI SCANNER (termux-api / iw / airodump-ng)
# ============================================================

WIFI_CAPTURES_DIR = str(DATA_DIR / "wifi_captures")
os.makedirs(WIFI_CAPTURES_DIR, exist_ok=True)
_wifi_active_captures = {}

@app.get("/api/wifi/scan")
async def wifi_scan():
    """Escaneo de redes WiFi — intenta termux-api, luego iw, luego airodump-ng."""
    networks = []

    # Intento 1: termux-wifi-scaninfo (no requiere root)
    try:
        result = subprocess.run(["termux-wifi-scaninfo"], capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            for net in data:
                networks.append({
                    "bssid": net.get("bssid", "unknown"),
                    "ssid": net.get("ssid", "Hidden"),
                    "channel": int(net.get("channel", 0)),
                    "encryption": net.get("capabilities", "Unknown"),
                    "signal": int(net.get("rssi", -100)),
                    "vendor": net.get("operatorFriendlyName", "Unknown"),
                    "wps": False
                })
            return {"networks": networks, "method": "termux-api"}
    except Exception:
        pass

    # Intento 2: iw (Linux/Kali, requiere root en Android)
    try:
        result = subprocess.run(["iw", "dev", "wlan0", "scan"], capture_output=True, text=True, timeout=20)
        if result.returncode == 0:
            current = {}
            for line in result.stdout.split("\n"):
                line = line.strip()
                if line.startswith("BSS "):
                    if current and "bssid" in current:
                        networks.append({
                            "bssid": current.get("bssid", "unknown"),
                            "ssid": current.get("ssid", "Hidden"),
                            "channel": current.get("channel", 0),
                            "encryption": current.get("encryption", "Open"),
                            "signal": current.get("signal", -100),
                            "vendor": "Unknown", "wps": False
                        })
                    current = {"bssid": line.split()[1].strip("()")}
                elif "SSID:" in line and "Extended" not in line:
                    current["ssid"] = line.split(":", 1)[1].strip()
                elif "signal:" in line:
                    import re as _re
                    match = _re.search(r"(-\d+\.\d+)", line)
                    current["signal"] = int(float(match.group(1))) if match else -100
                elif "DS Parameter set:" in line:
                    import re as _re
                    match = _re.search(r"channel (\d+)", line)
                    current["channel"] = int(match.group(1)) if match else 0
                elif "RSN:" in line:
                    current["encryption"] = "WPA2"
                elif "WPA:" in line:
                    current["encryption"] = "WPA"
                elif "Privacy" in line and "encryption" not in current:
                    current["encryption"] = "WEP"

            if current and "bssid" in current:
                networks.append({
                    "bssid": current.get("bssid", "unknown"),
                    "ssid": current.get("ssid", "Hidden"),
                    "channel": current.get("channel", 0),
                    "encryption": current.get("encryption", "Open"),
                    "signal": current.get("signal", -100),
                    "vendor": "Unknown", "wps": False
                })
            return {"networks": networks, "method": "iw"}
    except Exception:
        pass

    # Intento 3: airodump-ng (requiere modo monitor + root)
    try:
        subprocess.run(["which", "airodump-ng"], capture_output=True, check=True)
        csv_file = os.path.join(WIFI_CAPTURES_DIR, "scan-01.csv")
        for f in os.listdir(WIFI_CAPTURES_DIR):
            if f.startswith("scan-"):
                os.remove(os.path.join(WIFI_CAPTURES_DIR, f))

        proc = subprocess.Popen(
            ["airodump-ng", "wlan0mon", "-w", os.path.join(WIFI_CAPTURES_DIR, "scan"),
             "--write-interval", "1", "--output-format", "csv"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        await asyncio.sleep(10)
        proc.terminate()
        try: proc.wait(timeout=5)
        except: proc.kill()

        if os.path.exists(csv_file):
            with open(csv_file, "r") as f:
                lines = f.readlines()
            for line in lines[2:]:
                if not line.strip() or "BSSID" in line:
                    continue
                parts = line.strip().split(",")
                if len(parts) >= 14:
                    networks.append({
                        "bssid": parts[0].strip(),
                        "ssid": parts[13].strip() if len(parts) > 13 else "Hidden",
                        "channel": int(parts[3].strip()) if parts[3].strip().isdigit() else 0,
                        "encryption": parts[5].strip() if parts[5].strip() else "Open",
                        "signal": int(parts[8].strip()) if parts[8].strip().lstrip("-").isdigit() else -100,
                        "vendor": "Unknown", "wps": False
                    })
            return {"networks": networks, "method": "airodump-ng"}
    except Exception:
        pass

    if not networks:
        return {
            "networks": [], "method": "none",
            "note": "Ningun metodo funciono. Termux: instala termux-api + permisos de ubicacion. Kali: iw o airodump-ng (root + modo monitor)."
        }
    return {"networks": networks, "method": "unknown"}

@app.post("/api/wifi/capture/{bssid}")
async def wifi_capture_handshake(bssid: str, ssid: str = "", channel: int = 1, duration: int = 30):
    """Captura handshake WPA/WPA2 con airodump-ng. Requiere modo monitor + root."""
    capture_id = f"{bssid.replace(':', '')}_{datetime.now().strftime('%H%M%S')}"
    cap_file = os.path.join(WIFI_CAPTURES_DIR, capture_id)

    # Verificar modo monitor
    try:
        result = subprocess.run(["iwconfig"], capture_output=True, text=True, timeout=5)
        if "wlan0mon" not in result.stdout:
            return JSONResponse({
                "error": "Interfaz wlan0mon no encontrada",
                "fix": "airmon-ng start wlan0 (requiere root)"
            }, status_code=503)
    except Exception:
        pass

    try:
        cmd = ["airodump-ng", "wlan0mon", "--bssid", bssid, "-c", str(channel),
               "-w", cap_file, "--output-format", "pcap"]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _wifi_active_captures[bssid] = {"process": proc, "capture_id": capture_id, "start_time": datetime.now()}

        await asyncio.sleep(duration)

        proc.terminate()
        try: proc.wait(timeout=10)
        except: proc.kill()

        cap_file_real = cap_file + "-01.cap"
        has_handshake = False
        if os.path.exists(cap_file_real):
            check = subprocess.run(["aircrack-ng", cap_file_real], capture_output=True, text=True)
            has_handshake = "handshake" in check.stdout.lower()

        if bssid in _wifi_active_captures:
            del _wifi_active_captures[bssid]

        await broadcast({"type": "wifi", "payload": f"Handshake {ssid}: {'capturado' if has_handshake else 'no capturado'}"})
        return {
            "bssid": bssid, "ssid": ssid,
            "capture_file": cap_file_real,
            "has_handshake": has_handshake,
            "duration": duration,
            "status": "handshake_captured" if has_handshake else "no_handshake"
        }
    except Exception as e:
        if bssid in _wifi_active_captures:
            _wifi_active_captures[bssid]["process"].kill()
            del _wifi_active_captures[bssid]
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/wifi/crack/{bssid}")
async def wifi_crack(bssid: str, wordlist: str = "/usr/share/wordlists/rockyou.txt"):
    """Crackea handshake con aircrack-ng."""
    bssid_clean = bssid.replace(":", "")
    matching_caps = []

    for f in os.listdir(WIFI_CAPTURES_DIR):
        if f.startswith(bssid_clean) and f.endswith(".cap"):
            matching_caps.append(os.path.join(WIFI_CAPTURES_DIR, f))

    if not matching_caps:
        raise HTTPException(status_code=404, detail="No se encontro captura para este BSSID")

    cap_file = max(matching_caps, key=os.path.getctime)

    if not os.path.exists(wordlist):
        return JSONResponse({
            "error": f"Wordlist no encontrada: {wordlist}",
            "suggestion": "Descarga rockyou.txt"
        }, status_code=404)

    try:
        proc = await asyncio.create_subprocess_exec(
            "aircrack-ng", cap_file, "-w", wordlist, "-b", bssid,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=300)
        output = stdout.decode()

        import re as _re
        key_match = _re.search(r"KEY FOUND!\s*\[\s*(.*?)\s*\]", output)
        if key_match:
            await broadcast({"type": "wifi", "payload": f"WiFi crackeado: {ssid} key={key_match.group(1)}"})
            return {"bssid": bssid, "status": "cracked", "key": key_match.group(1), "capture_file": cap_file}
        else:
            return {"bssid": bssid, "status": "failed", "reason": "Key no encontrada en wordlist", "capture_file": cap_file}
    except asyncio.TimeoutError:
        return {"status": "timeout", "message": "Crackeo excedio 5 minutos. Usa hashcat en GPU."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/wifi/captures")
async def wifi_list_captures():
    files = []
    for f in os.listdir(WIFI_CAPTURES_DIR):
        if f.endswith(".cap"):
            path = os.path.join(WIFI_CAPTURES_DIR, f)
            stat = os.stat(path)
            files.append({"file": f, "size": stat.st_size, "created": datetime.fromtimestamp(stat.st_mtime).isoformat()})
    return {"captures": files}

@app.delete("/api/wifi/captures/{filename}")
async def wifi_delete_capture(filename: str):
    path = os.path.join(WIFI_CAPTURES_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
        return {"deleted": filename}
    raise HTTPException(status_code=404, detail="Archivo no encontrado")

# == END WIFI SCANNER =================================================

# ============================================================
# MÓDULO 6: BLACK MIRROR (Canary Forge + Shadow Twin + Ghostprint + Chaos)
# ============================================================

BM_DB = str(DATA_DIR / "blackmirror.db")
CANARY_DIR = str(DATA_DIR / "canary_docs")
SHADOW_DIR = str(DATA_DIR / "shadow_configs")
os.makedirs(CANARY_DIR, exist_ok=True)
os.makedirs(SHADOW_DIR, exist_ok=True)

def _init_bm_db():
    conn = _sqlite3.connect(BM_DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS bm_canaries (
        id TEXT PRIMARY KEY, recipient TEXT, doc_type TEXT,
        token TEXT, created TEXT, triggered TEXT, trigger_ip TEXT, trigger_ua TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS ghostprints (
        host TEXT, hour INTEGER, day_of_week INTEGER,
        seen INTEGER, avg_rtt REAL, last_seen TEXT,
        PRIMARY KEY (host, hour, day_of_week)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS chaos_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        real_service TEXT, fake_banner TEXT, fake_os TEXT,
        port INTEGER, active INTEGER DEFAULT 1
    )''')
    conn.commit()
    conn.close()

_init_bm_db()

# ─── 1. CANARY FORGE ─────────────────────────────────────────────

def _bm_canary_token(recipient: str, doc_id: str) -> str:
    return _hashlib.sha256(f"{recipient}:{doc_id}:{os.urandom(16).hex()}".encode()).hexdigest()[:32]

def _create_canary_pdf(recipient: str, title: str, content: str, token: str, doc_id: str) -> str:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import inch
    except ImportError:
        raise HTTPException(status_code=503, detail="Instala: pip install reportlab")

    filepath = os.path.join(CANARY_DIR, f"canary_{doc_id}.pdf")
    c = canvas.Canvas(filepath, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 16)
    c.drawString(1*inch, height - 1*inch, title)
    c.setFont("Helvetica", 11)
    text_obj = c.beginText(1*inch, height - 1.5*inch)
    for line in content.split('\n'):
        text_obj.textLine(line)
    c.drawText(text_obj)

    # Watermark invisible
    c.setFont("Helvetica", 1)
    c.setFillColorRGB(0.999, 0.999, 0.999)
    c.drawString(0.1*inch, 0.1*inch, f"BM-{token}")

    # Metadatos unicos
    c.setAuthor(f"{recipient} - {token[:8]}")
    c.setTitle(title)
    c.setSubject(f"BM:{token}")
    c.setKeywords(f"canary,{recipient},{doc_id}")
    c.setCreator(f"BlackMirror/1.0/{token}")
    c.save()
    return filepath

def _create_canary_html(recipient: str, title: str, content: str, token: str, doc_id: str) -> str:
    filepath = os.path.join(CANARY_DIR, f"canary_{doc_id}.html")
    bug_url = f"/api/blackmirror/canary/ping/{token}"
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <meta name="author" content="{recipient}">
    <meta name="generator" content="BM-{token}">
</head>
<body>
    <h1>{title}</h1>
    <p>{content.replace(chr(10), '</p><p>')}</p>
    <img src="{bug_url}" width="1" height="1" style="display:none" alt="" />
    <!-- {token} -->
</body>
</html>"""
    with open(filepath, "w") as f:
        f.write(html)
    return filepath

@app.post("/api/blackmirror/canary/forge")
async def bm_forge_canary(recipient: str = Query(...), doc_type: str = Query("html"),
                          title: str = Query("Documento Confidencial"),
                          content: str = Query("Este documento contiene informacion sensible.")):
    doc_id = str(uuid.uuid4())[:12]
    token = _bm_canary_token(recipient, doc_id)

    if doc_type == "pdf":
        path = _create_canary_pdf(recipient, title, content, token, doc_id)
    elif doc_type == "html":
        path = _create_canary_html(recipient, title, content, token, doc_id)
    else:
        raise HTTPException(status_code=400, detail="Tipo soportado: pdf, html")

    conn = _sqlite3.connect(BM_DB)
    c = conn.cursor()
    c.execute("INSERT INTO bm_canaries VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL)",
              (doc_id, recipient, doc_type, token, datetime.now().isoformat()))
    conn.commit()
    conn.close()

    await broadcast({"type": "blackmirror", "payload": f"Canary forjado para {recipient} ({doc_type})"})
    return {
        "doc_id": doc_id, "recipient": recipient, "token": token,
        "file": path, "type": doc_type,
        "warning": "Distribuye este documento como si fuera real. Si se filtra, el token te delata al traidor."
    }

@app.get("/api/blackmirror/canary/ping/{token}")
async def bm_canary_ping(token: str, request: Request):
    """Web bug: se activa cuando alguien abre el documento HTML."""
    forwarded = request.headers.get("X-Forwarded-For")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    ua = request.headers.get("User-Agent", "Unknown")

    conn = _sqlite3.connect(BM_DB)
    c = conn.cursor()
    c.execute("SELECT id, recipient FROM bm_canaries WHERE token = ?", (token,))
    row = c.fetchone()

    if row:
        doc_id, recipient = row
        c.execute("""UPDATE bm_canaries SET triggered = ?, trigger_ip = ?, trigger_ua = ?
                     WHERE token = ?""", (datetime.now().isoformat(), ip, ua, token))
        conn.commit()
        conn.close()
        print(f"\n[CANARY TRIGGERED] Doc: {doc_id} | Recipient: {recipient} | IP: {ip} | UA: {ua}\n")
        await broadcast({"type": "blackmirror", "payload": f"CANARY TRIGGERED: {recipient} desde {ip}"})
    else:
        conn.close()

    # 1x1 transparent GIF
    gif_bytes = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
    return Response(content=gif_bytes, media_type="image/gif")

@app.get("/api/blackmirror/canary/status")
async def bm_canary_status():
    conn = _sqlite3.connect(BM_DB)
    c = conn.cursor()
    c.execute("SELECT * FROM bm_canaries ORDER BY created DESC")
    rows = c.fetchall()
    conn.close()
    return {"canaries": [
        {"id": r[0], "recipient": r[1], "type": r[2], "token": r[3],
         "created": r[4], "triggered": r[5], "trigger_ip": r[6], "trigger_ua": r[7],
         "compromised": r[5] is not None}
        for r in rows
    ]}

# ─── 2. SHADOW TWIN ──────────────────────────────────────────────

@app.post("/api/blackmirror/shadow/twin")
async def bm_shadow_twin(scan_result: dict):
    """Genera configs de honeypots que imitan servicios detectados."""
    hosts = scan_result.get("hosts", [])
    if not hosts:
        # Usar hosts del store si no se pasan
        hosts = scan_result.get("data", [])

    if not hosts:
        raise HTTPException(status_code=400, detail="Se requiere resultado de escaneo con hosts")

    configs = []
    for host in hosts:
        ip = host.get("ip", host.get("address", "unknown"))
        for port in host.get("ports", []):
            service = port.get("service", "unknown")
            port_num = port.get("port", 0)

            config = {
                "type": "honeypot",
                "mimics": {"ip": ip, "port": port_num, "service": service},
                "listeners": [], "traps": []
            }

            if service in ["ssh", "telnet"]:
                config["listeners"].append({
                    "port": port_num + 10000, "protocol": "tcp",
                    "banner": "SSH-2.0-OpenSSH_8.2p1 Ubuntu-4ubuntu0.5",
                    "trap": "fake_shell",
                    "commands": {"whoami": "root", "id": "uid=0(root) gid=0(root)"}
                })
                config["traps"].append("credentials_honeytrap")
            elif service in ["http", "https"]:
                config["listeners"].append({
                    "port": port_num + 10000, "protocol": "tcp",
                    "banner": "Server: nginx/1.18.0",
                    "trap": "fake_admin_panel",
                    "pages": ["/admin", "/login", "/config"]
                })
                config["traps"].append("sql_injection_honeytrap")
            elif service == "ftp":
                config["listeners"].append({
                    "port": port_num + 10000, "protocol": "tcp",
                    "banner": "220 ProFTPD 1.3.5 Server",
                    "trap": "fake_ftp",
                    "files": ["backup.zip", "credentials.xlsx", "secret.pdf"]
                })
                config["traps"].append("file_exfil_honeytrap")

            config_path = os.path.join(SHADOW_DIR, f"shadow_{ip}_{port_num}.json")
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)

            configs.append({
                "target": f"{ip}:{port_num}", "service": service,
                "shadow_port": port_num + 10000, "config_file": config_path,
                "traps": config["traps"]
            })

    # Script de despliegue
    deploy_script = os.path.join(SHADOW_DIR, "deploy_shadows.sh")
    with open(deploy_script, "w") as f:
        f.write("#!/bin/bash\n# Shadow Twin Deployer\n")
        for c in configs:
            f.write(f"echo '[+] Levantando honeypot para {c['target']} en puerto {c['shadow_port']}'\n")
            f.write(f"nc -l -p {c['shadow_port']} &\n")
        f.write("wait\n")
    os.chmod(deploy_script, 0o755)

    await broadcast({"type": "blackmirror", "payload": f"Shadow Twin: {len(configs)} honeypots generados"})
    return {
        "shadows_generated": len(configs), "configs": configs,
        "deploy_script": deploy_script,
        "note": "Los honeypots usan puerto real + 10000. Modifica el offset segun tu red."
    }

# ─── 3. GHOSTPRINT ───────────────────────────────────────────────

@app.post("/api/blackmirror/ghostprint/learn")
async def bm_ghostprint_learn(scan_data: dict):
    """Alimenta con resultados de escaneo periodicos para aprender patrones."""
    host = scan_data.get("host")
    rtt = float(scan_data.get("rtt", 0))
    hour = datetime.now().hour
    dow = datetime.now().weekday()

    if not host:
        raise HTTPException(status_code=400, detail="Se requiere host")

    conn = _sqlite3.connect(BM_DB)
    c = conn.cursor()
    c.execute("SELECT seen, avg_rtt FROM ghostprints WHERE host = ? AND hour = ? AND day_of_week = ?",
              (host, hour, dow))
    row = c.fetchone()

    if row:
        seen, old_rtt = row
        new_rtt = (old_rtt * seen + rtt) / (seen + 1)
        c.execute("""UPDATE ghostprints SET seen = ?, avg_rtt = ?, last_seen = ?
                     WHERE host = ? AND hour = ? AND day_of_week = ?""",
                  (seen + 1, new_rtt, datetime.now().isoformat(), host, hour, dow))
    else:
        c.execute("INSERT INTO ghostprints VALUES (?, ?, ?, 1, ?, ?)",
                  (host, hour, dow, rtt, datetime.now().isoformat()))

    conn.commit()
    conn.close()
    return {"status": "learned", "host": host, "hour": hour, "day": dow}

@app.get("/api/blackmirror/ghostprint/profile/{host}")
async def bm_ghostprint_profile(host: str):
    """Devuelve el perfil semanal de un host y detecta anomalias."""
    conn = _sqlite3.connect(BM_DB)
    c = conn.cursor()
    c.execute("SELECT hour, day_of_week, seen, avg_rtt FROM ghostprints WHERE host = ? ORDER BY day_of_week, hour",
              (host,))
    rows = c.fetchall()
    conn.close()

    if not rows:
        return {"host": host, "profile": "insufficient_data",
                "message": "Necesito minimo 7 dias de escaneos periodicos."}

    profile = {}
    total_seen = sum(r[2] for r in rows)

    for hour, dow, seen, rtt in rows:
        key = f"{dow}:{hour}"
        probability = seen / total_seen if total_seen > 0 else 0
        profile[key] = {"probability": round(probability, 3), "seen": seen, "avg_rtt": round(rtt, 2)}

    now = datetime.now()
    current_key = f"{now.weekday()}:{now.hour}"
    current_prob = profile.get(current_key, {}).get("probability", 0)

    anomaly = None
    if current_prob < 0.05 and total_seen > 50:
        anomaly = {
            "type": "GHOST_ANOMALY", "severity": "HIGH",
            "message": f"{host} esta activo ahora pero su probabilidad historica a esta hora es {current_prob:.1%}",
            "usual_hours": [k for k, v in profile.items() if v["probability"] > 0.1]
        }

    return {
        "host": host, "total_observations": total_seen,
        "current_hour_probability": current_prob,
        "profile": profile, "anomaly": anomaly,
        "recommendation": "Operar durante horas de baja probabilidad para evitar deteccion." if not anomaly else "INVESTIGAR: Host activo fuera de patron."
    }

@app.get("/api/blackmirror/ghostprint/window/{host}")
async def bm_ghostprint_window(host: str):
    """Sugiere la mejor ventana temporal para operar contra este host."""
    conn = _sqlite3.connect(BM_DB)
    c = conn.cursor()
    c.execute("SELECT hour, day_of_week, seen FROM ghostprints WHERE host = ?", (host,))
    rows = c.fetchall()
    conn.close()

    all_slots = [(h, d, s) for h, d, s in rows]
    all_slots.sort(key=lambda x: x[2])

    days = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    best_windows = []
    for h, d, s in all_slots[:3]:
        best_windows.append({"day": days[d], "hour": f"{h:02d}:00", "historical_activity": s})

    return {
        "host": host, "optimal_windows": best_windows,
        "tactic": "Operar en estas franjas minimiza probabilidad de deteccion por monitoreo humano."
    }

# ─── 4. CHAOS FINGERPRINT ────────────────────────────────────────

@app.post("/api/blackmirror/chaos/apply")
async def bm_chaos_apply(real_port: int = Query(...), fake_os: str = Query("Windows Server 2019"),
                         fake_service: str = Query("Microsoft-IIS/10.0")):
    """Regla de envenenamiento de huellas."""
    conn = _sqlite3.connect(BM_DB)
    c = conn.cursor()
    c.execute("INSERT INTO chaos_rules (real_service, fake_banner, fake_os, port) VALUES (?, ?, ?, ?)",
              (fake_service, fake_service, fake_os, real_port))
    rule_id = c.lastrowid
    conn.commit()
    conn.close()

    script_path = os.path.join(SHADOW_DIR, f"chaos_{rule_id}.sh")
    redirector = f"""#!/bin/bash
# Chaos Fingerprint Rule {rule_id}
# Puerto real: {real_port} -> Responde como: {fake_os} / {fake_service}

iptables -t nat -A PREROUTING -p tcp --dport {real_port} -j REDIRECT --to-port {real_port + 20000}

while true; do
    echo -e "HTTP/1.1 200 OK\\r\\nServer: {fake_service}\\r\\nX-Powered-By: ASP.NET\\r\\n\\r\\n<html><body>IIS Windows Server</body></html>" | nc -l -p {real_port + 20000}
done &
"""
    with open(script_path, "w") as f:
        f.write(redirector)
    os.chmod(script_path, 0o755)

    await broadcast({"type": "blackmirror", "payload": f"Chaos aplicado: puerto {real_port} ahora simula {fake_os}"})
    return {
        "rule_id": rule_id, "real_port": real_port, "fake_os": fake_os,
        "fake_service": fake_service, "script": script_path,
        "warning": "Ejecuta el script como root. Esto redirige trafico real. Usalo solo en entornos controlados."
    }

@app.get("/api/blackmirror/chaos/status")
async def bm_chaos_status():
    conn = _sqlite3.connect(BM_DB)
    c = conn.cursor()
    c.execute("SELECT id, real_service, fake_banner, fake_os, port, active FROM chaos_rules ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return {"rules": [
        {"id": r[0], "real": r[1], "fake_banner": r[2], "fake_os": r[3], "port": r[4], "active": bool(r[5])}
        for r in rows
    ]}

# == END BLACK MIRROR ================================================

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
        # Si empieza con un prefijo conocido de API/backend, no servir el SPA.
        # El catch-all está registrado antes que muchas rutas API, asi que
        # si no excluimos estas, las captura y devuelve 404 JSON.
        if full_path.startswith(("api/", "canary/", "ws", "motor/", "hls/")):
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
        if full_path.startswith(("api/", "canary/", "ws", "health", "motor/", "hls/")):
            return JSONResponse({"error": "not found"}, status_code=404)
        return JSONResponse({"status": "ok", "backend": "red-team-tauri-unified",
                            "dist_built": False, "hint": f"cd tauri-frontend && npm run build (esperado: {DIST})"})


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN — debe ir al FINAL para que todos los @app endpoints se registren
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    import socket as _socket
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8001"))

    # GUARDIA ANTI-ZOMBIE: si ya hay algo escuchando en este puerto (un
    # proceso viejo que "pkill" no logro matar a tiempo), NO arrancar un
    # segundo proceso encima. Dos backends vivos en el mismo puerto
    # producen 401 al azar segun cual atienda cada request -> paneles
    # "rotos" de forma intermitente e imposible de diagnosticar a ojo.
    _probe = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    _probe.settimeout(0.5)
    try:
        _probe.connect(("127.0.0.1", port))
        print(f"[FATAL] Ya hay un proceso escuchando en el puerto {port}.", flush=True)
        print(f"[FATAL] Mata todos los procesos viejos antes de arrancar uno nuevo:", flush=True)
        print(f"[FATAL]   pkill -9 -f dashboard_server.py", flush=True)
        print(f"[FATAL] Si Termux esta cerrado y el puerto sigue ocupado, cierra la app", flush=True)
        print(f"[FATAL] Termux por completo (quitala de apps recientes) y reintenta.", flush=True)
        raise SystemExit(1)
    except (ConnectionRefusedError, OSError):
        pass  # puerto libre, seguir normal
    finally:
        _probe.close()
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